import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sddgov.fs_security import remove_owned_at


class FilesystemSecurityTests(unittest.TestCase):
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
