import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from sddgov.autonomy import (
    ACTION_REQUIRED_FIELDS,
    DEPLOY_GUARDS,
    authorize_operation,
    checkpoint,
    consume_operation_approval,
    evaluate_deployment,
    evaluate_escalation,
    lock_artifact,
    record_decision,
    render_action_required,
    verify_artifact,
)
from sddgov.governance import init_project


def decision_package(risk="L2", decision_id="DEC-NEW"):
    return {
        "decision_id": decision_id,
        "risk_level": risk,
        "why_human_input_is_required": "The unresolved choice changes the approved product contract.",
        "what_agent_already_verified": ["SDD searched", "Tests cannot determine product intent"],
        "options": [
            {"label": "A", "description": "Keep the current product contract."},
            {"label": "B", "description": "Approve the bounded contract change."},
        ],
        "recommended": "A",
        "why": "It preserves the current contract and is reversible.",
        "impact_if_no_decision": "Only the dependent Work Package remains blocked.",
        "scope_of_approval": "This decision only; no Production operation is authorized.",
    }


class AutonomyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        init_project(self.root, "team-standard")

    def tearDown(self):
        self.temporary.cleanup()

    def test_l0_l1_routine_engineering_never_prompts(self):
        operations = (
            "issue",
            "branch",
            "implementation",
            "commit",
            "feature_branch_push",
            "pull_request",
            "review",
            "review_fix",
            "lint",
            "typecheck",
            "test",
            "e2e",
            "security_scan",
            "dependency_conflict",
            "git_conflict",
            "recoverable_retry",
            "integrity_verification",
            "ci",
            "merge",
        )
        for risk in ("L0", "L1"):
            for category in operations:
                with self.subTest(risk=risk, category=category):
                    result = evaluate_escalation(
                        self.root,
                        {"risk_level": risk, "category": category},
                    )
                    self.assertEqual(result["state"], "CONTINUE")
                    self.assertFalse(result["requires_response"])

    def test_checkpoint_is_informational_and_continues(self):
        result = checkpoint("WP-001 complete", "WP-002")
        self.assertFalse(result["requires_response"])
        self.assertEqual(result["next_state"], "CONTINUE")
        classified = evaluate_escalation(
            self.root, {"risk_level": "L1", "category": "checkpoint"}
        )
        self.assertEqual(classified["state"], "CONTINUE")

    def test_machine_verifiable_uncertainty_uses_tools_before_escalation(self):
        result = evaluate_escalation(
            self.root,
            {
                "risk_level": "L1",
                "category": "uncertainty",
                "machine_verifiable": True,
            },
        )
        self.assertEqual(result["state"], "CONTINUE")
        self.assertEqual(
            result["next_action"], "verify_with_repo_decisions_tests_ci_or_tools"
        )
        self.assertFalse(result["requires_response"])

        with self.assertRaisesRegex(ValueError, "strict decision_package"):
            evaluate_escalation(
                self.root,
                {
                    "risk_level": "L2",
                    "category": "uncertainty",
                    "machine_verifiable": True,
                },
            )

    def test_decision_log_prevents_duplicate_l2_questions(self):
        first = evaluate_escalation(
            self.root,
            {
                "risk_level": "L2",
                "category": "product_decision",
                "decision_id": "DEC-023",
                "decision_package": decision_package(decision_id="DEC-023"),
            },
        )
        self.assertEqual(first["state"], "ACTION_REQUIRED")
        record_decision(
            self.root,
            "DEC-023",
            "Supabase approved for MVP",
            "MVP data layer",
            "Approved SDD baseline",
            "Reopen only when privacy, vendor, or product boundary changes",
        )
        second = evaluate_escalation(
            self.root,
            {
                "risk_level": "L2",
                "category": "product_decision",
                "decision_id": "DEC-023",
                "decision_scope": "MVP data layer",
                "assumptions_unchanged": True,
            },
        )
        self.assertEqual(second["state"], "CONTINUE")
        self.assertFalse(second["requires_response"])
        changed_scope = evaluate_escalation(
            self.root,
            {
                "risk_level": "L2",
                "category": "product_decision",
                "decision_id": "DEC-023",
                "decision_scope": "Production analytics export",
                "decision_package": decision_package(decision_id="DEC-023-SCOPE"),
            },
        )
        self.assertEqual(changed_scope["state"], "ACTION_REQUIRED")
        with self.assertRaisesRegex(ValueError, "already recorded"):
            record_decision(
                self.root, "DEC-023", "duplicate", "scope", "basis", "condition"
            )

    def test_l2_and_l3_emit_strict_action_required(self):
        l2 = evaluate_escalation(
            self.root,
            {
                "risk_level": "L2",
                "category": "product_decision",
                "decision_package": decision_package("L2", "DEC-UX"),
            },
        )
        self.assertEqual(l2["state"], "ACTION_REQUIRED")
        self.assertTrue(l2["requires_response"])
        self.assertEqual(l2["decision_package"]["heading"], "ACTION REQUIRED")
        self.assertTrue(
            set(ACTION_REQUIRED_FIELDS).issubset(l2["decision_package"])
        )
        self.assertTrue(render_action_required(l2["decision_package"]).startswith("ACTION REQUIRED\n"))

        l3 = evaluate_escalation(
            self.root,
            {
                "risk_level": "L3",
                "category": "high_risk_operation",
                "operation_id": "PROD-DELETE-1",
                "decision_package": decision_package("L3", "APPROVAL-1"),
            },
        )
        self.assertEqual(l3["state"], "ACTION_REQUIRED")
        invalid = decision_package("L2", "DEC-BLANK")
        invalid["scope_of_approval"] = "   "
        with self.assertRaisesRegex(ValueError, "missing fields"):
            evaluate_escalation(
                self.root,
                {
                    "risk_level": "L2",
                    "category": "product_decision",
                    "decision_package": invalid,
                },
            )

    def test_l3_requires_fresh_exact_one_use_approval(self):
        record_decision(
            self.root,
            "DEC-ARCH",
            "Architecture approved",
            "Architecture only",
            "Baseline",
            "Boundary change",
        )
        request = {
            "risk_level": "L3",
            "category": "high_risk_operation",
            "operation_id": "PROD-OP-1",
            "approval_id": "DEC-ARCH",
            "decision_package": decision_package("L3", "APP-OP-1"),
        }
        self.assertEqual(evaluate_escalation(self.root, request)["state"], "ACTION_REQUIRED")

        machine_claim = dict(request)
        machine_claim["machine_verifiable"] = True
        self.assertEqual(
            evaluate_escalation(self.root, machine_claim)["state"],
            "ACTION_REQUIRED",
        )
        routine_claim = dict(request)
        routine_claim["category"] = "commit"
        self.assertEqual(
            evaluate_escalation(self.root, routine_claim)["state"],
            "ACTION_REQUIRED",
        )

        authorize_operation(
            self.root,
            "APP-OP-1",
            "PROD-OP-1",
            "Run exact Production operation",
            "One operation only",
            "product-owner",
        )
        request["approval_id"] = "APP-OP-1"
        authorized = evaluate_escalation(self.root, request)
        self.assertEqual(authorized["state"], "CONTINUE")
        consume_operation_approval(self.root, "APP-OP-1", "PROD-OP-1")
        self.assertEqual(evaluate_escalation(self.root, request)["state"], "ACTION_REQUIRED")

    def test_l3_approval_consumption_is_serialized(self):
        authorize_operation(
            self.root,
            "APP-CONCURRENT",
            "PROD-CONCURRENT",
            "Run one exact operation",
            "One operation only",
            "product-owner",
        )

        def consume_once():
            try:
                consume_operation_approval(
                    self.root, "APP-CONCURRENT", "PROD-CONCURRENT"
                )
            except ValueError:
                return "rejected"
            return "consumed"

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: consume_once(), range(2)))
        self.assertEqual(sorted(results), ["consumed", "rejected"])

    def test_malformed_decision_store_fails_closed(self):
        decisions = self.root / ".sddgov" / "decisions.json"
        decisions.write_text('{"schema_version":"1.0","decisions":"bad"}\n')
        with self.assertRaisesRegex(ValueError, "invalid contract"):
            record_decision(
                self.root, "DEC-FAIL", "summary", "scope", "basis", "condition"
            )

    def test_blocked_operational_action_does_not_stop_unrelated_work(self):
        result = evaluate_escalation(
            self.root,
            {
                "risk_level": "L3",
                "category": "operational_action",
                "unrelated_work_exists": True,
                "decision_package": decision_package("Operational", "LOGIN-1"),
            },
        )
        self.assertEqual(result["state"], "CONTINUE")
        self.assertFalse(result["requires_response"])
        self.assertIn("action_required", result)

    def test_sha256_is_generated_verified_and_never_a_human_token(self):
        artifact = self.root / "package.whl"
        artifact.write_bytes(b"verified build")
        lock = self.root / "release.lock"
        locked = lock_artifact(artifact, "release-1", lock)
        lock_data = json.loads(lock.read_text(encoding="utf-8"))
        self.assertRegex(lock_data["sha256"], r"^[a-f0-9]{64}$")
        self.assertFalse(locked["human_action_required"])

        verified = verify_artifact(artifact, lock)
        self.assertTrue(verified["ok"])
        self.assertEqual(verified["integrity"], "MATCH")
        self.assertFalse(verified["human_action_required"])
        self.assertNotIn("sha256", verified)

        artifact.write_bytes(b"different build")
        mismatch = verify_artifact(artifact, lock)
        self.assertFalse(mismatch["ok"])
        self.assertEqual(mismatch["state"], "BLOCKED")
        self.assertFalse(mismatch["human_action_required"])
        self.assertNotIn("sha256", mismatch)

    def test_integrity_mismatch_blocks_only_the_artifact(self):
        result = evaluate_escalation(
            self.root,
            {
                "risk_level": "L1",
                "category": "integrity_mismatch",
                "unrelated_work_exists": True,
            },
        )
        self.assertEqual(result["artifact_state"], "BLOCKED")
        self.assertEqual(result["state"], "CONTINUE")
        self.assertFalse(result["requires_response"])

    def test_routine_production_deploy_requires_every_machine_guard(self):
        record_decision(
            self.root,
            "DEC-DEPLOY-WEB",
            "Routine reversible web Production promotion approved",
            "production_deploy:web_app",
            "Approved release baseline",
            "Reopen on product, permission, secret, data, rollback, or blast-radius change",
        )
        gate = {name: True for name in DEPLOY_GUARDS}
        gate.update(
            {
                "risk_level": "L1",
                "deployment_class": "web_app",
                "baseline_decision_id": "DEC-DEPLOY-WEB",
                "baseline_assumptions_unchanged": True,
            }
        )
        allowed = evaluate_deployment(self.root, gate)
        self.assertTrue(allowed["ok"])
        self.assertEqual(allowed["state"], "CONTINUE")
        self.assertFalse(allowed["requires_response"])

        forged = dict(gate)
        forged["baseline_deployment_authorized"] = True
        forged["baseline_decision_id"] = "DEC-NOT-RECORDED"
        self.assertEqual(evaluate_deployment(self.root, forged)["state"], "BLOCKED")

        gate["rollback_available"] = False
        blocked = evaluate_deployment(self.root, gate)
        self.assertEqual(blocked["state"], "BLOCKED")
        self.assertFalse(blocked["requires_response"])
        self.assertIn("rollback_available", blocked["failed_guards"])

        gate["rollback_available"] = True
        gate["risk_level"] = "L0"
        l0 = evaluate_deployment(self.root, gate)
        self.assertEqual(l0["state"], "BLOCKED")
        self.assertIn("at_least_l1", l0["reason"])


if __name__ == "__main__":
    unittest.main()
