"""Shared descriptor-relative filesystem transaction helpers."""

from __future__ import annotations

import os
import secrets
import stat


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
    try:
        os.unlink(pending, dir_fd=directory_fd)
    except FileNotFoundError:
        pass
    os.fsync(directory_fd)
    return False
