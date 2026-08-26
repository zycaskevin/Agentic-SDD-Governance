import hashlib
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sddgov.redaction as redaction_module
from sddgov.fs_security import exclusive_rename_at
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

    def test_streaming_fails_closed_on_every_cross_line_sensitive_field(self):
        probes = (
            ("authorization", "multiline-token", "authorization\n:\nBearer multiline-token\n"),
            ("cookie", "multiline-cookie", "cookie\n:\nmultiline-cookie\n"),
            ("password", "multiline-password", "password\n=\nmultiline-password\n"),
            ("secret-field", "multiline-secret", "api_key\n=\nmultiline-secret\n"),
            ("patient-identifier", "patient-123", "patient_id\n=\npatient-123\n"),
            ("customer-identifier", "customer-456", "customer_id\n=\ncustomer-456\n"),
        )
        for rule_id, exposed, source_text in probes:
            with self.subTest(rule=rule_id), tempfile.TemporaryDirectory() as temporary:
                cleaned, counts = redact_text(source_text)
                self.assertNotIn(exposed, cleaned)
                self.assertEqual(counts[rule_id], 1)

                root = Path(temporary)
                source = root / "capture.log"
                output = root / "output"
                source.write_text(source_text, encoding="utf-8")
                with patch(
                    "sddgov.redaction.STREAM_CHUNK_BYTES", 3
                ), self.assertRaisesRegex(
                    ValueError, f"cross-line sensitive field.*{rule_id}"
                ):
                    redact_files([source], output)
                self.assertEqual(list(output.iterdir()), [])

    def test_cross_line_failure_removes_every_prior_call_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "first.log"
            second = root / "second.log"
            output = root / "output"
            first.write_text("owner@example.com\n", encoding="utf-8")
            second.write_text("password\n=\nmultiline-password\n", encoding="utf-8")

            with self.assertRaisesRegex(
                ValueError, "cross-line sensitive field.*password"
            ):
                redact_files([first, second], output)

            self.assertEqual(list(output.iterdir()), [])

    def test_streaming_matches_whole_text_for_multiline_quoted_sensitive_fields(self):
        probes = (
            ("password", 'password="synthetic-first\nsynthetic-second"\n'),
            ("password", "passwd='synthetic-first\nsynthetic-second'\n"),
            ("secret-field", 'api_key="synthetic-first\nsynthetic-second"\n'),
            ("secret-field", "client_secret='synthetic-first\nsynthetic-second'\n"),
        )
        for rule_id, source_text in probes:
            with self.subTest(rule=rule_id), tempfile.TemporaryDirectory() as temporary:
                expected, expected_counts = redact_text(source_text)
                root = Path(temporary)
                source = root / "capture.log"
                output = root / "output"
                source.write_text(source_text, encoding="utf-8")

                with patch("sddgov.redaction.STREAM_CHUNK_BYTES", 2):
                    report = redact_files([source], output)

                actual = (output / source.name).read_text(encoding="utf-8")
                self.assertEqual(actual, expected)
                self.assertEqual(report["totals"], expected_counts)
                self.assertNotIn("synthetic-first", actual)
                self.assertNotIn("synthetic-second", actual)

    def test_incomplete_quoted_sensitive_fields_fail_transactionally(self):
        probes = (
            (
                "unterminated",
                'password="synthetic-first\nsynthetic-second\n',
                {},
                "unterminated quoted sensitive field",
            ),
            (
                "oversized",
                'api_key="' + "x" * 40 + "\n",
                {"sddgov.redaction.MAX_CROSS_LINE_FIELD_CHARACTERS": 32},
                "quoted sensitive field exceeds",
            ),
            (
                "invalid-escape",
                'client_secret="synthetic-first\\\nsynthetic-second"\n',
                {},
                "invalid line escape",
            ),
        )
        for label, source_text, limits, error in probes:
            with self.subTest(case=label), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                first = root / "first.log"
                second = root / "second.log"
                output = root / "output"
                first.write_text("owner@example.com\n", encoding="utf-8")
                second.write_text(source_text, encoding="utf-8")
                maximum = limits.get(
                    "sddgov.redaction.MAX_CROSS_LINE_FIELD_CHARACTERS",
                    redaction_module.MAX_CROSS_LINE_FIELD_CHARACTERS,
                )
                with patch(
                    "sddgov.redaction.MAX_CROSS_LINE_FIELD_CHARACTERS", maximum
                ), patch(
                    "sddgov.redaction.STREAM_CHUNK_BYTES", 3
                ), self.assertRaisesRegex(ValueError, error):
                    redact_files([first, second], output)
                self.assertEqual(list(output.iterdir()), [])

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

    def test_masks_canonical_darwin_and_wsl_workspace_paths(self):
        source = (
            "plain=/private/var/folders/zz/T/report.json\n"
            'quoted="/private/var/folders/zz/a b/T/report.json"\n'
            'wsl="/mnt/c/Users/Kevin/My Project/report.json"\n'
            'unc="//wsl.localhost/Ubuntu/home/kevin/My Project/report.json"\n'
            'win_unc="\\\\wsl.localhost\\Ubuntu\\home\\kevin\\My Project\\report.json"\n'
            "legacy_unc=\\\\wsl$\\Ubuntu\\home\\Kevin\\My Project\\report.json\n"
        )
        cleaned, counts = redact_text(source)
        for exposed in (
            "/private/var/folders/zz/T/report.json",
            "/private/var/folders/zz/a b/T/report.json",
            "/mnt/c/Users/Kevin/My Project/report.json",
            "//wsl.localhost/Ubuntu/home/kevin/My Project/report.json",
            "\\\\wsl.localhost\\Ubuntu\\home\\kevin\\My Project\\report.json",
            "\\\\wsl$\\Ubuntu\\home\\Kevin\\My Project\\report.json",
        ):
            self.assertNotIn(exposed, cleaned)
        self.assertEqual(counts["local-path"], 6)

    def test_masks_native_and_escaped_wsl_unc_paths(self):
        native_paths = (
            r"\\wsl.localhost\Ubuntu\home\kevin\report.json",
            r"\\wsl.localhost\Ubuntu\home\kevin\My Project\report.json",
            r"\\wsl$\Ubuntu\home\kevin\report.json",
            r"\\wsl$\Ubuntu\home\kevin\My Project\report.json",
        )
        rendered = []
        for native in native_paths:
            rendered.extend((native, json.dumps(native), repr(native)))
        for value in rendered:
            with self.subTest(value=value):
                cleaned, counts = redact_text(value)
                self.assertNotIn("wsl", cleaned.casefold())
                self.assertEqual(counts["local-path"], 1)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "capture.json"
            output = root / "output"
            source.write_text("\n".join(rendered) + "\n", encoding="utf-8")
            with patch("sddgov.redaction.STREAM_CHUNK_BYTES", 3):
                report = redact_files([source], output)
            cleaned = (output / source.name).read_text(encoding="utf-8")
            self.assertNotIn("wsl", cleaned.casefold())
            self.assertEqual(report["totals"]["local-path"], len(rendered))

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

    def test_streaming_masks_darwin_and_wsl_paths_across_chunks(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "capture.log"
            output = root / "output"
            source.write_text(
                'darwin="/private/var/folders/zz/a b/T/report.json"\n'
                'wsl="/mnt/c/Users/Kevin/My Project/report.json"\n'
                'unc="//wsl.localhost/Ubuntu/home/kevin/My Project/report.json"\n'
                'win_unc="\\\\wsl.localhost\\Ubuntu\\home\\kevin\\My Project\\report.json"\n'
                "legacy_unc=\\\\wsl$\\Ubuntu\\home\\kevin\\My Project\\report.json\n",
                encoding="utf-8",
            )
            with patch("sddgov.redaction.STREAM_CHUNK_BYTES", 5):
                report = redact_files([source], output)
            cleaned = (output / source.name).read_text(encoding="utf-8")
            self.assertNotIn("/private/var/folders", cleaned)
            self.assertNotIn("/mnt/c/Users", cleaned)
            self.assertNotIn("//wsl.localhost", cleaned)
            self.assertNotIn("\\\\wsl.localhost", cleaned)
            self.assertNotIn("\\\\wsl$", cleaned)
            self.assertEqual(report["totals"]["local-path"], 5)

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

    def test_later_source_failure_removes_every_earlier_call_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "first.log"
            second = root / "second.log"
            outside = root / "outside.log"
            output = root / "output"
            first.write_text("owner@example.com\n", encoding="utf-8")
            outside.write_text("preserve me\n", encoding="utf-8")
            second.symlink_to(outside)

            with self.assertRaisesRegex(ValueError, "must not be a symlink"):
                redact_files([first, second], output)

            self.assertEqual(outside.read_text(encoding="utf-8"), "preserve me\n")
            self.assertEqual(list(output.iterdir()), [])

    def test_disappeared_or_unopenable_later_source_removes_earlier_output(self):
        for failure in ("disappeared", "unopenable"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                first = root / "first.log"
                second = root / "second.log"
                output = root / "output"
                first.write_text("owner@example.com\n", encoding="utf-8")
                if failure == "unopenable":
                    second.write_text("synthetic\n", encoding="utf-8")
                original_open = os.open

                def fail_second_open(
                    path,
                    *args,
                    _failure=failure,
                    _second=second,
                    _open=original_open,
                    **kwargs,
                ):
                    if _failure == "unopenable" and path == _second.name:
                        raise PermissionError("synthetic open failure")
                    return _open(path, *args, **kwargs)

                context = patch(
                    "sddgov.redaction.os.open", side_effect=fail_second_open
                )
                with context, self.assertRaisesRegex(
                    ValueError,
                    "source (?:disappeared|cannot be opened safely)",
                ):
                    redact_files([first, second], output)

                self.assertEqual(list(output.iterdir()), [])

    def test_later_source_failure_preserves_replacement_of_earlier_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "first.log"
            second = root / "second.log"
            outside = root / "outside.log"
            later = root / "later.log"
            output = root / "output"
            first.write_text("owner@example.com\n", encoding="utf-8")
            outside.write_text("preserve source\n", encoding="utf-8")
            later.write_text("preserve later writer\n", encoding="utf-8")
            second.symlink_to(outside)

            def replace_at_cleanup(source_fd, src, destination_fd, dst):
                if src == first.name and ".cleanup-pending-" in dst:
                    later.replace(output / first.name)
                return exclusive_rename_at(source_fd, src, destination_fd, dst)

            with patch(
                "sddgov.fs_security.exclusive_rename_at",
                side_effect=replace_at_cleanup,
            ), self.assertRaisesRegex(ValueError, "must not be a symlink"):
                redact_files([first, second], output)

            self.assertEqual(
                (output / first.name).read_text(encoding="utf-8"),
                "preserve later writer\n",
            )

    def test_source_descriptor_close_failure_removes_published_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "capture.log"
            output = root / "output"
            source.write_text("owner@example.com\n", encoding="utf-8")
            source_identity = (source.stat().st_dev, source.stat().st_ino)
            published: dict[str, tuple[int, int]] = {}
            original_close = os.close
            raised = False

            def close_then_fail(descriptor):
                nonlocal raised
                metadata = os.fstat(descriptor)
                original_close(descriptor)
                if not raised and (metadata.st_dev, metadata.st_ino) == source_identity:
                    raised = True
                    raise OSError("synthetic source descriptor close failure")

            with patch(
                "sddgov.redaction.os.close", side_effect=close_then_fail
            ), self.assertRaisesRegex(OSError, "source descriptor close failure"):
                redact_files([source], output, published_outputs=published)

            self.assertTrue(raised)
            self.assertEqual(list(output.iterdir()), [])
            self.assertEqual(published, {})

    def test_source_descriptor_close_failure_preserves_replacement(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "capture.log"
            output = root / "output"
            later = root / "later.log"
            source.write_text("owner@example.com\n", encoding="utf-8")
            later.write_text("preserve later writer\n", encoding="utf-8")
            source_identity = (source.stat().st_dev, source.stat().st_ino)
            original_close = os.close
            raised = False

            def close_then_fail(descriptor):
                nonlocal raised
                metadata = os.fstat(descriptor)
                original_close(descriptor)
                if not raised and (metadata.st_dev, metadata.st_ino) == source_identity:
                    raised = True
                    raise OSError("synthetic source descriptor close failure")

            def replace_at_cleanup(source_fd, src, destination_fd, dst):
                if src == source.name and ".cleanup-pending-" in dst:
                    later.replace(output / source.name)
                return exclusive_rename_at(source_fd, src, destination_fd, dst)

            with patch(
                "sddgov.redaction.os.close", side_effect=close_then_fail
            ), patch(
                "sddgov.fs_security.exclusive_rename_at",
                side_effect=replace_at_cleanup,
            ), self.assertRaisesRegex(OSError, "source descriptor close failure"):
                redact_files([source], output)

            self.assertTrue(raised)
            self.assertEqual(
                (output / source.name).read_text(encoding="utf-8"),
                "preserve later writer\n",
            )

    def test_later_source_close_failure_removes_current_and_prior_outputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "first.log"
            second = root / "second.log"
            output = root / "output"
            first.write_text("first@example.com\n", encoding="utf-8")
            second.write_text("second@example.com\n", encoding="utf-8")
            second_identity = (second.stat().st_dev, second.stat().st_ino)
            original_close = os.close
            raised = False

            def close_then_fail(descriptor):
                nonlocal raised
                metadata = os.fstat(descriptor)
                original_close(descriptor)
                if not raised and (metadata.st_dev, metadata.st_ino) == second_identity:
                    raised = True
                    raise OSError("synthetic second source close failure")

            with patch(
                "sddgov.redaction.os.close", side_effect=close_then_fail
            ), self.assertRaisesRegex(OSError, "second source close failure"):
                redact_files([first, second], output)

            self.assertTrue(raised)
            self.assertEqual(list(output.iterdir()), [])

    def test_output_directory_close_failure_keeps_committed_report_and_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "capture.log"
            output = root / "output"
            source.write_text("owner@example.com\n", encoding="utf-8")
            output.mkdir()
            output_identity = (output.stat().st_dev, output.stat().st_ino)
            original_close = os.close
            raised = False

            def close_then_fail(descriptor):
                nonlocal raised
                metadata = os.fstat(descriptor)
                original_close(descriptor)
                if not raised and (metadata.st_dev, metadata.st_ino) == output_identity:
                    raised = True
                    raise OSError("synthetic output directory close failure")

            with patch("sddgov.redaction.os.close", side_effect=close_then_fail):
                report = redact_files([source], output)

            cleaned = (output / source.name).read_bytes()
            self.assertTrue(raised)
            self.assertEqual(cleaned, b"[REDACTED_EMAIL]\n")
            self.assertEqual(len(report["files"]), 1)
            self.assertEqual(report["files"][0]["output_size"], len(cleaned))
            self.assertEqual(
                report["files"][0]["output_sha256"],
                hashlib.sha256(cleaned).hexdigest(),
            )
            self.assertEqual(report["totals"], {"email": 1})

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

    def test_redaction_stage_replacement_is_never_published_or_deleted(self):
        for replacement_kind in ("regular", "symlink", "hardlink", "fifo"):
            with self.subTest(replacement_kind=replacement_kind), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                source = root / "capture.log"
                output = root / "output"
                source.write_text("password=synthetic\n", encoding="utf-8")
                original_link = os.link
                swapped_name = ""

                def replace_before_claim(src, dst, *args, **kwargs):
                    nonlocal swapped_name
                    if (
                        not swapped_name
                        and str(src).startswith(".sddgov.redaction-stage-")
                        and str(dst).startswith(".sddgov.redaction-claim-")
                    ):
                        directory_fd = kwargs["src_dir_fd"]
                        swapped_name = str(src)
                        os.unlink(src, dir_fd=directory_fd)
                        if replacement_kind == "regular":
                            descriptor = os.open(
                                src,
                                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                                0o600,
                                dir_fd=directory_fd,
                            )
                            try:
                                os.write(descriptor, b"FORGED REDACTION\n")
                            finally:
                                os.close(descriptor)
                        elif replacement_kind == "symlink":
                            os.symlink("attacker-target", src, dir_fd=directory_fd)
                        elif replacement_kind == "hardlink":
                            attacker_name = ".attacker-redaction-source"
                            descriptor = os.open(
                                attacker_name,
                                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                                0o600,
                                dir_fd=directory_fd,
                            )
                            try:
                                os.write(descriptor, b"FORGED HARDLINK\n")
                            finally:
                                os.close(descriptor)
                            original_link(
                                attacker_name,
                                src,
                                src_dir_fd=directory_fd,
                                dst_dir_fd=directory_fd,
                                follow_symlinks=False,
                            )
                        else:
                            os.mkfifo(output / str(src), 0o600)
                    return original_link(src, dst, *args, **kwargs)

                with (
                    patch("sddgov.redaction.os.link", side_effect=replace_before_claim),
                    self.assertRaises(ValueError),
                ):
                    redact_files([source], output)
                self.assertTrue(swapped_name)
                self.assertFalse((output / source.name).exists())
                preserved = list(output.iterdir())
                self.assertTrue(
                    any(
                        path.is_symlink()
                        or stat.S_ISFIFO(path.lstat().st_mode)
                        or (
                            path.is_file()
                            and b"FORGED" in path.read_bytes()
                        )
                        for path in preserved
                    ),
                    preserved,
                )

    def test_redaction_stage_close_failure_preserves_replacement(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "capture.log"
            output = root / "output"
            source.write_text("password=synthetic\n", encoding="utf-8")
            source_identity = (source.stat().st_dev, source.stat().st_ino)
            original_close = os.close
            original_rename = os.rename
            replacement = b"later staging generation\n"
            swapped_name = ""
            failed = False

            def close_then_replace_and_fail(descriptor: int) -> None:
                nonlocal failed, swapped_name
                metadata = os.fstat(descriptor)
                identity = (metadata.st_dev, metadata.st_ino)
                if stat.S_ISREG(metadata.st_mode) and identity != source_identity and not failed:
                    stage = next(output.glob(".sddgov.redaction-stage-*"))
                    swapped_name = stage.name
                    original_rename(stage, output / ".owned-redaction-stage")
                    stage.write_bytes(replacement)
                    failed = True
                    original_close(descriptor)
                    raise OSError("synthetic redaction stage close failure")
                original_close(descriptor)

            with patch(
                "sddgov.redaction.os.close", side_effect=close_then_replace_and_fail
            ), self.assertRaisesRegex(OSError, "redaction stage close failure"):
                redact_files([source], output)

            self.assertTrue(failed)
            self.assertFalse((output / source.name).exists())
            self.assertEqual((output / swapped_name).read_bytes(), replacement)
            self.assertEqual(
                (output / ".owned-redaction-stage").read_bytes(),
                b"password=[REDACTED_PASSWORD]\n",
            )

    def test_supplied_output_dirfd_performs_no_output_path_operations(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "capture.log"
            output = root / "retained-output"
            source.write_text("owner@example.com\n", encoding="utf-8")
            output.mkdir()
            source_fd = os.open(
                root, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
            )
            output_fd = os.open(
                output, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
            )
            try:
                with patch.object(
                    Path,
                    "is_symlink",
                    side_effect=AssertionError("unexpected pathname read"),
                ), patch.object(
                    Path,
                    "mkdir",
                    side_effect=AssertionError("unexpected pathname write"),
                ):
                    report = redact_files(
                        [source],
                        root / "attacker-controlled-alias",
                        source_dir_fd=source_fd,
                        output_dir_fd=output_fd,
                    )
            finally:
                os.close(output_fd)
                os.close(source_fd)

            self.assertEqual(report["totals"], {"email": 1})
            self.assertEqual(
                (output / source.name).read_text(encoding="utf-8"),
                "[REDACTED_EMAIL]\n",
            )

    def test_owned_output_rejects_a_symlinked_parent_without_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "capture.log"
            outside = root / "outside"
            alias = root / "alias"
            source.write_text("owner@example.com\n", encoding="utf-8")
            outside.mkdir()
            alias.symlink_to(outside, target_is_directory=True)

            with self.assertRaises((OSError, ValueError)):
                redact_files([source], alias / "output")

            self.assertEqual(list(outside.iterdir()), [])

    def test_owned_output_parent_disappearance_rolls_back_publication(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "capture.log"
            output = root / "output"
            parked = root / "output-parked"
            source.write_text("owner@example.com\n", encoding="utf-8")
            original = redaction_module.require_directory_path_identity
            moved = False

            def move_before_commit(path, descriptor, label):
                nonlocal moved
                if label == "redaction output directory" and not moved:
                    moved = True
                    output.rename(parked)
                return original(path, descriptor, label)

            with (
                patch(
                    "sddgov.redaction.require_directory_path_identity",
                    side_effect=move_before_commit,
                ),
                self.assertRaisesRegex(ValueError, "changed during operation"),
            ):
                redact_files([source], output)

            self.assertTrue(moved)
            self.assertEqual(list(parked.iterdir()), [])

    def test_owned_output_parent_replacement_preserves_a_later_writer(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "capture.log"
            output = root / "output"
            parked = root / "output-parked"
            outside = root / "outside"
            later = root / "later.log"
            source.write_text("owner@example.com\n", encoding="utf-8")
            outside.mkdir()
            later.write_text("later writer\n", encoding="utf-8")
            original = redaction_module.require_directory_path_identity
            moved = False

            def replace_before_commit(path, descriptor, label):
                nonlocal moved
                if label == "redaction output directory" and not moved:
                    moved = True
                    output.rename(parked)
                    output.symlink_to(outside, target_is_directory=True)
                    later.replace(parked / source.name)
                return original(path, descriptor, label)

            with (
                patch(
                    "sddgov.redaction.require_directory_path_identity",
                    side_effect=replace_before_commit,
                ),
                self.assertRaisesRegex(ValueError, "changed during operation"),
            ):
                redact_files([source], output)

            self.assertEqual(list(outside.iterdir()), [])
            self.assertEqual(
                (parked / source.name).read_text(encoding="utf-8"),
                "later writer\n",
            )

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

    def test_masks_home_paths_and_removes_trailing_whitespace(self):
        source = (
            '  File "/home/example/private/project/test_runner.py", line 10   \n'
            "  File '/Users/example/private/project/test_runner.py', line 11\t\n"
        )
        cleaned, counts = redact_text(source)
        self.assertNotIn("/home/example", cleaned)
        self.assertNotIn("/Users/example", cleaned)
        for line in cleaned.splitlines():
            self.assertEqual(line, line.rstrip())
        self.assertEqual(counts["local-path"], 2)
        self.assertEqual(counts["trailing-whitespace"], 2)

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
