import hashlib
import json
import os
import stat
import subprocess
import sys
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

    def _prepare_attachable_dep(self) -> None:
        self._complete("reproduction.md", "Synthetic failure is reproducible.")
        source = self.root / "attach-source.log"
        source.write_text("password=synthetic\n", encoding="utf-8")
        collect(self.dep, "terminal", source)
        redact(self.dep)
        transition(self.dep, "evidence")
        self._complete("root-cause-hypothesis.md", "The synthetic source exposes a bounded defect.")
        self._complete("fix-scope.md", "Only the bounded synthetic path is changed.")
        transition(self.dep, "fix")
        self._complete("regression-evidence.md", "The regression suite covers the synthetic defect.")
        self._complete("verification.md", "The corrected synthetic behavior is green.")
        transition(self.dep, "green")
        self._complete("rollback.md", "Revert the bounded synthetic change and rerun tests.")
        transition(self.dep, "proof")

    def _default_attachment_path(self, dep: Path, target: str = "pr") -> Path:
        controls = {
            name: (dep / name).read_bytes()
            for name in ("summary.yaml", "manifest.json")
        }
        digest = evidence_module._control_snapshot_digest(controls)
        return dep / f"attach-{target}-{digest[:16]}.md"

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

    @unittest.skipUnless(sys.platform == "darwin", "requires native Darwin aliases")
    def test_collect_accepts_the_darwin_tmp_system_alias(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as temporary:
            source = Path(temporary) / "darwin-alias.log"
            source.write_text("synthetic evidence\n", encoding="utf-8")
            collected = collect(self.dep, "terminal", source)
        self.assertTrue(collected.is_file())

    def test_verifier_rejects_oversized_control_before_parsing(self):
        manifest = self.dep / "manifest.json"
        manifest.write_text("{" + " " * 128 + "}", encoding="utf-8")
        with patch("sddgov.evidence.MAX_DEP_CONTROL_FILE_BYTES", 64):
            errors = verify(self.dep)
        self.assertTrue(any("exceeds 64 bytes" in error for error in errors), errors)

    def test_verifier_rejects_oversized_artifact_before_digesting(self):
        self._complete("reproduction.md", "Synthetic failure is reproducible.")
        source = self.root / "bounded.log"
        source.write_text("x" * 128 + "\n", encoding="utf-8")
        collect(self.dep, "terminal", source)
        redact(self.dep)
        transition(self.dep, "evidence")
        with patch("sddgov.evidence.MAX_DEP_ARTIFACT_BYTES", 64):
            errors = verify(self.dep)
        self.assertTrue(any("exceeds 64 bytes" in error for error in errors), errors)

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

    def test_dep_root_rejects_an_intermediate_symlink_component(self):
        alias = self.root / "evidence-alias"
        alias.symlink_to(self.root / "evidence", target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "directory path"):
            with evidence_module._opened_dep_root(alias / self.dep.name):
                pass

    def test_regular_file_reader_requests_nonblocking_open(self):
        source = self.root / "nonblocking-source.log"
        source.write_text("synthetic evidence\n", encoding="utf-8")
        original = os.open
        observed_flags = []

        def inspect_flags(path, flags, *args, **kwargs):
            if path == source.name:
                observed_flags.append(flags)
            return original(path, flags, *args, **kwargs)

        with patch("sddgov.evidence.os.open", side_effect=inspect_flags):
            evidence_module._read_regular_bytes(
                source,
                "collector input",
                max_bytes=evidence_module.MAX_DEP_ARTIFACT_BYTES,
            )
        self.assertTrue(observed_flags)
        self.assertTrue(observed_flags[0] & getattr(os, "O_NONBLOCK", 0))

    def test_collect_failure_removes_unregistered_raw_artifact(self):
        source = self.root / "transactional-collect.log"
        source.write_text("synthetic failure\n", encoding="utf-8")
        original = evidence_module._save_at

        def fail_manifest(directory_fd, name, data, *args, **kwargs):
            if name == "manifest.json":
                raise OSError("synthetic manifest failure")
            return original(directory_fd, name, data, *args, **kwargs)

        with (
            patch("sddgov.evidence._save_at", side_effect=fail_manifest),
            self.assertRaisesRegex(OSError, "synthetic manifest failure"),
        ):
            collect(self.dep, "terminal", source)
        manifest = json.loads((self.dep / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["raw"], [])
        self.assertEqual(list((self.dep / "private/raw").iterdir()), [])

    def test_collect_post_publish_failure_is_treated_as_committed(self):
        source = self.root / "post-publish-collect.log"
        source.write_text("synthetic committed evidence\n", encoding="utf-8")
        original = evidence_module._save_at

        def fail_after_publish(directory_fd, name, data, *args, **kwargs):
            result = original(directory_fd, name, data, *args, **kwargs)
            if name == "manifest.json":
                raise OSError("synthetic fsync-after-publish failure")
            return result

        with patch("sddgov.evidence._save_at", side_effect=fail_after_publish):
            destination = collect(self.dep, "terminal", source)
        manifest = json.loads((self.dep / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["raw"][0]["path"], f"private/raw/{destination.name}")
        self.assertTrue(destination.is_file())

    def test_collect_after_redaction_fails_without_staling_the_report(self):
        first = self.root / "first-collection.log"
        first.write_text("synthetic first collection\n", encoding="utf-8")
        collect(self.dep, "terminal", first)
        redact(self.dep)
        manifest_before = (self.dep / "manifest.json").read_bytes()
        report_before = (self.dep / "redaction-report.json").read_bytes()
        raw_before = sorted(path.name for path in (self.dep / "private/raw").iterdir())

        later = self.root / "later-collection.log"
        later.write_text("synthetic later collection\n", encoding="utf-8")
        with patch(
            "sddgov.evidence._read_regular_bytes",
            side_effect=AssertionError("closed DEP read collector input"),
        ), self.assertRaisesRegex(ValueError, "closed after redaction"):
            collect(self.dep, "terminal", later)

        self.assertEqual((self.dep / "manifest.json").read_bytes(), manifest_before)
        self.assertEqual(
            (self.dep / "redaction-report.json").read_bytes(), report_before
        )
        self.assertEqual(
            sorted(path.name for path in (self.dep / "private/raw").iterdir()),
            raw_before,
        )

    def test_collect_bounds_the_redaction_report_probe_before_source_read(self):
        source = self.root / "bounded-report-probe.log"
        source.write_text("synthetic evidence\n", encoding="utf-8")
        original = evidence_module._read_regular_bytes_at
        observed = []

        def inspect_report(directory_fd, name, label, **kwargs):
            if name == "redaction-report.json":
                observed.append(kwargs.get("max_bytes"))
            return original(directory_fd, name, label, **kwargs)

        with patch(
            "sddgov.evidence._read_regular_bytes_at", side_effect=inspect_report
        ):
            collect(self.dep, "terminal", source)

        self.assertEqual(observed, [redaction_module.MAX_REDACTION_FILE_BYTES])

    def test_valid_json_evidence_is_labeled_application_json(self):
        source = self.root / "release-report.json"
        source.write_text('{"ok":true}\n', encoding="utf-8")
        collect(self.dep, "terminal", source)
        manifest = json.loads((self.dep / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["schema_version"], "1.1")
        self.assertEqual(manifest["raw"][0]["media_type"], "application/json")
        self.assertFalse(any("media_type" in error for error in verify(self.dep)))

    def test_json_media_type_compatibility_is_limited_to_legacy_manifests(self):
        source = self.root / "legacy-release-report.json"
        source.write_text('{"ok":true}\n', encoding="utf-8")
        collect(self.dep, "terminal", source)
        manifest_path = self.dep / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["raw"][0]["media_type"] = "text/plain; charset=utf-8"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        self.assertTrue(
            any("media_type mismatch" in error for error in verify(self.dep, strict=True))
        )

        manifest["schema_version"] = "1.0"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        self.assertFalse(
            any("media_type" in error for error in verify(self.dep, strict=True))
        )

    def test_collect_preserves_later_manifest_writer_and_removes_owned_raw(self):
        source = self.root / "later-writer-collect.log"
        source.write_text("synthetic uncommitted evidence\n", encoding="utf-8")
        manifest_path = self.dep / "manifest.json"
        later_manifest = b'{"later_writer":true}\n'
        original = evidence_module._save_at

        def inject_later_writer(directory_fd, name, data, *args, **kwargs):
            if name == "manifest.json":
                manifest_path.write_bytes(later_manifest)
            return original(directory_fd, name, data, *args, **kwargs)

        with (
            patch("sddgov.evidence._save_at", side_effect=inject_later_writer),
            self.assertRaisesRegex(ValueError, "changed before publication"),
        ):
            collect(self.dep, "terminal", source)
        self.assertEqual(manifest_path.read_bytes(), later_manifest)
        self.assertEqual(list((self.dep / "private/raw").iterdir()), [])

    def test_collect_rename_boundary_preserves_later_manifest_writer(self):
        source = self.root / "rename-boundary-collect.log"
        source.write_text("synthetic uncommitted evidence\n", encoding="utf-8")
        manifest_path = self.dep / "manifest.json"
        later_manifest = b'{"rename_boundary_later_writer":true}\n'
        original = os.rename

        def inject_at_claim(src, dst, *args, **kwargs):
            if src == "manifest.json":
                manifest_path.write_bytes(later_manifest)
            return original(src, dst, *args, **kwargs)

        with (
            patch("sddgov.evidence.os.rename", side_effect=inject_at_claim),
            self.assertRaisesRegex(ValueError, "changed before publication"),
        ):
            collect(self.dep, "terminal", source)
        self.assertEqual(manifest_path.read_bytes(), later_manifest)
        self.assertEqual(list((self.dep / "private/raw").iterdir()), [])

    def test_redact_failure_removes_unregistered_shareable_artifacts(self):
        source = self.root / "transactional-redact.log"
        source.write_text("password=synthetic\n", encoding="utf-8")
        collect(self.dep, "terminal", source)
        manifest_before = (self.dep / "manifest.json").read_bytes()
        report_path = self.dep / "redaction-report.json"
        self.assertFalse(report_path.exists())
        original = evidence_module._save_at

        def fail_report(directory_fd, name, data, *args, **kwargs):
            if name == "redaction-report.json":
                raise OSError("synthetic report failure")
            return original(directory_fd, name, data, *args, **kwargs)

        with (
            patch("sddgov.evidence._save_at", side_effect=fail_report),
            self.assertRaisesRegex(OSError, "synthetic report failure"),
        ):
            redact(self.dep)
        self.assertEqual(list((self.dep / "shareable/artifacts").iterdir()), [])
        self.assertEqual((self.dep / "manifest.json").read_bytes(), manifest_before)
        self.assertFalse(report_path.exists())

    def test_redact_artifact_post_publish_failure_cleans_owned_output(self):
        source = self.root / "artifact-post-publish.log"
        source.write_text("password=synthetic\n", encoding="utf-8")
        collect(self.dep, "terminal", source)
        manifest_before = (self.dep / "manifest.json").read_bytes()
        original = redaction_module._stream_text_at

        def fail_after_output(source_fd, directory_fd, name, published_outputs=None):
            original(source_fd, directory_fd, name, published_outputs)
            raise OSError("synthetic output fsync failure")

        with (
            patch("sddgov.redaction._stream_text_at", side_effect=fail_after_output),
            self.assertRaisesRegex(OSError, "output fsync failure"),
        ):
            redact(self.dep)
        self.assertEqual(list((self.dep / "shareable/artifacts").iterdir()), [])
        self.assertEqual((self.dep / "manifest.json").read_bytes(), manifest_before)
        self.assertFalse((self.dep / "redaction-report.json").exists())

    def test_redact_report_post_publish_failure_completes_consistent_commit(self):
        source = self.root / "report-post-publish.log"
        source.write_text("password=synthetic\n", encoding="utf-8")
        collect(self.dep, "terminal", source)
        original = evidence_module._save_at

        def fail_after_report(directory_fd, name, data, *args, **kwargs):
            result = original(directory_fd, name, data, *args, **kwargs)
            if name == "redaction-report.json":
                raise OSError("synthetic report fsync failure")
            return result

        with patch("sddgov.evidence._save_at", side_effect=fail_after_report):
            report = redact(self.dep)
        manifest = json.loads((self.dep / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(len(manifest["shareable"]), len(report["files"]))
        self.assertTrue((self.dep / "redaction-report.json").is_file())

    def test_redact_preserves_later_manifest_writer(self):
        source = self.root / "redact-later-writer.log"
        source.write_text("password=synthetic\n", encoding="utf-8")
        collect(self.dep, "terminal", source)
        manifest_path = self.dep / "manifest.json"
        later_manifest = b'{"later_writer":true}\n'
        original = evidence_module._save_at

        def inject_later_writer(directory_fd, name, data, *args, **kwargs):
            if name == "manifest.json":
                manifest_path.write_bytes(later_manifest)
            return original(directory_fd, name, data, *args, **kwargs)

        with (
            patch("sddgov.evidence._save_at", side_effect=inject_later_writer),
            self.assertRaisesRegex(ValueError, "changed before publication"),
        ):
            redact(self.dep)
        self.assertEqual(manifest_path.read_bytes(), later_manifest)
        self.assertEqual(list((self.dep / "shareable/artifacts").iterdir()), [])

    def test_redact_cleanup_preserves_output_later_writer_at_claim_boundary(self):
        source = self.root / "redact-cleanup-boundary.log"
        source.write_text("password=synthetic\n", encoding="utf-8")
        collect(self.dep, "terminal", source)
        manifest_before = (self.dep / "manifest.json").read_bytes()
        output = self.dep / "shareable/artifacts/terminal--artifact-1.log"
        later = self.root / "redact-output-later-writer.log"
        later.write_text("preserve output later writer\n", encoding="utf-8")
        original_save = evidence_module._save_at
        original_rename = os.rename

        def fail_report(directory_fd, name, data, *args, **kwargs):
            if name == "redaction-report.json":
                raise OSError("synthetic report failure")
            return original_save(directory_fd, name, data, *args, **kwargs)

        def inject_at_cleanup(src, dst, *args, **kwargs):
            if src == output.name and ".cleanup-pending-" in str(dst):
                later.replace(output)
            return original_rename(src, dst, *args, **kwargs)

        with (
            patch("sddgov.evidence._save_at", side_effect=fail_report),
            patch("sddgov.evidence.os.rename", side_effect=inject_at_cleanup),
            self.assertRaisesRegex(OSError, "synthetic report failure"),
        ):
            redact(self.dep)
        self.assertEqual(output.read_text(encoding="utf-8"), "preserve output later writer\n")
        self.assertEqual((self.dep / "manifest.json").read_bytes(), manifest_before)
        self.assertFalse((self.dep / "redaction-report.json").exists())

    @unittest.skipUnless(hasattr(os, "mkfifo"), "requires POSIX FIFO support")
    def test_redaction_rejects_fifo_without_blocking_or_mutation(self):
        source = self.root / "fifo-source.log"
        source.write_text("password=synthetic\n", encoding="utf-8")
        collected = collect(self.dep, "terminal", source)
        collected.unlink()
        os.mkfifo(collected)
        script = (
            "from pathlib import Path\n"
            "from sddgov.evidence import redact\n"
            "try:\n"
            "    redact(Path(__import__('sys').argv[1]))\n"
            "except ValueError as exc:\n"
            "    assert 'regular file' in str(exc), exc\n"
            "else:\n"
            "    raise SystemExit('FIFO unexpectedly accepted')\n"
        )
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
        completed = subprocess.run(
            [sys.executable, "-c", script, str(self.dep)],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
            env=environment,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(list((self.dep / "shareable/artifacts").iterdir()), [])
        self.assertFalse((self.dep / "redaction-report.json").exists())

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
        self.assertFalse((parked / "terminal--artifact-1.log").exists())

    def test_redaction_keeps_verified_output_dirfd_during_parent_replacement(self):
        source = self.root / "source.log"
        source.write_text("password=synthetic", encoding="utf-8")
        collect(self.dep, "terminal", source)
        shareable = self.dep / "shareable/artifacts"
        parked = self.dep / "shareable/artifacts-parked"
        outside = self.root / "outside-output"
        outside.mkdir()
        original = redaction_module._stream_text_at

        def replace_parent(source_fd, directory_fd, name, published_outputs=None):
            shareable.rename(parked)
            shareable.symlink_to(outside, target_is_directory=True)
            return original(source_fd, directory_fd, name, published_outputs)

        with (
            patch("sddgov.redaction._stream_text_at", side_effect=replace_parent),
            self.assertRaisesRegex(ValueError, "changed during operation"),
        ):
            redact(self.dep)
        self.assertEqual(list(outside.iterdir()), [])
        self.assertFalse((parked / "terminal--artifact-1.log").exists())

    def test_transition_preserves_later_summary_writer(self):
        self._complete("reproduction.md", "Synthetic failure is reproducible.")
        source = self.root / "transition-later-writer.log"
        source.write_text("password=synthetic\n", encoding="utf-8")
        collect(self.dep, "terminal", source)
        redact(self.dep)
        summary_path = self.dep / "summary.yaml"
        later = json.loads(summary_path.read_text(encoding="utf-8"))
        later["issue"] = "ISSUE-LATER-WRITER"
        later_bytes = (json.dumps(later, ensure_ascii=False, indent=2) + "\n").encode()
        original = evidence_module._write_bytes_at

        def inject_later_writer(directory_fd, name, data, label, *args, **kwargs):
            if name == "summary.yaml":
                summary_path.write_bytes(later_bytes)
            return original(directory_fd, name, data, label, *args, **kwargs)

        with (
            patch("sddgov.evidence._write_bytes_at", side_effect=inject_later_writer),
            self.assertRaisesRegex(ValueError, "changed before publication"),
        ):
            transition(self.dep, "evidence")
        self.assertEqual(summary_path.read_bytes(), later_bytes)

    def test_transition_post_publish_failure_is_treated_as_committed(self):
        self._complete("reproduction.md", "Synthetic failure is reproducible.")
        source = self.root / "transition-post-publish.log"
        source.write_text("password=synthetic\n", encoding="utf-8")
        collect(self.dep, "terminal", source)
        redact(self.dep)
        original = evidence_module._write_bytes_at

        def fail_after_publish(directory_fd, name, data, label, *args, **kwargs):
            result = original(directory_fd, name, data, label, *args, **kwargs)
            if name == "summary.yaml":
                raise OSError("synthetic summary fsync failure")
            return result

        with patch("sddgov.evidence._write_bytes_at", side_effect=fail_after_publish):
            summary = transition(self.dep, "evidence")
        self.assertEqual(summary["workflow"]["phase"], "evidence")
        persisted = json.loads((self.dep / "summary.yaml").read_text(encoding="utf-8"))
        self.assertEqual(persisted["workflow"]["phase"], "evidence")

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

        def replace_parent(directory_fd, name, label, **kwargs):
            nonlocal replaced
            if not replaced and label.startswith("artifact shareable/artifacts/"):
                replaced = True
                shareable.rename(parked)
                shareable.symlink_to(outside, target_is_directory=True)
            return original(directory_fd, name, label, **kwargs)

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

                def replace_parent(directory_fd, name, data, label, *args, **kwargs):
                    nonlocal replaced
                    if not replaced and name == control_name:
                        replaced = True
                        dep.rename(parked)
                        dep.symlink_to(outside, target_is_directory=True)
                    return original(
                        directory_fd, name, data, label, *args, **kwargs
                    )

                with (
                    patch(
                        "sddgov.evidence._write_bytes_at",
                        side_effect=replace_parent,
                    ),
            self.assertRaisesRegex(
                ValueError,
                "DEP root changed|directory path changed|cannot enter",
            ),
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

    def test_make_dep_fails_closed_when_evidence_root_is_replaced(self):
        case_root = self.root / "make-dep-toctou"
        case_root.mkdir()
        evidence_root = case_root / "evidence"
        parked = case_root / "evidence-parked"
        outside = case_root / "outside"
        outside.mkdir()
        sentinel = outside / "sentinel.txt"
        sentinel.write_text("untouched\n", encoding="utf-8")
        original = evidence_module._write_bytes_at
        replaced = False

        def replace_parent(directory_fd, name, data, label, *args, **kwargs):
            nonlocal replaced
            if not replaced:
                replaced = True
                evidence_root.rename(parked)
                evidence_root.symlink_to(outside, target_is_directory=True)
            return original(directory_fd, name, data, label, *args, **kwargs)

        with (
            patch(
                "sddgov.evidence._write_bytes_at", side_effect=replace_parent
            ),
            self.assertRaisesRegex(ValueError, "directory path changed"),
        ):
            make_dep(
                evidence_root,
                issue="ISSUE-MAKE-DEP-TOCTOU",
                risk="L1",
                dep_id="DEP-MAKE-DEP-TOCTOU",
            )
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "untouched\n")
        self.assertFalse((outside / "DEP-MAKE-DEP-TOCTOU").exists())

    def test_collector_input_parent_replacement_fails_closed(self):
        source_parent = self.root / "source-parent"
        source_parent.mkdir()
        source = source_parent / "source.log"
        source.write_text("original synthetic bytes\n", encoding="utf-8")
        parked = self.root / "source-parent-parked"
        outside = self.root / "source-outside"
        outside.mkdir()
        (outside / "source.log").write_text(
            "replacement bytes must not be accepted\n", encoding="utf-8"
        )
        original = evidence_module._read_regular_bytes_at
        replaced = False

        def replace_parent(directory_fd, name, label, **kwargs):
            nonlocal replaced
            if not replaced and label == "collector input":
                replaced = True
                source_parent.rename(parked)
                source_parent.symlink_to(outside, target_is_directory=True)
            return original(directory_fd, name, label, **kwargs)

        with (
            patch(
                "sddgov.evidence._read_regular_bytes_at", side_effect=replace_parent
            ),
            self.assertRaisesRegex(ValueError, "directory path changed"),
        ):
            collect(self.dep, "terminal", source)
        manifest = json.loads((self.dep / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["raw"], [])
        self.assertEqual(list((self.dep / "private/raw").iterdir()), [])

    def test_collector_rejects_oversized_input_before_publication(self):
        source = self.root / "oversized.log"
        with source.open("wb") as handle:
            handle.truncate(redaction_module.MAX_REDACTION_FILE_BYTES + 1)
        with self.assertRaisesRegex(ValueError, "collector input exceeds"):
            collect(self.dep, "terminal", source)
        manifest = json.loads((self.dep / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["raw"], [])
        self.assertEqual(list((self.dep / "private/raw").iterdir()), [])

    def test_shared_cleanup_tolerates_concurrent_pending_disappearance(self):
        directory = self.root / "cleanup"
        directory.mkdir()
        target = directory / "artifact.log"
        target.write_text("owned\n", encoding="utf-8")
        metadata = target.stat()
        descriptor = os.open(directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        original = os.stat

        def disappear(name, *args, **kwargs):
            if isinstance(name, str) and ".cleanup-pending-" in name:
                try:
                    os.unlink(name, dir_fd=descriptor)
                except FileNotFoundError:
                    pass
                raise FileNotFoundError(name)
            return original(name, *args, **kwargs)

        try:
            with patch("sddgov.fs_security.os.stat", side_effect=disappear):
                redaction_module._reconcile_failed_publication(
                    descriptor,
                    target.name,
                    (metadata.st_dev, metadata.st_ino),
                )
        finally:
            os.close(descriptor)
        self.assertFalse(target.exists())
        self.assertEqual(list(directory.iterdir()), [])

    def test_attach_verification_and_read_share_one_dep_snapshot(self):
        self._prepare_attachable_dep()
        parked = self.root / "attach-dep-parked"
        outside = self.root / "attach-dep-outside"
        outside.mkdir()
        original = evidence_module._verify_open

        def replace_after_verify(dep, dep_fd, strict, portable):
            errors = original(dep, dep_fd, strict, portable)
            self.dep.rename(parked)
            self.dep.symlink_to(outside, target_is_directory=True)
            return errors

        with (
            patch("sddgov.evidence._verify_open", side_effect=replace_after_verify),
            self.assertRaisesRegex(ValueError, "DEP root changed|directory path changed"),
        ):
            attach(self.dep, "pr")
        self.assertEqual(list(outside.glob("attach-pr-*.md")), [])

    def test_attach_rejects_atomic_control_document_replacement(self):
        self._prepare_attachable_dep()
        alternate = self.root / "alternate-summary.yaml"
        replacement = json.loads(
            (self.dep / "summary.yaml").read_text(encoding="utf-8")
        )
        replacement["issue"] = "UNVERIFIED-CONTROL-DOCUMENT"
        alternate.write_text(
            json.dumps(replacement, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        original = evidence_module._verify_open

        def replace_after_verify(dep, dep_fd, strict, portable):
            result = original(dep, dep_fd, strict, portable)
            alternate.replace(self.dep / "summary.yaml")
            return result

        with (
            patch("sddgov.evidence._verify_open", side_effect=replace_after_verify),
            self.assertRaisesRegex(ValueError, "verified control document changed"),
        ):
            attach(self.dep, "pr")
        self.assertEqual(list(self.dep.glob("attach-pr-*.md")), [])

    def test_attachment_rechecks_verified_artifact_before_publication(self):
        self._prepare_attachable_dep()
        artifact = next((self.dep / "shareable/artifacts").iterdir())
        replacement = self.root / "replacement-artifact.log"
        replacement.write_text("unverified replacement bytes\n", encoding="utf-8")
        output = self._default_attachment_path(self.dep)
        original = evidence_module._stage_attachment_at
        swapped = False

        def swap_after_stage(directory_fd, name, data):
            nonlocal swapped
            temporary = original(directory_fd, name, data)
            if not swapped:
                swapped = True
                replacement.replace(artifact)
            return temporary

        with (
            patch("sddgov.evidence._stage_attachment_at", side_effect=swap_after_stage),
            self.assertRaisesRegex(ValueError, "verified artifact changed"),
        ):
            attach(self.dep, "pr")
        self.assertFalse(output.exists())

    def test_attachment_staging_cleans_up_on_controlled_interruption(self):
        output_parent = self.root / "interrupted-attachment"
        output_parent.mkdir()
        directory_fd = os.open(
            output_parent,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
        )
        try:
            with (
                patch("sddgov.evidence.os.write", side_effect=KeyboardInterrupt),
                self.assertRaises(KeyboardInterrupt),
            ):
                evidence_module._stage_attachment_at(
                    directory_fd,
                    "proof.md",
                    b"synthetic proof\n",
                )
        finally:
            os.close(directory_fd)
        self.assertEqual(list(output_parent.glob(".proof.md.pending-*")), [])

    def test_strict_verify_rejects_pending_attachment_residue(self):
        self._prepare_attachable_dep()
        pending = self.dep / ".attach-pr-deadbeef.md.pending-interrupted"
        pending.write_text("incomplete transaction\n", encoding="utf-8")
        errors = verify(self.dep, strict=True)
        self.assertTrue(
            any("pending Evidence transaction" in error for error in errors),
            errors,
        )

    def test_default_attachment_preserves_later_writer_when_control_changes(self):
        self._prepare_attachable_dep()
        alternate = self.root / "default-boundary-summary.yaml"
        alternate.write_bytes((self.dep / "summary.yaml").read_bytes())
        third_party = self.root / "default-later-writer.md"
        third_party.write_text("preserve later writer\n", encoding="utf-8")
        original = evidence_module._stage_attachment_at
        replaced = False
        output = self._default_attachment_path(self.dep)

        def replace_control(directory_fd, name, data):
            nonlocal replaced
            temporary = original(directory_fd, name, data)
            if not replaced:
                replaced = True
                alternate.replace(self.dep / "summary.yaml")
                third_party.replace(output)
            return temporary

        with (
            patch("sddgov.evidence._stage_attachment_at", side_effect=replace_control),
            self.assertRaisesRegex(ValueError, "verified control document changed"),
        ):
            attach(self.dep, "pr")
        self.assertEqual(
            output.read_text(encoding="utf-8"),
            "preserve later writer\n",
        )

    def test_custom_attachment_preserves_later_writer_when_control_changes(self):
        self._prepare_attachable_dep()
        alternate = self.root / "custom-boundary-summary.yaml"
        alternate.write_bytes((self.dep / "summary.yaml").read_bytes())
        output_parent = self.root / "custom-boundary-output"
        output_parent.mkdir()
        output = output_parent / "pr-evidence.md"
        later = self.root / "custom-later-writer.md"
        later.write_text("preserve later writer\n", encoding="utf-8")
        original = evidence_module._stage_attachment_at
        replaced = False

        def replace_control(directory_fd, name, data):
            nonlocal replaced
            temporary = original(directory_fd, name, data)
            if not replaced:
                replaced = True
                alternate.replace(self.dep / "summary.yaml")
                later.replace(output)
            return temporary

        with (
            patch("sddgov.evidence._stage_attachment_at", side_effect=replace_control),
            self.assertRaisesRegex(ValueError, "verified control document changed"),
        ):
            attach(self.dep, "pr", output=output)
        self.assertEqual(output.read_text(encoding="utf-8"), "preserve later writer\n")

    def test_attachment_publish_never_clobbers_a_later_writer(self):
        for custom in (False, True):
            with self.subTest(custom=custom):
                case_root = self.root / f"later-writer-{custom}"
                dep = make_dep(
                    case_root / "evidence",
                    issue="ISSUE-ATTACH-LATER-WRITER",
                    risk="L1",
                    dep_id="DEP-ATTACH-LATER-WRITER",
                )
                original_dep = self.dep
                self.dep = dep
                try:
                    self._prepare_attachable_dep()
                finally:
                    self.dep = original_dep
                if custom:
                    output_parent = case_root / "custom-output"
                    output_parent.mkdir()
                    output = output_parent / "pr-evidence.md"
                else:
                    output = self._default_attachment_path(dep)
                later = case_root / "later-writer.md"
                later.write_text("preserve later writer\n", encoding="utf-8")
                original = evidence_module._stage_attachment_at
                inserted = False

                def insert_after_stage(directory_fd, name, data):
                    nonlocal inserted
                    temporary = original(directory_fd, name, data)
                    if not inserted:
                        inserted = True
                        later.replace(output)
                    return temporary

                with (
                    patch(
                        "sddgov.evidence._stage_attachment_at",
                        side_effect=insert_after_stage,
                    ),
                    self.assertRaises(FileExistsError),
                ):
                    attach(dep, "pr", output=output if custom else None)
                self.assertEqual(
                    output.read_text(encoding="utf-8"), "preserve later writer\n"
                )

    def test_link_boundary_control_update_blocks_attachment_publication(self):
        self._prepare_attachable_dep()
        old_output = self._default_attachment_path(self.dep)
        old_digest = old_output.stem.rsplit("-", 1)[-1]
        replacement = json.loads(
            (self.dep / "summary.yaml").read_text(encoding="utf-8")
        )
        replacement["issue"] = "ISSUE-NEXT-CONTROL-GENERATION"
        alternate = self.root / "next-summary.yaml"
        alternate.write_text(
            json.dumps(replacement, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        original = os.link
        replaced = False

        def update_at_publish(src, dst, **kwargs):
            nonlocal replaced
            if not replaced:
                replaced = True
                alternate.replace(self.dep / "summary.yaml")
            return original(src, dst, **kwargs)

        with (
            patch("sddgov.evidence.os.link", side_effect=update_at_publish),
            self.assertRaisesRegex(ValueError, "control document"),
        ):
            attach(self.dep, "pr")
        self.assertFalse(old_output.exists())

    def test_attachment_cleanup_preserves_later_writer_at_claim_boundary(self):
        self._prepare_attachable_dep()
        output = self._default_attachment_path(self.dep)
        alternate = self.root / "attachment-cleanup-summary.yaml"
        alternate.write_bytes((self.dep / "summary.yaml").read_bytes())
        later = self.root / "attachment-cleanup-later.md"
        later.write_text("preserve attachment later writer\n", encoding="utf-8")
        original_link = os.link
        original_rename = os.rename
        changed = False

        def change_control_at_publish(src, dst, *args, **kwargs):
            nonlocal changed
            if not changed and dst == output.name:
                changed = True
                alternate.replace(self.dep / "summary.yaml")
            return original_link(src, dst, *args, **kwargs)

        def inject_at_cleanup(src, dst, *args, **kwargs):
            if src == output.name and ".cleanup-pending-" in str(dst):
                later.replace(output)
            return original_rename(src, dst, *args, **kwargs)

        with (
            patch("sddgov.evidence.os.link", side_effect=change_control_at_publish),
            patch("sddgov.evidence.os.rename", side_effect=inject_at_cleanup),
            self.assertRaisesRegex(ValueError, "control document"),
        ):
            attach(self.dep, "pr")
        self.assertEqual(
            output.read_text(encoding="utf-8"),
            "preserve attachment later writer\n",
        )

    def test_same_inode_same_size_control_rewrite_blocks_attachment(self):
        self._prepare_attachable_dep()
        summary = self.dep / "summary.yaml"
        original_bytes = summary.read_bytes()
        original_stat = summary.stat()
        output = self._default_attachment_path(self.dep)
        stage = evidence_module._stage_attachment_at

        def rewrite_after_stage(directory_fd, name, data):
            temporary = stage(directory_fd, name, data)
            replacement = bytearray(original_bytes)
            replacement[-2] = ord(" ") if replacement[-2] != ord(" ") else ord("x")
            with summary.open("r+b") as stream:
                stream.write(replacement)
                stream.flush()
                os.fsync(stream.fileno())
            os.utime(
                summary,
                ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns),
            )
            return temporary

        with (
            patch("sddgov.evidence._stage_attachment_at", side_effect=rewrite_after_stage),
            self.assertRaisesRegex(ValueError, "control document bytes changed"),
        ):
            attach(self.dep, "pr")
        self.assertFalse(output.exists())

    def test_custom_attachment_publishes_to_an_absent_output(self):
        self._prepare_attachable_dep()
        output_parent = self.root / "normal-custom-output"
        output_parent.mkdir()
        output = output_parent / "pr-evidence.md"
        self.assertEqual(attach(self.dep, "pr", output=output), output)
        self.assertIn("Evidence: DEP-TEST-128", output.read_text(encoding="utf-8"))

    def test_custom_attachment_output_parent_replacement_fails_closed(self):
        self._prepare_attachable_dep()
        output_parent = self.root / "attachment-output"
        output_parent.mkdir()
        output = output_parent / "custom.md"
        parked = self.root / "attachment-output-parked"
        outside = self.root / "attachment-output-outside"
        outside.mkdir()
        external = outside / "custom.md"
        external.write_text("do not overwrite\n", encoding="utf-8")
        original = evidence_module._stage_attachment_at
        replaced = False

        def replace_parent(directory_fd, name, data):
            nonlocal replaced
            if not replaced:
                replaced = True
                output_parent.rename(parked)
                output_parent.symlink_to(outside, target_is_directory=True)
            return original(directory_fd, name, data)

        with (
            patch(
                "sddgov.evidence._stage_attachment_at", side_effect=replace_parent
            ),
            self.assertRaisesRegex(ValueError, "directory path changed"),
        ):
            attach(self.dep, "pr", output=output)
        self.assertEqual(external.read_text(encoding="utf-8"), "do not overwrite\n")

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
