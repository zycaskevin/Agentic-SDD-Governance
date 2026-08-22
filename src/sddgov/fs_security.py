"""Shared descriptor-relative filesystem transaction helpers."""

from __future__ import annotations

import ctypes
import errno
import hashlib
import os
import secrets
import stat
import sys
from pathlib import Path, PurePosixPath
from typing import Any


LINUX_RENAME_NOREPLACE = 1
DARWIN_RENAME_EXCL = 0x00000004


def _file_snapshot(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_nlink,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


class FileSetSnapshot:
    """Read and reconcile one call-wide set of regular files under one root.

    Every directory and file descriptor stays open until all requested files have
    been read and revalidated.  This prevents a caller from constructing one
    approval identity from path generations that were never simultaneously
    reachable from the requested root.
    """

    def __init__(
        self,
        root: Path,
        label: str,
        *,
        require_protected: bool = False,
    ) -> None:
        self.root = canonicalize_platform_path(root)
        self.label = label
        self.require_protected = require_protected
        self.root_fd = -1
        self._records: dict[str, dict[str, Any]] = {}

    def __enter__(self) -> "FileSetSnapshot":
        self.root_fd = open_directory_path(self.root, self.label)
        return self

    def _close_descriptors(self) -> BaseException | None:
        error: BaseException | None = None
        for record in reversed(list(self._records.values())):
            file_fd = record["file_fd"]
            record["file_fd"] = -1
            if file_fd >= 0:
                try:
                    os.close(file_fd)
                except BaseException as exc:
                    if error is None:
                        error = exc
            directories = record["directories"]
            while directories:
                descriptor = directories.pop()
                try:
                    os.close(descriptor)
                except BaseException as exc:
                    if error is None:
                        error = exc
        root_fd = self.root_fd
        self.root_fd = -1
        if root_fd >= 0:
            try:
                os.close(root_fd)
            except BaseException as exc:
                if error is None:
                    error = exc
        return error

    def __exit__(self, exc_type, exc, _traceback) -> bool:
        primary: BaseException | None = exc
        if primary is None:
            try:
                self.revalidate()
            except BaseException as revalidation_error:
                primary = revalidation_error
        cleanup_error = self._close_descriptors()
        if exc is not None:
            if cleanup_error is not None:
                raise exc from cleanup_error
            return False
        if primary is not None:
            if cleanup_error is not None:
                raise primary from cleanup_error
            raise primary
        if cleanup_error is not None:
            raise cleanup_error
        return False

    @staticmethod
    def _bounded_read(descriptor: int, max_bytes: int) -> bytes:
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(descriptor, min(1024 * 1024, max_bytes + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > max_bytes:
                raise ValueError("descriptor snapshot input exceeds the bounded size")
        return b"".join(chunks)

    def read(self, relative: PurePosixPath, *, max_bytes: int) -> bytes:
        if self.root_fd < 0:
            raise ValueError(f"{self.label} snapshot is not open")
        value = str(relative)
        if (
            not value
            or "\\" in value
            or "\x00" in value
            or relative.is_absolute()
            or str(relative) != value
            or any(part in {"", ".", ".."} for part in relative.parts)
        ):
            raise ValueError(f"{self.label} path is unsafe")
        existing = self._records.get(value)
        if existing is not None:
            return existing["raw"]

        flags = (
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0)
        )
        directories: list[int] = []
        file_fd = -1
        try:
            current = os.dup(self.root_fd)
            directories.append(current)
            for part in relative.parts[:-1]:
                child = os.open(part, flags, dir_fd=current)
                metadata = os.fstat(child)
                if not stat.S_ISDIR(metadata.st_mode):
                    raise ValueError(f"{self.label} path component is not a directory")
                directories.append(child)
                current = child
            file_fd = os.open(
                relative.name,
                os.O_RDONLY
                | getattr(os, "O_NONBLOCK", 0)
                | getattr(os, "O_NOFOLLOW", 0)
                | getattr(os, "O_CLOEXEC", 0),
                dir_fd=directories[-1],
            )
            before = os.fstat(file_fd)
            path_before = os.stat(
                relative.name,
                dir_fd=directories[-1],
                follow_symlinks=False,
            )
            if (
                not stat.S_ISREG(before.st_mode)
                or before.st_nlink != 1
                or _file_snapshot(before) != _file_snapshot(path_before)
                or before.st_size > max_bytes
                or (
                    self.require_protected
                    and os.name != "nt"
                    and (before.st_uid != os.geteuid() or before.st_mode & 0o022)
                )
            ):
                raise ValueError(f"{self.label} file cannot be read safely")
            raw = self._bounded_read(file_fd, max_bytes)
            after = os.fstat(file_fd)
            if _file_snapshot(before) != _file_snapshot(after) or len(raw) != before.st_size:
                raise ValueError(f"{self.label} file changed while being read")
            self._records[value] = {
                "relative": relative,
                "directories": directories,
                "file_fd": file_fd,
                "snapshot": _file_snapshot(before),
                "raw": raw,
                "max_bytes": max_bytes,
            }
            directories = []
            file_fd = -1
            return raw
        except BaseException as primary:
            if isinstance(primary, OSError):
                safe_primary = ValueError(f"{self.label} file cannot be opened safely")
                safe_primary.__cause__ = primary
                primary = safe_primary
            cleanup_error: BaseException | None = None
            if file_fd >= 0:
                closing = file_fd
                file_fd = -1
                try:
                    os.close(closing)
                except BaseException as error:
                    cleanup_error = error
            while directories:
                closing = directories.pop()
                try:
                    os.close(closing)
                except BaseException as error:
                    if cleanup_error is None:
                        cleanup_error = error
            if cleanup_error is not None:
                raise primary from cleanup_error
            raise primary

    def revalidate(self) -> None:
        if self.root_fd < 0:
            raise ValueError(f"{self.label} snapshot is not open")
        for record in self._records.values():
            try:
                relative = record["relative"]
                directories = record["directories"]
                file_fd = record["file_fd"]
                expected = record["snapshot"]
                os.lseek(file_fd, 0, os.SEEK_SET)
                raw = self._bounded_read(file_fd, record["max_bytes"])
                current_file = os.fstat(file_fd)
                current_path = os.stat(
                    relative.name,
                    dir_fd=directories[-1],
                    follow_symlinks=False,
                )
                if (
                    raw != record["raw"]
                    or _file_snapshot(current_file) != expected
                    or _file_snapshot(current_path) != expected
                ):
                    raise ValueError(f"{self.label} file set changed during operation")
                for index, part in enumerate(relative.parts[:-1]):
                    current = os.stat(
                        part,
                        dir_fd=directories[index],
                        follow_symlinks=False,
                    )
                    opened = os.fstat(directories[index + 1])
                    if (
                        stat.S_ISLNK(current.st_mode)
                        or not stat.S_ISDIR(current.st_mode)
                        or (current.st_dev, current.st_ino)
                        != (opened.st_dev, opened.st_ino)
                    ):
                        raise ValueError(
                            f"{self.label} directory set changed during operation"
                        )
            except OSError as exc:
                raise ValueError(f"{self.label} file set changed during operation") from exc
        require_directory_path_identity(self.root, self.root_fd, self.label)


def exclusive_rename_at(
    source_directory: int,
    source_name: str,
    destination_directory: int,
    destination_name: str,
) -> None:
    """Rename one direct child without replacing an existing generation."""
    if (
        not source_name
        or not destination_name
        or "/" in source_name
        or "/" in destination_name
    ):
        raise ValueError("exclusive rename requires single path components")
    if sys.platform == "linux":
        symbol = "renameat2"
        flag = LINUX_RENAME_NOREPLACE
    elif sys.platform == "darwin":
        symbol = "renameatx_np"
        flag = DARWIN_RENAME_EXCL
    else:
        raise NotImplementedError(
            "exclusive descriptor-relative rename requires Linux or macOS"
        )
    library = ctypes.CDLL(None, use_errno=True)
    operation = getattr(library, symbol, None)
    if operation is None:
        raise NotImplementedError(f"platform libc does not expose required {symbol}")
    operation.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    operation.restype = ctypes.c_int
    ctypes.set_errno(0)
    result = operation(
        source_directory,
        os.fsencode(source_name),
        destination_directory,
        os.fsencode(destination_name),
        flag,
    )
    if result != 0:
        error = ctypes.get_errno() or errno.EIO
        raise OSError(error, os.strerror(error), destination_name)


def canonicalize_platform_path(path: Path) -> Path:
    """Normalize only fixed Darwin system aliases, never caller path links."""
    candidate = Path(os.path.abspath(os.fspath(path)))
    if sys.platform == "darwin":
        if candidate.parts[:2] == ("/", "var"):
            return Path("/private/var").joinpath(*candidate.parts[2:])
        if candidate.parts[:2] == ("/", "tmp"):
            return Path("/private/tmp").joinpath(*candidate.parts[2:])
        if candidate.parts[:2] == ("/", "etc"):
            return Path("/private/etc").joinpath(*candidate.parts[2:])
    return candidate


def open_directory_path(
    path: Path,
    label: str,
    *,
    create: bool = False,
    directory_mode: int = 0o755,
) -> int:
    """Retain one directory generation through a no-follow component walk."""
    if os.name != "posix":
        raise ValueError(f"{label} requires POSIX descriptor-bound filesystem support")
    expanded = canonicalize_platform_path(path)
    flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0)
    )
    descriptor = os.open(expanded.anchor or os.sep, flags)
    try:
        parts = expanded.parts[1:] if expanded.anchor else expanded.parts
        for part in parts:
            if part in {"", ".", ".."}:
                raise ValueError(f"{label} has an unsafe path component")
            if create:
                try:
                    os.mkdir(part, mode=directory_mode, dir_fd=descriptor)
                    os.fsync(descriptor)
                except FileExistsError:
                    pass
            next_descriptor = os.open(part, flags, dir_fd=descriptor)
            metadata = os.fstat(next_descriptor)
            if not stat.S_ISDIR(metadata.st_mode):
                os.close(next_descriptor)
                raise ValueError(f"{label} component is not a directory")
            previous_descriptor = descriptor
            descriptor = next_descriptor
            os.close(previous_descriptor)
        return descriptor
    except BaseException as primary:
        closing_descriptor = descriptor
        descriptor = -1
        try:
            os.close(closing_descriptor)
        except BaseException as cleanup_error:
            raise primary from cleanup_error
        raise


def require_directory_path_identity(path: Path, descriptor: int, label: str) -> None:
    """Require ``path`` to still reach the retained directory generation."""
    current_descriptor = -1
    try:
        current_descriptor = open_directory_path(path, label)
        opened = os.fstat(descriptor)
        current = os.fstat(current_descriptor)
        if (
            not stat.S_ISDIR(opened.st_mode)
            or not stat.S_ISDIR(current.st_mode)
            or (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino)
        ):
            raise ValueError(f"{label} changed during operation")
    except OSError as exc:
        raise ValueError(f"{label} changed during operation") from exc
    finally:
        if current_descriptor >= 0:
            closing_descriptor = current_descriptor
            current_descriptor = -1
            try:
                os.close(closing_descriptor)
            except OSError:
                pass


def remove_owned_at(
    directory_fd: int,
    name: str,
    expected_identity: tuple[int, int],
    label: str,
    *,
    expected_size: int | None = None,
    expected_digest: str | None = None,
) -> bool:
    """Remove only one owned generation while preserving a later writer."""
    # Keep the private reconciliation name independent of the caller-controlled
    # basename. A valid leaf may already consume every byte allowed by NAME_MAX;
    # appending a marker would then make failure cleanup fail before it can
    # inspect the owned generation.
    pending = ""
    for _ in range(16):
        candidate = f".sddgov.cleanup-pending-{secrets.token_hex(16)}"
        try:
            exclusive_rename_at(
                directory_fd,
                name,
                directory_fd,
                candidate,
            )
        except FileNotFoundError:
            return False
        except FileExistsError:
            continue
        except (OSError, NotImplementedError) as exc:
            raise ValueError(
                f"{label} cleanup could not reserve a private generation"
            ) from exc
        pending = candidate
        break
    if not pending:
        raise ValueError(f"{label} cleanup could not reserve a private generation")

    def restore_claim(primary: BaseException | None = None) -> None:
        try:
            exclusive_rename_at(directory_fd, pending, directory_fd, name)
        except FileNotFoundError:
            return
        except FileExistsError as exc:
            error = ValueError(
                f"{label} changed during cleanup; preserved pending generation {pending}"
            )
            if primary is not None:
                raise primary from error
            raise error from exc
        except (OSError, NotImplementedError) as exc:
            error = ValueError(
                f"{label} cleanup could not restore the original name; "
                f"preserved pending generation {pending}"
            )
            if primary is not None:
                raise primary from error
            raise error from exc

    try:
        metadata = os.stat(pending, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    except BaseException as primary:
        restore_claim(primary)
        raise
    owned = (
        stat.S_ISREG(metadata.st_mode)
        and (metadata.st_dev, metadata.st_ino) == expected_identity
    )
    if owned and (expected_size is not None or expected_digest is not None):
        descriptor = -1
        try:
            descriptor = os.open(
                pending,
                os.O_RDONLY
                | getattr(os, "O_NONBLOCK", 0)
                | getattr(os, "O_NOFOLLOW", 0)
                | getattr(os, "O_CLOEXEC", 0),
                dir_fd=directory_fd,
            )
            opened = os.fstat(descriptor)
            digest = hashlib.sha256()
            size = 0
            while True:
                chunk = os.read(descriptor, 1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if expected_size is not None and size > expected_size:
                    break
                digest.update(chunk)
            final = os.fstat(descriptor)
            owned = (
                stat.S_ISREG(opened.st_mode)
                and (opened.st_dev, opened.st_ino) == expected_identity
                and (
                    opened.st_dev,
                    opened.st_ino,
                    opened.st_size,
                    opened.st_mtime_ns,
                    opened.st_ctime_ns,
                    opened.st_nlink,
                )
                == (
                    final.st_dev,
                    final.st_ino,
                    final.st_size,
                    final.st_mtime_ns,
                    final.st_ctime_ns,
                    final.st_nlink,
                )
                and (expected_size is None or size == expected_size)
                and (expected_digest is None or digest.hexdigest() == expected_digest)
            )
            closing_descriptor = descriptor
            descriptor = -1
            os.close(closing_descriptor)
        except BaseException as primary:
            if descriptor >= 0:
                closing_descriptor = descriptor
                descriptor = -1
                try:
                    os.close(closing_descriptor)
                except BaseException as cleanup_error:
                    restore_claim(primary)
                    raise primary from cleanup_error
            restore_claim(primary)
            raise
    if owned:
        try:
            os.unlink(pending, dir_fd=directory_fd)
        except FileNotFoundError:
            pass
        except OSError as exc:
            try:
                os.stat(pending, dir_fd=directory_fd, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise exc
        os.fsync(directory_fd)
        return True
    restore_claim()
    os.fsync(directory_fd)
    return False


def write_new_regular_file(
    path: Path,
    data: bytes,
    label: str,
    *,
    mode: int = 0o600,
    directory_mode: int = 0o755,
) -> None:
    """Create a new regular file through a retained, no-follow parent chain."""
    if os.name != "posix":
        raise ValueError(f"{label} requires POSIX descriptor-bound filesystem support")
    expanded = canonicalize_platform_path(path)
    if not expanded.name or expanded.name in {".", ".."}:
        raise ValueError(f"{label} has an unsafe filename")
    flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0)
    )
    directory_fd = os.open(expanded.anchor or os.sep, flags)
    descriptor = -1
    staging_guard = -1
    identity: tuple[int, int] | None = None
    try:
        parts = expanded.parent.parts[1:] if expanded.anchor else expanded.parent.parts
        for part in parts:
            if part in {"", ".", ".."}:
                raise ValueError(f"{label} has an unsafe parent path")
            try:
                os.mkdir(part, mode=directory_mode, dir_fd=directory_fd)
                os.fsync(directory_fd)
            except FileExistsError:
                pass
            next_fd = os.open(part, flags, dir_fd=directory_fd)
            previous_directory_fd = directory_fd
            directory_fd = next_fd
            os.close(previous_directory_fd)
        descriptor = os.open(
            expanded.name,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
            mode,
            dir_fd=directory_fd,
        )
        created = os.fstat(descriptor)
        identity = (created.st_dev, created.st_ino)
        if not stat.S_ISREG(created.st_mode) or created.st_nlink != 1:
            raise ValueError(f"{label} must be a single-linked regular file")
        view = memoryview(data)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError(f"{label} write made no progress")
            view = view[written:]
        os.fsync(descriptor)
        final_fd = os.fstat(descriptor)
        final_path = os.stat(
            expanded.name, dir_fd=directory_fd, follow_symlinks=False
        )
        if (
            not stat.S_ISREG(final_path.st_mode)
            or final_path.st_nlink != 1
            or (final_fd.st_dev, final_fd.st_ino) != identity
            or (final_path.st_dev, final_path.st_ino) != identity
        ):
            raise ValueError(f"{label} changed during write")
        staging_guard = os.dup(descriptor)
        closing_descriptor = descriptor
        descriptor = -1
        os.close(closing_descriptor)
        os.fsync(directory_fd)
        require_directory_path_identity(
            expanded.parent,
            directory_fd,
            f"{label} parent directory",
        )
        committed_fd = os.fstat(staging_guard)
        committed_path = os.stat(
            expanded.name,
            dir_fd=directory_fd,
            follow_symlinks=False,
        )
        expected_snapshot = (
            final_fd.st_dev,
            final_fd.st_ino,
            final_fd.st_mode,
            final_fd.st_nlink,
            final_fd.st_size,
            final_fd.st_mtime_ns,
            final_fd.st_ctime_ns,
        )
        if (
            (
                committed_fd.st_dev,
                committed_fd.st_ino,
                committed_fd.st_mode,
                committed_fd.st_nlink,
                committed_fd.st_size,
                committed_fd.st_mtime_ns,
                committed_fd.st_ctime_ns,
            )
            != expected_snapshot
            or (
                committed_path.st_dev,
                committed_path.st_ino,
                committed_path.st_mode,
                committed_path.st_nlink,
                committed_path.st_size,
                committed_path.st_mtime_ns,
                committed_path.st_ctime_ns,
            )
            != expected_snapshot
        ):
            raise ValueError(f"{label} changed before path publication committed")
        closing_guard = staging_guard
        staging_guard = -1
        try:
            os.close(closing_guard)
        except OSError:
            # The generation is durable. A close error is not safely retryable.
            pass
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
                remove_owned_at(
                    directory_fd,
                    expanded.name,
                    identity,
                    label,
                    expected_size=len(data),
                    expected_digest=hashlib.sha256(data).hexdigest(),
                )
            except BaseException as exc:
                if cleanup_error is None:
                    cleanup_error = exc
        if staging_guard >= 0:
            closing_guard = staging_guard
            staging_guard = -1
            try:
                os.close(closing_guard)
            except BaseException as exc:
                if cleanup_error is None:
                    cleanup_error = exc
        closing_directory_fd = directory_fd
        directory_fd = -1
        try:
            os.close(closing_directory_fd)
        except BaseException as exc:
            if cleanup_error is None:
                cleanup_error = exc
        if cleanup_error is not None:
            raise primary from cleanup_error
        raise
    else:
        closing_directory_fd = directory_fd
        directory_fd = -1
        try:
            os.close(closing_directory_fd)
        except OSError:
            # The file and containing directory are already durable. close(2)
            # errors are not safely retryable because the fd may be reused.
            pass
