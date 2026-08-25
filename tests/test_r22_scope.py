import unittest

from sddgov.r22_scope import requires_r22_validation


class R22ScopeTests(unittest.TestCase):
    def test_unrelated_af27_change_does_not_require_r22(self):
        self.assertFalse(
            requires_r22_validation(
                [
                    "src/sddgov/production_containment.py",
                    "tests/test_production_containment.py",
                    "docs/TRUSTED_RUNNER_V0_2_AF27.md",
                ]
            )
        )

    def test_authority_inputs_and_gate_configuration_require_r22(self):
        for path in (
            ".sddgov/ci-cost-guard.json",
            ".sddgov/decisions.json",
            "src/sddgov/owner_approval.py",
            "work-packages/DEC-RC1-APPROVER-AUTHORITY-R22.md",
            "src/sddgov/resources/governance/policies/autonomy-policy.json",
        ):
            with self.subTest(path=path):
                self.assertTrue(requires_r22_validation([path]))

    def test_unknown_or_malformed_change_set_fails_closed(self):
        self.assertTrue(requires_r22_validation(None))
        self.assertTrue(requires_r22_validation([]))
        for path in (
            "../owner_approval.py",
            "/tmp/owner_approval.py",
            "./src/sddgov/autonomy.py",
            "src\\sddgov\\autonomy.py",
        ):
            with self.subTest(path=path):
                with self.assertRaisesRegex(ValueError, "canonical repository-relative"):
                    requires_r22_validation([path])
