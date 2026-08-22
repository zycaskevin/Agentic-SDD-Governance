import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sddgov.fs_security import (
    canonicalize_platform_path,
    remove_owned_at,
    write_new_regular_file,
)


class FilesystemSecurityTests(unittest.TestCase):
    def test_darwin_canonicalizes_only_fixed_system_aliases(self):
        with patch("sddgov.fs_security.sys.platform", "darwin"):
            self.assertEqual(
                canonicalize_platform_path(Path("/var/folders/zz/result.json")),
                Path("/private/var/folders/zz/result.json"),
            )
            self.assertEqual(
                canonicalize_platform_path(Path("/tmp/result.json")),
                Path("/private/tmp/result.json"),
            )
            self.assertEqual(
                canonicalize_platform_path(Path("/variable/result.json")),
                Path("/variable/result.json"),
            )

    def test_failed_new_file_cleanup_preserves_a_replacement_generation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "result.json"
            owned = root / "owned-generation.json"
            replacement = b"replacement generation\n"
            real_fsync = os.fsync
            real_rename = os.rename
            real_stat = os.stat
            state = {"failed": False, "swapped": False}

            def swap_generation(directory_fd: int) -> None:
                real_rename(
                    output.name,
                    owned.name,
                    src_dir_fd=directory_fd,
                    dst_dir_fd=directory_fd,
                )
                replacement_fd = os.open(
                    output.name,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                    0o600,
                    dir_fd=directory_fd,
                )
                try:
                    os.write(replacement_fd, replacement)
                    real_fsync(replacement_fd)
                finally:
                    os.close(replacement_fd)
                state["swapped"] = True

            def fail_first_regular_file_fsync(descriptor: int) -> None:
                metadata = os.fstat(descriptor)
                if stat.S_ISREG(metadata.st_mode) and not state["failed"]:
                    state["failed"] = True
                    raise OSError("synthetic write failure")
                real_fsync(descriptor)

            def swap_before_path_stat(
                path: str,
                *,
                dir_fd: int | None = None,
                follow_symlinks: bool = True,
            ):
                metadata = real_stat(
                    path, dir_fd=dir_fd, follow_symlinks=follow_symlinks
                )
                if path == output.name and dir_fd is not None and not state["swapped"]:
                    swap_generation(dir_fd)
                return metadata

            def swap_before_cleanup_rename(
                source: str,
                destination: str,
                *,
                src_dir_fd: int | None = None,
                dst_dir_fd: int | None = None,
            ) -> None:
                if (
                    source == output.name
                    and ".cleanup-pending-" in destination
                    and src_dir_fd is not None
                    and not state["swapped"]
                ):
                    swap_generation(src_dir_fd)
                real_rename(
                    source,
                    destination,
                    src_dir_fd=src_dir_fd,
                    dst_dir_fd=dst_dir_fd,
                )

            with patch(
                "sddgov.fs_security.os.fsync",
                side_effect=fail_first_regular_file_fsync,
            ), patch(
                "sddgov.fs_security.os.stat", side_effect=swap_before_path_stat
            ), patch(
                "sddgov.fs_security.os.rename",
                side_effect=swap_before_cleanup_rename,
            ), self.assertRaisesRegex(OSError, "synthetic write failure"):
                write_new_regular_file(output, b"owned generation\n", "test output")

            self.assertTrue(state["swapped"])
            self.assertEqual(output.read_bytes(), replacement)
            self.assertEqual(owned.read_bytes(), b"owned generation\n")
            self.assertEqual(list(root.glob(".sddgov.cleanup-pending-*")), [])

    def test_directory_cleanup_failure_reports_the_pending_generation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "result").mkdir()
            directory_fd = os.open(
                root,
                os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
            )
            try:
                with patch(
                    "sddgov.fs_security.os.link",
                    side_effect=IsADirectoryError("directory hard links are forbidden"),
                ), self.assertRaisesRegex(
                    ValueError, r"preserved pending generation \.sddgov\.cleanup-pending-"
                ):
                    remove_owned_at(
                        directory_fd,
                        "result",
                        (-1, -1),
                        "synthetic output",
                    )
            finally:
                os.close(directory_fd)

    def test_cleanup_handles_a_leaf_at_the_filesystem_name_limit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            name_max = os.pathconf(root, "PC_NAME_MAX")
            output = root / ("x" * name_max)
            real_fsync = os.fsync
            failed = False

            def fail_first_regular_file_fsync(descriptor: int) -> None:
                nonlocal failed
                metadata = os.fstat(descriptor)
                if stat.S_ISREG(metadata.st_mode) and not failed:
                    failed = True
                    raise OSError("synthetic near-name-max write failure")
                real_fsync(descriptor)

            with patch(
                "sddgov.fs_security.os.fsync",
                side_effect=fail_first_regular_file_fsync,
            ), self.assertRaisesRegex(OSError, "near-name-max write failure"):
                write_new_regular_file(output, b"owned generation\n", "test output")

            self.assertTrue(failed)
            self.assertFalse(output.exists())
            self.assertEqual(list(root.glob(".sddgov.cleanup-pending-*")), [])

    def test_near_name_limit_cleanup_preserves_a_replacement_generation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            name_max = os.pathconf(root, "PC_NAME_MAX")
            output = root / ("x" * name_max)
            owned = root / "owned-generation"
            replacement = b"replacement generation\n"
            real_fsync = os.fsync
            real_rename = os.rename
            failed = False
            swapped = False

            def fail_first_regular_file_fsync(descriptor: int) -> None:
                nonlocal failed
                metadata = os.fstat(descriptor)
                if stat.S_ISREG(metadata.st_mode) and not failed:
                    failed = True
                    raise OSError("synthetic near-name-max write failure")
                real_fsync(descriptor)

            def replace_before_cleanup(
                source: str,
                destination: str,
                *,
                src_dir_fd: int | None = None,
                dst_dir_fd: int | None = None,
            ) -> None:
                nonlocal swapped
                if (
                    source == output.name
                    and ".cleanup-pending-" in destination
                    and src_dir_fd is not None
                    and not swapped
                ):
                    real_rename(
                        output.name,
                        owned.name,
                        src_dir_fd=src_dir_fd,
                        dst_dir_fd=dst_dir_fd,
                    )
                    replacement_fd = os.open(
                        output.name,
                        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                        0o600,
                        dir_fd=src_dir_fd,
                    )
                    try:
                        os.write(replacement_fd, replacement)
                        real_fsync(replacement_fd)
                    finally:
                        os.close(replacement_fd)
                    swapped = True
                real_rename(
                    source,
                    destination,
                    src_dir_fd=src_dir_fd,
                    dst_dir_fd=dst_dir_fd,
                )

            with patch(
                "sddgov.fs_security.os.fsync",
                side_effect=fail_first_regular_file_fsync,
            ), patch(
                "sddgov.fs_security.os.rename",
                side_effect=replace_before_cleanup,
            ), self.assertRaisesRegex(OSError, "near-name-max write failure"):
                write_new_regular_file(output, b"owned generation\n", "test output")

            self.assertTrue(swapped)
            self.assertEqual(output.read_bytes(), replacement)
            self.assertEqual(owned.read_bytes(), b"owned generation\n")

    def test_cleanup_reports_unsupported_descriptor_relative_restore(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            replacement = root / "result"
            replacement.write_text("replacement\n", encoding="utf-8")
            directory_fd = os.open(
                root,
                os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
            )
            try:
                with patch(
                    "sddgov.fs_security.os.link",
                    side_effect=NotImplementedError("linkat unavailable"),
                ), self.assertRaisesRegex(
                    ValueError,
                    r"cleanup could not restore.*preserved pending generation",
                ):
                    remove_owned_at(
                        directory_fd,
                        replacement.name,
                        (-1, -1),
                        "synthetic output",
                    )
            finally:
                os.close(directory_fd)

    def test_file_descriptor_close_failure_cleans_owned_output_without_retry(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "result.json"
            root_identity = (root.stat().st_dev, root.stat().st_ino)
            original_close = os.close
            failed = False

            def close_then_fail(descriptor: int) -> None:
                nonlocal failed
                metadata = os.fstat(descriptor)
                is_output = stat.S_ISREG(metadata.st_mode)
                original_close(descriptor)
                if is_output and not failed:
                    failed = True
                    raise OSError("synthetic output descriptor close failure")

            with patch(
                "sddgov.fs_security.os.close", side_effect=close_then_fail
            ), self.assertRaisesRegex(
                OSError, "output descriptor close failure"
            ) as raised:
                write_new_regular_file(output, b"owned generation\n", "test output")

            self.assertTrue(failed)
            self.assertNotIn("Bad file descriptor", str(raised.exception))
            self.assertFalse(output.exists())
            self.assertEqual(root_identity, (root.stat().st_dev, root.stat().st_ino))

    def test_file_descriptor_close_failure_preserves_close_time_replacement(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "result.json"
            owned = root / "owned-generation.json"
            replacement = b"later generation\n"
            original_close = os.close
            original_rename = os.rename
            failed = False

            def close_then_replace_and_fail(descriptor: int) -> None:
                nonlocal failed
                metadata = os.fstat(descriptor)
                is_output = stat.S_ISREG(metadata.st_mode)
                original_close(descriptor)
                if is_output and not failed:
                    failed = True
                    original_rename(output, owned)
                    output.write_bytes(replacement)
                    raise OSError("synthetic output descriptor close failure")

            with patch(
                "sddgov.fs_security.os.close", side_effect=close_then_replace_and_fail
            ), self.assertRaisesRegex(OSError, "output descriptor close failure"):
                write_new_regular_file(output, b"owned generation\n", "test output")

            self.assertTrue(failed)
            self.assertEqual(output.read_bytes(), replacement)
            self.assertEqual(owned.read_bytes(), b"owned generation\n")
            self.assertEqual(list(root.glob(".sddgov.cleanup-pending-*")), [])

    def test_directory_descriptor_close_failure_after_commit_is_not_retried(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "result.json"
            root_identity = (root.stat().st_dev, root.stat().st_ino)
            original_close = os.close
            failed = False

            def close_then_fail(descriptor: int) -> None:
                nonlocal failed
                metadata = os.fstat(descriptor)
                identity = (metadata.st_dev, metadata.st_ino)
                original_close(descriptor)
                if identity == root_identity and not failed:
                    failed = True
                    raise OSError("synthetic directory descriptor close failure")

            with patch(
                "sddgov.fs_security.os.close", side_effect=close_then_fail
            ):
                write_new_regular_file(output, b"committed generation\n", "test output")

            self.assertTrue(failed)
            self.assertEqual(output.read_bytes(), b"committed generation\n")


if __name__ == "__main__":
    unittest.main()
