import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from scripts.verify_readiness_handoff import _load_object, main, validate_workflow_run


SHA = "a" * 40
VERIFIER_SHA = "b" * 40
REPOSITORY = "owner/repository"
TAG = "v0.2.0rc1"
WORKFLOW_NAME = "release-candidate"
WORKFLOW_PATH = ".github/workflows/release-candidate.yml"


def _event():
    return {
        "action": "completed",
        "repository": {"full_name": REPOSITORY},
        "workflow_run": {
            "id": 123,
            "run_attempt": 2,
            "workflow_id": 456,
            "name": WORKFLOW_NAME,
            "path": f"{WORKFLOW_PATH}@refs/tags/{TAG}",
            "event": "workflow_dispatch",
            "status": "completed",
            "conclusion": "success",
            "head_branch": TAG,
            "head_sha": SHA,
            "repository": {"full_name": REPOSITORY},
        },
    }


def _validate(event):
    return validate_workflow_run(
        event,
        expected_repository=REPOSITORY,
        expected_run_id=123,
        expected_sha=SHA,
        expected_tag=TAG,
        expected_workflow_name=WORKFLOW_NAME,
        expected_workflow_path=WORKFLOW_PATH,
        expected_trusted_verifier_sha=VERIFIER_SHA,
    )


class ReadinessHandoffTests(unittest.TestCase):
    def test_successful_exact_run_produces_closed_handoff(self):
        self.assertEqual(
            _validate(_event()),
            {
                "schema_version": "1.1",
                "repository": REPOSITORY,
                "readiness_run_id": 123,
                "readiness_run_attempt": 2,
                "readiness_workflow_id": 456,
                "readiness_workflow_name": WORKFLOW_NAME,
                "readiness_workflow_path": WORKFLOW_PATH,
                "release_tag": TAG,
                "head_sha": SHA,
                "trusted_verifier_sha": VERIFIER_SHA,
                "artifact_name": f"distributions-{SHA}-2",
            },
        )

    def test_current_github_api_path_without_ref_suffix_is_accepted(self):
        event = _event()
        event["workflow_run"]["path"] = WORKFLOW_PATH
        self.assertEqual(_validate(event)["release_tag"], TAG)

    def test_every_authority_field_fails_closed_when_changed(self):
        changes = {
            "id": 124,
            "name": "other",
            "path": f"{WORKFLOW_PATH}@main",
            "event": "pull_request",
            "status": "in_progress",
            "conclusion": "failure",
            "head_sha": "b" * 40,
            "run_attempt": 0,
            "workflow_id": True,
            "repository": {"full_name": "other/repository"},
        }
        for field, value in changes.items():
            with self.subTest(field=field):
                event = _event()
                event["workflow_run"][field] = value
                with self.assertRaises(ValueError):
                    _validate(event)

        for field in ("run_attempt", "workflow_id"):
            with self.subTest(field=field, value="oversized"):
                event = _event()
                event["workflow_run"][field] = 1 << 63
                with self.assertRaises(ValueError):
                    _validate(event)

    def test_outer_repository_and_completed_action_are_bound(self):
        for field, value in (
            ("action", "requested"),
            ("repository", {"full_name": "other/repository"}),
        ):
            with self.subTest(field=field):
                event = _event()
                event[field] = value
                with self.assertRaises(ValueError):
                    _validate(event)

    def test_cli_creates_then_reverifies_the_same_record(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            event_path = root / "event.json"
            record_path = root / "handoff.json"
            event_path.write_text(json.dumps(_event()), encoding="utf-8")
            common = [
                "verify_readiness_handoff.py",
                "--event",
                str(event_path),
                "--repository",
                REPOSITORY,
                "--run-id",
                "123",
                "--sha",
                SHA,
                "--tag",
                TAG,
                "--trusted-verifier-sha",
                VERIFIER_SHA,
            ]
            with patch.object(sys, "argv", common + ["--output", str(record_path)]):
                self.assertEqual(main(), 0)
            with patch.object(sys, "argv", common + ["--record", str(record_path)]):
                self.assertEqual(main(), 0)

            record = json.loads(record_path.read_text(encoding="utf-8"))
            record["readiness_run_id"] = 999
            record_path.write_text(json.dumps(record), encoding="utf-8")
            output = io.StringIO()
            with patch.object(
                sys, "argv", common + ["--record", str(record_path)]
            ), redirect_stdout(output):
                self.assertEqual(main(), 1)
            self.assertIn("does not match", output.getvalue())

    def test_trusted_verifier_sha_is_exact_and_bound(self):
        with self.assertRaisesRegex(ValueError, "trusted verifier SHA"):
            validate_workflow_run(
                _event(),
                expected_repository=REPOSITORY,
                expected_run_id=123,
                expected_sha=SHA,
                expected_tag=TAG,
                expected_workflow_name=WORKFLOW_NAME,
                expected_workflow_path=WORKFLOW_PATH,
                expected_trusted_verifier_sha="main",
            )

    def test_oversized_expected_inputs_fail_closed(self):
        cases = (
            {"expected_repository": "owner/" + "r" * 101},
            {"expected_run_id": 1 << 63},
            {"expected_tag": "v" + "x" * 255},
            {"expected_workflow_name": "w" * 256},
            {
                "expected_workflow_path": ".github/workflows/"
                + "x" * 491
                + ".yml"
            },
        )
        defaults = {
            "expected_repository": REPOSITORY,
            "expected_run_id": 123,
            "expected_sha": SHA,
            "expected_tag": TAG,
            "expected_workflow_name": WORKFLOW_NAME,
            "expected_workflow_path": WORKFLOW_PATH,
            "expected_trusted_verifier_sha": VERIFIER_SHA,
        }
        for override in cases:
            with self.subTest(override=override), self.assertRaises(ValueError):
                validate_workflow_run(_event(), **(defaults | override))

    def test_event_and_handoff_files_have_independent_byte_caps(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            event = root / "event.json"
            record = root / "record.json"
            event.write_bytes(b"x" * (1024 * 1024 + 1))
            record.write_bytes(b"x" * (64 * 1024 + 1))
            with self.assertRaisesRegex(ValueError, "byte limit"):
                _load_object(event, "workflow_run event", 1024 * 1024)
            with self.assertRaisesRegex(ValueError, "byte limit"):
                _load_object(record, "release handoff record", 64 * 1024)


if __name__ == "__main__":
    unittest.main()
