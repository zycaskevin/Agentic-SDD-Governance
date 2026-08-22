from __future__ import annotations

import json
import os
import re
import stat
from pathlib import Path
from typing import Any

from .fs_security import canonicalize_platform_path


FULL_COMMIT_SHA = re.compile(r"[0-9a-fA-F]{40}")
TRUSTED_APPROVERS_FILE = Path("/etc/sddgov/trusted-approvers.json")
TRUSTED_APPROVER_DOMAINS_FILE = Path("/etc/sddgov/trusted-approver-domains.json")
TRUSTED_APPROVERS_ENVIRONMENT = "SDDGOV_TRUSTED_APPROVERS_FILE"
MAX_CONTROL_PLANE_BYTES = 1024 * 1024


class _DuplicateJSONMember(ValueError):
    pass


def _reject_duplicate_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, member in pairs:
        if key in value:
            raise _DuplicateJSONMember(f"duplicate JSON member: {key}")
        value[key] = member
    return value


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


def trusted_approver_domains_path(root: Path) -> Path:
    """Return the fixed repository/trust-domain binding sidecar path."""
    source = TRUSTED_APPROVER_DOMAINS_FILE.absolute()
    try:
        source.resolve().relative_to(root.resolve())
    except ValueError:
        return source
    raise ValueError("fixed trusted approver domain store must be outside the repository")


def load_owner_controlled_json(path: Path, label: str) -> dict[str, Any]:
    """Read one owner-only regular JSON file without following a final symlink."""
    candidate = canonicalize_platform_path(path.expanduser())
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
            value = json.load(
                handle,
                object_pairs_hook=_reject_duplicate_json_object,
            )
    except (OSError, json.JSONDecodeError, _DuplicateJSONMember) as exc:
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
    candidate = canonicalize_platform_path(path.expanduser())
    if not candidate.name or candidate.name in {".", ".."}:
        raise ValueError(f"{label} has an unsafe control-plane path")
    directory_flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0)
    )
    descriptors: list[int] = []
    descriptor = -1
    try:
        descriptors.append(os.open(candidate.anchor or os.sep, directory_flags))
        root_metadata = os.fstat(descriptors[0])
        if (
            not stat.S_ISDIR(root_metadata.st_mode)
            or root_metadata.st_uid != 0
            or root_metadata.st_mode & 0o022
        ):
            raise ValueError(
                f"{label} parent chain must be root-owned and not writable by group or other"
            )
        components = candidate.parent.parts[1:]
        for part in components:
            before = os.stat(
                part,
                dir_fd=descriptors[-1],
                follow_symlinks=False,
            )
            child = os.open(part, directory_flags, dir_fd=descriptors[-1])
            current = os.fstat(child)
            if (
                stat.S_ISLNK(before.st_mode)
                or not stat.S_ISDIR(before.st_mode)
                or not stat.S_ISDIR(current.st_mode)
                or (before.st_dev, before.st_ino) != (current.st_dev, current.st_ino)
                or current.st_uid != 0
                or current.st_mode & 0o022
            ):
                os.close(child)
                raise ValueError(
                    f"{label} parent chain must be root-owned and not writable by group or other"
                )
            descriptors.append(child)

        before = os.stat(
            candidate.name,
            dir_fd=descriptors[-1],
            follow_symlinks=False,
        )
        if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode):
            raise ValueError(f"{label} must be a non-symlink regular file")
        if before.st_uid != 0 or before.st_mode & 0o022:
            raise ValueError(
                f"{label} must be root-owned and not writable by group or other"
            )
        descriptor = os.open(
            candidate.name,
            os.O_RDONLY
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
            dir_fd=descriptors[-1],
        )
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink != 1
            or (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino)
            or opened.st_uid != 0
            or opened.st_mode & 0o022
        ):
            raise ValueError(
                f"{label} must remain a root-owned, non-linked regular file"
            )
        if opened.st_size > MAX_CONTROL_PLANE_BYTES:
            raise ValueError(f"{label} exceeds the {MAX_CONTROL_PLANE_BYTES}-byte limit")
        chunks: list[bytes] = []
        size = 0
        while True:
            chunk = os.read(descriptor, 64 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_CONTROL_PLANE_BYTES:
                raise ValueError(
                    f"{label} exceeds the {MAX_CONTROL_PLANE_BYTES}-byte limit"
                )
            chunks.append(chunk)
        final = os.fstat(descriptor)
        leaf = os.stat(
            candidate.name,
            dir_fd=descriptors[-1],
            follow_symlinks=False,
        )
        snapshot = (
            opened.st_dev,
            opened.st_ino,
            opened.st_size,
            opened.st_mtime_ns,
            opened.st_ctime_ns,
            opened.st_nlink,
        )
        if snapshot != (
            final.st_dev,
            final.st_ino,
            final.st_size,
            final.st_mtime_ns,
            final.st_ctime_ns,
            final.st_nlink,
        ) or snapshot != (
            leaf.st_dev,
            leaf.st_ino,
            leaf.st_size,
            leaf.st_mtime_ns,
            leaf.st_ctime_ns,
            leaf.st_nlink,
        ):
            raise ValueError(f"{label} changed while it was being read")
        for index, part in enumerate(components):
            current_path = os.stat(
                part,
                dir_fd=descriptors[index],
                follow_symlinks=False,
            )
            opened_directory = os.fstat(descriptors[index + 1])
            if (
                stat.S_ISLNK(current_path.st_mode)
                or not stat.S_ISDIR(current_path.st_mode)
                or (current_path.st_dev, current_path.st_ino)
                != (opened_directory.st_dev, opened_directory.st_ino)
                or opened_directory.st_uid != 0
                or opened_directory.st_mode & 0o022
            ):
                raise ValueError(f"{label} parent chain changed while it was being read")
        try:
            value = json.loads(
                b"".join(chunks).decode("utf-8"),
                object_pairs_hook=_reject_duplicate_json_object,
            )
        except (UnicodeDecodeError, json.JSONDecodeError, _DuplicateJSONMember) as exc:
            raise ValueError(f"invalid {label}: {exc}") from exc
    except OSError as exc:
        raise ValueError(f"{label} cannot be opened safely: {exc}") from exc
    finally:
        if descriptor >= 0:
            closing_descriptor = descriptor
            descriptor = -1
            try:
                os.close(closing_descriptor)
            except OSError:
                pass
        while descriptors:
            closing_descriptor = descriptors.pop()
            try:
                os.close(closing_descriptor)
            except OSError:
                pass
    if not isinstance(value, dict):
        raise ValueError(f"{label} must contain a JSON object")
    return value
