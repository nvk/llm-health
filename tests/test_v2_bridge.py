import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from llm_health.assessment_v2.bridge import import_latest_for_profile
from llm_health.engine import DiagnosticGapEngine


class V2BridgeTests(unittest.TestCase):
    def test_import_latest_fixture_without_source_aliases(self):
        root = Path(__file__).parent / "fixtures" / "v2-wiki"
        meta, observations = import_latest_for_profile(root, "rod")
        self.assertEqual(meta.imported_count, 2)
        self.assertEqual(meta.latest_date, "2026-06-05")
        self.assertTrue(all(".pdf" not in obs.note for obs in observations if obs.note))
        mercury = next(obs for obs in observations if "Mercury" in obs.marker)
        self.assertEqual(
            mercury.reference_range, "Normal population: <5.0; exposed population: 5.0-20.0"
        )
        self.assertEqual(mercury.comparator, "<")
        self.assertEqual(mercury.specimen, "whole blood")
        gaps = DiagnosticGapEngine().create_gaps("rod", observations)
        self.assertTrue(any("Heavy-metals" in gap.title for gap in gaps))

    def test_cli_sync_v2_fixture(self):
        repo = Path(__file__).resolve().parents[1]
        root = repo / "tests" / "fixtures" / "v2-wiki"
        env = os.environ.copy()
        env["PYTHONPATH"] = str(repo / "src")
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "llm_health",
                    "sync-v2",
                    "--store",
                    tmp,
                    "--wiki-root",
                    str(root),
                    "--profile",
                    "all",
                    "--accept-risk",
                ],
                cwd=repo,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("sync-v2 complete", result.stdout)
            lookup = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "llm_health",
                    "result",
                    "--store",
                    tmp,
                    "--profile",
                    "rod",
                    "--marker",
                    "mercury",
                ],
                cwd=repo,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(lookup.returncode, 0, lookup.stderr)
            self.assertIn("Normal range (source): Normal population: <5.0", lookup.stdout)
            self.assertIn("Result: <1 ug/L", lookup.stdout)
            stored = "\n".join(p.read_text() for p in Path(tmp).glob("*.jsonl"))
            self.assertNotIn(".pdf", stored)
            self.assertNotIn(str(root), stored)


class LocalRodCaraDataSmokeTests(unittest.TestCase):
    def test_optional_local_health_wiki_smoke(self):
        wiki_root = os.environ.get("HEALTH_WIKI_ROOT")
        if not wiki_root:
            self.skipTest(
                "Set HEALTH_WIKI_ROOT to run local Rod/Cara smoke against deidentified wiki"
            )
        root = Path(wiki_root)
        if not (root / "output" / "data" / "lab-observations-long.csv").exists():
            self.skipTest("HEALTH_WIKI_ROOT lacks canonical v2 observations CSV")
        for profile in ["rod", "cara"]:
            meta, observations = import_latest_for_profile(root, profile)
            self.assertGreater(meta.imported_count, 0)
            payload = "\n".join(obs.note or "" for obs in observations)
            self.assertNotIn(str(root), payload)


if __name__ == "__main__":
    unittest.main()
