import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.benchmark_monorepo_rollback import main as benchmark_main
from scripts.benchmark_monorepo_rollback import run_benchmark
from scripts.benchmark_monorepo_rollback import setup_timeout_seconds


class MonorepoRollbackBenchmarkTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("git"), "git is required for the benchmark smoke")
    def test_small_smoke_preserves_exact_proof_and_claim_boundary(self):
        report = run_benchmark([25], 1)
        case = report["cases"][0]
        self.assertTrue(case["all_proofs_passed"], report)
        self.assertFalse(report["claim_allowed"])
        self.assertFalse(report["decision"]["optimize_required"], report)
        self.assertEqual(
            report["decision"]["action"],
            "retain full-tree proof; no affected-path optimization",
        )

    def test_cli_rejects_caller_selected_threshold(self):
        root = Path(__file__).resolve().parents[1]
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/benchmark_monorepo_rollback.py",
                "--file-counts",
                "1",
                "--repeats",
                "1",
                "--threshold-seconds",
                "inf",
            ],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(completed.returncode, 2, completed)
        self.assertIn("error: unrecognized arguments:", completed.stderr)
        self.assertIn("--threshold-seconds inf", completed.stderr)

    def test_proof_failure_is_a_correctness_failure_not_an_optimization_signal(self):
        with patch(
            "scripts.benchmark_monorepo_rollback._case",
            return_value={
                "file_count": 25,
                "changed_file_count": 1,
                "repeats": 1,
                "all_proofs_passed": False,
                "setup_seconds": 0.1,
                "samples_seconds": [0.1],
                "median_seconds": 0.1,
                "p95_seconds": 0.1,
            },
        ):
            report = run_benchmark([25], 1)

        self.assertEqual(report["decision"]["state"], "proof_failure")
        self.assertFalse(report["decision"]["optimize_required"])
        self.assertIn("correctness", report["decision"]["action"])

    def test_cli_writes_json_report_when_benchmark_execution_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "nested/result.json"
            with patch(
                "scripts.benchmark_monorepo_rollback._case",
                side_effect=RuntimeError("/tmp/private Benchmark/input escaped"),
            ), patch(
                "sys.argv",
                [
                    "benchmark_monorepo_rollback.py",
                    "--file-counts",
                    "1",
                    "--repeats",
                    "1",
                    "--output",
                    str(output),
                ],
            ), redirect_stdout(StringIO()):
                status = benchmark_main()

            self.assertEqual(status, 1)
            report = output.read_text(encoding="utf-8")
            self.assertIn('"state": "benchmark_error"', report)
            self.assertIn("benchmark execution failed (RuntimeError)", report)
            self.assertNotIn("/tmp/private Benchmark", report)
            self.assertNotIn("input escaped", report)
            document = json.loads(report)
            self.assertIn("environment", document)
            self.assertIn("threshold_seconds_p95", document)
            self.assertIn("note", document)

    def test_cli_rejects_a_leaf_symlink_without_overwriting_its_target(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            victim = root / "victim.json"
            victim.write_text("keep me\n", encoding="utf-8")
            output = root / "report.json"
            output.symlink_to(victim)
            stderr = StringIO()
            with patch(
                "scripts.benchmark_monorepo_rollback.run_benchmark",
                return_value={"decision": {"state": "retain_full_tree"}},
            ), patch(
                "sys.argv",
                ["benchmark_monorepo_rollback.py", "--output", str(output)],
            ), redirect_stdout(StringIO()), redirect_stderr(stderr):
                status = benchmark_main()

            self.assertEqual(status, 1)
            self.assertEqual(stderr.getvalue(), "benchmark report write failed\n")
            self.assertTrue(output.is_symlink())
            self.assertEqual(victim.read_text(encoding="utf-8"), "keep me\n")

    def test_cli_rejects_a_symlinked_parent_without_writing_outside(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            outside = root / "outside"
            outside.mkdir()
            alias = root / "alias"
            alias.symlink_to(outside, target_is_directory=True)
            output = alias / "report.json"
            stderr = StringIO()
            with patch(
                "scripts.benchmark_monorepo_rollback.run_benchmark",
                return_value={"decision": {"state": "retain_full_tree"}},
            ), patch(
                "sys.argv",
                ["benchmark_monorepo_rollback.py", "--output", str(output)],
            ), redirect_stdout(StringIO()), redirect_stderr(stderr):
                status = benchmark_main()

            self.assertEqual(status, 1)
            self.assertEqual(stderr.getvalue(), "benchmark report write failed\n")
            self.assertFalse((outside / "report.json").exists())

    def test_git_version_probe_has_a_bounded_timeout(self):
        passing_case = {
            "file_count": 1,
            "changed_file_count": 1,
            "repeats": 1,
            "all_proofs_passed": True,
            "setup_seconds": 0.1,
            "samples_seconds": [0.1],
            "median_seconds": 0.1,
            "p95_seconds": 0.1,
        }
        with patch(
            "scripts.benchmark_monorepo_rollback._case", return_value=passing_case
        ), patch(
            "scripts.benchmark_monorepo_rollback.subprocess.run",
            return_value=SimpleNamespace(stdout="git version synthetic\n"),
        ) as run:
            run_benchmark([1], 1)
        self.assertEqual(run.call_args.kwargs["timeout"], 30)

    def test_large_fixture_setup_timeout_scales_beyond_the_small_default(self):
        self.assertEqual(setup_timeout_seconds(1), 180)
        self.assertGreater(setup_timeout_seconds(50_000), 180)


if __name__ == "__main__":
    unittest.main()
