from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from importlib import resources
from pathlib import Path, PurePosixPath
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .ci_guard import run_local_gate
from .evidence import verify as verify_dep
from .trust import load_control_plane_json, load_owner_controlled_json


DEFAULT_GATE = Path(".sddgov/merge-gate.json")
LEGACY_ROLLBACK_V1_BOOTSTRAP_BASE_SHA = (
    "f44cb5f4897f6c821f817fcf178581b43777163a"
)
LEGACY_ROLLBACK_V1_BOOTSTRAP_PATH = (
    "evidence/DEP-SDG-SECURITY-HARDENING-EXP8-001/rollback.md"
)
ROLLBACK_V2_POSTCONDITION_BOOTSTRAP_BASE_SHA = (
    "ce08f48c5d7c4232e9c0154dabb3b43c63b920c1"
)
ROLLBACK_V2_POSTCONDITION_BOOTSTRAP_PATH = (
    "evidence/DEP-RELEASE-READINESS-HARDENING-010/rollback.md"
)
AUDIT_EXCLUDES = (
    ":(exclude).sddgov/merge-gate.json",
    ":(exclude).sddgov/reviews/**",
)
FIRST_CONSUMER_BASE_MARKERS = (
    "policies/protected-files.yaml",
    ".agentic-sdd-governance/manifest.json",
    ".sddgov/project.json",
    ".sddgov/trusted-reviewers.json",
    ".github/workflows/governance.yml",
)


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=root, check=False, capture_output=True, text=True
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise ValueError(f"git {' '.join(args)} failed: {detail}")
    return completed.stdout.strip()


def change_digest(root: Path, base_ref: str) -> str:
    """Bind review and evidence to the executable change while excluding audit receipts."""
    patch = _git(
        root,
        "diff",
        "--binary",
        f"{base_ref}...HEAD",
        "--",
        ".",
        *AUDIT_EXCLUDES,
    ).encode("utf-8")
    return hashlib.sha256(patch).hexdigest()


def compute_change_digest(root: Path, base_ref: str) -> dict[str, str]:
    root = root.resolve()
    base_sha = _git(root, "rev-parse", "--verify", f"{base_ref}^{{commit}}")
    return {
        "base_ref": base_ref,
        "base_sha": base_sha,
        "head_sha": _git(root, "rev-parse", "HEAD"),
        "change_digest": change_digest(root, base_ref),
    }


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must contain a JSON object")
    return value


def _bounded_repository_path(root: Path, relative: Any, label: str) -> Path:
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise ValueError(f"{label} path is invalid")
    pure = PurePosixPath(relative)
    if (
        pure.is_absolute()
        or str(pure) != relative
        or any(part in {"", ".", ".."} for part in pure.parts)
    ):
        raise ValueError(f"{label} path escapes or is not normalized")
    current = root
    for part in pure.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"{label} path contains a symlink")
    resolved = current.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"{label} path escapes the repository") from exc
    return resolved


def _canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def gate_metadata_digest(gate: dict[str, Any]) -> str:
    """Bind review to the gate fields that affect verification decisions."""
    required = (
        "schema_version",
        "base_sha",
        "head_sha",
        "risk_level",
        "builder_id",
        "change_digest",
        "deps",
        "rollback_path",
    )
    missing = [key for key in required if key not in gate]
    if missing:
        raise ValueError("merge gate metadata is missing: " + ", ".join(missing))
    metadata = {key: gate[key] for key in required}
    return hashlib.sha256(_canonical(metadata)).hexdigest()


def compute_gate_metadata_digest(
    root: Path, gate_path: Path = DEFAULT_GATE
) -> dict[str, str]:
    root = root.resolve()
    gate = _load_json(root / gate_path, str(gate_path))
    return {"gate_metadata_digest": gate_metadata_digest(gate)}


def _parse_time(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"review receipt {field} must be an RFC3339 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"review receipt {field} must be an RFC3339 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"review receipt {field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _verify_review_receipt(
    root: Path,
    relative: str,
    *,
    builder_id: str,
    digest: str,
    metadata_digest: str,
    trust: dict[str, Any],
) -> dict[str, Any]:
    path = _bounded_repository_path(root, relative, "review receipt")
    try:
        path.relative_to(root / ".sddgov" / "reviews")
    except ValueError as exc:
        raise ValueError("review receipt must stay under .sddgov/reviews") from exc
    envelope = _load_json(path, "protected-file review receipt")
    if (
        set(envelope) != {"schema_version", "algorithm", "review", "signature"}
        or envelope.get("schema_version") != "1.0"
        or envelope.get("algorithm") != "ed25519"
        or not isinstance(envelope.get("review"), dict)
        or not isinstance(envelope.get("signature"), str)
    ):
        raise ValueError("protected-file review receipt has an invalid contract")
    review = envelope["review"]
    required = {
        "review_id",
        "reviewer_id",
        "builder_id",
        "change_digest",
        "gate_metadata_digest",
        "verdict",
        "issued_at",
        "expires_at",
        "nonce",
    }
    if set(review) != required or any(
        not isinstance(review.get(field), str) or not review[field].strip()
        for field in required
    ):
        raise ValueError("protected-file review payload has an invalid contract")
    if review["builder_id"] != builder_id or review["reviewer_id"] == builder_id:
        raise ValueError("protected-file review is not independent of the Builder")
    if (
        review["change_digest"] != digest
        or review["gate_metadata_digest"] != metadata_digest
        or review["verdict"] != "approved"
    ):
        raise ValueError("protected-file review does not approve the exact executable change")
    issued_at = _parse_time(review["issued_at"], "issued_at")
    expires_at = _parse_time(review["expires_at"], "expires_at")
    now = datetime.now(timezone.utc)
    if (
        issued_at > now + timedelta(minutes=5)
        or expires_at <= now
        or expires_at <= issued_at
    ):
        raise ValueError("protected-file review receipt is not currently valid")
    if expires_at - issued_at > timedelta(hours=24):
        raise ValueError("protected-file review validity exceeds 24 hours")
    if (
        set(trust) != {"schema_version", "reviewers"}
        or trust.get("schema_version") != "1.0"
        or not isinstance(trust.get("reviewers"), list)
    ):
        raise ValueError("trusted reviewer store has an invalid contract")
    seen: set[str] = set()
    for row in trust["reviewers"]:
        if (
            not isinstance(row, dict)
            or set(row) != {"reviewer_id", "algorithm", "public_key", "status"}
            or not isinstance(row.get("reviewer_id"), str)
            or not row["reviewer_id"].strip()
            or row.get("algorithm") != "ed25519"
            or row.get("status") not in {"active", "revoked"}
            or not isinstance(row.get("public_key"), str)
        ):
            raise ValueError("trusted reviewer record has an invalid contract")
        if row["reviewer_id"] in seen:
            raise ValueError("trusted reviewer store contains duplicate reviewer_id")
        seen.add(row["reviewer_id"])
    matches = [
        row
        for row in trust["reviewers"]
        if isinstance(row, dict)
        and row.get("reviewer_id") == review["reviewer_id"]
        and row.get("status") == "active"
    ]
    if len(matches) != 1:
        raise ValueError("review signer is not a unique active trusted reviewer")
    reviewer = matches[0]
    try:
        public_key = base64.b64decode(reviewer["public_key"], validate=True)
        signature = base64.b64decode(envelope["signature"], validate=True)
        Ed25519PublicKey.from_public_bytes(public_key).verify(
            signature, _canonical(review)
        )
    except (ValueError, binascii.Error, InvalidSignature) as exc:
        raise ValueError("protected-file review signature verification failed") from exc
    return review


def _base_has_path(root: Path, base_ref: str, relative: str) -> bool:
    completed = subprocess.run(
        ["git", "cat-file", "-e", f"{base_ref}:{relative}"],
        cwd=root,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return completed.returncode == 0


def _first_consumer_base(root: Path, base_ref: str) -> bool:
    return not any(
        _base_has_path(root, base_ref, marker)
        for marker in FIRST_CONSUMER_BASE_MARKERS
    )


def _parse_protected_patterns(text: str) -> list[str]:
    patterns: list[str] = []
    in_protected = False
    for raw in text.splitlines():
        if raw.strip() == "protected:":
            in_protected = True
            continue
        if in_protected and raw.startswith("  - "):
            patterns.append(raw[4:].strip())
            continue
        if in_protected and raw and not raw.startswith(" "):
            break
    if not patterns:
        raise ValueError("protected-file policy contains no paths")
    return patterns


def _protected_patterns(root: Path, base_ref: str) -> list[str]:
    for relative in (
        "policies/protected-files.yaml",
        ".agentic-sdd-governance/policies/protected-files.yaml",
    ):
        try:
            text = _git(root, "show", f"{base_ref}:{relative}")
        except ValueError:
            continue
        return _parse_protected_patterns(text)
    if not _first_consumer_base(root, base_ref):
        raise ValueError("protected-file policy is required at the trusted base")
    # A first installation has no Base policy.  Use only the verifier package's
    # immutable built-in policy; never fall back to Candidate bytes.
    text = (
        resources.files("sddgov")
        .joinpath("resources", "governance", "policies", "protected-files.yaml")
        .read_text(encoding="utf-8")
    )
    return _parse_protected_patterns(text)


def _external_trusted_reviewers(
    root: Path, *, require_separate_identity: bool = False
) -> dict[str, Any]:
    external = os.environ.get("SDDGOV_TRUSTED_REVIEWERS_FILE")
    if not external:
        raise ValueError(
            "trusted reviewer bootstrap requires SDDGOV_TRUSTED_REVIEWERS_FILE"
        )
    source = Path(external).expanduser().absolute()
    try:
        source.resolve().relative_to(root)
    except ValueError:
        if require_separate_identity:
            return load_control_plane_json(
                source, "first-consumer trusted reviewer store"
            )
        return load_owner_controlled_json(
            source, "out-of-band trusted reviewer store"
        )
    raise ValueError("out-of-band trusted reviewer store must be outside the repository")


def _trusted_reviewers(root: Path, base_ref: str) -> dict[str, Any]:
    """Prefer base-anchored reviewer authority; use external trust for bootstrap only."""
    try:
        text = _git(root, "show", f"{base_ref}:.sddgov/trusted-reviewers.json")
    except ValueError as exc:
        if _first_consumer_base(root, base_ref):
            return _external_trusted_reviewers(
                root, require_separate_identity=True
            )
        raise ValueError("trusted reviewer store is required at the trusted base") from exc
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("trusted reviewer store at trusted base is invalid") from exc
    if (
        not isinstance(value, dict)
        or set(value) != {"schema_version", "reviewers"}
        or value.get("schema_version") != "1.0"
        or not isinstance(value.get("reviewers"), list)
    ):
        raise ValueError("trusted reviewer store at trusted base has an invalid contract")
    base_store = value
    reviewers = base_store["reviewers"]
    if reviewers:
        # A populated Base store is authoritative even when every key is revoked.
        # Falling back here would let a stale bootstrap variable resurrect a key.
        return base_store

    return _external_trusted_reviewers(root)


def _is_protected(path: str, patterns: list[str]) -> bool:
    return any(
        path.startswith(pattern) if pattern.endswith("/") else path == pattern
        for pattern in patterns
    )


def changed_paths(root: Path, start: str, end: str = "HEAD") -> list[str]:
    """Return exact source and destination paths from NUL-delimited Git output."""
    fields = _git(
        root, "diff", "-M", "--name-status", "-z", f"{start}...{end}"
    ).split("\0")
    if fields and fields[-1] == "":
        fields.pop()
    paths: set[str] = set()
    index = 0
    while index < len(fields):
        status = fields[index]
        width = 3 if status.startswith(("R", "C")) else 2
        record = fields[index : index + width]
        if len(record) != width or not status:
            raise ValueError("git diff produced an invalid NUL name-status record")
        paths.update(record[1:])
        index += width
    return sorted(paths)


def only_audit_changes_after_review(
    root: Path, reviewed_head_sha: str, current_head_sha: str
) -> bool:
    completed = subprocess.run(
        ["git", "merge-base", "--is-ancestor", reviewed_head_sha, current_head_sha],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return False
    allowed = (".sddgov/merge-gate.json", ".sddgov/reviews/")
    return all(
        path == allowed[0] or path.startswith(allowed[1])
        for path in changed_paths(root, reviewed_head_sha, current_head_sha)
    )


def _rollback_contract(
    text: str,
    *,
    allow_legacy_v1: bool = False,
    allow_v2_postcondition_bridge: bool = False,
) -> dict[str, str] | None:
    """Validate rollback bytes loaded from the immutable candidate commit.

    Declarative v2 is the normal contract.  One exact legacy v1 form remains as a
    migration bridge for a trusted Base verifier that predates v2; it is an
    allowlist, not a shell parser, and no value from the document is executed.
    """
    fields: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in raw:
            return None
        key, value = raw.split(":", 1)
        if (
            raw != line
            or not key
            or key != key.strip()
            or key != key.lower()
            or key in fields
            or not value.startswith(" ")
            or value.startswith("  ")
            or value[1:] != value[1:].strip()
        ):
            return None
        fields[key] = value[1:]
    target = fields.get("target", "")
    if (
        not target
        or len(target) > 240
        or any(token in target.lower() for token in ("todo", "unavailable", "<", ">"))
    ):
        return None
    version = fields.get("rollback_version")
    if version == "1.0":
        if not allow_legacy_v1 or set(fields) != {
            "rollback_version",
            "target",
            "command",
            "verify",
        }:
            return None
        match = re.fullmatch(r"git revert --no-edit ([0-9a-f]{40})", fields["command"])
        if match is None or fields["verify"] != "python -m pytest":
            return None
        return {"version": version, "rollback_ref": match.group(1)}
    required_v2 = {
        "rollback_version",
        "target",
        "rollback_action",
        "rollback_ref",
        "verify_action",
        "verify_module",
    }
    if version == "2.0":
        if set(fields) != required_v2 or not allow_v2_postcondition_bridge:
            return None
        bridge_comments = (
            "# reconcile_action: setup_agent_from_reverted_source",
            "# reconcile_agent: codex",
            "# reconcile_profile: team-standard",
            "# post_verify_action: doctor_and_python_module",
        )
        lines = text.splitlines()
        if any(lines.count(comment) != 1 for comment in bridge_comments):
            return None
        if fields["rollback_action"] != "git_revert":
            return None
        if not re.fullmatch(r"[0-9a-f]{40}", fields["rollback_ref"]):
            return None
        if fields["verify_action"] != "python_module":
            return None
        if fields["verify_module"] not in {"pytest", "unittest"}:
            return None
        return {
            "version": version,
            "rollback_ref": fields["rollback_ref"],
            "reconcile_action": "setup_agent_from_reverted_source",
            "reconcile_agent": "codex",
            "reconcile_profile": "team-standard",
            "verify_action": "doctor_and_python_module",
            "verify_module": fields["verify_module"],
        }
    required_v3 = required_v2 | {
        "reconcile_action",
        "reconcile_agent",
        "reconcile_profile",
    }
    if set(fields) != required_v3 or version != "3.0":
        return None
    if fields["rollback_action"] != "git_revert":
        return None
    if not re.fullmatch(r"[0-9a-f]{40}", fields["rollback_ref"]):
        return None
    if fields["reconcile_action"] != "setup_agent_from_reverted_source":
        return None
    if fields["reconcile_agent"] not in {"codex", "hermes"}:
        return None
    if fields["reconcile_profile"] not in {
        "solo-fast",
        "team-standard",
        "regulated",
    }:
        return None
    if fields["verify_action"] != "doctor_and_python_module":
        return None
    if fields["verify_module"] not in {"pytest", "unittest"}:
        return None
    return {key: fields[key] for key in required_v3}


def _real_rollback(
    text: str,
    *,
    allow_legacy_v1: bool = False,
    allow_v2_postcondition_bridge: bool = False,
) -> bool:
    return (
        _rollback_contract(
            text,
            allow_legacy_v1=allow_legacy_v1,
            allow_v2_postcondition_bridge=allow_v2_postcondition_bridge,
        )
        is not None
    )


def _rollback_ref_is_in_candidate_range(
    root: Path, rollback_ref: str, *, base_sha: str, reviewed_head_sha: str
) -> bool:
    try:
        resolved = _git(root, "rev-parse", "--verify", f"{rollback_ref}^{{commit}}")
    except ValueError:
        return False
    if resolved != rollback_ref or rollback_ref == base_sha:
        return False
    for older, newer in (
        (base_sha, rollback_ref),
        (rollback_ref, reviewed_head_sha),
    ):
        completed = subprocess.run(
            ["git", "merge-base", "--is-ancestor", older, newer],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            return False
    return True


def _rollback_ref_is_cleanly_revertible(
    root: Path, rollback_ref: str, *, base_sha: str, reviewed_head_sha: str
) -> bool:
    """Prove the declared single-commit rollback applies without conflicts.

    ``git merge-tree`` performs the same three-way merge shape as reverting the
    commit: the rollback commit is the merge base, the reviewed Head is ours,
    and the rollback commit's sole parent is theirs.  An isolated bare Git
    directory prevents repository config, hooks, lazy fetches, or custom merge
    drivers from becoming executable authority.  The result must restore the
    trusted Base outside Evidence/audit paths, not merely avoid conflicts.
    """
    try:
        parent_row = _git(root, "rev-list", "--parents", "-n", "1", rollback_ref)
    except ValueError:
        return False
    parents = parent_row.split()
    if len(parents) != 2 or parents[0] != rollback_ref:
        return False
    try:
        rollback_paths = changed_paths(root, parents[1], rollback_ref)
        descendant_paths = changed_paths(root, rollback_ref, reviewed_head_sha)
    except ValueError:
        return False
    if any(
        path == ".sddgov/merge-gate.json"
        or path.startswith(("evidence/", ".sddgov/reviews/"))
        for path in rollback_paths
    ):
        return False
    if any(not path.startswith("evidence/") for path in descendant_paths):
        return False
    try:
        objects_text = _git(root, "rev-parse", "--git-path", "objects")
        objects = Path(objects_text)
        if not objects.is_absolute():
            objects = root / objects
        objects = objects.resolve(strict=True)
    except (OSError, ValueError):
        return False
    if not objects.is_dir():
        return False

    environment = os.environ.copy()
    for key in tuple(environment):
        if key.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_")) or key in {
            "GIT_DIR",
            "GIT_WORK_TREE",
            "GIT_COMMON_DIR",
            "GIT_OBJECT_DIRECTORY",
            "GIT_ALTERNATE_OBJECT_DIRECTORIES",
            "GIT_CONFIG_COUNT",
        }:
            environment.pop(key, None)
    environment.update(
        {
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_NO_LAZY_FETCH": "1",
            "GIT_NO_REPLACE_OBJECTS": "1",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_OPTIONAL_LOCKS": "0",
        }
    )
    try:
        with tempfile.TemporaryDirectory(prefix="sddgov-rollback-") as temporary:
            isolated_git = Path(temporary) / "git"
            empty_hooks = Path(temporary) / "hooks"
            empty_hooks.mkdir(mode=0o700)
            initialized = subprocess.run(
                [
                    "git",
                    "-c",
                    f"core.hooksPath={empty_hooks}",
                    "-c",
                    "protocol.allow=never",
                    "init",
                    "--bare",
                    "--quiet",
                    "--template=",
                    str(isolated_git),
                ],
                cwd=root,
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=environment,
                timeout=10,
            )
            if initialized.returncode != 0:
                return False
            isolated_environment = dict(environment)
            isolated_environment.update(
                {
                    "GIT_DIR": str(isolated_git),
                    "GIT_ALTERNATE_OBJECT_DIRECTORIES": str(objects),
                }
            )
            completed = subprocess.run(
                [
                    "git",
                    "-c",
                    f"core.hooksPath={empty_hooks}",
                    "-c",
                    "protocol.allow=never",
                    "merge-tree",
                    "--write-tree",
                    "--no-messages",
                    "--merge-base",
                    rollback_ref,
                    reviewed_head_sha,
                    parents[1],
                ],
                cwd=root,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env=isolated_environment,
                timeout=15,
                text=True,
            )
            if completed.returncode != 0 or not re.fullmatch(
                r"[0-9a-f]{40,64}\n?", completed.stdout
            ):
                return False
            result_tree = completed.stdout.strip()
            exact_base_restore = subprocess.run(
                [
                    "git",
                    "-c",
                    "protocol.allow=never",
                    "diff",
                    "--quiet",
                    base_sha,
                    result_tree,
                    "--",
                    ".",
                    ":(exclude)evidence/**",
                    ":(exclude).sddgov/merge-gate.json",
                    ":(exclude).sddgov/reviews/**",
                ],
                cwd=root,
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=isolated_environment,
                timeout=15,
            )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return exact_base_restore.returncode == 0


def _rollback_postcondition_is_green(
    root: Path,
    rollback: dict[str, str],
    *,
    reviewed_head_sha: str,
) -> bool:
    """Execute the closed rollback post-condition only in local verification.

    The privileged hosted verifier never calls this function because it receives
    ``--skip-local-checks``.  A fresh local clone loads the reverted source tree,
    reconciles only managed Agent-governance files, then runs Doctor and the
    allowlisted Python test module without a shell. Candidate-controlled
    reverted CLI and test code still has the local reviewer's process access;
    callers must provide a disposable no-credential, network-isolated runtime.
    """
    if (
        rollback.get("reconcile_action")
        != "setup_agent_from_reverted_source"
        or rollback.get("verify_action") != "doctor_and_python_module"
    ):
        return False
    agent = rollback.get("reconcile_agent")
    profile = rollback.get("reconcile_profile")
    verify_module = rollback.get("verify_module")
    if agent not in {"codex", "hermes"}:
        return False
    if profile not in {"solo-fast", "team-standard", "regulated"}:
        return False
    if verify_module not in {"pytest", "unittest"}:
        return False

    environment = os.environ.copy()
    for key in tuple(environment):
        if key.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_")) or key in {
            "GIT_DIR",
            "GIT_WORK_TREE",
            "GIT_COMMON_DIR",
            "GIT_OBJECT_DIRECTORY",
            "GIT_ALTERNATE_OBJECT_DIRECTORIES",
            "GIT_CONFIG_COUNT",
            "GIT_CONFIG_PARAMETERS",
            "GIT_ATTR_SOURCE",
            "GIT_REPLACE_REF_BASE",
        }:
            environment.pop(key, None)
    environment.update(
        {
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_NO_LAZY_FETCH": "1",
            "GIT_NO_REPLACE_OBJECTS": "1",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_OPTIONAL_LOCKS": "0",
        }
    )

    try:
        with tempfile.TemporaryDirectory(prefix="sddgov-rollback-drill-") as temporary:
            temporary_root = Path(temporary)
            drill = temporary_root / "repository"
            empty_hooks = temporary_root / "hooks"
            empty_hooks.mkdir(mode=0o700)
            commands = (
                (
                    [
                        "git",
                        "-c",
                        f"core.hooksPath={empty_hooks}",
                        "-c",
                        "protocol.file.allow=always",
                        "clone",
                        "--no-local",
                        "--no-checkout",
                        "--quiet",
                        "--template=",
                        str(root),
                        str(drill),
                    ],
                    root,
                    environment,
                    60,
                ),
                (
                    [
                        "git",
                        "-c",
                        f"core.hooksPath={empty_hooks}",
                        "-c",
                        "protocol.allow=never",
                        "checkout",
                        "--detach",
                        "--quiet",
                        reviewed_head_sha,
                    ],
                    drill,
                    environment,
                    30,
                ),
                (
                    [
                        "git",
                        "-c",
                        f"core.hooksPath={empty_hooks}",
                        "-c",
                        "protocol.allow=never",
                        "revert",
                        "--no-commit",
                        rollback["rollback_ref"],
                    ],
                    drill,
                    environment,
                    30,
                ),
            )
            for argv, cwd, command_environment, timeout in commands:
                completed = subprocess.run(
                    argv,
                    cwd=cwd,
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    env=command_environment,
                    timeout=timeout,
                )
                if completed.returncode != 0:
                    return False

            python_environment = dict(environment)
            python_environment["PYTHONPATH"] = str(drill / "src")
            python_commands = [
                [
                    sys.executable,
                    "-m",
                    "sddgov.cli",
                    "setup-agent",
                    str(drill),
                    "--agent",
                    agent,
                    "--profile",
                    profile,
                    "--force",
                ],
                [
                    sys.executable,
                    "-m",
                    "sddgov.cli",
                    "doctor",
                    str(drill),
                ],
            ]
            if verify_module == "pytest":
                python_commands.append([sys.executable, "-m", "pytest"])
            else:
                python_commands.append(
                    [
                        sys.executable,
                        "-m",
                        "unittest",
                        "discover",
                        "-s",
                        "tests",
                        "-v",
                    ]
                )
            for index, argv in enumerate(python_commands):
                completed = subprocess.run(
                    argv,
                    cwd=drill,
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    env=python_environment,
                    timeout=300 if index == len(python_commands) - 1 else 60,
                )
                if completed.returncode != 0:
                    return False
    except (OSError, KeyError, subprocess.TimeoutExpired):
        return False
    return True


def verify_merge(
    root: Path,
    base_ref: str,
    gate_path: Path = DEFAULT_GATE,
    *,
    run_checks: bool = True,
) -> dict[str, Any]:
    root = root.resolve()
    if _git(root, "status", "--porcelain"):
        raise ValueError("merge verification requires a clean exact-HEAD worktree")
    head_sha = _git(root, "rev-parse", "HEAD")
    base_sha = _git(root, "rev-parse", "--verify", f"{base_ref}^{{commit}}")
    gate = _load_json(root / gate_path, str(gate_path))
    required = {
        "schema_version",
        "base_sha",
        "head_sha",
        "risk_level",
        "builder_id",
        "change_digest",
        "deps",
        "rollback_path",
        "protected_file_review",
    }
    if set(gate) != required or gate.get("schema_version") != "1.0":
        raise ValueError("merge gate has an invalid contract")
    if gate.get("risk_level") not in {"L0", "L1", "L2", "L3"}:
        raise ValueError("merge gate risk_level is invalid")
    if gate.get("base_sha") != base_sha:
        raise ValueError("merge gate base_sha does not match the trusted exact base")
    if not isinstance(gate.get("head_sha"), str) or not gate["head_sha"].strip():
        raise ValueError("merge gate head_sha is required")
    if not only_audit_changes_after_review(root, gate["head_sha"], head_sha):
        raise ValueError(
            "merge gate head_sha is not the exact reviewed Head or has non-audit descendants"
        )
    if not isinstance(gate.get("builder_id"), str) or not gate["builder_id"].strip():
        raise ValueError("merge gate builder_id is required")
    actual_digest = change_digest(root, base_ref)
    if gate.get("change_digest") != actual_digest:
        raise ValueError("merge gate change_digest does not match the exact executable change")
    deps = gate.get("deps")
    if not isinstance(deps, list) or any(
        not isinstance(item, str) or not item for item in deps
    ):
        raise ValueError("merge gate deps must be a string array")
    if gate["risk_level"] != "L0" and not deps:
        raise ValueError("L1-L3 Merge requires at least one strict DEP")
    dep_errors: list[str] = []
    for relative in deps:
        dep = _bounded_repository_path(root, relative, "merge DEP")
        dep_errors.extend(
            f"{relative}: {error}"
            for error in verify_dep(dep, strict=True, portable=True)
        )
    if dep_errors:
        raise ValueError("strict DEP verification failed: " + "; ".join(dep_errors))
    rollback_relative = gate.get("rollback_path")
    _bounded_repository_path(root, rollback_relative, "rollback")
    try:
        rollback_text = _git(root, "show", f"{gate['head_sha']}:{rollback_relative}")
    except ValueError as exc:
        raise ValueError("rollback record is missing or incomplete") from exc
    allow_legacy_v1 = (
        base_sha == LEGACY_ROLLBACK_V1_BOOTSTRAP_BASE_SHA
        and rollback_relative == LEGACY_ROLLBACK_V1_BOOTSTRAP_PATH
    )
    allow_v2_postcondition_bridge = (
        base_sha == ROLLBACK_V2_POSTCONDITION_BOOTSTRAP_BASE_SHA
        and rollback_relative == ROLLBACK_V2_POSTCONDITION_BOOTSTRAP_PATH
    )
    rollback = _rollback_contract(
        rollback_text,
        allow_legacy_v1=allow_legacy_v1,
        allow_v2_postcondition_bridge=allow_v2_postcondition_bridge,
    )
    if (
        rollback is None
        or not _rollback_ref_is_in_candidate_range(
            root,
            rollback["rollback_ref"],
            base_sha=base_sha,
            reviewed_head_sha=gate["head_sha"],
        )
        or not _rollback_ref_is_cleanly_revertible(
            root,
            rollback["rollback_ref"],
            base_sha=base_sha,
            reviewed_head_sha=gate["head_sha"],
        )
    ):
        raise ValueError("rollback record is missing or incomplete")
    if run_checks and not _rollback_postcondition_is_green(
        root,
        rollback,
        reviewed_head_sha=gate["head_sha"],
    ):
        raise ValueError("rollback post-condition did not return to Green")
    commits = _git(root, "rev-list", f"{base_ref}..HEAD").splitlines()
    raw = sorted(
        {
            path
            for commit in commits
            for path in _git(root, "ls-tree", "-r", "--name-only", commit).splitlines()
            if "/private/raw/" in f"/{path}"
        }
    )
    if raw:
        raise ValueError("raw evidence is tracked by Git: " + ", ".join(raw))
    changed = changed_paths(root, base_ref)
    protected = [
        path
        for path in changed
        if _is_protected(path, _protected_patterns(root, base_ref))
    ]
    review = gate.get("protected_file_review")
    if protected:
        if not isinstance(review, str) or not review:
            raise ValueError("protected-file changes require a signed independent review receipt")
        verified_review = _verify_review_receipt(
            root,
            review,
            builder_id=gate["builder_id"],
            digest=actual_digest,
            metadata_digest=gate_metadata_digest(gate),
            trust=_trusted_reviewers(root, base_ref),
        )
    elif review is not None:
        raise ValueError("protected_file_review must be null when no protected file changed")
    else:
        verified_review = None
    local_green = run_local_gate(root) if run_checks else {"ok": True, "commands": []}
    if not local_green.get("ok"):
        raise ValueError("Local Green Gate did not pass")
    return {
        "ok": True,
        "state": "MERGE_READY",
        "head_sha": head_sha,
        "base_ref": base_ref,
        "base_sha": base_sha,
        "reviewed_head_sha": gate["head_sha"],
        "change_digest": actual_digest,
        "risk_level": gate["risk_level"],
        "deps_verified": deps,
        "protected_files_changed": protected,
        "protected_file_reviewer": verified_review["reviewer_id"] if verified_review else None,
        "local_green": local_green,
    }
