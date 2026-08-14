from __future__ import annotations

import base64
import json
import os
import secrets
import stat
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from .merge_gate import (
    DEFAULT_GATE,
    change_digest,
    gate_metadata_digest,
    only_audit_changes_after_review,
)


def _canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=root, check=False, capture_output=True, text=True
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise ValueError(f"git {' '.join(args)} failed: {detail}")
    return completed.stdout.strip()


def _safe_id(value: str, label: str) -> str:
    value = value.strip()
    if not value or len(value) > 128 or any(
        character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
        for character in value
    ):
        raise ValueError(f"{label} must use 1-128 letters, numbers, dot, underscore, or hyphen")
    return value


def _external_path(root: Path, path: Path, label: str) -> Path:
    root = root.resolve()
    expanded = path.expanduser()
    if expanded.is_symlink():
        raise ValueError(f"{label} must not be a symbolic link")
    resolved = expanded.resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        return resolved
    raise ValueError(f"{label} must stay outside the repository")


def _prepare_parent(path: Path) -> None:
    if path.parent.exists():
        if not path.parent.is_dir():
            raise ValueError(f"parent is not a directory: {path.parent}")
        return
    path.parent.mkdir(parents=True, mode=0o700)
    path.parent.chmod(0o700)


def _exclusive_write(path: Path, content: bytes, mode: int) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor: int | None = os.open(path, flags, mode)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = None
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        path.chmod(mode)
    except Exception:
        if descriptor is not None:
            os.close(descriptor)
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        raise


def _public_record(reviewer_id: str, key: Ed25519PrivateKey) -> dict[str, str]:
    public = key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return {
        "reviewer_id": reviewer_id,
        "algorithm": "ed25519",
        "public_key": base64.b64encode(public).decode("ascii"),
        "status": "active",
    }


def bootstrap_reviewer(
    root: Path,
    reviewer_id: str,
    private_key_path: Path,
    trust_path: Path,
) -> dict[str, Any]:
    """Create one independent reviewer identity without exposing private key bytes."""
    root = root.resolve()
    reviewer_id = _safe_id(reviewer_id, "reviewer_id")
    private_key_path = _external_path(root, private_key_path, "private key")
    trust_path = _external_path(root, trust_path, "trusted reviewer store")
    if private_key_path == trust_path:
        raise ValueError("private key and trusted reviewer store must use different paths")
    if private_key_path.exists() or trust_path.exists():
        existing = private_key_path if private_key_path.exists() else trust_path
        raise FileExistsError(f"refusing to overwrite reviewer identity file: {existing}")
    _prepare_parent(private_key_path)
    _prepare_parent(trust_path)

    key = Ed25519PrivateKey.generate()
    private_bytes = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    trust = {"schema_version": "1.0", "reviewers": [_public_record(reviewer_id, key)]}
    trust_bytes = json.dumps(trust, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
    key_created = False
    try:
        _exclusive_write(private_key_path, private_bytes, 0o600)
        key_created = True
        _exclusive_write(trust_path, trust_bytes, 0o600)
    except Exception:
        if key_created and private_key_path.is_file():
            private_key_path.unlink()
        raise

    return {
        "ok": True,
        "reviewer_id": reviewer_id,
        "private_key_path": str(private_key_path),
        "trusted_reviewers_file": str(trust_path),
        "github_variable_name": "SDDGOV_TRUSTED_REVIEWERS_JSON",
        "github_variable_value": json.dumps(
            trust, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ),
        "private_key_exported": False,
    }


def export_trust(root: Path, trust_path: Path) -> str:
    trust_path = _external_path(root.resolve(), trust_path, "trusted reviewer store")
    trust = _load_trust(trust_path)
    return json.dumps(trust, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _load_trust(path: Path) -> dict[str, Any]:
    if path.is_symlink():
        raise ValueError("trusted reviewer store must not be a symbolic link")
    try:
        details = path.stat()
    except OSError as exc:
        raise ValueError(f"trusted reviewer store is unavailable: {exc}") from exc
    if not stat.S_ISREG(details.st_mode):
        raise ValueError("trusted reviewer store must be a regular file")
    if os.name != "nt" and details.st_mode & 0o077:
        raise ValueError("trusted reviewer store must have owner-only permissions (0600)")
    if os.name != "nt" and details.st_uid != os.geteuid():
        raise ValueError("trusted reviewer store must be owned by the current user")
    if details.st_nlink != 1:
        raise ValueError("trusted reviewer store must not be hard-linked")
    try:
        trust = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid trusted reviewer store: {exc}") from exc
    if (
        not isinstance(trust, dict)
        or set(trust) != {"schema_version", "reviewers"}
        or trust.get("schema_version") != "1.0"
        or not isinstance(trust.get("reviewers"), list)
    ):
        raise ValueError("trusted reviewer store has an invalid contract")
    seen: set[str] = set()
    for record in trust["reviewers"]:
        if (
            not isinstance(record, dict)
            or set(record) != {"reviewer_id", "algorithm", "public_key", "status"}
            or not isinstance(record.get("reviewer_id"), str)
            or not record["reviewer_id"].strip()
            or record.get("algorithm") != "ed25519"
            or record.get("status") not in {"active", "revoked"}
            or not isinstance(record.get("public_key"), str)
        ):
            raise ValueError("trusted reviewer store contains an invalid reviewer record")
        if record["reviewer_id"] in seen:
            raise ValueError("trusted reviewer store contains duplicate reviewer_id")
        seen.add(record["reviewer_id"])
        try:
            public = base64.b64decode(record["public_key"], validate=True)
            Ed25519PublicKey.from_public_bytes(public)
        except (ValueError, TypeError) as exc:
            raise ValueError("trusted reviewer store contains an invalid public key") from exc
    return trust


def _load_owner_only_private_key(path: Path) -> Ed25519PrivateKey:
    if path.is_symlink():
        raise ValueError("private key must not be a symbolic link")
    try:
        details = path.stat()
    except OSError as exc:
        raise ValueError(f"private key is unavailable: {exc}") from exc
    if not stat.S_ISREG(details.st_mode):
        raise ValueError("private key must be a regular file")
    if os.name != "nt" and details.st_mode & 0o077:
        raise ValueError("private key must have owner-only permissions (0600)")
    if os.name != "nt" and details.st_uid != os.geteuid():
        raise ValueError("private key must be owned by the current user")
    if details.st_nlink != 1:
        raise ValueError("private key must not be hard-linked")
    try:
        key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    except (OSError, ValueError, TypeError, UnsupportedAlgorithm) as exc:
        raise ValueError("private key is not a valid unencrypted PEM key") from exc
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("private key must be Ed25519")
    return key


def _review_binding(root: Path, base_ref: str, gate_path: Path) -> dict[str, Any]:
    if _git(root, "status", "--porcelain"):
        raise ValueError("review signing requires a clean exact-HEAD worktree")
    resolved_gate = (root / gate_path).resolve()
    try:
        resolved_gate.relative_to(root)
    except ValueError as exc:
        raise ValueError("merge gate must stay inside the repository") from exc
    try:
        gate = json.loads(resolved_gate.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid merge gate: {exc}") from exc
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
    if not isinstance(gate, dict) or set(gate) != required or gate.get("schema_version") != "1.0":
        raise ValueError("merge gate has an invalid contract")
    base_sha = _git(root, "rev-parse", "--verify", f"{base_ref}^{{commit}}")
    if gate["base_sha"] != base_sha:
        raise ValueError("merge gate base_sha does not match the independently selected base")
    current_head = _git(root, "rev-parse", "HEAD")
    if not only_audit_changes_after_review(root, gate["head_sha"], current_head):
        raise ValueError("merge gate head_sha is not the exact reviewed Head or has non-audit descendants")
    actual_digest = change_digest(root, base_ref)
    if gate["change_digest"] != actual_digest:
        raise ValueError("merge gate change_digest does not match the exact executable change")
    return {
        "gate": gate,
        "change_digest": actual_digest,
        "gate_metadata_digest": gate_metadata_digest(gate),
    }


def sign_protected_review(
    root: Path,
    reviewer_id: str,
    private_key_path: Path,
    trust_path: Path,
    review_id: str,
    output_path: Path,
    *,
    base_ref: str | None = None,
    gate_path: Path = DEFAULT_GATE,
    valid_hours: float = 1.0,
    approved: bool = False,
) -> dict[str, Any]:
    """Sign the exact reviewed change on an independent host."""
    root = root.resolve()
    reviewer_id = _safe_id(reviewer_id, "reviewer_id")
    review_id = _safe_id(review_id, "review_id")
    if not approved:
        raise ValueError("review receipt requires an explicit approved verdict")
    if valid_hours <= 0 or valid_hours > 24:
        raise ValueError("review receipt validity must be greater than 0 and at most 24 hours")
    preliminary_gate_path = (root / gate_path).resolve()
    try:
        preliminary_gate_path.relative_to(root)
    except ValueError as exc:
        raise ValueError("merge gate must stay inside the repository") from exc
    try:
        preliminary_gate = json.loads(preliminary_gate_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid merge gate: {exc}") from exc
    if isinstance(preliminary_gate, dict) and reviewer_id == preliminary_gate.get("builder_id"):
        raise ValueError("reviewer must be independent of the Builder")
    private_key_path = _external_path(root, private_key_path, "private key")
    trust_path = _external_path(root, trust_path, "trusted reviewer store")
    key = _load_owner_only_private_key(private_key_path)
    trust = _load_trust(trust_path)
    public_record = _public_record(reviewer_id, key)
    matching = [
        record
        for record in trust["reviewers"]
        if isinstance(record, dict)
        and record.get("reviewer_id") == reviewer_id
        and record.get("status") == "active"
    ]
    if len(matching) != 1 or matching[0] != public_record:
        raise ValueError("private key does not match the active reviewer in the trust store")

    requested_output = output_path.expanduser()
    if requested_output.is_symlink():
        raise ValueError("review receipt must not be a symbolic link")
    output_path = requested_output.resolve()
    review_root = (root / ".sddgov/reviews").resolve()
    try:
        relative_output = output_path.relative_to(root)
        output_path.relative_to(review_root)
    except ValueError as exc:
        raise ValueError("review receipt must stay under .sddgov/reviews") from exc
    if output_path.exists() or output_path.is_symlink():
        raise FileExistsError(f"refusing to overwrite review receipt: {output_path}")
    if base_ref is None:
        raise ValueError(
            "base_ref is required; obtain the exact Pull Request base independently"
        )
    binding = _review_binding(root, base_ref, gate_path)
    gate = binding["gate"]
    if reviewer_id == gate["builder_id"]:
        raise ValueError("reviewer must be independent of the Builder")
    if gate["protected_file_review"] != relative_output.as_posix():
        raise ValueError("review receipt output does not match merge gate protected_file_review")

    now = datetime.now(timezone.utc).replace(microsecond=0)
    review = {
        "review_id": review_id,
        "reviewer_id": reviewer_id,
        "builder_id": gate["builder_id"],
        "change_digest": binding["change_digest"],
        "gate_metadata_digest": binding["gate_metadata_digest"],
        "verdict": "approved",
        "issued_at": now.isoformat().replace("+00:00", "Z"),
        "expires_at": (now + timedelta(hours=valid_hours)).isoformat().replace("+00:00", "Z"),
        "nonce": secrets.token_urlsafe(18),
    }
    envelope = {
        "schema_version": "1.0",
        "algorithm": "ed25519",
        "review": review,
        "signature": base64.b64encode(key.sign(_canonical(review))).decode("ascii"),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _exclusive_write(
        output_path,
        json.dumps(envelope, ensure_ascii=False, indent=2).encode("utf-8") + b"\n",
        0o644,
    )
    return {
        "ok": True,
        "state": "SIGNED",
        "review_id": review_id,
        "reviewer_id": reviewer_id,
        "receipt_path": relative_output.as_posix(),
        "expires_at": review["expires_at"],
        "private_key_exported": False,
    }
