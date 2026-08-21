import io
import unittest
import urllib.error
from email.message import Message
from unittest.mock import patch

from scripts.check_release_environment import _get_json, check, validate_environment


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

    def test_api_read_retries_only_transient_failures_with_bounded_backoff(self):
        transient = urllib.error.HTTPError(
            "https://api.github.example.invalid",
            503,
            "synthetic unavailable",
            {},
            None,
        )
        with patch(
            "scripts.check_release_environment.urllib.request.urlopen",
            side_effect=[transient, io.BytesIO(b'{"ok": true}')],
        ) as urlopen, patch(
            "scripts.check_release_environment.time.sleep"
        ) as sleep:
            result = _get_json("https://api.github.example.invalid", "token")

        self.assertEqual(result, {"ok": True})
        self.assertEqual(urlopen.call_count, 2)
        sleep.assert_called_once_with(0.25)

    def test_api_read_does_not_retry_non_transient_http_error(self):
        permanent = urllib.error.HTTPError(
            "https://api.github.example.invalid",
            404,
            "synthetic missing",
            {},
            None,
        )
        with patch(
            "scripts.check_release_environment.urllib.request.urlopen",
            side_effect=permanent,
        ) as urlopen, patch(
            "scripts.check_release_environment.time.sleep"
        ) as sleep, self.assertRaises(urllib.error.HTTPError):
            _get_json("https://api.github.example.invalid", "token")

        self.assertEqual(urlopen.call_count, 1)
        sleep.assert_not_called()

    def test_rate_limit_retry_honors_retry_after_and_closes_response(self):
        headers = Message()
        headers["Retry-After"] = "2"
        limited = urllib.error.HTTPError(
            "https://api.github.example.invalid",
            429,
            "synthetic rate limit",
            headers,
            None,
        )
        with patch.object(limited, "close", wraps=limited.close) as close, patch(
            "scripts.check_release_environment.urllib.request.urlopen",
            side_effect=[limited, io.BytesIO(b'{"ok": true}')],
        ) as urlopen, patch(
            "scripts.check_release_environment.time.sleep"
        ) as sleep:
            result = _get_json("https://api.github.example.invalid", "token")

        self.assertEqual(result, {"ok": True})
        self.assertEqual(urlopen.call_count, 2)
        close.assert_called_once_with()
        sleep.assert_called_once_with(2.0)

    def test_rate_limit_retry_uses_reset_or_bounded_secondary_delay(self):
        for label, headers, expected in (
            ("reset", {"X-RateLimit-Reset": "110"}, 10.0),
            ("secondary", {}, 60.0),
        ):
            with self.subTest(label=label):
                limited = urllib.error.HTTPError(
                    "https://api.github.example.invalid",
                    403,
                    "synthetic rate limit",
                    headers,
                    None,
                )
                with patch(
                    "scripts.check_release_environment.urllib.request.urlopen",
                    side_effect=[limited, io.BytesIO(b'{"ok": true}')],
                ), patch(
                    "scripts.check_release_environment.time.sleep"
                ) as sleep, patch(
                    "scripts.check_release_environment.time.time",
                    return_value=100.0,
                ):
                    self.assertEqual(
                        _get_json("https://api.github.example.invalid", "token"),
                        {"ok": True},
                    )
                sleep.assert_called_once_with(expected)

    def test_repository_slug_rejects_normalizable_or_invalid_paths(self):
        for repository in ("owner/..", "owner/a b", "owner/repo/extra"):
            with self.subTest(repository=repository), self.assertRaisesRegex(
                ValueError, "owner/name"
            ), patch(
                "scripts.check_release_environment._get_json"
            ) as get_json:
                check(repository, "testpypi", "v0.2.0rc1", "token")
            get_json.assert_not_called()


if __name__ == "__main__":
    unittest.main()
