import json
import unittest

from llm_health.core.models import ContextNote, EnrolledProfile, Observation, TestCandidate


class ModelTests(unittest.TestCase):
    def test_observation_serializes_json(self):
        obs = Observation(
            profile_id="rod",
            marker="ALT",
            value=76,
            unit="U/L",
            category="liver",
            reference_range="0-55",
        )
        payload = obs.to_dict()
        self.assertEqual(payload["profile_id"], "rod")
        self.assertEqual(payload["reference_range"], "0-55")
        self.assertIn("OBSERVED", payload["tags"])
        json.dumps(payload)
        clone = Observation.from_dict(payload)
        self.assertEqual(clone.marker, "ALT")
        self.assertEqual(clone.reference_range, "0-55")

    def test_pending_and_flag_semantics(self):
        pending = Observation(profile_id="rod", marker="Mercury", value=None, flag="pending")
        self.assertTrue(pending.is_pending)
        self.assertFalse(pending.is_flagged)
        high = Observation(profile_id="rod", marker="ALT", value=76, flag="high")
        self.assertTrue(high.is_flagged)

    def test_candidate_score_is_bounded(self):
        candidate = TestCandidate(name="context questionnaire", role="close confounder gap")
        self.assertGreaterEqual(candidate.score(), 0.0)
        self.assertLessEqual(candidate.score(), 1.0)

    def test_context_note_has_visible_context_tag(self):
        note = ContextNote(
            profile_id="rod",
            subject="GI",
            status="self-reported fine",
            note="Self-reported current status is fine.",
        )
        payload = note.to_dict()
        self.assertIn("CONTEXT", payload["tags"])
        clone = ContextNote.from_dict(payload)
        self.assertEqual(clone.subject, "GI")

    def test_enrolled_profile_uses_birth_year_month_only(self):
        profile = EnrolledProfile(profile_id="lele", birth_year=2026, birth_month=1)
        self.assertEqual(profile.profile_id, "lele")
        self.assertEqual(profile.birth_label, "2026-01")
        self.assertIn("CONTEXT", profile.tags)


if __name__ == "__main__":
    unittest.main()
