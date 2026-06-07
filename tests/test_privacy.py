import unittest

from llm_health.core.models import Observation
from llm_health.core.privacy import PrivacyError, assert_safe_text, validate_profile_alias


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


if __name__ == "__main__":
    unittest.main()
