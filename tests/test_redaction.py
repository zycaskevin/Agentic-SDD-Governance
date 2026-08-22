import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sddgov.redaction as redaction_module
from sddgov.redaction import (
    MAX_LOGICAL_LINE_CHARACTERS,
    MAX_REDACTION_FILE_BYTES,
    STREAM_RULES,
    redact_files,
    redact_text,
)


class RedactionTests(unittest.TestCase):
    def test_masks_credentials_and_identifiers(self):
        source = (
            "Authorization: Bearer abc.def.ghi\n"
            "Cookie: session=secret\n"
            "api_key=sk-example-secret\n"
            "owner@example.com\n"
        )
        cleaned, counts = redact_text(source)
        self.assertNotIn("abc.def.ghi", cleaned)
        self.assertNotIn("session=secret", cleaned)
        self.assertNotIn("sk-example-secret", cleaned)
        self.assertNotIn("owner@example.com", cleaned)
        self.assertIn("authorization", counts)
        self.assertIn("cookie", counts)
        self.assertIn("secret-field", counts)
        self.assertIn("email", counts)

    def test_removes_private_key_block(self):
        source = "-----BEGIN " + "PRIVATE KEY-----\nsecret\n-----END " + "PRIVATE KEY-----"
        cleaned, counts = redact_text(source)
        self.assertEqual(cleaned, "[REDACTED_PRIVATE_KEY]")
        self.assertEqual(counts["private-key"], 1)

    def test_masks_explicit_password_patient_and_customer_identifiers(self):
        source = (
            "password=correct-horse\n"
            "patient_id=patient-123\n"
            "customer_identifier: customer-456\n"
        )
        cleaned, counts = redact_text(source)
        self.assertNotIn("correct-horse", cleaned)
        self.assertNotIn("patient-123", cleaned)
        self.assertNotIn("customer-456", cleaned)
        self.assertEqual(counts["password"], 1)
        self.assertEqual(counts["patient-identifier"], 1)
        self.assertEqual(counts["customer-identifier"], 1)

    def test_masks_quoted_json_keys_and_escaped_quoted_values(self):
        source = (
            r'''{"password":"correct-\"horse","api_key":"sk-\"secret",'''
            r'''"patient_id":"patient-\"123","customer_identifier":"customer-\"456"}'''
        )
        cleaned, counts = redact_text(source)
        for fragment in ("correct", "sk-", "patient-", "customer-"):
            self.assertNotIn(fragment, cleaned)
        self.assertEqual(counts["password"], 1)
        self.assertEqual(counts["secret-field"], 1)
        self.assertEqual(counts["patient-identifier"], 1)
        self.assertEqual(counts["customer-identifier"], 1)

    def test_masks_uppercase_snake_case_credentials(self):
        source = (
            "DB_PASSWORD=database-secret\n"
            "SECRET_KEY=signing-secret\n"
            "ACCESS_KEY=provider-secret\n"
            "secret-key=hyphen-secret\n"
            "AWS_ACCESS_KEY_ID=aws-secret\n"
        )
        cleaned, counts = redact_text(source)
        for fragment in (
            "database-secret",
            "signing-secret",
            "provider-secret",
            "hyphen-secret",
            "aws-secret",
        ):
            self.assertNotIn(fragment, cleaned)
        self.assertEqual(counts["password"], 1)
        self.assertEqual(counts["secret-field"], 4)

    def test_masks_known_provider_credential_identifiers(self):
        source = (
            "aws_access_key_id=AKIAIOSFODNN7EXAMPLE\n"
            "github_token=ghp_0123456789abcdefghijklmnopqrstuvwxyzAB\n"
            "ordinary synthetic sentence with no credential\n"
        )
        cleaned, counts = redact_text(source)
        self.assertNotIn("AKIAIOSFODNN7EXAMPLE", cleaned)
        self.assertNotIn("ghp_0123456789abcdefghijklmnopqrstuvwxyzAB", cleaned)
        self.assertGreaterEqual(counts.get("provider-credential", 0), 2)
        self.assertIn("ordinary synthetic sentence", cleaned)

    def test_clean_zero_match_text_remains_eligible(self):
        source = "Synthetic test completed with no credentials."
        cleaned, counts = redact_text(source)
        self.assertEqual(cleaned, source)
        self.assertEqual(counts, {})

    def test_masks_absolute_user_workspace_paths(self):
        source = (
            '  File "/home/alice/work/repository/tests/test_demo.py", line 7\n'
            '  File "/Users/bob/source/repository/src/module.py", line 9\n'
            'project=C:\\Users\\carol\\workspace\\repository\n'
            r'traceback=C:\\Users\\dana\\workspace\\repository\\module.py' + "\n"
            "slash=C:/Users/erin/workspace/repository/module.py\n"
        )
        cleaned, counts = redact_text(source)
        for exposed in (
            "/home/alice",
            "/Users/bob",
            "C:\\Users\\carol",
            r"C:\\Users\\dana",
            "C:/Users/erin",
        ):
            self.assertNotIn(exposed, cleaned)
        self.assertEqual(cleaned.count("[REDACTED_LOCAL_PATH]"), 5)
        self.assertEqual(counts["local-path"], 5)
        self.assertIn("slash=[REDACTED_LOCAL_PATH]\n", cleaned)

    def test_masks_temporary_paths_and_paths_with_spaces(self):
        source = (
            'artifact="/tmp/SDG Build/input.whl"\n'
            "raw=/private/tmp/sddgov-run/output.log\n"
            'cache="/var/folders/zz/a b/T/report.json"\n'
            'home="/home/alice/My Project/result.json"\n'
            "ordinary=/tmpfile-is-not-a-temp-path\n"
        )
        cleaned, counts = redact_text(source)
        for exposed in (
            "/tmp/SDG Build/input.whl",
            "/private/tmp/sddgov-run/output.log",
            "/var/folders/zz/a b/T/report.json",
            "/home/alice/My Project/result.json",
        ):
            self.assertNotIn(exposed, cleaned)
        self.assertIn("/tmpfile-is-not-a-temp-path", cleaned)
        self.assertEqual(counts["local-path"], 4)

    def test_streaming_masks_space_containing_temporary_path_across_chunks(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "capture.log"
            output = root / "output"
            source.write_text(
                'failure="/tmp/SDG Build/input.whl"\n', encoding="utf-8"
            )
            with patch("sddgov.redaction.STREAM_CHUNK_BYTES", 7):
                report = redact_files([source], output)
            cleaned = (output / source.name).read_text(encoding="utf-8")
            self.assertNotIn("SDG Build/input.whl", cleaned)
            self.assertEqual(report["totals"]["local-path"], 1)

    def test_streaming_masks_user_workspace_paths_across_chunks(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "capture.log"
            output = root / "output"
            source.write_text(
                '  File "/home/alice/work/repository/tests/test_demo.py", line 7\n'
                "project=C:/Users/erin/workspace/repository/module.py\n",
                encoding="utf-8",
            )
            with patch("sddgov.redaction.STREAM_CHUNK_BYTES", 7):
                report = redact_files([source], output)
            cleaned = (output / source.name).read_text(encoding="utf-8")
            self.assertNotIn("/home/alice", cleaned)
            self.assertNotIn("C:/Users/erin", cleaned)
            self.assertIn("project=[REDACTED_LOCAL_PATH]\n", cleaned)
            self.assertIn("[REDACTED_LOCAL_PATH]", cleaned)
            self.assertEqual(report["totals"]["local-path"], 2)

    def test_streaming_redacts_secrets_and_private_keys_across_chunks(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            output = root / "output"
            source.mkdir()
            credential = "ghp_0123456789abcdefghijklmnopqrstuvwxyzAB"
            raw = (
                "prefix\n"
                f"github_token={credential}\n"
                "-----BEGIN " + "PRIVATE KEY-----\n"
                "synthetic-private-material\n"
                "-----END " + "PRIVATE KEY-----\n"
                "owner@example.com\n"
            )
            path = source / "capture.log"
            path.write_text(raw, encoding="utf-8")

            with patch("sddgov.redaction.STREAM_CHUNK_BYTES", 7):
                report = redact_files([path], output)

            cleaned = (output / path.name).read_text(encoding="utf-8")
            for exposed in (
                credential,
                "synthetic-private-material",
                "owner@example.com",
            ):
                self.assertNotIn(exposed, cleaned)
            self.assertIn("[REDACTED_PROVIDER_CREDENTIAL]", cleaned)
            self.assertIn("[REDACTED_PRIVATE_KEY]", cleaned)
            self.assertEqual(report["totals"]["private-key"], 1)
            self.assertEqual(report["totals"]["provider-credential"], 1)

    def test_streaming_redacts_private_key_markers_split_across_lines(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            output = root / "output"
            source.mkdir()
            raw = (
                "prefix\n"
                "-----BEGIN \n" + "PRIVATE KEY-----\n"
                "synthetic-private-material\n"
                "-----END \n" + "PRIVATE KEY-----\n"
                "suffix\n"
            )
            path = source / "capture.log"
            path.write_text(raw, encoding="utf-8")

            with patch("sddgov.redaction.STREAM_CHUNK_BYTES", 5):
                report = redact_files([path], output)

            cleaned = (output / path.name).read_text(encoding="utf-8")
            self.assertNotIn("synthetic-private-material", cleaned)
            self.assertIn("[REDACTED_PRIVATE_KEY]", cleaned)
            self.assertEqual(report["totals"]["private-key"], 1)
            validated, remaining = redact_text(cleaned)
            self.assertEqual(validated, cleaned)
            self.assertEqual(remaining, {})

    def test_partial_private_key_delimiter_split_across_lines_fails_closed(self):
        for first, second in (
            ("-", "----BEGIN"),
            ("--", "---BEGIN"),
            ("---", "--BEGIN"),
            ("----", "-BEGIN"),
        ):
            with self.subTest(first=first), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                source = root / "capture.log"
                output = root / "output"
                source.write_text(
                    f"{first}\n{second} PRIVATE KEY-----\n"
                    "synthetic-private-material\n"
                    "-----END PRIVATE KEY-----\n",
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(ValueError, "private key marker"):
                    redact_files([source], output)
                self.assertFalse((output / source.name).exists())

    def test_dash_only_test_separator_is_not_a_private_key_marker(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "capture.log"
            output = root / "output"
            separator = "-\nordinary output\n" + "-" * 70 + "\n"
            source.write_text(separator, encoding="utf-8")
            report = redact_files([source], output)
            self.assertEqual((output / source.name).read_text(), separator)
            self.assertEqual(report["totals"], {})

    def test_oversized_file_fails_before_redaction_output_is_created(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "large.log"
            output = root / "output"
            with source.open("wb") as handle:
                handle.truncate(MAX_REDACTION_FILE_BYTES + 1)
            with self.assertRaisesRegex(ValueError, "collect a bounded excerpt or summary"):
                redact_files([source], output)
            self.assertFalse((output / source.name).exists())

    def test_streaming_rules_exclude_private_keys_by_identity(self):
        self.assertNotIn("private-key", {rule.rule_id for rule in STREAM_RULES})

    def test_oversized_logical_line_with_newline_publishes_no_output(self):
        self._assert_oversized_logical_line_fails("\n")

    def test_oversized_logical_line_without_newline_publishes_no_output(self):
        self._assert_oversized_logical_line_fails("")

    def _assert_oversized_logical_line_fails(self, terminator: str):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "capture.log"
            output = root / "output"
            source.write_text("x" * 65 + terminator, encoding="utf-8")
            with patch("sddgov.redaction.MAX_LOGICAL_LINE_CHARACTERS", 64), patch(
                "sddgov.redaction.STREAM_CHUNK_BYTES", 8
            ):
                with self.assertRaisesRegex(ValueError, "logical line exceeding 64"):
                    redact_files([source], output)
            self.assertFalse((output / source.name).exists())
            self.assertEqual(MAX_LOGICAL_LINE_CHARACTERS, 1024 * 1024)

    def test_unterminated_private_key_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "capture.log"
            output = root / "output"
            source.write_text(
                "-----BEGIN PRIVATE KEY-----\nnot-terminated\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "unterminated private key"):
                redact_files([source], output)
            self.assertFalse((output / source.name).exists())

    def test_cross_chunk_private_key_preserves_unicode_before_marker(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "capture.log"
            output = root / "output"
            source.write_text(
                "ß-----begin \nprivate key-----\nsecret\n-----end private key-----\n",
                encoding="utf-8",
            )
            with patch("sddgov.redaction.STREAM_CHUNK_BYTES", 12):
                report = redact_files([source], output)
            cleaned = (output / source.name).read_text(encoding="utf-8")
            self.assertEqual(cleaned, "ß[REDACTED_PRIVATE_KEY]\n")
            self.assertEqual(report["totals"]["private-key"], 1)

    def test_streaming_destination_symlink_is_rejected_without_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "capture.log"
            output = root / "output"
            outside = root / "outside.log"
            source.write_text("password=synthetic\n", encoding="utf-8")
            outside.write_text("preserve me\n", encoding="utf-8")
            output.mkdir()
            (output / source.name).symlink_to(outside)

            with self.assertRaisesRegex(ValueError, "must not be a symlink"):
                redact_files([source], output)
            self.assertEqual(outside.read_text(encoding="utf-8"), "preserve me\n")

    def test_failed_post_publish_validation_removes_only_owned_generation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "capture.log"
            output = root / "output"
            source.write_text("password=synthetic\n", encoding="utf-8")

            with patch(
                "sddgov.redaction._validate_published_identity",
                side_effect=ValueError("synthetic post-publish validation failure"),
            ), self.assertRaisesRegex(ValueError, "post-publish validation failure"):
                redact_files([source], output)

            self.assertFalse((output / source.name).exists())
            self.assertEqual(list(output.iterdir()), [])

    def test_failed_post_publish_validation_preserves_changed_generation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "capture.log"
            output = root / "output"
            source.write_text("password=synthetic\n", encoding="utf-8")
            later = b"later writer generation\n"

            def replace_generation(directory_fd, name, _temporary_metadata):
                os.unlink(name, dir_fd=directory_fd)
                descriptor = os.open(
                    name,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                    0o600,
                    dir_fd=directory_fd,
                )
                try:
                    os.write(descriptor, later)
                finally:
                    os.close(descriptor)
                raise ValueError("synthetic changed generation")

            with patch(
                "sddgov.redaction._validate_published_identity",
                side_effect=replace_generation,
            ), self.assertRaisesRegex(ValueError, "changed generation"):
                redact_files([source], output)

            self.assertEqual((output / source.name).read_bytes(), later)

    def test_source_identity_failure_reconciles_the_published_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "capture.log"
            output = root / "output"
            source.write_text("password=synthetic\n", encoding="utf-8")
            stream_text_at = redaction_module._stream_text_at

            def mutate_source_after_publish(*args, **kwargs):
                result = stream_text_at(*args, **kwargs)
                source.write_text(
                    "password=synthetic changed after publish\n", encoding="utf-8"
                )
                return result

            with patch(
                "sddgov.redaction._stream_text_at",
                side_effect=mutate_source_after_publish,
            ), self.assertRaisesRegex(ValueError, "source changed during read"):
                redact_files([source], output)

            self.assertFalse((output / source.name).exists())
            self.assertEqual(list(output.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
