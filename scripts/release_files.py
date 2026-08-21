"""Shared regular-file and digest checks for release tooling."""

from __future__ import annotations

import hashlib
import re
import stat
from pathlib import Path


SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]*$")


def regular_file(path: Path, label: str) -> Path:
    expanded = path.expanduser()
    metadata = expanded.stat(follow_symlinks=False)
    if (
        expanded.is_symlink()
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
    ):
        raise ValueError(f"{label} must be a single-linked regular file: {path}")
    if SAFE_NAME.fullmatch(expanded.name) is None:
        raise ValueError(f"{label} has an unsafe filename: {expanded.name}")
    return expanded.resolve(strict=True)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
