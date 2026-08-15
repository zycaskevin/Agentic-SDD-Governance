import unittest

from sddgov.redaction import redact_text


class RedactionTests(unittest.TestCase):
    def test_masks_credentials_and_identifiers(self):
        source = (
            "Authorization: Bearer abc.def.ghi\n"
            "Cookie: session=secret\n"
            "api_key=sk-example-secret\n"
            "owner@example.com\n"
        )
        cleaned, counts = redact_text(source)
        self.assertNotIn("abc.def.ghi", cleaned)
        self.assertNotIn("session=secret", cleaned)
        self.assertNotIn("sk-example-secret", cleaned)
        self.assertNotIn("owner@example.com", cleaned)
        self.assertIn("authorization", counts)
        self.assertIn("cookie", counts)
        self.assertIn("secret-field", counts)
        self.assertIn("email", counts)

    def test_removes_private_key_block(self):
        source = "-----BEGIN " + "PRIVATE KEY-----\nsecret\n-----END " + "PRIVATE KEY-----"
        cleaned, counts = redact_text(source)
        self.assertEqual(cleaned, "[REDACTED_PRIVATE_KEY]")
        self.assertEqual(counts["private-key"], 1)

    def test_masks_explicit_password_patient_and_customer_identifiers(self):
        source = (
            "password=correct-horse\n"
            "patient_id=patient-123\n"
            "customer_identifier: customer-456\n"
        )
        cleaned, counts = redact_text(source)
        self.assertNotIn("correct-horse", cleaned)
        self.assertNotIn("patient-123", cleaned)
        self.assertNotIn("customer-456", cleaned)
        self.assertEqual(counts["password"], 1)
        self.assertEqual(counts["patient-identifier"], 1)
        self.assertEqual(counts["customer-identifier"], 1)

    def test_masks_quoted_json_keys_and_escaped_quoted_values(self):
        source = (
            r'''{"password":"correct-\"horse","api_key":"sk-\"secret",'''
            r'''"patient_id":"patient-\"123","customer_identifier":"customer-\"456"}'''
        )
        cleaned, counts = redact_text(source)
        for fragment in ("correct", "sk-", "patient-", "customer-"):
            self.assertNotIn(fragment, cleaned)
        self.assertEqual(counts["password"], 1)
        self.assertEqual(counts["secret-field"], 1)
        self.assertEqual(counts["patient-identifier"], 1)
        self.assertEqual(counts["customer-identifier"], 1)

    def test_masks_uppercase_snake_case_credentials(self):
        source = (
            "DB_PASSWORD=database-secret\n"
            "SECRET_KEY=signing-secret\n"
            "ACCESS_KEY=provider-secret\n"
            "secret-key=hyphen-secret\n"
            "AWS_ACCESS_KEY_ID=aws-secret\n"
        )
        cleaned, counts = redact_text(source)
        for fragment in (
            "database-secret",
            "signing-secret",
            "provider-secret",
            "hyphen-secret",
            "aws-secret",
        ):
            self.assertNotIn(fragment, cleaned)
        self.assertEqual(counts["password"], 1)
        self.assertEqual(counts["secret-field"], 4)

    def test_masks_known_provider_credential_identifiers(self):
        source = (
            "aws_access_key_id=AKIAIOSFODNN7EXAMPLE\n"
            "github_token=ghp_0123456789abcdefghijklmnopqrstuvwxyzAB\n"
            "ordinary synthetic sentence with no credential\n"
        )
        cleaned, counts = redact_text(source)
        self.assertNotIn("AKIAIOSFODNN7EXAMPLE", cleaned)
        self.assertNotIn("ghp_0123456789abcdefghijklmnopqrstuvwxyzAB", cleaned)
        self.assertGreaterEqual(counts.get("provider-credential", 0), 2)
        self.assertIn("ordinary synthetic sentence", cleaned)

    def test_clean_zero_match_text_remains_eligible(self):
        source = "Synthetic test completed with no credentials."
        cleaned, counts = redact_text(source)
        self.assertEqual(cleaned, source)
        self.assertEqual(counts, {})


if __name__ == "__main__":
    unittest.main()
