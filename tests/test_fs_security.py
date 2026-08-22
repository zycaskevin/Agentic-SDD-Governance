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
                    and destination.startswith(f".{output.name}.cleanup-pending-")
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
            self.assertEqual(list(root.glob(".result.json.cleanup-pending-*")), [])

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
                    ValueError, r"preserved pending generation \.result\.cleanup-pending-"
                ):
                    remove_owned_at(
                        directory_fd,
                        "result",
                        (-1, -1),
                        "synthetic output",
                    )
            finally:
                os.close(directory_fd)


if __name__ == "__main__":
    unittest.main()
