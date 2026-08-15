import hashlib
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

        manifest = json.loads((self.dep / "manifest.json").read_text(encoding="utf-8"))
        self.assertGreater(manifest["raw"][0]["size"], 0)
        self.assertGreater(manifest["shareable"][0]["size"], 0)

        redacted_path = next((self.dep / "shareable" / "artifacts").iterdir())
        redacted_path.write_text("tampered after redaction\n", encoding="utf-8")
        self.assertTrue(
            any("sha256 mismatch" in error for error in verify(self.dep, strict=True))
        )
        redacted_path.unlink()
        self.assertTrue(
            any("missing artifact" in error for error in verify(self.dep, strict=True))
        )

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

    def test_dep_id_cannot_escape_evidence_root(self):
        with self.assertRaisesRegex(ValueError, "DEP ID"):
            make_dep(
                self.root / "evidence",
                issue="ISSUE-ESCAPE",
                risk="L1",
                dep_id="../escaped-dep",
            )
        self.assertFalse((self.root / "escaped-dep").exists())

    def test_collector_rejects_symlink_source_and_duplicate_label(self):
        first = self.root / "first.log"
        second = self.root / "second.log"
        first.write_text("first evidence\n", encoding="utf-8")
        second.write_text("second evidence\n", encoding="utf-8")
        linked = self.root / "linked.log"
        linked.symlink_to(first)

        with self.assertRaisesRegex(ValueError, "symlink"):
            collect(self.dep, "terminal", linked, label="linked.log")

        destination = collect(self.dep, "terminal", first, label="same.log")
        with self.assertRaisesRegex(FileExistsError, "already exists"):
            collect(self.dep, "terminal", second, label="same.log")
        self.assertEqual(destination.read_text(encoding="utf-8"), "first evidence\n")

    def test_redaction_rejects_per_file_symlinks(self):
        outside_source = self.root / "outside-source.txt"
        outside_source.write_text("password=outside\n", encoding="utf-8")
        raw_link = self.dep / "private/raw/terminal--linked.txt"
        raw_link.symlink_to(outside_source)
        with self.assertRaisesRegex(ValueError, "symlink"):
            redact(self.dep)

        raw_link.unlink()
        source = self.root / "source.txt"
        source.write_text("password=inside\n", encoding="utf-8")
        collect(self.dep, "terminal", source, label="source.txt")
        outside_target = self.root / "outside-target.txt"
        outside_target.write_text("do not overwrite\n", encoding="utf-8")
        output_link = self.dep / "shareable/artifacts/terminal--source.txt"
        output_link.symlink_to(outside_target)
        with self.assertRaisesRegex(ValueError, "symlink"):
            redact(self.dep)
        self.assertEqual(outside_target.read_text(encoding="utf-8"), "do not overwrite\n")

    def test_control_files_and_attachment_outputs_reject_symlinks(self):
        source = self.root / "source.log"
        source.write_text("safe synthetic evidence\n", encoding="utf-8")
        manifest = self.dep / "manifest.json"
        original_manifest = manifest.read_text(encoding="utf-8")
        outside_manifest = self.root / "outside-manifest.json"
        outside_manifest.write_text(original_manifest, encoding="utf-8")
        manifest.unlink()
        manifest.symlink_to(outside_manifest)
        with self.assertRaisesRegex(ValueError, "symlink"):
            collect(self.dep, "terminal", source)
        self.assertEqual(outside_manifest.read_text(encoding="utf-8"), original_manifest)

        manifest.unlink()
        manifest.write_text(original_manifest, encoding="utf-8")
        collect(self.dep, "terminal", source)
        outside_report = self.root / "outside-report.json"
        outside_report.write_text("do not overwrite\n", encoding="utf-8")
        report = self.dep / "redaction-report.json"
        report.symlink_to(outside_report)
        with self.assertRaisesRegex(ValueError, "symlink"):
            redact(self.dep)
        self.assertEqual(outside_report.read_text(encoding="utf-8"), "do not overwrite\n")

    def test_consistent_manifest_tampering_cannot_forge_redaction_provenance(self):
        self._complete("reproduction.md", "A deterministic synthetic failure is reproduced.")
        source = self.root / "source.log"
        source.write_text("POST /facts -> 409 confirmation_required\n", encoding="utf-8")
        collect(self.dep, "terminal", source, label="source.log")
        redact(self.dep)
        transition(self.dep, "evidence")

        output = self.dep / "shareable/artifacts/terminal--source.log"
        forged = b"invented but internally hash-consistent evidence\n"
        output.write_bytes(forged)
        digest = hashlib.sha256(forged).hexdigest()
        manifest_path = self.dep / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["shareable"][0]["sha256"] = digest
        manifest["shareable"][0]["size"] = len(forged)
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        report_path = self.dep / "redaction-report.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report["files"][0]["output_sha256"] = digest
        report["files"][0]["output_size"] = len(forged)
        report_path.write_text(json.dumps(report), encoding="utf-8")

        errors = verify(self.dep)
        self.assertTrue(
            any("not the deterministic redaction" in error for error in errors),
            errors,
        )

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
