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
        or action_class != "operational_action"
    ):
        raise ValueError(
            "external action must be an explicitly classified Operational Action"
        )
    if not all(
        isinstance(value, str) and value.strip()
        for value in (action_id, summary, owner, scope)
    ):
        raise ValueError("external action requires action_id, summary, owner, and scope")
    if not isinstance(ttl_minutes, int) or isinstance(ttl_minutes, bool) or not 1 <= ttl_minutes <= 10080:
        raise ValueError("external action ttl_minutes must be between 1 and 10080")
    path = root / ".sddgov" / "external-actions.json"
    data = _read(path, {"schema_version": "1.1", "actions": []})
    if data == {"schema_version": "1.0", "actions": []}:
        data = {"schema_version": "1.1", "actions": []}
    if (
        not isinstance(data, dict)
        or set(data) != {"schema_version", "actions"}
        or data.get("schema_version") != "1.1"
        or not isinstance(data.get("actions"), list)
    ):
        raise ValueError("external action store has an invalid contract")
    request = {
        "action_id": action_id,
        "summary": summary,
        "risk_level": risk,
        "owner": owner,
        "action_class": action_class,
        "scope": scope,
    }
    request_sha256 = hashlib.sha256(
        json.dumps(
            request,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    existing = [row for row in data["actions"] if row.get("action_id") == action_id]
    if len(existing) > 1:
        raise ValueError(f"duplicate external action state: {action_id}")
    if existing:
        row = existing[0]
        if row.get("request_sha256") != request_sha256:
            raise ValueError(f"external action identity changed: {action_id}")
        if row.get("status") != "pending":
            raise ValueError(f"external action is not pending: {action_id}")
        try:
            expiry = datetime.fromisoformat(
                str(row["expires_at"]).replace("Z", "+00:00")
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("external action expiry is invalid") from exc
        if expiry.tzinfo is None or expiry <= now():
            raise ValueError(
                f"external action expired; create a new bounded action_id: {action_id}"
            )
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
