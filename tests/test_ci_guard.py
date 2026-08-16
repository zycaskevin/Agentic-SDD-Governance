import json
import os
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
            "post_merge_verification": "manual_only",
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
  workflow_dispatch:
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

    def test_manual_only_post_merge_verification_rejects_automatic_push(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            workflow = GOOD_WORKFLOW.replace(
                "  workflow_dispatch:\n",
                "  push:\n    branches: [main]\n  workflow_dispatch:\n",
            )
            _write_project(
                project,
                _contract([sys.executable, "-c", "pass"]),
                workflow,
            )
            report = verify_guard(project)
            self.assertFalse(report["ok"])
            self.assertIn(
                "manual-only post-merge verification forbids automatic push",
                "\n".join(report["errors"]),
            )

    def test_manual_only_push_cannot_hide_behind_workflow_exemption(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            contract = _contract([sys.executable, "-c", "pass"])
            contract["workflow_controls"]["exempt_workflows"] = ["ci.yml"]
            workflow = GOOD_WORKFLOW.replace(
                "  workflow_dispatch:\n",
                "  push:\n    branches: [main]\n  workflow_dispatch:\n",
            )
            _write_project(project, contract, workflow)
            report = verify_guard(project)
            self.assertFalse(report["ok"])
            self.assertIn(
                "manual-only post-merge verification forbids automatic push",
                "\n".join(report["errors"]),
            )

    def test_v1_contract_defaults_missing_post_merge_policy_to_automatic(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            contract = _contract([sys.executable, "-c", "pass"])
            del contract["hosted"]["post_merge_verification"]
            workflow = GOOD_WORKFLOW.replace(
                "  workflow_dispatch:\n",
                "  push:\n    branches: [main]\n  workflow_dispatch:\n",
            )
            _write_project(project, contract, workflow)
            self.assertTrue(verify_guard(project)["ok"])

    def test_invalid_contract_mappings_fail_closed_without_exception(self):
        for key in ("hosted", "workflow_controls"):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as temporary:
                project = Path(temporary)
                contract = _contract([sys.executable, "-c", "pass"])
                contract[key] = "invalid"
                _write_project(project, contract, GOOD_WORKFLOW)
                report = verify_guard(project)
                self.assertFalse(report["ok"])
                self.assertIn(f"{key} must be an object", "\n".join(report["errors"]))

    def test_invalid_exemption_entry_returns_structured_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            contract = _contract([sys.executable, "-c", "pass"])
            contract["workflow_controls"]["exempt_workflows"] = [{}]
            _write_project(project, contract, GOOD_WORKFLOW)
            report = verify_guard(project)
            self.assertFalse(report["ok"])
            self.assertIn(
                "workflow_controls.exempt_workflows must be a string array",
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

    def test_draft_guard_must_not_be_hidden_inside_always_true_expression(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            hostile = GOOD_WORKFLOW.replace(
                "github.event_name != 'pull_request' || github.event.pull_request.draft == false",
                "true || github.event_name != 'pull_request' || github.event.pull_request.draft == false",
            )
            _write_project(project, _contract([sys.executable, "-c", "pass"]), hostile)
            report = verify_guard(project)
            self.assertFalse(report["ok"])
            self.assertIn("exact guard", "\n".join(report["errors"]))

    def test_runner_and_concurrency_values_are_semantically_validated(self):
        cases = {
            "null runner": GOOD_WORKFLOW.replace(
                "runs-on: ubuntu-latest", "runs-on: null"
            ),
            "missing group": GOOD_WORKFLOW.replace(
                "  group: ci-${{ github.event.pull_request.number || github.ref }}\n",
                "",
            ),
        }
        for label, workflow in cases.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temporary:
                project = Path(temporary)
                _write_project(
                    project,
                    _contract([sys.executable, "-c", "pass"]),
                    workflow,
                )
                self.assertFalse(verify_guard(project)["ok"])

    def test_non_mapping_job_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            hostile = GOOD_WORKFLOW.replace(
                "  verify:\n",
                "  invalid: external-workflow-reference\n  verify:\n",
            )
            _write_project(project, _contract([sys.executable, "-c", "pass"]), hostile)
            report = verify_guard(project)
            self.assertFalse(report["ok"])
            self.assertIn("every job must be a named mapping", "\n".join(report["errors"]))

    def test_yaml_11_boolean_alias_cannot_hide_duplicate_on_key(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            hostile = GOOD_WORKFLOW.replace(
                "permissions:\n  contents: read",
                '"on": push\npermissions:\n  contents: read',
            )
            _write_project(project, _contract([sys.executable, "-c", "pass"]), hostile)
            report = verify_guard(project)
            self.assertFalse(report["ok"])
            self.assertIn("duplicate key", "\n".join(report["errors"]))

    def test_workflow_parent_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            project = base / "project"
            external = base / "external"
            project.mkdir()
            external.mkdir()
            state = project / ".sddgov"
            state.mkdir()
            (state / "ci-cost-guard.json").write_text(
                json.dumps(_contract([sys.executable, "-c", "pass"])),
                encoding="utf-8",
            )
            (external / "workflows").mkdir()
            (external / "workflows/ci.yml").write_text(
                GOOD_WORKFLOW, encoding="utf-8"
            )
            (project / ".github").symlink_to(external, target_is_directory=True)
            report = verify_guard(project)
            self.assertFalse(report["ok"])
            self.assertIn("unsafe", "\n".join(report["errors"]))

    def test_workflow_leaf_symlink_and_hardlink_are_rejected(self):
        for kind in ("symlink", "hardlink"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                base = Path(temporary)
                project = base / "project"
                external = base / "external.yml"
                external.write_text(GOOD_WORKFLOW, encoding="utf-8")
                _write_project(
                    project,
                    _contract([sys.executable, "-c", "pass"]),
                    GOOD_WORKFLOW,
                )
                target = project / ".github/workflows/ci.yml"
                target.unlink()
                if kind == "symlink":
                    target.symlink_to(external)
                else:
                    os.link(external, target)
                report = verify_guard(project)
                self.assertFalse(report["ok"])
                self.assertIn("single-linked regular file", "\n".join(report["errors"]))

    def test_ci_contract_symlink_and_hardlink_are_rejected(self):
        for kind in ("symlink", "hardlink"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                base = Path(temporary)
                project = base / "project"
                _write_project(
                    project,
                    _contract([sys.executable, "-c", "pass"]),
                    GOOD_WORKFLOW,
                )
                contract = project / ".sddgov/ci-cost-guard.json"
                external = base / "external-contract.json"
                external.write_bytes(contract.read_bytes())
                contract.unlink()
                if kind == "symlink":
                    contract.symlink_to(external)
                else:
                    os.link(external, contract)
                with self.assertRaises((ValueError, OSError)):
                    verify_guard(project)

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
