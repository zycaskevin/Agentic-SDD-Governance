import unittest

from scripts.benchmark_monorepo_rollback import run_benchmark


class MonorepoRollbackBenchmarkTests(unittest.TestCase):
    def test_small_smoke_preserves_exact_proof_and_claim_boundary(self):
        report = run_benchmark([25], 1, threshold_seconds=5.0)
        self.assertTrue(report["cases"][0]["all_proofs_passed"], report)
        self.assertFalse(report["claim_allowed"])
        self.assertFalse(report["decision"]["optimize_required"], report)
        self.assertIn("full-tree proof", report["decision"]["action"])


if __name__ == "__main__":
    unittest.main()
