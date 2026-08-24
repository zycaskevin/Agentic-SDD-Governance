from __future__ import annotations

import fcntl
import hashlib
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import __version__


PROFILES = ("solo-fast", "team-standard", "regulated")


def now() -> datetime:
    return datetime.now(timezone.utc)


def stamp(value: datetime | None = None) -> str:
    return (value or now()).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def init_project(root: Path, profile: str) -> list[Path]:
    if profile not in PROFILES:
        raise ValueError(f"profile must be one of: {', '.join(PROFILES)}")
    state = root / ".sddgov"
    state.mkdir(parents=True, exist_ok=True)
    first_initialization = not (state / "project.json").exists()
    defaults = {
        state / "project.json": {
            "schema_version": "1.0", "governance_version": __version__,
            "profile": profile, "created_at": stamp(),
        },
        state / "work-claims.json": {"schema_version": "1.0", "claims": []},
        state / "external-actions.json": {"schema_version": "1.1", "actions": []},
        state / "decisions.json": {"schema_version": "1.0", "decisions": []},
        state / "trusted-approvers.json": {
            "schema_version": "1.0", "approvers": []
        },
        state / "trusted-reviewers.json": {
            "schema_version": "1.0", "reviewers": []
        },
    }
    created: list[Path] = []
    for path, value in defaults.items():
        if not path.exists():
            _write(path, value)
            created.append(path)
    events = state / "events.jsonl"
    if not events.exists():
        events.write_text("", encoding="utf-8")
        created.append(events)
    if first_initialization:
        emit_event(root, "governance_initialized", "L0", {"profile": profile})
    return created


def emit_event(root: Path, event_type: str, risk: str, payload: dict | None = None) -> dict:
    if risk not in {"L0", "L1", "L2", "L3"}:
        raise ValueError("risk must be L0, L1, L2, or L3")
    path = root / ".sddgov" / "events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "schema_version": "1.0", "event_type": event_type, "risk_level": risk,
        "at": stamp(), "payload": payload or {},
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    return event


def claim_work(root: Path, work_package: str, agent: str, ttl_minutes: int = 60) -> dict:
    if ttl_minutes < 1 or ttl_minutes > 1440:
        raise ValueError("ttl_minutes must be between 1 and 1440")
    path = root / ".sddgov" / "work-claims.json"
    data = _read(path, {"schema_version": "1.0", "claims": []})
    current = now()
    active = []
    for claim in data["claims"]:
        expiry = datetime.fromisoformat(claim["expires_at"].replace("Z", "+00:00"))
        if expiry > current and claim["status"] == "active":
            active.append(claim)
    if any(row["work_package"] == work_package for row in active):
        raise ValueError(f"work package already has an active claim: {work_package}")
    claim = {
        "work_package": work_package, "agent": agent, "status": "active",
        "claimed_at": stamp(current), "expires_at": stamp(current + timedelta(minutes=ttl_minutes)),
    }
    data["claims"] = active + [claim]
    _write(path, data)
    emit_event(root, "work_claimed", "L0", claim)
    return claim


_EXTERNAL_ACTION_BASE_FIELDS = {
    "action_id",
    "summary",
    "risk_level",
    "owner",
    "action_class",
    "scope",
    "status",
    "created_at",
    "expires_at",
    "request_sha256",
    "authorization_scope",
}
_EXTERNAL_ACTION_RESOLUTION_FIELDS = {
    "resolved_at",
    "resolution_receipt_sha256",
    "resolution_evidence_sha256",
    "resolution_envelope",
}


def _external_action_request_sha256(
    action_id: str,
    summary: str,
    risk: str,
    owner: str,
    action_class: str,
    scope: str,
) -> str:
    request = {
        "action_id": action_id,
        "summary": summary,
        "risk_level": risk,
        "owner": owner,
        "action_class": action_class,
        "scope": scope,
    }
    return hashlib.sha256(
        json.dumps(
            request,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _load_external_action_store(path: Path) -> dict:
    data = _read(path, {"schema_version": "1.1", "actions": []})
    if data == {"schema_version": "1.0", "actions": []}:
        return {"schema_version": "1.1", "actions": []}
    if isinstance(data, dict) and data.get("schema_version") == "1.0":
        raise ValueError(
            "legacy external action store 1.0 cannot be migrated automatically; "
            "archive it and re-queue each exact bounded action"
        )
    if (
        not isinstance(data, dict)
        or set(data) != {"schema_version", "actions"}
        or data.get("schema_version") != "1.1"
        or not isinstance(data.get("actions"), list)
    ):
        raise ValueError("external action store has an invalid contract")
    return data


def _validate_external_action_row(row: object) -> str:
    if not isinstance(row, dict):
        raise ValueError("external action row has an invalid contract")
    fields = set(row)
    missing = _EXTERNAL_ACTION_BASE_FIELDS - fields
    if missing:
        raise ValueError(
            f"external action row {sorted(missing)[0]} is required"
        )
    if fields - (
        _EXTERNAL_ACTION_BASE_FIELDS | _EXTERNAL_ACTION_RESOLUTION_FIELDS
    ):
        raise ValueError("external action row has an invalid field contract")
    for label in ("action_id", "summary", "owner", "scope"):
        if not isinstance(row.get(label), str) or not row[label].strip():
            raise ValueError(f"external action row {label} is required")
    risk = row.get("risk_level")
    if risk not in {"L1", "L2", "L3"}:
        raise ValueError("external action row risk_level is invalid")
    action_class = row.get("action_class")
    if action_class not in {"operational_action", "necessary_uat"}:
        raise ValueError("external action row action_class is invalid")
    status = row.get("status")
    if status not in {"pending", "completed", "cancelled", "expired"}:
        raise ValueError("external action row status is invalid")
    if row.get("authorization_scope") != "one concrete action only":
        raise ValueError("external action row authorization_scope is invalid")
    try:
        created = datetime.fromisoformat(
            str(row["created_at"]).replace("Z", "+00:00")
        )
        expiry = datetime.fromisoformat(
            str(row["expires_at"]).replace("Z", "+00:00")
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("external action row timestamps are invalid") from exc
    if created.tzinfo is None or expiry.tzinfo is None or expiry <= created:
        raise ValueError("external action row timestamps are invalid")
    expected_digest = _external_action_request_sha256(
        row["action_id"],
        row["summary"],
        risk,
        row["owner"],
        action_class,
        row["scope"],
    )
    if row.get("request_sha256") != expected_digest:
        raise ValueError("external action row request_sha256 is invalid")
    if status in {"completed", "cancelled"}:
        if not _EXTERNAL_ACTION_RESOLUTION_FIELDS.issubset(fields):
            raise ValueError("terminal external action row requires resolution proof")
        if (
            not isinstance(row.get("resolved_at"), str)
            or not row["resolved_at"].strip()
        ):
            raise ValueError("terminal external action row resolved_at is invalid")
        for label in ("resolution_receipt_sha256", "resolution_evidence_sha256"):
            digest = row.get(label)
            if (
                not isinstance(digest, str)
                or len(digest) != 64
                or any(character not in "0123456789abcdef" for character in digest)
            ):
                raise ValueError(f"terminal external action row {label} is invalid")
        if not isinstance(row.get("resolution_envelope"), dict):
            raise ValueError(
                "terminal external action row resolution_envelope is invalid"
            )
    elif status == "pending":
        if any(
            row.get(field) is not None
            for field in _EXTERNAL_ACTION_RESOLUTION_FIELDS
        ):
            raise ValueError("pending external action row cannot contain resolution proof")
    else:
        if (
            not isinstance(row.get("resolved_at"), str)
            or not row["resolved_at"].strip()
        ):
            raise ValueError("expired external action row resolved_at is invalid")
        if any(
            row.get(field) is not None
            for field in (
                "resolution_receipt_sha256",
                "resolution_evidence_sha256",
                "resolution_envelope",
            )
        ):
            raise ValueError(
                "expired external action row cannot contain signed resolution proof"
            )
    return risk


def _enqueue_external_action_unlocked(
    root: Path,
    action_id: str,
    summary: str,
    risk: str,
    owner: str,
    *,
    scope: str | None = None,
    ttl_minutes: int = 1440,
    action_class: str | None = None,
) -> dict:
    if (
        risk not in {"L1", "L2", "L3"}
        or action_class not in {"operational_action", "necessary_uat"}
    ):
        raise ValueError(
            "external action must be an explicitly classified Operational Action or Necessary UAT"
        )
    if not all(
        isinstance(value, str) and value.strip()
        for value in (action_id, summary, owner, scope)
    ):
        raise ValueError("external action requires action_id, summary, owner, and scope")
    if not isinstance(ttl_minutes, int) or isinstance(ttl_minutes, bool) or not 1 <= ttl_minutes <= 10080:
        raise ValueError("external action ttl_minutes must be between 1 and 10080")
    path = root / ".sddgov" / "external-actions.json"
    data = _load_external_action_store(path)
    validated_rows = [
        (_validate_external_action_row(row), row) for row in data["actions"]
    ]
    request_sha256 = _external_action_request_sha256(
        action_id, summary, risk, owner, action_class, scope
    )
    existing = [
        row
        for _row_risk, row in validated_rows
        if row.get("action_id") == action_id
    ]
    if len(existing) > 1:
        raise ValueError(f"duplicate external action state: {action_id}")
    if existing:
        row = existing[0]
        if row.get("request_sha256") != request_sha256:
            raise ValueError(f"external action identity changed: {action_id}")
        if row.get("status") not in {
            "pending", "completed", "cancelled", "expired"
        }:
            raise ValueError(f"external action status is invalid: {action_id}")
        if row["status"] != "pending":
            return {**row, "external_action_created": False}
        try:
            expiry = datetime.fromisoformat(
                str(row["expires_at"]).replace("Z", "+00:00")
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("external action expiry is invalid") from exc
        if expiry.tzinfo is None:
            raise ValueError("external action expiry is invalid")
        if expiry <= now():
            row["status"] = "expired"
            row["resolved_at"] = stamp()
            row["resolution_receipt_sha256"] = None
            row["resolution_evidence_sha256"] = None
            row["resolution_envelope"] = None
            _write(path, data)
            emit_event(
                root,
                "external_action_expired",
                row["risk_level"],
                {"action_id": action_id},
            )
            return {**row, "external_action_created": False}
        return {**row, "external_action_created": False}
    current = now()
    item = {
        "action_id": action_id, "summary": summary, "risk_level": risk,
        "owner": owner, "action_class": action_class, "scope": scope,
        "status": "pending", "created_at": stamp(current),
        "expires_at": stamp(current + timedelta(minutes=ttl_minutes)),
        "request_sha256": request_sha256,
        "authorization_scope": "one concrete action only",
    }
    data["actions"].append(item)
    _write(path, data)
    emit_event(root, "external_action_queued", risk, {"action_id": action_id})
    return {**item, "external_action_created": True}


def resolve_external_action(
    root: Path,
    *,
    action_id: str,
    action_class: str,
    owner: str,
    scope: str,
    request_sha256: str,
    status: str,
    resolved_at: str,
    resolution_receipt_sha256: str,
    resolution_evidence_sha256: str,
    resolution_envelope: dict,
) -> dict:
    """Apply one exact, independently verified terminal transition.

    Signature and trust-root verification happen before this state mutation.  The
    stored action identity is rechecked while holding the same lock used by queue
    creation so a completion can never resolve a different owner, scope, or
    request generation.
    """
    if status not in {"completed", "cancelled"}:
        raise ValueError("external action resolution status must be completed or cancelled")
    for label, value in (
        ("action_id", action_id),
        ("action_class", action_class),
        ("owner", owner),
        ("scope", scope),
        ("resolved_at", resolved_at),
    ):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"external action resolution {label} is required")
    for label, digest in (
        ("request_sha256", request_sha256),
        ("resolution_receipt_sha256", resolution_receipt_sha256),
        ("resolution_evidence_sha256", resolution_evidence_sha256),
    ):
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise ValueError(f"external action resolution {label} is invalid")
    if not isinstance(resolution_envelope, dict):
        raise ValueError("external action resolution envelope is invalid")

    lock_path = root / ".sddgov" / "external-actions.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            path = root / ".sddgov" / "external-actions.json"
            data = _load_external_action_store(path)
            validated_rows = [
                (_validate_external_action_row(row), row) for row in data["actions"]
            ]
            matches = [row for row in data["actions"] if row.get("action_id") == action_id]
            if len(matches) != 1:
                raise ValueError("external action resolution requires one exact action")
            row = matches[0]
            risk_level = next(
                validated_risk
                for validated_risk, validated_row in validated_rows
                if validated_row is row
            )
            expected = {
                "action_class": action_class,
                "owner": owner,
                "scope": scope,
                "request_sha256": request_sha256,
            }
            if any(row.get(field) != value for field, value in expected.items()):
                raise ValueError("external action resolution identity does not match pending action")
            if row.get("status") == status:
                if row.get("resolution_receipt_sha256") != resolution_receipt_sha256:
                    raise ValueError("external action was resolved by a different receipt")
                return {**row, "state_changed": False}
            if row.get("status") != "pending":
                raise ValueError("external action is not pending")
            try:
                expiry = datetime.fromisoformat(
                    str(row["expires_at"]).replace("Z", "+00:00")
                )
                resolution_time = datetime.fromisoformat(
                    resolved_at.replace("Z", "+00:00")
                )
                created_time = datetime.fromisoformat(
                    str(row["created_at"]).replace("Z", "+00:00")
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError("external action resolution timestamp is invalid") from exc
            if (
                expiry.tzinfo is None
                or resolution_time.tzinfo is None
                or created_time.tzinfo is None
            ):
                raise ValueError("external action resolution timestamp requires a timezone")
            if resolution_time < created_time or resolution_time > expiry:
                raise ValueError("external action resolution is outside the action lifetime")
            row.update(
                {
                    "status": status,
                    "resolved_at": resolved_at,
                    "resolution_receipt_sha256": resolution_receipt_sha256,
                    "resolution_evidence_sha256": resolution_evidence_sha256,
                    "resolution_envelope": resolution_envelope,
                }
            )
            _write(path, data)
            emit_event(
                root,
                f"external_action_{status}",
                risk_level,
                {"action_id": action_id, "action_class": action_class},
            )
            return {**row, "state_changed": True}
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def enqueue_external_action(
    root: Path,
    action_id: str,
    summary: str,
    risk: str,
    owner: str,
    *,
    scope: str | None = None,
    ttl_minutes: int = 1440,
    action_class: str | None = None,
) -> dict:
    lock_path = root / ".sddgov" / "external-actions.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            return _enqueue_external_action_unlocked(
                root,
                action_id,
                summary,
                risk,
                owner,
                scope=scope,
                ttl_minutes=ttl_minutes,
                action_class=action_class,
            )
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def project_status(root: Path) -> dict:
    state = root / ".sddgov"
    project = _read(state / "project.json", None)
    if project is None:
        raise FileNotFoundError(".sddgov/project.json; run sddgov init first")
    claims = _read(state / "work-claims.json", {"claims": []})["claims"]
    actions = _read(state / "external-actions.json", {"actions": []})["actions"]
    decisions = _read(state / "decisions.json", {"decisions": []})["decisions"]
    current = now()
    active = 0
    expired = 0
    for claim in claims:
        expiry = datetime.fromisoformat(claim["expires_at"].replace("Z", "+00:00"))
        if claim["status"] == "active" and expiry > current:
            active += 1
        elif claim["status"] == "active":
            expired += 1
    event_count = 0
    events = state / "events.jsonl"
    if events.exists():
        event_count = sum(1 for line in events.read_text(encoding="utf-8").splitlines() if line.strip())
    return {
        "governance_version": project["governance_version"], "profile": project["profile"],
        "active_claims": active, "expired_claims": expired,
        "pending_external_actions": sum(1 for row in actions if row["status"] == "pending"),
        "recorded_decisions": len(decisions),
        "event_count": event_count,
    }
