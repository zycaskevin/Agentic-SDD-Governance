from __future__ import annotations

import base64
import binascii
import fcntl
import hashlib
import json
import os
import re
import secrets
import socket
import stat
import subprocess
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable

try:
    import grp
except ImportError:  # pragma: no cover - exercised by native non-POSIX hosts
    grp = None  # type: ignore[assignment]

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .fs_security import FileSetSnapshot, canonicalize_platform_path
from .governance import enqueue_external_action, resolve_external_action
from .trust import (
    load_control_plane_json,
    trusted_approver_domains_path,
    trusted_approvers_path,
)


RISK_LEVELS = {"L0", "L1", "L2", "L3"}
SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
GITHUB_REPOSITORY_COMPONENT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$")
OWNER_CLIENT_BINDING_PREFIX = "Owner client binding: "
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
    "release_readiness",
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
    "public_release",
}
SENSITIVE_EFFECTS = {
    "production",
    "destructive",
    "irreversible",
    "secret_change",
    "permission_boundary_change",
    "real_payment",
    "high_privilege",
    "public_publish",
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
L3_NONCE_BROKER_GROUP = "_sddgov" if sys.platform == "darwin" else "sddgov"
L3_RUNTIME_CONTEXT_FILE = Path("/etc/sddgov/runtime-context.json")
L2_REOPEN_CONDITIONS = {"scope_or_assumptions_change"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _stamp(value: datetime | None = None) -> str:
    return (value or _now()).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _reject_duplicate_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Build one JSON object while rejecting recursive duplicate member names."""
    value: dict[str, Any] = {}
    for key, member in pairs:
        if key in value:
            raise ValueError(f"JSON object contains duplicate member: {key}")
        value[key] = member
    return value


def _load_unique_json_bytes(raw: bytes, label: str) -> Any:
    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_json_object,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} must contain UTF-8 JSON") from exc


def _exact_line_occurrences(artifacts: list[bytes], marker: bytes) -> int:
    """Count one exact marker line across every bounded signed artifact."""
    return sum(raw.splitlines().count(marker) for raw in artifacts)


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


def _project_profile(root: Path) -> str:
    project = _read_json(root / ".sddgov" / "project.json")
    if not isinstance(project, dict) or project.get("profile") not in {
        "solo-fast",
        "team-standard",
        "regulated",
    }:
        raise ValueError(".sddgov/project.json has an invalid profile")
    return project["profile"]


def _plain_l2_request_binding(
    root: Path,
    request_path: str,
    *,
    decision_id: str,
    scope: str,
    selected_label: str,
    decision_package: Any = None,
) -> str:
    pure = PurePosixPath(request_path)
    if (
        not request_path
        or "\\" in request_path
        or "\x00" in request_path
        or pure.is_absolute()
        or str(pure) != request_path
        or any(part in {"", ".", ".."} for part in pure.parts)
    ):
        raise ValueError("plain-language product decision request must be repository-relative")
    raw = _read_repository_regular_file(root, pure)
    request = _load_unique_json_bytes(raw, "plain-language product decision request")
    allowed = {
        "risk_level",
        "category",
        "effects",
        "decision_id",
        "decision_scope",
        "decision_package",
    }
    if (
        not isinstance(request, dict)
        or set(request) != allowed
        or request.get("risk_level") != "L2"
        or request.get("category") != "product_decision"
        or request.get("effects") != {}
        or request.get("decision_id") != decision_id
        or request.get("decision_scope") != scope
    ):
        raise ValueError("plain-language product decision request is not exact")
    try:
        package = build_action_required(**request["decision_package"])
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        raise ValueError(
            "plain-language product decision request has an invalid Decision Package"
        ) from exc
    if _action_required_binding_error(request, package) is not None:
        raise ValueError("plain-language product decision request is not scope-bound")
    options = _require_bounded_ab_card(package)
    labels = [option["label"] for option in options]
    if labels.count(selected_label) != 1:
        raise ValueError("selected product decision label is not in the bounded card")
    if decision_package is not None:
        try:
            incoming_package = build_action_required(**decision_package)
        except (AttributeError, TypeError, ValueError) as exc:
            raise ValueError(
                "incoming plain-language Decision Package is invalid"
            ) from exc
        if incoming_package != package:
            raise ValueError(
                "incoming plain-language Decision Package differs from the approved request"
            )
    return hashlib.sha256(raw).hexdigest()


def _require_bounded_ab_card(package: dict[str, Any]) -> list[dict[str, Any]]:
    """Return one canonical two-option Owner card or fail closed.

    Both plain-language and signed L2 paths use this validator so recording and
    later verification cannot drift into different card shapes.
    """
    options = package.get("options")
    if (
        not isinstance(options, list)
        or len(options) != 2
        or not all(isinstance(option, dict) for option in options)
        or [option.get("label") for option in options] != ["A", "B"]
        or package.get("recommended") != "A"
        or not all(
            isinstance(option.get("description"), str)
            and bool(option["description"].strip())
            for option in options
        )
    ):
        raise ValueError("product decision request must present one bounded A/B card")
    return options


def record_decision(
    root: Path,
    decision_id: str,
    summary: str,
    scope: str,
    basis: str,
    reopen_condition: str,
    request_path: str,
) -> dict[str, Any]:
    """Record one bounded plain-language L2 choice for team-standard.

    This is an auditable product-direction record, not authority for an L3
    operation. Solo-fast and regulated profiles retain the signed receipt path.
    """
    profile = _project_profile(root)
    if profile != "team-standard":
        raise ValueError(
            "this profile requires a signed owner L2 approval; "
            "use import-product-approval"
        )
    fields = {
        "decision_id": decision_id,
        "summary": summary,
        "scope": scope,
        "basis": basis,
        "reopen_condition": reopen_condition,
    }
    if any(
        not isinstance(value, str)
        or not value.strip()
        or len(value.encode("utf-8")) > 4096
        for value in fields.values()
    ):
        raise ValueError("plain-language product decision fields must be bounded text")
    if not basis.startswith("owner_explicit_choice:") or not basis.removeprefix(
        "owner_explicit_choice:"
    ).strip():
        raise ValueError(
            "plain-language product decision basis must be owner_explicit_choice:<label>"
        )
    if reopen_condition != "scope_or_assumptions_change":
        raise ValueError(
            "plain-language product decision reopen_condition must be "
            "scope_or_assumptions_change"
        )
    selected_label = basis.removeprefix("owner_explicit_choice:").strip()
    request_sha256 = _plain_l2_request_binding(
        root,
        request_path,
        decision_id=decision_id,
        scope=scope,
        selected_label=selected_label,
    )
    with _decision_lock(root):
        data = _decision_store(root)
        if any(row["decision_id"] == decision_id for row in data["decisions"]):
            raise ValueError("product decision ID already exists")
        decision = {
            "decision_id": decision_id,
            "risk_level": "L2",
            "summary": summary,
            "scope": scope,
            "basis": basis,
            "status": "approved",
            "recorded_at": _stamp(),
            "reopen_condition": reopen_condition,
            "approval_mode": "plain_language_owner_choice",
            "profile": profile,
            "approved_by": "project_owner",
            "request_path": request_path,
            "request_sha256": request_sha256,
        }
        data["decisions"].append(decision)
        _atomic_json(_decisions_path(root), data)
    return {
        "decision_id": decision_id,
        "verification": "PLAIN_LANGUAGE_DECISION_RECORDED",
        "approval_mode": decision["approval_mode"],
        "profile": profile,
    }


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


def _read_repository_regular_file(
    root: Path,
    relative: PurePosixPath,
    *,
    max_bytes: int | None = None,
) -> bytes:
    """Read one repository file through a call-wide descriptor snapshot."""
    with FileSetSnapshot(root, "product approval repository") as snapshot:
        return snapshot.read(relative, max_bytes=max_bytes or 1024 * 1024)


def _verified_assumptions_digest(
    root: Path,
    assumptions: Any,
    *,
    snapshot: FileSetSnapshot | None = None,
) -> str:
    """Recalculate the signed L2 assumptions from current repository bytes."""
    if not isinstance(assumptions, list) or not assumptions:
        raise ValueError("product approval assumptions must be a non-empty array")

    def verify(active_snapshot: FileSetSnapshot) -> str:
        normalized: list[dict[str, str]] = []
        seen: set[str] = set()
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
            raw = active_snapshot.read(pure, max_bytes=1024 * 1024)
            digest = hashlib.sha256(raw)
            if digest.hexdigest() != row["sha256"]:
                raise ValueError("product approval assumption artifact changed")
            normalized.append({"path": value, "sha256": row["sha256"]})
        encoded = json.dumps(
            normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    if snapshot is not None:
        return verify(snapshot)
    with FileSetSnapshot(root, "product approval assumptions") as owned_snapshot:
        return verify(owned_snapshot)


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
    if payload["category"] == "public_release" and effects.get(
        "public_publish"
    ) is not True:
        raise ValueError("public_release operation must declare public_publish")
    if "public_publish" in effects and payload["category"] != "public_release":
        raise ValueError("public_publish effect requires public_release category")
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


ControlPlaneLoader = Callable[[Path, str], dict[str, Any]]


def _trusted_approver_store(
    root: Path,
    *,
    control_plane_loader: ControlPlaneLoader | None = None,
) -> dict[str, Any]:
    source = trusted_approvers_path(root)
    loader = load_control_plane_json if control_plane_loader is None else control_plane_loader
    data = loader(source, "fixed trusted approver store")
    if not isinstance(data, dict):
        raise ValueError("trusted approver store must contain a JSON object")
    return data


def _trusted_approver(
    root: Path,
    approver_id: str,
    *,
    control_plane_loader: ControlPlaneLoader | None = None,
) -> dict[str, Any]:
    data = _trusted_approver_store(
        root,
        control_plane_loader=control_plane_loader,
    )
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


def _trusted_approver_domain(
    root: Path,
    approver_id: str,
    *,
    control_plane_loader: ControlPlaneLoader | None = None,
) -> dict[str, str]:
    loader = load_control_plane_json if control_plane_loader is None else control_plane_loader
    data = loader(
        trusted_approver_domains_path(root),
        "fixed trusted approver domain store",
    )
    if (
        not isinstance(data, dict)
        or set(data) != {"schema_version", "bindings"}
        or data.get("schema_version") != "1.0"
        or not isinstance(data.get("bindings"), list)
    ):
        raise ValueError("trusted approver domain store is missing or invalid")
    seen: set[str] = set()
    for row in data["bindings"]:
        if (
            not isinstance(row, dict)
            or set(row)
            != {
                "approver_id",
                "repository_id",
                "repository_root",
                "trust_domain",
                "status",
            }
            or not all(
                isinstance(row.get(field), str) and row[field].strip()
                for field in (
                    "approver_id",
                    "repository_id",
                    "repository_root",
                    "trust_domain",
                )
            )
            or row.get("status") not in {"active", "revoked"}
            or row["approver_id"] in seen
        ):
            raise ValueError("trusted approver domain record has an invalid contract")
        seen.add(row["approver_id"])
    matches = [
        row
        for row in data["bindings"]
        if row.get("approver_id") == approver_id and row.get("status") == "active"
    ]
    if len(matches) != 1:
        raise ValueError("trusted approver has no unique active trust-domain binding")
    binding = matches[0]
    configured_root = canonicalize_platform_path(Path(binding["repository_root"]))
    current_root = canonicalize_platform_path(root)
    if (
        not Path(binding["repository_root"]).is_absolute()
        or os.fspath(configured_root) != binding["repository_root"]
        or configured_root != current_root
    ):
        raise ValueError("trusted approver is not authorized for this repository root")
    repository_id = _repository_identity(root)
    if binding["repository_id"] != repository_id:
        raise ValueError("trusted approver is not authorized for this repository")
    return {
        "approver_id": binding["approver_id"],
        "repository_id": binding["repository_id"],
        "trust_domain": binding["trust_domain"],
        "status": binding["status"],
    }


def _repository_identity(root: Path) -> str:
    """Return one canonical GitHub repository identity for approval audience checks."""
    safe_root = canonicalize_platform_path(root)
    environment = {
        "PATH": "/usr/bin:/bin",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
    }

    def git(*arguments: str) -> str:
        try:
            result = subprocess.run(
                [
                    "/usr/bin/git",
                    "-c",
                    f"safe.directory={os.fspath(safe_root)}",
                    "-C",
                    os.fspath(safe_root),
                    *arguments,
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
                env=environment,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise ValueError("repository identity is unavailable") from exc
        if result.returncode != 0 or not result.stdout.strip():
            raise ValueError("repository identity is unavailable")
        value = result.stdout.strip()
        if len(value.encode("utf-8")) > 4096 or "\n" in value or "\r" in value:
            raise ValueError("repository identity output is invalid")
        return value

    top_level = Path(git("rev-parse", "--show-toplevel")).absolute()
    if top_level != safe_root:
        raise ValueError("approval root must be the exact Git worktree root")
    remote = git("config", "--local", "--get", "remote.origin.url")
    if remote.startswith("git@github.com:"):
        repository = remote[len("git@github.com:") :]
    else:
        repository = ""
        for prefix in ("https://github.com/", "ssh://git@github.com/"):
            if remote.startswith(prefix):
                repository = remote[len(prefix) :]
                break
    repository = repository.removesuffix(".git").strip("/")
    components = repository.split("/")
    if (
        len(components) != 2
        or any(
            GITHUB_REPOSITORY_COMPONENT_PATTERN.fullmatch(component) is None
            for component in components
        )
    ):
        raise ValueError("repository origin is not one canonical GitHub repository")
    return f"github.com/{components[0].lower()}/{components[1].lower()}"


def _verify_product_envelope(
    root: Path,
    envelope: Any,
    *,
    control_plane_loader: ControlPlaneLoader | None = None,
    assumption_snapshot: FileSetSnapshot | None = None,
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
    if receipt["reopen_condition"] not in L2_REOPEN_CONDITIONS:
        raise ValueError(
            "product approval reopen_condition is unsupported; use scope_or_assumptions_change"
        )
    if not SHA256_PATTERN.fullmatch(receipt["assumptions_sha256"]):
        raise ValueError("product approval assumptions_sha256 is invalid")
    if (
        _verified_assumptions_digest(
            root,
            receipt["assumptions"],
            snapshot=assumption_snapshot,
        )
        != receipt["assumptions_sha256"]
    ):
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
    approver = _trusted_approver(
        root,
        receipt["approved_by"],
        control_plane_loader=control_plane_loader,
    )
    _trusted_approver_domain(
        root,
        receipt["approved_by"],
        control_plane_loader=control_plane_loader,
    )
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
    expanded = canonicalize_platform_path(envelope_path)
    if not expanded.name or expanded.name in {".", ".."}:
        raise ValueError("signed product approval path is unsafe")
    with FileSetSnapshot(
        expanded.parent,
        "signed product approval envelope",
    ) as snapshot:
        raw_envelope = snapshot.read(
            PurePosixPath(expanded.name),
            max_bytes=1024 * 1024,
        )
        envelope = _load_unique_json_bytes(
            raw_envelope,
            "signed product approval envelope",
        )
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


def verify_product_decision(
    root: Path,
    decision_id: str,
    request_path: str,
) -> dict[str, Any]:
    """Reverify one stored L2 signature, row, audience, and exact request."""
    pure = PurePosixPath(request_path)
    if (
        not request_path
        or "\\" in request_path
        or "\x00" in request_path
        or pure.is_absolute()
        or str(pure) != request_path
        or any(part in {"", ".", ".."} for part in pure.parts)
    ):
        raise ValueError("product decision request must be repository-relative")
    with FileSetSnapshot(
        root,
        "stored product decision repository",
    ) as snapshot:
        raw = snapshot.read(pure, max_bytes=1024 * 1024)
        request = _load_unique_json_bytes(raw, "product decision request")
        if (
            not isinstance(request, dict)
            or request.get("risk_level") != "L2"
            or request.get("category") != "product_decision"
            or request.get("effects") != {}
            or _closed_category_envelope_error(request) is not None
            or request.get("decision_id") != decision_id
        ):
            raise ValueError("product decision request has an invalid exact L2 contract")
        package_input = request.get("decision_package")
        if not isinstance(package_input, dict):
            raise ValueError("product decision request lacks one exact Decision Package")
        try:
            package = build_action_required(**package_input)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "product decision request has an invalid Decision Package"
            ) from exc
        if _action_required_binding_error(request, package) is not None:
            raise ValueError("product decision request package is not bound to its scope")
        options = _require_bounded_ab_card(package)
        decision = _find_decision(root, decision_id)
        if decision is None:
            if _project_profile(root) == "team-standard":
                raise ValueError("stored plain-language product decision is missing")
            raise ValueError("stored product decision failed cryptographic verification")
        if decision.get("approval_mode") == "plain_language_owner_choice":
            allowed = {
                "risk_level",
                "category",
                "effects",
                "decision_id",
                "decision_scope",
                "decision_package",
            }
            if (
                set(request) != allowed
                or decision.get("request_path") != request_path
                or not isinstance(decision.get("request_sha256"), str)
                or not secrets.compare_digest(
                    decision["request_sha256"], hashlib.sha256(raw).hexdigest()
                )
                or not _plain_l2_approval_matches(
                    root,
                    decision,
                    scope=request.get("decision_scope"),
                    decision_package=package_input,
                )
            ):
                raise ValueError(
                    "stored plain-language product decision does not match the request"
                )
            return {
                "decision_id": decision_id,
                "verification": "PLAIN_LANGUAGE_DECISION_VERIFIED",
                "approval_mode": decision["approval_mode"],
                "profile": decision["profile"],
                "recorded_at": decision["recorded_at"],
            }
        try:
            receipt, receipt_sha256 = _verify_product_envelope(
                root,
                decision["approval_envelope"],
                assumption_snapshot=snapshot,
            )
        except (KeyError, ValueError) as exc:
            raise ValueError(
                "stored product decision failed cryptographic verification"
            ) from exc
        if not _l2_approval_matches_verified(
            decision,
            scope=request.get("decision_scope"),
            receipt=receipt,
            receipt_sha256=receipt_sha256,
        ):
            raise ValueError("stored product decision failed cryptographic verification")
        assumption_paths = request.get("assumption_paths")
        if (
            not isinstance(assumption_paths, list)
            or not assumption_paths
            or any(
                not isinstance(path, str)
                or not path
                or "\\" in path
                or "\x00" in path
                or PurePosixPath(path).is_absolute()
                or str(PurePosixPath(path)) != path
                or any(
                    part in {"", ".", ".."}
                    for part in PurePosixPath(path).parts
                )
                for path in assumption_paths
            )
            or assumption_paths != sorted(set(assumption_paths))
            or assumption_paths.count(request_path) != 1
            or assumption_paths
            != [row.get("path") for row in receipt["assumptions"]]
        ):
            raise ValueError("stored product decision assumptions do not match the request")
        request_rows = [
            row for row in receipt["assumptions"] if row.get("path") == request_path
        ]
        if (
            len(request_rows) != 1
            or not secrets.compare_digest(
                request_rows[0]["sha256"],
                hashlib.sha256(raw).hexdigest(),
            )
        ):
            raise ValueError("stored product decision is not bound to this exact request")
        valid_days = request.get("valid_days")
        if (
            not isinstance(valid_days, int)
            or isinstance(valid_days, bool)
            or not 1 <= valid_days <= 366
            or _parse_time(receipt["expires_at"], "expires_at")
            - _parse_time(receipt["issued_at"], "issued_at")
            != timedelta(days=valid_days)
            or request.get("approver_id") != receipt["approved_by"]
        ):
            raise ValueError("stored product decision signer or validity differs from request")
        owner_client = request.get("owner_client")
        if (
            not isinstance(owner_client, dict)
            or set(owner_client) != {"version", "source_sha256"}
            or not isinstance(owner_client.get("version"), str)
            or not owner_client["version"].strip()
            or not isinstance(owner_client.get("source_sha256"), str)
            or SHA256_PATTERN.fullmatch(owner_client["source_sha256"]) is None
        ):
            raise ValueError("product decision Owner client binding is invalid")
        # Import lazily to avoid an autonomy/Owner-client module cycle.  Reuse is
        # authorized only while the currently installed reviewed client is still
        # byte-identical to the identity signed into the decision.
        from .owner_approval import _owner_client_identity

        current_owner_client = _owner_client_identity()
        if (
            owner_client.get("version") != current_owner_client.get("version")
            or not secrets.compare_digest(
                owner_client["source_sha256"],
                current_owner_client.get("source_sha256", ""),
            )
        ):
            raise ValueError(
                "stored product decision Owner client no longer matches the reviewed installed source"
            )
        marker = (
            OWNER_CLIENT_BINDING_PREFIX
            + json.dumps(
                owner_client,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
        ).encode("utf-8")
        assumption_artifacts = [
            snapshot.read(
                PurePosixPath(row["path"]),
                max_bytes=1024 * 1024,
            )
            for row in receipt["assumptions"]
        ]
        if _exact_line_occurrences(assumption_artifacts, marker) != 1:
            raise ValueError(
                "signed product decision does not bind one exact Owner client identity"
            )
        if (
            receipt.get("summary")
            != f"Approved option A: {options[0]['description']}"
        ):
            raise ValueError(
                "stored product decision summary differs from the exact request"
            )
        binding = _trusted_approver_domain(root, receipt["approved_by"])
        result = {
            "decision_id": decision_id,
            "approved_by": receipt["approved_by"],
            "repository_id": binding["repository_id"],
            "trust_domain": binding["trust_domain"],
            "expires_at": receipt["expires_at"],
            "receipt_sha256": receipt_sha256,
            "verification": "SIGNATURE_ROW_AUDIENCE_AND_REQUEST_VERIFIED",
        }
    return result


def _verify_external_action_resolution_envelope(
    root: Path, envelope: Any, *, require_fresh: bool
) -> tuple[dict[str, str], str]:
    """Verify one exact owner-signed terminal action assertion.

    Freshness is required while importing.  Once imported, the signature is
    rechecked on every reuse without expiring the historical completion: the
    receipt is bound to one immutable action ID, owner, scope, and request
    digest, so it cannot authorize a later action generation.
    """
    if (
        not isinstance(envelope, dict)
        or set(envelope) != {"schema_version", "algorithm", "receipt", "signature"}
        or envelope.get("schema_version") != "1.0"
        or envelope.get("algorithm") != "ed25519"
        or not isinstance(envelope.get("receipt"), dict)
        or not isinstance(envelope.get("signature"), str)
    ):
        raise ValueError("external action resolution has an invalid contract")
    receipt = envelope["receipt"]
    required = {
        "resolution_id",
        "action_id",
        "action_class",
        "owner",
        "scope",
        "request_sha256",
        "status",
        "evidence_sha256",
        "resolved_at",
        "expires_at",
        "nonce",
    }
    if set(receipt) != required or any(
        not isinstance(receipt.get(field), str) or not receipt[field].strip()
        for field in required
    ):
        raise ValueError("external action resolution payload has an invalid contract")
    if receipt["action_class"] not in {"operational_action", "necessary_uat"}:
        raise ValueError("external action resolution class is invalid")
    if receipt["status"] not in {"completed", "cancelled"}:
        raise ValueError("external action resolution status is invalid")
    if not SHA256_PATTERN.fullmatch(receipt["request_sha256"]):
        raise ValueError("external action resolution request_sha256 is invalid")
    if not SHA256_PATTERN.fullmatch(receipt["evidence_sha256"]):
        raise ValueError("external action resolution evidence_sha256 is invalid")
    if len(receipt["nonce"]) < 12:
        raise ValueError("external action resolution nonce must contain at least 12 characters")
    resolved_at = _parse_time(receipt["resolved_at"], "resolved_at")
    expires_at = _parse_time(receipt["expires_at"], "expires_at")
    current = _now()
    if resolved_at > current + timedelta(minutes=5):
        raise ValueError("external action resolution resolved_at is in the future")
    if expires_at <= resolved_at:
        raise ValueError("external action resolution is expired or invalid")
    if require_fresh and expires_at <= current:
        raise ValueError("external action resolution is expired or invalid")
    if expires_at - resolved_at > timedelta(days=7):
        raise ValueError("external action resolution validity exceeds seven days")
    approver = _trusted_approver(root, receipt["owner"])
    try:
        public_key = base64.b64decode(approver["public_key"], validate=True)
        signature = base64.b64decode(envelope["signature"], validate=True)
        Ed25519PublicKey.from_public_bytes(public_key).verify(
            signature, _canonical_receipt(receipt)
        )
    except (ValueError, binascii.Error, InvalidSignature) as exc:
        raise ValueError("external action resolution signature verification failed") from exc
    receipt_sha256 = hashlib.sha256(_canonical_receipt(receipt)).hexdigest()
    return receipt, receipt_sha256


def import_external_action_resolution(
    root: Path, envelope_path: Path
) -> dict[str, Any]:
    """Verify an owner-signed completion/cancellation and resolve one exact action."""
    envelope = _read_json(envelope_path)
    receipt, receipt_sha256 = _verify_external_action_resolution_envelope(
        root, envelope, require_fresh=True
    )
    resolved = resolve_external_action(
        root,
        action_id=receipt["action_id"],
        action_class=receipt["action_class"],
        owner=receipt["owner"],
        scope=receipt["scope"],
        request_sha256=receipt["request_sha256"],
        status=receipt["status"],
        resolved_at=receipt["resolved_at"],
        resolution_receipt_sha256=receipt_sha256,
        resolution_evidence_sha256=receipt["evidence_sha256"],
        resolution_envelope=envelope,
    )
    return {
        "action_id": resolved["action_id"],
        "action_class": resolved["action_class"],
        "status": resolved["status"],
        "state_changed": resolved["state_changed"],
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
    if (
        os.name != "posix"
        or sys.platform not in {"linux", "darwin"}
        or grp is None
        or not hasattr(os, "geteuid")
        or os.geteuid() == 0
    ):
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
    try:
        expected_group_id = grp.getgrnam(L3_NONCE_BROKER_GROUP).gr_gid
    except (AttributeError, KeyError, OSError, TypeError, ValueError):
        return False
    if (
        metadata.st_uid != 0
        or metadata.st_gid != expected_group_id
        or stat.S_IMODE(metadata.st_mode) != 0o660
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
    expected_response = b"CONSUMED\n"
    response = bytearray()
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(10)
            client.connect(str(L3_NONCE_BROKER))
            client.sendall(request)
            client.shutdown(socket.SHUT_WR)
            while len(response) <= len(expected_response):
                chunk = client.recv(len(expected_response) + 1 - len(response))
                if not chunk:
                    break
                response.extend(chunk)
                if len(response) > len(expected_response):
                    return False
    except OSError:
        return False
    return bytes(response) == expected_response


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


def _plain_l2_approval_matches(
    root: Path,
    decision: dict[str, Any],
    *,
    scope: Any,
    decision_package: Any = None,
) -> bool:
    required = {
        "decision_id",
        "risk_level",
        "summary",
        "scope",
        "basis",
        "status",
        "recorded_at",
        "reopen_condition",
        "approval_mode",
        "profile",
        "approved_by",
        "request_path",
        "request_sha256",
    }
    if (
        set(decision) != required
        or decision.get("risk_level") != "L2"
        or decision.get("status") != "approved"
        or decision.get("approval_mode") != "plain_language_owner_choice"
        or decision.get("profile") != "team-standard"
        or decision.get("approved_by") != "project_owner"
        or decision.get("reopen_condition") != "scope_or_assumptions_change"
        or not isinstance(scope, str)
        or not scope.strip()
        or decision.get("scope") != scope
    ):
        return False
    try:
        if _project_profile(root) != "team-standard":
            return False
        _parse_time(decision.get("recorded_at"), "recorded_at")
    except ValueError:
        return False
    basis = decision.get("basis")
    if not isinstance(basis, str) or not basis.startswith("owner_explicit_choice:"):
        return False
    selected = basis.removeprefix("owner_explicit_choice:").strip()
    if not selected:
        return False
    request_path = decision.get("request_path")
    request_sha256 = decision.get("request_sha256")
    if (
        not isinstance(request_path, str)
        or not isinstance(request_sha256, str)
        or SHA256_PATTERN.fullmatch(request_sha256) is None
    ):
        return False
    try:
        current_request_sha256 = _plain_l2_request_binding(
            root,
            request_path,
            decision_id=decision["decision_id"],
            scope=decision["scope"],
            selected_label=selected,
            decision_package=decision_package,
        )
    except (AttributeError, OSError, ValueError):
        return False
    if not secrets.compare_digest(current_request_sha256, request_sha256):
        return False
    return True


def _l2_approval_matches_verified(
    decision: dict[str, Any],
    *,
    scope: Any,
    receipt: dict[str, Any],
    receipt_sha256: str,
) -> bool:
    if (
        decision.get("risk_level") != "L2"
        or decision.get("status") != "approved"
        or not isinstance(scope, str)
        or not scope.strip()
    ):
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


def _l2_approval_matches(
    root: Path,
    decision: dict[str, Any],
    *,
    scope: Any,
) -> bool:
    if decision.get("approval_mode") == "plain_language_owner_choice":
        return _plain_l2_approval_matches(root, decision, scope=scope)
    try:
        receipt, receipt_sha256 = _verify_product_envelope(
            root, decision.get("approval_envelope")
        )
    except ValueError:
        return False
    return _l2_approval_matches_verified(
        decision,
        scope=scope,
        receipt=receipt,
        receipt_sha256=receipt_sha256,
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
    operation_payload: dict[str, Any] | None = None,
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
    if risk_level == "L3":
        _validate_operation_payload(operation_payload)
    elif operation_payload is not None:
        raise ValueError("only an L3 ACTION REQUIRED may contain operation_payload")
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
    if operation_payload is not None:
        package["operation_payload"] = operation_payload
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
    if package.get("risk_level") == "L3":
        payload = package.get("operation_payload")
        _validate_operation_payload(payload)
        lines.extend(
            [
                "",
                "Exact operation payload:",
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                ),
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


def _blocked(
    reason: str, next_action: str, *, detail: str | None = None
) -> dict[str, Any]:
    result = {
        "state": "BLOCKED",
        "requires_response": False,
        "reason": reason,
        "next_action": next_action,
    }
    if detail is not None:
        result["detail"] = detail
    return result


def _l0_l1_envelope_error(request: dict[str, Any]) -> str | None:
    """Return an error for a low-risk envelope that could encode an executable action.

    Free text and arbitrary nested parameters are never evidence that an action is
    low risk. Concrete targets and parameters belong to a separately typed executor
    contract; this classifier only pre-authorizes authority-free engineering records.
    """
    category = request["category"]
    allowed = {"risk_level", "category", "effects"}
    if category == "integrity_mismatch":
        allowed.add("unrelated_work_exists")
    elif category == "uncertainty":
        allowed.update({"machine_verifiable", "unrelated_work_exists"})
    elif category in {"operational_action", "necessary_uat"}:
        return None
    extra = set(request) - allowed
    if extra:
        return "low_risk_action_requires_closed_typed_executor_contract"
    if request.get("effects") != {}:
        return None
    for field in ("machine_verifiable", "unrelated_work_exists"):
        if field in request and not isinstance(request[field], bool):
            return "low_risk_action_boolean_field_is_invalid"
    return None


def _closed_category_envelope_error(request: dict[str, Any]) -> str | None:
    """Reject fields that belong to another authority or executor contract.

    The risk label is caller supplied, so the category schema must be closed before
    an existing approval is looked up.  In particular, a valid L2 product decision
    must never turn an embedded L3 operation payload into authorized work.
    """
    category = request["category"]
    allowed = {"risk_level", "category", "effects"}
    if category == "product_decision":
        allowed.update(
            {
                "decision_id",
                "decision_scope",
                "assumptions_sha256",
                "reopen_condition_triggered",
                "decision_package",
                "unrelated_work_exists",
                "assumption_paths",
                "approver_id",
                "valid_days",
                "owner_client",
            }
        )
    elif category in {"high_risk_operation", *HIGH_RISK_CATEGORIES}:
        allowed.update(
            {
                "approval_id",
                "operation_id",
                "operation_payload",
                "decision_package",
                "machine_verifiable",
                "unrelated_work_exists",
            }
        )
    elif category == "operational_action":
        allowed.update(
            {
                "action_id",
                "action_owner",
                "action_scope",
                "action_ttl_minutes",
                "decision_package",
                "unrelated_work_exists",
            }
        )
    elif category == "necessary_uat":
        if "machine_verifiable" in request:
            return "machine_verifiable_work_is_not_necessary_uat"
        allowed.update(
            {
                "uat_id",
                "uat_owner",
                "uat_scope",
                "uat_ttl_minutes",
                "decision_package",
                "unrelated_work_exists",
            }
        )
    elif category == "uncertainty":
        allowed.update(
            {"machine_verifiable", "unrelated_work_exists", "decision_package"}
        )
    elif category == "integrity_mismatch":
        allowed.add("unrelated_work_exists")
    extra = set(request) - allowed
    if extra:
        return "request_contains_fields_outside_closed_category_schema"
    return None


def _action_required_binding_error(
    request: dict[str, Any], package: dict[str, Any]
) -> str | None:
    """Bind the displayed decision to the exact outer authority request."""
    category = request["category"]
    risk = request["risk_level"]
    if category == "product_decision":
        expected_risk = "L2"
        identity = request.get("decision_id")
        scope = request.get("decision_scope")
    elif category in HIGH_RISK_CATEGORIES | {"high_risk_operation"}:
        expected_risk = "L3"
        identity = request.get("approval_id")
        if package.get("risk_level") != expected_risk:
            return "action_required_risk_does_not_match_request"
        payload = request.get("operation_payload")
        if not isinstance(payload, dict):
            return "l3_prompt_requires_exact_operation_payload"
        try:
            _validate_operation_payload(payload)
        except ValueError:
            return "l3_prompt_requires_exact_operation_payload"
        if (
            payload.get("category") != category
            or payload.get("effects") != request.get("effects")
        ):
            return "l3_prompt_payload_does_not_match_request"
        if package.get("operation_payload") != payload:
            return "l3_prompt_package_payload_does_not_match_request"
        if not isinstance(request.get("operation_id"), str) or not request["operation_id"].strip():
            return "l3_prompt_requires_operation_id"
        scope = payload.get("scope")
    elif category == "operational_action":
        expected_risk = "Operational"
        identity = request.get("action_id")
        scope = request.get("action_scope")
    elif category == "necessary_uat":
        expected_risk = "UAT"
        identity = request.get("uat_id")
        scope = request.get("uat_scope")
    else:
        expected_risk = risk
        identity = package.get("decision_id")
        scope = package.get("scope_of_approval")
    if package.get("risk_level") != expected_risk:
        return "action_required_risk_does_not_match_request"
    if not isinstance(identity, str) or not identity.strip():
        return "action_required_outer_identity_is_required"
    if package.get("decision_id") != identity:
        return "action_required_identity_does_not_match_request"
    if not isinstance(scope, str) or not scope.strip():
        return "action_required_outer_scope_is_required"
    if package.get("scope_of_approval") != scope:
        return "action_required_scope_does_not_match_request"
    return None


def evaluate_escalation(root: Path, request: dict[str, Any]) -> dict[str, Any]:
    risk = request.get("risk_level")
    category = request.get("category")
    if not isinstance(risk, str) or risk not in RISK_LEVELS:
        return {
            "state": "BLOCKED",
            "requires_response": False,
            "reason": "autonomy_request_has_an_invalid_contract",
            "next_action": "repair_the_machine_request_before_reclassification",
        }
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
    authority_fields = {
        "approval_id",
        "operation_id",
        "operation_payload",
        "decision_id",
        "decision_scope",
        "decision_package",
    }
    if risk in {"L0", "L1"} and category in ROUTINE_OPERATIONS and any(
        field in request for field in authority_fields
    ):
        return {
            "state": "BLOCKED",
            "requires_response": False,
            "reason": "authority_bearing_fields_not_allowed_for_routine_action",
            "next_action": "rebuild_request_with_one_exact_authority_class",
        }
    envelope_error = (
        _l0_l1_envelope_error(request) if risk in {"L0", "L1"} else None
    )
    if envelope_error:
        return {
            "state": "BLOCKED",
            "requires_response": False,
            "reason": envelope_error,
            "next_action": "use_one_closed_typed_executor_contract_or_remove_executable_fields",
        }
    category_envelope_error = _closed_category_envelope_error(request)
    if category_envelope_error:
        return {
            "state": "BLOCKED",
            "requires_response": False,
            "reason": category_envelope_error,
            "next_action": "rebuild_request_with_one_exact_category_schema",
        }
    if "public_publish" in effects and category != "public_release":
        return {
            "state": "BLOCKED",
            "requires_response": False,
            "reason": "public_publish_requires_canonical_public_release_category",
            "required_risk_levels": ["L3"],
            "required_category": "public_release",
            "reality_boundary": True,
            "next_action": "prepare_one_exact_public_release_operation",
        }
    if category == "public_release" and effects.get("public_publish") is not True:
        return {
            "state": "BLOCKED",
            "requires_response": False,
            "reason": "public_release_requires_public_publish_effect",
            "required_risk_levels": ["L3"],
            "reality_boundary": True,
            "next_action": "declare_the_public_publish_effect",
        }
    if category in {"merge", "release_readiness"} and effects:
        required_category = (
            "public_release" if "public_publish" in effects else "high_risk_operation"
        )
        return {
            "state": "BLOCKED",
            "requires_response": False,
            "reason": "reality_effect_requires_canonical_l3_operation",
            "required_risk_levels": ["L3"],
            "required_category": required_category,
            "reality_boundary": True,
            "next_action": "separate_readiness_from_the_exact_external_operation",
        }
    if category in {"merge", "release_readiness"} and risk != "L1":
        return {
            "state": "BLOCKED",
            "requires_response": False,
            "reason": f"{category}_requires_exact_l1_without_reality_effects",
            "required_risk_levels": ["L1"],
            "reality_boundary": False,
            "next_action": "reclassify_the_effect_free_engineering_channel_as_l1",
        }
    if category == "product_decision" and risk != "L2":
        return {
            "state": "BLOCKED",
            "requires_response": False,
            "reason": "product_decision_requires_exact_l2_risk",
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
    if category == "uncertainty":
        if request.get("machine_verifiable") is True:
            return _continue(
                "machine_verifiable_uncertainty_requires_investigation",
                "verify_with_repo_decisions_tests_ci_or_tools",
            )
        return {
            "state": (
                "CONTINUE" if request.get("unrelated_work_exists") else "BLOCKED"
            ),
            "requires_response": False,
            "reason": "uncertainty_must_be_investigated_not_escalated",
            "next_action": (
                "investigate_and_continue_unrelated_work"
                if request.get("unrelated_work_exists")
                else "investigate_and_reclassify_with_one_canonical_category"
            ),
        }
    if (
        not forced_human_category
        and category in ROUTINE_OPERATIONS
        and risk in {"L0", "L1"}
    ):
        result = _continue(
            "no_human_escalation_if_machine_verifiable",
            "verify_with_repo_decisions_tests_ci_or_tools",
        )
        if category in {"merge", "release_readiness"}:
            result.update(
                {
                    "channel": (
                        "release_readiness"
                        if category == "release_readiness"
                        else "development"
                    ),
                    "reality_boundary": False,
                    "owner_operations_required": 0,
                }
            )
        return result
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
    if risk == "L2" and category == "product_decision":
        recorded = _find_decision(root, decision_id)
        plain_language_match = bool(
            recorded
            and recorded.get("approval_mode") == "plain_language_owner_choice"
            and _plain_l2_approval_matches(
                root,
                recorded,
                scope=request.get("decision_scope"),
                decision_package=request.get("decision_package"),
            )
        )
        if (
            recorded
            and (
                plain_language_match
                or _l2_approval_matches(
                    root,
                    recorded,
                    scope=request.get("decision_scope"),
                )
            )
        ):
            if "decision_package" in request and not plain_language_match:
                if recorded.get("approval_mode") == "plain_language_owner_choice":
                    return {
                        "state": "BLOCKED",
                        "requires_response": False,
                        "reason": "existing_plain_language_decision_package_changed",
                        "next_action": "reopen_one_bounded_product_decision",
                    }
                return {
                    "state": "BLOCKED",
                    "requires_response": False,
                    "reason": "existing_decision_reuse_must_not_include_decision_package",
                    "next_action": "remove_the_new_package_or_reopen_one_bounded_product_decision",
                }
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
        if any(
            row.get("decision_id") == request.get("approval_id")
            for row in _decision_store(root)["decisions"]
        ):
            return {
                "state": "BLOCKED",
                "requires_response": False,
                "reason": "l3_approval_is_unavailable_expired_or_consumed",
                "next_action": "prepare_a_new_exact_operation_approval_id",
            }

    package_input = request.get("decision_package")
    if not isinstance(package_input, dict):
        return _blocked(
            "decision_package_has_an_invalid_contract",
            "rebuild_one_strict_decision_package",
            detail="a genuine escalation requires a strict decision_package",
        )
    try:
        package = build_action_required(**package_input)
    except (AttributeError, TypeError, ValueError) as exc:
        return _blocked(
            "decision_package_has_an_invalid_contract",
            "rebuild_one_strict_decision_package",
            detail=str(exc),
        )
    binding_error = _action_required_binding_error(request, package)
    if binding_error:
        return {
            "state": "BLOCKED",
            "requires_response": False,
            "reason": binding_error,
            "next_action": "bind_the_package_to_the_exact_outer_request",
        }
    external_action = None
    if category in {"operational_action", "necessary_uat"}:
        if category == "operational_action":
            action_id = request.get("action_id")
            owner = request.get("action_owner")
            scope = request.get("action_scope")
            ttl_minutes = request.get("action_ttl_minutes", 1440)
        else:
            action_id = request.get("uat_id")
            owner = request.get("uat_owner")
            scope = request.get("uat_scope")
            ttl_minutes = request.get("uat_ttl_minutes", 1440)
        if not isinstance(owner, str) or not owner.strip():
            return {
                "state": "BLOCKED",
                "requires_response": False,
                "reason": f"{category}_owner_is_required",
                "next_action": "bind_one_owner_and_bounded_scope_before_prompting",
            }
        try:
            external_action = enqueue_external_action(
                root,
                action_id,
                package["why_human_input_is_required"],
                risk,
                owner,
                scope=scope,
                ttl_minutes=ttl_minutes,
                action_class=category,
            )
        except ValueError as exc:
            invalid_terminal_proof = str(exc).startswith(
                "terminal external action row"
            )
            return {
                "state": "BLOCKED",
                "requires_response": False,
                "reason": (
                    f"{category}_resolution_is_untrusted"
                    if invalid_terminal_proof
                    else f"{category}_state_is_invalid"
                ),
                "detail": str(exc),
                "next_action": (
                    "import_one_exact_owner_signed_resolution_receipt"
                    if invalid_terminal_proof
                    else "repair_or_reissue_the_bounded_external_action"
                ),
            }
        if not external_action["external_action_created"]:
            if external_action["status"] in {"completed", "cancelled"}:
                try:
                    resolution, receipt_sha256 = (
                        _verify_external_action_resolution_envelope(
                            root,
                            external_action.get("resolution_envelope"),
                            require_fresh=False,
                        )
                    )
                except ValueError:
                    return {
                        "state": "BLOCKED",
                        "requires_response": False,
                        "reason": f"{category}_resolution_is_untrusted",
                        "next_action": "import_one_exact_owner_signed_resolution_receipt",
                    }
                if (
                    resolution.get("action_id") != external_action.get("action_id")
                    or resolution.get("action_class") != external_action.get("action_class")
                    or resolution.get("owner") != external_action.get("owner")
                    or resolution.get("scope") != external_action.get("scope")
                    or resolution.get("request_sha256")
                    != external_action.get("request_sha256")
                    or resolution.get("status") != external_action.get("status")
                    or receipt_sha256
                    != external_action.get("resolution_receipt_sha256")
                ):
                    return {
                        "state": "BLOCKED",
                        "requires_response": False,
                        "reason": f"{category}_resolution_is_untrusted",
                        "next_action": "import_one_exact_owner_signed_resolution_receipt",
                    }
                if external_action["status"] == "completed":
                    return _continue(f"{category}_already_completed")
                return {
                    "state": "BLOCKED",
                    "requires_response": False,
                    "reason": f"{category}_cancelled",
                    "external_action_created": False,
                    "action_id": external_action["action_id"],
                    "next_action": "issue_a_new_bounded_request_only_if_the_need_still_exists",
                }
            if external_action["status"] == "expired":
                return {
                    "state": "BLOCKED",
                    "requires_response": False,
                    "reason": f"{category}_{external_action['status']}",
                    "external_action_created": False,
                    "action_id": external_action["action_id"],
                    "next_action": "issue_a_new_bounded_request_only_if_the_need_still_exists",
                }
            return {
                "state": (
                    "CONTINUE" if request.get("unrelated_work_exists") else "BLOCKED"
                ),
                "requires_response": False,
                "reason": f"{category}_already_pending",
                "external_action_created": False,
                "action_id": external_action["action_id"],
                "next_action": (
                    "continue_unrelated_work"
                    if request.get("unrelated_work_exists")
                    else "wait_for_existing_bounded_owner_action"
                ),
            }
    if category in {"operational_action", "necessary_uat"} and request.get("unrelated_work_exists"):
        return {
            "state": "CONTINUE",
            "requires_response": False,
            "reason": f"{category}_blocks_only_dependent_work",
            "next_action": "queue_action_required_and_continue_unrelated_work",
            "action_required": package,
            "external_action_created": True,
            "action_id": external_action["action_id"],
        }
    if category not in {"operational_action", "necessary_uat"} and request.get(
        "unrelated_work_exists"
    ):
        return {
            "state": "CONTINUE",
            "requires_response": False,
            "reason": "human_decision_blocks_only_dependent_work",
            "next_action": "surface_action_required_and_continue_unrelated_work",
            "action_required": package,
        }
    result = {
        "state": "ACTION_REQUIRED",
        "requires_response": True,
        "reason": "human_judgment_required_by_policy",
        "decision_package": package,
    }
    if external_action is not None:
        result["external_action_created"] = True
        result["action_id"] = external_action["action_id"]
    return result


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
    if not isinstance(risk, str) or risk not in RISK_LEVELS:
        return {
            "ok": False,
            "state": "BLOCKED",
            "requires_response": False,
            "reason": "deployment_gate_has_an_invalid_contract",
            "next_action": "repair_the_machine_gate_before_reclassification",
        }
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
    if risk != "L3":
        return {
            "ok": False,
            "state": "BLOCKED",
            "requires_response": False,
            "reason": "actual_production_deploy_requires_exact_l3_operation",
            "required_risk_levels": ["L3"],
            "reality_boundary": True,
            "next_action": "prepare_release_readiness_then_one_exact_l3_deploy_operation",
        }
    request_input = gate.get("escalation_request")
    if not isinstance(request_input, dict):
        return {
            "ok": False,
            "state": "BLOCKED",
            "requires_response": False,
            "reason": "deployment_escalation_request_has_an_invalid_contract",
            "next_action": "prepare_one_exact_l3_escalation_request_object",
        }
    required_category = "high_risk_operation"
    supplied_risk = request_input.get("risk_level")
    supplied_category = request_input.get("category")
    if (
        supplied_risk is not None and not isinstance(supplied_risk, str)
    ) or (
        supplied_category is not None and not isinstance(supplied_category, str)
    ):
        return {
            "ok": False,
            "state": "BLOCKED",
            "requires_response": False,
            "reason": "deployment_escalation_request_has_an_invalid_contract",
            "next_action": "prepare_one_exact_l3_escalation_request_object",
        }
    if (
        supplied_risk not in (None, risk)
        or supplied_category not in (None, required_category)
    ):
        return {
            "ok": False,
            "state": "BLOCKED",
            "requires_response": False,
            "reason": "deployment_escalation_request_does_not_match_the_exact_l3_gate",
            "required_risk_levels": ["L3"],
            "required_category": required_category,
            "reality_boundary": True,
            "next_action": "rebuild_one_exact_l3_escalation_request_object",
        }
    request = dict(request_input)
    request["risk_level"] = risk
    request["category"] = required_category
    try:
        return evaluate_escalation(root, request)
    except (AttributeError, KeyError, TypeError, ValueError):
        return {
            "ok": False,
            "state": "BLOCKED",
            "requires_response": False,
            "reason": "deployment_escalation_request_has_an_invalid_contract",
            "next_action": "prepare_one_exact_l3_escalation_request_object",
        }
