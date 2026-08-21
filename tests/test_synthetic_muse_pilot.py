import tempfile
import unittest
from pathlib import Path

from sddgov.pilot import run_quick_demo, run_synthetic_muse_pilot


class SyntheticMusePilotTests(unittest.TestCase):
    def test_disposable_offline_pilot_passes_without_real_data(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "pilot-result.json"
            result = run_synthetic_muse_pilot(output)
            self.assertEqual(result["verdict"], "PASS")
            self.assertFalse(result["network_used"])
            self.assertFalse(result["real_data_used"])
            self.assertTrue(result["binary_image_fail_closed"])
            self.assertTrue(result["text_redaction_ok"])
            self.assertTrue(result["strict_dep_ok"])
            self.assertTrue(result["portable_dep_ok"])
            self.assertTrue(output.is_file())

    def test_quick_demo_exposes_allow_block_and_evidence_boundaries(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "quick-demo.json"
            result = run_quick_demo(output)
            self.assertEqual(result["verdict"], "PASS")
            self.assertFalse(result["network_used"])
            self.assertFalse(result["real_data_used"])
            self.assertTrue(result["routine_l1_continues"])
            self.assertTrue(result["dangerous_downgrade_blocked"])
            self.assertTrue(result["agent_install_ok"])
            self.assertTrue(result["text_redaction_ok"])
            self.assertTrue(result["binary_evidence_fail_closed"])
            self.assertTrue(result["strict_dep_ok"])
            self.assertTrue(output.is_file())


if __name__ == "__main__":
    unittest.main()
