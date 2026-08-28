import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.release_validation import read_bounded_git_blob
from scripts.verify_release_source import verify_release_source


READINESS_SHA = "a" * 40
VERIFIER_SHA = "b" * 40
ROOT = Path(__file__).resolve().parents[1]


class _Result:
    def __init__(self, stdout=""):
        self.stdout = stdout


class _Pipe:
    def __init__(self):
        self.closed = False

    def fileno(self):
        return 9

    def close(self):
        self.closed = True


class _Process:
    def __init__(self):
        self.stdout = _Pipe()
        self.killed = False
        self.wait_timeouts = []

    def poll(self):
        return None

    def kill(self):
        self.killed = True

    def wait(self, *, timeout):
        self.wait_timeouts.append(timeout)
        return 0


class _Selector:
    def register(self, *_args):
        return None

    def select(self, _timeout):
        return [object()]

    def close(self):
        return None


class ReleaseSourceTests(unittest.TestCase):
    def test_elapsed_deadline_after_eof_stops_and_reaps_git_child(self):
        process = _Process()
        with patch(
            "scripts.release_validation.subprocess.Popen", return_value=process
        ), patch(
            "scripts.release_validation.selectors.DefaultSelector",
            return_value=_Selector(),
        ), patch(
            "scripts.release_validation.os.read", side_effect=[b"notes", b""]
        ), patch(
            "scripts.release_validation.time.monotonic",
            side_effect=[0.0, 0.0, 0.0, 31.0],
        ):
            with self.assertRaisesRegex(ValueError, "time limit"):
                read_bounded_git_blob(
                    ROOT,
                    "HEAD:RELEASE_NOTES.md",
                    timeout_seconds=30,
                )
        self.assertTrue(process.killed)
        self.assertEqual(process.wait_timeouts, [5])
        self.assertTrue(process.stdout.closed)

    def test_release_notes_git_blob_is_bounded_while_reading(self):
        expected = subprocess.run(
            ["git", "-C", str(ROOT), "show", "HEAD:RELEASE_NOTES.md"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=10,
        ).stdout
        self.assertEqual(
            read_bounded_git_blob(
                ROOT,
                "HEAD:RELEASE_NOTES.md",
                maximum_bytes=len(expected),
                timeout_seconds=10,
            ),
            expected,
        )
        with self.assertRaisesRegex(ValueError, "byte limit"):
            read_bounded_git_blob(
                ROOT,
                "HEAD:RELEASE_NOTES.md",
                maximum_bytes=len(expected) - 1,
                timeout_seconds=10,
            )

    def _runner(self, *, head=VERIFIER_SHA, tag=READINESS_SHA, ancestry_ok=True):
        calls = []
        options = []

        def run(command, **kwargs):
            calls.append(command)
            options.append(kwargs)
            if command[3:] == ["rev-parse", "HEAD"]:
                return _Result(head + "\n")
            if command[3:] == ["rev-list", "-n", "1", "refs/tags/v0.2.0rc1"]:
                return _Result(tag + "\n")
            if command[3:5] == ["merge-base", "--is-ancestor"] and not ancestry_ok:
                raise subprocess.CalledProcessError(1, command)
            return _Result()

        return run, calls, options

    def test_refreshes_exact_tag_and_branch_before_accepting_source(self):
        run, calls, options = self._runner()
        verify_release_source(
            Path("trusted"),
            remote="origin",
            default_branch="main",
            release_tag="v0.2.0rc1",
            readiness_sha=READINESS_SHA,
            trusted_verifier_sha=VERIFIER_SHA,
            runner=run,
        )
        self.assertIn(
            [
                "git",
                "-C",
                "trusted",
                "fetch",
                "--force",
                "--no-tags",
                "origin",
                "+refs/tags/v0.2.0rc1:refs/tags/v0.2.0rc1",
            ],
            calls,
        )
        self.assertTrue(options)
        self.assertTrue(all(row["timeout"] == 10 for row in options))
        self.assertTrue(all(row["stderr"] == subprocess.DEVNULL for row in options))
        for command, option in zip(calls, options):
            if command[3:5] in (["rev-parse", "HEAD"], ["rev-list", "-n"]):
                self.assertEqual(option["stdout"], subprocess.PIPE)
            else:
                self.assertEqual(option["stdout"], subprocess.DEVNULL)
        self.assertIn(
            [
                "git",
                "-C",
                "trusted",
                "fetch",
                "--force",
                "--no-tags",
                "origin",
                "+refs/heads/main:refs/remotes/origin/main",
            ],
            calls,
        )

    def test_rejects_a_changed_verifier_or_tag_and_uncontained_readiness(self):
        scenarios = (
            ({"head": "c" * 40}, "trusted verifier"),
            ({"tag": "c" * 40}, "release tag"),
            ({"ancestry_ok": False}, "default branch"),
        )
        for runner_args, message in scenarios:
            with self.subTest(runner_args=runner_args):
                run, _calls, _options = self._runner(**runner_args)
                with self.assertRaisesRegex(ValueError, message):
                    verify_release_source(
                        Path("trusted"),
                        remote="origin",
                        default_branch="main",
                        release_tag="v0.2.0rc1",
                        readiness_sha=READINESS_SHA,
                        trusted_verifier_sha=VERIFIER_SHA,
                        runner=run,
                    )

    def test_rejects_ref_or_sha_injection(self):
        run, _calls, _options = self._runner()
        for field, value in (
            ("default_branch", "--upload-pack=evil"),
            ("release_tag", "../escape"),
            ("readiness_sha", "main"),
            ("trusted_verifier_sha", "HEAD"),
        ):
            with self.subTest(field=field):
                arguments = {
                    "remote": "origin",
                    "default_branch": "main",
                    "release_tag": "v0.2.0rc1",
                    "readiness_sha": READINESS_SHA,
                    "trusted_verifier_sha": VERIFIER_SHA,
                    "runner": run,
                }
                arguments[field] = value
                with self.assertRaises(ValueError):
                    verify_release_source(Path("trusted"), **arguments)

    def test_git_timeout_fails_closed(self):
        def timed_out(command, **kwargs):
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])

        with self.assertRaisesRegex(ValueError, "refresh or verification failed"):
            verify_release_source(
                Path("trusted"),
                remote="origin",
                default_branch="main",
                release_tag="v0.2.0rc1",
                readiness_sha=READINESS_SHA,
                trusted_verifier_sha=VERIFIER_SHA,
                runner=timed_out,
            )

    def test_oversized_inputs_stop_before_git_execution(self):
        cases = (
            (Path("r" * 4097), "origin", "main", "v0.2.0rc1"),
            (Path("trusted"), "r" * 101, "main", "v0.2.0rc1"),
            (Path("trusted"), "origin", "m" * 256, "v0.2.0rc1"),
            (Path("trusted"), "origin", "main", "v" + "x" * 255),
        )
        for repository, remote, branch, tag in cases:
            with self.subTest(remote=remote, branch=branch, tag=tag):
                run, calls, _options = self._runner()
                with self.assertRaises(ValueError):
                    verify_release_source(
                        repository,
                        remote=remote,
                        default_branch=branch,
                        release_tag=tag,
                        readiness_sha=READINESS_SHA,
                        trusted_verifier_sha=VERIFIER_SHA,
                        runner=run,
                    )
                self.assertEqual(calls, [])

    def test_git_ref_output_is_bounded(self):
        def noisy(_command, **_kwargs):
            return _Result("x" * 129)

        with self.assertRaisesRegex(ValueError, "bounded size"):
            verify_release_source(
                Path("trusted"),
                remote="origin",
                default_branch="main",
                release_tag="v0.2.0rc1",
                readiness_sha=READINESS_SHA,
                trusted_verifier_sha=VERIFIER_SHA,
                runner=noisy,
            )


if __name__ == "__main__":
    unittest.main()
