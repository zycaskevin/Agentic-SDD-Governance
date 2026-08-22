"""Shared descriptor-relative filesystem transaction helpers."""

from __future__ import annotations

import os
import secrets
import stat
from pathlib import Path


def remove_owned_at(
    directory_fd: int,
    name: str,
    expected_identity: tuple[int, int],
    label: str,
) -> bool:
    """Remove only one owned generation while preserving a later writer."""
    pending = f".{name}.cleanup-pending-{secrets.token_hex(16)}"
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
    except OSError as exc:
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
    expanded = Path(os.path.abspath(os.fspath(path)))
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
            os.close(directory_fd)
            directory_fd = next_fd
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
        os.close(descriptor)
        descriptor = -1
        os.fsync(directory_fd)
    except BaseException:
        if descriptor >= 0:
            os.close(descriptor)
            descriptor = -1
        if identity is not None:
            try:
                current = os.stat(
                    expanded.name, dir_fd=directory_fd, follow_symlinks=False
                )
            except FileNotFoundError:
                pass
            else:
                if (current.st_dev, current.st_ino) == identity:
                    os.unlink(expanded.name, dir_fd=directory_fd)
                    os.fsync(directory_fd)
        raise
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        os.close(directory_fd)
