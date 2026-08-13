import json
import stat
import tempfile
import unittest
from pathlib import Path

from sddgov.evidence import attach, collect, make_dep, redact, transition, verify


class EvidenceFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.dep = make_dep(
            self.root / "evidence",
            issue="ISSUE-128",
            risk="L1",
            sdd_ref="FAMILY-03",
            dep_id="DEP-TEST-128",
        )

    def tearDown(self):
        self.temp.cleanup()

    def _complete(self, name: str, text: str) -> None:
        (self.dep / name).write_text(f"# Record\n\n{text}\n", encoding="utf-8")

    def test_full_red_to_proof_flow(self):
        self._complete("reproduction.md", "Create item, observe success, refresh, item disappears.")
        log = self.root / "failure.log"
        log.write_text(
            "Authorization: Bearer secret-token\nowner@example.com\ninsert returned 403\n",
            encoding="utf-8",
        )
        collect(self.dep, "terminal", log)
        report = redact(self.dep)
        self.assertFalse(report["blocked"])
        transition(self.dep, "evidence")

        self._complete("root-cause-hypothesis.md", "The insert is rejected; the UI ignores the response. Falsified by a direct contract test.")
        self._complete("fix-scope.md", "Handle the failed insert and preserve persistence behavior; unrelated UI is excluded.")
        transition(self.dep, "fix")

        self._complete("regression-evidence.md", "Added an integration regression test and ran the related persistence suite.")
        self._complete("verification.md", "The original test now passes and refresh retains the item.")
        transition(self.dep, "green")

        self._complete("rollback.md", "Revert the bounded commit and rerun the persistence suite.")
        transition(self.dep, "proof")

        self.assertEqual(verify(self.dep, strict=True), [])
        block = attach(self.dep, "pr")
        block_text = block.read_text(encoding="utf-8")
        self.assertIn("DEP-TEST-128", block_text)
        self.assertIn("shareable/artifacts", block_text)
        self.assertNotIn("private/raw", block_text)
        redacted = next((self.dep / "shareable" / "artifacts").iterdir()).read_text(encoding="utf-8")
        self.assertNotIn("secret-token", redacted)
        self.assertNotIn("owner@example.com", redacted)

    def test_transition_fails_closed_on_incomplete_template(self):
        with self.assertRaisesRegex(ValueError, "cannot enter evidence"):
            transition(self.dep, "evidence")

    def test_binary_evidence_blocks_verification(self):
        self._complete("reproduction.md", "A reviewed reproduction exists.")
        binary = self.root / "trace.zip"
        binary.write_bytes(b"PK\x03\x04binary")
        collect(self.dep, "playwright-trace", binary)
        report = redact(self.dep)
        self.assertTrue(report["blocked"])
        with self.assertRaisesRegex(ValueError, "blocked artifacts"):
            transition(self.dep, "evidence")

    def test_summary_cannot_reference_raw_evidence(self):
        summary_path = self.dep / "summary.yaml"
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        summary["attachments"] = [{"path": "private/raw/failure.log", "sha256": "a" * 64}]
        summary_path.write_text(json.dumps(summary), encoding="utf-8")
        self.assertIn("summary attachments must never reference private/raw evidence", verify(self.dep))

    def test_collector_rejects_platform_normalized_or_symlinked_destinations(self):
        source = self.root / "source.log"
        source.write_text("failure", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "platform normalization"):
            collect(self.dep, "terminal", source, label="unsafe.")

        redirected = self.root / "redirected"
        redirected.mkdir()
        raw = self.dep / "private" / "raw"
        raw.rmdir()
        raw.symlink_to(redirected, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "zone"):
            collect(self.dep, "terminal", source)

    def test_raw_zone_is_owner_only(self):
        mode = stat.S_IMODE((self.dep / "private" / "raw").stat().st_mode)
        self.assertEqual(mode, 0o700)

    def test_summary_datetime_formats_are_enforced(self):
        summary_path = self.dep / "summary.yaml"
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        summary["created_at"] = "not-a-date"
        summary["workflow"]["history"][0]["at"] = "also-not-a-date"
        summary_path.write_text(json.dumps(summary), encoding="utf-8")

        errors = verify(self.dep)
        self.assertTrue(any("created_at" in error and "date-time" in error for error in errors), errors)
        self.assertTrue(any("workflow.history.0.at" in error and "date-time" in error for error in errors), errors)

    def test_lowercase_rfc3339_separators_are_accepted(self):
        summary_path = self.dep / "summary.yaml"
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        summary["created_at"] = "2026-08-13t10:20:30z"
        summary["updated_at"] = "2026-08-13t10:20:30z"
        summary["workflow"]["history"][0]["at"] = "2026-08-13t10:20:30z"
        summary_path.write_text(json.dumps(summary), encoding="utf-8")
        errors = verify(self.dep)
        self.assertFalse(any("date-time" in error for error in errors), errors)

    def test_workflow_history_must_be_exact_nonduplicated_phase_prefix(self):
        summary_path = self.dep / "summary.yaml"
        original = json.loads(summary_path.read_text(encoding="utf-8"))
        cases = (
            [],
            [original["workflow"]["history"][0], original["workflow"]["history"][0]],
            [{"phase": "evidence", "at": original["created_at"]}],
        )
        for history in cases:
            with self.subTest(history=history):
                summary = json.loads(json.dumps(original))
                summary["workflow"]["history"] = history
                summary_path.write_text(json.dumps(summary), encoding="utf-8")
                errors = verify(self.dep)
                self.assertTrue(
                    any("workflow history must be the exact phase prefix" in error for error in errors),
                    errors,
                )

    def test_summary_rejects_unknown_root_history_and_attachment_fields(self):
        summary_path = self.dep / "summary.yaml"
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        summary["unexpected_root"] = True
        summary["workflow"]["history"][0]["unexpected_history"] = True
        summary["attachments"] = [
            {
                "path": "shareable/artifacts/safe.txt",
                "sha256": "a" * 64,
                "unexpected_attachment": True,
            }
        ]
        summary_path.write_text(json.dumps(summary), encoding="utf-8")

        errors = verify(self.dep)
        self.assertTrue(any("unexpected_root" in error for error in errors), errors)
        self.assertTrue(any("unexpected_history" in error for error in errors), errors)
        self.assertTrue(any("unexpected_attachment" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
