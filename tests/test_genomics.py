import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

from llm_health.core.models import EnrolledProfile
from llm_health.core.privacy import PrivacyError
from llm_health.genomics import (
    GenomicsStore,
    build_qc,
    import_raw_genotype_text_into_store,
    parse_raw_genotype_file,
    parse_raw_genotype_text,
)
from llm_health.genomics.gui import GenomicsGuiServer, render_genomics_import_ui
from llm_health.genomics.knowledge import (
    MARKERS,
    MATCHABLE_MARKERS,
    marker_count_by_runtime,
    markers_for_matching,
)
from llm_health.genomics.pipeline import genomics_review_payload
from llm_health.genomics.workflow import matched_allowlist_variants
from llm_health.service import route_manifest
from llm_health.stores import LocalHealthStore


class GenomicsTests(unittest.TestCase):
    def run_cli(self, *args, store=None):
        env = os.environ.copy()
        repo = Path(__file__).resolve().parents[1]
        env["PYTHONPATH"] = str(repo / "src")
        cmd = [sys.executable, "-m", "llm_health", *args]
        if store is not None:
            cmd.extend(["--store", store])
        return subprocess.run(cmd, cwd=repo, env=env, text=True, capture_output=True, check=False)

    def write_genotype(self, folder: str) -> Path:
        path = Path(folder) / "synthetic-genotype.txt"
        path.write_text(
            "# synthetic 23andMe-like raw data\n"
            "# reference build GRCh37\n"
            "rsid\tchromosome\tposition\tgenotype\n"
            "rs1800562\t6\t26092913\tAG\n"
            "rs6742078\t2\t234668879\tTT\n"
            "rs4149056\t12\t21178615\tCT\n"
            "rs4244285\t10\t96541616\tAG\n"
            "rs999999\t1\t100\t--\n",
            encoding="utf-8",
        )
        return path

    def test_clinical_marker_catalog_is_loaded_and_filters_default_matching(self):
        self.assertGreaterEqual(len(MARKERS), 916)
        self.assertGreaterEqual(len(MATCHABLE_MARKERS), 400)
        runtime_counts = marker_count_by_runtime()
        self.assertGreaterEqual(runtime_counts["candidate_default_after_qc"], 400)
        self.assertEqual(runtime_counts["research_opt_in"], 111)
        self.assertEqual(MARKERS["rs1057910"].gene, "CYP2C9")
        self.assertEqual(MARKERS["rs1057910"].effect_allele, "C")
        self.assertEqual(MARKERS["rs3918290"].gene, "DPYD")
        self.assertIn("CPIC", MARKERS["rs3918290"].clinical_reference)
        self.assertIn("http", MARKERS["rs3918290"].source_url)
        self.assertEqual(MARKERS["rs429358"].gene, "APOE")
        self.assertNotIn("rs429358", MATCHABLE_MARKERS)
        self.assertNotIn("rs7412", MATCHABLE_MARKERS)
        self.assertNotIn("rs6025", MATCHABLE_MARKERS)
        self.assertEqual(MARKERS["rs13082684"].runtime_default, "research_opt_in")
        self.assertEqual(MARKERS["rs13082684"].topic, "dyslexia")
        self.assertNotIn("rs13082684", MATCHABLE_MARKERS)
        self.assertIn("rs13082684", markers_for_matching(include_research=True))
        self.assertEqual(MARKERS["rs549845"].runtime_default, "research_opt_in")
        self.assertEqual(MARKERS["rs549845"].topic, "adhd")
        self.assertEqual(MARKERS["rs10099100"].topic, "autism_spectrum")
        self.assertEqual(MARKERS["rs201910565"].match_alleles, ("AT",))
        self.assertNotIn("rs549845", MATCHABLE_MARKERS)
        self.assertIn("rs549845", markers_for_matching(include_research=True))
        self.assertIn("rs10099100", markers_for_matching(include_research=True))

    def test_expanded_default_matching_excludes_sensitive_and_deferred_markers(self):
        parsed = parse_raw_genotype_text(
            "# synthetic expanded marker fixture\n"
            "rsid\tchromosome\tposition\tgenotype\n"
            "rs1057910\t10\t94981296\tCC\n"
            "rs3918290\t1\t97098502\tCT\n"
            "rs4149056\t12\t21178615\tCT\n"
            "rs429358\t19\t44908684\tCT\n"
            "rs7412\t19\t44908822\tCT\n"
            "rs6025\t1\t169549811\tAG\n",
            profile_id="alex",
        )
        matched = matched_allowlist_variants(parsed.variants)
        rsids = {variant.rsid for variant in matched}
        self.assertIn("rs1057910", rsids)
        self.assertIn("rs3918290", rsids)
        self.assertIn("rs4149056", rsids)
        self.assertNotIn("rs429358", rsids)
        self.assertNotIn("rs7412", rsids)
        self.assertNotIn("rs6025", rsids)

    def test_dyslexia_gwas_markers_are_research_opt_in_and_aggregated(self):
        parsed = parse_raw_genotype_text(
            "# synthetic dyslexia research marker fixture\n"
            "rsid\tchromosome\tposition\tgenotype\n"
            "rs13082684\t3\t136000000\tGG\n"
            "rs2426117\t20\t49000000\tAG\n"
            "rs999999\t1\t100\tAA\n",
            profile_id="alex",
        )
        default_rsids = {variant.rsid for variant in matched_allowlist_variants(parsed.variants)}
        self.assertNotIn("rs13082684", default_rsids)
        research_markers = markers_for_matching(include_research=True)
        research_rsids = {
            variant.rsid
            for variant in matched_allowlist_variants(
                parsed.variants, marker_catalog=research_markers
            )
        }
        self.assertIn("rs13082684", research_rsids)
        self.assertIn("rs2426117", research_rsids)

        with tempfile.TemporaryDirectory() as tmp:
            health_store = LocalHealthStore(tmp)
            health_store.init()
            health_store.enroll_profile(EnrolledProfile(profile_id="alex", birth_year=1983))
            genomics_store = GenomicsStore(tmp)
            summary = import_raw_genotype_text_into_store(
                health_store,
                genomics_store,
                profile_id="alex",
                content=(
                    "# synthetic dyslexia research marker fixture\n"
                    "rsid\tchromosome\tposition\tgenotype\n"
                    "rs13082684\t3\t136000000\tGG\n"
                    "rs2426117\t20\t49000000\tAG\n"
                ),
                accept_genetic_risk=True,
                include_research_markers=True,
            )
            self.assertEqual(summary.stored_variant_count, 2)
            self.assertTrue(summary.match_diagnostics["include_research_markers"])
            self.assertEqual(summary.match_diagnostics["dyslexia_gwas_catalog_markers"], 80)
            self.assertEqual(summary.match_diagnostics["dyslexia_gwas_marker_matches"], 2)
            self.assertEqual(
                summary.match_diagnostics["dyslexia_gwas_effect_marker_matches"], 2
            )
            titles = [card.title for card in summary.inferences]
            self.assertIn("Dyslexia GWAS research marker coverage", titles)
            dyslexia_card = next(
                card for card in summary.inferences if card.title.startswith("Dyslexia")
            )
            self.assertEqual(dyslexia_card.finding_type, "research_trait_context")
            self.assertEqual(dyslexia_card.confidence, "low")
            self.assertIn("not a polygenic score", " ".join(dyslexia_card.evidence))
            payload = summary.to_dict()
            self.assertIn("RESEARCH_CONTEXT", payload["patient_summary"]["tags"])
            self.assertIn("research-context", payload["patient_summary"]["lead"])
            self.assertIn(
                "dyslexia GWAS research context",
                " ".join(payload["patient_summary"]["bullets"]),
            )
            self.assertIn("not a diagnosis", " ".join(payload["patient_summary"]["bullets"]))

    def test_neurodevelopmental_research_markers_are_research_opt_in_and_aggregated(self):
        parsed = parse_raw_genotype_text(
            "# synthetic neurodevelopmental research marker fixture\n"
            "rsid\tchromosome\tposition\tgenotype\n"
            "rs13082684\t3\t136000000\tGG\n"
            "rs549845\t1\t44076469\tGG\n"
            "rs10099100\t8\t10099100\tCC\n",
            profile_id="alex",
        )
        default_rsids = {variant.rsid for variant in matched_allowlist_variants(parsed.variants)}
        self.assertNotIn("rs549845", default_rsids)
        self.assertNotIn("rs10099100", default_rsids)
        research_markers = markers_for_matching(include_research=True)
        research_rsids = {
            variant.rsid
            for variant in matched_allowlist_variants(
                parsed.variants, marker_catalog=research_markers
            )
        }
        self.assertIn("rs549845", research_rsids)
        self.assertIn("rs10099100", research_rsids)

        with tempfile.TemporaryDirectory() as tmp:
            health_store = LocalHealthStore(tmp)
            health_store.init()
            health_store.enroll_profile(EnrolledProfile(profile_id="alex", birth_year=1983))
            genomics_store = GenomicsStore(tmp)
            summary = import_raw_genotype_text_into_store(
                health_store,
                genomics_store,
                profile_id="alex",
                content=(
                    "# synthetic neurodevelopmental research marker fixture\n"
                    "rsid\tchromosome\tposition\tgenotype\n"
                    "rs13082684\t3\t136000000\tGG\n"
                    "rs549845\t1\t44076469\tGG\n"
                    "rs10099100\t8\t10099100\tCC\n"
                ),
                accept_genetic_risk=True,
                include_research_markers=True,
            )
            self.assertEqual(summary.stored_variant_count, 3)
            self.assertEqual(summary.match_diagnostics["research_catalog_markers"], 111)
            self.assertEqual(summary.match_diagnostics["research_marker_matches"], 3)
            self.assertEqual(summary.match_diagnostics["research_effect_marker_matches"], 3)
            self.assertEqual(summary.match_diagnostics["adhd_gwas_catalog_markers"], 27)
            self.assertEqual(summary.match_diagnostics["adhd_gwas_marker_matches"], 1)
            self.assertEqual(summary.match_diagnostics["adhd_gwas_effect_marker_matches"], 1)
            self.assertEqual(summary.match_diagnostics["autism_spectrum_gwas_catalog_markers"], 4)
            self.assertEqual(summary.match_diagnostics["autism_spectrum_gwas_marker_matches"], 1)
            self.assertEqual(
                summary.match_diagnostics["autism_spectrum_gwas_effect_marker_matches"],
                1,
            )
            titles = {card.title for card in summary.inferences}
            self.assertIn("Dyslexia GWAS research marker coverage", titles)
            self.assertIn("ADHD GWAS research marker coverage", titles)
            self.assertIn("Autism spectrum GWAS research marker coverage", titles)
            payload = summary.to_dict()
            bullets = " ".join(payload["patient_summary"]["bullets"])
            self.assertIn("dyslexia GWAS research context", bullets)
            self.assertIn("ADHD GWAS research context", bullets)
            self.assertIn("autism spectrum GWAS research context", bullets)

    def test_parse_raw_genotype_and_qc(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_genotype(tmp)
            result = parse_raw_genotype_file(path, profile_id="alex", source_kind="auto")
            self.assertEqual(result.source.profile_id, "alex")
            self.assertEqual(result.source.source_kind, "23andme")
            self.assertEqual(result.source.genome_build, "GRCh37")
            self.assertEqual(result.source.marker_count, 5)
            self.assertEqual(result.source.called_count, 4)
            self.assertEqual(result.variants[-1].call_status, "no_call")
            qc = build_qc(result.source, result.variants)
            self.assertIn("call_rate_below_95_percent", qc.warnings)
            self.assertIn("consumer_or_unconfirmed_source_review", qc.warnings)

    def test_parse_raw_genotype_text_and_gui_import_workflow_privacy(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_genotype(tmp)
            content = path.read_text(encoding="utf-8")
            parsed = parse_raw_genotype_text(content, profile_id="alex", source_kind="auto")
            self.assertEqual(parsed.source.source_kind, "23andme")
            self.assertEqual(parsed.source.genome_build, "GRCh37")
            self.assertEqual(parsed.source.marker_count, 5)

            health_store = LocalHealthStore(tmp)
            health_store.init()
            health_store.enroll_profile(EnrolledProfile(profile_id="alex", birth_year=1983))
            genomics_store = GenomicsStore(tmp)
            with self.assertRaises(PrivacyError):
                import_raw_genotype_text_into_store(
                    health_store,
                    genomics_store,
                    profile_id="alex",
                    content=content,
                    accept_genetic_risk=False,
                )

            summary = import_raw_genotype_text_into_store(
                health_store,
                genomics_store,
                profile_id="alex",
                content=content,
                accept_genetic_risk=True,
            )
            self.assertEqual(summary.source.marker_count, 5)
            self.assertEqual(summary.qc.no_call_count, 1)
            self.assertEqual(summary.stored_variant_scope, "matched_allowlist_only")
            self.assertEqual(summary.stored_variant_count, 4)
            self.assertEqual(len(genomics_store.variants("alex")), 4)
            payload = summary.to_dict()
            self.assertFalse(payload["match_diagnostics"]["include_research_markers"])
            self.assertEqual(payload["match_diagnostics"]["dyslexia_gwas_marker_matches"], 0)
            self.assertIn("not stored", payload["privacy"])
            self.assertIn("patient_summary", payload)
            self.assertIn("CONFIRM_FIRST", payload["patient_summary"]["tags"])
            self.assertIn("This profile", payload["patient_summary"]["lead"])
            self.assertNotIn("Rod", payload["patient_summary"]["lead"])
            self.assertTrue(
                all("patient_summary" in inference for inference in payload["inferences"])
            )
            review = genomics_review_payload(health_store, "alex")
            self.assertIn("patient_summary", review)
            self.assertIn("warning_details", review["qc"]["qc"][0])
            self.assertIn("patient_summary", review["crossrefs"]["cards"][0])
            stored_sources = (Path(tmp) / "genomics" / "sources.jsonl").read_text()
            self.assertNotIn(str(path), stored_sources)
            self.assertNotIn(path.name, stored_sources)
            stored_variants = "\n".join(
                file.read_text()
                for file in (Path(tmp) / "genomics" / "variants").glob("*.jsonl")
            )
            self.assertIn("rs1800562", stored_variants)
            self.assertNotIn("rs999999", stored_variants)

    def test_genomics_cli_import_crossref_and_privacy(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = self.write_genotype(tmp)
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

            blocked = self.run_cli(
                "genomics",
                "import",
                str(source),
                "--profile",
                "alex",
                store=tmp,
            )
            self.assertEqual(blocked.returncode, 4)
            self.assertIn("genetic risk acknowledgement required", blocked.stderr)

            dense_blocked = self.run_cli(
                "genomics",
                "import",
                str(source),
                "--profile",
                "alex",
                "--accept-genetic-risk",
                "--store-dense-variants",
                store=tmp,
            )
            self.assertEqual(dense_blocked.returncode, 2)
            self.assertIn("dense genetic storage requires", dense_blocked.stderr)

            imported = self.run_cli(
                "genomics",
                "import",
                str(source),
                "--profile",
                "alex",
                "--accept-genetic-risk",
                store=tmp,
            )
            self.assertEqual(imported.returncode, 0, imported.stderr)
            self.assertIn("Matched genomic source", imported.stdout)
            self.assertIn("source_kind: 23andme", imported.stdout)
            self.assertIn("stored_variant_scope: matched_allowlist_only", imported.stdout)
            self.assertIn("stored_variants: 4", imported.stdout)
            self.assertIn("dense genome-wide calls are not stored by default", imported.stdout)
            self.assertIn("review_note: context only", imported.stdout)
            self.assertNotIn(str(source), imported.stdout)
            self.assertNotIn(source.name, imported.stdout)

            stored_sources = (Path(tmp) / "genomics" / "sources.jsonl").read_text()
            self.assertNotIn(str(source), stored_sources)
            self.assertNotIn(source.name, stored_sources)
            store = GenomicsStore(tmp)
            self.assertEqual(len(store.variants("alex")), 4)
            self.assertFalse(any(variant.rsid == "rs999999" for variant in store.variants("alex")))

            ferritin = self.run_cli(
                "ingest-note",
                "--profile",
                "alex",
                "--marker",
                "Ferritin",
                "--value",
                "350",
                "--unit",
                "ug/L",
                "--category",
                "iron",
                "--flag",
                "high",
                store=tmp,
            )
            self.assertEqual(ferritin.returncode, 0, ferritin.stderr)
            med = self.run_cli(
                "self-report",
                "--profile",
                "alex",
                "--subject",
                "Medication",
                "--status",
                "active",
                "--note",
                "Current medication includes simvastatin.",
                store=tmp,
            )
            self.assertEqual(med.returncode, 0, med.stderr)
            relative = self.run_cli(
                "enroll",
                "--alias",
                "sam",
                "--birth-year",
                "1952",
                "--role",
                "family",
                store=tmp,
            )
            self.assertEqual(relative.returncode, 0, relative.stderr)
            relation = self.run_cli(
                "family",
                "add",
                "--profile",
                "alex",
                "--relative",
                "sam",
                "--relation",
                "father",
                store=tmp,
            )
            self.assertEqual(relation.returncode, 0, relation.stderr)
            family_context = self.run_cli(
                "family",
                "condition",
                "--profile",
                "sam",
                "--condition",
                "hemochromatosis",
                "--status",
                "reported",
                store=tmp,
            )
            self.assertEqual(family_context.returncode, 0, family_context.stderr)

            crossref = self.run_cli("genomics", "crossref", "--profile", "alex", store=tmp)
            self.assertEqual(crossref.returncode, 0, crossref.stderr)
            self.assertIn("Genomics cross-reference review", crossref.stdout)
            self.assertIn("HFE C282Y", crossref.stdout)
            self.assertIn("SLCO1B1", crossref.stdout)
            self.assertIn("Family history/context matched", crossref.stdout)
            self.assertIn("confirmation_required: true", crossref.stdout)
            self.assertIn("Review note: use these as discussion prompts", crossref.stdout)
            self.assertIn("stored_genomic_inferences:", crossref.stdout)

            status = self.run_cli("genomics", "status", "--profile", "alex", store=tmp)
            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("sources: 1", status.stdout)
            self.assertIn("variants: 4", status.stdout)
            self.assertIn("stored_variant_scope: matched_allowlist_only", status.stdout)
            self.assertIn("review_note: context only", status.stdout)

            qc = self.run_cli("genomics", "qc", "--profile", "alex", store=tmp)
            self.assertEqual(qc.returncode, 0, qc.stderr)
            self.assertIn("call_rate: 0.800", qc.stdout)
            self.assertIn("consumer_or_unconfirmed_source_review", qc.stdout)

            annotated = self.run_cli("genomics", "annotate", "--profile", "alex", store=tmp)
            self.assertEqual(annotated.returncode, 0, annotated.stderr)
            self.assertIn("known_marker_matches: 4", annotated.stdout)
            self.assertIn("No external annotation calls were made", annotated.stdout)

            explain = self.run_cli(
                "genomics", "explain", "rs1800562", "--profile", "alex", store=tmp
            )
            self.assertEqual(explain.returncode, 0, explain.stderr)
            self.assertIn("HFE", explain.stdout)
            self.assertIn("source_url:", explain.stdout)
            self.assertIn("AG", explain.stdout)

            pgx = self.run_cli("genomics", "pgx", "--profile", "alex", store=tmp)
            self.assertEqual(pgx.returncode, 0, pgx.stderr)
            self.assertIn("Pharmacogenomics context", pgx.stdout)
            self.assertIn("medication decisions with clinical review", pgx.stdout)

            confirm = self.run_cli("genomics", "confirm-list", "--profile", "alex", store=tmp)
            self.assertEqual(confirm.returncode, 0, confirm.stderr)
            self.assertIn("Genomics confirmation list", confirm.stdout)
            self.assertIn("Confirm decision-relevant findings", confirm.stdout)

    def test_genomics_service_routes_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_cli("service", "--local", "--smoke", "--accept-risk", store=tmp)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("/genomics/sources", result.stdout)
            self.assertIn("/health/ui/", result.stdout)
            self.assertIn("/genomics/qc", result.stdout)
            self.assertIn("/genomics/crossrefs", result.stdout)
            self.assertIn("/genomics/review", result.stdout)
            self.assertIn("/genomics/ui", result.stdout)
            self.assertIn("/genomics/import-text", result.stdout)
            self.assertIn("/genomics/crossrefs/run", result.stdout)

    def test_genomics_gui_contract_is_local_and_privacy_safe(self):
        html = render_genomics_import_ui()
        routes = {f"{row['method']} {row['path']}" for row in route_manifest()}
        self.assertIn('id="file"', html)
        self.assertIn("acceptRisk", html)
        self.assertIn("/genomics/import-text", html)
        self.assertIn("/genomics/crossrefs/run", html)
        self.assertIn("/genomics/review", html)
        self.assertIn("includeResearch", html)
        self.assertIn("Health home", html)
        self.assertIn("/health/ui/", html)
        self.assertIn("does not send the browser filename", html)
        self.assertIn("form-stack", html)
        self.assertIn("checkbox-group", html)
        self.assertIn("review-table", html)
        self.assertIn("cardPatientSummary", html)
        self.assertIn("patientSummary", html)
        self.assertIn("renderPatientSummary", html)
        self.assertIn("patient_summary", html)
        self.assertIn("Research context", html)
        self.assertIn("renderResearchCard", html)
        self.assertIn("isResearchCard", html)
        self.assertNotIn("Genetic data warning", html)
        self.assertNotIn("Plain-language summary", html)
        self.assertNotIn("/Users/", html)
        self.assertNotIn("Mobile Documents", html)
        self.assertIn("GET /genomics/ui", routes)
        self.assertIn("GET /health/ui/", routes)
        self.assertIn("GET /genomics/review", routes)
        self.assertIn("POST /genomics/import-text", routes)
        self.assertIn("POST /genomics/crossrefs/run", routes)

    def test_genomics_gui_import_passes_research_opt_in(self):
        with tempfile.TemporaryDirectory() as tmp:
            health_store = LocalHealthStore(tmp)
            health_store.init()
            health_store.enroll_profile(EnrolledProfile(profile_id="alex", birth_year=1983))
            server = GenomicsGuiServer(("127.0.0.1", 0), health_store)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                port = server.server_address[1]
                body = json.dumps(
                    {
                        "profile_id": "alex",
                        "source_kind": "auto",
                        "clinical_grade": False,
                        "include_research_markers": True,
                        "accept_genetic_risk": True,
                        "content": (
                            "# synthetic dyslexia research marker fixture\n"
                            "rsid\tchromosome\tposition\tgenotype\n"
                            "rs13082684\t3\t136000000\tGG\n"
                            "rs2426117\t20\t49000000\tAG\n"
                        ),
                    }
                ).encode("utf-8")
                request = urllib.request.Request(
                    f"http://127.0.0.1:{port}/genomics/import-text",
                    data=body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(request, timeout=5) as response:
                    payload = json.loads(response.read().decode("utf-8"))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

            diagnostics = payload["match_diagnostics"]
            self.assertTrue(diagnostics["include_research_markers"])
            self.assertEqual(diagnostics["dyslexia_gwas_marker_matches"], 2)
            self.assertEqual(diagnostics["dyslexia_gwas_effect_marker_matches"], 2)
            self.assertEqual(payload["stored_variant_count"], 2)
            titles = {card["title"] for card in payload["inferences"]}
            self.assertIn("Dyslexia GWAS research marker coverage", titles)

    def test_genomics_health_home_static_target_is_path_safe(self):
        from llm_health.genomics.gui import health_ui_target, render_health_ui_missing

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(
                health_ui_target(root, "/health/ui/"),
                (root / "v2-web" / "index.html").resolve(),
            )
            self.assertEqual(
                health_ui_target(root, "/health/ui/assets/app.js"),
                (root / "v2-web" / "assets" / "app.js").resolve(),
            )
            self.assertIsNone(health_ui_target(root, "/health/ui/../../secret"))
        missing = render_health_ui_missing()
        self.assertIn("Health home is not exported yet", missing)
        self.assertNotIn("/Users/", missing)

    def test_capabilities_include_genomics(self):
        result = self.run_cli("capabilities", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        ids = {row["capability_id"] for row in payload}
        self.assertIn("genomics", ids)


if __name__ == "__main__":
    unittest.main()
