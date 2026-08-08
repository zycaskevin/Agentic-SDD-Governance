import unittest
from pathlib import Path

from sddgov.benchmark import compare


ROOT = Path(__file__).resolve().parents[1]


class BenchmarkTests(unittest.TestCase):
    def test_pair_scoring_and_claim_boundary(self):
        result = compare(
            ROOT / "benchmarks/fixtures/screenshot-only-result.json",
            ROOT / "benchmarks/fixtures/evidence-driven-result.json",
        )
        self.assertGreater(result["delta"], 0)
        self.assertFalse(result["claim_allowed"])
        self.assertIn("not an empirical superiority claim", result["note"])


if __name__ == "__main__":
    unittest.main()
