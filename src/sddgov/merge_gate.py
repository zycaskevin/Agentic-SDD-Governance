from __future__ import annotations

import base64
import binascii
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .ci_guard import run_local_gate
from .evidence import verify as verify_dep


DEFAULT_GATE = Path(".sddgov/merge-gate.json")
AUDIT_EXCLUDES = (
    ":(exclude).sddgov/merge-gate.json",
    ":(exclude).sddgov/reviews/**",
    ":(exclude)evidence/**",
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
    _git(root, "rev-parse", "--verify", base_ref)
    return {
        "base_ref": base_ref,
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


def _canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


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
) -> dict[str, Any]:
    path = (root / relative).resolve()
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
    if review["change_digest"] != digest or review["verdict"] != "approved":
        raise ValueError("protected-file review does not approve the exact executable change")
    issued_at = _parse_time(review["issued_at"], "issued_at")
    expires_at = _parse_time(review["expires_at"], "expires_at")
    now = datetime.now(timezone.utc)
    if issued_at > now or expires_at <= now or expires_at <= issued_at:
        raise ValueError("protected-file review receipt is not currently valid")
    trust = _load_json(
        root / ".sddgov" / "trusted-reviewers.json", "trusted reviewer store"
    )
    if (
        set(trust) != {"schema_version", "reviewers"}
        or trust.get("schema_version") != "1.0"
        or not isinstance(trust.get("reviewers"), list)
    ):
        raise ValueError("trusted reviewer store has an invalid contract")
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
    if set(reviewer) != {"reviewer_id", "algorithm", "public_key", "status"} or reviewer.get("algorithm") != "ed25519":
        raise ValueError("trusted reviewer record has an invalid contract")
    try:
        public_key = base64.b64decode(reviewer["public_key"], validate=True)
        signature = base64.b64decode(envelope["signature"], validate=True)
        Ed25519PublicKey.from_public_bytes(public_key).verify(
            signature, _canonical(review)
        )
    except (ValueError, binascii.Error, InvalidSignature) as exc:
        raise ValueError("protected-file review signature verification failed") from exc
    return review


def _protected_patterns(root: Path) -> list[str]:
    path = root / "policies" / "protected-files.yaml"
    if not path.is_file():
        raise ValueError("policies/protected-files.yaml is required")
    patterns: list[str] = []
    in_protected = False
    for raw in path.read_text(encoding="utf-8").splitlines():
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


def _is_protected(path: str, patterns: list[str]) -> bool:
    return any(path.startswith(pattern) if pattern.endswith("/") else path == pattern for pattern in patterns)


def _real_rollback(path: Path) -> bool:
    if not path.is_file():
        return False
    lines = [
        line.strip()
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    return any("TODO" not in line and "<!--" not in line for line in lines)


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
    _git(root, "rev-parse", "--verify", base_ref)
    gate = _load_json(root / gate_path, str(gate_path))
    required = {
        "schema_version",
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
    if not isinstance(gate.get("builder_id"), str) or not gate["builder_id"].strip():
        raise ValueError("merge gate builder_id is required")
    actual_digest = change_digest(root, base_ref)
    if gate.get("change_digest") != actual_digest:
        raise ValueError("merge gate change_digest does not match the exact executable change")
    deps = gate.get("deps")
    if not isinstance(deps, list) or any(not isinstance(item, str) or not item for item in deps):
        raise ValueError("merge gate deps must be a string array")
    if gate["risk_level"] != "L0" and not deps:
        raise ValueError("L1-L3 Merge requires at least one strict DEP")
    dep_errors: list[str] = []
    for relative in deps:
        dep = (root / relative).resolve()
        try:
            dep.relative_to(root)
        except ValueError as exc:
            raise ValueError("merge DEP escapes the repository") from exc
        dep_errors.extend(f"{relative}: {error}" for error in verify_dep(dep, strict=True))
    if dep_errors:
        raise ValueError("strict DEP verification failed: " + "; ".join(dep_errors))
    rollback = (root / str(gate.get("rollback_path", ""))).resolve()
    try:
        rollback.relative_to(root)
    except ValueError as exc:
        raise ValueError("rollback path escapes the repository") from exc
    if not _real_rollback(rollback):
        raise ValueError("rollback record is missing or incomplete")
    tracked = _git(root, "ls-files").splitlines()
    raw = [path for path in tracked if "/private/raw/" in f"/{path}"]
    if raw:
        raise ValueError("raw evidence is tracked by Git: " + ", ".join(raw))
    changed = _git(root, "diff", "--name-only", f"{base_ref}...HEAD").splitlines()
    protected = [path for path in changed if _is_protected(path, _protected_patterns(root))]
    review = gate.get("protected_file_review")
    if protected:
        if not isinstance(review, str) or not review:
            raise ValueError("protected-file changes require a signed independent review receipt")
        verified_review = _verify_review_receipt(
            root, review, builder_id=gate["builder_id"], digest=actual_digest
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
        "change_digest": actual_digest,
        "risk_level": gate["risk_level"],
        "deps_verified": deps,
        "protected_files_changed": protected,
        "protected_file_reviewer": verified_review["reviewer_id"] if verified_review else None,
        "local_green": local_green,
    }
