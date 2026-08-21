import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.benchmark_monorepo_rollback import main as benchmark_main
from scripts.benchmark_monorepo_rollback import run_benchmark


class MonorepoRollbackBenchmarkTests(unittest.TestCase):
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
                side_effect=RuntimeError("synthetic benchmark failure"),
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
            ):
                status = benchmark_main()

            self.assertEqual(status, 1)
            report = output.read_text(encoding="utf-8")
            self.assertIn('"state": "benchmark_error"', report)
            self.assertIn("synthetic benchmark failure", report)


if __name__ == "__main__":
    unittest.main()
