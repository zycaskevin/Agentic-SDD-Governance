"""Shared descriptor-relative filesystem transaction helpers."""

from __future__ import annotations

import os
import secrets
import stat
import sys
from pathlib import Path


def canonicalize_platform_path(path: Path) -> Path:
    """Normalize only fixed Darwin system aliases, never caller path links."""
    candidate = Path(os.path.abspath(os.fspath(path)))
    if sys.platform == "darwin":
        if candidate.parts[:2] == ("/", "var"):
            return Path("/private/var").joinpath(*candidate.parts[2:])
        if candidate.parts[:2] == ("/", "tmp"):
            return Path("/private/tmp").joinpath(*candidate.parts[2:])
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


def remove_owned_at(
    directory_fd: int,
    name: str,
    expected_identity: tuple[int, int],
    label: str,
) -> bool:
    """Remove only one owned generation while preserving a later writer."""
    # Keep the private reconciliation name independent of the caller-controlled
    # basename. A valid leaf may already consume every byte allowed by NAME_MAX;
    # appending a marker would then make failure cleanup fail before it can
    # inspect the owned generation.
    pending = f".sddgov.cleanup-pending-{secrets.token_hex(16)}"
    try:
        os.rename(
            name,
            pending,
            src_dir_fd=directory_fd,
            dst_dir_fd=directory_fd,
        )
    except FileNotFoundError:
        return False
    try:
        metadata = os.stat(pending, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    if (
        stat.S_ISREG(metadata.st_mode)
        and (metadata.st_dev, metadata.st_ino) == expected_identity
    ):
        try:
            os.unlink(pending, dir_fd=directory_fd)
        except FileNotFoundError:
            pass
        os.fsync(directory_fd)
        return True
    try:
        os.link(
            pending,
            name,
            src_dir_fd=directory_fd,
            dst_dir_fd=directory_fd,
            follow_symlinks=False,
        )
    except FileNotFoundError:
        return False
    except FileExistsError as exc:
        raise ValueError(
            f"{label} changed during cleanup; preserved pending generation {pending}"
        ) from exc
    except (OSError, NotImplementedError) as exc:
        raise ValueError(
            f"{label} cleanup could not restore the original name; "
            f"preserved pending generation {pending}"
        ) from exc
    try:
        os.unlink(pending, dir_fd=directory_fd)
    except FileNotFoundError:
        pass
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
                remove_owned_at(directory_fd, expanded.name, identity, label)
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
