import base64
import hashlib
import io
import json
import os
import socket
import stat
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stderr
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from sddgov.autonomy import (
    ACTION_REQUIRED_FIELDS,
    DEPLOY_GUARDS,
    L3_NONCE_BROKER,
    checkpoint,
    evaluate_deployment,
    evaluate_escalation as _evaluate_escalation,
    import_operation_approval,
    import_product_approval,
    lock_artifact,
    record_decision,
    render_action_required,
    verify_artifact,
    _consume_nonce_via_control_plane,
)
from sddgov.trust import load_control_plane_json
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


def operation_payload(operation_id, category="high_risk_operation", effects=None):
    return {
        "repository": "zycaskevin/synthetic-repository",
        "project": "synthetic-project",
        "environment": "synthetic-production",
        "scope": f"one exact operation:{operation_id}",
        "category": category,
        "target": f"synthetic:{operation_id}",
        "parameters": {"mode": "synthetic"},
        "effects": effects or {},
    }


class AutonomyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.trust_temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.trust_path = Path(self.trust_temporary.name) / "trusted-approvers.json"
        self.runtime_context_path = Path(self.trust_temporary.name) / "runtime-context.json"
        self.runtime_context_path.write_text(
            json.dumps({
                "schema_version": "1.0",
                "repository": "zycaskevin/synthetic-repository",
                "project": "synthetic-project",
                "environment": "synthetic-production",
            }),
            encoding="utf-8",
        )
        self.runtime_context = patch(
            "sddgov.autonomy.L3_RUNTIME_CONTEXT_FILE", self.runtime_context_path
        )
        self.runtime_context.start()
        self.trust_environment = patch.dict(
            "os.environ", {"SDDGOV_TRUSTED_APPROVERS_FILE": str(self.trust_path)}
        )
        self.trust_environment.start()
        init_project(self.root, "team-standard")
        self.control_plane_loader = patch(
            "sddgov.autonomy.load_control_plane_json",
            side_effect=lambda path, _label: json.loads(Path(path).read_text()),
        )
        self.control_plane_loader.start()
        self.nonce_broker = patch(
            "sddgov.autonomy._consume_nonce_via_control_plane", return_value=True
        )
        self.nonce_broker.start()

    def tearDown(self):
        self.nonce_broker.stop()
        self.control_plane_loader.stop()
        self.runtime_context.stop()
        self.trust_environment.stop()
        self.trust_temporary.cleanup()
        self.temporary.cleanup()

    def _signed_operation_approval(
        self,
        approval_id="APP-OP-1",
        operation_id="PROD-OP-1",
        approved_by="product-owner",
        payload=None,
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
        exact_payload = payload or operation_payload(operation_id)
        receipt = {
            "approval_id": approval_id,
            "operation_id": operation_id,
            "operation_payload": exact_payload,
            "summary": "Run one exact Production operation",
            "scope": exact_payload["scope"],
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

    def _signed_product_approval(
        self,
        decision_id="DEC-023",
        scope="MVP data layer",
        assumptions="mvp-assumptions-v1",
        approved_by="product-owner",
        reopen_condition="scope_or_assumptions_change",
    ):
        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        self.trust_path.write_text(
            json.dumps(
                {
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
            ),
            encoding="utf-8",
        )
        self.trust_path.chmod(0o600)
        now = datetime.now(timezone.utc).replace(microsecond=0)
        assumption_path = self.root / ".sddgov" / "assumptions" / f"{decision_id}.txt"
        assumption_path.parent.mkdir(parents=True, exist_ok=True)
        assumption_path.write_text(assumptions, encoding="utf-8")
        assumption_rows = [{
            "path": assumption_path.relative_to(self.root).as_posix(),
            "sha256": hashlib.sha256(assumptions.encode("utf-8")).hexdigest(),
        }]
        assumptions_digest = hashlib.sha256(
            json.dumps(
                assumption_rows,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        receipt = {
            "decision_id": decision_id,
            "summary": "Owner-approved bounded product decision",
            "scope": scope,
            "assumptions": assumption_rows,
            "assumptions_sha256": assumptions_digest,
            "reopen_condition": reopen_condition,
            "approved_by": approved_by,
            "issued_at": now.isoformat().replace("+00:00", "Z"),
            "expires_at": (now + timedelta(days=30)).isoformat().replace(
                "+00:00", "Z"
            ),
            "nonce": f"nonce-{decision_id}-{assumptions}",
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
        path = self.root / f"signed-product-{decision_id}.json"
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

    def test_low_risk_actions_reject_free_text_and_nested_executable_intent(self):
        cases = (
            {"target": "customer database live"},
            {"parameters": {"environmentName": "production"}},
            {"parameters": {"nested": {"operation": "delete"}}},
            {"parameters": {"credentialReference": "owner-vault-entry"}},
        )
        for executable_fields in cases:
            with self.subTest(executable_fields=executable_fields):
                disguised = evaluate_escalation(
                    self.root,
                    {
                        "risk_level": "L1",
                        "category": "implementation",
                        **executable_fields,
                    },
                )
                self.assertEqual(disguised["state"], "BLOCKED")
                self.assertEqual(
                    disguised["reason"],
                    "low_risk_action_requires_closed_typed_executor_contract",
                )

        ambiguous = evaluate_escalation(
            self.root,
            {
                "risk_level": "L1",
                "category": "uncertainty",
                "machine_verifiable": True,
                "details": {"nested": "effectful request"},
            },
        )
        self.assertEqual(ambiguous["state"], "BLOCKED")

        hidden_l3_payload = evaluate_escalation(
            self.root,
            {
                "risk_level": "L1",
                "category": "implementation",
                "operation_payload": operation_payload("HIDDEN-L3"),
            },
        )
        self.assertEqual(hidden_l3_payload["state"], "BLOCKED")
        self.assertEqual(
            hidden_l3_payload["reason"],
            "authority_bearing_fields_not_allowed_for_routine_action",
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
            with self.assertRaisesRegex(ValueError, "separate control-plane"):
                import_operation_approval(self.root, path)

    def test_same_uid_external_approver_store_is_not_owner_authority(self):
        path, _ = self._signed_operation_approval()
        self.control_plane_loader.stop()
        try:
            with self.assertRaisesRegex(ValueError, "root-owned"):
                import_operation_approval(self.root, path)
        finally:
            self.control_plane_loader.start()

    def test_root_agent_cannot_treat_root_owned_file_as_separate_authority(self):
        with patch("sddgov.trust.os.geteuid", return_value=0):
            with self.assertRaisesRegex(ValueError, "Agent runs as root"):
                load_control_plane_json(self.trust_path, "test authority")

    def test_caller_selected_trusted_base_ref_is_never_authority(self):
        path, _ = self._signed_operation_approval()
        with patch.dict(
            "os.environ",
            {
                "SDDGOV_TRUSTED_APPROVERS_FILE": "",
                "SDDGOV_TRUSTED_BASE_REF": "a" * 40,
            },
        ):
            with self.assertRaisesRegex(ValueError, "separate control-plane"):
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
                "operation_payload": operation_payload("PROD-NAIVE"),
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

    def test_product_and_high_risk_categories_cannot_be_caller_downgraded(self):
        product = evaluate_escalation(
            self.root,
            {"risk_level": "L1", "category": "product_decision"},
        )
        self.assertEqual(product["state"], "BLOCKED")
        self.assertEqual(product["required_risk_levels"], ["L2"])

        operation = evaluate_escalation(
            self.root,
            {"risk_level": "L1", "category": "high_risk_operation"},
        )
        self.assertEqual(operation["state"], "BLOCKED")
        self.assertEqual(operation["required_risk_levels"], ["L3"])

    def test_unsigned_l2_decision_cannot_be_recorded_as_approved(self):
        with self.assertRaisesRegex(ValueError, "signed.*L2"):
            record_decision(
                self.root,
                "DEC-UNSIGNED",
                "Unsigned product decision",
                "product:contract",
                "caller assertion",
                "reopen when assumptions change",
            )

    def test_l2_owner_receipt_tampering_fails_closed(self):
        path, envelope = self._signed_product_approval("DEC-TAMPERED")
        envelope["receipt"]["scope"] = "expanded product scope"
        path.write_text(json.dumps(envelope), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "signature"):
            import_product_approval(self.root, path)

    def test_l2_receipt_rejects_unsupported_free_form_reopen_condition(self):
        path, _ = self._signed_product_approval(
            "DEC-UNSUPPORTED-REOPEN",
            reopen_condition="ask the owner again whenever the agent is uncertain",
        )
        with self.assertRaisesRegex(ValueError, "reopen_condition"):
            import_product_approval(self.root, path)

    def test_product_decision_receipt_cannot_authorize_forced_human_action(self):
        approval_path, _ = self._signed_product_approval("DEC-NOT-OPERATIONAL")
        import_product_approval(self.root, approval_path)
        result = evaluate_escalation(
            self.root,
            {
                "risk_level": "L2",
                "category": "operational_action",
                "decision_id": "DEC-NOT-OPERATIONAL",
                "decision_scope": "MVP data layer",
                "action_owner": "product-owner",
                "decision_package": decision_package(
                    "Operational", "LOGIN-OWNER-REQUIRED"
                ),
            },
        )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertFalse(result["requires_response"])
        self.assertEqual(
            result["reason"],
            "request_contains_fields_outside_closed_category_schema",
        )

    def test_product_assumption_parent_replacement_fails_closed(self):
        approval_path, _ = self._signed_product_approval("DEC-TOCTOU")
        assumption_parent = self.root / ".sddgov/assumptions"
        parked = self.root / ".sddgov/assumptions-parked"
        outside = self.root / "outside-assumptions"
        outside.mkdir()
        (outside / "DEC-TOCTOU.txt").write_bytes(
            (assumption_parent / "DEC-TOCTOU.txt").read_bytes()
        )
        original_open = os.open
        replaced = False

        def replace_parent(path, flags, *args, **kwargs):
            nonlocal replaced
            if not replaced and str(path).endswith("DEC-TOCTOU.txt"):
                replaced = True
                assumption_parent.rename(parked)
                assumption_parent.symlink_to(outside, target_is_directory=True)
            return original_open(path, flags, *args, **kwargs)

        with (
            patch("sddgov.autonomy.os.open", side_effect=replace_parent),
            self.assertRaisesRegex(ValueError, "path changed"),
        ):
            import_product_approval(self.root, approval_path)

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
        approval_path, approval = self._signed_product_approval()
        imported = import_product_approval(self.root, approval_path)
        self.assertEqual(imported["verification"], "SIGNATURE_VERIFIED")
        second = evaluate_escalation(
            self.root,
            {
                "risk_level": "L2",
                "category": "product_decision",
                "decision_id": "DEC-023",
                "decision_scope": "MVP data layer",
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
        with self.assertRaisesRegex(ValueError, "already imported"):
            import_product_approval(self.root, approval_path)

        assumption_path = self.root / approval["receipt"]["assumptions"][0]["path"]
        assumption_path.write_text("changed baseline", encoding="utf-8")
        stale = evaluate_escalation(
            self.root,
            {
                "risk_level": "L2",
                "category": "product_decision",
                "decision_id": "DEC-023",
                "decision_scope": "MVP data layer",
                "assumptions_sha256": approval["receipt"]["assumptions_sha256"],
                "reopen_condition_triggered": False,
                "decision_package": decision_package(decision_id="DEC-023-STALE"),
            },
        )
        self.assertEqual(stale["state"], "ACTION_REQUIRED")

    def test_l2_product_reuse_rejects_foreign_authority_and_executor_fields(self):
        approval_path, _ = self._signed_product_approval("DEC-CLOSED-L2")
        import_product_approval(self.root, approval_path)
        foreign_fields = (
            {"approval_id": "APP-FOREIGN"},
            {"operation_id": "PROD-FOREIGN"},
            {"operation_payload": operation_payload("PROD-FOREIGN")},
            {"target": "synthetic:production"},
            {"parameters": {"mode": "execute"}},
            {"nested": {"operation_payload": operation_payload("PROD-NESTED")}},
        )
        for foreign in foreign_fields:
            with self.subTest(foreign=tuple(foreign)):
                result = evaluate_escalation(
                    self.root,
                    {
                        "risk_level": "L2",
                        "category": "product_decision",
                        "decision_id": "DEC-CLOSED-L2",
                        "decision_scope": "MVP data layer",
                        **foreign,
                    },
                )
                self.assertEqual(result["state"], "BLOCKED")
                self.assertEqual(
                    result["reason"],
                    "request_contains_fields_outside_closed_category_schema",
                )

    def test_l2_product_reuse_rejects_nested_decision_package(self):
        approval_path, _ = self._signed_product_approval("DEC-CLOSED-PACKAGE")
        import_product_approval(self.root, approval_path)
        package = decision_package("L2", "DEC-FOREIGN-PACKAGE")
        package["operation_payload"] = operation_payload("PROD-NESTED-PACKAGE")
        result = evaluate_escalation(
            self.root,
            {
                "risk_level": "L2",
                "category": "product_decision",
                "decision_id": "DEC-CLOSED-PACKAGE",
                "decision_scope": "MVP data layer",
                "decision_package": package,
            },
        )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertFalse(result["requires_response"])
        self.assertEqual(
            result["reason"],
            "existing_decision_reuse_must_not_include_decision_package",
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
        product_path, _ = self._signed_product_approval(
            "DEC-ARCH", "Architecture only", "architecture-baseline-v1"
        )
        import_product_approval(self.root, product_path)
        request = {
            "risk_level": "L3",
            "category": "high_risk_operation",
            "operation_id": "PROD-OP-1",
            "approval_id": "DEC-ARCH",
            "operation_payload": operation_payload("PROD-OP-1"),
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
            "BLOCKED",
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
            "operation_payload": operation_payload("PROD-CONCURRENT"),
            "decision_package": decision_package("L3", "APP-CONCURRENT-NEXT"),
        }

        def evaluate_once():
            return evaluate_escalation(self.root, request)["state"]

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: evaluate_once(), range(2)))
        self.assertEqual(sorted(results), ["ACTION_REQUIRED", "CONTINUE"])

    def test_l3_approval_is_bound_to_the_complete_operation_payload(self):
        signed_payload = operation_payload("PROD-PAYLOAD")
        receipt, _ = self._signed_operation_approval(
            "APP-PAYLOAD", "PROD-PAYLOAD", payload=signed_payload
        )
        import_operation_approval(self.root, receipt)
        changed_payload = json.loads(json.dumps(signed_payload))
        changed_payload["parameters"]["mode"] = "different-target-mode"
        request = {
            "risk_level": "L3",
            "category": "high_risk_operation",
            "operation_id": "PROD-PAYLOAD",
            "approval_id": "APP-PAYLOAD",
            "operation_payload": changed_payload,
            "decision_package": decision_package("L3", "APP-PAYLOAD-NEXT"),
        }
        self.assertEqual(evaluate_escalation(self.root, request)["state"], "ACTION_REQUIRED")
        decisions = json.loads(
            (self.root / ".sddgov/decisions.json").read_text(encoding="utf-8")
        )
        self.assertIsNone(decisions["decisions"][-1]["consumed_at"])

        request["operation_payload"] = signed_payload
        result = evaluate_escalation(self.root, request)
        self.assertEqual(result["state"], "CONTINUE")
        self.assertEqual(result["authorized_operation_payload"], signed_payload)

    def test_l3_runtime_context_mismatch_blocks_before_nonce_consumption(self):
        payload = operation_payload("PROD-CONTEXT")
        receipt, _ = self._signed_operation_approval(
            "APP-CONTEXT", "PROD-CONTEXT", payload=payload
        )
        import_operation_approval(self.root, receipt)
        self.runtime_context_path.write_text(
            json.dumps({
                "schema_version": "1.0",
                "repository": "zycaskevin/different-repository",
                "project": "synthetic-project",
                "environment": "synthetic-production",
            }),
            encoding="utf-8",
        )
        request = {
            "risk_level": "L3",
            "category": "high_risk_operation",
            "operation_id": "PROD-CONTEXT",
            "approval_id": "APP-CONTEXT",
            "operation_payload": payload,
            "decision_package": decision_package("L3", "APP-CONTEXT-NEXT"),
        }
        result = evaluate_escalation(self.root, request)
        self.assertEqual(result["state"], "BLOCKED")
        self.assertEqual(result["reason"], "l3_runtime_context_mismatch")
        decisions = json.loads(
            (self.root / ".sddgov/decisions.json").read_text(encoding="utf-8")
        )
        self.assertIsNone(decisions["decisions"][-1]["consumed_at"])

    def test_l3_outer_scope_must_equal_signed_payload_scope(self):
        path, envelope = self._signed_operation_approval("APP-SCOPE", "PROD-SCOPE")
        envelope["receipt"]["scope"] = "different scope"
        private_key = Ed25519PrivateKey.generate()
        # The mismatch is rejected before signer trust is relevant.
        canonical = json.dumps(
            envelope["receipt"], ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        envelope["signature"] = base64.b64encode(private_key.sign(canonical)).decode("ascii")
        path.write_text(json.dumps(envelope), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "scope does not match"):
            import_operation_approval(self.root, path)

    def test_l3_never_falls_back_to_clone_local_single_use(self):
        receipt, _ = self._signed_operation_approval("APP-BROKER", "PROD-BROKER")
        import_operation_approval(self.root, receipt)
        request = {
            "risk_level": "L3",
            "category": "high_risk_operation",
            "operation_id": "PROD-BROKER",
            "approval_id": "APP-BROKER",
            "operation_payload": operation_payload("PROD-BROKER"),
            "decision_package": decision_package("L3", "APP-BROKER-NEXT"),
        }
        self.nonce_broker.stop()
        try:
            with patch("sddgov.autonomy.L3_NONCE_BROKER", self.root / "missing-broker"):
                result = evaluate_escalation(self.root, request)
        finally:
            self.nonce_broker.start()
        self.assertEqual(result["state"], "BLOCKED")
        self.assertFalse(result["requires_response"])
        self.assertEqual(result["reason"], "l3_external_nonce_ledger_unavailable")

    def test_same_uid_fake_l3_broker_is_not_a_control_plane(self):
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            self.skipTest("same-UID non-root boundary requires a non-root test user")
        receipt, _ = self._signed_operation_approval("APP-FAKE", "PROD-FAKE")
        import_operation_approval(self.root, receipt)
        fake = self.root / "fake-broker"
        fake.write_text("#!/bin/sh\nprintf 'CONSUMED\\n'\n", encoding="utf-8")
        fake.chmod(0o755)
        request = {
            "risk_level": "L3",
            "category": "high_risk_operation",
            "operation_id": "PROD-FAKE",
            "approval_id": "APP-FAKE",
            "operation_payload": operation_payload("PROD-FAKE"),
            "decision_package": decision_package("L3", "APP-FAKE-NEXT"),
        }
        self.nonce_broker.stop()
        try:
            with patch("sddgov.autonomy.L3_NONCE_BROKER", fake):
                result = evaluate_escalation(self.root, request)
        finally:
            self.nonce_broker.start()
        self.assertEqual(result["state"], "BLOCKED")
        self.assertEqual(result["reason"], "l3_external_nonce_ledger_unavailable")

    def test_root_agent_cannot_consume_l3_broker_nonce(self):
        with patch("sddgov.autonomy.os.geteuid", return_value=0):
            self.assertFalse(_consume_nonce_via_control_plane("nonce-value-1", "a" * 64, "b" * 64))

    def test_l3_broker_path_is_fixed_for_supported_platform(self):
        expected = (
            Path("/private/var/db/sddgov/approval-broker.sock")
            if sys.platform == "darwin"
            else Path("/run/sddgov/approval-broker.sock")
        )
        self.assertEqual(L3_NONCE_BROKER, expected)

    def test_l3_broker_uses_real_platform_unix_socket_protocol(self):
        broker_path = self.root / "approval-broker.sock"
        directory = SimpleNamespace(
            st_mode=stat.S_IFDIR | 0o755, st_uid=0, st_nlink=1, st_dev=1, st_ino=1
        )
        broker = SimpleNamespace(
            st_mode=stat.S_IFSOCK | 0o660, st_uid=0, st_nlink=1, st_dev=1, st_ino=2
        )
        received = {}
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
            try:
                server.bind(str(broker_path))
            except PermissionError as exc:
                if exc.errno == 1:
                    self.skipTest("execution sandbox forbids Unix socket creation")
                raise
            server.listen(1)

            def serve_once():
                connection, _ = server.accept()
                with connection:
                    received["request"] = connection.recv(4096)
                    connection.sendall(b"CON")
                    threading.Event().wait(0.05)
                    connection.sendall(b"SUMED\n")

            worker = threading.Thread(target=serve_once)
            worker.start()
            with (
                patch("sddgov.autonomy.os.geteuid", return_value=501),
                patch("sddgov.autonomy.L3_NONCE_BROKER", broker_path),
                patch(
                    "pathlib.Path.lstat",
                    autospec=True,
                    side_effect=lambda path: broker if path == broker_path else directory,
                ),
            ):
                self.assertTrue(
                    _consume_nonce_via_control_plane(
                        "nonce-value-2", "a" * 64, "b" * 64
                    )
                )
            worker.join(timeout=5)
        self.assertIn(b'"action":"consume"', received["request"])

    def test_l3_broker_rejects_extra_response_bytes(self):
        directory = SimpleNamespace(st_mode=stat.S_IFDIR | 0o755, st_uid=0)
        broker = SimpleNamespace(st_mode=stat.S_IFSOCK | 0o660, st_uid=0)
        client = MagicMock()
        client.__enter__.return_value = client
        client.recv.side_effect = [b"CONSUMED\n", b"X"]
        with (
            patch("sddgov.autonomy.os.geteuid", return_value=501),
            patch(
                "pathlib.Path.lstat",
                autospec=True,
                side_effect=lambda path: broker if path == L3_NONCE_BROKER else directory,
            ),
            patch("sddgov.autonomy.socket.socket", return_value=client),
        ):
            self.assertFalse(
                _consume_nonce_via_control_plane(
                    "nonce-value-extra", "a" * 64, "b" * 64
                )
            )

    def test_l3_broker_symlinked_parent_fails_before_connection(self):
        linked_parent = SimpleNamespace(
            st_mode=stat.S_IFLNK | 0o777, st_uid=0, st_nlink=1, st_dev=1, st_ino=1
        )
        with (
            patch("sddgov.autonomy.os.geteuid", return_value=501),
            patch("pathlib.Path.lstat", autospec=True, return_value=linked_parent),
            patch("sddgov.autonomy.socket.socket") as socket_factory,
        ):
            self.assertFalse(
                _consume_nonce_via_control_plane(
                    "nonce-value-3", "a" * 64, "b" * 64
                )
            )
        socket_factory.assert_not_called()

    def test_operation_payload_cannot_embed_secret_material(self):
        payload = operation_payload("PROD-SECRET")
        payload["parameters"] = {
            "deployment": {"credentials": {"api_token": "must-not-be-stored"}}
        }
        receipt, _ = self._signed_operation_approval(
            "APP-SECRET", "PROD-SECRET", payload=payload
        )
        with self.assertRaisesRegex(ValueError, "reference secrets"):
            import_operation_approval(self.root, receipt)

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
                "operation_payload": operation_payload(
                    "PROD-ATTACKER-CONTROLLED"
                ),
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
        approval_path, _ = self._signed_product_approval("DEC-FAIL")
        with self.assertRaisesRegex(ValueError, "invalid contract"):
            import_product_approval(self.root, approval_path)

    def test_blocked_operational_action_does_not_stop_unrelated_work(self):
        result = evaluate_escalation(
            self.root,
            {
                "risk_level": "L3",
                "category": "operational_action",
                "unrelated_work_exists": True,
                "action_owner": "product-owner",
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
                "action_owner": "product-owner",
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

    def test_operational_action_is_durable_and_not_reprompted(self):
        request = {
            "risk_level": "L1",
            "category": "operational_action",
            "action_owner": "product-owner",
            "action_ttl_minutes": 60,
            "decision_package": decision_package("Operational", "LOGIN-DURABLE-1"),
        }
        first = evaluate_escalation(self.root, request)
        self.assertEqual(first["state"], "ACTION_REQUIRED")
        self.assertTrue(first["requires_response"])
        self.assertTrue(first["external_action_created"])

        second = evaluate_escalation(self.root, request)
        self.assertEqual(second["state"], "BLOCKED")
        self.assertFalse(second["requires_response"])
        self.assertEqual(second["reason"], "operational_action_already_pending")
        self.assertFalse(second["external_action_created"])

        store = json.loads(
            (self.root / ".sddgov/external-actions.json").read_text(encoding="utf-8")
        )
        self.assertEqual(len(store["actions"]), 1)
        self.assertEqual(store["actions"][0]["owner"], "product-owner")
        self.assertIn("expires_at", store["actions"][0])

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
        approval_path, approval = self._signed_product_approval(
            "DEC-DEPLOY-WEB",
            "production_deploy:web_app",
            "approved-release-baseline-v1",
        )
        import_product_approval(self.root, approval_path)
        gate = {name: True for name in DEPLOY_GUARDS}
        gate.update(
            {
                "risk_level": "L1",
                "deployment_class": "web_app",
                "baseline_decision_id": "DEC-DEPLOY-WEB",
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
