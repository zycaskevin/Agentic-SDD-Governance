import errno
import os
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import sddgov.broker as broker_module

from sddgov.broker import (
    BROKER_STAGING_DIRECTORY,
    NonceLedger,
    _open_broker_directories,
    _publish_broker_socket,
    _serve_broker_at,
    _unlink_socket_if_identity,
)


@unittest.skipUnless(
    os.name == "posix" and sys.platform in {"linux", "darwin"},
    "native Broker tests require Linux or macOS",
)
class NativeBrokerTests(unittest.TestCase):
    def setUp(self):
        # Darwin's sockaddr_un.sun_path is short. Keep the native test root
        # deliberately bounded so the test exercises publication semantics,
        # not the host runner's long private temporary-directory prefix.
        self.temporary = tempfile.TemporaryDirectory(prefix="sgb-", dir="/tmp")
        self.root = Path(self.temporary.name)
        probe = self.root / "probe.sock"
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
                server.bind(str(probe))
        except OSError as exc:
            if exc.errno not in {errno.EACCES, errno.EPERM} or os.environ.get("CI"):
                raise
            self.skipTest("local sandbox denies native AF_UNIX bind")
        finally:
            probe.unlink(missing_ok=True)

    def tearDown(self):
        self.temporary.cleanup()

    def _directories(self, socket_path: Path) -> tuple[int, int]:
        return _open_broker_directories(socket_path, owner_uid=os.geteuid())

    def test_candidate_import_comes_from_installed_wheel_when_required(self):
        if os.environ.get("SDDGOV_EXPECT_INSTALLED_WHEEL") != "1":
            self.skipTest("installed-wheel provenance is asserted by native CI")
        checkout_source = Path(__file__).resolve().parents[1] / "src"
        imported = Path(broker_module.__file__).resolve()
        self.assertFalse(imported.is_relative_to(checkout_source))

    def test_fixed_darwin_staging_path_fits_native_limit(self):
        staging = (
            Path("/private/var/db/sddgov")
            / BROKER_STAGING_DIRECTORY
            / ("broker-" + "0" * 32 + ".sock")
        )
        # Darwin reserves one byte for NUL in sockaddr_un.sun_path[104].
        self.assertLessEqual(len(os.fsencode(staging)), 103)

    def _wait_for_health(self, socket_path: Path, process: subprocess.Popen) -> None:
        deadline = time.monotonic() + 10
        last_error = "socket was not published"
        while time.monotonic() < deadline:
            if process.poll() is not None:
                break
            if socket_path.exists():
                try:
                    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                        client.settimeout(1)
                        client.connect(str(socket_path))
                        client.sendall(b'{"action":"health"}\n')
                        client.shutdown(socket.SHUT_WR)
                        self.assertEqual(client.recv(64), b"READY\n")
                    return
                except OSError as exc:
                    last_error = str(exc)
            time.sleep(0.05)
        stdout, stderr = process.communicate(timeout=5)
        self.fail(
            f"native Broker did not become healthy: {last_error}; "
            f"stdout={stdout!r}; stderr={stderr!r}"
        )

    def _start_installed_or_source_broker(
        self, socket_path: Path, state_path: Path
    ) -> subprocess.Popen:
        code = (
            "import os,sys; from pathlib import Path; "
            "from sddgov.broker import NonceLedger,_serve_broker_at; "
            "socket_path=Path(sys.argv[1]); state_path=Path(sys.argv[2]); "
            "ledger=NonceLedger(state_path,expected_uid=os.geteuid(),"
            "validate_parent_chain=False); "
            "_serve_broker_at(socket_path,ledger,os.getgid(),owner_uid=os.geteuid())"
        )
        return subprocess.Popen(
            [sys.executable, "-c", code, str(socket_path), str(state_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def test_bound_descriptor_and_path_are_distinct_socket_inodes(self):
        socket_path = self.root / "identity.sock"
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
            server.bind(str(socket_path))
            descriptor_metadata = os.fstat(server.fileno())
            path_metadata = socket_path.lstat()
        self.assertTrue(stat.S_ISSOCK(descriptor_metadata.st_mode))
        self.assertTrue(stat.S_ISSOCK(path_metadata.st_mode))
        self.assertNotEqual(
            (descriptor_metadata.st_dev, descriptor_metadata.st_ino),
            (path_metadata.st_dev, path_metadata.st_ino),
        )

    def test_first_staging_stat_failure_cleans_stage_and_preserves_final(self):
        socket_path = self.root / "approval.sock"
        parent_descriptor, staging_descriptor = self._directories(socket_path)
        replacement = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        replacement_created = False

        def fail_first_staging_stat(directory: int, name: str):
            nonlocal replacement_created
            if directory == staging_descriptor and name.startswith("broker-"):
                replacement.bind(str(socket_path))
                replacement.listen(1)
                replacement_created = True
                raise OSError("synthetic first staging stat failure")
            return broker_module._stat_at(directory, name)

        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
                with self.assertRaisesRegex(OSError, "first staging stat failure"):
                    _publish_broker_socket(
                        server,
                        socket_path,
                        os.getgid(),
                        owner_uid=os.geteuid(),
                        parent_descriptor=parent_descriptor,
                        staging_descriptor=staging_descriptor,
                        stat_at=fail_first_staging_stat,
                    )
            self.assertTrue(replacement_created)
            self.assertEqual(
                list((self.root / BROKER_STAGING_DIRECTORY).iterdir()), []
            )
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.connect(str(socket_path))
        finally:
            replacement.close()
            socket_path.unlink(missing_ok=True)
            os.close(staging_descriptor)
            os.close(parent_descriptor)

    def test_cleanup_preserves_a_connectable_replacement(self):
        socket_path = self.root / "approval.sock"
        parent_descriptor, staging_descriptor = self._directories(socket_path)
        replacement = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
                identity = _publish_broker_socket(
                    server,
                    socket_path,
                    os.getgid(),
                    owner_uid=os.geteuid(),
                    parent_descriptor=parent_descriptor,
                    staging_descriptor=staging_descriptor,
                )
                socket_path.unlink()
                replacement.bind(str(socket_path))
                replacement.listen(1)
                replacement_identity = socket_path.stat().st_ino
                _unlink_socket_if_identity(
                    parent_descriptor, socket_path.name, identity
                )
                self.assertEqual(socket_path.stat().st_ino, replacement_identity)
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                    client.connect(str(socket_path))
        finally:
            replacement.close()
            socket_path.unlink(missing_ok=True)
            os.close(staging_descriptor)
            os.close(parent_descriptor)

    def test_atomic_publication_race_does_not_clobber_final_socket(self):
        socket_path = self.root / "approval.sock"
        parent_descriptor, staging_descriptor = self._directories(socket_path)
        replacement = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        native_rename = broker_module._exclusive_rename_at

        def publish_after_replacement(*args):
            replacement.bind(str(socket_path))
            replacement.listen(1)
            return native_rename(*args)

        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server, patch(
                "sddgov.broker._exclusive_rename_at",
                side_effect=publish_after_replacement,
            ):
                with self.assertRaises(FileExistsError):
                    _publish_broker_socket(
                        server,
                        socket_path,
                        os.getgid(),
                        owner_uid=os.geteuid(),
                        parent_descriptor=parent_descriptor,
                        staging_descriptor=staging_descriptor,
                    )
            self.assertEqual(
                list((self.root / BROKER_STAGING_DIRECTORY).iterdir()), []
            )
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.connect(str(socket_path))
        finally:
            replacement.close()
            socket_path.unlink(missing_ok=True)
            os.close(staging_descriptor)
            os.close(parent_descriptor)

    def test_real_server_health_signal_cleanup_and_restart(self):
        socket_path = self.root / "approval.sock"
        state_path = self.root / "consumed.jsonl"
        for _ in range(2):
            process = self._start_installed_or_source_broker(socket_path, state_path)
            try:
                self._wait_for_health(socket_path, process)
                process.send_signal(signal.SIGTERM)
                self.assertEqual(process.wait(timeout=10), 0)
                self.assertFalse(socket_path.exists())
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=5)
                process.communicate(timeout=1)

    def test_post_listen_failure_cleans_real_socket_and_allows_restart(self):
        socket_path = self.root / "approval.sock"
        state_path = self.root / "consumed.jsonl"
        ledger = NonceLedger(
            state_path,
            expected_uid=os.geteuid(),
            validate_parent_chain=False,
        )
        with patch(
            "sddgov.broker._serve_requests",
            side_effect=OSError("synthetic post-listen failure"),
        ), self.assertRaisesRegex(OSError, "post-listen failure"):
            _serve_broker_at(
                socket_path,
                ledger,
                os.getgid(),
                owner_uid=os.geteuid(),
            )
        self.assertFalse(socket_path.exists())

        process = self._start_installed_or_source_broker(socket_path, state_path)
        try:
            self._wait_for_health(socket_path, process)
            process.send_signal(signal.SIGTERM)
            self.assertEqual(process.wait(timeout=10), 0)
            self.assertFalse(socket_path.exists())
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
            process.communicate(timeout=1)


if __name__ == "__main__":
    unittest.main()
