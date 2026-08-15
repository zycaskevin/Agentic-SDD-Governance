from __future__ import annotations

import base64
import binascii
import fcntl
import hashlib
import json
import os
import re
import socket
import stat
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .trust import load_control_plane_json


RISK_LEVELS = {"L0", "L1", "L2", "L3"}
SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
ROUTINE_OPERATIONS = {
    "issue",
    "branch",
    "implementation",
    "commit",
    "feature_branch_push",
    "pull_request",
    "review",
    "review_fix",
    "lint",
    "typecheck",
    "test",
    "e2e",
    "security_scan",
    "dependency_conflict",
    "git_conflict",
    "recoverable_retry",
    "integrity_verification",
    "ci",
    "merge",
}
ESCALATION_CATEGORIES = {
    "uncertainty",
    "product_decision",
    "high_risk_operation",
    "operational_action",
    "necessary_uat",
}
HIGH_RISK_CATEGORIES = {
    "production_data_deletion",
    "irreversible_migration",
    "secret_change",
    "permission_boundary_change",
    "real_payment",
    "high_privilege_production_operation",
}
SENSITIVE_EFFECTS = {
    "production",
    "destructive",
    "irreversible",
    "secret_change",
    "permission_boundary_change",
    "real_payment",
    "high_privilege",
}
KNOWN_CATEGORIES = ROUTINE_OPERATIONS | ESCALATION_CATEGORIES | HIGH_RISK_CATEGORIES | {
    "checkpoint",
    "integrity_mismatch",
}
ACTION_REQUIRED_FIELDS = (
    "decision_id",
    "risk_level",
    "why_human_input_is_required",
    "what_agent_already_verified",
    "options",
    "recommended",
    "why",
    "impact_if_no_decision",
    "scope_of_approval",
)
DEPLOY_GUARDS = (
    "all_required_checks_pass",
    "rollback_available",
    "no_unresolved_security_findings",
    "no_destructive_schema_change",
    "no_secret_change",
    "no_permission_boundary_change",
    "health_check_pass",
    "blast_radius_within_policy",
)
L3_NONCE_BROKER = (
    Path("/private/var/db/sddgov/approval-broker.sock")
    if sys.platform == "darwin"
    else Path("/run/sddgov/approval-broker.sock")
)
L3_RUNTIME_CONTEXT_FILE = Path("/etc/sddgov/runtime-context.json")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _stamp(value: datetime | None = None) -> str:
    return (value or _now()).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def _decisions_path(root: Path) -> Path:
    return root / ".sddgov" / "decisions.json"


def _decision_store(root: Path) -> dict[str, Any]:
    data = _read_json(
        _decisions_path(root), {"schema_version": "1.0", "decisions": []}
    )
    if (
        not isinstance(data, dict)
        or data.get("schema_version") != "1.0"
        or set(data) != {"schema_version", "decisions"}
        or not isinstance(data.get("decisions"), list)
        or any(
            not isinstance(row, dict)
            or not isinstance(row.get("decision_id"), str)
            or not row["decision_id"].strip()
            for row in data["decisions"]
        )
    ):
        raise ValueError(".sddgov/decisions.json has an invalid contract")
    return data


@contextmanager
def _decision_lock(root: Path):
    """Serialize the complete decisions.json read-modify-write transaction."""
    lock_path = root / ".sddgov" / "decisions.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def record_decision(
    root: Path,
    decision_id: str,
    summary: str,
    scope: str,
    basis: str,
    reopen_condition: str,
) -> dict[str, Any]:
    """Reject the legacy caller-authorized L2 path."""
    del root, decision_id, summary, scope, basis, reopen_condition
    raise ValueError(
        "a signed owner L2 approval is required; use import-product-approval"
    )


def _canonical_receipt(receipt: dict[str, Any]) -> bytes:
    """Return signing bytes: canonical UTF-8 JSON without ASCII escaping."""
    return json.dumps(
        receipt,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _canonical_digest(value: dict[str, Any]) -> str:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("canonical payload must contain finite JSON values") from exc
    return hashlib.sha256(encoded).hexdigest()


def _verified_assumptions_digest(root: Path, assumptions: Any) -> str:
    """Recalculate the signed L2 assumptions from current repository bytes."""
    if not isinstance(assumptions, list) or not assumptions:
        raise ValueError("product approval assumptions must be a non-empty array")
    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    root_resolved = root.resolve()
    for index, row in enumerate(assumptions):
        if (
            not isinstance(row, dict)
            or set(row) != {"path", "sha256"}
            or not isinstance(row.get("path"), str)
            or not row["path"].strip()
            or not isinstance(row.get("sha256"), str)
            or not SHA256_PATTERN.fullmatch(row["sha256"])
        ):
            raise ValueError(f"product approval assumptions[{index}] is invalid")
        value = row["path"]
        pure = PurePosixPath(value)
        if (
            "\\" in value
            or pure.is_absolute()
            or str(pure) != value
            or any(part in {"", ".", ".."} for part in pure.parts)
            or value in seen
        ):
            raise ValueError(f"product approval assumptions[{index}] path is unsafe")
        seen.add(value)
        candidate = root.joinpath(*pure.parts)
        current = root
        for part in pure.parts:
            current = current / part
            if current.is_symlink():
                raise ValueError("product approval assumption path contains a symlink")
        try:
            candidate.resolve(strict=True).relative_to(root_resolved)
        except (FileNotFoundError, ValueError) as exc:
            raise ValueError("product approval assumption artifact is unavailable") from exc
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(candidate, flags)
        except OSError as exc:
            raise ValueError("product approval assumption cannot be opened safely") from exc
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                raise ValueError("product approval assumption must be a non-linked regular file")
            digest = hashlib.sha256()
            while True:
                chunk = os.read(descriptor, 1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
        finally:
            os.close(descriptor)
        if digest.hexdigest() != row["sha256"]:
            raise ValueError("product approval assumption artifact changed")
        normalized.append({"path": value, "sha256": row["sha256"]})
    encoded = json.dumps(
        normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_operation_payload(payload: Any) -> str:
    required = {
        "repository", "project", "environment", "scope",
        "category", "target", "parameters", "effects",
    }
    if not isinstance(payload, dict) or set(payload) != required:
        raise ValueError("operation_payload has an invalid contract")
    if payload.get("category") not in HIGH_RISK_CATEGORIES | {"high_risk_operation"}:
        raise ValueError("operation_payload category is not an L3 operation")
    if not isinstance(payload.get("target"), str) or not payload["target"].strip():
        raise ValueError("operation_payload target must not be blank")
    for field in ("repository", "project", "environment", "scope"):
        if not isinstance(payload.get(field), str) or not payload[field].strip():
            raise ValueError(f"operation_payload {field} must not be blank")
    if not isinstance(payload.get("parameters"), dict):
        raise ValueError("operation_payload parameters must be an object")
    sensitive_key = re.compile(r"(?i)(password|secret|token|credential|private[_-]?key)")

    def contains_sensitive_key(value: Any) -> bool:
        if isinstance(value, dict):
            return any(
                sensitive_key.search(str(key)) or contains_sensitive_key(child)
                for key, child in value.items()
            )
        if isinstance(value, list):
            return any(contains_sensitive_key(child) for child in value)
        return False

    if contains_sensitive_key(payload["parameters"]):
        raise ValueError("operation_payload must reference secrets, never contain them")
    effects = payload.get("effects")
    if not isinstance(effects, dict) or any(
        key not in SENSITIVE_EFFECTS or value is not True
        for key, value in effects.items()
    ):
        raise ValueError("operation_payload effects are invalid")
    return _canonical_digest(payload)


def _runtime_context() -> dict[str, str]:
    data = load_control_plane_json(
        L3_RUNTIME_CONTEXT_FILE, "L3 runtime context"
    )
    required = {"schema_version", "repository", "project", "environment"}
    if (
        set(data) != required
        or data.get("schema_version") != "1.0"
        or any(
            not isinstance(data.get(field), str) or not data[field].strip()
            for field in ("repository", "project", "environment")
        )
    ):
        raise ValueError("L3 runtime context has an invalid contract")
    return {field: data[field] for field in ("repository", "project", "environment")}


def _require_matching_runtime_context(payload: dict[str, Any]) -> None:
    context = _runtime_context()
    if any(payload.get(field) != value for field, value in context.items()):
        raise ValueError("operation payload does not match the trusted runtime context")


def _parse_time(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"approval receipt {field} must be an RFC3339 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"approval receipt {field} must be an RFC3339 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"approval receipt {field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _trusted_approver_store(root: Path) -> dict[str, Any]:
    external = os.environ.get("SDDGOV_TRUSTED_APPROVERS_FILE")
    if not external:
        raise ValueError(
            "trusted approver authority requires a separate control-plane file"
        )
    source = Path(external).expanduser().absolute()
    try:
        source.resolve().relative_to(root.resolve())
    except ValueError:
        data = load_control_plane_json(
            source, "out-of-band trusted approver store"
        )
    else:
        raise ValueError(
            "out-of-band trusted approver store must be outside the repository"
        )
    if not isinstance(data, dict):
        raise ValueError("trusted approver store must contain a JSON object")
    return data


def _trusted_approver(root: Path, approver_id: str) -> dict[str, Any]:
    data = _trusted_approver_store(root)
    if (
        not isinstance(data, dict)
        or set(data) != {"schema_version", "approvers"}
        or data.get("schema_version") != "1.0"
        or not isinstance(data.get("approvers"), list)
    ):
        raise ValueError("trusted approver store is missing or invalid")
    seen: set[str] = set()
    for row in data["approvers"]:
        if (
            not isinstance(row, dict)
            or set(row) != {"approver_id", "algorithm", "public_key", "status"}
            or not isinstance(row.get("approver_id"), str)
            or not row["approver_id"].strip()
            or row.get("algorithm") != "ed25519"
            or row.get("status") not in {"active", "revoked"}
            or not isinstance(row.get("public_key"), str)
        ):
            raise ValueError("trusted approver record has an invalid contract")
        if row["approver_id"] in seen:
            raise ValueError("trusted approver store contains duplicate approver_id")
        seen.add(row["approver_id"])
    matches = [
        row
        for row in data["approvers"]
        if isinstance(row, dict)
        and row.get("approver_id") == approver_id
        and row.get("status") == "active"
    ]
    if len(matches) != 1:
        raise ValueError("approval receipt signer is not a unique active trusted approver")
    approver = matches[0]
    return approver


def _verify_product_envelope(
    root: Path, envelope: Any
) -> tuple[dict[str, Any], str]:
    """Verify one trusted-owner-signed L2 product decision."""
    if (
        not isinstance(envelope, dict)
        or set(envelope) != {"schema_version", "algorithm", "receipt", "signature"}
        or envelope.get("schema_version") != "1.0"
        or envelope.get("algorithm") != "ed25519"
        or not isinstance(envelope.get("receipt"), dict)
        or not isinstance(envelope.get("signature"), str)
    ):
        raise ValueError("signed product approval has an invalid contract")
    receipt = envelope["receipt"]
    required = {
        "decision_id",
        "summary",
        "scope",
        "assumptions",
        "assumptions_sha256",
        "reopen_condition",
        "approved_by",
        "issued_at",
        "expires_at",
        "nonce",
    }
    string_fields = required - {"assumptions"}
    if set(receipt) != required or any(
        not isinstance(receipt.get(field), str) or not receipt[field].strip()
        for field in string_fields
    ):
        raise ValueError("product approval receipt payload has an invalid contract")
    if not SHA256_PATTERN.fullmatch(receipt["assumptions_sha256"]):
        raise ValueError("product approval assumptions_sha256 is invalid")
    if _verified_assumptions_digest(root, receipt["assumptions"]) != receipt["assumptions_sha256"]:
        raise ValueError("product approval assumptions digest does not match artifacts")
    if len(receipt["nonce"]) < 12:
        raise ValueError("product approval nonce must contain at least 12 characters")
    issued_at = _parse_time(receipt["issued_at"], "issued_at")
    expires_at = _parse_time(receipt["expires_at"], "expires_at")
    now = _now()
    if issued_at > now + timedelta(minutes=5):
        raise ValueError("product approval issued_at is in the future")
    if expires_at <= now or expires_at <= issued_at:
        raise ValueError("product approval is expired or has an invalid validity window")
    if expires_at - issued_at > timedelta(days=366):
        raise ValueError("product approval validity exceeds 366 days")
    approver = _trusted_approver(root, receipt["approved_by"])
    try:
        public_key = base64.b64decode(approver["public_key"], validate=True)
        signature = base64.b64decode(envelope["signature"], validate=True)
        Ed25519PublicKey.from_public_bytes(public_key).verify(
            signature, _canonical_receipt(receipt)
        )
    except (ValueError, binascii.Error, InvalidSignature) as exc:
        raise ValueError("product approval signature verification failed") from exc
    return receipt, hashlib.sha256(_canonical_receipt(receipt)).hexdigest()


def import_product_approval(root: Path, envelope_path: Path) -> dict[str, Any]:
    """Verify and import one trusted-owner-signed L2 product decision."""
    envelope = _read_json(envelope_path)
    receipt, receipt_sha256 = _verify_product_envelope(root, envelope)
    with _decision_lock(root):
        data = _decision_store(root)
        if any(
            row["decision_id"] == receipt["decision_id"]
            or row.get("approval_nonce") == receipt["nonce"]
            for row in data["decisions"]
        ):
            raise ValueError("product approval receipt or nonce was already imported")
        decision = {
            "decision_id": receipt["decision_id"],
            "risk_level": "L2",
            "summary": receipt["summary"],
            "scope": receipt["scope"],
            "basis": "verified owner-signed L2 product approval receipt",
            "status": "approved",
            "recorded_at": _stamp(),
            "reopen_condition": receipt["reopen_condition"],
            "assumptions_sha256": receipt["assumptions_sha256"],
            "assumptions": receipt["assumptions"],
            "approved_by": receipt["approved_by"],
            "expires_at": receipt["expires_at"],
            "approval_nonce": receipt["nonce"],
            "receipt_sha256": receipt_sha256,
            "signature_algorithm": "ed25519",
            "approval_envelope": envelope,
        }
        data["decisions"].append(decision)
        _atomic_json(_decisions_path(root), data)
    return {
        "decision_id": decision["decision_id"],
        "approved_by": decision["approved_by"],
        "expires_at": decision["expires_at"],
        "assumptions_sha256": decision["assumptions_sha256"],
        "receipt_sha256": receipt_sha256,
        "verification": "SIGNATURE_VERIFIED",
    }


def _verify_operation_envelope(
    root: Path, envelope: Any
) -> tuple[dict[str, Any], str, str]:
    """Verify one exact, fresh owner-signed L3 approval envelope."""
    if (
        not isinstance(envelope, dict)
        or set(envelope) != {"schema_version", "algorithm", "receipt", "signature"}
        or envelope.get("schema_version") != "1.0"
        or envelope.get("algorithm") != "ed25519"
        or not isinstance(envelope.get("receipt"), dict)
        or not isinstance(envelope.get("signature"), str)
    ):
        raise ValueError("signed approval receipt has an invalid contract")
    receipt = envelope["receipt"]
    required = {
        "approval_id",
        "operation_id",
        "operation_payload",
        "summary",
        "scope",
        "approved_by",
        "issued_at",
        "expires_at",
        "nonce",
    }
    string_fields = required - {"operation_payload"}
    if set(receipt) != required or any(
        not isinstance(receipt.get(field), str) or not receipt[field].strip()
        for field in string_fields
    ):
        raise ValueError("approval receipt payload has an invalid contract")
    operation_payload_sha256 = _validate_operation_payload(
        receipt["operation_payload"]
    )
    if receipt["scope"] != receipt["operation_payload"]["scope"]:
        raise ValueError("approval receipt scope does not match operation payload scope")
    if len(receipt["nonce"]) < 12:
        raise ValueError("approval receipt nonce must contain at least 12 characters")
    issued_at = _parse_time(receipt["issued_at"], "issued_at")
    expires_at = _parse_time(receipt["expires_at"], "expires_at")
    now = _now()
    if issued_at > now + timedelta(minutes=5):
        raise ValueError("approval receipt issued_at is in the future")
    if expires_at <= now or expires_at <= issued_at:
        raise ValueError("approval receipt is expired or has an invalid validity window")
    if expires_at - issued_at > timedelta(hours=24):
        raise ValueError("approval receipt validity exceeds 24 hours")
    approver = _trusted_approver(root, receipt["approved_by"])
    try:
        public_key = base64.b64decode(approver["public_key"], validate=True)
        signature = base64.b64decode(envelope["signature"], validate=True)
        Ed25519PublicKey.from_public_bytes(public_key).verify(
            signature, _canonical_receipt(receipt)
        )
    except (ValueError, binascii.Error, InvalidSignature) as exc:
        raise ValueError("approval receipt signature verification failed") from exc
    receipt_sha256 = hashlib.sha256(_canonical_receipt(receipt)).hexdigest()
    return receipt, receipt_sha256, operation_payload_sha256


def import_operation_approval(root: Path, envelope_path: Path) -> dict[str, Any]:
    """Verify and import one owner-signed, exact, expiring L3 approval receipt."""
    envelope = _read_json(envelope_path)
    receipt, receipt_sha256, operation_payload_sha256 = _verify_operation_envelope(
        root, envelope
    )
    _require_matching_runtime_context(receipt["operation_payload"])
    with _decision_lock(root):
        data = _decision_store(root)
        if any(
            row["decision_id"] == receipt["approval_id"]
            or row.get("approval_nonce") == receipt["nonce"]
            for row in data["decisions"]
        ):
            raise ValueError("approval receipt or nonce was already imported")
        decision = {
            "decision_id": receipt["approval_id"],
            "risk_level": "L3",
            "summary": receipt["summary"],
            "scope": receipt["scope"],
            "basis": "verified owner-signed approval receipt for one concrete operation",
            "status": "approved",
            "recorded_at": _stamp(),
            "reopen_condition": "a different operation or changed scope requires a new signed receipt",
            "operation_id": receipt["operation_id"],
            "approved_by": receipt["approved_by"],
            "expires_at": receipt["expires_at"],
            "consumed_at": None,
            "approval_nonce": receipt["nonce"],
            "receipt_sha256": receipt_sha256,
            "operation_payload_sha256": operation_payload_sha256,
            "signature_algorithm": "ed25519",
            "approval_envelope": envelope,
        }
        data["decisions"].append(decision)
        _atomic_json(_decisions_path(root), data)
    return {
        "approval_id": decision["decision_id"],
        "operation_id": decision["operation_id"],
        "approved_by": decision["approved_by"],
        "expires_at": decision["expires_at"],
        "receipt_sha256": receipt_sha256,
        "operation_payload_sha256": operation_payload_sha256,
        "verification": "SIGNATURE_VERIFIED",
    }


def _consume_operation_approval(
    root: Path,
    approval_id: str,
    operation_id: str,
    operation_payload: Any,
) -> dict[str, Any] | None:
    try:
        requested_payload_sha256 = _validate_operation_payload(operation_payload)
        _require_matching_runtime_context(operation_payload)
    except ValueError:
        return {"_runtime_context_blocked": True}
    with _decision_lock(root):
        data = _decision_store(root)
        for row in data["decisions"]:
            if row["decision_id"] != approval_id:
                continue
            if row.get("risk_level") != "L3" or row.get("operation_id") != operation_id:
                return None
            if row.get("consumed_at") is not None:
                return None
            if not _l3_approval_is_fresh(row, operation_id):
                return None
            try:
                receipt, receipt_sha256, operation_payload_sha256 = _verify_operation_envelope(
                    root, row.get("approval_envelope")
                )
            except ValueError:
                return None
            signed_fields = {
                "decision_id": receipt["approval_id"],
                "summary": receipt["summary"],
                "scope": receipt["scope"],
                "operation_id": receipt["operation_id"],
                "approved_by": receipt["approved_by"],
                "expires_at": receipt["expires_at"],
                "approval_nonce": receipt["nonce"],
                "receipt_sha256": receipt_sha256,
                "operation_payload_sha256": operation_payload_sha256,
                "signature_algorithm": "ed25519",
            }
            if any(row.get(field) != value for field, value in signed_fields.items()):
                return None
            if operation_payload_sha256 != requested_payload_sha256:
                return None
            if not _consume_nonce_via_control_plane(
                receipt["nonce"], receipt_sha256, operation_payload_sha256
            ):
                return {"_control_plane_blocked": True}
            row["consumed_at"] = _stamp()
            row["status"] = "completed"
            _atomic_json(_decisions_path(root), data)
            return row
    return None


def _consume_nonce_via_control_plane(
    nonce: str, receipt_sha256: str, operation_payload_sha256: str
) -> bool:
    """Atomically consume an L3 nonce through an independent Unix service."""
    if os.name == "nt" or not hasattr(os, "geteuid") or os.geteuid() == 0:
        return False
    if not L3_NONCE_BROKER.is_absolute():
        return False
    for parent in reversed(L3_NONCE_BROKER.parents):
        try:
            parent_metadata = parent.lstat()
        except OSError:
            return False
        if (
            stat.S_ISLNK(parent_metadata.st_mode)
            or not stat.S_ISDIR(parent_metadata.st_mode)
            or parent_metadata.st_uid != 0
            or parent_metadata.st_mode & 0o022
        ):
            return False
    try:
        metadata = L3_NONCE_BROKER.lstat()
    except OSError:
        return False
    if (
        metadata.st_uid != 0
        or metadata.st_mode & 0o002
        or not stat.S_ISSOCK(metadata.st_mode)
    ):
        return False
    request = json.dumps(
        {
            "action": "consume",
            "nonce": nonce,
            "receipt_sha256": receipt_sha256,
            "operation_payload_sha256": operation_payload_sha256,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8") + b"\n"
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(10)
            client.connect(str(L3_NONCE_BROKER))
            client.sendall(request)
            client.shutdown(socket.SHUT_WR)
            response = client.recv(64)
            if client.recv(1):
                return False
    except OSError:
        return False
    return response == b"CONSUMED\n"


def _find_decision(root: Path, decision_id: str | None) -> dict[str, Any] | None:
    if not decision_id:
        return None
    return next(
        (
            row
            for row in _decision_store(root)["decisions"]
            if row["decision_id"] == decision_id
        ),
        None,
    )


def _l2_approval_matches(
    root: Path,
    decision: dict[str, Any],
    *,
    scope: Any,
) -> bool:
    if (
        decision.get("risk_level") != "L2"
        or decision.get("status") != "approved"
        or not isinstance(scope, str)
        or not scope.strip()
    ):
        return False
    try:
        receipt, receipt_sha256 = _verify_product_envelope(
            root, decision.get("approval_envelope")
        )
    except ValueError:
        return False
    signed_fields = {
        "decision_id": receipt["decision_id"],
        "summary": receipt["summary"],
        "scope": receipt["scope"],
        "reopen_condition": receipt["reopen_condition"],
        "assumptions_sha256": receipt["assumptions_sha256"],
        "assumptions": receipt["assumptions"],
        "approved_by": receipt["approved_by"],
        "expires_at": receipt["expires_at"],
        "approval_nonce": receipt["nonce"],
        "receipt_sha256": receipt_sha256,
        "signature_algorithm": "ed25519",
    }
    if any(decision.get(field) != value for field, value in signed_fields.items()):
        return False
    return receipt["scope"] == scope


def _l3_approval_is_fresh(decision: dict[str, Any], operation_id: str | None) -> bool:
    if (
        decision.get("risk_level") != "L3"
        or decision.get("status") != "approved"
        or decision.get("operation_id") != operation_id
        or decision.get("consumed_at") is not None
    ):
        return False
    try:
        expires_at = datetime.fromisoformat(
            str(decision["expires_at"]).replace("Z", "+00:00")
        )
    except (KeyError, TypeError, ValueError):
        return False
    if expires_at.tzinfo is None:
        return False
    try:
        return expires_at > _now()
    except TypeError:
        return False


def build_action_required(
    *,
    decision_id: str,
    risk_level: str,
    why_human_input_is_required: str,
    what_agent_already_verified: Iterable[str],
    options: Iterable[dict[str, str]],
    recommended: str,
    why: str,
    impact_if_no_decision: str,
    scope_of_approval: str,
) -> dict[str, Any]:
    if risk_level not in {"L2", "L3", "Operational", "UAT"}:
        raise ValueError("ACTION REQUIRED risk must be L2, L3, Operational, or UAT")
    verified = [item.strip() for item in what_agent_already_verified if item.strip()]
    choices = list(options)
    if not decision_id.strip() or not why_human_input_is_required.strip():
        raise ValueError("ACTION REQUIRED needs a decision ID and bounded reason")
    if not verified:
        raise ValueError("ACTION REQUIRED must list what the Agent already verified")
    if len(choices) < 2:
        raise ValueError("ACTION REQUIRED must provide at least two options")
    labels = []
    for option in choices:
        if set(option) != {"label", "description"}:
            raise ValueError("each option must contain only label and description")
        if not option["label"].strip() or not option["description"].strip():
            raise ValueError("ACTION REQUIRED options must not be blank")
        labels.append(option["label"])
    if recommended not in labels:
        raise ValueError("recommended must name one provided option")
    package = {
        "heading": "ACTION REQUIRED",
        "decision_id": decision_id,
        "risk_level": risk_level,
        "why_human_input_is_required": why_human_input_is_required,
        "what_agent_already_verified": verified,
        "options": choices,
        "recommended": recommended,
        "why": why,
        "impact_if_no_decision": impact_if_no_decision,
        "scope_of_approval": scope_of_approval,
    }
    missing = [
        field
        for field in ACTION_REQUIRED_FIELDS
        if not package.get(field)
        or (
            isinstance(package[field], str)
            and not package[field].strip()
        )
    ]
    if missing:
        raise ValueError(f"ACTION REQUIRED missing fields: {', '.join(missing)}")
    return package


def render_action_required(package: dict[str, Any]) -> str:
    missing = [field for field in ACTION_REQUIRED_FIELDS if not package.get(field)]
    if package.get("heading") != "ACTION REQUIRED" or missing:
        raise ValueError("invalid ACTION REQUIRED package")
    lines = [
        "ACTION REQUIRED",
        "",
        f"Decision ID: {package['decision_id']}",
        f"Risk Level: {package['risk_level']}",
        "",
        "Why human input is required:",
        package["why_human_input_is_required"],
        "",
        "What Agent already verified:",
        *[f"- {item}" for item in package["what_agent_already_verified"]],
        "",
    ]
    for option in package["options"]:
        lines.extend([f"Option {option['label']}:", option["description"], ""])
    lines.extend(
        [
            "Recommended:",
            package["recommended"],
            "",
            "Why:",
            package["why"],
            "",
            "Impact if no decision:",
            package["impact_if_no_decision"],
            "",
            "Scope of this approval:",
            package["scope_of_approval"],
        ]
    )
    return "\n".join(lines) + "\n"


def checkpoint(summary: str, next_work_package: str | None = None) -> dict[str, Any]:
    if not summary.strip():
        raise ValueError("checkpoint summary must not be blank")
    return {
        "type": "checkpoint",
        "summary": summary,
        "requires_response": False,
        "next_state": "CONTINUE",
        "next_work_package": next_work_package,
    }


def _continue(reason: str, next_action: str = "continue") -> dict[str, Any]:
    return {
        "state": "CONTINUE",
        "requires_response": False,
        "reason": reason,
        "next_action": next_action,
    }


def evaluate_escalation(root: Path, request: dict[str, Any]) -> dict[str, Any]:
    risk = request.get("risk_level")
    category = request.get("category")
    if risk not in RISK_LEVELS:
        raise ValueError("risk_level must be L0, L1, L2, or L3")
    if not isinstance(category, str) or not category:
        raise ValueError("category is required")
    if category not in KNOWN_CATEGORIES:
        return {
            "state": "BLOCKED",
            "requires_response": False,
            "reason": "unrecognized_action_category",
            "next_action": "classify_with_canonical_action_category_and_effects",
        }
    if "effects" not in request:
        raise ValueError("effects is required and must explicitly classify sensitive effects")
    effects = request["effects"]
    if not isinstance(effects, dict):
        raise ValueError("effects must be an object of known sensitive flags")
    if any(
        key not in SENSITIVE_EFFECTS or value is not True
        for key, value in effects.items()
    ):
        raise ValueError("effects must contain only known sensitive flags set to true")
    if category == "product_decision" and risk in {"L0", "L1"}:
        return {
            "state": "BLOCKED",
            "requires_response": False,
            "reason": "product_decision_cannot_be_downgraded",
            "required_risk_levels": ["L2"],
            "next_action": "reclassify_and_prepare_signed_l2_decision_package",
        }
    if category == "high_risk_operation" and risk != "L3":
        return {
            "state": "BLOCKED",
            "requires_response": False,
            "reason": "high_risk_operation_cannot_be_downgraded",
            "required_risk_levels": ["L3"],
            "next_action": "reclassify_and_prepare_exact_l3_decision_package",
        }
    high_risk = category in HIGH_RISK_CATEGORIES or bool(effects)
    if high_risk and risk != "L3":
        return {
            "state": "BLOCKED",
            "requires_response": False,
            "reason": "dangerous_action_cannot_be_downgraded",
            "required_risk_levels": ["L3"],
            "next_action": "reclassify_and_prepare_exact_l3_decision_package",
        }
    forced_human_category = category in {"operational_action", "necessary_uat"}

    if category == "checkpoint":
        return _continue("checkpoint_is_informational")
    if category == "integrity_mismatch":
        result = {
            "state": "CONTINUE" if request.get("unrelated_work_exists") else "BLOCKED",
            "artifact_state": "BLOCKED",
            "requires_response": False,
            "reason": "integrity_mismatch_requires_machine_investigation",
            "next_action": (
                "investigate_artifact_and_continue_unrelated_work"
                if request.get("unrelated_work_exists")
                else "investigate_artifact"
            ),
        }
        return result
    if (
        not forced_human_category
        and category in ROUTINE_OPERATIONS
        and risk in {"L0", "L1"}
    ):
        return _continue(
            "no_human_escalation_if_machine_verifiable",
            "verify_with_repo_decisions_tests_ci_or_tools",
        )
    if (
        not forced_human_category
        and request.get("machine_verifiable")
        and risk in {"L0", "L1"}
    ):
        return _continue(
            "no_human_escalation_if_machine_verifiable",
            "verify_with_repo_decisions_tests_ci_or_tools",
        )
    if risk in {"L0", "L1"} and not forced_human_category:
        return _continue("l0_l1_engineering_is_pre_authorized")

    decision_id = request.get("decision_id")
    if risk == "L2":
        recorded = _find_decision(root, decision_id)
        if (
            recorded
            and _l2_approval_matches(
                root,
                recorded,
                scope=request.get("decision_scope"),
            )
        ):
            return _continue("existing_decision_reused_without_duplicate_question")

    if risk == "L3" and request.get("approval_id"):
        operation_payload = request.get("operation_payload")
        try:
            _validate_operation_payload(operation_payload)
        except ValueError as exc:
            return {
                "state": "BLOCKED",
                "requires_response": False,
                "reason": "exact_operation_payload_required",
                "next_action": "prepare_canonical_operation_payload",
                "detail": str(exc),
            }
        if (
            operation_payload["category"] != category
            or operation_payload["effects"] != effects
        ):
            return {
                "state": "BLOCKED",
                "requires_response": False,
                "reason": "operation_payload_does_not_match_request",
                "next_action": "rebuild_exact_operation_request",
            }
        approval = _consume_operation_approval(
            root,
            request.get("approval_id"),
            request.get("operation_id"),
            operation_payload,
        )
        if approval:
            if approval.get("_runtime_context_blocked"):
                return {
                    "state": "BLOCKED",
                    "requires_response": False,
                    "reason": "l3_runtime_context_mismatch",
                    "next_action": "recover_independent_runtime_context_or_reissue_exact_payload",
                }
            if approval.get("_control_plane_blocked"):
                return {
                    "state": "BLOCKED",
                    "requires_response": False,
                    "reason": "l3_external_nonce_ledger_unavailable",
                    "next_action": "provision_or_recover_independent_l3_control_plane",
                }
            result = _continue("fresh_l3_operation_approval_verified")
            result["approval_id"] = approval["decision_id"]
            result["operation_id"] = approval["operation_id"]
            result["authorized_operation_payload"] = approval["approval_envelope"]["receipt"]["operation_payload"]
            result["operation_payload_sha256"] = approval["operation_payload_sha256"]
            result["approval_consumed"] = True
            return result

    package_input = request.get("decision_package")
    if not isinstance(package_input, dict):
        raise ValueError("a genuine escalation requires a strict decision_package")
    package = build_action_required(**package_input)
    if category == "operational_action" and request.get("unrelated_work_exists"):
        return {
            "state": "CONTINUE",
            "requires_response": False,
            "reason": "operational_action_blocks_only_dependent_work",
            "next_action": "queue_action_required_and_continue_unrelated_work",
            "action_required": package,
        }
    return {
        "state": "ACTION_REQUIRED",
        "requires_response": True,
        "reason": "human_judgment_required_by_policy",
        "decision_package": package,
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def lock_artifact(artifact: Path, release_id: str, output: Path) -> dict[str, Any]:
    artifact = artifact.resolve()
    if not artifact.is_file():
        raise FileNotFoundError(f"artifact does not exist: {artifact}")
    if not release_id.strip():
        raise ValueError("release_id must not be blank")
    lock = {
        "schema_version": "1.0",
        "release_id": release_id,
        "artifact_name": artifact.name,
        "size": artifact.stat().st_size,
        "sha256": _sha256(artifact),
        "created_at": _stamp(),
    }
    _atomic_json(output, lock)
    return {
        "ok": True,
        "state": "CONTINUE",
        "integrity": "LOCKED",
        "human_action_required": False,
        "release_id": release_id,
        "lock": str(output),
    }


def verify_artifact(artifact: Path, lock_path: Path) -> dict[str, Any]:
    artifact = artifact.resolve()
    if not artifact.is_file():
        raise FileNotFoundError(f"artifact does not exist: {artifact}")
    lock = _read_json(lock_path)
    if not isinstance(lock, dict):
        raise ValueError("artifact lock is invalid")
    required = {"schema_version", "release_id", "artifact_name", "size", "sha256", "created_at"}
    if set(lock) != required or lock.get("schema_version") != "1.0":
        raise ValueError("artifact lock has an invalid contract")
    matched = (
        lock["artifact_name"] == artifact.name
        and lock["size"] == artifact.stat().st_size
        and lock["sha256"] == _sha256(artifact)
    )
    if matched:
        return {
            "ok": True,
            "state": "CONTINUE",
            "integrity": "MATCH",
            "human_action_required": False,
            "release_id": lock["release_id"],
        }
    return {
        "ok": False,
        "state": "BLOCKED",
        "integrity": "MISMATCH",
        "human_action_required": False,
        "release_id": lock["release_id"],
        "next_action": "stop_artifact_and_investigate",
    }


def evaluate_deployment(root: Path, gate: dict[str, Any]) -> dict[str, Any]:
    risk = gate.get("risk_level")
    if risk not in RISK_LEVELS:
        raise ValueError("deployment risk_level must be L0, L1, L2, or L3")
    missing = [name for name in DEPLOY_GUARDS if gate.get(name) is not True]
    if missing:
        return {
            "ok": False,
            "state": "BLOCKED",
            "requires_response": False,
            "reason": "production_guardrails_not_satisfied",
            "failed_guards": missing,
            "next_action": "investigate_and_restore_machine_verifiable_guards",
        }
    if risk == "L0":
        return {
            "ok": False,
            "state": "BLOCKED",
            "requires_response": False,
            "reason": "production_deploy_requires_at_least_l1_classification",
            "next_action": "reclassify_as_l1_and_verify_recorded_baseline_authorization",
        }
    if risk == "L1":
        deployment_class = gate.get("deployment_class")
        baseline = _find_decision(root, gate.get("baseline_decision_id"))
        baseline_is_valid = (
            isinstance(deployment_class, str)
            and bool(deployment_class.strip())
            and baseline is not None
            and _l2_approval_matches(
                root,
                baseline,
                scope=f"production_deploy:{deployment_class}",
            )
        )
        if not baseline_is_valid:
            return {
                "ok": False,
                "state": "BLOCKED",
                "requires_response": False,
                "reason": "recorded_baseline_deployment_authorization_missing",
                "next_action": "look_up_sdd_adr_or_decision_log",
            }
        return {
            "ok": True,
            "state": "CONTINUE",
            "requires_response": False,
            "reason": "routine_reversible_l1_deploy_pre_authorized",
            "baseline_decision_id": baseline["decision_id"],
            "deployment_class": deployment_class,
        }
    request = dict(gate.get("escalation_request") or {})
    request.setdefault("risk_level", risk)
    request.setdefault("category", "product_decision" if risk == "L2" else "high_risk_operation")
    return evaluate_escalation(root, request)
