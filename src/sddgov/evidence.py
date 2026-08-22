from __future__ import annotations

import errno
import hashlib
import json
import os
import re
import stat
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path, PurePosixPath

from .fs_security import (
    canonicalize_platform_path,
    exclusive_rename_at,
    remove_owned_at,
)
from .redaction import (
    MAX_REDACTION_FILE_BYTES,
    TEXT_SUFFIXES,
    redact_files,
    redact_text,
)
from .schema_validation import bundled_schema, validate_instance


COLLECTORS = {
    "browser-console", "browser-har", "playwright-trace", "flutter-log",
    "android-logcat", "supabase-log", "docker-log", "terminal", "git",
}
PHASES = ("red", "evidence", "fix", "green", "proof")
MANIFEST_SCHEMA_VERSION = "1.1"
LEGACY_MANIFEST_SCHEMA_VERSION = "1.0"
DEP_ID_PATTERN = re.compile(r"^DEP-[A-Za-z0-9._-]+$")
SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
MAX_DEP_CONTROL_FILE_BYTES = 1024 * 1024
MAX_DEP_ARTIFACT_BYTES = MAX_REDACTION_FILE_BYTES
REQUIRED_DOCS = {
    "red": ("reproduction.md",),
    "evidence": ("reproduction.md", "redaction-report.json"),
    "fix": ("reproduction.md", "root-cause-hypothesis.md", "fix-scope.md", "redaction-report.json"),
    "green": ("reproduction.md", "root-cause-hypothesis.md", "fix-scope.md", "regression-evidence.md", "verification.md", "redaction-report.json"),
    "proof": ("reproduction.md", "root-cause-hypothesis.md", "fix-scope.md", "regression-evidence.md", "verification.md", "rollback.md", "redaction-report.json"),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _resource_dir():
    return resources.files("sddgov").joinpath("resources/dep")


def _close_directory_descriptors(descriptors: list[int]) -> None:
    """Close every read-only directory fd without reversing committed work."""
    while descriptors:
        descriptor = descriptors.pop()
        try:
            os.close(descriptor)
        except OSError:
            # A directory close error cannot roll back an already-published
            # generation and close(2) must never be retried after an error.
            pass


class _MutationTransaction:
    """Defer publication finalization until the retained path lease is valid."""

    def __init__(self) -> None:
        self._rollback: list[object] = []
        self._finalize: list[object] = []
        self._verify: list[object] = []
        self._directory_fds: list[int] = []
        self._finished = False

    def retain_directory(self, directory_fd: int) -> int:
        """Retain a transaction-owned duplicate without reopening a pathname."""
        if self._finished:
            raise RuntimeError("mutation transaction is already finished")
        retained = os.dup(directory_fd)
        self._directory_fds.append(retained)
        return retained

    def add(self, rollback, finalize=None, verify=None) -> None:
        if self._finished:
            raise RuntimeError("mutation transaction is already finished")
        self._rollback.append(rollback)
        if finalize is not None:
            self._finalize.append(finalize)
        if verify is not None:
            self._verify.append(verify)

    def _close_directories(self) -> None:
        while self._directory_fds:
            descriptor = self._directory_fds.pop()
            try:
                os.close(descriptor)
            except OSError:
                # A retained directory fd is only a lease. Closing it cannot
                # reverse a transaction that was already finalized or rolled back.
                pass

    def rollback(self, _directory_fd: int | None = None) -> None:
        if self._finished:
            return
        self._finished = True
        cleanup_error: BaseException | None = None
        for operation in reversed(self._rollback):
            try:
                operation()
            except BaseException as exc:
                if cleanup_error is None:
                    cleanup_error = exc
        self._rollback.clear()
        self._finalize.clear()
        self._verify.clear()
        self._close_directories()
        if cleanup_error is not None:
            raise cleanup_error

    def finalize(self, _directory_fd: int | None = None) -> None:
        if self._finished:
            return
        verify_error: BaseException | None = None
        for operation in self._verify:
            try:
                operation()
            except BaseException as exc:
                verify_error = exc
                break
        if verify_error is not None:
            try:
                self.rollback()
            except BaseException as cleanup_error:
                raise verify_error from cleanup_error
            raise verify_error
        finalize_error: BaseException | None = None
        for operation in self._finalize:
            try:
                operation()
            except BaseException as exc:
                if finalize_error is None:
                    finalize_error = exc
        if finalize_error is not None:
            try:
                self.rollback()
            except BaseException as cleanup_error:
                raise finalize_error from cleanup_error
            raise finalize_error
        self._finished = True
        self._rollback.clear()
        self._finalize.clear()
        self._verify.clear()
        self._close_directories()


def _notify_path_change(on_change, descriptor: int, error: ValueError) -> None:
    if on_change is None:
        raise error
    try:
        on_change(descriptor)
    except BaseException as cleanup_error:
        raise error from cleanup_error
    raise error


@contextmanager
def _opened_directory_path(
    path: Path,
    *,
    create: bool,
    on_change=None,
    on_commit=None,
):
    """Walk an absolute directory path without following mutable components."""
    candidate = canonicalize_platform_path(path)
    if any(part in {"", ".", ".."} for part in candidate.parts[1:]):
        raise ValueError("directory path is not normalized")
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    directory_flags |= getattr(os, "O_NOFOLLOW", 0)
    anchor = Path(candidate.anchor or os.sep)
    descriptors = [os.open(anchor, directory_flags)]
    components: list[str] = []
    try:
        for part in candidate.parts[1:]:
            try:
                child = os.open(part, directory_flags, dir_fd=descriptors[-1])
            except FileNotFoundError:
                if not create:
                    raise
                os.mkdir(part, 0o755, dir_fd=descriptors[-1])
                child = os.open(part, directory_flags, dir_fd=descriptors[-1])
            except OSError as exc:
                error = ValueError(
                    f"directory path cannot be opened safely: {candidate}"
                )
                if on_change is not None:
                    try:
                        on_change(descriptors[-1])
                    except BaseException as cleanup_error:
                        raise error from cleanup_error
                raise error from exc
            metadata = os.fstat(child)
            if not stat.S_ISDIR(metadata.st_mode):
                os.close(child)
                raise ValueError(f"directory path component is unsafe: {candidate}")
            descriptors.append(child)
            components.append(part)
        try:
            yield candidate, descriptors[-1]
        except BaseException as primary:
            if on_change is not None:
                try:
                    on_change(descriptors[-1])
                except BaseException as cleanup_error:
                    raise primary from cleanup_error
            raise
        for index, part in enumerate(components):
            try:
                current = os.stat(
                    part, dir_fd=descriptors[index], follow_symlinks=False
                )
            except OSError as exc:
                error = ValueError(
                    f"directory path changed during operation: {candidate}"
                )
                if on_change is not None:
                    try:
                        on_change(descriptors[-1])
                    except BaseException as cleanup_error:
                        raise error from cleanup_error
                raise error from exc
            opened = os.fstat(descriptors[index + 1])
            if (
                stat.S_ISLNK(current.st_mode)
                or not stat.S_ISDIR(current.st_mode)
                or (current.st_dev, current.st_ino) != (opened.st_dev, opened.st_ino)
            ):
                _notify_path_change(
                    on_change,
                    descriptors[-1],
                    ValueError(
                        f"directory path changed during operation: {candidate}"
                    ),
                )
        if on_commit is not None:
            on_commit(descriptors[-1])
    finally:
        _close_directory_descriptors(descriptors)


@contextmanager
def _opened_dep_root(dep: Path, *, on_change=None, on_commit=None):
    try:
        with _opened_directory_path(
            dep,
            create=False,
            on_change=on_change,
            on_commit=on_commit,
        ) as (_, descriptor):
            yield descriptor
    except FileNotFoundError as exc:
        raise ValueError("DEP root must be an existing safe directory path") from exc


@contextmanager
def _opened_zone_at(
    root_fd: int,
    relative: Path,
    *,
    create: bool = True,
    on_change=None,
):
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        raise ValueError(f"evidence zone is not normalized: {relative}")
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    directory_flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptors = [os.dup(root_fd)]
    components: list[str] = []
    try:
        for part in relative.parts:
            try:
                child = os.open(part, directory_flags, dir_fd=descriptors[-1])
            except FileNotFoundError:
                if not create:
                    raise
                os.mkdir(part, dir_fd=descriptors[-1])
                child = os.open(part, directory_flags, dir_fd=descriptors[-1])
            except OSError as exc:
                raise ValueError(f"evidence zone cannot be opened safely: {relative}") from exc
            metadata = os.fstat(child)
            if not stat.S_ISDIR(metadata.st_mode):
                os.close(child)
                raise ValueError(f"evidence zone component is not a directory: {relative}")
            descriptors.append(child)
            components.append(part)
        try:
            yield descriptors[-1]
        except BaseException as primary:
            if on_change is not None:
                try:
                    on_change(descriptors[-1])
                except BaseException as cleanup_error:
                    raise primary from cleanup_error
            raise
        for index, part in enumerate(components):
            try:
                current = os.stat(
                    part, dir_fd=descriptors[index], follow_symlinks=False
                )
            except OSError as exc:
                if on_change is not None:
                    on_change(descriptors[-1])
                raise ValueError(
                    f"evidence zone changed during operation: {relative}"
                ) from exc
            opened = os.fstat(descriptors[index + 1])
            if (
                stat.S_ISLNK(current.st_mode)
                or not stat.S_ISDIR(current.st_mode)
                or (current.st_dev, current.st_ino) != (opened.st_dev, opened.st_ino)
            ):
                if on_change is not None:
                    on_change(descriptors[-1])
                raise ValueError(f"evidence zone changed during operation: {relative}")
    finally:
        _close_directory_descriptors(descriptors)


@contextmanager
def _bounded_zone(dep: Path, relative: Path, *, create: bool = True):
    dep_root = dep.resolve(strict=True)
    candidate = dep_root.joinpath(*relative.parts)
    with _opened_dep_root(dep) as root_fd:
        with _opened_zone_at(root_fd, relative, create=create) as zone_fd:
            yield candidate, zone_fd


def _bounded_filename(directory: Path, name: str) -> Path:
    if not name or name in {".", ".."} or name.rstrip(" .") != name:
        raise ValueError("evidence filename is unsafe after platform normalization")
    candidate_path = directory / name
    if candidate_path.is_symlink():
        raise ValueError("evidence destination must not be a symlink")
    candidate = candidate_path.resolve()
    if candidate.parent != directory.resolve():
        raise ValueError("evidence destination escapes its collector zone")
    return candidate


def _require_regular_file(path: Path, label: str) -> None:
    if path.is_symlink():
        raise ValueError(f"{label} must not be a symlink")
    try:
        metadata = path.lstat()
    except FileNotFoundError as exc:
        raise FileNotFoundError(path) from exc
    if not stat.S_ISREG(metadata.st_mode):
        raise ValueError(f"{label} must be a regular file")
    if metadata.st_nlink != 1:
        raise ValueError(f"{label} must not be hard-linked")


def _read_regular_bytes(path: Path, label: str, *, max_bytes: int) -> bytes:
    """Read a file while retaining and rechecking its complete parent chain."""
    with _opened_directory_path(path.parent, create=False) as (_, parent_fd):
        raw, _ = _read_regular_bytes_at(
            parent_fd, path.name, label, max_bytes=max_bytes
        )
        return raw


def _read_regular_bytes_at(
    directory_fd: int,
    name: str,
    label: str,
    *,
    max_bytes: int,
) -> tuple[bytes, os.stat_result]:
    """Read one direct child through a retained directory descriptor."""
    if not name or Path(name).name != name:
        raise ValueError(f"{label} has an invalid filename")
    flags = (
        os.O_RDONLY
        | getattr(os, "O_NONBLOCK", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        descriptor = os.open(name, flags, dir_fd=directory_fd)
    except FileNotFoundError:
        raise
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise ValueError(f"{label} must not be a symlink") from exc
        raise ValueError(f"{label} cannot be opened safely: {exc}") from exc
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError(f"{label} must be a regular file")
        if metadata.st_nlink != 1:
            raise ValueError(f"{label} must not be hard-linked")
        if metadata.st_size > max_bytes:
            raise ValueError(
                f"{label} exceeds {max_bytes} bytes; collect a bounded excerpt or summary"
            )
        chunks: list[bytes] = []
        observed_size = 0
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            observed_size += len(chunk)
            if observed_size > max_bytes:
                raise ValueError(
                    f"{label} exceeds {max_bytes} bytes; collect a bounded excerpt or summary"
                )
            chunks.append(chunk)
        final_descriptor = os.fstat(descriptor)
        try:
            final_name = os.stat(
                name, dir_fd=directory_fd, follow_symlinks=False
            )
        except OSError as exc:
            raise ValueError(f"{label} changed during read") from exc
        expected = (
            metadata.st_dev,
            metadata.st_ino,
            metadata.st_size,
            metadata.st_mtime_ns,
            metadata.st_ctime_ns,
            metadata.st_nlink,
        )
        if (
            (
                final_descriptor.st_dev,
                final_descriptor.st_ino,
                final_descriptor.st_size,
                final_descriptor.st_mtime_ns,
                final_descriptor.st_ctime_ns,
                final_descriptor.st_nlink,
            )
            != expected
            or (
                final_name.st_dev,
                final_name.st_ino,
                final_name.st_size,
                final_name.st_mtime_ns,
                final_name.st_ctime_ns,
                final_name.st_nlink,
            )
            != expected
            or not stat.S_ISREG(final_name.st_mode)
        ):
            raise ValueError(f"{label} changed during read")
        return b"".join(chunks), final_descriptor
    finally:
        os.close(descriptor)


def _require_regular_snapshot_at(
    directory_fd: int,
    name: str,
    identity: tuple[int, int],
    size: int,
    digest: str,
    label: str,
    *,
    max_bytes: int,
) -> None:
    """Require a public single-linked file to match one complete snapshot."""
    raw, metadata = _read_regular_bytes_at(
        directory_fd,
        name,
        label,
        max_bytes=max_bytes,
    )
    if (
        (metadata.st_dev, metadata.st_ino) != identity
        or metadata.st_size != size
        or len(raw) != size
        or hashlib.sha256(raw).hexdigest() != digest
    ):
        raise ValueError(f"{label} changed before transaction commit: {name}")


def _load_at(directory_fd: int, name: str) -> dict:
    raw, _ = _read_regular_bytes_at(
        directory_fd,
        name,
        f"machine-readable document {name}",
        max_bytes=MAX_DEP_CONTROL_FILE_BYTES,
    )
    return json.loads(raw.decode("utf-8"))


def _control_snapshot_digest(control_bytes: dict[str, bytes]) -> str:
    """Bind an attachment to the exact summary and manifest bytes it verified."""
    digest = hashlib.sha256(b"SDDGOV-DEP-CONTROL-SNAPSHOT-v1\0")
    for name in ("summary.yaml", "manifest.json"):
        document = control_bytes[name]
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(len(document).to_bytes(8, "big"))
        digest.update(document)
    return digest.hexdigest()


def _capture_artifact_snapshot(
    dep_fd: int, manifest: dict
) -> dict[str, tuple[int, int, int, int, str]]:
    snapshot: dict[str, tuple[int, int, int, int, str]] = {}
    for kind, zone in (("raw", "private/raw"), ("shareable", "shareable/artifacts")):
        rows = manifest.get(kind, [])
        if not isinstance(rows, list):
            raise ValueError(f"manifest {kind} must be an array")
        with _opened_zone_at(dep_fd, Path(zone), create=False) as zone_fd:
            for row in rows:
                if not isinstance(row, dict):
                    raise ValueError(f"manifest {kind} row is invalid")
                path = row.get("path")
                name = Path(str(path)).name
                raw, metadata = _read_regular_bytes_at(
                    zone_fd,
                    name,
                    f"verified artifact {path}",
                    max_bytes=MAX_DEP_ARTIFACT_BYTES,
                )
                digest = hashlib.sha256(raw).hexdigest()
                if len(raw) != row.get("size") or digest != row.get("sha256"):
                    raise ValueError(f"verified artifact changed: {path}")
                snapshot[str(path)] = (
                    metadata.st_dev,
                    metadata.st_ino,
                    metadata.st_size,
                    metadata.st_mtime_ns,
                    digest,
                )
    return snapshot


def _require_artifact_snapshot(
    dep_fd: int, snapshot: dict[str, tuple[int, int, int, int, str]]
) -> None:
    grouped: dict[str, list[tuple[str, tuple[int, int, int, int, str]]]] = {
        "private/raw": [],
        "shareable/artifacts": [],
    }
    for path, identity in snapshot.items():
        zone = str(PurePosixPath(path).parent)
        if zone not in grouped:
            raise ValueError(f"verified artifact path is unsafe: {path}")
        grouped[zone].append((path, identity))
    for zone, rows in grouped.items():
        with _opened_zone_at(dep_fd, Path(zone), create=False) as zone_fd:
            for path, identity in rows:
                try:
                    raw, metadata = _read_regular_bytes_at(
                        zone_fd,
                        PurePosixPath(path).name,
                        f"verified artifact {path}",
                        max_bytes=MAX_DEP_ARTIFACT_BYTES,
                    )
                except (OSError, ValueError) as exc:
                    raise ValueError(f"verified artifact changed: {path}") from exc
                observed = (
                    metadata.st_dev,
                    metadata.st_ino,
                    metadata.st_size,
                    metadata.st_mtime_ns,
                    hashlib.sha256(raw).hexdigest(),
                )
                if observed != identity:
                    raise ValueError(f"verified artifact changed: {path}")


def _remove_owned_at(
    directory_fd: int,
    name: str,
    expected_identity: tuple[int, int],
    label: str,
    *,
    expected_size: int | None = None,
    expected_digest: str | None = None,
) -> bool:
    """Compatibility wrapper around the shared owned-generation protocol."""
    return remove_owned_at(
        directory_fd,
        name,
        expected_identity,
        label,
        expected_size=expected_size,
        expected_digest=expected_digest,
    )


def _remove_owned_tree_at(
    directory_fd: int,
    name: str,
    expected_identity: tuple[int, int],
    label: str,
    expected_snapshot: dict[str, tuple[str, int, int, int, int, str]] | None,
) -> None:
    """Claim and remove one operation-owned directory tree without following links."""
    pending = ""
    for _ in range(16):
        candidate = f".sddgov.dep-cleanup-{uuid.uuid4().hex}"
        try:
            exclusive_rename_at(
                directory_fd,
                name,
                directory_fd,
                candidate,
            )
        except FileNotFoundError:
            return
        except FileExistsError:
            continue
        pending = candidate
        break
    if not pending:
        raise ValueError(f"{label} cleanup could not reserve a private generation")

    def restore() -> None:
        try:
            exclusive_rename_at(directory_fd, pending, directory_fd, name)
        except FileExistsError as exc:
            raise ValueError(
                f"{label} changed during cleanup; preserved pending generation {pending}"
            ) from exc

    metadata = os.stat(pending, dir_fd=directory_fd, follow_symlinks=False)
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or (metadata.st_dev, metadata.st_ino) != expected_identity
    ):
        restore()
        return

    flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    tree_fd = os.open(pending, flags, dir_fd=directory_fd)

    def snapshot_tree(active_fd: int, prefix: str = "") -> dict[str, tuple[str, int, int, int, int, str]]:
        snapshot: dict[str, tuple[str, int, int, int, int, str]] = {}
        for child_name in sorted(os.listdir(active_fd)):
            child = os.stat(child_name, dir_fd=active_fd, follow_symlinks=False)
            relative = f"{prefix}/{child_name}" if prefix else child_name
            if stat.S_ISDIR(child.st_mode):
                snapshot[relative] = (
                    "directory",
                    child.st_dev,
                    child.st_ino,
                    child.st_nlink,
                    0,
                    "",
                )
                child_fd = os.open(child_name, flags, dir_fd=active_fd)
                try:
                    snapshot.update(snapshot_tree(child_fd, relative))
                finally:
                    closing_child = child_fd
                    child_fd = -1
                    os.close(closing_child)
                continue
            if not stat.S_ISREG(child.st_mode) or child.st_nlink != 1:
                snapshot[relative] = (
                    "other",
                    child.st_dev,
                    child.st_ino,
                    child.st_nlink,
                    child.st_size,
                    "",
                )
                continue
            raw, observed = _read_regular_bytes_at(
                active_fd,
                child_name,
                f"{label} child",
                max_bytes=MAX_DEP_CONTROL_FILE_BYTES,
            )
            snapshot[relative] = (
                "file",
                observed.st_dev,
                observed.st_ino,
                observed.st_nlink,
                observed.st_size,
                hashlib.sha256(raw).hexdigest(),
            )
        return snapshot

    if expected_snapshot is None or snapshot_tree(tree_fd) != expected_snapshot:
        closing_tree = tree_fd
        tree_fd = -1
        os.close(closing_tree)
        restore()
        raise ValueError(f"{label} changed during cleanup")

    def empty_tree(active_fd: int, prefix: str = "") -> None:
        for child_name in sorted(os.listdir(active_fd)):
            relative = f"{prefix}/{child_name}" if prefix else child_name
            expected = expected_snapshot.get(relative)
            if expected is None:
                raise ValueError(f"{label} received a later child during cleanup")
            child_claim = ""
            for _ in range(16):
                candidate = f".sddgov.dep-child-{uuid.uuid4().hex}"
                try:
                    exclusive_rename_at(
                        active_fd,
                        child_name,
                        active_fd,
                        candidate,
                    )
                except FileNotFoundError as exc:
                    raise ValueError(
                        f"{label} child changed during cleanup: {relative}"
                    ) from exc
                except FileExistsError:
                    continue
                child_claim = candidate
                break
            if not child_claim:
                raise ValueError(
                    f"{label} child cleanup could not reserve a private generation"
                )

            def restore_child() -> None:
                try:
                    exclusive_rename_at(
                        active_fd,
                        child_claim,
                        active_fd,
                        child_name,
                    )
                except FileNotFoundError:
                    return
                except FileExistsError as exc:
                    raise ValueError(
                        f"{label} child changed during cleanup; preserved "
                        f"pending generation {child_claim}"
                    ) from exc

            try:
                child = os.stat(
                    child_claim,
                    dir_fd=active_fd,
                    follow_symlinks=False,
                )
                if expected[0] == "file":
                    raw, observed = _read_regular_bytes_at(
                        active_fd,
                        child_claim,
                        f"{label} child",
                        max_bytes=MAX_DEP_CONTROL_FILE_BYTES,
                    )
                    if (
                        not stat.S_ISREG(child.st_mode)
                        or child.st_nlink != 1
                        or (
                            observed.st_dev,
                            observed.st_ino,
                            observed.st_nlink,
                            observed.st_size,
                            hashlib.sha256(raw).hexdigest(),
                        )
                        != (expected[1], expected[2], expected[3], expected[4], expected[5])
                    ):
                        raise ValueError(
                            f"{label} child changed during cleanup: {relative}"
                        )
                    removed = _remove_owned_at(
                        active_fd,
                        child_claim,
                        (expected[1], expected[2]),
                        f"{label} child",
                        expected_size=expected[4],
                        expected_digest=expected[5],
                    )
                    if not removed:
                        raise ValueError(
                            f"{label} child changed during cleanup: {relative}"
                        )
                    child_claim = ""
                    continue
                if (
                    expected[0] != "directory"
                    or not stat.S_ISDIR(child.st_mode)
                    or (child.st_dev, child.st_ino, child.st_nlink)
                    != (expected[1], expected[2], expected[3])
                ):
                    raise ValueError(
                        f"{label} child changed during cleanup: {relative}"
                    )
                child_fd = os.open(child_claim, flags, dir_fd=active_fd)
                try:
                    empty_tree(child_fd, relative)
                finally:
                    closing_child = child_fd
                    child_fd = -1
                    os.close(closing_child)
                final_child = os.stat(
                    child_claim,
                    dir_fd=active_fd,
                    follow_symlinks=False,
                )
                if (
                    not stat.S_ISDIR(final_child.st_mode)
                    or (final_child.st_dev, final_child.st_ino)
                    != (expected[1], expected[2])
                ):
                    raise ValueError(
                        f"{label} child changed during cleanup: {relative}"
                    )
                os.rmdir(child_claim, dir_fd=active_fd)
                child_claim = ""
            except BaseException as primary:
                if child_claim:
                    try:
                        restore_child()
                    except BaseException as cleanup_error:
                        raise primary from cleanup_error
                raise
        os.fsync(active_fd)

    try:
        empty_tree(tree_fd)
    finally:
        closing_tree = tree_fd
        tree_fd = -1
        os.close(closing_tree)
    os.rmdir(pending, dir_fd=directory_fd)
    os.fsync(directory_fd)


def _tree_snapshot_at(
    directory_fd: int,
) -> dict[str, tuple[str, int, int, int, int, str]]:
    """Capture the exact safe DEP tree generation before outer lease commit."""
    flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    snapshot: dict[str, tuple[str, int, int, int, int, str]] = {}
    for child_name in sorted(os.listdir(directory_fd)):
        child = os.stat(child_name, dir_fd=directory_fd, follow_symlinks=False)
        if stat.S_ISDIR(child.st_mode):
            snapshot[child_name] = (
                "directory",
                child.st_dev,
                child.st_ino,
                child.st_nlink,
                0,
                "",
            )
            child_fd = os.open(child_name, flags, dir_fd=directory_fd)
            try:
                for relative, value in _tree_snapshot_at(child_fd).items():
                    snapshot[f"{child_name}/{relative}"] = value
            finally:
                closing_child = child_fd
                child_fd = -1
                os.close(closing_child)
            continue
        if not stat.S_ISREG(child.st_mode) or child.st_nlink != 1:
            snapshot[child_name] = (
                "other",
                child.st_dev,
                child.st_ino,
                child.st_nlink,
                child.st_size,
                "",
            )
            continue
        raw, observed = _read_regular_bytes_at(
            directory_fd,
            child_name,
            "DEP tree child",
            max_bytes=MAX_DEP_CONTROL_FILE_BYTES,
        )
        snapshot[child_name] = (
            "file",
            observed.st_dev,
            observed.st_ino,
            observed.st_nlink,
            observed.st_size,
            hashlib.sha256(raw).hexdigest(),
        )
    return snapshot


def _write_bytes_at(
    directory_fd: int,
    name: str,
    encoded: bytes,
    label: str,
    published_identity: list[tuple[int, int]] | None = None,
    expected_snapshot: tuple[tuple[int, int, int, int], str] | None = None,
    must_not_exist: bool = False,
    transaction: _MutationTransaction | None = None,
) -> None:
    """Publish one direct child without clobbering a changed expected generation."""
    owned_transaction = transaction is None and expected_snapshot is not None
    if owned_transaction:
        transaction = _MutationTransaction()
    if not name or Path(name).name != name:
        raise ValueError(f"{label} has an invalid filename")
    try:
        current = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        current = None
    if current is not None and stat.S_ISLNK(current.st_mode):
        raise ValueError(f"{label} must not be a symlink: {name}")
    if current is not None and (
        not stat.S_ISREG(current.st_mode) or current.st_nlink != 1
    ):
        raise ValueError(
            f"{label} must be a single-linked regular file: {name}"
        )
    if must_not_exist and current is not None:
        raise FileExistsError(f"{label} already exists: {name}")
    if expected_snapshot is not None:
        if current is None:
            raise ValueError(f"{label} changed before publication: {name}")
        observed_raw, observed_metadata = _read_regular_bytes_at(
            directory_fd,
            name,
            label,
            max_bytes=MAX_DEP_CONTROL_FILE_BYTES,
        )
        observed_identity = (
            observed_metadata.st_dev,
            observed_metadata.st_ino,
            observed_metadata.st_size,
            observed_metadata.st_mtime_ns,
        )
        if (
            observed_identity != expected_snapshot[0]
            or hashlib.sha256(observed_raw).hexdigest() != expected_snapshot[1]
        ):
            raise ValueError(f"{label} changed before publication: {name}")
    temporary = f".sddgov.control-stage-{uuid.uuid4().hex}"
    staged_claim = f".sddgov.control-new-{uuid.uuid4().hex}"
    old_claim = f".sddgov.control-old-{uuid.uuid4().hex}"
    descriptor = -1
    staging_guard = -1
    staged_identity: tuple[int, int] | None = None
    staged_verified = False
    old_identity: tuple[int, int] | None = None
    old_claim_exists = False
    published = False
    committed = False
    encoded_digest = hashlib.sha256(encoded).hexdigest()

    def require_exact(
        candidate: str,
        identity: tuple[int, int],
        size: int,
        digest: str,
        candidate_label: str,
    ) -> os.stat_result:
        raw, metadata = _read_regular_bytes_at(
            directory_fd,
            candidate,
            candidate_label,
            max_bytes=max(size, 0),
        )
        if (
            (metadata.st_dev, metadata.st_ino) != identity
            or metadata.st_size != size
            or hashlib.sha256(raw).hexdigest() != digest
        ):
            raise ValueError(f"{label} changed before publication: {name}")
        return metadata

    def restore_old_claim(active_directory_fd: int = directory_fd) -> None:
        nonlocal old_claim_exists
        if not old_claim_exists:
            return
        if old_identity is None or expected_snapshot is None:
            raise ValueError(f"{label} predecessor claim is incomplete")

        def discard_old_claim() -> None:
            nonlocal old_claim_exists
            removed = _remove_owned_at(
                active_directory_fd,
                old_claim,
                old_identity,
                label,
                expected_size=expected_snapshot[0][2],
                expected_digest=expected_snapshot[1],
            )
            if not removed:
                raise ValueError(f"{label} predecessor claim changed during cleanup")
            old_claim_exists = False

        _require_regular_snapshot_at(
            active_directory_fd,
            old_claim,
            old_identity,
            expected_snapshot[0][2],
            expected_snapshot[1],
            f"{label} predecessor claim",
            max_bytes=MAX_DEP_CONTROL_FILE_BYTES,
        )
        try:
            os.link(
                old_claim,
                name,
                src_dir_fd=active_directory_fd,
                dst_dir_fd=active_directory_fd,
                follow_symlinks=False,
            )
        except FileExistsError:
            discard_old_claim()
            return
        discard_old_claim()
        _require_regular_snapshot_at(
            active_directory_fd,
            name,
            old_identity,
            expected_snapshot[0][2],
            expected_snapshot[1],
            label,
            max_bytes=MAX_DEP_CONTROL_FILE_BYTES,
        )

    try:
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=directory_fd,
        )
        opened = os.fstat(descriptor)
        staged_identity = (opened.st_dev, opened.st_ino)
        if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1:
            raise ValueError(f"{label} staging file is unsafe: {name}")
        view = memoryview(encoded)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError(f"{label} staging write made no progress")
            view = view[written:]
        os.fsync(descriptor)
        final_fd = os.fstat(descriptor)
        final_path = os.stat(
            temporary,
            dir_fd=directory_fd,
            follow_symlinks=False,
        )
        if (
            not stat.S_ISREG(final_path.st_mode)
            or final_path.st_nlink != 1
            or (final_fd.st_dev, final_fd.st_ino) != staged_identity
            or (final_path.st_dev, final_path.st_ino) != staged_identity
            or final_fd.st_size != len(encoded)
        ):
            raise ValueError(f"{label} staging file changed during write: {name}")
        closing_descriptor = descriptor
        staging_guard = os.dup(descriptor)
        descriptor = -1
        os.close(closing_descriptor)
        os.fsync(directory_fd)

        os.link(
            temporary,
            staged_claim,
            src_dir_fd=directory_fd,
            dst_dir_fd=directory_fd,
            follow_symlinks=False,
        )
        closing_guard = staging_guard
        staging_guard = -1
        try:
            os.close(closing_guard)
        except OSError:
            pass
        removed_temporary = _remove_owned_at(
            directory_fd,
            temporary,
            staged_identity,
            f"{label} staging file",
            expected_size=len(encoded),
            expected_digest=encoded_digest,
        )
        if not removed_temporary:
            raise ValueError(f"{label} staging file changed before cleanup: {name}")
        temporary = ""
        require_exact(
            staged_claim,
            staged_identity,
            len(encoded),
            encoded_digest,
            f"{label} claimed staging file",
        )
        staged_verified = True

        if expected_snapshot is not None:
            expected_file_identity = expected_snapshot[0][:2]
            os.link(
                name,
                old_claim,
                src_dir_fd=directory_fd,
                dst_dir_fd=directory_fd,
                follow_symlinks=False,
            )
            old_claim_exists = True
            _remove_owned_at(
                directory_fd,
                name,
                expected_file_identity,
                label,
                expected_size=expected_snapshot[0][2],
                expected_digest=expected_snapshot[1],
            )
            old_raw, old_metadata = _read_regular_bytes_at(
                directory_fd,
                old_claim,
                label,
                max_bytes=MAX_DEP_CONTROL_FILE_BYTES,
            )
            old_identity = (old_metadata.st_dev, old_metadata.st_ino)
            observed_old = (
                old_metadata.st_dev,
                old_metadata.st_ino,
                old_metadata.st_size,
                old_metadata.st_mtime_ns,
            )
            if (
                observed_old != expected_snapshot[0]
                or hashlib.sha256(old_raw).hexdigest() != expected_snapshot[1]
            ):
                restore_old_claim()
                raise ValueError(f"{label} changed before publication: {name}")

        try:
            os.link(
                staged_claim,
                name,
                src_dir_fd=directory_fd,
                dst_dir_fd=directory_fd,
                follow_symlinks=False,
            )
        except FileExistsError as exc:
            if expected_snapshot is not None:
                raise ValueError(
                    f"{label} received a later writer before publication: {name}"
                ) from exc
            if must_not_exist:
                raise FileExistsError(f"{label} already exists: {name}") from exc
            raise FileExistsError(f"{label} received an unexpected writer: {name}") from exc
        published = True
        removed_claim = _remove_owned_at(
            directory_fd,
            staged_claim,
            staged_identity,
            f"{label} claimed staging file",
            expected_size=len(encoded),
            expected_digest=encoded_digest,
        )
        if not removed_claim:
            raise ValueError(f"{label} staging claim changed before cleanup: {name}")
        staged_claim = ""
        published_metadata = require_exact(
            name,
            staged_identity,
            len(encoded),
            encoded_digest,
            label,
        )
        os.fsync(directory_fd)
        published_metadata = require_exact(
            name,
            staged_identity,
            len(encoded),
            encoded_digest,
            label,
        )
        if published_identity is not None:
            published_identity.append(
                (published_metadata.st_dev, published_metadata.st_ino)
            )
        new_identity = (published_metadata.st_dev, published_metadata.st_ino)
        if transaction is not None:
            transaction_fd = transaction.retain_directory(directory_fd)

            def rollback_publication() -> None:
                _remove_owned_at(
                    transaction_fd,
                    name,
                    new_identity,
                    label,
                    expected_size=len(encoded),
                    expected_digest=encoded_digest,
                )
                if expected_snapshot is not None:
                    restore_old_claim(transaction_fd)

            def verify_publication() -> None:
                _require_regular_snapshot_at(
                    transaction_fd,
                    name,
                    new_identity,
                    len(encoded),
                    encoded_digest,
                    label,
                    max_bytes=MAX_DEP_CONTROL_FILE_BYTES,
                )

            def finalize_predecessor() -> None:
                nonlocal old_claim_exists
                if old_claim_exists and old_identity is not None:
                    try:
                        removed = _remove_owned_at(
                            transaction_fd,
                            old_claim,
                            old_identity,
                            label,
                            expected_size=expected_snapshot[0][2],
                            expected_digest=expected_snapshot[1],
                        )
                    except BaseException:
                        try:
                            os.stat(
                                old_claim,
                                dir_fd=transaction_fd,
                                follow_symlinks=False,
                            )
                        except FileNotFoundError:
                            # The unlink linearized before its durability report
                            # failed. The new public generation must stay committed;
                            # rolling it back now would lose the predecessor too.
                            old_claim_exists = False
                            return
                        raise
                    if not removed:
                        raise ValueError(
                            f"{label} predecessor claim changed before finalization"
                        )
                    old_claim_exists = False

            transaction.add(
                rollback_publication,
                finalize_predecessor if expected_snapshot is not None else None,
                verify_publication,
            )
            if owned_transaction:
                transaction.finalize()
        committed = True
    except BaseException as primary:
        cleanup_error: BaseException | None = None
        if descriptor >= 0:
            closing_descriptor = descriptor
            descriptor = -1
            try:
                os.close(closing_descriptor)
            except BaseException as exc:
                cleanup_error = exc
        if published and not committed and staged_identity is not None:
            try:
                _remove_owned_at(
                    directory_fd,
                    name,
                    staged_identity,
                    label,
                    expected_size=len(encoded),
                    expected_digest=encoded_digest,
                )
            except BaseException as exc:
                if cleanup_error is None:
                    cleanup_error = exc
        if expected_snapshot is not None:
            try:
                restore_old_claim()
            except BaseException as exc:
                if cleanup_error is None:
                    cleanup_error = exc
        if staging_guard >= 0:
            closing_guard = staging_guard
            staging_guard = -1
            try:
                os.close(closing_guard)
            except OSError:
                pass
        if staged_identity is not None and temporary:
            try:
                removed = _remove_owned_at(
                    directory_fd,
                    temporary,
                    staged_identity,
                    f"{label} staging file",
                    expected_size=len(encoded) if staged_verified else None,
                    expected_digest=encoded_digest if staged_verified else None,
                )
                if not removed:
                    raise ValueError(f"{label} staging file changed during cleanup")
                temporary = ""
            except BaseException as exc:
                if cleanup_error is None:
                    cleanup_error = exc
        if staged_identity is not None and staged_claim:
            try:
                removed = _remove_owned_at(
                    directory_fd,
                    staged_claim,
                    staged_identity,
                    f"{label} staging claim",
                    expected_size=len(encoded) if staged_verified else None,
                    expected_digest=encoded_digest if staged_verified else None,
                )
                if not removed:
                    raise ValueError(f"{label} staging claim changed during cleanup")
                staged_claim = ""
            except BaseException as exc:
                if cleanup_error is None:
                    cleanup_error = exc
        if cleanup_error is not None:
            raise primary from cleanup_error
        raise
    finally:
        if staged_identity is not None and temporary:
            try:
                _remove_owned_at(
                    directory_fd,
                    temporary,
                    staged_identity,
                    f"{label} staging file",
                    expected_size=len(encoded),
                    expected_digest=encoded_digest,
                )
            except (OSError, ValueError):
                pass
        if staged_identity is not None and staged_claim:
            try:
                _remove_owned_at(
                    directory_fd,
                    staged_claim,
                    staged_identity,
                    f"{label} claimed staging file",
                    expected_size=len(encoded),
                    expected_digest=encoded_digest,
                )
            except (OSError, ValueError):
                pass


def _save_at(
    directory_fd: int,
    name: str,
    data: dict,
    published_identity: list[tuple[int, int]] | None = None,
    expected_snapshot: tuple[tuple[int, int, int, int], str] | None = None,
    must_not_exist: bool = False,
    transaction: _MutationTransaction | None = None,
) -> None:
    """Atomically replace one control document through its retained DEP fd."""
    encoded = (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    _write_bytes_at(
        directory_fd,
        name,
        encoded,
        "machine-readable destination",
        published_identity,
        expected_snapshot,
        must_not_exist,
        transaction,
    )


def _stage_attachment_at(
    output_fd: int,
    name: str,
    encoded: bytes,
) -> tuple[str, tuple[int, int], int, str, int]:
    """Stage attachment bytes without mutating the destination directory entry."""
    if not name or Path(name).name != name:
        raise ValueError("attachment output has an invalid filename")
    try:
        current = os.stat(name, dir_fd=output_fd, follow_symlinks=False)
    except FileNotFoundError:
        current = None
    if current is not None and (
        stat.S_ISLNK(current.st_mode)
        or not stat.S_ISREG(current.st_mode)
        or current.st_nlink != 1
    ):
        raise ValueError(
            f"attachment output must be a single-linked regular file: {name}"
        )
    if current is not None:
        raise FileExistsError(f"attachment output already exists: {name}")
    temporary = f".sddgov.attachment-stage-{uuid.uuid4().hex}"
    descriptor = -1
    staging_guard = -1
    identity: tuple[int, int] | None = None
    try:
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=output_fd,
        )
        opened = os.fstat(descriptor)
        identity = (opened.st_dev, opened.st_ino)
        if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1:
            raise ValueError("attachment staging file is not a single-linked regular file")
        view = memoryview(encoded)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError("attachment staging write made no progress")
            view = view[written:]
        os.fsync(descriptor)
        final_fd = os.fstat(descriptor)
        final_path = os.stat(temporary, dir_fd=output_fd, follow_symlinks=False)
        if (
            not stat.S_ISREG(final_path.st_mode)
            or final_path.st_nlink != 1
            or (final_fd.st_dev, final_fd.st_ino) != identity
            or (final_path.st_dev, final_path.st_ino) != identity
            or final_fd.st_size != len(encoded)
        ):
            raise ValueError("attachment staging file changed during write")
        closing_descriptor = descriptor
        staging_guard = os.dup(descriptor)
        descriptor = -1
        os.close(closing_descriptor)
        os.fsync(output_fd)
    except BaseException as primary:
        cleanup_error: BaseException | None = None
        if descriptor >= 0:
            closing_descriptor = descriptor
            descriptor = -1
            try:
                os.close(closing_descriptor)
            except BaseException as exc:
                cleanup_error = exc
        if identity is not None:
            try:
                _remove_owned_at(
                    output_fd,
                    temporary,
                    identity,
                    "attachment staging file",
                )
            except BaseException as exc:
                if cleanup_error is None:
                    cleanup_error = exc
        if staging_guard >= 0:
            closing_guard = staging_guard
            staging_guard = -1
            try:
                os.close(closing_guard)
            except OSError:
                pass
        if cleanup_error is not None:
            raise primary from cleanup_error
        raise
    if identity is None:  # pragma: no cover - guarded by the successful open/fstat
        raise RuntimeError("attachment staging identity was not captured")
    return (
        temporary,
        identity,
        len(encoded),
        hashlib.sha256(encoded).hexdigest(),
        staging_guard,
    )


def _publish_verified_attachment_at(
    dep_fd: int,
    output_fd: int,
    name: str,
    encoded: bytes,
    control_identities: dict[str, tuple[int, int, int, int]],
    control_snapshot_digest: str,
    artifact_identities: dict[str, tuple[int, int, int, int, str]],
) -> tuple[int, int]:
    """Stage, recheck controls, then publish without clobbering another writer."""
    (
        temporary,
        staged_identity,
        staged_size,
        staged_digest,
        staging_guard,
    ) = _stage_attachment_at(output_fd, name, encoded)
    claimed = f".sddgov.attachment-claim-{uuid.uuid4().hex}"
    claim_verified = False
    published = False
    try:
        # Hard-link first to atomically claim the current staging generation.
        # A same-UID writer may replace the public staging pathname at any
        # instant; the private claim remains pinned to exactly what was linked.
        os.link(
            temporary,
            claimed,
            src_dir_fd=output_fd,
            dst_dir_fd=output_fd,
            follow_symlinks=False,
        )
        closing_guard = staging_guard
        staging_guard = -1
        try:
            os.close(closing_guard)
        except OSError:
            pass
        _remove_owned_at(
            output_fd,
            temporary,
            staged_identity,
            "attachment staging file",
        )
        def require_exact_attachment(candidate: str, label: str) -> None:
            raw, metadata = _read_regular_bytes_at(
                output_fd,
                candidate,
                label,
                max_bytes=staged_size,
            )
            if (
                (metadata.st_dev, metadata.st_ino) != staged_identity
                or metadata.st_size != staged_size
                or hashlib.sha256(raw).hexdigest() != staged_digest
            ):
                raise ValueError("attachment staging file changed before publication")

        require_exact_attachment(claimed, "claimed attachment staging file")
        claim_verified = True
        _require_control_snapshot(
            dep_fd, control_identities, control_snapshot_digest
        )
        _require_artifact_snapshot(dep_fd, artifact_identities)
        os.link(
            claimed,
            name,
            src_dir_fd=output_fd,
            dst_dir_fd=output_fd,
            follow_symlinks=False,
        )
        published = True
        _require_control_snapshot(
            dep_fd, control_identities, control_snapshot_digest
        )
        _require_artifact_snapshot(dep_fd, artifact_identities)
        _remove_owned_at(
            output_fd,
            claimed,
            staged_identity,
            "claimed attachment staging file",
        )
        claimed = ""
        require_exact_attachment(name, "published attachment output")
        _require_control_snapshot(
            dep_fd, control_identities, control_snapshot_digest
        )
        _require_artifact_snapshot(dep_fd, artifact_identities)
        require_exact_attachment(name, "published attachment output")
        os.fsync(output_fd)
        return staged_identity
    except BaseException:
        if published:
            _remove_owned_at(
                output_fd,
                name,
                    staged_identity,
                    "attachment output",
                    expected_size=staged_size,
                    expected_digest=staged_digest,
                )
        raise
    finally:
        if staging_guard >= 0:
            try:
                os.close(staging_guard)
            except OSError:
                pass
        if claimed:
            try:
                _remove_owned_at(
                    output_fd,
                    claimed,
                    staged_identity,
                    "claimed attachment staging file",
                    expected_size=staged_size,
                    expected_digest=staged_digest,
                )
            except (OSError, ValueError):
                pass
        if temporary:
            try:
                _remove_owned_at(
                    output_fd,
                    temporary,
                    staged_identity,
                    "attachment staging file",
                    expected_size=staged_size,
                    expected_digest=staged_digest,
                )
            except (OSError, ValueError):
                pass


def _artifact_media_type(suffix: str, raw: bytes) -> str:
    normalized = suffix.lower()
    if normalized == ".har":
        return "application/har+json"
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        parsed = None
    if (
        isinstance(parsed, dict)
        and isinstance(parsed.get("log"), dict)
        and isinstance(parsed["log"].get("entries"), list)
    ):
        return "application/har+json"
    if normalized == ".json" and parsed is not None:
        return "application/json"
    if normalized in TEXT_SUFFIXES:
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError:
            return "application/octet-stream"
        return "text/plain; charset=utf-8"
    return "application/octet-stream"


def _manifest_artifact_path(dep: Path, value: object, zone: str) -> Path:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError(f"artifact path is invalid for {zone}")
    pure = PurePosixPath(value)
    if (
        pure.is_absolute()
        or str(pure) != value
        or any(part in {"", ".", ".."} for part in pure.parts)
        or tuple(pure.parts[: len(PurePosixPath(zone).parts)])
        != PurePosixPath(zone).parts
        or pure.parent != PurePosixPath(zone)
    ):
        raise ValueError(f"artifact path escapes or is not normalized for {zone}: {value}")
    candidate = dep.joinpath(*pure.parts)
    current = dep
    for part in pure.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"artifact path contains a symlink: {value}")
    try:
        candidate.absolute().relative_to(dep.absolute())
    except ValueError as exc:
        raise ValueError(f"artifact path escapes DEP root: {value}") from exc
    return candidate


def _actual_zone_files_at(directory_fd: int, zone: str) -> tuple[set[str], list[str]]:
    actual: set[str] = set()
    errors: list[str] = []
    for name in os.listdir(directory_fd):
        relative = f"{zone}/{name}"
        if not name or Path(name).name != name:
            errors.append(f"artifact filename is not normalized: {relative}")
            continue
        try:
            metadata = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        except OSError as exc:
            errors.append(f"artifact cannot be inspected safely: {relative}: {exc}")
            continue
        if stat.S_ISLNK(metadata.st_mode):
            errors.append(f"artifact path contains a symlink: {relative}")
        elif not stat.S_ISREG(metadata.st_mode):
            errors.append(f"artifact path is not a regular file: {relative}")
        elif metadata.st_nlink != 1:
            errors.append(f"artifact path must not be hard-linked: {relative}")
        else:
            actual.add(relative)
    return actual, errors


def make_dep(base: Path, issue: str, risk: str, sdd_ref: str | None = None, dep_id: str | None = None) -> Path:
    if risk not in {"L0", "L1", "L2", "L3"}:
        raise ValueError("risk must be L0, L1, L2, or L3")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    safe_issue = "".join(c if c.isalnum() or c in "-_" else "-" for c in issue).strip("-") or "untracked"
    dep_id = dep_id or f"DEP-{stamp}-{safe_issue}"
    if not DEP_ID_PATTERN.fullmatch(dep_id):
        raise ValueError("DEP ID must match DEP-[A-Za-z0-9._-]+ and cannot contain a path")
    summary = {
        "$schema": "../../schemas/debug-evidence-package.schema.json",
        "schema_version": "1.0",
        "dep_id": dep_id,
        "issue": issue,
        "sdd_references": [sdd_ref] if sdd_ref else [],
        "risk_level": risk,
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "workflow": {"phase": "red", "history": [{"phase": "red", "at": utc_now()}]},
        "expected_behavior": "TODO",
        "actual_behavior": "TODO",
        "environment": {"commit": "TODO", "branch": "TODO", "runtime": "TODO"},
        "root_cause_status": "unknown",
        "attachments": [],
    }
    transaction = _MutationTransaction()
    with _opened_directory_path(
        base,
        create=True,
        on_change=transaction.rollback,
        on_commit=transaction.finalize,
    ) as (safe_base, base_fd):
        try:
            os.stat(dep_id, dir_fd=base_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise FileExistsError(f"DEP already exists: {safe_base / dep_id}")
        staging_name = f".sddgov.dep-stage-{uuid.uuid4().hex}"
        os.mkdir(staging_name, 0o700, dir_fd=base_fd)
        directory_flags = (
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        dep_fd = os.open(staging_name, directory_flags, dir_fd=base_fd)
        dep_metadata = os.fstat(dep_fd)
        dep_identity = (dep_metadata.st_dev, dep_metadata.st_ino)
        dep_snapshot: dict[str, tuple[str, int, int, int, int, str]] | None = None
        published = False
        try:
            with _opened_zone_at(dep_fd, Path("private/raw"), create=True) as raw_fd:
                with _opened_zone_at(
                    dep_fd, Path("shareable/artifacts"), create=True
                ):
                    os.fchmod(raw_fd, 0o700)
                    for item in _resource_dir().iterdir():
                        if item.name == "summary.yaml":
                            continue
                        _write_bytes_at(
                            dep_fd,
                            item.name,
                            item.read_bytes(),
                            "DEP template destination",
                        )
                    _save_at(dep_fd, "summary.yaml", summary)
                    _save_at(
                        dep_fd,
                        "manifest.json",
                        {
                            "schema_version": MANIFEST_SCHEMA_VERSION,
                            "dep_id": dep_id,
                            "raw": [],
                            "shareable": [],
                        },
                    )
                    dep_snapshot = _tree_snapshot_at(dep_fd)
                    os.fsync(dep_fd)

            transaction_base_fd = transaction.retain_directory(base_fd)
            transaction_dep_fd = transaction.retain_directory(dep_fd)
            exclusive_rename_at(
                base_fd,
                staging_name,
                base_fd,
                dep_id,
            )
            published = True

            def rollback_dep_tree() -> None:
                _remove_owned_tree_at(
                    transaction_base_fd,
                    dep_id,
                    dep_identity,
                    "DEP directory",
                    dep_snapshot,
                )

            def verify_dep_tree() -> None:
                public = os.stat(
                    dep_id,
                    dir_fd=transaction_base_fd,
                    follow_symlinks=False,
                )
                if (
                    not stat.S_ISDIR(public.st_mode)
                    or (public.st_dev, public.st_ino) != dep_identity
                    or dep_snapshot is None
                    or _tree_snapshot_at(transaction_dep_fd) != dep_snapshot
                ):
                    raise ValueError("DEP directory changed before transaction commit")

            transaction.add(
                rollback_dep_tree,
                verify=verify_dep_tree,
            )
            os.fsync(base_fd)
        except BaseException as primary:
            if not published:
                cleanup_error: BaseException | None = None
                try:
                    current_snapshot = _tree_snapshot_at(dep_fd)
                    _remove_owned_tree_at(
                        base_fd,
                        staging_name,
                        dep_identity,
                        "DEP staging directory",
                        current_snapshot,
                    )
                except BaseException as exc:
                    cleanup_error = exc
                if cleanup_error is not None:
                    raise primary from cleanup_error
            raise
        finally:
            closing_dep = dep_fd
            dep_fd = -1
            try:
                os.close(closing_dep)
            except OSError:
                # The transaction-owned duplicate retains the published tree.
                # A close error is not safely retryable and cannot reverse commit.
                pass
        return safe_base / dep_id


def collect(dep: Path, collector: str, input_path: Path, label: str | None = None) -> Path:
    if collector not in COLLECTORS:
        raise ValueError(f"unsupported collector: {collector}")
    transaction = _MutationTransaction()
    with _opened_dep_root(
        dep,
        on_change=transaction.rollback,
        on_commit=transaction.finalize,
    ) as dep_fd:
        try:
            _read_regular_bytes_at(
                dep_fd,
                "redaction-report.json",
                "machine-readable document redaction-report.json",
                max_bytes=MAX_DEP_CONTROL_FILE_BYTES,
            )
        except FileNotFoundError:
            pass
        else:
            raise ValueError(
                "Evidence collection is closed after redaction; create a new DEP"
            )
        manifest_raw, manifest_metadata = _read_regular_bytes_at(
            dep_fd,
            "manifest.json",
            "machine-readable document manifest.json",
            max_bytes=MAX_DEP_CONTROL_FILE_BYTES,
        )
        manifest = json.loads(manifest_raw.decode("utf-8"))
        if manifest.get("shareable"):
            raise ValueError(
                "Evidence collection is closed after shareable artifacts exist"
            )
        manifest_snapshot = (
            (
                manifest_metadata.st_dev,
                manifest_metadata.st_ino,
                manifest_metadata.st_size,
                manifest_metadata.st_mtime_ns,
            ),
            hashlib.sha256(manifest_raw).hexdigest(),
        )
        raw = _read_regular_bytes(
            input_path,
            "collector input",
            max_bytes=MAX_REDACTION_FILE_BYTES,
        )
        ordinal = len(manifest.get("raw", [])) + 1
        source_suffix = input_path.suffix.lower()
        default_label = f"artifact-{ordinal}{source_suffix}"
        requested_label = label or default_label
        if requested_label.rstrip(" .") != requested_label:
            raise ValueError("evidence filename is unsafe after platform normalization")
        safe_label = "".join(
            c if c.isalnum() or c in "-_." else "-" for c in requested_label
        )
        label_suffix = Path(safe_label).suffix.lower()
        if label_suffix and label_suffix != source_suffix:
            raise ValueError("evidence label suffix must match the collector input type")
        if not label_suffix:
            safe_label += source_suffix
        filename = f"{collector}--{safe_label}"
        raw_dir = dep.resolve(strict=True) / "private" / "raw"
        raw_digest = hashlib.sha256(raw).hexdigest()
        written_identity: tuple[int, int] | None = None
        cleanup_fd: int | None = None

        def cleanup_owned_raw(directory_fd: int) -> None:
            if written_identity is None:
                return
            _remove_owned_at(
                directory_fd,
                filename,
                written_identity,
                "collector raw artifact",
                expected_size=len(raw),
                expected_digest=raw_digest,
            )

        try:
            with _opened_zone_at(
                dep_fd,
                Path("private/raw"),
                create=False,
                on_change=cleanup_owned_raw,
            ) as raw_dir_fd:
                cleanup_fd = os.dup(raw_dir_fd)
                os.fchmod(raw_dir_fd, 0o700)
                destination = _bounded_filename(raw_dir, filename)
                flags = (
                    os.O_WRONLY
                    | os.O_CREAT
                    | os.O_EXCL
                    | getattr(os, "O_NOFOLLOW", 0)
                )
                descriptor = -1
                try:
                    descriptor = os.open(filename, flags, 0o600, dir_fd=raw_dir_fd)
                except FileExistsError as exc:
                    raise FileExistsError(
                        f"Evidence artifact already exists: {filename}"
                    ) from exc
                try:
                    view = memoryview(raw)
                    while view:
                        written = os.write(descriptor, view)
                        view = view[written:]
                    os.fsync(descriptor)
                    written_metadata = os.fstat(descriptor)
                    written_identity = (
                        written_metadata.st_dev,
                        written_metadata.st_ino,
                    )
                except BaseException as primary:
                    closing_descriptor = descriptor
                    descriptor = -1
                    try:
                        os.close(closing_descriptor)
                    except BaseException as cleanup_error:
                        raise primary from cleanup_error
                    raise
                closing_descriptor = descriptor
                descriptor = -1
                os.close(closing_descriptor)
                os.fsync(raw_dir_fd)
                if written_identity is not None:
                    transaction_raw_fd = transaction.retain_directory(raw_dir_fd)

                    def rollback_raw_artifact() -> None:
                        cleanup_owned_raw(transaction_raw_fd)

                    def verify_raw_artifact() -> None:
                        _require_regular_snapshot_at(
                            transaction_raw_fd,
                            filename,
                            written_identity,
                            len(raw),
                            raw_digest,
                            "collector raw artifact",
                            max_bytes=MAX_REDACTION_FILE_BYTES,
                        )

                    transaction.add(
                        rollback_raw_artifact,
                        verify=verify_raw_artifact,
                    )
            digest = raw_digest
            manifest["raw"].append({
                "collector": collector,
                "path": f"private/raw/{filename}",
                "source_suffix": source_suffix,
                "media_type": _artifact_media_type(source_suffix, raw),
                "sha256": digest,
                "size": len(raw),
                "collected_at": utc_now(),
                "shareable": False,
            })
            manifest_publication: list[tuple[int, int]] = []
            _save_at(
                dep_fd,
                "manifest.json",
                manifest,
                manifest_publication,
                manifest_snapshot,
                transaction=transaction,
            )
        except BaseException:
            if cleanup_fd is not None:
                cleanup_owned_raw(cleanup_fd)
            raise
        finally:
            if cleanup_fd is not None:
                try:
                    os.close(cleanup_fd)
                except OSError:
                    pass
        return destination


def redact(dep: Path) -> dict:
    transaction = _MutationTransaction()
    with _opened_dep_root(
        dep,
        on_change=transaction.rollback,
        on_commit=transaction.finalize,
    ) as dep_fd:
        manifest_before, manifest_metadata = _read_regular_bytes_at(
            dep_fd,
            "manifest.json",
            "machine-readable document manifest.json",
            max_bytes=MAX_DEP_CONTROL_FILE_BYTES,
        )
        try:
            _read_regular_bytes_at(
                dep_fd,
                "redaction-report.json",
                "machine-readable document redaction-report.json",
                max_bytes=MAX_DEP_CONTROL_FILE_BYTES,
            )
        except FileNotFoundError:
            pass
        else:
            raise FileExistsError(
                "redaction transaction requires no existing redaction report"
            )
        manifest = json.loads(manifest_before.decode("utf-8"))
        manifest_snapshot = (
            (
                manifest_metadata.st_dev,
                manifest_metadata.st_ino,
                manifest_metadata.st_size,
                manifest_metadata.st_mtime_ns,
            ),
            hashlib.sha256(manifest_before).hexdigest(),
        )
        raw_rows = manifest.get("raw", [])
        if not isinstance(raw_rows, list):
            raise ValueError("Evidence manifest raw must be an array")
        raw_by_name = {
            Path(row.get("path", "")).name: row
            for row in raw_rows
            if isinstance(row, dict)
        }
        if len(raw_by_name) != len(raw_rows):
            raise ValueError("Evidence manifest contains duplicate or invalid raw paths")
        dep_root = dep.resolve(strict=True)
        raw_dir = dep_root / "private" / "raw"
        shareable = dep_root / "shareable" / "artifacts"
        written_outputs: dict[str, tuple[int, int]] = {}
        cleanup_fd: int | None = None

        def cleanup_owned_outputs(directory_fd: int) -> None:
            for name, identity in tuple(written_outputs.items()):
                _remove_owned_at(
                    directory_fd,
                    name,
                    identity,
                    "redaction artifact",
                )

        try:
            with _opened_zone_at(
                dep_fd, Path("private/raw"), create=False
            ) as raw_dir_fd:
                with _opened_zone_at(
                    dep_fd,
                    Path("shareable/artifacts"),
                    create=False,
                    on_change=cleanup_owned_outputs,
                ) as shareable_fd:
                    cleanup_fd = os.dup(shareable_fd)
                    names = sorted(os.listdir(raw_dir_fd))
                    files = [raw_dir / name for name in names]
                    existing_outputs = set(os.listdir(shareable_fd))
                    if existing_outputs:
                        for existing_name in existing_outputs:
                            existing_metadata = os.stat(
                                existing_name,
                                dir_fd=shareable_fd,
                                follow_symlinks=False,
                            )
                            if stat.S_ISLNK(existing_metadata.st_mode):
                                raise ValueError(
                                    "redaction destination must not be a symlink: "
                                    + existing_name
                                )
                        raise FileExistsError(
                            "redaction transaction requires an empty shareable artifact zone"
                        )
                    report = redact_files(
                        files,
                        shareable,
                        metadata_by_name=raw_by_name,
                        source_dir_fd=raw_dir_fd,
                        output_dir_fd=shareable_fd,
                        published_outputs=written_outputs,
                    )
                    output_snapshots = {
                        row["output"]: (row["output_size"], row["output_sha256"])
                        for row in report["files"]
                    }
                    transaction_shareable_fd = transaction.retain_directory(
                        shareable_fd
                    )
                    for output_name, output_identity in written_outputs.items():
                        output_size, output_digest = output_snapshots[output_name]

                        def rollback_output(
                            name=output_name,
                            identity=output_identity,
                            size=output_size,
                            digest=output_digest,
                        ) -> None:
                            _remove_owned_at(
                                transaction_shareable_fd,
                                name,
                                identity,
                                "redaction artifact",
                                expected_size=size,
                                expected_digest=digest,
                            )

                        def verify_output(
                            name=output_name,
                            identity=output_identity,
                            size=output_size,
                            digest=output_digest,
                        ) -> None:
                            _require_regular_snapshot_at(
                                transaction_shareable_fd,
                                name,
                                identity,
                                size,
                                digest,
                                "redaction artifact",
                                max_bytes=MAX_DEP_ARTIFACT_BYTES,
                            )

                        transaction.add(
                            rollback_output,
                            verify=verify_output,
                        )
                    report["dep_id"] = _load_at(dep_fd, "summary.yaml")["dep_id"]
                    report["generated_at"] = utc_now()
                    observed_raw = {
                        row["source"]: (row["source_sha256"], row["source_size"])
                        for row in report["files"]
                    }
                    observed_raw.update(
                        {
                            row["file"]: (row["sha256"], row["size"])
                            for row in report["blocked"]
                        }
                    )
                    for name, row in raw_by_name.items():
                        observed = observed_raw.get(name)
                        if observed is None:
                            raise ValueError(
                                f"raw artifact is not covered by redaction: {name}"
                            )
                        row["sha256"], row["size"] = observed
                    manifest["shareable"] = [
                        {
                            "path": f"shareable/artifacts/{row['output']}",
                            "sha256": row["output_sha256"],
                            "size": row["output_size"],
                            "shareable": True,
                        }
                        for row in report["files"]
                    ]

            report_publication: list[tuple[int, int]] = []
            _save_at(
                dep_fd,
                "redaction-report.json",
                report,
                report_publication,
                must_not_exist=True,
                transaction=transaction,
            )

            expected_report = (
                json.dumps(report, ensure_ascii=False, indent=2) + "\n"
            ).encode("utf-8")
            observed_report, observed_report_metadata = _read_regular_bytes_at(
                dep_fd,
                "redaction-report.json",
                "machine-readable document redaction-report.json",
                max_bytes=MAX_DEP_CONTROL_FILE_BYTES,
            )
            if (
                not report_publication
                or (observed_report_metadata.st_dev, observed_report_metadata.st_ino)
                != report_publication[-1]
                or observed_report != expected_report
            ):
                raise ValueError("redaction report changed before manifest publication")

            manifest_publication: list[tuple[int, int]] = []
            _save_at(
                dep_fd,
                "manifest.json",
                manifest,
                manifest_publication,
                manifest_snapshot,
                transaction=transaction,
            )
            return report
        except BaseException:
            if cleanup_fd is not None:
                cleanup_owned_outputs(cleanup_fd)
            raise
        finally:
            if cleanup_fd is not None:
                try:
                    os.close(cleanup_fd)
                except OSError:
                    pass


def transition(dep: Path, phase: str) -> dict:
    if phase not in PHASES:
        raise ValueError(f"phase must be one of: {', '.join(PHASES)}")
    transaction = _MutationTransaction()
    with _opened_dep_root(
        dep,
        on_change=transaction.rollback,
        on_commit=transaction.finalize,
    ) as dep_fd:
        summary_raw, summary_metadata = _read_regular_bytes_at(
            dep_fd,
            "summary.yaml",
            "machine-readable document summary.yaml",
            max_bytes=MAX_DEP_CONTROL_FILE_BYTES,
        )
        summary = json.loads(summary_raw.decode("utf-8"))
        current = summary["workflow"]["phase"]
        if PHASES.index(phase) != PHASES.index(current) + 1:
            raise ValueError(f"transition must advance exactly one phase: {current} -> {phase}")
        summary["workflow"]["phase"] = phase
        summary["workflow"]["history"].append({"phase": phase, "at": utc_now()})
        summary["updated_at"] = utc_now()
        encoded = (
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
        ).encode("utf-8")
        errors, _, _, _, _ = _verify_open(
            dep,
            dep_fd,
            strict=False,
            portable=False,
            control_overrides={"summary.yaml": encoded},
        )
        if errors:
            raise ValueError(f"cannot enter {phase}: " + "; ".join(errors))
        published: list[tuple[int, int]] = []
        _write_bytes_at(
            dep_fd,
            "summary.yaml",
            encoded,
            "summary transition",
            published,
            (
                (
                    summary_metadata.st_dev,
                    summary_metadata.st_ino,
                    summary_metadata.st_size,
                    summary_metadata.st_mtime_ns,
                ),
                hashlib.sha256(summary_raw).hexdigest(),
            ),
            transaction=transaction,
        )
        return summary


def _verify_manifest_artifacts(
    dep: Path, dep_fd: int, manifest: dict, *, portable: bool
) -> list[str]:
    errors: list[str] = []
    expected_paths: dict[str, set[str]] = {
        "private/raw": set(),
        "shareable/artifacts": set(),
    }
    row_contracts = {
        "raw": {
            "collector", "path", "source_suffix", "media_type", "sha256", "size",
            "collected_at", "shareable"
        },
        "shareable": {"path", "sha256", "size", "shareable"},
    }
    for kind, zone in (("raw", "private/raw"), ("shareable", "shareable/artifacts")):
        rows = manifest.get(kind)
        if not isinstance(rows, list):
            errors.append(f"manifest {kind} must be an array")
            continue
        zone_fd: int | None = None
        zone_context = _opened_zone_at(dep_fd, Path(zone), create=False)
        try:
            zone_fd = zone_context.__enter__()
        except FileNotFoundError:
            if not (portable and kind == "raw"):
                errors.append(f"missing artifact zone: {zone}")
        try:
            for index, row in enumerate(rows):
                label = f"manifest {kind}[{index}]"
                if not isinstance(row, dict) or set(row) != row_contracts[kind]:
                    errors.append(f"{label} has an invalid contract")
                    continue
                if kind == "raw" and row.get("collector") not in COLLECTORS:
                    errors.append(f"{label} has an unsupported collector")
                if kind == "raw" and (
                    not isinstance(row.get("source_suffix"), str)
                    or row["source_suffix"] != Path(str(row.get("path", ""))).suffix.lower()
                ):
                    errors.append(f"{label} source_suffix does not match its immutable path")
                if kind == "raw" and row.get("media_type") not in {
                    "application/har+json",
                    "application/json",
                    "application/octet-stream",
                    "text/plain; charset=utf-8",
                }:
                    errors.append(f"{label} media_type is invalid")
                if kind == "raw" and (
                    not isinstance(row.get("collected_at"), str)
                    or not row["collected_at"].strip()
                ):
                    errors.append(f"{label} collected_at is invalid")
                expected_shareable = kind == "shareable"
                if row.get("shareable") is not expected_shareable:
                    errors.append(f"{label} shareable flag is invalid")
                if (
                    not isinstance(row.get("size"), int)
                    or isinstance(row.get("size"), bool)
                    or row["size"] < 0
                ):
                    errors.append(f"{label} size is invalid")
                if not isinstance(row.get("sha256"), str) or not SHA256_PATTERN.fullmatch(
                    row["sha256"]
                ):
                    errors.append(f"{label} sha256 is invalid")
                try:
                    path = _manifest_artifact_path(dep, row.get("path"), zone)
                except ValueError as exc:
                    errors.append(str(exc))
                    continue
                relative = path.relative_to(dep).as_posix()
                if relative in expected_paths[zone]:
                    errors.append(f"duplicate manifest artifact path: {relative}")
                    continue
                expected_paths[zone].add(relative)
                if zone_fd is None:
                    if not (portable and kind == "raw"):
                        errors.append(f"missing artifact: {relative}")
                    continue
                try:
                    artifact, metadata = _read_regular_bytes_at(
                        zone_fd,
                        path.name,
                        f"artifact {relative}",
                        max_bytes=MAX_DEP_ARTIFACT_BYTES,
                    )
                except FileNotFoundError:
                    if not (portable and kind == "raw"):
                        errors.append(f"missing artifact: {relative}")
                    continue
                except ValueError as exc:
                    errors.append(str(exc))
                    continue
                if isinstance(row.get("size"), int) and metadata.st_size != row["size"]:
                    errors.append(f"artifact size mismatch: {relative}")
                if (
                    isinstance(row.get("sha256"), str)
                    and hashlib.sha256(artifact).hexdigest() != row["sha256"]
                ):
                    errors.append(f"artifact sha256 mismatch: {relative}")
                if kind == "raw":
                    detected = _artifact_media_type(row.get("source_suffix", ""), artifact)
                    legacy_json_label = (
                        manifest.get("schema_version") == LEGACY_MANIFEST_SCHEMA_VERSION
                        and row.get("source_suffix") == ".json"
                        and row.get("media_type") == "text/plain; charset=utf-8"
                        and detected == "application/json"
                    )
                    if row.get("media_type") != detected and not legacy_json_label:
                        errors.append(f"artifact media_type mismatch: {relative}")
            if zone_fd is not None:
                actual, zone_errors = _actual_zone_files_at(zone_fd, zone)
                errors.extend(zone_errors)
                extras = sorted(actual - expected_paths[zone])
                if extras:
                    errors.append(
                        f"unregistered artifacts in {zone}: " + ", ".join(extras)
                    )
        finally:
            if zone_fd is not None:
                zone_context.__exit__(None, None, None)
    return errors


def _verify_redaction_associations(
    dep: Path, dep_fd: int, manifest: dict, report: dict
) -> list[str]:
    errors: list[str] = []
    required_report = {
        "schema_version", "files", "blocked", "totals", "dep_id", "generated_at"
    }
    if set(report) != required_report or report.get("schema_version") != "1.0":
        return ["redaction report has an invalid contract"]
    if report.get("dep_id") != manifest.get("dep_id"):
        errors.append("redaction report dep_id does not match manifest")
    files = report.get("files")
    if not isinstance(files, list):
        return errors + ["redaction report files must be an array"]
    blocked = report.get("blocked")
    if not isinstance(blocked, list):
        return errors + ["redaction report blocked must be an array"]
    raw_rows = {
        Path(row["path"]).name: row
        for row in manifest.get("raw", [])
        if isinstance(row, dict) and isinstance(row.get("path"), str)
    }
    shareable_rows = {
        Path(row["path"]).name: row
        for row in manifest.get("shareable", [])
        if isinstance(row, dict) and isinstance(row.get("path"), str)
    }
    expected_fields = {
        "source", "output", "source_sha256", "source_size",
        "output_sha256", "output_size", "redactions",
    }
    seen_sources: set[str] = set()
    seen_blocked: set[str] = set()
    seen_outputs: set[str] = set()
    computed_totals: dict[str, int] = {}
    for index, row in enumerate(files):
        label = f"redaction report files[{index}]"
        if not isinstance(row, dict) or set(row) != expected_fields:
            errors.append(f"{label} has an invalid contract")
            continue
        source = row.get("source")
        output = row.get("output")
        if (
            not isinstance(source, str)
            or not source
            or Path(source).name != source
            or not isinstance(output, str)
            or not output
            or Path(output).name != output
        ):
            errors.append(f"{label} contains an invalid source or output name")
            continue
        if source in seen_sources or output in seen_outputs:
            errors.append(f"{label} duplicates a source or output association")
            continue
        seen_sources.add(source)
        seen_outputs.add(output)
        if Path(source).suffix.lower() not in TEXT_SUFFIXES:
            errors.append(f"{label} source type is not eligible for deterministic redaction")
        if Path(output).suffix.lower() not in TEXT_SUFFIXES:
            errors.append(f"{label} output type is not eligible for deterministic redaction")
        if Path(source).suffix.lower() != Path(output).suffix.lower():
            errors.append(f"{label} source and output types do not match")
        raw = raw_rows.get(source)
        shareable = shareable_rows.get(output)
        if raw is None or shareable is None:
            errors.append(f"{label} is not fully associated with manifest artifacts")
            continue
        if raw.get("collector") == "browser-har" or raw.get("media_type") == "application/har+json":
            errors.append(f"{label} HAR evidence must remain blocked")
        for report_key, manifest_key, manifest_row in (
            ("source_sha256", "sha256", raw),
            ("source_size", "size", raw),
            ("output_sha256", "sha256", shareable),
            ("output_size", "size", shareable),
        ):
            if row.get(report_key) != manifest_row.get(manifest_key):
                errors.append(f"{label} {report_key} does not match manifest")
        redactions = row.get("redactions")
        if not isinstance(redactions, dict) or any(
            not isinstance(key, str)
            or not key
            or not isinstance(value, int)
            or isinstance(value, bool)
            or value < 1
            for key, value in redactions.items()
        ):
            errors.append(f"{label} redactions are invalid")
        else:
            for key, value in redactions.items():
                computed_totals[key] = computed_totals.get(key, 0) + value

        try:
            raw_path = _manifest_artifact_path(dep, raw["path"], "private/raw")
            output_path = _manifest_artifact_path(
                dep, shareable["path"], "shareable/artifacts"
            )
        except (KeyError, ValueError):
            continue
        if output_path.suffix.lower() in TEXT_SUFFIXES:
            try:
                with _opened_zone_at(
                    dep_fd, Path("shareable/artifacts"), create=False
                ) as shareable_fd:
                    output_bytes, _ = _read_regular_bytes_at(
                        shareable_fd,
                        output_path.name,
                        f"{label} shareable output",
                        max_bytes=MAX_DEP_ARTIFACT_BYTES,
                    )
                output_text = output_bytes.decode("utf-8")
            except FileNotFoundError:
                continue
            except UnicodeDecodeError:
                errors.append(f"{label} shareable text is not valid UTF-8")
            except ValueError as exc:
                errors.append(str(exc))
            else:
                rescanned_output, _ = redact_text(output_text)
                if rescanned_output != output_text:
                    errors.append(f"{label} shareable output still matches redaction rules")
                try:
                    with _opened_zone_at(
                        dep_fd, Path("private/raw"), create=False
                    ) as raw_fd:
                        raw_bytes, _ = _read_regular_bytes_at(
                            raw_fd,
                            raw_path.name,
                            f"{label} raw source",
                            max_bytes=MAX_DEP_ARTIFACT_BYTES,
                        )
                    raw_text = raw_bytes.decode("utf-8")
                except FileNotFoundError:
                    pass
                except UnicodeDecodeError:
                    errors.append(f"{label} raw text is not valid UTF-8")
                except ValueError as exc:
                    errors.append(str(exc))
                else:
                    expected_output, expected_redactions = redact_text(raw_text)
                    if output_text != expected_output:
                        errors.append(
                            f"{label} output is not the deterministic redaction of source"
                        )
                    if redactions != expected_redactions:
                        errors.append(
                            f"{label} redaction counts do not match recalculation"
                        )
    blocked_fields = {"file", "reason", "sha256", "size"}
    for index, row in enumerate(blocked):
        label = f"redaction report blocked[{index}]"
        if not isinstance(row, dict) or set(row) != blocked_fields:
            errors.append(f"{label} has an invalid contract")
            continue
        source = row.get("file")
        if (
            not isinstance(source, str)
            or not source
            or Path(source).name != source
            or not isinstance(row.get("reason"), str)
            or not row["reason"].strip()
        ):
            errors.append(f"{label} contains an invalid file or reason")
            continue
        if source in seen_sources or source in seen_blocked:
            errors.append(f"{label} duplicates or overlaps a raw association")
            continue
        seen_blocked.add(source)
        raw = raw_rows.get(source)
        if raw is None:
            errors.append(f"{label} is not associated with a manifest raw artifact")
            continue
        if row.get("sha256") != raw.get("sha256"):
            errors.append(f"{label} sha256 does not match manifest")
        if row.get("size") != raw.get("size"):
            errors.append(f"{label} size does not match manifest")
        if (
            raw.get("collector") == "browser-har"
            or raw.get("media_type") == "application/har+json"
        ) and row.get("reason") != "har_requires_dedicated_body_stripping":
            errors.append(f"{label} HAR block reason is invalid")

    if seen_sources | seen_blocked != set(raw_rows):
        errors.append("redaction report does not cover every raw artifact exactly once")
    if seen_outputs != set(shareable_rows):
        errors.append("redaction report does not cover every shareable artifact")
    if report.get("totals") != computed_totals:
        errors.append("redaction report totals do not match file associations")
    return errors


def _verify_open(
    dep: Path,
    dep_fd: int,
    strict: bool,
    portable: bool,
    control_overrides: dict[str, bytes] | None = None,
) -> tuple[
    list[str],
    dict | None,
    dict | None,
    dict[str, tuple[int, int, int, int]],
    str | None,
]:
    """Verify one immutable-in-memory snapshot of the DEP control documents."""
    errors: list[str] = []
    control_bytes: dict[str, bytes] = {}
    control_identities: dict[str, tuple[int, int, int, int]] = {}
    for name in os.listdir(dep_fd):
        if (
            name.startswith(".attach-") and ".pending-" in name
        ) or name.startswith(
            (
                ".sddgov.attachment-stage-",
                ".sddgov.attachment-claim-",
                ".sddgov.control-stage-",
                ".sddgov.control-new-",
                ".sddgov.control-old-",
                ".sddgov.redaction-stage-",
                ".sddgov.redaction-claim-",
            )
        ) or name.startswith(".redact-pending-") or any(
            marker in name
            for marker in (".control-pending-", ".cleanup-pending-")
        ):
            errors.append(f"pending Evidence transaction residue: {name}")
    if portable and not strict:
        errors.append("portable verification requires strict mode")
    for name in ("summary.yaml", "manifest.json"):
        try:
            document, metadata = _read_regular_bytes_at(
                dep_fd, name, name, max_bytes=MAX_DEP_CONTROL_FILE_BYTES
            )
            control_bytes[name] = (control_overrides or {}).get(name, document)
            control_identities[name] = (
                metadata.st_dev,
                metadata.st_ino,
                metadata.st_size,
                metadata.st_mtime_ns,
            )
        except FileNotFoundError:
            errors.append(f"missing {name}")
        except ValueError as exc:
            errors.append(str(exc))
    if errors:
        return errors, None, None, control_identities, None
    snapshot_digest = _control_snapshot_digest(control_bytes)
    try:
        summary = json.loads(control_bytes["summary.yaml"].decode("utf-8"))
        manifest = json.loads(control_bytes["manifest.json"].decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return (
            [f"invalid machine-readable document: {exc}"],
            None,
            None,
            control_identities,
            snapshot_digest,
        )
    try:
        errors.extend(
            f"summary schema: {error}"
            for error in validate_instance(
                summary,
                bundled_schema("debug-evidence-package.schema.json"),
            )
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        errors.append(f"summary schema unavailable: {exc}")
    for field in ("dep_id", "issue", "risk_level", "workflow", "expected_behavior", "actual_behavior", "environment"):
        if field not in summary:
            errors.append(f"summary missing {field}")
    if (
        set(manifest) != {"schema_version", "dep_id", "raw", "shareable"}
        or manifest.get("schema_version")
        not in {LEGACY_MANIFEST_SCHEMA_VERSION, MANIFEST_SCHEMA_VERSION}
    ):
        errors.append("manifest has an invalid root contract")
    if manifest.get("dep_id") != summary.get("dep_id"):
        errors.append("manifest dep_id does not match summary")
    phase = summary.get("workflow", {}).get("phase")
    if phase not in PHASES:
        errors.append("invalid workflow phase")
        return errors, summary, manifest, control_identities, snapshot_digest
    history = summary.get("workflow", {}).get("history")
    expected_history = list(PHASES[: PHASES.index(phase) + 1])
    actual_history = (
        [item.get("phase") for item in history if isinstance(item, dict)]
        if isinstance(history, list)
        else []
    )
    if actual_history != expected_history or not isinstance(history, list) or len(history) != len(expected_history):
        errors.append(
            "workflow history must be the exact phase prefix: " + " -> ".join(expected_history)
        )
    if strict and phase != "proof":
        errors.append(f"strict verification requires proof phase, found {phase}")
    for name in REQUIRED_DOCS["proof" if strict else phase]:
        try:
            document, _ = _read_regular_bytes_at(
                dep_fd, name, name, max_bytes=MAX_DEP_CONTROL_FILE_BYTES
            )
        except FileNotFoundError:
            errors.append(f"missing {name}")
            continue
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if name.endswith(".md"):
            text = document.decode("utf-8", errors="ignore")
            meaningful = [
                line
                for line in text.splitlines()
                if line.strip() and not line.lstrip().startswith("#")
            ]
            if not any(
                "TODO" not in line and "<!--" not in line and "-->" not in line
                for line in meaningful
            ):
                errors.append(f"template not completed: {name}")
    if PHASES.index(phase) >= PHASES.index("evidence") or strict:
        if not manifest.get("raw"):
            errors.append("no collected evidence")
        try:
            report = _load_at(dep_fd, "redaction-report.json")
        except FileNotFoundError:
            report = None
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            errors.append(f"invalid redaction report: {exc}")
            report = None
        if report is not None:
            if report.get("blocked"):
                errors.append("redaction report contains blocked artifacts requiring manual review")
            if not manifest.get("shareable"):
                errors.append("no shareable redacted evidence")
            errors.extend(
                _verify_redaction_associations(dep, dep_fd, manifest, report)
            )
        errors.extend(
            _verify_manifest_artifacts(
                dep, dep_fd, manifest, portable=portable
            )
        )
    raw_refs = [
        attachment
        for attachment in summary.get("attachments", [])
        if isinstance(attachment, dict)
        and str(attachment.get("path", "")).startswith("private/")
    ]
    if raw_refs:
        errors.append("summary attachments must never reference private/raw evidence")
    shareable_by_path = {
        row.get("path"): row
        for row in manifest.get("shareable", [])
        if isinstance(row, dict)
    }
    for attachment in summary.get("attachments", []):
        if not isinstance(attachment, dict):
            continue
        registered = shareable_by_path.get(attachment.get("path"))
        if registered is None or registered.get("sha256") != attachment.get("sha256"):
            errors.append("summary attachment is not bound to a matching shareable artifact")
    return errors, summary, manifest, control_identities, snapshot_digest


def _require_control_snapshot(
    dep_fd: int,
    identities: dict[str, tuple[int, int, int, int]],
    expected_digest: str,
) -> None:
    """Fail closed if verified control identity or exact bytes changed before use."""
    control_bytes: dict[str, bytes] = {}
    for name in ("summary.yaml", "manifest.json"):
        try:
            raw, metadata = _read_regular_bytes_at(
                dep_fd,
                name,
                f"verified control document {name}",
                max_bytes=MAX_DEP_CONTROL_FILE_BYTES,
            )
        except (OSError, ValueError) as exc:
            raise ValueError(f"verified control document changed: {name}") from exc
        observed = (
            metadata.st_dev,
            metadata.st_ino,
            metadata.st_size,
            metadata.st_mtime_ns,
        )
        if not stat.S_ISREG(metadata.st_mode) or observed != identities.get(name):
            raise ValueError(f"verified control document changed: {name}")
        control_bytes[name] = raw
    if _control_snapshot_digest(control_bytes) != expected_digest:
        raise ValueError("verified control document bytes changed")


def verify(dep: Path, strict: bool = False, portable: bool = False) -> list[str]:
    try:
        with _opened_dep_root(dep) as dep_fd:
            errors, _, _, _, _ = _verify_open(dep, dep_fd, strict, portable)
            return errors
    except (OSError, ValueError) as exc:
        return [f"Evidence filesystem boundary changed or is unsafe: {exc}"]


def attach(dep: Path, target: str, output: Path | None = None) -> Path:
    if target not in {"issue", "commit", "pr", "changelog"}:
        raise ValueError("target must be issue, commit, pr, or changelog")
    published_name = ""
    published_identity: tuple[int, int] | None = None
    cleanup_fd = -1
    attachment_size = 0
    attachment_digest = ""

    def cleanup_attachment(directory_fd: int) -> None:
        if published_identity is None or not published_name:
            return
        active_directory_fd = cleanup_fd if cleanup_fd >= 0 else directory_fd
        _remove_owned_at(
            active_directory_fd,
            published_name,
            published_identity,
            "attachment output",
            expected_size=attachment_size,
            expected_digest=attachment_digest,
        )

    try:
        with _opened_dep_root(dep, on_change=cleanup_attachment) as dep_fd:
            errors, summary, manifest, identities, snapshot_digest = _verify_open(
                dep, dep_fd, strict=True, portable=False
            )
            if errors:
                raise ValueError("DEP is not attachable: " + "; ".join(errors))
            if summary is None or manifest is None or snapshot_digest is None:
                raise ValueError("DEP verification did not return a control snapshot")
            artifact_identities = _capture_artifact_snapshot(dep_fd, manifest)
            lines = [
                f"Evidence: {summary['dep_id']}",
                f"Issue: {summary['issue']}",
                f"SDD: {', '.join(summary.get('sdd_references') or ['n/a'])}",
                f"Risk: {summary['risk_level']}",
                f"Control snapshot SHA-256: `{snapshot_digest}`",
                "Workflow: Red -> Evidence -> Fix -> Green -> Proof",
                "Verified artifacts:",
            ]
            lines.extend(
                f"- `{row['path']}` (sha256: `{row['sha256']}`)"
                for row in manifest.get("shareable", [])
            )
            lines.extend(["", f"Target: {target}"])
            encoded = ("\n".join(lines) + "\n").encode("utf-8")
            attachment_size = len(encoded)
            attachment_digest = hashlib.sha256(encoded).hexdigest()
            if output is None:
                published_name = f"attach-{target}-{snapshot_digest[:16]}.md"
                cleanup_fd = os.dup(dep_fd)
                published_identity = _publish_verified_attachment_at(
                    dep_fd,
                    dep_fd,
                    published_name,
                    encoded,
                    identities,
                    snapshot_digest,
                    artifact_identities,
                )
                result = dep / published_name
            else:
                published_name = output.name
                with _opened_directory_path(
                    output.parent,
                    create=False,
                    on_change=cleanup_attachment,
                ) as (_, output_fd):
                    cleanup_fd = os.dup(output_fd)
                    published_identity = _publish_verified_attachment_at(
                        dep_fd,
                        output_fd,
                        published_name,
                        encoded,
                        identities,
                        snapshot_digest,
                        artifact_identities,
                    )
                result = output
        return result
    finally:
        if cleanup_fd >= 0:
            try:
                os.close(cleanup_fd)
            except OSError:
                pass
