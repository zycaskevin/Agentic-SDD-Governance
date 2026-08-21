import unittest

from scripts.check_release_environment import validate_environment


class ReleaseEnvironmentTests(unittest.TestCase):
    def _environment(self):
        return {
            "can_admins_bypass": False,
            "protection_rules": [
                {
                    "type": "required_reviewers",
                    "prevent_self_review": True,
                    "reviewers": [{"type": "User", "reviewer": {"login": "owner"}}],
                }
            ],
            "deployment_branch_policy": {
                "protected_branches": False,
                "custom_branch_policies": True,
            },
        }

    def test_exact_protected_tag_passes(self):
        errors = validate_environment(
            self._environment(),
            {
                "total_count": 1,
                "branch_policies": [{"name": "v0.2.0rc1", "type": "tag"}],
            },
            "v0.2.0rc1",
        )
        self.assertEqual(errors, [])

    def test_incomplete_policy_page_fails_closed(self):
        errors = validate_environment(
            self._environment(),
            {
                "total_count": 2,
                "branch_policies": [{"name": "v0.2.0rc1", "type": "tag"}],
            },
            "v0.2.0rc1",
        )
        self.assertTrue(any("complete policy inventory" in error for error in errors))

    def test_missing_review_or_broad_policy_fails_closed(self):
        environment = self._environment()
        environment["can_admins_bypass"] = True
        environment["protection_rules"][0]["prevent_self_review"] = False
        environment["protection_rules"][0]["reviewers"] = []
        errors = validate_environment(
            environment,
            {
                "total_count": 1,
                "branch_policies": [{"name": "v*", "type": "tag"}],
            },
            "v0.2.0rc1",
        )
        self.assertGreaterEqual(len(errors), 4)
        self.assertTrue(any("administrator bypass" in error for error in errors))
        self.assertTrue(any("exact tag" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
