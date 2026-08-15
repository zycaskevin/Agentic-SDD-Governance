import hashlib
import json
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sddgov.evidence as evidence_module
import sddgov.redaction as redaction_module
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
        self.assertFalse((redirected / "raw").exists())

    def test_collector_keeps_verified_dirfd_during_parent_replacement(self):
        source = self.root / "source.log"
        source.write_text("synthetic failure", encoding="utf-8")
        raw = self.dep / "private/raw"
        parked = self.dep / "private/raw-parked"
        outside = self.root / "outside"
        outside.mkdir()
        original = evidence_module._bounded_filename

        def replace_parent(directory, name):
            result = original(directory, name)
            raw.rename(parked)
            raw.symlink_to(outside, target_is_directory=True)
            return result

        with (
            patch("sddgov.evidence._bounded_filename", side_effect=replace_parent),
            self.assertRaisesRegex(ValueError, "changed during operation"),
        ):
            collect(self.dep, "terminal", source)
        self.assertEqual(list(outside.iterdir()), [])
        self.assertTrue((parked / "terminal--artifact-1.log").is_file())

    def test_redaction_keeps_verified_output_dirfd_during_parent_replacement(self):
        source = self.root / "source.log"
        source.write_text("password=synthetic", encoding="utf-8")
        collect(self.dep, "terminal", source)
        shareable = self.dep / "shareable/artifacts"
        parked = self.dep / "shareable/artifacts-parked"
        outside = self.root / "outside-output"
        outside.mkdir()
        original = redaction_module._write_at

        def replace_parent(directory_fd, name, data):
            shareable.rename(parked)
            shareable.symlink_to(outside, target_is_directory=True)
            return original(directory_fd, name, data)

        with (
            patch("sddgov.redaction._write_at", side_effect=replace_parent),
            self.assertRaisesRegex(ValueError, "changed during operation"),
        ):
            redact(self.dep)
        self.assertEqual(list(outside.iterdir()), [])
        self.assertTrue((parked / "terminal--artifact-1.log").is_file())

    def test_verifier_fails_closed_when_artifact_parent_is_replaced(self):
        self._complete("reproduction.md", "Synthetic failure is reproducible.")
        source = self.root / "verify-source.log"
        source.write_text("password=synthetic\n", encoding="utf-8")
        collect(self.dep, "terminal", source)
        redact(self.dep)
        transition(self.dep, "evidence")
        shareable = self.dep / "shareable/artifacts"
        parked = self.dep / "shareable/artifacts-parked"
        outside = self.root / "verify-outside"
        outside.mkdir()
        (outside / "terminal--artifact-1.log").write_text(
            "forged replacement\n", encoding="utf-8"
        )
        original = evidence_module._read_regular_bytes_at
        replaced = False

        def replace_parent(directory_fd, name, label):
            nonlocal replaced
            if not replaced and label.startswith("artifact shareable/artifacts/"):
                replaced = True
                shareable.rename(parked)
                shareable.symlink_to(outside, target_is_directory=True)
            return original(directory_fd, name, label)

        with patch(
            "sddgov.evidence._read_regular_bytes_at", side_effect=replace_parent
        ):
            errors = verify(self.dep)
        self.assertTrue(
            any("filesystem boundary changed" in error for error in errors), errors
        )

    def test_control_writes_fail_closed_when_dep_parent_is_replaced(self):
        for control_name in ("manifest.json", "redaction-report.json", "summary.yaml"):
            with self.subTest(control_name=control_name):
                case_root = self.root / f"control-{control_name.replace('.', '-')}"
                dep = make_dep(
                    case_root / "evidence",
                    issue="ISSUE-CONTROL-TOCTOU",
                    risk="L1",
                    dep_id="DEP-CONTROL-TOCTOU",
                )
                source = case_root / "source.log"
                source.write_text("password=synthetic\n", encoding="utf-8")
                if control_name != "manifest.json":
                    collect(dep, "terminal", source)
                if control_name == "summary.yaml":
                    (dep / "reproduction.md").write_text(
                        "# Record\n\nSynthetic failure is reproducible.\n",
                        encoding="utf-8",
                    )
                    redact(dep)
                parked = case_root / "dep-parked"
                outside = case_root / "outside"
                outside.mkdir()
                sentinel = outside / control_name
                sentinel.write_text("do not overwrite\n", encoding="utf-8")
                original = evidence_module._write_bytes_at
                replaced = False

                def replace_parent(directory_fd, name, data, label):
                    nonlocal replaced
                    if not replaced and name == control_name:
                        replaced = True
                        dep.rename(parked)
                        dep.symlink_to(outside, target_is_directory=True)
                    return original(directory_fd, name, data, label)

                with (
                    patch(
                        "sddgov.evidence._write_bytes_at",
                        side_effect=replace_parent,
                    ),
                    self.assertRaisesRegex(ValueError, "DEP root changed|cannot enter"),
                ):
                    if control_name == "manifest.json":
                        collect(dep, "terminal", source)
                    elif control_name == "redaction-report.json":
                        redact(dep)
                    else:
                        transition(dep, "evidence")
                self.assertEqual(
                    sentinel.read_text(encoding="utf-8"), "do not overwrite\n"
                )

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

    def test_collector_rejects_hardlinked_source(self):
        source = self.root / "source.log"
        linked = self.root / "linked.log"
        source.write_text("synthetic evidence\n", encoding="utf-8")
        linked.hardlink_to(source)
        with self.assertRaisesRegex(ValueError, "hard-linked"):
            collect(self.dep, "terminal", linked)

    def test_every_raw_artifact_must_be_in_files_or_blocked(self):
        self._complete("reproduction.md", "Synthetic failure is reproducible.")
        source = self.root / "source.log"
        source.write_text("initial synthetic failure\n", encoding="utf-8")
        collect(self.dep, "terminal", source, label="source.log")
        redact(self.dep)
        transition(self.dep, "evidence")

        contradiction = self.dep / "private/raw/terminal--contradiction.log"
        contradiction.write_text("contradictory synthetic evidence\n", encoding="utf-8")
        manifest_path = self.dep / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        data = contradiction.read_bytes()
        manifest["raw"].append({
            "collector": "terminal",
            "path": "private/raw/terminal--contradiction.log",
            "sha256": hashlib.sha256(data).hexdigest(),
            "size": len(data),
            "collected_at": manifest["raw"][0]["collected_at"],
            "shareable": False,
        })
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        errors = verify(self.dep)
        self.assertTrue(any("cover every raw artifact" in error for error in errors), errors)

    def test_unknown_extension_cannot_bypass_deterministic_redaction(self):
        self._complete("reproduction.md", "Synthetic failure is reproducible.")
        source = self.root / "source.log"
        source.write_text("synthetic@example.com\n", encoding="utf-8")
        collect(self.dep, "terminal", source, label="source.log")
        redact(self.dep)
        transition(self.dep, "evidence")

        raw_old = self.dep / "private/raw/terminal--source.log"
        out_old = self.dep / "shareable/artifacts/terminal--source.log"
        raw_new = raw_old.with_suffix(".bin")
        out_new = out_old.with_suffix(".bin")
        raw_old.rename(raw_new)
        out_old.rename(out_new)
        exposed = b"synthetic@example.com\n"
        raw_new.write_bytes(exposed)
        out_new.write_bytes(exposed)
        digest = hashlib.sha256(exposed).hexdigest()
        manifest_path = self.dep / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["raw"][0].update({"path": "private/raw/terminal--source.bin", "sha256": digest, "size": len(exposed)})
        manifest["shareable"][0].update({"path": "shareable/artifacts/terminal--source.bin", "sha256": digest, "size": len(exposed)})
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        report_path = self.dep / "redaction-report.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report["files"][0].update({
            "source": "terminal--source.bin",
            "output": "terminal--source.bin",
            "source_sha256": digest,
            "source_size": len(exposed),
            "output_sha256": digest,
            "output_size": len(exposed),
            "redactions": {},
        })
        report["totals"] = {}
        report_path.write_text(json.dumps(report), encoding="utf-8")
        errors = verify(self.dep)
        self.assertTrue(any("not eligible for deterministic redaction" in error for error in errors), errors)

    def test_har_with_body_is_blocked_by_default(self):
        self._complete("reproduction.md", "Synthetic browser failure is reproducible.")
        har = self.root / "network.har"
        har.write_text(
            json.dumps({"log": {"entries": [{"response": {"content": {"encoding": "base64", "text": "c3ludGhldGljLXNlY3JldA=="}}}]}}),
            encoding="utf-8",
        )
        collect(self.dep, "browser-har", har)
        report = redact(self.dep)
        self.assertEqual(report["files"], [])
        self.assertEqual(report["blocked"][0]["reason"], "har_requires_dedicated_body_stripping")

    def test_browser_har_collector_cannot_hide_behind_text_label(self):
        source = self.root / "network.har"
        source.write_text(
            json.dumps({"log": {"entries": [{"response": {"content": {"text": "c2VjcmV0"}}}]}}),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "suffix must match"):
            collect(self.dep, "browser-har", source, label="network.txt")

        collected = collect(self.dep, "browser-har", source, label="network.har")
        disguised = collected.with_suffix(".txt")
        collected.rename(disguised)
        manifest_path = self.dep / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["raw"][0]["path"] = "private/raw/browser-har--network.txt"
        manifest["raw"][0]["source_suffix"] = ".txt"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        report = redact(self.dep)
        self.assertEqual(report["files"], [])
        self.assertEqual(
            report["blocked"][0]["reason"],
            "har_requires_dedicated_body_stripping",
        )
        with self.assertRaisesRegex(ValueError, "blocked artifacts"):
            transition(self.dep, "evidence")

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
