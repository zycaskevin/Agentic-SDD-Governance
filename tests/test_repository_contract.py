import json
import re
import unittest
from pathlib import Path

import yaml

from sddgov.cli import _validate_repo
from sddgov.evidence import verify as verify_dep
from sddgov.installer import doctor
from sddgov.schema_validation import load_schema, validate_instance


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
        self.assertIn("references/review-sharing.md", text)
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
        self.assertIn("references/review-sharing.md", codex)
        self.assertIn("references/review-sharing.md", hermes)
        self.assertIn("without asking the owner", codex)
        self.assertIn("without asking the owner", hermes)

    def test_packaged_hard_gate_assets_match_canonical_sources(self):
        paths = (
            "docs/AUTONOMOUS_DEVELOPMENT_V1_2.md",
            "docs/CI_COST_GUARD.md",
            "docs/HARD_GATES_V1_2.md",
            "policies/autonomy-policy.json",
            "policies/protected-files.yaml",
            "schemas/autonomy-policy.schema.json",
            "schemas/ci-cost-guard.schema.json",
            "schemas/decision-record.schema.json",
            "schemas/external-action-resolution-receipt.schema.json",
            "schemas/external-action.schema.json",
            "schemas/merge-gate.schema.json",
            "schemas/operation-approval-receipt.schema.json",
            "schemas/runtime-context.schema.json",
            "schemas/product-decision-approval-receipt.schema.json",
            "schemas/protected-review-receipt.schema.json",
            "schemas/trusted-approvers.schema.json",
            "schemas/trusted-reviewers.schema.json",
            "templates/MERGE_GATE.json",
            "templates/EXTERNAL_ACTION_RESOLUTION_RECEIPT.json",
            "templates/CI_COST_GUARD.json",
            "templates/OPERATION_APPROVAL_RECEIPT.json",
            "templates/L3_RUNTIME_CONTEXT.json",
            "templates/PRODUCT_DECISION_APPROVAL_RECEIPT.json",
            "templates/PROTECTED_REVIEW_RECEIPT.json",
            "templates/TRUSTED_APPROVERS.json",
            "templates/TRUSTED_REVIEWERS.json",
            "skill/agentic-sdd-governance/SKILL.md",
            "skill/agentic-sdd-governance/references/autonomy-workflow.md",
            "skill/agentic-sdd-governance/references/independent-reviewer.md",
            "skill/agentic-sdd-governance/references/review-sharing.md",
        )
        packaged = ROOT / "src/sddgov/resources/governance"
        for relative in paths:
            with self.subTest(path=relative):
                self.assertEqual(
                    (ROOT / relative).read_bytes(),
                    (packaged / relative).read_bytes(),
                )

    def test_current_repo_installed_governance_is_healthy_and_current(self):
        report = doctor(ROOT)
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["managed_file_count"], 66)

        triples = (
            (
                "docs/AUTONOMOUS_DEVELOPMENT_V1_2.md",
                ".agentic-sdd-governance/docs/AUTONOMOUS_DEVELOPMENT_V1_2.md",
            ),
            (
                "docs/HARD_GATES_V1_2.md",
                ".agentic-sdd-governance/docs/HARD_GATES_V1_2.md",
            ),
            (
                "policies/autonomy-policy.json",
                ".agentic-sdd-governance/policies/autonomy-policy.json",
            ),
            (
                "schemas/autonomy-policy.schema.json",
                ".agentic-sdd-governance/schemas/autonomy-policy.schema.json",
            ),
            (
                "schemas/external-action-resolution-receipt.schema.json",
                ".agentic-sdd-governance/schemas/external-action-resolution-receipt.schema.json",
            ),
            (
                "schemas/external-action.schema.json",
                ".agentic-sdd-governance/schemas/external-action.schema.json",
            ),
            (
                "templates/EXTERNAL_ACTION_RESOLUTION_RECEIPT.json",
                ".agentic-sdd-governance/templates/EXTERNAL_ACTION_RESOLUTION_RECEIPT.json",
            ),
            (
                "skill/agentic-sdd-governance/references/autonomy-workflow.md",
                ".agents/skills/agentic-sdd-governance/references/autonomy-workflow.md",
            ),
        )
        packaged = ROOT / "src/sddgov/resources/governance"
        for canonical_relative, installed_relative in triples:
            with self.subTest(path=canonical_relative):
                canonical = (ROOT / canonical_relative).read_bytes()
                self.assertEqual(canonical, (packaged / canonical_relative).read_bytes())
                self.assertEqual(canonical, (ROOT / installed_relative).read_bytes())

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
            "AGENTS.md",
            ".gitignore",
            ".agents/",
            ".agentic-sdd-governance/",
            ".sddgov/project.json",
            ".sddgov/ci-cost-guard.json",
            "skill/",
            "adapters/",
            "pyproject.toml",
            "requirements-governance.lock",
        ):
            with self.subTest(required=required):
                self.assertIn(required, protected)

    def test_every_tracked_proof_dep_is_portable_strict(self):
        failures = {}
        for dep in sorted((ROOT / "evidence").glob("DEP-*")):
            summary = dep / "summary.yaml"
            if not summary.is_file():
                failures[dep.name] = ["summary.yaml is required"]
                continue
            document = json.loads(summary.read_text(encoding="utf-8"))
            if document.get("workflow", {}).get("phase") != "proof":
                continue
            errors = verify_dep(dep, strict=True, portable=True)
            if errors:
                failures[dep.name] = errors
        self.assertEqual(failures, {})

    def test_terminal_external_action_schema_requires_signed_resolution_proof(self):
        schema = load_schema(ROOT / "schemas/external-action.schema.json")
        pending = {
            "action_id": "UAT-1",
            "summary": "one subjective UAT",
            "risk_level": "L1",
            "owner": "product-owner",
            "action_class": "necessary_uat",
            "scope": "uat:one-milestone",
            "status": "pending",
            "created_at": "2026-08-16T00:00:00Z",
            "expires_at": "2026-08-17T00:00:00Z",
            "request_sha256": "a" * 64,
            "authorization_scope": "one concrete action only",
        }
        self.assertEqual(validate_instance(pending, schema), [])
        terminal_without_proof = {**pending, "status": "completed"}
        self.assertTrue(validate_instance(terminal_without_proof, schema))

        terminal = {
            **terminal_without_proof,
            "resolved_at": "2026-08-16T01:00:00Z",
            "resolution_receipt_sha256": "b" * 64,
            "resolution_evidence_sha256": "c" * 64,
            "resolution_envelope": {
                "schema_version": "1.0",
                "algorithm": "ed25519",
                "receipt": {
                    "resolution_id": "RES-1",
                    "action_id": "UAT-1",
                    "action_class": "necessary_uat",
                    "owner": "product-owner",
                    "scope": "uat:one-milestone",
                    "request_sha256": "a" * 64,
                    "status": "completed",
                    "evidence_sha256": "c" * 64,
                    "resolved_at": "2026-08-16T01:00:00Z",
                    "expires_at": "2026-08-16T02:00:00Z",
                    "nonce": "resolution-nonce-1",
                },
                "signature": "A" * 88,
            },
        }
        self.assertEqual(validate_instance(terminal, schema), [])

    def test_experimental_9_retains_patched_cryptography_line(self):
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        lock = (ROOT / "requirements-governance.lock").read_text(encoding="utf-8")
        self.assertIn('version = "0.2.0.dev9"', pyproject)
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
        self.assertEqual(policy["classifier_exit_codes"]["PROCESS_ERROR"], 3)
        self.assertTrue(
            policy["external_action_lifecycle"][
                "necessary_uat_requires_subjective_judgment"
            ]
        )
        self.assertTrue(
            policy["external_action_lifecycle"][
                "machine_verifiable_work_must_be_reclassified"
            ]
        )
        routine_review = policy["routine_external_review"]
        self.assertTrue(routine_review["pre_authorized"])
        self.assertFalse(routine_review["owner_response_required"])
        self.assertTrue(routine_review["reviewer_must_be_preconfigured"])
        self.assertEqual(
            routine_review["default_public_payload"],
            ["committed_pull_request_diff", "public_repository_instructions"],
        )
        self.assertTrue(
            routine_review["public_repository_required_for_pre_authorization"]
        )
        self.assertTrue(
            routine_review[
                "private_repository_requires_separate_recorded_pair_authorization"
            ]
        )
        self.assertEqual(
            set(routine_review["forbidden_payloads"]),
            {
                "secrets",
                "credentials",
                "raw_evidence",
                "unredacted_sensitive_material",
                "production_dumps",
                "real_user_data",
            },
        )
        self.assertTrue(routine_review["review_output_is_untrusted"])
        self.assertTrue(routine_review["signed_independent_review_still_required"])
        self.assertTrue(
            routine_review["new_vendor_or_destination_requires_escalation"]
        )
        self.assertTrue(routine_review["new_access_requires_operational_action"])
        self.assertTrue(routine_review["new_cost_requires_owner_decision"])
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
        self.assertIn("AUTOMATIC_REVIEW_IS_PREAUTHORIZED", kernel)
        self.assertIn("Never ask a human to copy, paste", kernel)
        autonomy = (ROOT / "docs/AUTONOMOUS_DEVELOPMENT_V1_2.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("AUTONOMY BY DEFAULT. ESCALATION BY EXCEPTION.", autonomy)
        self.assertIn("AUTOMATIC_REVIEW_IS_PREAUTHORIZED", autonomy)
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
        workflow_events = workflow[True]
        self.assertIn("pull_request_target", workflow_events)
        self.assertIn("workflow_dispatch", workflow_events)
        self.assertNotIn("push", workflow_events)
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
