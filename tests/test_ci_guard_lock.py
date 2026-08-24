from __future__ import annotations

import fcntl
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

from sddgov import ci_guard

from test_ci_guard import GOOD_WORKFLOW, _contract, _write_project


class LocalGateLockTests(unittest.TestCase):
    def test_lock_serializes_competing_processes(self):
        probe = (
            "import fcntl, os, sys; "
            "fd=os.open(sys.argv[1], os.O_RDWR|os.O_CLOEXEC|os.O_NOFOLLOW); "
            "status='unexpected'; "
            "\ntry: fcntl.flock(fd, fcntl.LOCK_EX|fcntl.LOCK_NB)"
            "\nexcept BlockingIOError: status='blocked'"
            "\nif status != 'blocked':"
            "\n fcntl.flock(fd, fcntl.LOCK_UN); os.close(fd); raise SystemExit(73)"
            "\nprint(status, flush=True); "
            "fcntl.flock(fd, fcntl.LOCK_EX); "
            "print('acquired', flush=True); "
            "fcntl.flock(fd, fcntl.LOCK_UN); "
            "os.close(fd)"
        )
        with tempfile.TemporaryDirectory() as temporary:
            runtime_root = Path(temporary)
            child = None
            try:
                with ci_guard._local_gate_lock(runtime_root=runtime_root) as lock_path:
                    child = subprocess.Popen(
                        [sys.executable, "-c", probe, os.fspath(lock_path)],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                    )
                    self.assertIsNotNone(child.stdout)
                    self.assertEqual(child.stdout.readline().strip(), "blocked")

                stdout, stderr = child.communicate(timeout=5)
                self.assertEqual(child.returncode, 0, stderr)
                self.assertEqual(stdout.strip(), "acquired")
            finally:
                if child is not None and child.poll() is None:
                    child.kill()
                    child.wait(timeout=5)

    def test_run_local_gate_enters_lock_before_verification_and_commands(self):
        events = []

        @contextmanager
        def locked():
            events.append("enter")
            try:
                yield Path("$LOCAL_GATE_LOCK")
            finally:
                events.append("exit")

        def verify(_root: Path):
            events.append("verify")
            return {"ok": True, "errors": []}

        def run(*_args, **_kwargs):
            events.append("command")
            return type("Completed", (), {"returncode": 0})()

        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            _write_project(
                project,
                _contract([sys.executable, "-c", "pass"]),
                GOOD_WORKFLOW,
            )
            with (
                mock.patch.object(ci_guard, "_local_gate_lock", locked),
                mock.patch.object(ci_guard, "verify_guard", verify),
                mock.patch.object(ci_guard.subprocess, "run", run),
            ):
                result = ci_guard.run_local_gate(project)

        self.assertTrue(result["ok"])
        self.assertEqual(events, ["enter", "verify", "command", "exit"])

    def test_lock_rejects_a_symbolic_link_record(self):
        with tempfile.TemporaryDirectory() as temporary:
            runtime_root = Path(temporary)
            lock_directory = runtime_root / (
                f"{ci_guard.LOCAL_GATE_LOCK_DIRECTORY_PREFIX}{os.getuid()}"
            )
            lock_directory.mkdir(mode=0o700)
            target = runtime_root / "outside-lock"
            target.touch(mode=0o600)
            (lock_directory / ci_guard.LOCAL_GATE_LOCK_NAME).symlink_to(target)

            with self.assertRaises(OSError):
                with ci_guard._local_gate_lock(runtime_root=runtime_root):
                    self.fail("symbolic lock record entered the critical section")

    def test_lock_rejects_a_permissive_coordination_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            runtime_root = Path(temporary)
            lock_directory = runtime_root / (
                f"{ci_guard.LOCAL_GATE_LOCK_DIRECTORY_PREFIX}{os.getuid()}"
            )
            lock_directory.mkdir(mode=0o700)
            lock_directory.chmod(0o750)

            with self.assertRaisesRegex(ValueError, "owner-only"):
                with ci_guard._local_gate_lock(runtime_root=runtime_root):
                    self.fail("permissive lock directory entered the critical section")

    def test_lock_is_released_after_an_inner_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            runtime_root = Path(temporary)
            with self.assertRaisesRegex(RuntimeError, "synthetic gate failure"):
                with ci_guard._local_gate_lock(runtime_root=runtime_root) as lock_path:
                    raise RuntimeError("synthetic gate failure")

            competing_fd = os.open(
                lock_path,
                os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW,
            )
            try:
                fcntl.flock(competing_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(competing_fd, fcntl.LOCK_UN)
            finally:
                os.close(competing_fd)


if __name__ == "__main__":
    unittest.main()
