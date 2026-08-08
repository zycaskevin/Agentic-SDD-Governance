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


if __name__ == "__main__":
    unittest.main()
