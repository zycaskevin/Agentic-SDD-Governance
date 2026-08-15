import json
import sys
import tempfile
import unittest
from pathlib import Path

from sddgov.ci_guard import run_local_gate, verify_guard


def _contract(command):
    return {
        "schema_version": "1.0",
        "profile": "team-standard",
        "local_green": {"environment": {}, "commands": [command]},
        "hosted": {
            "max_runs_per_work_package": 1,
            "max_reruns_per_revision": 1,
            "expected_minutes": 5,
            "full_matrix": "manual_or_ready_for_review",
        },
        "workflow_controls": {
            "require_concurrency": True,
            "cancel_in_progress": True,
            "require_job_timeouts": True,
            "require_read_only_permissions": True,
            "skip_draft_pull_requests": True,
            "exempt_workflows": [],
        },
    }


def _write_project(project: Path, contract, workflow: str) -> None:
    state = project / ".sddgov"
    state.mkdir(parents=True)
    (state / "ci-cost-guard.json").write_text(
        json.dumps(contract, indent=2) + "\n", encoding="utf-8"
    )
    workflows = project / ".github/workflows"
    workflows.mkdir(parents=True)
    (workflows / "ci.yml").write_text(workflow, encoding="utf-8")


GOOD_WORKFLOW = """name: CI
on:
  pull_request:
    types: [opened, synchronize, reopened, ready_for_review, converted_to_draft]
  push:
    branches: [main]
permissions:
  contents: read
concurrency:
  group: ci-${{ github.event.pull_request.number || github.ref }}
  cancel-in-progress: true
jobs:
  verify:
    if: github.event_name != 'pull_request' || github.event.pull_request.draft == false
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - run: true
"""


class CICostGuardTests(unittest.TestCase):
    def test_verify_and_local_gate(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            _write_project(project, _contract([sys.executable, "-c", "print('green')"]), GOOD_WORKFLOW)
            self.assertTrue(verify_guard(project)["ok"])
            result = run_local_gate(project)
            self.assertTrue(result["ok"])
            self.assertEqual(result["commands"][0]["returncode"], 0)

    def test_missing_controls_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            workflow = """name: CI
on:
  pull_request:
jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - run: true
"""
            _write_project(project, _contract([sys.executable, "-c", "pass"]), workflow)
            report = verify_guard(project)
            self.assertFalse(report["ok"])
            text = "\n".join(report["errors"])
            self.assertIn("permissions", text)
            self.assertIn("concurrency", text)
            self.assertIn("cancel stale", text)
            self.assertIn("Draft PR", text)
            self.assertIn("ready_for_review", text)
            self.assertIn("timeout-minutes", text)

    def test_every_pull_request_job_must_skip_drafts(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            workflow = GOOD_WORKFLOW + """
  second:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - run: true
"""
            _write_project(project, _contract([sys.executable, "-c", "pass"]), workflow)
            report = verify_guard(project)
            self.assertFalse(report["ok"])
            self.assertIn(
                "pull-request job second must skip Draft PR runners",
                "\n".join(report["errors"]),
            )

    def test_draft_conversion_must_cancel_the_active_pull_request_run(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            workflow = GOOD_WORKFLOW.replace(", converted_to_draft", "")
            _write_project(project, _contract([sys.executable, "-c", "pass"]), workflow)
            report = verify_guard(project)
            self.assertFalse(report["ok"])
            self.assertIn(
                "pull_request types must include converted_to_draft",
                "\n".join(report["errors"]),
            )

    def test_comments_cannot_fake_types_or_hide_job_write_permissions(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            hostile = """name: CI
on:
  pull_request:
    types: [opened, synchronize]
# ready_for_review converted_to_draft
permissions:
  contents: read
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true
jobs:
  verify:
    if: github.event_name != 'pull_request' || github.event.pull_request.draft == false
    permissions:
      contents: write
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - run: true
"""
            _write_project(
                project,
                _contract([sys.executable, "-c", "pass"]),
                hostile,
            )
            report = verify_guard(project)
            self.assertFalse(report["ok"])
            text = "\n".join(report["errors"])
            self.assertIn("ready_for_review", text)
            self.assertIn("converted_to_draft", text)
            self.assertIn("job verify permissions", text)

    def test_duplicate_yaml_keys_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            duplicate = GOOD_WORKFLOW.replace(
                "permissions:\n  contents: read",
                "permissions:\n  contents: read\npermissions:\n  contents: write",
            )
            _write_project(
                project,
                _contract([sys.executable, "-c", "pass"]),
                duplicate,
            )
            report = verify_guard(project)
            self.assertFalse(report["ok"])
            self.assertIn("duplicate key", "\n".join(report["errors"]))

    def test_contract_rejects_shell_string_and_local_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            bad = _contract("python3 -c pass")
            _write_project(project, bad, GOOD_WORKFLOW)
            self.assertFalse(verify_guard(project)["ok"])

        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            contract = _contract([sys.executable, "-c", "raise SystemExit(7)"])
            _write_project(project, contract, GOOD_WORKFLOW)
            with self.assertRaisesRegex(ValueError, "local Green Gate failed"):
                run_local_gate(project)


if __name__ == "__main__":
    unittest.main()
