"""Descriptor-bound regular-file operations for release tooling."""

from __future__ import annotations

import hashlib
import os
import re
import stat
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Iterator


SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]*$")


def _identity(metadata: os.stat_result) -> tuple[int, int, int, int, int, int]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
        metadata.st_nlink,
    )


@dataclass
class OpenedRegularFile:
    """One validated release input held open for its complete use window."""

    path: Path
    label: str
    descriptor: int
    initial_metadata: os.stat_result

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def suffix(self) -> str:
        return self.path.suffix

    def _verify_unchanged(self) -> None:
        current = os.fstat(self.descriptor)
        if _identity(current) != _identity(self.initial_metadata):
            raise ValueError(f"{self.label} changed after it was opened: {self.path}")

    def _rewind(self) -> None:
        self._verify_unchanged()
        os.lseek(self.descriptor, 0, os.SEEK_SET)

    def read_bytes(self) -> bytes:
        self._rewind()
        chunks: list[bytes] = []
        while True:
            chunk = os.read(self.descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        self._verify_unchanged()
        return b"".join(chunks)

    def read_text(self, *, encoding: str) -> str:
        return self.read_bytes().decode(encoding)

    def sha256(self) -> str:
        self._rewind()
        digest = hashlib.sha256()
        while True:
            chunk = os.read(self.descriptor, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
        self._verify_unchanged()
        return digest.hexdigest()

    @contextmanager
    def binary_stream(self) -> Iterator[BinaryIO]:
        self._rewind()
        duplicate = os.dup(self.descriptor)
        try:
            with os.fdopen(duplicate, "rb", closefd=True) as handle:
                duplicate = -1
                yield handle
        finally:
            if duplicate >= 0:
                os.close(duplicate)
            self._verify_unchanged()

    def copy_to(self, destination: Path, *, mode: int = 0o644) -> None:
        self._rewind()
        destination_descriptor = -1
        created = False
        try:
            destination_descriptor = os.open(
                destination,
                os.O_WRONLY
                | os.O_CREAT
                | os.O_EXCL
                | getattr(os, "O_NOFOLLOW", 0)
                | getattr(os, "O_CLOEXEC", 0),
                mode,
            )
            created = True
            while True:
                chunk = os.read(self.descriptor, 1024 * 1024)
                if not chunk:
                    break
                remaining = memoryview(chunk)
                while remaining:
                    written = os.write(destination_descriptor, remaining)
                    if written <= 0:
                        raise OSError("release copy made no progress")
                    remaining = remaining[written:]
            os.fsync(destination_descriptor)
            self._verify_unchanged()
            os.fchmod(destination_descriptor, mode)
        except BaseException:
            if created:
                try:
                    destination.unlink()
                except FileNotFoundError:
                    pass
            raise
        finally:
            if destination_descriptor >= 0:
                os.close(destination_descriptor)

    def close(self) -> None:
        if self.descriptor >= 0:
            os.close(self.descriptor)
            self.descriptor = -1

    def __enter__(self) -> OpenedRegularFile:
        return self

    def __exit__(self, _exc_type, _exc, _traceback) -> None:
        self.close()


def open_regular_file(path: Path, label: str) -> OpenedRegularFile:
    expanded = path.expanduser().absolute()
    if SAFE_NAME.fullmatch(expanded.name) is None:
        raise ValueError(f"{label} has an unsafe filename: {expanded.name}")
    descriptor = os.open(
        expanded,
        os.O_RDONLY
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NONBLOCK", 0),
    )
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise ValueError(
                f"{label} must be a single-linked regular file: {path}"
            )
        return OpenedRegularFile(expanded, label, descriptor, metadata)
    except BaseException:
        os.close(descriptor)
        raise


def sha256_file(path: Path) -> str:
    with open_regular_file(path, "release digest input") as source:
        return source.sha256()
