import subprocess
import sys
import unittest
from pathlib import Path

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
        self.assertIn("--threshold-seconds", completed.stderr)


if __name__ == "__main__":
    unittest.main()
