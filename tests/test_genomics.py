import json
import os
import subprocess
import sys
import tempfile
import unittest
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
from llm_health.genomics.gui import render_genomics_import_ui
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
            self.assertIn("consumer_or_unconfirmed_source_not_diagnostic", qc.warnings)

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
            self.assertIn("not stored", summary.to_dict()["privacy"])
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
            self.assertIn("not diagnostic", imported.stdout)
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
            self.assertIn("This is not medical advice", crossref.stdout)
            self.assertIn("stored_genomic_inferences:", crossref.stdout)

            status = self.run_cli("genomics", "status", "--profile", "alex", store=tmp)
            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("sources: 1", status.stdout)
            self.assertIn("variants: 4", status.stdout)
            self.assertIn("stored_variant_scope: matched_allowlist_only", status.stdout)
            self.assertIn("not diagnostic", status.stdout)

            qc = self.run_cli("genomics", "qc", "--profile", "alex", store=tmp)
            self.assertEqual(qc.returncode, 0, qc.stderr)
            self.assertIn("call_rate: 0.800", qc.stdout)
            self.assertIn("consumer_or_unconfirmed_source_not_diagnostic", qc.stdout)

            annotated = self.run_cli("genomics", "annotate", "--profile", "alex", store=tmp)
            self.assertEqual(annotated.returncode, 0, annotated.stderr)
            self.assertIn("known_marker_matches: 4", annotated.stdout)
            self.assertIn("No external annotation calls were made", annotated.stdout)

            explain = self.run_cli(
                "genomics", "explain", "rs1800562", "--profile", "alex", store=tmp
            )
            self.assertEqual(explain.returncode, 0, explain.stderr)
            self.assertIn("HFE", explain.stdout)
            self.assertIn("AG", explain.stdout)

            pgx = self.run_cli("genomics", "pgx", "--profile", "alex", store=tmp)
            self.assertEqual(pgx.returncode, 0, pgx.stderr)
            self.assertIn("Pharmacogenomics context", pgx.stdout)
            self.assertIn("do not change medication", pgx.stdout)

            confirm = self.run_cli("genomics", "confirm-list", "--profile", "alex", store=tmp)
            self.assertEqual(confirm.returncode, 0, confirm.stderr)
            self.assertIn("Genomics confirmation list", confirm.stdout)
            self.assertIn("Confirm high-impact findings", confirm.stdout)

    def test_genomics_service_routes_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_cli("service", "--local", "--smoke", "--accept-risk", store=tmp)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("/genomics/sources", result.stdout)
            self.assertIn("/genomics/qc", result.stdout)
            self.assertIn("/genomics/crossrefs", result.stdout)
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
        self.assertIn("does not send the selected file name/path", html)
        self.assertNotIn("/Users/", html)
        self.assertNotIn("Mobile Documents", html)
        self.assertIn("GET /genomics/ui", routes)
        self.assertIn("POST /genomics/import-text", routes)
        self.assertIn("POST /genomics/crossrefs/run", routes)

    def test_capabilities_include_genomics(self):
        result = self.run_cli("capabilities", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        ids = {row["capability_id"] for row in payload}
        self.assertIn("genomics", ids)


if __name__ == "__main__":
    unittest.main()
