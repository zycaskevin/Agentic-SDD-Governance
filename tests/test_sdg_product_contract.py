import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "specs" / "sdg-product-contract.json"
SCHEMA_PATH = ROOT / "schemas" / "sdg-product-contract.schema.json"


def _contract():
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


class SDGProductContractTests(unittest.TestCase):
    def test_product_contract_validates_against_schema(self):
        contract = _contract()
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(contract)

    def test_development_and_release_readiness_require_zero_owner_operations(self):
        channels = _contract()["channels"]
        for name in ("development", "release_readiness"):
            with self.subTest(channel=name):
                self.assertIs(channels[name]["reality_effects"], False)
                self.assertEqual(channels[name]["owner_operations_max"], 0)

    def test_machine_integrity_never_becomes_owner_ui(self):
        contract = _contract()
        forbidden = set(
            contract["channels"]["development"]["human_ui_forbidden"]
        )
        self.assertLessEqual(
            {"sha256", "base_ref", "head_ref", "receipt", "dep_manifest"},
            forbidden,
        )
        self.assertIs(contract["integrity"]["sha256_retained"], True)
        self.assertIs(contract["integrity"]["owner_handles_hashes"], False)

    def test_team_standard_l2_is_one_plain_language_choice_without_crypto_ceremony(self):
        decision = _contract()["product_decisions"]
        self.assertEqual(decision["level"], "L2")
        self.assertEqual(decision["profile"], "team-standard")
        self.assertEqual(decision["owner_operations_max"], 1)
        self.assertEqual(decision["interaction"], "bounded_plain_language_choice")
        self.assertIs(decision["cryptographic_receipt_required"], False)
        self.assertEqual(
            decision["signed_receipt_profiles_retained"],
            ["solo-fast", "regulated"],
        )

    def test_merge_escalates_only_for_real_l3_effects(self):
        merge = _contract()["merge"]
        self.assertEqual(merge["default_level"], "L1")
        self.assertIs(merge["intrinsically_l3"], False)
        self.assertEqual(
            merge["escalate_to_l3_only_when"],
            [
                "merge_triggers_production_deploy",
                "merge_triggers_publication",
                "merge_triggers_other_l3_effect",
            ],
        )

    def test_review_findings_never_route_through_owner(self):
        self.assertEqual(
            _contract()["review"],
            {
                "independent_review_retained": True,
                "owner_relays_findings": False,
                "main_agent_absorbs_findings": True,
                "automated_third_party_review": "required_when_service_returns_an_actual_review",
                "skip_or_unavailable_fallback": "signed_independent_review_plus_full_gate_and_hosted_ci",
                "provider_status_without_review_is_not_review": True,
                "external_provider_is_single_merge_blocker": False,
                "automatic_retry_limit_per_exact_revision": 1,
            },
        )

    def test_release_handoff_is_machine_bound_before_one_native_approval(self):
        handoff = _contract()["release_handoff"]
        self.assertEqual(handoff["source_channel"], "release_readiness")
        self.assertEqual(handoff["consumer_channel"], "production_action")
        self.assertIs(handoff["machine_verified_before_owner_approval"], True)
        self.assertIs(handoff["owner_handles_integrity_fields"], False)
        self.assertEqual(handoff["protected_environment_jobs"], 1)
        self.assertEqual(
            set(handoff["required_bindings"]),
            {
                "repository",
                "readiness_workflow_path",
                "readiness_run_id",
                "readiness_run_attempt",
                "release_tag",
                "head_sha",
                "trusted_verifier_sha",
                "artifact_name",
            },
        )

    def test_strong_authorization_requires_reality_effect_and_distinct_boundary(self):
        strong = _contract()["strong_authorization"]
        self.assertIs(strong["default_enabled"], False)
        self.assertEqual(
            strong["allowed_only_when"],
            {"true_reality_effect": True, "distinct_trust_boundary": True},
        )

    def test_installer_never_activates_strong_authorization_by_default(self):
        self.assertEqual(
            _contract()["installer"],
            {
                "default_profile": "team-standard",
                "development_owner_operations": 0,
                "release_readiness_owner_operations": 0,
                "broker_service": "not_installed_or_started",
                "owner_signing": "not_created_or_configured",
                "strong_authorization": "inactive_until_separately_provisioned",
                "copied_resources_are_authority": False,
            },
        )

    def test_legacy_rc1_security_work_is_preserved_but_not_a_default_dependency(self):
        legacy = _contract()["legacy_rc1"]
        self.assertIs(legacy["release_work_paused"], True)
        self.assertIs(legacy["broker_default_dependency"], False)
        self.assertIs(legacy["bootstrap_default_dependency"], False)
        self.assertIs(legacy["artifacts_deleted"], False)
