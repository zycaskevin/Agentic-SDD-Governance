import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sddgov.fs_security as fs_security
from sddgov.fs_security import (
    canonicalize_platform_path,
    exclusive_rename_at,
    remove_owned_at,
    write_new_regular_file,
)


class FilesystemSecurityTests(unittest.TestCase):
    def test_new_file_parent_lease_failure_removes_only_owned_generation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "out" / "receipt.json"
            parked = root / "parked-out"
            replacement = b"later writer\n"
            real_require = fs_security.require_directory_path_identity
            swapped = False

            def replace_parent(path, descriptor, label):
                nonlocal swapped
                if not swapped:
                    output.parent.rename(parked)
                    output.parent.mkdir()
                    output.write_bytes(replacement)
                    swapped = True
                real_require(path, descriptor, label)

            with (
                patch(
                    "sddgov.fs_security.require_directory_path_identity",
                    side_effect=replace_parent,
                ),
                self.assertRaisesRegex(ValueError, "changed during operation"),
            ):
                write_new_regular_file(output, b"owned receipt\n", "test receipt")

            self.assertTrue(swapped)
            self.assertEqual(output.read_bytes(), replacement)
            self.assertFalse((parked / output.name).exists())

    def test_new_file_final_leaf_recheck_preserves_replacement(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "receipt.json"
            owned = root / "owned-receipt.json"
            replacement = b"later writer\n"
            real_require = fs_security.require_directory_path_identity
            swapped = False

            def replace_leaf_after_parent_recheck(path, descriptor, label):
                nonlocal swapped
                real_require(path, descriptor, label)
                if not swapped:
                    output.rename(owned)
                    output.write_bytes(replacement)
                    swapped = True

            with (
                patch(
                    "sddgov.fs_security.require_directory_path_identity",
                    side_effect=replace_leaf_after_parent_recheck,
                ),
                self.assertRaisesRegex(ValueError, "changed before path publication"),
            ):
                write_new_regular_file(output, b"owned receipt\n", "test receipt")

            self.assertTrue(swapped)
            self.assertEqual(output.read_bytes(), replacement)
            self.assertEqual(owned.read_bytes(), b"owned receipt\n")

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
                canonicalize_platform_path(Path("/etc/sddgov/trusted.json")),
                Path("/private/etc/sddgov/trusted.json"),
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

            def swap_before_cleanup_rename(
                source_directory: int,
                source: str,
                destination_directory: int,
                destination: str,
            ) -> None:
                if (
                    source == output.name
                    and ".cleanup-pending-" in destination
                    and not state["swapped"]
                ):
                    swap_generation(source_directory)
                exclusive_rename_at(
                    source_directory,
                    source,
                    destination_directory,
                    destination,
                )

            with patch(
                "sddgov.fs_security.os.fsync",
                side_effect=fail_first_regular_file_fsync,
            ), patch(
                "sddgov.fs_security.exclusive_rename_at",
                side_effect=swap_before_cleanup_rename,
            ), self.assertRaisesRegex(OSError, "synthetic write failure"):
                write_new_regular_file(output, b"owned generation\n", "test output")

            self.assertTrue(state["swapped"])
            self.assertEqual(output.read_bytes(), replacement)
            self.assertEqual(owned.read_bytes(), b"owned generation\n")
            self.assertEqual(list(root.glob(".sddgov.cleanup-pending-*")), [])

    def test_directory_cleanup_restores_an_unowned_generation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "result").mkdir()
            directory_fd = os.open(
                root,
                os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
            )
            try:
                removed = remove_owned_at(
                    directory_fd,
                    "result",
                    (-1, -1),
                    "synthetic output",
                )
                self.assertFalse(removed)
                self.assertTrue((root / "result").is_dir())
                self.assertEqual(list(root.glob(".sddgov.cleanup-pending-*")), [])
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
                source_directory: int,
                source: str,
                destination_directory: int,
                destination: str,
            ) -> None:
                nonlocal swapped
                if (
                    source == output.name
                    and ".cleanup-pending-" in destination
                    and not swapped
                ):
                    real_rename(
                        output.name,
                        owned.name,
                        src_dir_fd=source_directory,
                        dst_dir_fd=source_directory,
                    )
                    replacement_fd = os.open(
                        output.name,
                        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                        0o600,
                        dir_fd=source_directory,
                    )
                    try:
                        os.write(replacement_fd, replacement)
                        real_fsync(replacement_fd)
                    finally:
                        os.close(replacement_fd)
                    swapped = True
                exclusive_rename_at(
                    source_directory,
                    source,
                    destination_directory,
                    destination,
                )

            with patch(
                "sddgov.fs_security.os.fsync",
                side_effect=fail_first_regular_file_fsync,
            ), patch(
                "sddgov.fs_security.exclusive_rename_at",
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
                calls = 0

                def fail_restore(source_fd, source, destination_fd, destination):
                    nonlocal calls
                    calls += 1
                    if calls == 2:
                        raise NotImplementedError("exclusive restore unavailable")
                    exclusive_rename_at(
                        source_fd,
                        source,
                        destination_fd,
                        destination,
                    )

                with patch(
                    "sddgov.fs_security.exclusive_rename_at",
                    side_effect=fail_restore,
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

    def test_cleanup_retries_a_private_name_collision_without_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "result"
            target.write_text("owned\n", encoding="utf-8")
            metadata = target.stat()
            first_token = "a" * 32
            second_token = "b" * 32
            collision = root / f".sddgov.cleanup-pending-{first_token}"
            collision.write_text("later writer\n", encoding="utf-8")
            directory_fd = os.open(
                root,
                os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
            )
            try:
                with patch(
                    "sddgov.fs_security.secrets.token_hex",
                    side_effect=[first_token, second_token],
                ):
                    removed = remove_owned_at(
                        directory_fd,
                        target.name,
                        (metadata.st_dev, metadata.st_ino),
                        "synthetic output",
                        expected_size=metadata.st_size,
                        expected_digest="33bff9108736f23280e9cd50cb1472e3a5b4403ed3f2da1fe67b8487a4fb75c6",
                    )
            finally:
                os.close(directory_fd)
            self.assertTrue(removed)
            self.assertFalse(target.exists())
            self.assertEqual(collision.read_text(encoding="utf-8"), "later writer\n")
            self.assertFalse((root / f".sddgov.cleanup-pending-{second_token}").exists())

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
