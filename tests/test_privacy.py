import unittest

from llm_health.core.models import Observation
from llm_health.core.privacy import PrivacyError, assert_safe_text, validate_profile_alias
from llm_health.deid import deidentify_text


class PrivacyTests(unittest.TestCase):
    def test_profile_aliases_only(self):
        self.assertEqual(validate_profile_alias("Rod"), "rod")
        self.assertEqual(validate_profile_alias("Sol"), "sol")
        with self.assertRaises(PrivacyError):
            validate_profile_alias("father")
        with self.assertRaises(PrivacyError):
            validate_profile_alias("full name")

    def test_blocks_source_paths_and_raw_filenames(self):
        with self.assertRaises(PrivacyError):
            assert_safe_text("read /Users/example/private/report.pdf")
        with self.assertRaises(PrivacyError):
            assert_safe_text("source was lab-result.pdf")
        with self.assertRaises(PrivacyError):
            assert_safe_text("person@example.com")

    def test_observation_blocks_private_note(self):
        with self.assertRaises(PrivacyError):
            Observation(profile_id="rod", marker="ALT", note="from raw.pdf")

    def test_deidentify_text_removes_common_identifiers(self):
        result = deidentify_text(
            "Patient: Jane Doe\n"
            "Email: jane@example.com\n"
            "Path: /Users/example/private/result.pdf\n"
            "Date: 2026-01-05\n"
        )
        self.assertIn("[PERSON_", result.text)
        self.assertIn("[EMAIL_", result.text)
        self.assertIn("[PATH_", result.text)
        self.assertIn("[DATE_", result.text)
        self.assertNotIn("Jane", result.text)
        self.assertNotIn("example.com", result.text)
        self.assertNotIn("/Users", result.text)
        self.assertNotIn(".pdf", result.text)
        self.assertGreaterEqual(result.entity_count, 4)


if __name__ == "__main__":
    unittest.main()
