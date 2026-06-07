import tempfile
import unittest

from llm_health.core.models import EnrolledProfile
from llm_health.core.privacy import PrivacyError
from llm_health.stores import LocalHealthStore


class StoreProfileTests(unittest.TestCase):
    def test_enrolled_profiles_merge_defaults_and_upsert_custom_aliases(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalHealthStore(tmp)
            store.init()

            self.assertEqual(
                [profile.profile_id for profile in store.enrolled_profiles()], ["cara", "rod"]
            )

            store.enroll_profile(EnrolledProfile(profile_id="Sol", birth_year=2018, role="child"))
            store.enroll_profile(
                EnrolledProfile(profile_id="sol", birth_year=2018, birth_month=2, role="child")
            )
            store.enroll_profile(EnrolledProfile(profile_id="rod", birth_year=1983, role="adult"))

            profiles = store.enrolled_profiles(include_defaults=True)
            ids = [profile.profile_id for profile in profiles]
            self.assertEqual(ids, ["cara", "rod", "sol"])
            self.assertEqual(ids.count("rod"), 1)
            self.assertEqual(ids.count("sol"), 1)

            sol = next(profile for profile in profiles if profile.profile_id == "sol")
            self.assertEqual(sol.birth_label, "2018-02")
            self.assertTrue(store.profile_exists("Sol"))

            rod = next(profile for profile in profiles if profile.profile_id == "rod")
            self.assertEqual(rod.birth_label, "1983")
            self.assertEqual(rod.role, "adult")

    def test_profile_store_rejects_private_notes_before_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalHealthStore(tmp)
            store.init()
            with self.assertRaises(PrivacyError):
                store.enroll_profile(
                    EnrolledProfile(
                        profile_id="sol", birth_year=2018, note="from /Users/me/raw.pdf"
                    )
                )
            self.assertEqual(store.enrolled_profiles(include_defaults=False), [])


if __name__ == "__main__":
    unittest.main()
