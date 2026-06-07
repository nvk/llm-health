import tempfile
import unittest

from llm_health.core.models import Observation
from llm_health.engine import ReviewEngine
from llm_health.stores import LocalHealthStore


class ReviewEngineTests(unittest.TestCase):
    def test_flagged_new_category_queues_research(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalHealthStore(tmp)
            store.init()
            obs = Observation(
                profile_id="rod",
                marker="ALT",
                value=76,
                unit="U/L",
                category="liver",
                flag="high",
            )
            result = ReviewEngine(store).review_new_observations("rod", [obs])
            self.assertGreaterEqual(result.interest_score, 0.60)
            self.assertEqual(len(result.research_jobs), 1)
            self.assertTrue(any("Flagged" in card.title for card in result.cards))

    def test_large_delta_trigger(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalHealthStore(tmp)
            store.init()
            store.append_observation(
                Observation(profile_id="rod", marker="ALT", value=40, unit="U/L", category="liver")
            )
            obs = Observation(
                profile_id="rod", marker="ALT", value=80, unit="U/L", category="liver"
            )
            result = ReviewEngine(store).review_new_observations("rod", [obs], persist=False)
            self.assertIn("large_delta", result.event.triggers)

    def test_repeated_review_does_not_duplicate_cards_or_jobs(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalHealthStore(tmp)
            store.init()
            obs = Observation(
                profile_id="rod",
                marker="ALT",
                value=76,
                unit="U/L",
                category="liver",
                flag="high",
                observation_id="obs_repeat_alt",
            )
            ReviewEngine(store).review_new_observations("rod", [obs])
            store.append_observation(obs)
            ReviewEngine(store).review_new_observations("rod", [obs])

            self.assertEqual(len(store.quick_review_cards("rod")), 2)
            self.assertEqual(len(store.research_jobs("rod")), 1)

    def test_observation_upsert_backfills_reference_range(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalHealthStore(tmp)
            store.init()
            store.append_observation(
                Observation(
                    profile_id="rod",
                    marker="Mercury whole blood",
                    value=1,
                    unit="ug/L",
                    category="Heavy metals",
                    observation_id="obs_mercury",
                )
            )
            store.append_observation(
                Observation(
                    profile_id="rod",
                    marker="Mercury whole blood",
                    value=1,
                    unit="ug/L",
                    category="Heavy metals",
                    observation_id="obs_mercury",
                    reference_range="Normal population: <5.0",
                )
            )
            observations = store.observations("rod")
            self.assertEqual(len(observations), 1)
            self.assertEqual(observations[0].reference_range, "Normal population: <5.0")


if __name__ == "__main__":
    unittest.main()
