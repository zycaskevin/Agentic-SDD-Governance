import json
import re
import unittest
from pathlib import Path

import yaml

from sddgov.cli import _validate_repo


ROOT = Path(__file__).resolve().parents[1]


class RepositoryContractTests(unittest.TestCase):
    def test_repository_assets_validate(self):
        self.assertEqual(_validate_repo(ROOT), [])

    def test_skill_is_thin_and_routes_one_level_references(self):
        skill = ROOT / "skill/agentic-sdd-governance/SKILL.md"
        lines = skill.read_text(encoding="utf-8").splitlines()
        self.assertLess(len(lines), 150)
        text = "\n".join(lines)
        self.assertIn("references/evidence-workflow.md", text)
        self.assertIn("references/autonomy-workflow.md", text)
        self.assertIn("references/independent-reviewer.md", text)
        self.assertNotIn("# Evidence-Driven SDD", text)

    def test_json_schemas_are_parseable(self):
        for path in (ROOT / "schemas").glob("*.json"):
            with self.subTest(path=path.name):
                json.loads(path.read_text(encoding="utf-8"))

    def test_dep_security_boundary_objects_reject_unknown_fields(self):
        schema = json.loads(
            (ROOT / "schemas/debug-evidence-package.schema.json").read_text(encoding="utf-8")
        )
        self.assertFalse(schema["additionalProperties"])
        history = schema["properties"]["workflow"]["properties"]["history"]
        self.assertEqual(history["minItems"], 1)
        self.assertEqual(history["maxItems"], 5)
        self.assertFalse(history["items"]["additionalProperties"])
        self.assertFalse(
            schema["properties"]["attachments"]["items"]["additionalProperties"]
        )

    def test_adapters_route_to_canonical_skill(self):
        codex = (ROOT / "adapters/codex/AGENTS.md").read_text(encoding="utf-8")
        hermes = (ROOT / "adapters/hermes/AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("agentic-sdd-governance", codex)
        self.assertIn("agentic-sdd-governance", hermes)
        self.assertIn("Red -> Evidence -> Fix -> Green -> Proof", codex)
        self.assertIn("sddgov reviewer bootstrap", codex)
        self.assertIn("sddgov reviewer bootstrap", hermes)

    def test_packaged_hard_gate_assets_match_canonical_sources(self):
        paths = (
            "docs/HARD_GATES_V1_2.md",
            "policies/autonomy-policy.json",
            "policies/protected-files.yaml",
            "schemas/autonomy-policy.schema.json",
            "schemas/decision-record.schema.json",
            "schemas/merge-gate.schema.json",
            "schemas/operation-approval-receipt.schema.json",
            "schemas/runtime-context.schema.json",
            "schemas/product-decision-approval-receipt.schema.json",
            "schemas/protected-review-receipt.schema.json",
            "schemas/trusted-approvers.schema.json",
            "schemas/trusted-reviewers.schema.json",
            "templates/MERGE_GATE.json",
            "templates/OPERATION_APPROVAL_RECEIPT.json",
            "templates/L3_RUNTIME_CONTEXT.json",
            "templates/PRODUCT_DECISION_APPROVAL_RECEIPT.json",
            "templates/PROTECTED_REVIEW_RECEIPT.json",
            "templates/TRUSTED_APPROVERS.json",
            "templates/TRUSTED_REVIEWERS.json",
            "skill/agentic-sdd-governance/SKILL.md",
            "skill/agentic-sdd-governance/references/autonomy-workflow.md",
            "skill/agentic-sdd-governance/references/independent-reviewer.md",
        )
        packaged = ROOT / "src/sddgov/resources/governance"
        for relative in paths:
            with self.subTest(path=relative):
                self.assertEqual(
                    (ROOT / relative).read_bytes(),
                    (packaged / relative).read_bytes(),
                )

    def test_codex_adapter_preserves_repository_bootstrap_before_layered_loading(self):
        codex = (ROOT / "adapters/codex/AGENTS.md").read_text(encoding="utf-8")
        self.assertIn(
            "After completing the repository's required bootstrap reads, load only the following additional Governance Root sources:",
            codex,
        )

    def test_evidence_paths_are_normalized_and_zone_bounded(self):
        collector = json.loads(
            (ROOT / "schemas/collector-event.schema.json").read_text(encoding="utf-8")
        )
        attachment = json.loads(
            (ROOT / "schemas/debug-evidence-package.schema.json").read_text(encoding="utf-8")
        )
        collector_pattern = collector["properties"]["path"]["pattern"]
        attachment_pattern = attachment["properties"]["attachments"]["items"]["properties"]["path"]["pattern"]

        for pattern, accepted, rejected in (
            (
                collector_pattern,
                ["private/raw/terminal.log", "private/raw/run/output.json"],
                [
                    "private/raw/../shareable/leak.txt",
                    "private/raw/./log.txt",
                    "private/raw\\leak.txt",
                    "private/raw/control\u0000value.txt",
                    "private/raw/control\u001fvalue.txt",
                    "private/raw/control\u007fvalue.txt",
                    "private/raw/.. /leak.txt",
                    "private/raw/report. ",
                    "private/raw/report.",
                    "private/raw/",
                ],
            ),
            (
                attachment_pattern,
                ["shareable/artifacts/summary.txt", "shareable/artifacts/run/report.json"],
                [
                    "shareable/report.json",
                    "shareable/manifest.json",
                    "shareable/../private/raw.txt",
                    "shareable/./report.txt",
                    "shareable\\leak.txt",
                    "shareable/control\u0000value.txt",
                    "shareable/control\u001fvalue.txt",
                    "shareable/control\u007fvalue.txt",
                    "shareable/artifacts/.. /leak.txt",
                    "shareable/artifacts/report. ",
                    "shareable/artifacts/report.",
                    "shareable/",
                ],
            ),
        ):
            for value in accepted:
                self.assertIsNotNone(re.fullmatch(pattern, value), value)
            for value in rejected:
                self.assertIsNone(re.fullmatch(pattern, value), value)

    def test_objective_contract_lists_reject_blank_items(self):
        schema = json.loads(
            (ROOT / "schemas/objective-contract.schema.json").read_text(encoding="utf-8")
        )
        for key in ("guardrails", "keep_condition", "rollback_condition"):
            pattern = schema["properties"][key]["items"]["pattern"]
            self.assertIsNotNone(re.search(pattern, "bounded rollback"), key)
            self.assertIsNone(re.search(pattern, "   \t"), key)

    def test_redaction_inventory_matches_sensitive_identifier_contract(self):
        rules = json.loads((ROOT / "redaction/rules.json").read_text(encoding="utf-8"))
        actions = {item["id"]: item["action"] for item in rules["rules"]}
        self.assertEqual(actions["password"], "replace")
        self.assertEqual(actions["patient-identifier"], "mask")
        self.assertEqual(actions["customer-identifier"], "mask")

    def test_security_critical_sources_and_dependency_inputs_are_protected(self):
        policy = yaml.safe_load(
            (ROOT / "policies/protected-files.yaml").read_text(encoding="utf-8")
        )
        protected = set(policy["protected"])
        for required in (
            "src/sddgov/",
            ".github/workflows/",
            ".sddgov/ci-cost-guard.json",
            "skill/",
            "adapters/",
            "pyproject.toml",
            "requirements-governance.lock",
        ):
            with self.subTest(required=required):
                self.assertIn(required, protected)

    def test_experimental_8_uses_patched_cryptography_line(self):
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        lock = (ROOT / "requirements-governance.lock").read_text(encoding="utf-8")
        self.assertIn('version = "0.2.0.dev8"', pyproject)
        self.assertIn('cryptography>=50,<51', pyproject)
        self.assertIn("cryptography==50.0.0", lock)
        self.assertNotIn("cryptography==46.0.7", lock)

    def test_collector_playbooks_preserve_safe_reproduction_context(self):
        browser = (ROOT / "collectors/browser-playwright.md").read_text(encoding="utf-8")
        terminal = (ROOT / "collectors/terminal-git.md").read_text(encoding="utf-8")
        self.assertIn("URL fragments", browser)
        self.assertIn("failing-test-context.txt", terminal)
        self.assertIn("exit status", terminal)

    def test_coderabbit_upstream_review_contracts(self):
        contracts = {
            "browser deny-by-default URL handling": (
                ROOT / "collectors/browser-playwright.md",
                (
                    "Deny by default",
                    "query parameters",
                    "path segments",
                    "headers",
                    "referrers",
                    "Supabase service-role",
                    "safe metadata allowlist",
                    "Referer",
                    "Set-Cookie",
                    "Proxy-Authorization",
                    "API-key",
                ),
            ),
            "bounded Flutter capture": (
                ROOT / "collectors/flutter-android.md",
                ("Press `q`", "wait until `flutter run` exits", "<DEP>/private/raw/flutter-failure.log"),
            ),
            "bounded Android capture": (
                ROOT / "collectors/flutter-android.md",
                ("Press Ctrl-C", "wait until `adb logcat` exits", "<DEP>/private/raw/logcat-failure.log"),
            ),
            "terminal private evidence and collection status": (
                ROOT / "collectors/terminal-git.md",
                (
                    "<DEP>/private/raw/failing-test.log",
                    "<DEP>/private/raw/failing-test-context.txt",
                    "collection_status",
                ),
            ),
            "Supabase and Docker private evidence": (
                ROOT / "collectors/supabase-docker.md",
                (
                    "<DEP>/private/raw/supabase-function.log",
                    "<DEP>/private/raw/docker-failure.log",
                ),
            ),
            "repository-relative Cost Guard template": (
                ROOT / "docs/CI_COST_GUARD.md",
                (".agentic-sdd-governance/templates/CI_COST_GUARD.json",),
            ),
            "explicit DEP verification command": (
                ROOT / "docs/EVIDENCE_DRIVEN_SDD.md",
                ("evidence verify <DEP> --strict",),
            ),
            "explicit DEP verification command in Skill": (
                ROOT / "skill/agentic-sdd-governance/SKILL.md",
                ("evidence verify <DEP> --strict",),
            ),
            "rejected Issue root-cause state": (
                ROOT / "templates/ISSUE_EVIDENCE.md",
                ("unknown / hypothesized / confirmed / rejected",),
            ),
            "destination-authorized attachment": (
                ROOT / "skill/agentic-sdd-governance/references/dep-contract.md",
                ("approved package state", "Decision Package", "explicit approval", "authorized destination", "minimum disclosure"),
            ),
            "narrow L2 trigger": (
                ROOT / "skill/agentic-sdd-governance/references/evidence-workflow.md",
                ("approved behavior", "user-visible promises", "authority boundaries", "ordinary bug fix"),
            ),
            "unambiguous regression level": (
                ROOT / "skill/agentic-sdd-governance/references/risk-evidence-matrix.md",
                ("Every regression fix is L1", "full DEP"),
            ),
        }
        for label, (path, fragments) in contracts.items():
            with self.subTest(contract=label):
                text = path.read_text(encoding="utf-8")
                for fragment in fragments:
                    self.assertIn(fragment, text)

    def test_autonomy_v1_2_contract_is_machine_enforced(self):
        policy = json.loads(
            (ROOT / "policies/autonomy-policy.json").read_text(encoding="utf-8")
        )
        self.assertEqual(policy["default_state"], "CONTINUE")
        self.assertTrue(policy["no_human_escalation_if_machine_verifiable"])
        self.assertEqual(policy["action_classifier"]["unknown_category_state"], "BLOCKED")
        self.assertTrue(policy["action_classifier"]["sensitive_effects_require_l3"])
        self.assertEqual(policy["approval_budget"]["L0"], 0)
        self.assertEqual(policy["approval_budget"]["L1"], 0)
        self.assertTrue(policy["integrity"]["human_copy_paste_forbidden"])
        self.assertFalse(policy["integrity"]["mismatch_requires_human_approval"])
        self.assertFalse(policy["l3_approval_receipts"]["caller_strings_are_authority"])
        self.assertFalse(
            policy["l3_approval_receipts"]["candidate_worktree_store_is_authority"]
        )
        self.assertTrue(policy["l3_approval_receipts"]["consume_atomically_on_continue"])
        self.assertFalse(policy["production_deploy"]["l0_pre_authorized"])
        self.assertFalse(policy["production_deploy"]["l1_pre_authorized"])
        self.assertTrue(
            policy["production_deploy"][
                "l1_autonomous_with_recorded_baseline_authorization"
            ]
        )
        kernel = (ROOT / "core/POLICY_KERNEL.md").read_text(encoding="utf-8")
        self.assertIn("NO_HUMAN_ESCALATION_IF_MACHINE_VERIFIABLE", kernel)
        self.assertIn("Never ask a human to copy, paste", kernel)
        autonomy = (ROOT / "docs/AUTONOMOUS_DEVELOPMENT_V1_2.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("AUTONOMY BY DEFAULT. ESCALATION BY EXCEPTION.", autonomy)
        self.assertIn("Main Agent", autonomy)
        workflow = yaml.safe_load(
            (ROOT / ".github/workflows/governance.yml").read_text(encoding="utf-8")
        )
        verifier_jobs = [
            job
            for job in workflow["jobs"].values()
            if any(
                "merge verify" in str(step.get("run", ""))
                for step in job.get("steps", [])
            )
        ]
        self.assertEqual(len(verifier_jobs), 1)
        verifier_steps = [
            step
            for step in verifier_jobs[0]["steps"]
            if "merge verify" in str(step.get("run", ""))
        ]
        self.assertEqual(len(verifier_steps), 1)
        self.assertIn(
            "SDDGOV_TRUSTED_REVIEWERS_JSON", verifier_steps[0].get("env", {})
        )
        self.assertIn(
            "SDDGOV_TRUSTED_REVIEWERS_FILE", verifier_steps[0].get("env", {})
        )
        checkout_steps = [
            step
            for step in verifier_jobs[0]["steps"]
            if str(step.get("uses", "")).startswith("actions/checkout@")
        ]
        self.assertEqual(len(checkout_steps), 2)
        by_path = {step["with"]["path"]: step for step in checkout_steps}
        self.assertEqual(set(by_path), {"candidate", "trusted-verifier"})
        self.assertEqual(by_path["candidate"]["with"]["fetch-depth"], 0)
        self.assertFalse(by_path["candidate"]["with"]["persist-credentials"])
        self.assertIn(
            "pull_request.head.sha", by_path["candidate"]["with"]["ref"]
        )
        self.assertIn(
            "pull_request.base.sha", by_path["trusted-verifier"]["with"]["ref"]
        )
        cli = (ROOT / "src/sddgov/cli.py").read_text(encoding="utf-8")
        self.assertIn("import-product-approval", cli)
        self.assertIn("import-operation-approval", cli)
        self.assertNotIn('"authorize-operation"', cli)
        all_runtime_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (
                ROOT / "core/POLICY_KERNEL.md",
                ROOT / "core/policy-kernel.yaml",
                ROOT / "policies/autonomy-policy.json",
                ROOT / "skill/agentic-sdd-governance/SKILL.md",
                ROOT / "src/sddgov/autonomy.py",
            )
        ).lower()
        self.assertNotIn("paste sha-256 to approve", all_runtime_text)
        self.assertNotIn("貼回 sha-256", all_runtime_text)

    def test_pull_request_gate_uses_base_trusted_verifier(self):
        workflow = (ROOT / ".github/workflows/governance.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("pull_request_target:", workflow)
        self.assertIn("path: candidate", workflow)
        self.assertIn("path: trusted-verifier", workflow)
        self.assertIn("github.event.pull_request.base.sha", workflow)
        self.assertIn("github.event.pull_request.head.sha", workflow)
        self.assertIn("PYTHONPATH", workflow)
        self.assertIn("trusted-verifier/src", workflow)
        self.assertIn("--skip-local-checks", workflow)
        self.assertIn("core.hooksPath=/dev/null", workflow)
        uses = re.findall(r"uses:\s*([^\s#]+)", workflow)
        self.assertTrue(uses)
        self.assertTrue(
            all(re.fullmatch(r"[^@\s]+@[0-9a-f]{40}", value) for value in uses),
            uses,
        )
        self.assertIn("--require-hashes", workflow)
        self.assertIn("requirements-governance.lock", workflow)
        lock = (ROOT / "requirements-governance.lock").read_text(encoding="utf-8")
        self.assertIn("--hash=sha256:", lock)
        self.assertNotIn("python -m pip install -e .", workflow)


if __name__ == "__main__":
    unittest.main()
