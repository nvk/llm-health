import tempfile
import unittest

from llm_health.core.models import Observation
from llm_health.engine import DiagnosticGapEngine, LeastHarmEngine
from llm_health.stores import LocalHealthStore


class GapAndLeastHarmTests(unittest.TestCase):
    def test_liver_gap_candidates(self):
        obs = Observation(profile_id="rod", marker="ALT", value=76, unit="U/L", category="liver")
        gaps = DiagnosticGapEngine().create_gaps("rod", [obs])
        self.assertTrue(any("Liver" in gap.title for gap in gaps))
        names = [candidate.name for gap in gaps for candidate in gap.candidates]
        self.assertIn("GGT", names)
        self.assertIn("direct + indirect bilirubin", names)

    def test_heavy_metals_gap(self):
        obs = Observation(
            profile_id="rod",
            marker="Mercury whole blood",
            value=1.0,
            unit="ug/L",
            category="Heavy metals",
        )
        gaps = DiagnosticGapEngine().create_gaps("rod", [obs])
        self.assertTrue(any("Heavy-metals" in gap.title for gap in gaps))

    def test_repeated_gap_generation_does_not_duplicate_store_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalHealthStore(tmp)
            store.init()
            obs = Observation(
                profile_id="rod",
                marker="Mercury whole blood",
                value=1.0,
                unit="ug/L",
                category="Heavy metals",
                observation_id="obs_repeat_mercury",
            )
            gaps = DiagnosticGapEngine().create_gaps("rod", [obs])
            for gap in gaps:
                store.append_diagnostic_gap(gap)
                store.append_diagnostic_gap(gap)
            self.assertEqual(len(store.diagnostic_gaps("rod")), 1)

    def test_least_harm_cards(self):
        engine = LeastHarmEngine()
        option = engine.watchful_waiting_option("mild ear symptoms")
        self.assertIn("LOW_INTERVENTION", option.tags)
        med = engine.medication_collateral_review("rod", "antibiotic", "unknown")
        self.assertTrue(any("microbiome" in item for item in med.collateral_damage))
        protocol = engine.preventive_protocol_review("rod", "flu shot")
        self.assertIn("decline", protocol.conclusion_options)


if __name__ == "__main__":
    unittest.main()
