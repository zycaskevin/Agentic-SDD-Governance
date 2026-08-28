import io
import unittest
import urllib.error
from unittest.mock import patch

from scripts.check_release_absence import (
    MAX_RESPONSE_BYTES,
    _get_optional_json,
    check_release_absence,
)


class ReleaseAbsenceTests(unittest.TestCase):
    def test_all_three_absent_allows_one_approval_path(self):
        with patch(
            "scripts.check_release_absence._get_optional_json",
            side_effect=[None, None, None],
        ) as get_json:
            check_release_absence(
                "owner/repository",
                "agentic-sdd-governance",
                "0.2.0rc1",
                "v0.2.0rc1",
                "synthetic-token",
            )
        self.assertEqual(get_json.call_count, 3)

    def test_any_partial_or_complete_publication_blocks_before_approval(self):
        for results, target in (
            ([{"info": {}}, None, None], "TestPyPI"),
            ([None, {"tag_name": "v0.2.0rc1"}, None], "GitHub Release"),
            ([None, None, {"info": {}}], "PyPI"),
        ):
            with self.subTest(target=target), patch(
                "scripts.check_release_absence._get_optional_json",
                side_effect=results,
            ), self.assertRaisesRegex(ValueError, target):
                check_release_absence(
                    "owner/repository",
                    "agentic-sdd-governance",
                    "0.2.0rc1",
                    "v0.2.0rc1",
                    "synthetic-token",
                )

    def test_only_not_found_means_absent(self):
        missing = urllib.error.HTTPError(
            "https://example.invalid/resource", 404, "not found", {}, None
        )
        with patch.object(missing, "close", wraps=missing.close) as close, patch(
            "scripts.check_release_absence.urllib.request.urlopen",
            side_effect=missing,
        ):
            self.assertIsNone(_get_optional_json("https://example.invalid/resource"))
        close.assert_called_once_with()

    def test_unexpected_http_or_non_object_response_fails_closed(self):
        unavailable = urllib.error.HTTPError(
            "https://example.invalid/resource", 503, "unavailable", {}, None
        )
        with patch(
            "scripts.check_release_absence.urllib.request.urlopen",
            side_effect=unavailable,
        ), self.assertRaises(urllib.error.HTTPError):
            _get_optional_json("https://example.invalid/resource")

        with patch(
            "scripts.check_release_absence.urllib.request.urlopen",
            return_value=io.BytesIO(b"[]"),
        ), self.assertRaisesRegex(ValueError, "non-object"):
            _get_optional_json("https://example.invalid/resource")

        with patch(
            "scripts.check_release_absence.urllib.request.urlopen",
            return_value=io.BytesIO(b"x" * (MAX_RESPONSE_BYTES + 1)),
        ), self.assertRaisesRegex(ValueError, "bounded size"):
            _get_optional_json("https://example.invalid/resource")

    def test_release_identity_inputs_are_one_exact_bounded_tuple(self):
        cases = (
            ("owner/repository/extra", "package", "1.0", "v1.0", "repository"),
            ("owner/" + "r" * 101, "package", "1.0", "v1.0", "repository"),
            ("owner/repository", "bad package", "1.0", "v1.0", "package"),
            ("owner/repository", "package", "../1.0", "v../1.0", "version"),
            ("owner/repository", "package", "1.0", "v2.0", "version"),
        )
        for repository, package, version, tag, error in cases:
            with self.subTest(error=error), patch(
                "scripts.check_release_absence._get_optional_json"
            ) as request, self.assertRaisesRegex(ValueError, error):
                check_release_absence(
                    repository,
                    package,
                    version,
                    tag,
                    "synthetic-token",
                )
            request.assert_not_called()

    def test_oversized_token_is_rejected_before_any_network_request(self):
        with patch(
            "scripts.check_release_absence._get_optional_json"
        ) as request, self.assertRaisesRegex(ValueError, "token"):
            check_release_absence(
                "owner/repository",
                "package",
                "1.0",
                "v1.0",
                "x" * 8193,
            )
        request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
