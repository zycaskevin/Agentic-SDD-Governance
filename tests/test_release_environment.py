import http.client
import io
import json
import sys
import tempfile
import unittest
import urllib.error
from contextlib import redirect_stdout
from email.message import Message
from pathlib import Path
from unittest.mock import patch

from scripts.check_release_environment import (
    MAX_RESPONSE_BYTES,
    _get_json,
    check,
    load_release_authority,
    main,
    validate_environment,
)


class ReleaseEnvironmentTests(unittest.TestCase):
    def test_preflight_maps_malformed_http_response_to_exit_one(self):
        output = io.StringIO()
        with patch.dict(
            "scripts.check_release_environment.os.environ",
            {
                "GITHUB_REPOSITORY": "owner/repository",
                "GITHUB_TOKEN": "synthetic-token",
            },
            clear=True,
        ), patch.object(
            sys,
            "argv",
            [
                "check_release_environment.py",
                "--environment",
                "release",
                "--expected-ref",
                "main",
                "--expected-ref-type",
                "branch",
                "--authority-policy",
                "synthetic-policy.json",
            ],
        ), patch(
            "scripts.check_release_environment.check",
            side_effect=http.client.BadStatusLine("synthetic malformed response"),
        ), redirect_stdout(output):
            status = main()

        self.assertEqual(status, 1)
        self.assertIn("release environment preflight failed", output.getvalue())

    def _environment(self):
        return {
            "can_admins_bypass": False,
            "protection_rules": [
                {
                    "type": "required_reviewers",
                    "prevent_self_review": True,
                    "reviewers": [
                        {
                            "type": "User",
                            "reviewer": {"id": 123, "login": "owner"},
                        }
                    ],
                }
            ],
            "deployment_branch_policy": {
                "protected_branches": False,
                "custom_branch_policies": True,
            },
        }

    def test_exact_protected_workflow_branch_passes(self):
        errors = validate_environment(
            self._environment(),
            {
                "total_count": 1,
                "branch_policies": [{"name": "main", "type": "branch"}],
            },
            "main",
            "branch",
            [("User", 123, "owner")],
        )
        self.assertEqual(errors, [])

    def test_incomplete_policy_page_fails_closed(self):
        errors = validate_environment(
            self._environment(),
            {
                "total_count": 2,
                "branch_policies": [{"name": "main", "type": "branch"}],
            },
            "main",
            "branch",
            [("User", 123, "owner")],
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
            "main",
            "branch",
            [("User", 123, "owner")],
        )
        self.assertGreaterEqual(len(errors), 4)
        self.assertTrue(any("administrator bypass" in error for error in errors))
        self.assertTrue(any("exact deployment ref" in error for error in errors))

    def test_wrong_or_extra_release_reviewer_fails_closed(self):
        for reviewers in (
            [{"type": "User", "reviewer": {"id": 456, "login": "other"}}],
            [
                {"type": "User", "reviewer": {"id": 123, "login": "owner"}},
                {"type": "User", "reviewer": {"id": 456, "login": "other"}},
            ],
        ):
            with self.subTest(reviewers=reviewers):
                environment = self._environment()
                environment["protection_rules"][0]["reviewers"] = reviewers
                errors = validate_environment(
                    environment,
                    {
                        "total_count": 1,
                        "branch_policies": [{"name": "main", "type": "branch"}],
                    },
                    "main",
                    "branch",
                    [("User", 123, "owner")],
                )
                self.assertTrue(any("reviewer identity" in error for error in errors))

    def test_release_authority_policy_binds_repository_environment_and_identity(self):
        policy = {
            "schema_version": "1.0",
            "repository": "owner/repository",
            "environment": "release",
            "reviewers": [{"type": "User", "id": 123, "login": "owner"}],
        }
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "release-authority.json"
            path.write_text(json.dumps(policy), encoding="utf-8")
            self.assertEqual(
                load_release_authority(path, "owner/repository", "release"),
                [("User", 123, "owner")],
            )
            with self.assertRaisesRegex(ValueError, "does not match"):
                load_release_authority(path, "other/repository", "release")
            with self.assertRaisesRegex(ValueError, "does not match"):
                load_release_authority(path, "owner/repository", "staging")

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

    def test_api_read_without_token_omits_authorization_header(self):
        with patch(
            "scripts.check_release_environment.urllib.request.urlopen",
            return_value=io.BytesIO(b'{"ok": true}'),
        ) as urlopen:
            result = _get_json("https://api.github.example.invalid")

        self.assertEqual(result, {"ok": True})
        request = urlopen.call_args.args[0]
        self.assertIsNone(request.get_header("Authorization"))
        self.assertEqual(
            request.get_header("X-github-api-version"),
            "2022-11-28",
        )

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

    def test_api_read_bounds_the_response_body(self):
        with patch(
            "scripts.check_release_environment.urllib.request.urlopen",
            return_value=io.BytesIO(b"x" * (MAX_RESPONSE_BYTES + 1)),
        ), self.assertRaisesRegex(ValueError, "bounded size"):
            _get_json("https://api.github.example.invalid", "token")

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

    def test_api_read_does_not_retry_a_non_rate_limit_403(self):
        forbidden = urllib.error.HTTPError(
            "https://api.github.example.invalid",
            403,
            "forbidden",
            {},
            io.BytesIO(b'{"message":"Resource not accessible by integration"}'),
        )
        with patch(
            "scripts.check_release_environment.urllib.request.urlopen",
            side_effect=forbidden,
        ) as urlopen, patch(
            "scripts.check_release_environment.time.sleep"
        ) as sleep, self.assertRaises(urllib.error.HTTPError):
            _get_json("https://api.github.example.invalid", "token")

        self.assertEqual(urlopen.call_count, 1)
        sleep.assert_not_called()

    def test_repository_slug_rejects_normalizable_or_invalid_paths(self):
        for repository in (
            "owner/..",
            "owner/a b",
            "owner/repo/extra",
            "owner/" + "r" * 101,
        ):
            with self.subTest(repository=repository), self.assertRaisesRegex(
                ValueError, "owner/name"
            ), patch(
                "scripts.check_release_environment._get_json"
            ) as get_json:
                check(
                    repository,
                    "release",
                    "main",
                    "branch",
                    "token",
                    Path("synthetic-policy.json"),
                )
            get_json.assert_not_called()

    def test_oversized_operation_inputs_fail_before_policy_or_network_access(self):
        cases = (
            ("owner/repository", "e" * 256, "main", None, "environment"),
            ("owner/repository", "release", "m" * 256, None, "exact ref"),
            ("owner/repository", "release", "main", "x" * 8193, "token"),
        )
        for repository, environment, expected_ref, token, error in cases:
            with self.subTest(error=error), patch(
                "scripts.check_release_environment.load_release_authority"
            ) as authority, patch(
                "scripts.check_release_environment._get_json"
            ) as get_json, self.assertRaisesRegex(ValueError, error):
                check(
                    repository,
                    environment,
                    expected_ref,
                    "branch",
                    token,
                    Path("synthetic-policy.json"),
                )
            authority.assert_not_called()
            get_json.assert_not_called()

    def test_authority_policy_and_reviewer_login_are_bounded(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "release-authority.json"
            path.write_bytes(b"x" * (64 * 1024 + 1))
            with self.assertRaisesRegex(ValueError, "byte limit"):
                load_release_authority(path, "owner/repository", "release")

            path.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "repository": "owner/repository",
                        "environment": "release",
                        "reviewers": [
                            {"type": "Team", "id": 123, "login": "x" * 101}
                        ],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "reviewer login"):
                load_release_authority(path, "owner/repository", "release")

            path.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "repository": "owner/repository",
                        "environment": "release",
                        "reviewers": [
                            {"type": "User", "id": 1 << 63, "login": "owner"}
                        ],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "reviewer ID"):
                load_release_authority(path, "owner/repository", "release")


if __name__ == "__main__":
    unittest.main()
