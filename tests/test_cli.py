import json
import os
import re
import subprocess
import sys
import tarfile
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

    def test_capabilities_registry(self):
        result = self.run_cli("capabilities")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("llm-health capabilities", result.stdout)
        self.assertIn("deid", result.stdout)
        self.assertIn("local-service", result.stdout)
        self.assertIn("health ui", result.stdout)
        self.assertIn("health report", result.stdout)
        self.assertIn("external", result.stdout)

        machine = self.run_cli("capabilities", "--json")
        self.assertEqual(machine.returncode, 0, machine.stderr)
        payload = json.loads(machine.stdout)
        ids = {row["capability_id"] for row in payload}
        self.assertIn("capabilities", ids)
        self.assertIn("deid", ids)
        self.assertIn("local-service", ids)
        self.assertIn("reports", ids)

    def test_deid_preview_extract_and_apply(self):
        synthetic = (
            "Patient: Jane Doe\n"
            "Email: jane@example.com\n"
            "Date: 2026-01-05\n"
            "Path: /Users/example/private/lab-result.pdf\n"
            "File: report.csv\n"
            "Mercury whole blood: <1.0 ug/L\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "input.txt"
            source.write_text(synthetic)

            preview = self.run_cli(
                "deid", "preview", str(source), "--accept-risk", store=tmp
            )
            self.assertEqual(preview.returncode, 0, preview.stderr)
            self.assertIn("Mercury whole blood", preview.stdout)
            self.assertIn("Email: [EMAIL_", preview.stdout)
            self.assertIn("[PERSON_", preview.stdout)
            self.assertIn("[EMAIL_", preview.stdout)
            self.assertIn("[PATH_", preview.stdout)
            self.assertNotIn("Jane", preview.stdout)
            self.assertNotIn("example.com", preview.stdout)
            self.assertNotIn("/Users", preview.stdout)
            self.assertNotIn(".pdf", preview.stdout)
            self.assertNotIn(".csv", preview.stdout)

            extract = self.run_cli(
                "deid", "extract", str(source), "--accept-risk", "--json", store=tmp
            )
            self.assertEqual(extract.returncode, 0, extract.stderr)
            payload = json.loads(extract.stdout)
            kinds = {entity["kind"] for entity in payload["entities"]}
            self.assertIn("PERSON", kinds)
            self.assertIn("EMAIL", kinds)
            self.assertIn("PATH", kinds)
            self.assertNotIn("Jane", extract.stdout)
            self.assertNotIn("example.com", extract.stdout)

            staged = self.run_cli(
                "deid",
                "apply",
                str(source),
                "--staging-only",
                "--accept-risk",
                store=tmp,
            )
            self.assertEqual(staged.returncode, 0, staged.stderr)
            self.assertIn("staged: deid-staging/deid_", staged.stdout)
            staged_files = list((Path(tmp) / "deid-staging").glob("deid_*.txt"))
            self.assertEqual(len(staged_files), 1)
            staged_text = staged_files[0].read_text()
            self.assertIn("Mercury whole blood", staged_text)
            self.assertNotIn("Jane", staged_text)
            self.assertNotIn("example.com", staged_text)
            self.assertNotIn("/Users", staged_text)

    def test_service_smoke_routes(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_cli("service", "--local", "--smoke", "--accept-risk", store=tmp)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("llm-health local service", result.stdout)
            self.assertIn("local_only: true", result.stdout)
            self.assertIn("/health", result.stdout)
            self.assertIn("/profiles", result.stdout)
            self.assertIn("/operator/drafts", result.stdout)
            self.assertIn("/family/tree", result.stdout)
            self.assertIn("status: smoke-ok", result.stdout)

    def test_family_history_tree_and_risk_notes(self):
        with tempfile.TemporaryDirectory() as tmp:
            for alias, year, role in [
                ("alex", "2018", "child"),
                ("parenta", "1983", "adult"),
                ("parentb", "1983", "adult"),
            ]:
                enroll = self.run_cli(
                    "enroll",
                    "--alias",
                    alias,
                    "--birth-year",
                    year,
                    "--role",
                    role,
                    "--accept-risk",
                    store=tmp,
                )
                self.assertEqual(enroll.returncode, 0, enroll.stderr)

            father = self.run_cli(
                "family",
                "add",
                "--profile",
                "alex",
                "--relative",
                "parenta",
                "--relation",
                "father",
                "--lineage",
                "paternal",
                "--shared-household",
                "yes",
                store=tmp,
            )
            self.assertEqual(father.returncode, 0, father.stderr)
            self.assertIn("Added relationship", father.stdout)
            self.assertIn("FAMILY_HISTORY", father.stdout)

            mother = self.run_cli(
                "family",
                "add",
                "--profile",
                "alex",
                "--relative",
                "parentb",
                "--relation",
                "mother",
                "--lineage",
                "maternal",
                "--shared-household",
                "yes",
                store=tmp,
            )
            self.assertEqual(mother.returncode, 0, mother.stderr)

            condition = self.run_cli(
                "family",
                "condition",
                "--profile",
                "parenta",
                "--condition",
                "Gilbert syndrome",
                "--status",
                "believed",
                "--evidence",
                "context",
                store=tmp,
            )
            self.assertEqual(condition.returncode, 0, condition.stderr)
            self.assertIn("Gilbert syndrome", condition.stdout)

            tree = self.run_cli("family", "tree", "--profile", "alex", store=tmp)
            self.assertEqual(tree.returncode, 0, tree.stderr)
            self.assertIn("parenta: father", tree.stdout)
            self.assertIn("parentb: mother", tree.stdout)
            self.assertIn("shared household", tree.stdout)

            history = self.run_cli("family", "history", "--profile", "parenta", store=tmp)
            self.assertEqual(history.returncode, 0, history.stderr)
            self.assertIn("Gilbert syndrome", history.stdout)

            risks = self.run_cli("family", "risks", "--profile", "alex", store=tmp)
            self.assertEqual(risks.returncode, 0, risks.stderr)
            self.assertIn("Family risk review", risks.stdout)
            self.assertIn("Family history: Gilbert syndrome", risks.stdout)
            self.assertIn("HEREDITARY_RISK", risks.stdout)
            self.assertIn("FAMILY_PATTERN", risks.stdout)
            self.assertIn("HOUSEHOLD_CONTEXT", risks.stdout)
            self.assertIn("stored_hereditary_risk_notes", risks.stdout)

            unsafe = self.run_cli(
                "family",
                "condition",
                "--profile",
                "parenta",
                "--condition",
                "from raw.pdf",
                store=tmp,
            )
            self.assertEqual(unsafe.returncode, 2)
            self.assertIn("privacy error", unsafe.stderr)

    def test_operator_runtime_draft_finalize_trace(self):
        with tempfile.TemporaryDirectory() as tmp:
            enroll = self.run_cli(
                "enroll",
                "--alias",
                "alex",
                "--birth-year",
                "1983",
                "--accept-risk",
                store=tmp,
            )
            self.assertEqual(enroll.returncode, 0, enroll.stderr)
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
            draft = self.run_cli(
                "operator",
                "draft",
                "--profile",
                "alex",
                "--intent",
                "review latest liver trend",
                store=tmp,
            )
            self.assertEqual(draft.returncode, 0, draft.stderr)
            self.assertIn("# Draft health review", draft.stdout)
            self.assertIn("Visible plan", draft.stdout)
            self.assertIn("approval_required: true", draft.stdout)
            self.assertIn("Finalize command:", draft.stdout)
            match = re.search(r"draft_id: (draft_[a-f0-9]+)", draft.stdout)
            self.assertIsNotNone(match, draft.stdout)
            draft_id = match.group(1)

            listing = self.run_cli("operator", "list", "--profile", "alex", store=tmp)
            self.assertEqual(listing.returncode, 0, listing.stderr)
            self.assertIn(draft_id, listing.stdout)
            self.assertIn("draft", listing.stdout)

            finalized = self.run_cli(
                "operator", "finalize", "--draft-id", draft_id, "--approve", store=tmp
            )
            self.assertEqual(finalized.returncode, 0, finalized.stderr)
            self.assertIn("finalized:", finalized.stdout)
            self.assertIn("status: finalized", finalized.stdout)

            shown = self.run_cli("operator", "show", "--draft-id", draft_id, store=tmp)
            self.assertEqual(shown.returncode, 0, shown.stderr)
            self.assertIn("status: finalized", shown.stdout)

            traces = self.run_cli("operator", "traces", "--profile", "alex", store=tmp)
            self.assertEqual(traces.returncode, 0, traces.stderr)
            self.assertIn("draft_finalized", traces.stdout)
            self.assertIn("fingerprints:", traces.stdout)

            unsafe = self.run_cli(
                "operator",
                "draft",
                "--profile",
                "alex",
                "--intent",
                "review /Users/example/raw.pdf",
                store=tmp,
            )
            self.assertEqual(unsafe.returncode, 2)
            self.assertIn("privacy error", unsafe.stderr)

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
        self.assertIn("See the UI early", result.stdout)
        self.assertIn("health ui", result.stdout)

        with tempfile.TemporaryDirectory() as tmp:
            wishlist = self.run_cli("data-wishlist", store=tmp)
            self.assertEqual(wishlist.returncode, 0, wishlist.stderr)
            self.assertIn("Apple", wishlist.stdout)
            self.assertIn("Doctor / clinic / lab records", wishlist.stdout)


    def test_ui_exports_static_dashboard_with_configured_wiki_root(self):
        repo = Path(__file__).resolve().parents[1]
        wiki_root = repo / "tests" / "fixtures" / "v2-wiki"
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.json"
            hub = Path(tmp) / "hub"
            output = Path(tmp) / "ui"
            env = os.environ.copy()
            env["PYTHONPATH"] = str(repo / "src")
            set_hub = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "llm_health",
                    "config",
                    "hub-path",
                    str(hub),
                    "--config-path",
                    str(config_path),
                    "--init",
                    "--accept-risk",
                ],
                cwd=repo,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(set_hub.returncode, 0, set_hub.stderr)
            set_wiki = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "llm_health",
                    "config",
                    "wiki-root",
                    str(wiki_root),
                    "--config-path",
                    str(config_path),
                ],
                cwd=repo,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(set_wiki.returncode, 0, set_wiki.stderr)
            ui = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "llm_health",
                    "ui",
                    "--store",
                    str(hub),
                    "--output",
                    str(output),
                    "--no-open",
                ],
                cwd=repo,
                env={**env, "LLM_HEALTH_CONFIG": str(config_path)},
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(ui.returncode, 0, ui.stderr)
            self.assertIn("exported UI", ui.stdout)
            self.assertTrue((output / "index.html").exists())
            self.assertTrue((output / "data.js").exists())
            self.assertTrue((output / "assets").is_dir())
            self.assertIn("Assessment board", (output / "index.html").read_text())

    def test_source_vault_and_audit_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            hub = root / "hub"
            wiki = root / "wiki"
            raw_dir = root / "raw"
            raw_dir.mkdir()
            raw = raw_dir / "source-a.pdf"
            raw.write_bytes(b"fake pdf ALT 61")
            data_dir = wiki / "output" / "data"
            data_dir.mkdir(parents=True)
            (data_dir / "lab-reports.csv").write_text(
                "source_id,profile_id,family_role,provider_alias,source_title,collection_date,"
                "report_date,language,status,source_file_alias,notes\n"
                "src1,rod,father,provider,title,2026-01-01,2026-01-01,en,ingested,"
                "rod/source-a.pdf,note\n",
                encoding="utf-8",
            )
            (data_dir / "lab-observations-long.csv").write_text(
                "observation_id,profile_id,family_role,observation_date,collection_date,"
                "report_date,source_id,source_title,source_file_alias,provider_alias,"
                "language_original,panel_original,panel_en,analyte_original,analyte_en,"
                "loinc_code,loinc_mapping_status,result_type,value_raw,numeric_value,"
                "comparator,unit_raw,ucum_unit,reference_range_raw,flag_raw,"
                "interpretation_en,specimen,method,confidence,notes\n"
                "obs1,rod,father,2026-01-01,2026-01-01,2026-01-01,src1,title,,,"
                "en,Liver,Liver,ALT,ALT,,unmapped,Numeric,61,61,,U/L,U/L,"
                "0-55,high,,,,medium,OCR ambiguous\n",
                encoding="utf-8",
            )

            init = self.run_cli("init", "--accept-risk", store=str(hub))
            self.assertEqual(init.returncode, 0, init.stderr)
            blocked = self.run_cli("source-vault", "add", str(raw_dir), "--copy", store=str(hub))
            self.assertEqual(blocked.returncode, 4)
            added = self.run_cli(
                "source-vault",
                "add",
                str(raw_dir),
                "--wiki-root",
                str(wiki),
                "--copy",
                "--accept-raw-storage",
                store=str(hub),
            )
            self.assertEqual(added.returncode, 0, added.stderr)
            self.assertIn("matched_to_ingested_sources: 1", added.stdout)
            manifest = (hub / "source-vault" / "manifest.jsonl").read_text()
            self.assertNotIn("source-a.pdf", manifest)

            audit = self.run_cli(
                "source-audit",
                "run",
                "--wiki-root",
                str(wiki),
                "--profile",
                "rod",
                store=str(hub),
            )
            self.assertEqual(audit.returncode, 0, audit.stderr)
            self.assertIn("medium rows: 1", audit.stdout)
            self.assertIn("Rows needing audit", audit.stdout)

    def test_archive_create_list_verify_and_privacy_skip(self):
        with tempfile.TemporaryDirectory() as tmp:
            init = self.run_cli("init", "--accept-risk", store=tmp)
            self.assertEqual(init.returncode, 0, init.stderr)
            root = Path(tmp)
            (root / "v2-web").mkdir()
            (root / "v2-web" / "index.html").write_text("<html>safe local dashboard</html>")
            (root / "v2-data").mkdir()
            (root / "v2-data" / "health.duckdb").write_bytes(b"binary old raw-source.pdf marker")

            created = self.run_cli("archive", "create", "--json", store=tmp)
            self.assertEqual(created.returncode, 0, created.stderr)
            payload = json.loads(created.stdout)
            archive_path = Path(payload["archive_path"])
            self.assertTrue(archive_path.exists())
            self.assertGreater(payload["member_count"], 0)
            self.assertEqual(payload["skipped_count"], 1)
            self.assertIn("v2-data/health.duckdb", payload["skipped"][0]["path"])

            with tarfile.open(archive_path, "r:gz") as tar:
                names = set(tar.getnames())
            self.assertIn("archive-manifest.json", names)
            self.assertIn("v2-web/index.html", names)
            self.assertNotIn("v2-data/health.duckdb", names)

            listed = self.run_cli("archive", "list", store=tmp)
            self.assertEqual(listed.returncode, 0, listed.stderr)
            self.assertIn(archive_path.name, listed.stdout)

            verified = self.run_cli("archive", "verify", str(archive_path), store=tmp)
            self.assertEqual(verified.returncode, 0, verified.stderr)
            self.assertIn("status: ok", verified.stdout)

            strict = self.run_cli("archive", "create", "--strict", store=tmp)
            self.assertEqual(strict.returncode, 2)
            self.assertIn("privacy error", strict.stderr)

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

    def test_profile_and_family_writes_refresh_existing_static_ui_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_path = Path(tmp) / "v2-web" / "data.js"
            data_path.parent.mkdir()
            data_path.write_text(
                "window.HEALTH_ASSESSMENT_V2 = "
                + json.dumps(
                    {
                        "generated": "2026-07-01",
                        "observations": [],
                        "normalization_issues": [],
                        "reports": [],
                        "wearable_daily": [],
                        "profile_context": {},
                        "genomics": {},
                        "profiles": [{"profile_id": "rod"}, {"profile_id": "cara"}],
                        "export_summary": {"profiles": ["rod", "cara"]},
                    },
                    separators=(",", ":"),
                )
                + ";\n",
                encoding="utf-8",
            )

            michael = self.run_cli(
                "enroll",
                "--alias",
                "michael",
                "--birth-year",
                "1949",
                "--accept-risk",
                store=tmp,
            )
            self.assertEqual(michael.returncode, 0, michael.stderr)
            self.assertIn("ui_refresh: incremental_hub_refresh", michael.stdout)
            payload = json.loads(
                data_path.read_text(encoding="utf-8").removeprefix(
                    "window.HEALTH_ASSESSMENT_V2 = "
                ).rstrip(";\n")
            )
            self.assertIn("michael", payload["export_summary"]["profiles"])
            michael_profile = next(
                profile for profile in payload["profiles"] if profile["profile_id"] == "michael"
            )
            self.assertEqual(michael_profile["birth_year"], 1949)

            relationship = self.run_cli(
                "family",
                "add",
                "--profile",
                "cara",
                "--relative",
                "michael",
                "--relation",
                "father",
                store=tmp,
            )
            self.assertEqual(relationship.returncode, 0, relationship.stderr)
            self.assertIn("ui_refresh: incremental_hub_refresh", relationship.stdout)
            payload = json.loads(
                data_path.read_text(encoding="utf-8").removeprefix(
                    "window.HEALTH_ASSESSMENT_V2 = "
                ).rstrip(";\n")
            )
            self.assertEqual(
                payload["profile_context"]["cara"]["familyRelationships"][0]["relative_id"],
                "michael",
            )
            self.assertEqual(
                payload["profile_context"]["michael"]["familyRelationships"][0]["relation"],
                "father",
            )

    def test_report_exports_doctor_and_family_pdfs(self):
        with tempfile.TemporaryDirectory() as tmp:
            ingest = self.run_cli(
                "ingest-note",
                "--profile",
                "rod",
                "--marker",
                "Mercury whole blood",
                "--value",
                "57.9",
                "--unit",
                "ug/L",
                "--category",
                "Heavy metals",
                "--flag",
                "High",
                "--reference-range",
                "<=19.7",
                "--accept-risk",
                store=tmp,
            )
            self.assertEqual(ingest.returncode, 0, ingest.stderr)
            output_dir = Path(tmp) / "exports"
            report = self.run_cli(
                "report",
                "--profile",
                "rod",
                "--audience",
                "both",
                "--output-dir",
                str(output_dir),
                store=tmp,
            )
            self.assertEqual(report.returncode, 0, report.stderr)
            self.assertIn("doctor:", report.stdout)
            self.assertIn("family:", report.stdout)
            pdfs = sorted(output_dir.glob("*.pdf"))
            self.assertEqual(len(pdfs), 2)
            for pdf in pdfs:
                data = pdf.read_bytes()
                self.assertTrue(data.startswith(b"%PDF-1.4"))
                self.assertNotIn(b"/Users", data)
                self.assertNotIn(b"Mobile Documents", data)
                self.assertNotIn(b"source_file_alias", data)


if __name__ == "__main__":
    unittest.main()
