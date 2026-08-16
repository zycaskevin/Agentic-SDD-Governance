from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .ci_guard import run_local_gate
from .evidence import verify as verify_dep
from .trust import load_owner_controlled_json


DEFAULT_GATE = Path(".sddgov/merge-gate.json")
AUDIT_EXCLUDES = (
    ":(exclude).sddgov/merge-gate.json",
    ":(exclude).sddgov/reviews/**",
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


def _protected_patterns(root: Path, base_ref: str) -> list[str]:
    try:
        text = _git(root, "show", f"{base_ref}:policies/protected-files.yaml")
    except ValueError as exc:
        raise ValueError("protected-file policy is required at the trusted base") from exc
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


def _trusted_reviewers(root: Path, base_ref: str) -> dict[str, Any]:
    """Prefer base-anchored reviewer authority; use external trust for bootstrap only."""
    try:
        text = _git(root, "show", f"{base_ref}:.sddgov/trusted-reviewers.json")
    except ValueError as exc:
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

    external = os.environ.get("SDDGOV_TRUSTED_REVIEWERS_FILE")
    if not external:
        raise ValueError(
            "trusted reviewer store at the trusted base is in initial empty bootstrap; "
            "bootstrap requires SDDGOV_TRUSTED_REVIEWERS_FILE"
        )
    source = Path(external).expanduser().absolute()
    try:
        source.resolve().relative_to(root)
    except ValueError:
        return load_owner_controlled_json(
            source, "out-of-band trusted reviewer store"
        )
    raise ValueError("out-of-band trusted reviewer store must be outside the repository")


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


def _real_rollback(path: Path) -> bool:
    if not path.is_file():
        return False
    fields: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip().lower()] = value.strip().strip("`")
    required = {"rollback_version", "target", "command", "verify"}
    if not required.issubset(fields) or fields["rollback_version"] != "1.0":
        return False
    forbidden = ("todo", "replace", "unavailable", "<", ">")
    return all(
        fields[key] and not any(token in fields[key].lower() for token in forbidden)
        for key in ("target", "command", "verify")
    )


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
    rollback = _bounded_repository_path(
        root, gate.get("rollback_path"), "rollback"
    )
    if not _real_rollback(rollback):
        raise ValueError("rollback record is missing or incomplete")
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
