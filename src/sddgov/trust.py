from __future__ import annotations

import json
import os
import re
import stat
from pathlib import Path
from typing import Any


FULL_COMMIT_SHA = re.compile(r"[0-9a-fA-F]{40}")
TRUSTED_APPROVERS_FILE = Path("/etc/sddgov/trusted-approvers.json")
TRUSTED_APPROVERS_ENVIRONMENT = "SDDGOV_TRUSTED_APPROVERS_FILE"


def require_full_commit_sha(value: str | None, label: str) -> str:
    """Accept only an immutable full Git commit identifier."""
    if not isinstance(value, str) or FULL_COMMIT_SHA.fullmatch(value) is None:
        raise ValueError(f"{label} must be a full 40-character commit SHA")
    return value.lower()


def trusted_approvers_path(root: Path) -> Path:
    """Return the only runtime approver authority path.

    The retired environment variable is rejected even when it names the fixed
    path. Otherwise an Agent-controlled process environment remains an apparent
    authority-selection mechanism and unsafe deployments can silently rely on it.
    """
    if TRUSTED_APPROVERS_ENVIRONMENT in os.environ:
        raise ValueError(
            f"caller override {TRUSTED_APPROVERS_ENVIRONMENT} is forbidden; "
            f"trusted approver authority is fixed at {TRUSTED_APPROVERS_FILE}"
        )
    source = TRUSTED_APPROVERS_FILE.absolute()
    try:
        source.resolve().relative_to(root.resolve())
    except ValueError:
        return source
    raise ValueError("fixed trusted approver store must be outside the repository")


def load_owner_controlled_json(path: Path, label: str) -> dict[str, Any]:
    """Read one owner-only regular JSON file without following a final symlink."""
    candidate = path.expanduser().absolute()
    try:
        before = candidate.lstat()
    except OSError as exc:
        raise ValueError(f"{label} is unavailable: {exc}") from exc
    if stat.S_ISLNK(before.st_mode):
        raise ValueError(f"{label} must not be a symbolic link")
    if not stat.S_ISREG(before.st_mode):
        raise ValueError(f"{label} must be a regular file")

    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(candidate, flags)
    except OSError as exc:
        raise ValueError(f"{label} cannot be opened safely: {exc}") from exc
    try:
        current = os.fstat(descriptor)
        if (before.st_dev, before.st_ino) != (current.st_dev, current.st_ino):
            raise ValueError(f"{label} changed while it was being opened")
        if not stat.S_ISREG(current.st_mode):
            raise ValueError(f"{label} must be a regular file")
        if current.st_nlink != 1:
            raise ValueError(f"{label} must not be hard-linked")
        if os.name != "nt" and current.st_uid != os.geteuid():
            raise ValueError(f"{label} must be owned by the current user")
        if os.name != "nt" and current.st_mode & 0o077:
            raise ValueError(f"{label} must have owner-only permissions (0600)")
        with os.fdopen(descriptor, "r", encoding="utf-8") as handle:
            descriptor = -1
            value = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid {label}: {exc}") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    if not isinstance(value, dict):
        raise ValueError(f"{label} must contain a JSON object")
    return value


def load_control_plane_json(path: Path, label: str) -> dict[str, Any]:
    """Load authority only from a Unix root-owned, non-writable control-plane file.

    A 0600 file owned by the current user is not an authority boundary when an
    Agent runs as that same user. Non-POSIX hosts fail closed until an external
    broker or platform ACL implementation is provided.
    """
    if os.name == "nt" or not hasattr(os, "geteuid"):
        raise ValueError(f"{label} requires an independent control-plane identity")
    if os.geteuid() == 0:
        raise ValueError(
            f"{label} cannot establish a separate identity while the Agent runs as root"
        )
    candidate = path.expanduser().absolute()
    try:
        before = candidate.lstat()
    except OSError as exc:
        raise ValueError(f"{label} is unavailable: {exc}") from exc
    if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode):
        raise ValueError(f"{label} must be a non-symlink regular file")
    if before.st_uid != 0 or before.st_mode & 0o022:
        raise ValueError(
            f"{label} must be root-owned and not writable by group or other"
        )
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(candidate, flags)
    except OSError as exc:
        raise ValueError(f"{label} cannot be opened safely: {exc}") from exc
    try:
        current = os.fstat(descriptor)
        if (before.st_dev, before.st_ino) != (current.st_dev, current.st_ino):
            raise ValueError(f"{label} changed while it was being opened")
        if not stat.S_ISREG(current.st_mode) or current.st_nlink != 1:
            raise ValueError(f"{label} must be a non-linked regular file")
        if current.st_uid != 0 or current.st_mode & 0o022:
            raise ValueError(
                f"{label} must remain root-owned and not writable by group or other"
            )
        with os.fdopen(descriptor, "r", encoding="utf-8") as handle:
            descriptor = -1
            value = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid {label}: {exc}") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    if not isinstance(value, dict):
        raise ValueError(f"{label} must contain a JSON object")
    return value
