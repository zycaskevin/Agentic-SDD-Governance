import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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

    def test_quick_demo_fails_when_the_evidence_pilot_verdict_fails(self):
        failed_pilot = {
            "verdict": "FAIL",
            "agent_install_ok": True,
            "text_redaction_ok": True,
            "binary_image_fail_closed": True,
            "strict_dep_ok": True,
        }
        with patch(
            "sddgov.pilot.run_synthetic_muse_pilot", return_value=failed_pilot
        ):
            result = run_quick_demo()
        self.assertEqual(result["verdict"], "FAIL")

    def test_quick_demo_fails_when_nested_pilot_check_is_false(self):
        inconsistent_pilot = {
            "verdict": "PASS",
            "agent_install_ok": True,
            "text_redaction_ok": True,
            "binary_image_fail_closed": False,
            "strict_dep_ok": True,
        }
        with patch(
            "sddgov.pilot.run_synthetic_muse_pilot",
            return_value=inconsistent_pilot,
        ):
            result = run_quick_demo()
        self.assertEqual(result["verdict"], "FAIL")

    def test_quick_demo_fails_loudly_when_nested_result_is_incomplete(self):
        incomplete_pilot = {
            "verdict": "PASS",
            "agent_install_ok": True,
            "text_redaction_ok": True,
            "strict_dep_ok": True,
        }
        with patch(
            "sddgov.pilot.run_synthetic_muse_pilot",
            return_value=incomplete_pilot,
        ), self.assertRaisesRegex(ValueError, "binary_image_fail_closed"):
            run_quick_demo()

    def test_pilot_reports_reject_leaf_symlinks_without_overwrite(self):
        for runner, name in (
            (run_synthetic_muse_pilot, "pilot"),
            (run_quick_demo, "quick"),
        ):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                sentinel = root / "sentinel.json"
                sentinel.write_text("preserve\n", encoding="utf-8")
                output = root / f"{name}.json"
                output.symlink_to(sentinel)
                with self.assertRaises(FileExistsError):
                    runner(output)
                self.assertTrue(output.is_symlink())
                self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserve\n")

    def test_pilot_reports_reject_symlinked_parent_directories(self):
        for runner, name in (
            (run_synthetic_muse_pilot, "pilot"),
            (run_quick_demo, "quick"),
        ):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                outside = root / "outside"
                outside.mkdir()
                alias = root / "alias"
                alias.symlink_to(outside, target_is_directory=True)
                with self.assertRaises(OSError):
                    runner(alias / f"{name}.json")
                self.assertEqual(list(outside.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
