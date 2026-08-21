"""Descriptor-bound regular-file operations for release tooling."""

from __future__ import annotations

import hashlib
import os
import re
import stat
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Callable, Iterator, NoReturn


SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]*$")


def _require_posix_release_files() -> None:
    if os.name != "posix":
        raise ValueError(
            "descriptor-bound release filesystem helpers require Linux or macOS; "
            "Windows is not supported"
        )


def _reraise_after_cleanup(
    primary: BaseException,
    *operations: Callable[[], None],
) -> NoReturn:
    cleanup_error: BaseException | None = None
    for operation in operations:
        try:
            operation()
        except BaseException as exc:
            if cleanup_error is None:
                cleanup_error = exc
    if cleanup_error is not None:
        raise primary.with_traceback(primary.__traceback__) from cleanup_error
    raise primary.with_traceback(primary.__traceback__)


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
    parent_descriptor: int = -1
    entry_name: str | None = None

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
        if self.parent_descriptor >= 0 and self.entry_name is not None:
            try:
                named = os.stat(
                    self.entry_name,
                    dir_fd=self.parent_descriptor,
                    follow_symlinks=False,
                )
            except OSError as exc:
                raise ValueError(
                    f"{self.label} changed after it was opened: {self.path}"
                ) from exc
            if (
                not stat.S_ISREG(named.st_mode)
                or _identity(named) != _identity(self.initial_metadata)
            ):
                raise ValueError(
                    f"{self.label} changed after it was opened: {self.path}"
                )

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
        with open_directory(
            destination.parent, "release destination directory"
        ) as directory:
            self.copy_to_at(directory, destination.name, mode=mode)

    def copy_to_at(
        self,
        destination: OpenedDirectory,
        name: str,
        *,
        mode: int = 0o644,
    ) -> None:
        self._rewind()
        destination.write_from_descriptor(name, self.descriptor, mode=mode)
        self._verify_unchanged()

    def close(self) -> None:
        if self.descriptor >= 0:
            os.close(self.descriptor)
            self.descriptor = -1
        if self.parent_descriptor >= 0:
            os.close(self.parent_descriptor)
            self.parent_descriptor = -1

    def __enter__(self) -> OpenedRegularFile:
        return self

    def __exit__(self, _exc_type, _exc, _traceback) -> None:
        self.close()


def _safe_direct_name(name: str, label: str) -> None:
    if SAFE_NAME.fullmatch(name) is None:
        raise ValueError(f"{label} has an unsafe filename: {name}")


@dataclass
class OpenedDirectory:
    """One directory generation retained for all release operations."""

    path: Path
    label: str
    descriptor: int

    def _verify_directory(self) -> None:
        metadata = os.fstat(self.descriptor)
        if not stat.S_ISDIR(metadata.st_mode):
            raise ValueError(f"{self.label} is no longer a directory")

    def names(self) -> list[str]:
        self._verify_directory()
        names = sorted(os.listdir(self.descriptor))
        for name in names:
            _safe_direct_name(name, f"entry in {self.label}")
        return names

    def open_regular_file(self, name: str, label: str) -> OpenedRegularFile:
        _safe_direct_name(name, label)
        self._verify_directory()
        descriptor = os.open(
            name,
            os.O_RDONLY
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NONBLOCK", 0),
            dir_fd=self.descriptor,
        )
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                raise ValueError(
                    f"{label} must be a single-linked regular file: {self.path / name}"
                )
            return OpenedRegularFile(
                self.path / name,
                label,
                descriptor,
                metadata,
                os.dup(self.descriptor),
                name,
            )
        except BaseException:
            os.close(descriptor)
            raise

    def open_directory(self, name: str, label: str) -> OpenedDirectory:
        _safe_direct_name(name, label)
        descriptor = os.open(
            name,
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
            dir_fd=self.descriptor,
        )
        metadata = os.fstat(descriptor)
        if not stat.S_ISDIR(metadata.st_mode):
            os.close(descriptor)
            raise ValueError(f"{label} must be a directory")
        return OpenedDirectory(self.path / name, label, descriptor)

    def make_directory(
        self, name: str, label: str, *, mode: int = 0o755
    ) -> OpenedDirectory:
        _safe_direct_name(name, label)
        self._verify_directory()
        os.mkdir(name, mode=mode, dir_fd=self.descriptor)
        os.fsync(self.descriptor)
        return self.open_directory(name, label)

    def open_relative_regular_file(
        self, relative: Path, label: str
    ) -> OpenedRegularFile:
        parts = relative.parts
        if (
            not parts
            or relative.is_absolute()
            or any(part in {"", ".", ".."} for part in parts)
        ):
            raise ValueError(f"{label} has an unsafe relative path: {relative}")
        current: OpenedDirectory = self
        opened: list[OpenedDirectory] = []
        try:
            for part in parts[:-1]:
                child = current.open_directory(part, f"directory for {label}")
                opened.append(child)
                current = child
            return current.open_regular_file(parts[-1], label)
        finally:
            for directory in reversed(opened):
                directory.close()

    def regular_file_inventory(self, prefix: Path = Path()) -> list[Path]:
        """Recursively inventory only safe single-linked regular files."""
        inventory: list[Path] = []
        for name in self.names():
            metadata = os.stat(name, dir_fd=self.descriptor, follow_symlinks=False)
            relative = prefix / name
            if stat.S_ISLNK(metadata.st_mode):
                raise ValueError(
                    f"release directory must not contain symlinks: {relative}"
                )
            if stat.S_ISDIR(metadata.st_mode):
                with self.open_directory(name, "release inventory directory") as child:
                    inventory.extend(child.regular_file_inventory(relative))
                continue
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                raise ValueError(
                    "release directory must contain only single-linked regular files: "
                    f"{relative}"
                )
            inventory.append(relative)
        return inventory

    def _new_file_descriptor(
        self, name: str, mode: int, *, readable: bool = False
    ) -> int:
        _safe_direct_name(name, f"release output in {self.label}")
        self._verify_directory()
        return os.open(
            name,
            (os.O_RDWR if readable else os.O_WRONLY)
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
            mode,
            dir_fd=self.descriptor,
        )

    def _remove_owned(self, name: str, identity: tuple[int, int]) -> None:
        try:
            current = os.stat(name, dir_fd=self.descriptor, follow_symlinks=False)
        except FileNotFoundError:
            return
        if (current.st_dev, current.st_ino) != identity:
            raise ValueError(
                f"release output changed during cleanup; preserved later writer: {name}"
            )
        os.unlink(name, dir_fd=self.descriptor)
        os.fsync(self.descriptor)

    def _verify_owned(self, name: str, identity: tuple[int, int]) -> None:
        try:
            current = os.stat(name, dir_fd=self.descriptor, follow_symlinks=False)
        except OSError as exc:
            raise ValueError(f"release output changed during write: {name}") from exc
        if (
            not stat.S_ISREG(current.st_mode)
            or current.st_nlink != 1
            or (current.st_dev, current.st_ino) != identity
        ):
            raise ValueError(f"release output changed during write: {name}")

    def write_from_descriptor(
        self, name: str, source_descriptor: int, *, mode: int = 0o644
    ) -> None:
        destination_descriptor = self._new_file_descriptor(name, mode)
        metadata = os.fstat(destination_descriptor)
        identity = (metadata.st_dev, metadata.st_ino)
        try:
            while True:
                chunk = os.read(source_descriptor, 1024 * 1024)
                if not chunk:
                    break
                remaining = memoryview(chunk)
                while remaining:
                    written = os.write(destination_descriptor, remaining)
                    if written <= 0:
                        raise OSError("release copy made no progress")
                    remaining = remaining[written:]
            os.fsync(destination_descriptor)
            os.fchmod(destination_descriptor, mode)
            self._verify_owned(name, identity)
        except BaseException as primary:
            _reraise_after_cleanup(
                primary,
                lambda: self._remove_owned(name, identity),
                lambda: os.close(destination_descriptor),
            )
        else:
            os.close(destination_descriptor)

    def write_bytes(self, name: str, value: bytes, *, mode: int = 0o644) -> None:
        descriptor = self._new_file_descriptor(name, mode)
        metadata = os.fstat(descriptor)
        identity = (metadata.st_dev, metadata.st_ino)
        try:
            remaining = memoryview(value)
            while remaining:
                written = os.write(descriptor, remaining)
                if written <= 0:
                    raise OSError("release output write made no progress")
                remaining = remaining[written:]
            os.fsync(descriptor)
            os.fchmod(descriptor, mode)
            self._verify_owned(name, identity)
        except BaseException as primary:
            _reraise_after_cleanup(
                primary,
                lambda: self._remove_owned(name, identity),
                lambda: os.close(descriptor),
            )
        else:
            os.close(descriptor)

    @contextmanager
    def binary_writer(
        self, name: str, *, mode: int = 0o644
    ) -> Iterator[BinaryIO]:
        descriptor = self._new_file_descriptor(name, mode, readable=True)
        metadata = os.fstat(descriptor)
        identity = (metadata.st_dev, metadata.st_ino)
        try:
            with os.fdopen(descriptor, "w+b", closefd=False) as handle:
                yield handle
                handle.flush()
                os.fsync(descriptor)
                os.fchmod(descriptor, mode)
                self._verify_owned(name, identity)
        except BaseException as primary:
            _reraise_after_cleanup(
                primary,
                lambda: os.close(descriptor),
                lambda: self._remove_owned(name, identity),
            )
        else:
            os.close(descriptor)

    def close(self) -> None:
        if self.descriptor >= 0:
            os.close(self.descriptor)
            self.descriptor = -1

    def __enter__(self) -> OpenedDirectory:
        return self

    def __exit__(self, _exc_type, _exc, _traceback) -> None:
        self.close()


def _absolute_without_symlink_resolution(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path.expanduser())))


def open_directory(
    path: Path,
    label: str,
    *,
    create: bool = False,
    mode: int = 0o755,
) -> OpenedDirectory:
    """Open one POSIX directory generation without following path symlinks.

    ``create=True`` creates only the final component. Every parent must already
    exist so release tooling cannot silently widen its output scope.
    """
    _require_posix_release_files()
    expanded = _absolute_without_symlink_resolution(path)
    flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0)
    )
    descriptor = os.open(expanded.anchor or os.sep, flags)
    try:
        parts = expanded.parts[1:] if expanded.anchor else expanded.parts
        for index, part in enumerate(parts):
            if part in {"", ".", ".."}:
                raise ValueError(f"{label} has an unsafe path component")
            final = index == len(parts) - 1
            if create and final:
                try:
                    os.mkdir(part, mode=mode, dir_fd=descriptor)
                    os.fsync(descriptor)
                except FileExistsError:
                    pass
            next_descriptor = os.open(part, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
        metadata = os.fstat(descriptor)
        if not stat.S_ISDIR(metadata.st_mode):
            raise ValueError(f"{label} must be a directory")
        return OpenedDirectory(expanded, label, descriptor)
    except BaseException:
        os.close(descriptor)
        raise


def open_regular_file(path: Path, label: str) -> OpenedRegularFile:
    expanded = _absolute_without_symlink_resolution(path)
    with open_directory(expanded.parent, f"parent directory for {label}") as parent:
        return parent.open_regular_file(expanded.name, label)


def sha256_file(path: Path) -> str:
    with open_regular_file(path, "release digest input") as source:
        return source.sha256()
