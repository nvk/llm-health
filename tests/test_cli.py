import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class CliTests(unittest.TestCase):
    def run_cli(self, *args, store=None):
        env = os.environ.copy()
        repo = Path(__file__).resolve().parents[1]
        env["PYTHONPATH"] = str(repo / "src")
        cmd = [sys.executable, "-m", "llm_health", *args]
        if store is not None:
            cmd.extend(["--store", store])
        return subprocess.run(cmd, cwd=repo, env=env, text=True, capture_output=True, check=False)

    def test_doctor(self):
        result = self.run_cli("doctor")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("status: ok", result.stdout)

    def test_agreement_required_and_acceptance(self):
        with tempfile.TemporaryDirectory() as tmp:
            blocked = self.run_cli("init", store=tmp)
            self.assertEqual(blocked.returncode, 3)
            self.assertIn("agreement required", blocked.stderr)

            show = self.run_cli("agreement", "show", store=tmp)
            self.assertEqual(show.returncode, 0, show.stderr)
            self.assertIn("own-risk agreement", show.stdout)
            self.assertIn("No medical advice", show.stdout)

            accept = self.run_cli("agreement", "accept", "--own-risk", store=tmp)
            self.assertEqual(accept.returncode, 0, accept.stderr)
            self.assertIn("Accepted llm-health own-risk agreement", accept.stdout)

            init = self.run_cli("init", store=tmp)
            self.assertEqual(init.returncode, 0, init.stderr)
            self.assertTrue((Path(tmp) / "agreement.json").exists())

    def test_plugin_paths_cover_agent_runtimes(self):
        result = self.run_cli("plugin-paths")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("codex:", result.stdout)
        self.assertIn("claude:", result.stdout)
        self.assertIn("opencode:", result.stdout)
        self.assertIn("agents:", result.stdout)

        opencode = self.run_cli("plugin-paths", "--kind", "opencode")
        self.assertEqual(opencode.returncode, 0, opencode.stderr)
        self.assertIn("llm-health", opencode.stdout)

    def test_first_run_welcome_and_data_prompts(self):
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("llm-health own-risk agreement", result.stdout)
        self.assertIn("Use at your own risk", result.stdout)
        self.assertIn("Welcome to llm-health", result.stdout)
        self.assertIn("No dumps yet", result.stdout)
        self.assertIn("Prose memory dump", result.stdout)
        self.assertIn("Family history and hereditary references", result.stdout)
        self.assertIn("Smoking, alcohol, drugs, and habits", result.stdout)
        self.assertIn("Adaptive digging rules", result.stdout)

        with tempfile.TemporaryDirectory() as tmp:
            wishlist = self.run_cli("data-wishlist", store=tmp)
            self.assertEqual(wishlist.returncode, 0, wishlist.stderr)
            self.assertIn("Apple", wishlist.stdout)
            self.assertIn("Doctor / clinic / lab records", wishlist.stdout)

    def test_dr_visit_cadence_questions(self):
        with tempfile.TemporaryDirectory() as tmp:
            enroll = self.run_cli(
                "enroll", "--alias", "sol", "--birth-year", "2018", "--accept-risk", store=tmp
            )
            self.assertEqual(enroll.returncode, 0, enroll.stderr)
            onboarding = self.run_cli(
                "dr-visit", "--profile", "sol", "--cadence", "onboarding", store=tmp
            )
            self.assertEqual(onboarding.returncode, 0, onboarding.stderr)
            self.assertIn("Minimum viable questionnaire", onboarding.stdout)
            self.assertIn("Write paragraphs", onboarding.stdout)
            self.assertIn("Enroll close family", onboarding.stdout)
            self.assertIn("Nicotine/tobacco", onboarding.stdout)
            self.assertIn("Negative clues are data", onboarding.stdout)

            monthly = self.run_cli(
                "dr-visit",
                "--profile",
                "sol",
                "--cadence",
                "monthly",
                "--sources",
                store=tmp,
            )
            self.assertEqual(monthly.returncode, 0, monthly.stderr)
            self.assertIn("Monthly Dr Visit", monthly.stdout)
            self.assertIn("Source/rationale notes", monthly.stdout)
            self.assertIn("Source links", monthly.stdout)

    def test_test_battery_foundation_and_gap_awareness(self):
        with tempfile.TemporaryDirectory() as tmp:
            enroll = self.run_cli(
                "enroll",
                "--alias",
                "alex",
                "--birth-year",
                "1983",
                "--role",
                "adult",
                "--accept-risk",
                store=tmp,
            )
            self.assertEqual(enroll.returncode, 0, enroll.stderr)
            battery = self.run_cli(
                "test-battery", "--profile", "alex", "--scope", "core", "--sources", store=tmp
            )
            self.assertEqual(battery.returncode, 0, battery.stderr)
            self.assertIn("Test battery candidates", battery.stdout)
            self.assertIn("home blood pressure", battery.stdout)
            self.assertIn("TEST_CANDIDATE", battery.stdout)
            self.assertIn("Source links", battery.stdout)

            ingest = self.run_cli(
                "ingest-note",
                "--profile",
                "alex",
                "--marker",
                "ALT",
                "--value",
                "80",
                "--unit",
                "U/L",
                "--category",
                "liver",
                "--flag",
                "high",
                store=tmp,
            )
            self.assertEqual(ingest.returncode, 0, ingest.stderr)
            gap_battery = self.run_cli(
                "test-battery", "--profile", "alex", "--category", "gaps", store=tmp
            )
            self.assertEqual(gap_battery.returncode, 0, gap_battery.stderr)
            self.assertIn("gap-driven candidates", gap_battery.stdout)
            self.assertIn("repeat hepatic panel", gap_battery.stdout)

    def test_test_battery_child_and_queue_research(self):
        with tempfile.TemporaryDirectory() as tmp:
            enroll = self.run_cli(
                "enroll",
                "--alias",
                "sol",
                "--birth-year",
                "2018",
                "--role",
                "child",
                "--accept-risk",
                store=tmp,
            )
            self.assertEqual(enroll.returncode, 0, enroll.stderr)
            battery = self.run_cli(
                "test-battery",
                "--profile",
                "sol",
                "--scope",
                "expanded",
                "--queue-research",
                store=tmp,
            )
            self.assertEqual(battery.returncode, 0, battery.stderr)
            self.assertIn("pediatric foundation", battery.stdout)
            self.assertIn("Queued research jobs", battery.stdout)
            research = self.run_cli("plan-research", "--profile", "sol", store=tmp)
            self.assertEqual(research.returncode, 0, research.stderr)
            self.assertIn("test battery", research.stdout)

    def test_specialists_and_internal_medicine_consult(self):
        with tempfile.TemporaryDirectory() as tmp:
            listing = self.run_cli("specialists", "--short")
            self.assertEqual(listing.returncode, 0, listing.stderr)
            self.assertIn("internal_medicine", listing.stdout)
            self.assertIn("Internal Medicine", listing.stdout)
            self.assertIn("toxins_exposures", listing.stdout)

            enroll = self.run_cli(
                "enroll",
                "--alias",
                "alex",
                "--birth-year",
                "1983",
                "--role",
                "adult",
                "--accept-risk",
                store=tmp,
            )
            self.assertEqual(enroll.returncode, 0, enroll.stderr)
            consult = self.run_cli(
                "consult",
                "--profile",
                "alex",
                "--specialist",
                "internal_medicine",
                "--topic",
                "baseline synthesis",
                store=tmp,
            )
            self.assertEqual(consult.returncode, 0, consult.stderr)
            self.assertIn("Whole-Person / Internal Medicine Synthesis consult", consult.stdout)
            self.assertIn("SPECIALIST_NOTE", consult.stdout)
            self.assertIn("stored_specialist_notes: 1", consult.stdout)

            notes = self.run_cli("specialist-notes", "--profile", "alex", store=tmp)
            self.assertEqual(notes.returncode, 0, notes.stderr)
            self.assertIn("Whole-Person / Internal Medicine Synthesis consult", notes.stdout)

    def test_auto_consult_routes_gap_specialists(self):
        with tempfile.TemporaryDirectory() as tmp:
            enroll = self.run_cli(
                "enroll",
                "--alias",
                "alex",
                "--birth-year",
                "1983",
                "--role",
                "adult",
                "--accept-risk",
                store=tmp,
            )
            self.assertEqual(enroll.returncode, 0, enroll.stderr)
            ingest = self.run_cli(
                "ingest-note",
                "--profile",
                "alex",
                "--marker",
                "Mercury whole blood",
                "--value",
                "4",
                "--unit",
                "ug/L",
                "--category",
                "heavy metals",
                "--flag",
                "normal",
                store=tmp,
            )
            self.assertEqual(ingest.returncode, 0, ingest.stderr)
            consult = self.run_cli(
                "consult", "--profile", "alex", "--specialist", "auto", store=tmp
            )
            self.assertEqual(consult.returncode, 0, consult.stderr)
            self.assertIn("Whole-Person / Internal Medicine Synthesis consult", consult.stdout)
            self.assertIn("Toxins / Exposures consult", consult.stdout)
            self.assertIn("Test Gap Steward consult", consult.stdout)

            alias_consult = self.run_cli(
                "consult",
                "--profile",
                "alex",
                "--specialist",
                "toxicology_heavy_metals",
                "--no-persist",
                store=tmp,
            )
            self.assertEqual(alias_consult.returncode, 0, alias_consult.stderr)
            self.assertIn("Toxins / Exposures consult", alias_consult.stdout)
            self.assertIn("category_agent: toxins_exposures", alias_consult.stdout)

    def test_ingest_review_gap_flow(self):
        with tempfile.TemporaryDirectory() as tmp:
            init = self.run_cli("init", "--accept-risk", store=tmp)
            self.assertEqual(init.returncode, 0, init.stderr)
            ingest = self.run_cli(
                "ingest-note",
                "--profile",
                "rod",
                "--marker",
                "ALT",
                "--value",
                "76",
                "--unit",
                "U/L",
                "--category",
                "liver",
                "--flag",
                "high",
                store=tmp,
            )
            self.assertEqual(ingest.returncode, 0, ingest.stderr)
            self.assertIn("Quick cards", ingest.stdout)
            review = self.run_cli("review", "--profile", "rod", store=tmp)
            self.assertEqual(review.returncode, 0, review.stderr)
            self.assertIn("New results ingested", review.stdout)
            gaps = self.run_cli("close-gaps", "--profile", "rod", store=tmp)
            self.assertEqual(gaps.returncode, 0, gaps.stderr)
            self.assertIn("Liver-pattern", gaps.stdout)

    def test_cli_privacy_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_cli(
                "ingest-note",
                "--profile",
                "rod",
                "--marker",
                "ALT",
                "--note",
                "raw.pdf",
                "--accept-risk",
                store=tmp,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("privacy error", result.stderr)

    def test_self_report_context_flow(self):
        with tempfile.TemporaryDirectory() as tmp:
            enroll = self.run_cli(
                "enroll", "--alias", "sol", "--birth-year", "2018", "--accept-risk", store=tmp
            )
            self.assertEqual(enroll.returncode, 0, enroll.stderr)
            result = self.run_cli(
                "self-report",
                "--profile",
                "sol",
                "--subject",
                "GI",
                "--status",
                "self-reported fine",
                "--note",
                "Self-reported current status is fine.",
                "--date",
                "2026-06-07",
                store=tmp,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Recorded self-report context", result.stdout)
            context = self.run_cli("context", "--profile", "sol", "--subject", "GI", store=tmp)
            self.assertEqual(context.returncode, 0, context.stderr)
            self.assertIn("CONTEXT", context.stdout)
            self.assertIn("self-reported fine", context.stdout)

    def test_enroll_profiles_flow(self):
        with tempfile.TemporaryDirectory() as tmp:
            sol = self.run_cli(
                "enroll",
                "--alias",
                "sol",
                "--birth-year",
                "2018",
                "--role",
                "child",
                "--accept-risk",
                store=tmp,
            )
            self.assertEqual(sol.returncode, 0, sol.stderr)
            lele = self.run_cli(
                "enroll",
                "--alias",
                "lele",
                "--birth-year",
                "2026",
                "--birth-month",
                "1",
                "--role",
                "child",
                "--accept-risk",
                store=tmp,
            )
            self.assertEqual(lele.returncode, 0, lele.stderr)
            profiles = self.run_cli("profiles", store=tmp)
            self.assertEqual(profiles.returncode, 0, profiles.stderr)
            self.assertIn("sol · birth 2018", profiles.stdout)
            self.assertIn("lele · birth 2026-01", profiles.stdout)


if __name__ == "__main__":
    unittest.main()
