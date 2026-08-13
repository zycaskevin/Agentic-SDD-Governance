from __future__ import annotations

import base64
import binascii
import fcntl
import hashlib
import json
import os
import subprocess
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


RISK_LEVELS = {"L0", "L1", "L2", "L3"}
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
    """Record one approved L2 product decision for later deterministic reuse."""
    if not all(value.strip() for value in (decision_id, summary, scope, basis, reopen_condition)):
        raise ValueError("decision fields must not be blank")
    with _decision_lock(root):
        data = _decision_store(root)
        if any(row["decision_id"] == decision_id for row in data["decisions"]):
            raise ValueError(f"decision already recorded: {decision_id}")
        decision = {
            "decision_id": decision_id,
            "risk_level": "L2",
            "summary": summary,
            "scope": scope,
            "basis": basis,
            "status": "approved",
            "recorded_at": _stamp(),
            "reopen_condition": reopen_condition,
        }
        data["decisions"].append(decision)
        _atomic_json(_decisions_path(root), data)
    return decision


def _canonical_receipt(receipt: dict[str, Any]) -> bytes:
    """Return signing bytes: canonical UTF-8 JSON without ASCII escaping."""
    return json.dumps(
        receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


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
    if external:
        source = Path(external).expanduser().resolve()
        try:
            source.relative_to(root.resolve())
        except ValueError:
            data = _read_json(source)
        else:
            raise ValueError(
                "out-of-band trusted approver store must be outside the repository"
            )
    else:
        base_ref = os.environ.get("SDDGOV_TRUSTED_BASE_REF")
        if not base_ref:
            raise ValueError(
                "trusted approver bootstrap requires SDDGOV_TRUSTED_APPROVERS_FILE "
                "or SDDGOV_TRUSTED_BASE_REF"
            )
        completed = subprocess.run(
            ["git", "show", f"{base_ref}:.sddgov/trusted-approvers.json"],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise ValueError("trusted approver store is absent from the trusted base")
        try:
            data = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise ValueError("trusted approver store at trusted base is invalid") from exc
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


def import_operation_approval(root: Path, envelope_path: Path) -> dict[str, Any]:
    """Verify and import one owner-signed, exact, expiring L3 approval receipt."""
    envelope = _read_json(envelope_path)
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
        "summary",
        "scope",
        "approved_by",
        "issued_at",
        "expires_at",
        "nonce",
    }
    if set(receipt) != required or any(
        not isinstance(receipt.get(field), str) or not receipt[field].strip()
        for field in required
    ):
        raise ValueError("approval receipt payload has an invalid contract")
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
            "signature_algorithm": "ed25519",
        }
        data["decisions"].append(decision)
        _atomic_json(_decisions_path(root), data)
    return {
        "approval_id": decision["decision_id"],
        "operation_id": decision["operation_id"],
        "approved_by": decision["approved_by"],
        "expires_at": decision["expires_at"],
        "receipt_sha256": receipt_sha256,
        "verification": "SIGNATURE_VERIFIED",
    }


def _consume_operation_approval(root: Path, approval_id: str, operation_id: str) -> dict[str, Any] | None:
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
            row["consumed_at"] = _stamp()
            row["status"] = "completed"
            _atomic_json(_decisions_path(root), data)
            return row
    return None


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
    effects = request.get("effects", {})
    if not isinstance(effects, dict):
        raise ValueError("effects must be an object of known sensitive flags")
    if any(
        key not in SENSITIVE_EFFECTS or value is not True
        for key, value in effects.items()
    ):
        raise ValueError("effects must contain only known sensitive flags set to true")
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
            and recorded.get("risk_level") == "L2"
            and recorded.get("status") == "approved"
            and recorded.get("scope") == request.get("decision_scope")
            and request.get("assumptions_unchanged", True)
            and not request.get("reopen_condition_triggered", False)
        ):
            return _continue("existing_decision_reused_without_duplicate_question")

    if risk == "L3":
        approval = _consume_operation_approval(
            root, request.get("approval_id"), request.get("operation_id")
        )
        if approval:
            result = _continue("fresh_l3_operation_approval_verified")
            result["approval_id"] = approval["decision_id"]
            result["operation_id"] = approval["operation_id"]
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
            and baseline.get("risk_level") == "L2"
            and baseline.get("status") == "approved"
            and baseline.get("scope") == f"production_deploy:{deployment_class}"
            and gate.get("baseline_assumptions_unchanged") is True
            and gate.get("baseline_reopen_condition_triggered") is not True
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
