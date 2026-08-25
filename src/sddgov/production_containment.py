"""Offline-only contracts for a future Trusted Runner production boundary.

This module intentionally does not create a cgroup or execute a runtime.  A
service manager must supply an atomic cgroup-launch primitive before production
can be enabled.  The classes here make that prerequisite explicit and testable.
"""

from __future__ import annotations

import hashlib
import os
import stat
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final


class ProductionContainmentViolation(RuntimeError):
    """Fail-closed error containing a schema-safe reason code."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


_ELF_MAGIC: Final = b"\x7fELF"


@dataclass(frozen=True, slots=True)
class CgroupLimits:
    """Fixed limits that must be installed before an atomic child launch."""

    pids_max: int
    memory_max: int
    cpu_max: str

    def __post_init__(self) -> None:
        if self.pids_max < 1 or self.memory_max < 1:
            raise ProductionContainmentViolation("cgroup_limits_invalid")
        quota, separator, period = self.cpu_max.partition(" ")
        if not separator or not quota.isdecimal() or not period.isdecimal():
            raise ProductionContainmentViolation("cgroup_limits_invalid")
        if int(quota) < 1 or int(period) < 1:
            raise ProductionContainmentViolation("cgroup_limits_invalid")


@dataclass(slots=True)
class RuntimeImage:
    """A verified, held ELF runtime descriptor.

    The descriptor is the authority.  Its source path is never returned and it
    is deliberately not executed by Python: production requires a native
    `execveat(AT_EMPTY_PATH)`/`fexecve` launcher supplied by a later service
    integration work package.
    """

    descriptor: int
    expected_sha256: str
    device: int
    inode: int

    @classmethod
    def open_verified(
        cls,
        path: str | Path,
        *,
        expected_sha256: str,
        allowed_uids: frozenset[int],
    ) -> RuntimeImage:
        candidate = Path(path).expanduser().absolute()
        if (
            not expected_sha256.startswith("sha256:")
            or len(expected_sha256) != 71
            or any(value not in "0123456789abcdef" for value in expected_sha256[7:])
        ):
            raise ProductionContainmentViolation("runtime_image_hash_invalid")
        try:
            descriptor = os.open(
                candidate,
                os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
            )
        except OSError as exc:
            raise ProductionContainmentViolation("runtime_image_unavailable") from exc
        try:
            info = os.fstat(descriptor)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_nlink != 1
                or info.st_uid not in allowed_uids
                or info.st_mode & 0o022
            ):
                raise ProductionContainmentViolation("runtime_image_metadata_invalid")
            os.lseek(descriptor, 0, os.SEEK_SET)
            digest = hashlib.sha256()
            prefix = os.read(descriptor, len(_ELF_MAGIC))
            digest.update(prefix)
            while True:
                chunk = os.read(descriptor, 128 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
            observed = "sha256:" + digest.hexdigest()
            if prefix != _ELF_MAGIC:
                raise ProductionContainmentViolation("runtime_image_not_elf")
            if observed != expected_sha256:
                raise ProductionContainmentViolation("runtime_image_hash_mismatch")
            os.lseek(descriptor, 0, os.SEEK_SET)
            return cls(descriptor, expected_sha256, info.st_dev, info.st_ino)
        except Exception:
            os.close(descriptor)
            raise

    def verify_held_identity(self) -> None:
        try:
            info = os.fstat(self.descriptor)
        except OSError as exc:
            raise ProductionContainmentViolation("runtime_image_fd_unavailable") from exc
        if (
            not stat.S_ISREG(info.st_mode)
            or (info.st_dev, info.st_ino) != (self.device, self.inode)
            or info.st_mode & 0o022
        ):
            raise ProductionContainmentViolation("runtime_image_fd_identity_changed")
        os.lseek(self.descriptor, 0, os.SEEK_SET)
        digest = hashlib.sha256()
        while True:
            chunk = os.read(self.descriptor, 128 * 1024)
            if not chunk:
                break
            digest.update(chunk)
        os.lseek(self.descriptor, 0, os.SEEK_SET)
        if "sha256:" + digest.hexdigest() != self.expected_sha256:
            raise ProductionContainmentViolation("runtime_image_fd_hash_changed")

    def close(self) -> None:
        if self.descriptor >= 0:
            os.close(self.descriptor)
            self.descriptor = -1


@dataclass(slots=True)
class SyntheticCgroupV2Scope:
    """Deterministic offline state machine; never a kernel cgroup controller."""

    limits: CgroupLimits
    configured: bool = False
    atomically_attached: bool = False
    killed: bool = False
    populated: bool = False
    removed: bool = False
    events: list[str] = field(default_factory=list)

    def configure(self) -> None:
        if self.configured or self.removed:
            raise ProductionContainmentViolation("cgroup_scope_state_invalid")
        self.configured = True
        self.events.append("limits_configured")

    def attach_at_launch(self) -> None:
        if not self.configured or self.killed or self.removed:
            raise ProductionContainmentViolation("cgroup_atomic_attach_required")
        self.atomically_attached = True
        self.populated = True
        self.events.append("atomically_attached")

    def kill_and_wait_empty(self, *, timeout_seconds: float = 1.0) -> None:
        if not self.atomically_attached or self.removed or timeout_seconds <= 0:
            raise ProductionContainmentViolation("cgroup_cleanup_invalid")
        self.killed = True
        self.events.append("cgroup_kill")
        deadline = time.monotonic() + timeout_seconds
        # The synthetic backend deterministically models the required kernel
        # observation without touching the host hierarchy.
        self.populated = False
        if self.populated or time.monotonic() > deadline:
            raise ProductionContainmentViolation("cgroup_not_empty_after_kill")
        self.events.append("populated_zero")

    def remove(self) -> None:
        if not self.killed or self.populated or self.removed:
            raise ProductionContainmentViolation("cgroup_remove_denied")
        self.removed = True
        self.events.append("scope_removed")


def production_activation_permitted() -> bool:
    """AF27 deliberately never authorizes production activation."""

    return False
