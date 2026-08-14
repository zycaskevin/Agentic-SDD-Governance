import base64
import io
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stderr
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from sddgov.autonomy import (
    ACTION_REQUIRED_FIELDS,
    DEPLOY_GUARDS,
    checkpoint,
    evaluate_deployment,
    evaluate_escalation as _evaluate_escalation,
    import_operation_approval,
    lock_artifact,
    record_decision,
    render_action_required,
    verify_artifact,
)
from sddgov.cli import main
from sddgov.governance import init_project


def evaluate_escalation(root, request):
    """Keep normal fixtures explicit while reserving omission for its regression test."""
    return _evaluate_escalation(root, {"effects": {}, **request})


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
        self.trust_temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.trust_path = Path(self.trust_temporary.name) / "trusted-approvers.json"
        self.trust_environment = patch.dict(
            "os.environ", {"SDDGOV_TRUSTED_APPROVERS_FILE": str(self.trust_path)}
        )
        self.trust_environment.start()
        init_project(self.root, "team-standard")

    def tearDown(self):
        self.trust_environment.stop()
        self.trust_temporary.cleanup()
        self.temporary.cleanup()

    def _signed_operation_approval(
        self,
        approval_id="APP-OP-1",
        operation_id="PROD-OP-1",
        approved_by="product-owner",
    ):
        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        trust = {
            "schema_version": "1.0",
            "approvers": [
                {
                    "approver_id": approved_by,
                    "algorithm": "ed25519",
                    "public_key": base64.b64encode(public_key).decode("ascii"),
                    "status": "active",
                }
            ],
        }
        self.trust_path.write_text(json.dumps(trust), encoding="utf-8")
        self.trust_path.chmod(0o600)
        now = datetime.now(timezone.utc).replace(microsecond=0)
        receipt = {
            "approval_id": approval_id,
            "operation_id": operation_id,
            "summary": "Run one exact Production operation",
            "scope": "One exact operation only",
            "approved_by": approved_by,
            "issued_at": now.isoformat().replace("+00:00", "Z"),
            "expires_at": (now + timedelta(minutes=30)).isoformat().replace(
                "+00:00", "Z"
            ),
            "nonce": f"nonce-{approval_id}-{operation_id}",
        }
        canonical = json.dumps(
            receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        envelope = {
            "schema_version": "1.0",
            "algorithm": "ed25519",
            "receipt": receipt,
            "signature": base64.b64encode(private_key.sign(canonical)).decode("ascii"),
        }
        path = self.root / "signed-approval.json"
        path.write_text(json.dumps(envelope), encoding="utf-8")
        return path, envelope

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

    def test_unknown_or_dangerous_action_cannot_be_downgraded_to_l1(self):
        unknown = evaluate_escalation(
            self.root,
            {"risk_level": "L1", "category": "delete_production_customer_data"},
        )
        self.assertEqual(unknown["state"], "BLOCKED")
        self.assertFalse(unknown["requires_response"])
        self.assertEqual(unknown["reason"], "unrecognized_action_category")

        dangerous = evaluate_escalation(
            self.root,
            {"risk_level": "L1", "category": "production_data_deletion"},
        )
        self.assertEqual(dangerous["state"], "BLOCKED")
        self.assertIn("L3", dangerous["required_risk_levels"])

        disguised = evaluate_escalation(
            self.root,
            {
                "risk_level": "L1",
                "category": "implementation",
                "effects": {"destructive": True, "production": True},
            },
        )
        self.assertEqual(disguised["state"], "BLOCKED")
        with self.assertRaisesRegex(ValueError, "effects must be an object"):
            evaluate_escalation(
                self.root,
                {"risk_level": "L1", "category": "implementation", "effects": []},
            )
        for invalid in ({"unknown_effect": True}, {"production": False}):
            with self.subTest(effects=invalid):
                with self.assertRaisesRegex(ValueError, "known sensitive flags"):
                    evaluate_escalation(
                        self.root,
                        {
                            "risk_level": "L1",
                            "category": "implementation",
                            "effects": invalid,
                        },
                    )

        with self.assertRaisesRegex(ValueError, "effects is required"):
            _evaluate_escalation(
                self.root,
                {"risk_level": "L1", "category": "implementation"},
            )

    def test_duplicate_approver_id_is_rejected_before_key_selection(self):
        path, _ = self._signed_operation_approval()
        trust_path = self.trust_path
        trust = json.loads(trust_path.read_text())
        duplicate = dict(trust["approvers"][0])
        duplicate["status"] = "revoked"
        trust["approvers"].append(duplicate)
        trust_path.write_text(json.dumps(trust))
        with self.assertRaisesRegex(ValueError, "duplicate approver_id"):
            import_operation_approval(self.root, path)

    def test_repo_local_approver_store_is_not_an_authority_source(self):
        path, _ = self._signed_operation_approval()
        repository_store = self.root / ".sddgov/trusted-approvers.json"
        repository_store.write_text(self.trust_path.read_text())
        with patch.dict(
            "os.environ",
            {
                "SDDGOV_TRUSTED_APPROVERS_FILE": "",
                "SDDGOV_TRUSTED_BASE_REF": "",
            },
        ):
            with self.assertRaisesRegex(ValueError, "bootstrap requires"):
                import_operation_approval(self.root, path)

    def test_external_approver_store_must_be_owner_controlled(self):
        path, _ = self._signed_operation_approval()
        self.trust_path.chmod(0o644)
        with self.assertRaisesRegex(ValueError, "owner-only permissions"):
            import_operation_approval(self.root, path)

    def test_trusted_base_ref_must_be_an_immutable_full_sha(self):
        path, _ = self._signed_operation_approval()
        with patch.dict(
            "os.environ",
            {
                "SDDGOV_TRUSTED_APPROVERS_FILE": "",
                "SDDGOV_TRUSTED_BASE_REF": "--help",
            },
        ):
            with self.assertRaisesRegex(ValueError, "full 40-character commit SHA"):
                import_operation_approval(self.root, path)

    def test_adversarial_receipt_encodings_fail_closed(self):
        path, envelope = self._signed_operation_approval("APP-BAD", "PROD-BAD")

        cases = {
            "invalid_base64_signature": "!" * 88,
            "wrong_length_signature": base64.b64encode(b"short").decode("ascii"),
            "valid_length_wrong_signature": base64.b64encode(bytes(64)).decode("ascii"),
        }
        for label, signature in cases.items():
            with self.subTest(case=label):
                candidate = dict(envelope)
                candidate["signature"] = signature
                path.write_text(json.dumps(candidate))
                with self.assertRaisesRegex(ValueError, "signature"):
                    import_operation_approval(self.root, path)

        trust = json.loads(self.trust_path.read_text())
        trust["approvers"][0]["public_key"] = base64.b64encode(b"short").decode(
            "ascii"
        )
        self.trust_path.write_text(json.dumps(trust))
        path.write_text(json.dumps(envelope))
        with self.assertRaisesRegex(ValueError, "signature"):
            import_operation_approval(self.root, path)

        path.write_text("[]")
        with patch(
            "sys.argv",
            [
                "sddgov",
                "decision",
                "import-operation-approval",
                str(path),
                "--path",
                str(self.root),
            ],
        ), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as exit_info:
            main()
        self.assertEqual(exit_info.exception.code, 2)

    def test_timezone_naive_imported_expiry_blocks_without_exception(self):
        path, _ = self._signed_operation_approval("APP-NAIVE", "PROD-NAIVE")
        import_operation_approval(self.root, path)
        decisions_path = self.root / ".sddgov/decisions.json"
        decisions = json.loads(decisions_path.read_text())
        decisions["decisions"][0]["expires_at"] = "2026-08-13"
        decisions_path.write_text(json.dumps(decisions))
        result = evaluate_escalation(
            self.root,
            {
                "risk_level": "L3",
                "category": "high_risk_operation",
                "operation_id": "PROD-NAIVE",
                "approval_id": "APP-NAIVE",
                "decision_package": decision_package("L3", "APP-NAIVE-NEXT"),
            },
        )
        self.assertEqual(result["state"], "ACTION_REQUIRED")

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

        receipt, _ = self._signed_operation_approval()
        import_operation_approval(self.root, receipt)
        request["approval_id"] = "APP-OP-1"
        authorized = evaluate_escalation(self.root, request)
        self.assertEqual(authorized["state"], "CONTINUE")
        self.assertEqual(evaluate_escalation(self.root, request)["state"], "ACTION_REQUIRED")

    def test_l3_signed_receipt_is_required_and_consumption_is_serialized(self):
        receipt, envelope = self._signed_operation_approval(
            "APP-CONCURRENT", "PROD-CONCURRENT"
        )
        imported = import_operation_approval(self.root, receipt)
        self.assertEqual(imported["approval_id"], "APP-CONCURRENT")
        self.assertEqual(imported["verification"], "SIGNATURE_VERIFIED")

        tampered = dict(envelope)
        tampered["receipt"] = dict(envelope["receipt"])
        tampered["receipt"]["operation_id"] = "PROD-DIFFERENT"
        tampered_path = self.root / "tampered-approval.json"
        tampered_path.write_text(json.dumps(tampered), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "signature"):
            import_operation_approval(self.root, tampered_path)

        request = {
            "risk_level": "L3",
            "category": "high_risk_operation",
            "operation_id": "PROD-CONCURRENT",
            "approval_id": "APP-CONCURRENT",
            "decision_package": decision_package("L3", "APP-CONCURRENT-NEXT"),
        }

        def evaluate_once():
            return evaluate_escalation(self.root, request)["state"]

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: evaluate_once(), range(2)))
        self.assertEqual(sorted(results), ["ACTION_REQUIRED", "CONTINUE"])

    def test_l3_decision_row_tampering_cannot_bypass_signed_receipt(self):
        receipt, _ = self._signed_operation_approval("APP-TAMPER", "PROD-TAMPER")
        import_operation_approval(self.root, receipt)
        decisions_path = self.root / ".sddgov/decisions.json"
        decisions = json.loads(decisions_path.read_text(encoding="utf-8"))
        row = next(
            item for item in decisions["decisions"]
            if item["decision_id"] == "APP-TAMPER"
        )
        row["operation_id"] = "PROD-ATTACKER-CONTROLLED"
        decisions_path.write_text(json.dumps(decisions), encoding="utf-8")
        result = evaluate_escalation(
            self.root,
            {
                "risk_level": "L3",
                "category": "high_risk_operation",
                "operation_id": "PROD-ATTACKER-CONTROLLED",
                "approval_id": "APP-TAMPER",
                "decision_package": decision_package("L3", "APP-TAMPER-NEXT"),
            },
        )
        self.assertEqual(result["state"], "ACTION_REQUIRED")
        self.assertFalse(
            json.loads(decisions_path.read_text(encoding="utf-8"))["decisions"][-1]
            ["consumed_at"]
        )

    def test_l3_receipt_rejects_unknown_signer_expiry_and_replay(self):
        receipt, envelope = self._signed_operation_approval("APP-EDGE", "PROD-EDGE")
        trust_path = self.trust_path
        trust = json.loads(trust_path.read_text(encoding="utf-8"))
        trust["approvers"][0]["approver_id"] = "different-owner"
        trust_path.write_text(json.dumps(trust), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "trusted approver"):
            import_operation_approval(self.root, receipt)

        receipt, envelope = self._signed_operation_approval("APP-EDGE", "PROD-EDGE")
        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        trust = {
            "schema_version": "1.0",
            "approvers": [{
                "approver_id": "product-owner",
                "algorithm": "ed25519",
                "public_key": base64.b64encode(public_key).decode("ascii"),
                "status": "active",
            }],
        }
        trust_path.write_text(json.dumps(trust), encoding="utf-8")
        now = datetime.now(timezone.utc).replace(microsecond=0)
        envelope["receipt"]["issued_at"] = (now - timedelta(hours=2)).isoformat().replace("+00:00", "Z")
        envelope["receipt"]["expires_at"] = (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        canonical = json.dumps(envelope["receipt"], ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        envelope["signature"] = base64.b64encode(private_key.sign(canonical)).decode("ascii")
        receipt.write_text(json.dumps(envelope), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "expired"):
            import_operation_approval(self.root, receipt)

        fresh_receipt, _ = self._signed_operation_approval("APP-REPLAY", "PROD-REPLAY")
        import_operation_approval(self.root, fresh_receipt)
        with self.assertRaisesRegex(ValueError, "already imported"):
            import_operation_approval(self.root, fresh_receipt)

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

    def test_operational_action_and_necessary_uat_bypass_l1_shortcut(self):
        operational = evaluate_escalation(
            self.root,
            {
                "risk_level": "L1",
                "category": "operational_action",
                "decision_package": decision_package("Operational", "LOGIN-L1"),
            },
        )
        self.assertEqual(operational["state"], "ACTION_REQUIRED")
        uat = evaluate_escalation(
            self.root,
            {
                "risk_level": "L1",
                "category": "necessary_uat",
                "machine_verifiable": True,
                "decision_package": decision_package("UAT", "UAT-L1"),
            },
        )
        self.assertEqual(uat["state"], "ACTION_REQUIRED")

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
