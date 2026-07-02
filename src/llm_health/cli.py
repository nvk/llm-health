from __future__ import annotations

import argparse
import json
import sys
import webbrowser
from importlib import resources
from pathlib import Path

from llm_health import __version__
from llm_health.agreement import (
    RiskAgreementRequired,
    read_agreement_status,
    render_disclaimer,
    require_agreement,
    write_agreement_acceptance,
)
from llm_health.archive import create_archive, list_archives, verify_archive
from llm_health.assessment_v2.bridge import import_latest_for_profile
from llm_health.assessment_v2.export.v2_web import export_v2_web
from llm_health.config import (
    load_config,
    resolve_store_path,
    resolve_wiki_root,
    set_hub_path,
    set_wiki_root,
)
from llm_health.core.models import ContextNote, EnrolledProfile, Observation, stable_id
from llm_health.core.privacy import PrivacyError, validate_profile_alias
from llm_health.deid import (
    deidentify_text,
    load_text_input,
    render_extract,
    stage_deidentified_text,
)
from llm_health.engine import DiagnosticGapEngine, LeastHarmEngine, ReviewEngine
from llm_health.family import (
    FamilyHistoryEvent,
    FamilyRelationship,
    create_family_risk_notes,
    render_family_history,
    render_family_risks,
    render_family_tree,
)
from llm_health.genomics import (
    GenomicsStore,
    build_crossrefs_for_review,
    build_qc,
    import_raw_genotype_text_into_store,
)
from llm_health.genomics.gui import GenomicsGuiServer
from llm_health.genomics.qc import render_qc
from llm_health.genomics.review import (
    render_annotation_summary,
    render_confirm_list,
    render_explain,
    render_inferences,
    render_pgx,
    render_sources,
)
from llm_health.onboarding import (
    SOURCE_LINKS,
    SOURCE_NOTES,
    render_data_wishlist,
    render_dr_visit,
    render_welcome,
)
from llm_health.operator_runtime import (
    build_operator_draft,
    render_audit_trace,
    render_operator_draft,
    trace_for_draft,
)
from llm_health.registry import dumps_capabilities, render_capabilities
from llm_health.reports import generate_profile_report, generate_profile_reports
from llm_health.research import ResearchWorkflowSpec
from llm_health.service import LOCAL_HOSTS, render_service_routes, run_service
from llm_health.source_vault import (
    audit_ingested_sources,
    catalog_sources,
    init_source_vault,
    latest_audit,
    load_records,
    render_audit,
    render_catalog_summary,
    render_records,
)
from llm_health.specialists import (
    create_specialist_notes,
    list_specialists,
    render_specialist_notes,
    render_specialists,
    resolve_specialist_id,
)
from llm_health.stores import LocalHealthStore
from llm_health.test_batteries import TestBatteryEngine, render_test_battery


def _store_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--store",
        default=None,
        help=(
            "Override store path; default resolves from LLM_HEALTH_HUB "
            "or ~/.config/llm-health/config.json"
        ),
    )


def _store_from_args(args: argparse.Namespace) -> LocalHealthStore:
    return LocalHealthStore(resolve_store_path(getattr(args, "store", None)))


def _risk_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--accept-risk",
        action="store_true",
        help="Explicitly accept the own-risk agreement for this local HUB before running",
    )


def _ensure_risk_agreement(args: argparse.Namespace, store: LocalHealthStore) -> None:
    if getattr(args, "accept_risk", False):
        write_agreement_acceptance(store.root)
        return
    require_agreement(store.root)


def _private_store_from_args(args: argparse.Namespace) -> LocalHealthStore:
    store = _store_from_args(args)
    _ensure_risk_agreement(args, store)
    return store


def _profile_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--profile", required=True, help="De-identified enrolled profile alias")


def _profile_for_store(args: argparse.Namespace, store: LocalHealthStore) -> str:
    profile = validate_profile_alias(args.profile)
    if not store.profile_exists(profile):
        raise PrivacyError(f"profile alias {profile!r} is not enrolled; run `health enroll` first")
    return profile


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="llm-health", description="Local health intelligence CLI")
    parser.add_argument("--version", action="version", version=f"llm-health {__version__}")
    sub = parser.add_subparsers(dest="command", required=False)

    doctor = sub.add_parser("doctor", help="Check basic runtime status")
    _store_arg(doctor)

    init = sub.add_parser("init", help="Initialize the resolved llm-health HUB/store")
    _store_arg(init)
    _risk_arg(init)

    enroll = sub.add_parser("enroll", help="Enroll a de-identified profile alias")
    _store_arg(enroll)
    _risk_arg(enroll)
    enroll.add_argument("--alias", required=True, help="Alias token, e.g. sol")
    enroll.add_argument("--birth-year", type=int, help="Birth year only; no full birth dates")
    enroll.add_argument(
        "--birth-month",
        type=int,
        help="Optional birth month 1-12 when month precision is useful; no birth day",
    )
    enroll.add_argument("--role", help="Alias-safe role/context label")
    enroll.add_argument("--note", help="Alias-safe note; do not include raw identifiers")

    profiles = sub.add_parser("profiles", help="List enrolled profile aliases")
    _store_arg(profiles)
    _risk_arg(profiles)

    welcome = sub.add_parser("welcome", help="Show first-run onboarding and intake prompts")
    _store_arg(welcome)

    data_wishlist = sub.add_parser("data-wishlist", help="Show useful data dumps to import")
    _store_arg(data_wishlist)

    dr_visit = sub.add_parser("dr-visit", help="Show cadence-aware check-in questions")
    _store_arg(dr_visit)
    _risk_arg(dr_visit)
    _profile_arg(dr_visit)
    dr_visit.add_argument(
        "--cadence",
        choices=[
            "onboarding",
            "weekly",
            "monthly",
            "quarterly",
            "annual",
            "pre-lab",
            "post-result",
        ],
        default="monthly",
    )
    dr_visit.add_argument(
        "--sources", action="store_true", help="Also print source/rationale notes for the cadence"
    )

    config = sub.add_parser("config", help="Read or write llm-health config")
    config_sub = config.add_subparsers(dest="config_command", required=True)
    config_show = config_sub.add_parser("show", help="Show current config and resolved store")
    config_show.add_argument("--config-path")
    config_hub = config_sub.add_parser("hub-path", help="Set the default llm-health HUB path")
    config_hub.add_argument("path")
    config_hub.add_argument("--config-path")
    config_hub.add_argument("--init", action="store_true", help="Initialize the hub after saving")
    config_hub.add_argument(
        "--accept-risk",
        action="store_true",
        help="Accept the own-risk agreement when initializing the hub",
    )
    config_wiki = config_sub.add_parser(
        "wiki-root", help="Set the default health-assessments wiki root for UI exports"
    )
    config_wiki.add_argument("path")
    config_wiki.add_argument("--config-path")

    ui = sub.add_parser("ui", help="Regenerate and open the local Assessment v2 static UI")
    _store_arg(ui)
    _risk_arg(ui)
    ui.add_argument("--wiki-root", help="Override health-assessments wiki root for this run")
    ui.add_argument(
        "--output",
        help="Override static UI output directory; default is <resolved HUB>/v2-web",
    )
    ui.add_argument("--no-open", action="store_true", help="Export only; do not open browser")

    report = sub.add_parser(
        "report", help="Generate de-identified PDF reports for doctors or family"
    )
    _store_arg(report)
    _risk_arg(report)
    _profile_arg(report)
    report.add_argument(
        "--audience",
        choices=["doctor", "family", "both"],
        default="both",
        help="doctor=clinician brief, family=plain-language summary, both=two PDFs",
    )
    report.add_argument(
        "--range",
        choices=["all", "30d", "90d", "ytd", "18mo"],
        default="all",
        help="Observation date window for the report",
    )
    report.add_argument(
        "--wiki-root",
        help=(
            "Optional health-assessments wiki root; default uses configured wiki root "
            "to include full v2 history"
        ),
    )
    report.add_argument(
        "--max-observations",
        type=int,
        default=50,
        help="Maximum recent source rows in the appendix",
    )
    report.add_argument(
        "--output",
        help="Output PDF path; valid only when --audience is doctor or family",
    )
    report.add_argument(
        "--output-dir",
        help="Output directory; default is <resolved HUB>/reports",
    )
    report.add_argument("--open", action="store_true", help="Open generated PDF(s)")

    archive = sub.add_parser("archive", help="Create/list/verify compressed HUB archives")
    archive_sub = archive.add_subparsers(dest="archive_command", required=True)
    archive_create = archive_sub.add_parser(
        "create", help="Create a privacy-scanned compressed archive under <HUB>/archives"
    )
    _store_arg(archive_create)
    _risk_arg(archive_create)
    archive_create.add_argument(
        "--output-dir", help="Override archive destination; default is <resolved HUB>/archives"
    )
    archive_create.add_argument(
        "--no-ui", action="store_true", help="Exclude generated v2-web static dashboard files"
    )
    archive_create.add_argument(
        "--no-v2-data", action="store_true", help="Exclude generated v2-data DuckDB/Parquet files"
    )
    archive_create.add_argument(
        "--no-deid-staging", action="store_true", help="Exclude de-identified staging text"
    )
    archive_create.add_argument(
        "--strict",
        action="store_true",
        help="Fail instead of skipping files that fail privacy scan",
    )
    archive_create.add_argument("--json", action="store_true", help="Print machine-readable JSON")

    archive_list = archive_sub.add_parser("list", help="List local HUB archive files")
    _store_arg(archive_list)
    _risk_arg(archive_list)
    archive_list.add_argument(
        "--output-dir", help="Override archive directory; default is <resolved HUB>/archives"
    )

    archive_verify = archive_sub.add_parser("verify", help="Verify archive member checksums")
    _store_arg(archive_verify)
    _risk_arg(archive_verify)
    archive_verify.add_argument("path", help="Archive .tar.gz path to verify")
    archive_verify.add_argument("--json", action="store_true", help="Print machine-readable JSON")

    source_vault = sub.add_parser(
        "source-vault", help="Manage optional raw-source vault catalog and hash blobs"
    )
    source_vault_sub = source_vault.add_subparsers(dest="source_vault_command", required=True)
    source_vault_init = source_vault_sub.add_parser("init", help="Initialize source vault")
    _store_arg(source_vault_init)
    _risk_arg(source_vault_init)

    source_vault_add = source_vault_sub.add_parser(
        "add", help="Catalog source files and optionally copy raw blobs by hash"
    )
    _store_arg(source_vault_add)
    _risk_arg(source_vault_add)
    source_vault_add.add_argument("inputs", nargs="+", help="Source file/folder inputs")
    source_vault_add.add_argument("--wiki-root", help="Map raw files to ingested source IDs")
    source_vault_add.add_argument("--profile", help="Alias for unmatched files")
    source_vault_add.add_argument("--copy", action="store_true", help="Copy raw blobs into vault")
    source_vault_add.add_argument(
        "--accept-raw-storage",
        action="store_true",
        help="Required with --copy; raw blobs stay private and are excluded from normal archives",
    )
    source_vault_add.add_argument("--json", action="store_true", help="Print JSON summary")

    source_vault_list = source_vault_sub.add_parser("list", help="List source-vault records")
    _store_arg(source_vault_list)
    _risk_arg(source_vault_list)
    source_vault_list.add_argument("--json", action="store_true", help="Print JSON records")

    source_audit = sub.add_parser(
        "source-audit", help="Audit ingested rows against source vault and extraction checks"
    )
    source_audit_sub = source_audit.add_subparsers(dest="source_audit_command", required=True)
    source_audit_run = source_audit_sub.add_parser("run", help="Run source/row audit")
    _store_arg(source_audit_run)
    _risk_arg(source_audit_run)
    source_audit_run.add_argument("--wiki-root", help="Override health-assessments wiki root")
    source_audit_run.add_argument("--profile", help="Optional profile alias")
    source_audit_run.add_argument(
        "--focus", choices=["medium", "all", "missing"], default="medium"
    )
    source_audit_run.add_argument(
        "--no-extract", action="store_true", help="Skip PDF extraction summaries"
    )
    source_audit_run.add_argument("--no-persist", action="store_true", help="Print only")
    source_audit_run.add_argument("--json", action="store_true", help="Print JSON audit")

    source_audit_report = source_audit_sub.add_parser(
        "report", help="Show latest persisted source audit"
    )
    _store_arg(source_audit_report)
    _risk_arg(source_audit_report)
    source_audit_report.add_argument("--json", action="store_true", help="Print JSON audit")

    agreement = sub.add_parser("agreement", help="Show or accept the own-risk agreement")
    _store_arg(agreement)
    agreement_sub = agreement.add_subparsers(dest="agreement_command", required=False)
    agreement_show = agreement_sub.add_parser("show", help="Print the full own-risk disclaimer")
    _store_arg(agreement_show)
    agreement_status = agreement_sub.add_parser(
        "status", help="Print agreement status for the resolved HUB"
    )
    _store_arg(agreement_status)
    agreement_accept = agreement_sub.add_parser("accept", help="Accept the own-risk agreement")
    _store_arg(agreement_accept)
    agreement_accept.add_argument(
        "--own-risk",
        action="store_true",
        required=True,
        help="Required explicit acknowledgement that use is at your own risk",
    )

    ingest = sub.add_parser(
        "ingest-note", help="Add one de-identified observation and trigger review"
    )
    _store_arg(ingest)
    _risk_arg(ingest)
    _profile_arg(ingest)
    ingest.add_argument("--marker", required=True)
    ingest.add_argument("--value", type=float)
    ingest.add_argument("--unit")
    ingest.add_argument("--category", default="uncategorized")
    ingest.add_argument("--date", dest="observed_on")
    ingest.add_argument("--flag")
    ingest.add_argument("--reference-range")
    ingest.add_argument("--comparator")
    ingest.add_argument("--specimen")
    ingest.add_argument("--interpretation")
    ingest.add_argument("--source-id", default="user_note")
    ingest.add_argument("--note")
    ingest.add_argument(
        "--deep",
        choices=["smart", "always", "none"],
        default="smart",
        help="Deep research queuing mode for this ingest",
    )

    sync_v2 = sub.add_parser(
        "sync-v2", help="Import latest de-identified v2 canonical rows and trigger review"
    )
    _store_arg(sync_v2)
    _risk_arg(sync_v2)
    sync_v2.add_argument(
        "--wiki-root",
        required=True,
        help="health-assessments wiki root containing output/data CSVs",
    )
    sync_v2.add_argument("--profile", required=True, choices=["rod", "cara", "all"])
    sync_v2.add_argument("--deep", choices=["smart", "always", "none"], default="smart")

    review = sub.add_parser("review", help="Show latest quick-review cards")
    _store_arg(review)
    _risk_arg(review)
    _profile_arg(review)
    review.add_argument("--limit", type=int, default=10)

    self_report = sub.add_parser(
        "self-report", help="Record a self-reported context note, not a lab result"
    )
    _store_arg(self_report)
    _risk_arg(self_report)
    _profile_arg(self_report)
    self_report.add_argument("--subject", required=True)
    self_report.add_argument("--status", required=True)
    self_report.add_argument("--note", required=True)
    self_report.add_argument("--date", dest="observed_on")

    context = sub.add_parser("context", help="Show self-reported context notes")
    _store_arg(context)
    _risk_arg(context)
    _profile_arg(context)
    context.add_argument("--subject")
    context.add_argument("--limit", type=int, default=10)

    family = sub.add_parser("family", help="Manage alias-only family history and kinship graph")
    family_sub = family.add_subparsers(dest="family_command", required=True)

    family_add = family_sub.add_parser("add", help="Add a relationship edge")
    _store_arg(family_add)
    _risk_arg(family_add)
    _profile_arg(family_add)
    family_add.add_argument("--relative", required=True, help="Alias of relative profile")
    family_add.add_argument(
        "--relation", required=True, help="father, mother, sibling, child, etc."
    )
    family_add.add_argument("--degree", type=int, help="Optional biological degree 1-5")
    family_add.add_argument(
        "--lineage", default="unknown", help="paternal, maternal, both, household, unknown"
    )
    family_add.add_argument(
        "--shared-household",
        choices=["yes", "no", "unknown"],
        default="unknown",
        help="Whether profiles share/sharing household exposure context",
    )
    family_add.add_argument("--note", help="Alias-safe relationship note")

    family_condition = family_sub.add_parser("condition", help="Record family health history")
    _store_arg(family_condition)
    _risk_arg(family_condition)
    _profile_arg(family_condition)
    family_condition.add_argument("--condition", required=True)
    family_condition.add_argument(
        "--status",
        default="reported",
        choices=["reported", "observed", "believed", "confirmed", "absent", "unknown"],
    )
    family_condition.add_argument("--evidence", default="self_report")
    family_condition.add_argument("--onset-age", type=int)
    family_condition.add_argument("--note", help="Alias-safe family-history note")
    family_condition.add_argument(
        "--related",
        action="append",
        default=[],
        help="Optional related profile alias; repeatable",
    )

    family_tree = family_sub.add_parser("tree", help="Show family tree around a profile")
    _store_arg(family_tree)
    _risk_arg(family_tree)
    _profile_arg(family_tree)

    family_history = family_sub.add_parser("history", help="Show family history events")
    _store_arg(family_history)
    _risk_arg(family_history)
    family_history.add_argument("--profile", help="Optional profile alias filter")

    family_risks = family_sub.add_parser("risks", help="Generate family-pattern risk notes")
    _store_arg(family_risks)
    _risk_arg(family_risks)
    _profile_arg(family_risks)
    family_risks.add_argument(
        "--no-persist", action="store_true", help="Print only; do not store generated risk notes"
    )

    result = sub.add_parser(
        "result", help="Show latest matching observation(s) with source reference range"
    )
    _store_arg(result)
    _risk_arg(result)
    _profile_arg(result)
    result.add_argument("--marker", required=True, help="Marker/category substring, e.g. mercury")
    result.add_argument("--category", help="Optional category substring filter")
    result.add_argument("--limit", type=int, default=5)

    gaps = sub.add_parser("close-gaps", help="Create diagnostic-gap/test-candidate cards")
    _store_arg(gaps)
    _risk_arg(gaps)
    _profile_arg(gaps)

    battery = sub.add_parser(
        "test-battery", help="Suggest profile-aware TEST_CANDIDATE batteries"
    )
    _store_arg(battery)
    _risk_arg(battery)
    _profile_arg(battery)
    battery.add_argument(
        "--scope",
        choices=["core", "expanded", "complete"],
        default="expanded",
        help="core=must/high, expanded=adds medium/low, complete=also nice-to-have",
    )
    battery.add_argument(
        "--category",
        default="all",
        help=(
            "all, foundation, cardio, metabolic, liver, kidney, nutrient, hormone, "
            "inflammation, exposure, sleep, pediatric, gaps"
        ),
    )
    battery.add_argument(
        "--no-gaps",
        action="store_true",
        help="Do not blend current diagnostic-gap candidates into the battery",
    )
    battery.add_argument(
        "--sources", action="store_true", help="Print source/rationale notes and links"
    )
    battery.add_argument(
        "--queue-research",
        action="store_true",
        help="Queue deep research jobs to refresh the selected battery",
    )

    plan = sub.add_parser(
        "plan-research", help="Show queued research jobs and the default research contract"
    )
    _store_arg(plan)
    _risk_arg(plan)
    _profile_arg(plan)
    plan.add_argument("--topic", help="Create a research workflow spec for a new topic")

    plugins = sub.add_parser(
        "plugin-paths", help="Print packaged agent/plugin template paths"
    )
    plugins.add_argument(
        "--kind",
        choices=["codex", "claude", "opencode", "agents", "all"],
        default="all",
    )

    genomics = sub.add_parser(
        "genomics",
        help="Import, QC, annotate, and cross-reference local genotype data",
    )
    genomics_sub = genomics.add_subparsers(dest="genomics_command", required=True)

    genomics_import = genomics_sub.add_parser(
        "import",
        help="Run local SNP matching against raw genotype text without storing the raw file/path",
    )
    _store_arg(genomics_import)
    _risk_arg(genomics_import)
    _profile_arg(genomics_import)
    genomics_import.add_argument("input", help="Local raw genotype text file to scan/match")
    genomics_import.add_argument(
        "--source-kind",
        choices=["auto", "23andme", "ancestrydna", "raw_genotype", "clinical_lab"],
        default="auto",
    )
    genomics_import.add_argument(
        "--clinical-grade",
        action="store_true",
        help="Mark source as clinical-grade; default treats it as unconfirmed context",
    )
    genomics_import.add_argument(
        "--accept-genetic-risk",
        action="store_true",
        help="Required: acknowledge genetic privacy/family implications for this import",
    )
    genomics_import.add_argument(
        "--store-dense-variants",
        action="store_true",
        help="Store dense genome-wide calls locally instead of matched SNP findings only",
    )
    genomics_import.add_argument(
        "--accept-dense-genetic-storage",
        action="store_true",
        help="Required with --store-dense-variants; intended only for local FOSS workflows",
    )
    genomics_import.add_argument(
        "--include-research-markers",
        action="store_true",
        help=(
            "Opt in to non-diagnostic research trait marker lists such as dyslexia, "
            "ADHD, and autism-spectrum GWAS lead SNPs; excluded from default matching"
        ),
    )

    for name, help_text in [
        ("status", "Show imported genomic sources and counts"),
        ("qc", "Show genotype source QC summaries"),
        ("annotate", "Summarize bundled local marker annotations"),
        ("crossref", "Create genotype x labs/meds/family review cards"),
        ("pgx", "Show pharmacogenomics review context"),
        ("confirm-list", "Show confirmation-first genomic review items"),
    ]:
        command = genomics_sub.add_parser(name, help=help_text)
        _store_arg(command)
        _risk_arg(command)
        _profile_arg(command)
        if name == "crossref":
            command.add_argument(
                "--with",
                dest="include",
                default="labs,meds,family",
                help="Comma-separated cross-reference domains: labs,meds,family",
            )
            command.add_argument(
                "--no-store",
                action="store_true",
                help="Print cards without persisting them",
            )

    genomics_explain = genomics_sub.add_parser("explain", help="Explain one rsID for a profile")
    _store_arg(genomics_explain)
    _risk_arg(genomics_explain)
    _profile_arg(genomics_explain)
    genomics_explain.add_argument("rsid")

    genomics_ui = genomics_sub.add_parser(
        "ui",
        aliases=["gui"],
        help="Open a localhost genotype import GUI with a browser file picker",
    )
    _store_arg(genomics_ui)
    _risk_arg(genomics_ui)
    genomics_ui.add_argument("--profile", help="Optional initial profile alias")
    genomics_ui.add_argument("--host", default="127.0.0.1", help="Bind host; defaults to localhost")
    genomics_ui.add_argument("--port", type=int, default=8766, help="Bind port")
    genomics_ui.add_argument("--no-open", action="store_true", help="Print URL without opening")
    genomics_ui.add_argument(
        "--allow-nonlocal",
        action="store_true",
        help="Allow a non-local bind; not recommended for private genetic data",
    )

    capabilities = sub.add_parser("capabilities", help="Show llm-health feature map metadata")
    capabilities.add_argument(
        "--kind",
        choices=["all", "core", "data", "review", "research", "ui", "agent", "privacy", "service"],
        default="all",
        help="Filter the registry by capability kind",
    )
    capabilities.add_argument("--json", action="store_true", help="Print machine-readable JSON")

    deid = sub.add_parser("deid", help="Preview or stage de-identified text")
    deid_sub = deid.add_subparsers(dest="deid_command", required=True)
    for action, help_text in [
        ("extract", "Extract safe de-id entity metadata"),
        ("preview", "Print redacted text without storing it"),
        ("apply", "Stage redacted text under the private HUB"),
    ]:
        deid_cmd = deid_sub.add_parser(action, help=help_text)
        _store_arg(deid_cmd)
        _risk_arg(deid_cmd)
        deid_cmd.add_argument("input", help="Text or path to a local text file")
        deid_cmd.add_argument(
            "--method",
            choices=["replace", "mask", "hash"],
            default="replace",
            help="Redaction style for replacements",
        )
        deid_cmd.add_argument("--json", action="store_true", help="Print JSON output")
        if action == "apply":
            deid_cmd.add_argument(
                "--staging-only",
                action="store_true",
                required=True,
                help="Required: write only redacted staging files, never raw input",
            )

    service = sub.add_parser("service", help="Start or smoke-test the local-only service")
    _store_arg(service)
    _risk_arg(service)
    service.add_argument(
        "--local",
        action="store_true",
        default=True,
        help="Use a localhost bind; this is the default and recommended mode",
    )
    service.add_argument("--host", default="127.0.0.1", help="Bind host; defaults to localhost")
    service.add_argument("--port", type=int, default=8765, help="Bind port")
    service.add_argument(
        "--allow-nonlocal",
        action="store_true",
        help="Explicitly allow a non-local bind host; not recommended",
    )
    service.add_argument("--smoke", action="store_true", help="Print routes without serving")

    operator = sub.add_parser(
        "operator", help="Visible plan/draft/finalize runtime for agent workflows"
    )
    operator_sub = operator.add_subparsers(dest="operator_command", required=True)
    operator_draft = operator_sub.add_parser("draft", help="Create a visible draft artifact")
    _store_arg(operator_draft)
    _risk_arg(operator_draft)
    _profile_arg(operator_draft)
    operator_draft.add_argument("--intent", required=True, help="Alias-safe user intent to plan")
    operator_draft.add_argument("--json", action="store_true", help="Print draft JSON")
    operator_draft.add_argument(
        "--no-store", action="store_true", help="Print only; do not persist draft/trace"
    )

    operator_list = operator_sub.add_parser("list", help="List operator drafts")
    _store_arg(operator_list)
    _risk_arg(operator_list)
    operator_list.add_argument("--profile", help="Optional profile alias filter")
    operator_list.add_argument(
        "--status",
        choices=["draft", "reviewed", "finalized", "archived"],
        help="Optional lifecycle status filter",
    )
    operator_list.add_argument("--limit", type=int, default=10)

    operator_show = operator_sub.add_parser("show", help="Show one operator draft")
    _store_arg(operator_show)
    _risk_arg(operator_show)
    operator_show.add_argument("--draft-id", required=True)
    operator_show.add_argument("--json", action="store_true")

    operator_finalize = operator_sub.add_parser(
        "finalize", help="Finalize a draft after explicit user approval"
    )
    _store_arg(operator_finalize)
    _risk_arg(operator_finalize)
    operator_finalize.add_argument("--draft-id", required=True)
    operator_finalize.add_argument(
        "--approve",
        action="store_true",
        required=True,
        help="Required explicit approval for lifecycle transition",
    )

    operator_traces = operator_sub.add_parser("traces", help="Show fingerprint-first audit traces")
    _store_arg(operator_traces)
    _risk_arg(operator_traces)
    operator_traces.add_argument("--profile", help="Optional profile alias filter")
    operator_traces.add_argument("--limit", type=int, default=10)

    specialists = sub.add_parser(
        "specialists", help="List registered specialist/category agents"
    )
    specialists.add_argument("--short", action="store_true", help="Print only ids and names")

    consult = sub.add_parser(
        "consult", help="Run a specialist/category-agent consult and persist notes"
    )
    _store_arg(consult)
    _risk_arg(consult)
    _profile_arg(consult)
    consult.add_argument(
        "--specialist",
        default="auto",
        help="auto, internal_medicine, liver_biliary_gi, toxins_exposures, etc.",
    )
    consult.add_argument("--topic", help="Optional focused question/topic for the consult")
    consult.add_argument(
        "--no-persist", action="store_true", help="Print consult notes without storing them"
    )

    specialist_notes = sub.add_parser("specialist-notes", help="Show stored specialist notes")
    _store_arg(specialist_notes)
    _risk_arg(specialist_notes)
    _profile_arg(specialist_notes)
    specialist_notes.add_argument("--specialist", help="Filter by specialist id/substring")
    specialist_notes.add_argument("--limit", type=int, default=10)

    least = sub.add_parser("least-harm", help="Draft a low-intervention option card")
    _store_arg(least)
    _risk_arg(least)
    least.add_argument("target")

    med = sub.add_parser("med-review", help="Draft a medication collateral-damage review")
    _store_arg(med)
    _risk_arg(med)
    _profile_arg(med)
    med.add_argument("--active", required=True)
    med.add_argument("--indication", default="unknown")

    protocol = sub.add_parser("protocol-review", help="Draft a preventive-protocol review card")
    _store_arg(protocol)
    _risk_arg(protocol)
    _profile_arg(protocol)
    protocol.add_argument("target")

    return parser


def cmd_doctor(args: argparse.Namespace) -> int:
    config = load_config()
    store_path = resolve_store_path(args.store)
    store = LocalHealthStore(store_path)
    exists = store_path.exists()
    try:
        config_exists = config.config_path.exists()
    except OSError:
        config_exists = False
    print(f"llm-health {__version__}")
    print(f"python: {sys.version.split()[0]}")
    print(f"config: {config.config_path} ({'exists' if config_exists else 'not found'})")
    print(f"hub: {config.hub_path or '[not set]'}")
    print(f"wiki_root: {config.wiki_root or '[not set]'}")
    print(f"store: {store.root} ({'exists' if exists else 'not initialized'})")
    agreement = read_agreement_status(store.root)
    print(f"agreement: {'accepted' if agreement.accepted else 'not accepted'}")
    if agreement.accepted_at:
        print(f"agreement_at: {agreement.accepted_at}")
    print("privacy: alias-only demo profiles; raw data paths blocked in stored artifacts")
    if not exists:
        print(
            "first_run: try `health welcome`, `health agreement show`, "
            "`health agreement accept --own-risk`, then "
            "`health enroll --alias <alias> --birth-year <yyyy>`"
        )
    print("status: ok")
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    store = _store_from_args(args)
    if args.accept_risk:
        status = write_agreement_acceptance(store.root)
        print(f"Accepted llm-health own-risk agreement: {status.version} at {status.accepted_at}")
    else:
        require_agreement(store.root)
    store.init()
    print(f"Initialized llm-health store: {store.root}")
    return 0


def cmd_enroll(args: argparse.Namespace) -> int:
    store = _private_store_from_args(args)
    store.init()
    profile = EnrolledProfile(
        profile_id=args.alias,
        birth_year=args.birth_year,
        birth_month=args.birth_month,
        role=args.role,
        note=args.note,
    )
    store.enroll_profile(profile)
    print(f"Enrolled profile alias: {profile.profile_id}")
    print(f"  Birth: {profile.birth_label}")
    if profile.role:
        print(f"  Role/context: {profile.role}")
    print(f"  Tags: {', '.join(profile.tags)}")
    return 0


def cmd_profiles(args: argparse.Namespace) -> int:
    store = _private_store_from_args(args)
    store.init()
    for profile in store.enrolled_profiles(include_defaults=True):
        role = f" · {profile.role}" if profile.role else ""
        print(f"{profile.profile_id} · birth {profile.birth_label}{role}")
    return 0


def cmd_welcome(args: argparse.Namespace) -> int:
    print(render_welcome())
    return 0


def cmd_data_wishlist(args: argparse.Namespace) -> int:
    print(render_data_wishlist())
    return 0


def cmd_dr_visit(args: argparse.Namespace) -> int:
    store = _private_store_from_args(args)
    store.init()
    profile = _profile_for_store(args, store)
    print(f"# Dr Visit for {profile} · {args.cadence}")
    print(render_dr_visit(args.cadence))
    if args.sources:
        print("\n## Source/rationale notes")
        for note in SOURCE_NOTES:
            print(f"- {note}")
        print("\n## Source links")
        for label, url in SOURCE_LINKS:
            print(f"- {label}: {url}")
    return 0


def cmd_agreement(args: argparse.Namespace) -> int:
    store = _store_from_args(args)
    command = args.agreement_command or "show"
    if command == "show":
        print(render_disclaimer())
        status = read_agreement_status(store.root)
        print()
        print("## Current HUB status")
        print(f"store: {store.root}")
        print(f"agreement: {'accepted' if status.accepted else 'not accepted'}")
        if status.accepted_at:
            print(f"accepted_at: {status.accepted_at}")
        return 0
    if command == "status":
        status = read_agreement_status(store.root)
        print(f"store: {store.root}")
        print(f"agreement: {'accepted' if status.accepted else 'not accepted'}")
        print(f"agreement_version: {status.version or '[none]'}")
        if status.accepted_at:
            print(f"accepted_at: {status.accepted_at}")
        return 0
    if command == "accept":
        status = write_agreement_acceptance(store.root)
        print(f"Accepted llm-health own-risk agreement: {status.version}")
        print(f"accepted_at: {status.accepted_at}")
        print(f"store: {store.root}")
        return 0
    raise ValueError(f"unknown agreement command: {command}")


def cmd_config(args: argparse.Namespace) -> int:
    if args.config_command == "show":
        config = load_config(args.config_path)
        print(f"config: {config.config_path}")
        print(f"hub: {config.hub_path or '[not set]'}")
        print(f"wiki_root: {config.wiki_root or '[not set]'}")
        print(f"resolved_store: {config.hub_path or resolve_store_path()}")
        print(f"resolved_wiki_root: {config.wiki_root or resolve_wiki_root() or '[not set]'}")
        return 0
    if args.config_command == "hub-path":
        config = set_hub_path(args.path, args.config_path)
        print(f"Saved llm-health hub_path: {config.hub_path}")
        print(f"config: {config.config_path}")
        if args.init:
            store = LocalHealthStore(config.hub_path)
            if args.accept_risk:
                status = write_agreement_acceptance(store.root)
                print(
                    f"Accepted llm-health own-risk agreement: {status.version} "
                    f"at {status.accepted_at}"
                )
            else:
                require_agreement(store.root)
            store.init()
            print(f"Initialized llm-health HUB/store: {store.root}")
        return 0
    if args.config_command == "wiki-root":
        config = set_wiki_root(args.path, args.config_path)
        print(f"Saved llm-health wiki_root: {config.wiki_root}")
        print(f"config: {config.config_path}")
        return 0
    raise ValueError(f"unknown config command: {args.config_command}")


def cmd_ui(args: argparse.Namespace) -> int:
    store = _private_store_from_args(args)
    store.init()
    wiki_root = resolve_wiki_root(args.wiki_root)
    if wiki_root is None:
        print(
            "wiki root not configured. Run `health config wiki-root <wiki-root>` "
            "or pass `health ui --wiki-root <path>`.",
            file=sys.stderr,
        )
        return 4
    observations_csv = wiki_root / "output" / "data" / "lab-observations-long.csv"
    if not observations_csv.exists():
        print(
            f"wiki root missing canonical observations CSV: {observations_csv}",
            file=sys.stderr,
        )
        return 4
    output_dir = Path(args.output).expanduser() if args.output else store.root / "v2-web"
    export = export_v2_web(wiki_root, output_dir)
    index_path = export.output_dir / "index.html"
    print(
        f"exported UI: {export.observation_count:,} observations, "
        f"{export.report_count:,} reports, {export.wearable_daily_count:,} wearable daily rows"
    )
    print(f"open: {index_path}")
    if export.latest_weights:
        weights = ", ".join(
            f"{profile}: {value:g} kg" for profile, value in sorted(export.latest_weights.items())
        )
        print(f"latest weights: {weights}")
    if not args.no_open:
        webbrowser.open(index_path.resolve().as_uri())
        print("browser: opened")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    store = _private_store_from_args(args)
    store.init()
    profile = _profile_for_store(args, store)
    if args.output and args.audience == "both":
        print(
            "--output can only be used with --audience doctor or --audience family",
            file=sys.stderr,
        )
        return 4
    if args.output and args.output_dir:
        print("use either --output or --output-dir, not both", file=sys.stderr)
        return 4
    output_dir = Path(args.output_dir).expanduser() if args.output_dir else None
    wiki_root = resolve_wiki_root(args.wiki_root)
    if args.output:
        report = generate_profile_report(
            store,
            profile,
            audience=args.audience,
            output=Path(args.output).expanduser(),
            wiki_root=wiki_root,
            date_range=args.range,
            max_observations=args.max_observations,
        )
        reports = [report]
    else:
        reports = generate_profile_reports(
            store,
            profile,
            audience=args.audience,
            output_dir=output_dir,
            wiki_root=wiki_root,
            date_range=args.range,
            max_observations=args.max_observations,
        )
    for report in reports:
        print(
            f"{report.audience}: {report.path} "
            f"({report.observation_count} rows, {report.active_flag_count} active flags, "
            f"{report.pending_count} pending)"
        )
        if args.open:
            webbrowser.open(report.path.resolve().as_uri())
    print("privacy: report is alias-only; verify original sources before decisions")
    return 0


def cmd_archive(args: argparse.Namespace) -> int:
    store = _private_store_from_args(args)
    store.init()

    if args.archive_command == "create":
        result = create_archive(
            store.root,
            output_dir=Path(args.output_dir).expanduser() if args.output_dir else None,
            include_ui=not args.no_ui,
            include_v2_data=not args.no_v2_data,
            include_deid_staging=not args.no_deid_staging,
            strict=args.strict,
        )
        if args.json:
            print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
            return 0
        print(f"archive: {result.archive_path}")
        print(f"archive_id: {result.archive_id}")
        print(f"members: {result.member_count}")
        print(f"skipped: {result.skipped_count}")
        print(f"size: {result.size_bytes:,} bytes")
        if result.skipped:
            print("privacy_skips:")
            for item in result.skipped[:8]:
                print(f"- {item.path}: {item.reason}")
            if len(result.skipped) > 8:
                print(f"- ... {len(result.skipped) - 8} more")
            print(
                "note: skipped files are not archived; rebuild/regenerate sanitized data if needed."
            )
        return 0

    if args.archive_command == "list":
        archives = list_archives(
            store.root, output_dir=Path(args.output_dir).expanduser() if args.output_dir else None
        )
        if not archives:
            print("No llm-health archives found.")
            return 0
        for path in archives:
            print(f"{path.name}	{path.stat().st_size} bytes")
        return 0

    if args.archive_command == "verify":
        manifest, failures = verify_archive(Path(args.path))
        if args.json:
            print(
                json.dumps(
                    {"manifest": manifest, "failures": failures, "ok": not failures},
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0 if not failures else 4
        print(f"archive_id: {manifest.get('archive_id', '[unknown]')}")
        print(f"members: {manifest.get('member_count', '[unknown]')}")
        print(f"skipped: {manifest.get('skipped_count', '[unknown]')}")
        if failures:
            print("status: failed")
            for failure in failures:
                print(f"- {failure}")
            return 4
        print("status: ok")
        return 0

    raise ValueError(f"unknown archive command: {args.archive_command}")


def cmd_source_vault(args: argparse.Namespace) -> int:
    store = _private_store_from_args(args)
    store.init()

    if args.source_vault_command == "init":
        path = init_source_vault(store.root)
        print("Initialized source vault")
        print(f"vault: {path}")
        print("privacy: raw paths and filenames are not stored in the manifest")
        print("archive: source-vault is excluded from normal de-identified HUB archives")
        return 0

    if args.source_vault_command == "add":
        if args.copy and not args.accept_raw_storage:
            print(
                "refusing raw blob copy without --accept-raw-storage; "
                "use catalog-only mode or explicitly accept private raw storage",
                file=sys.stderr,
            )
            return 4
        wiki_root = resolve_wiki_root(args.wiki_root)
        inputs = [Path(item) for item in args.inputs]
        summary = catalog_sources(
            store.root,
            inputs,
            wiki_root=wiki_root,
            profile_id=args.profile,
            copy_raw=args.copy,
        )
        if args.json:
            print(
                json.dumps(
                    {
                        "scanned_files": summary.scanned_files,
                        "cataloged": summary.cataloged,
                        "copied": summary.copied,
                        "matched": summary.matched,
                        "skipped": summary.skipped,
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        print(render_catalog_summary(summary))
        return 0

    if args.source_vault_command == "list":
        records = load_records(store.root)
        if args.json:
            print(json.dumps([record.to_dict() for record in records], indent=2, sort_keys=True))
            return 0
        print(render_records(records))
        return 0

    raise ValueError(f"unknown source-vault command: {args.source_vault_command}")


def cmd_source_audit(args: argparse.Namespace) -> int:
    store = _private_store_from_args(args)
    store.init()

    if args.source_audit_command == "run":
        wiki_root = resolve_wiki_root(args.wiki_root)
        if wiki_root is None:
            print(
                "wiki root not configured. Run `health config wiki-root <wiki-root>` "
                "or pass `health source-audit run --wiki-root <path>`.",
                file=sys.stderr,
            )
            return 4
        result = audit_ingested_sources(
            store.root,
            wiki_root,
            profile_id=args.profile,
            focus=args.focus,
            extract=not args.no_extract,
            persist=not args.no_persist,
        )
        if args.json:
            print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
            return 0
        print(render_audit(result))
        return 0

    if args.source_audit_command == "report":
        report = latest_audit(store.root)
        if report is None:
            print("No source audit report found.")
            return 0
        if args.json:
            print(json.dumps(report, indent=2, sort_keys=True))
            return 0
        result = _source_audit_result_from_payload(report)
        print(render_audit(result))
        return 0

    raise ValueError(f"unknown source-audit command: {args.source_audit_command}")


def _source_audit_result_from_payload(payload: dict[str, object]):
    from llm_health.source_vault import SourceAuditResult

    data = dict(payload)
    audit_path = data.get("audit_path")
    if isinstance(audit_path, str) and audit_path:
        data["audit_path"] = Path(audit_path)
    else:
        data["audit_path"] = None
    return SourceAuditResult(**data)


def cmd_ingest_note(args: argparse.Namespace) -> int:
    store = _private_store_from_args(args)
    store.init()
    profile = _profile_for_store(args, store)
    observation = Observation(
        profile_id=profile,
        marker=args.marker,
        value=args.value,
        unit=args.unit,
        category=args.category,
        observed_on=args.observed_on
        or Observation(profile_id=profile, marker=args.marker).observed_on,
        flag=args.flag,
        reference_range=args.reference_range,
        comparator=args.comparator,
        specimen=args.specimen,
        interpretation=args.interpretation,
        source_id=args.source_id,
        note=args.note,
    )
    threshold = 0.0 if args.deep == "always" else 2.0 if args.deep == "none" else 0.60
    result = ReviewEngine(store, interest_threshold=threshold).review_new_observations(
        profile, [observation], persist=True
    )
    store.append_observation(observation)
    gaps = DiagnosticGapEngine().create_gaps(profile, [observation])
    for gap in gaps:
        store.append_diagnostic_gap(gap)

    print(f"Added observation: {observation.marker} ({observation.category}) for {profile}")
    print(
        f"Quick cards: {len(result.cards)} | diagnostic gaps: {len(gaps)} | "
        f"research jobs: {len(result.research_jobs)}"
    )
    for card in result.cards:
        print(f"- {card.title}: {card.summary}")
    for job in result.research_jobs:
        print(f"Research queued: {job.topic}")
    return 0


def cmd_sync_v2(args: argparse.Namespace) -> int:
    store = _private_store_from_args(args)
    store.init()
    profiles = ["rod", "cara"] if args.profile == "all" else [args.profile]
    threshold = 0.0 if args.deep == "always" else 2.0 if args.deep == "none" else 0.60
    total_obs = total_cards = total_gaps = total_jobs = 0
    for profile in profiles:
        result_meta, observations = import_latest_for_profile(args.wiki_root, profile)
        existing_observation_ids = {
            observation.observation_id for observation in store.observations(profile)
        }
        new_observations = [
            observation
            for observation in observations
            if observation.observation_id not in existing_observation_ids
        ]
        review = ReviewEngine(store, interest_threshold=threshold).review_new_observations(
            profile, new_observations, persist=True
        ) if new_observations else None
        for observation in observations:
            store.append_observation(observation)
        gaps = DiagnosticGapEngine().create_gaps(profile, new_observations)
        for gap in gaps:
            store.append_diagnostic_gap(gap)
        total_obs += len(observations)
        total_cards += len(review.cards) if review else 0
        total_gaps += len(gaps)
        total_jobs += len(review.research_jobs) if review else 0
        sources = ", ".join(result_meta.source_ids) if result_meta.source_ids else "none"
        print(
            f"{profile}: imported {result_meta.imported_count} latest observation(s) "
            f"from {result_meta.latest_date or 'no date'}; "
            f"new={len(new_observations)}; sources: {sources}"
        )
    print(
        f"sync-v2 complete: observations={total_obs}, quick_cards={total_cards}, "
        f"diagnostic_gaps={total_gaps}, research_jobs={total_jobs}"
    )
    return 0


def cmd_review(args: argparse.Namespace) -> int:
    store = _private_store_from_args(args)
    profile = _profile_for_store(args, store)
    cards = store.quick_review_cards(profile)[-args.limit :]
    if not cards:
        print("No quick-review cards found. Try ingesting a note or syncing data first.")
        return 0
    for card in cards:
        print(f"[{card.priority:.2f}] {card.title}")
        print(f"  {card.summary}")
        if card.triggers:
            print(f"  triggers: {', '.join(card.triggers)}")
    return 0


def cmd_self_report(args: argparse.Namespace) -> int:
    store = _private_store_from_args(args)
    store.init()
    profile = _profile_for_store(args, store)
    observed_on = (
        args.observed_on or Observation(profile_id=profile, marker=args.subject).observed_on
    )
    note = ContextNote(
        profile_id=profile,
        subject=args.subject,
        status=args.status,
        note=args.note,
        observed_on=observed_on,
        context_id=stable_id(
            "context", profile, args.subject.strip().lower(), args.status, observed_on, args.note
        ),
    )
    store.append_context_note(note)
    print(f"Recorded self-report context for {profile}: {note.subject} · {note.status}")
    print(f"  Date: {note.observed_on}")
    print(f"  Tags: {', '.join(note.tags)}")
    return 0


def cmd_context(args: argparse.Namespace) -> int:
    store = _private_store_from_args(args)
    profile = _profile_for_store(args, store)
    notes = store.context_notes(profile, subject=args.subject)
    notes.sort(key=lambda item: (item.observed_on, item.created_at), reverse=True)
    if not notes:
        print("No self-reported context notes found.")
        return 0
    for index, note in enumerate(notes[: args.limit]):
        if index:
            print()
        print(f"{note.profile_id} · {note.subject} · {note.status}")
        print(f"  Date: {note.observed_on}")
        print(f"  Tag: {', '.join(note.tags)}")
        if note.note:
            print(f"  Note: {note.note}")
    return 0


def _shared_household_value(raw: str) -> bool | None:
    if raw == "yes":
        return True
    if raw == "no":
        return False
    return None


def cmd_family(args: argparse.Namespace) -> int:
    store = _private_store_from_args(args)
    store.init()

    if args.family_command == "add":
        profile = _profile_for_store(args, store)
        relative = validate_profile_alias(args.relative)
        if not store.profile_exists(relative):
            raise PrivacyError(
                f"relative alias {relative!r} is not enrolled; run `health enroll` first"
            )
        relationship = FamilyRelationship(
            profile_id=profile,
            relative_id=relative,
            relation=args.relation,
            degree=args.degree,
            lineage=args.lineage,
            shared_household=_shared_household_value(args.shared_household),
            note=args.note,
        )
        store.append_family_relationship(relationship)
        print(
            f"Added relationship: {relationship.profile_id} -> {relationship.relative_id} "
            f"({relationship.relation})"
        )
        print(
            "  Degree: " + (
                str(relationship.degree)
                if relationship.degree is not None
                else "[unknown/non-biological]"
            )
        )
        print(f"  Tags: {', '.join(relationship.tags)}")
        return 0

    if args.family_command == "condition":
        profile = _profile_for_store(args, store)
        event = FamilyHistoryEvent(
            profile_id=profile,
            condition=args.condition,
            status=args.status,
            evidence=args.evidence,
            onset_age=args.onset_age,
            note=args.note,
            related_profile_ids=args.related,
        )
        store.append_family_history_event(event)
        print(f"Recorded family history: {event.profile_id} · {event.condition} · {event.status}")
        print(f"  Evidence: {event.evidence}")
        print(f"  Tags: {', '.join(event.tags)}")
        return 0

    if args.family_command == "tree":
        profile = _profile_for_store(args, store)
        print(render_family_tree(profile, store.family_relationships(profile)))
        return 0

    if args.family_command == "history":
        profile = validate_profile_alias(args.profile) if args.profile else None
        if profile and not store.profile_exists(profile):
            raise PrivacyError(f"profile alias {profile!r} is not enrolled")
        print(render_family_history(store.family_history_events(profile)))
        return 0

    if args.family_command == "risks":
        profile = _profile_for_store(args, store)
        notes = create_family_risk_notes(store, profile)
        if not args.no_persist:
            for note in notes:
                store.append_hereditary_risk_note(note)
        print(render_family_risks(notes, profile))
        if notes and not args.no_persist:
            print(f"\nstored_hereditary_risk_notes: {len(notes)}")
        return 0

    raise ValueError(f"unknown family command: {args.family_command}")


def _format_observation_value(observation: Observation) -> str:
    if observation.value is None:
        return "pending/non-numeric"
    value = f"{observation.value:g}"
    comparator = (observation.comparator or "").strip()
    if comparator in {"<", ">", "<=", ">="}:
        value = f"{comparator}{value}"
    if observation.unit:
        value = f"{value} {observation.unit}"
    return value


def cmd_result(args: argparse.Namespace) -> int:
    store = _private_store_from_args(args)
    profile = _profile_for_store(args, store)
    marker = args.marker.strip().lower()
    category = (args.category or "").strip().lower()
    matches = []
    for observation in store.observations(profile):
        marker_hit = marker in observation.marker.lower() or marker in observation.category.lower()
        category_hit = not category or category in observation.category.lower()
        if marker_hit and category_hit:
            matches.append(observation)
    matches.sort(key=lambda obs: (obs.observed_on, obs.marker), reverse=True)

    if not matches:
        print("No matching observations found.")
        return 0

    for index, observation in enumerate(matches[: args.limit]):
        if index:
            print()
        print(f"{observation.profile_id} · {observation.marker}")
        print(f"  Date: {observation.observed_on}")
        print(f"  Result: {_format_observation_value(observation)}")
        print(
            "  Normal range (source): "
            f"{observation.reference_range or '[not available in source row]'}"
        )
        if observation.flag:
            print(f"  Source flag: {observation.flag}")
        if observation.interpretation:
            print(f"  Source interpretation: {observation.interpretation}")
        if observation.specimen:
            print(f"  Specimen: {observation.specimen}")
    return 0


def cmd_close_gaps(args: argparse.Namespace) -> int:
    store = _private_store_from_args(args)
    profile = _profile_for_store(args, store)
    observations = store.observations(profile)
    gaps = DiagnosticGapEngine().create_gaps(profile, observations)
    for gap in gaps:
        store.append_diagnostic_gap(gap)
    if not gaps:
        print("No diagnostic gaps generated from current observations.")
        return 0
    for gap in gaps:
        print(f"[{gap.priority:.2f}] {gap.title} · {gap.gap_type}")
        print(f"  {gap.rationale}")
        for candidate in gap.candidates:
            print(f"  - {candidate.name} ({candidate.score():.2f}): {candidate.role}")
        if gap.context_questions:
            print("  context first:")
            for question in gap.context_questions:
                print(f"    - {question}")
    return 0


def _profile_record(store: LocalHealthStore, profile_id: str) -> EnrolledProfile:
    for profile in store.enrolled_profiles(include_defaults=True):
        if profile.profile_id == profile_id:
            return profile
    raise PrivacyError(f"profile alias {profile_id!r} is not enrolled; run `health enroll` first")


def _merged_gaps(store: LocalHealthStore, profile: str, observations: list[Observation]):
    merged = {gap.gap_id: gap for gap in store.diagnostic_gaps(profile)}
    for gap in DiagnosticGapEngine().create_gaps(profile, observations):
        merged.setdefault(gap.gap_id, gap)
    return list(merged.values())


def cmd_test_battery(args: argparse.Namespace) -> int:
    store = _private_store_from_args(args)
    store.init()
    profile_id = _profile_for_store(args, store)
    profile = _profile_record(store, profile_id)
    observations = store.observations(profile_id)
    gaps = _merged_gaps(store, profile_id, observations) if not args.no_gaps else []
    engine = TestBatteryEngine()
    battery = engine.generate(
        profile,
        observations,
        gaps,
        scope=args.scope,
        category=args.category,
        include_gaps=not args.no_gaps,
    )
    if args.queue_research:
        jobs = engine.research_jobs_for(battery)
        for job in jobs:
            store.append_research_job(job)
        print(f"Queued research jobs: {len(jobs)}")
        for job in jobs:
            print(f"- {job.topic}")
        print()
    print(render_test_battery(battery, sources=args.sources))
    return 0


def cmd_plan_research(args: argparse.Namespace) -> int:
    store = _private_store_from_args(args)
    profile = _profile_for_store(args, store)
    if args.topic:
        spec = ResearchWorkflowSpec(topic=args.topic)
        print(f"Research workflow: {spec.topic}")
        print(f"Lenses: {', '.join(spec.lenses)}")
        print("Retrieval ladder:")
        for step in spec.retrieval_ladder:
            print(f"- {step}")
        return 0
    jobs = store.research_jobs(profile)
    if not jobs:
        print("No research jobs queued.")
        return 0
    for job in jobs:
        print(f"[{job.priority:.2f}] {job.topic} · {job.status}")
        print(f"  {job.rationale}")
        if job.triggers:
            print(f"  triggers: {', '.join(job.triggers)}")
    return 0


def cmd_plugin_paths(args: argparse.Namespace) -> int:
    base = resources.files("llm_health.plugin_templates")
    paths = {
        "codex": base / "codex" / "llm-health",
        "claude": base / "claude" / "health",
        "opencode": base / "opencode" / "llm-health",
        "agents": base / "agents" / "AGENTS.health.md",
    }
    for kind, path in paths.items():
        if args.kind in {"all", kind}:
            print(f"{kind}: {path}")
    return 0


def _genomics_store_from_args(
    args: argparse.Namespace,
) -> tuple[LocalHealthStore, GenomicsStore, str]:
    store = _private_store_from_args(args)
    profile = _profile_for_store(args, store)
    genomics_store = GenomicsStore(store.root)
    genomics_store.init()
    return store, genomics_store, profile


def cmd_genomics(args: argparse.Namespace) -> int:
    command = args.genomics_command
    if command in {"ui", "gui"}:
        if args.host not in LOCAL_HOSTS and not args.allow_nonlocal:
            print(
                "refusing non-local genomics GUI bind without --allow-nonlocal; "
                "use --host 127.0.0.1 for local-only mode",
                file=sys.stderr,
            )
            return 4
        store = _private_store_from_args(args)
        store.init()
        if args.profile:
            profile = validate_profile_alias(args.profile)
            if not store.profile_exists(profile):
                raise PrivacyError(
                    f"profile alias {profile!r} is not enrolled; run `health enroll` first"
                )
            path = f"/genomics/ui?profile={profile}"
        else:
            path = "/genomics/ui"
        server = GenomicsGuiServer((args.host, args.port), store)
        url = f"http://{args.host}:{args.port}{path}"
        home_path = (
            f"/health/ui/?profile={profile}&section=genomics" if args.profile else "/health/ui/"
        )
        health_home = f"http://{args.host}:{args.port}{home_path}"
        print(f"starting llm-health genomics GUI on {url}")
        print(f"health_home: {health_home}")
        print("local_only: true")
        print(
            "privacy: browser filename/path are not posted; raw genetic text and dense "
            "genome-wide calls are not stored by default"
        )
        print("stop: press Ctrl-C")
        if not args.no_open:
            webbrowser.open(url)
            print("browser: opened")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped")
        finally:
            server.server_close()
        return 0

    health_store, genomics_store, profile = _genomics_store_from_args(args)
    if command == "import":
        if not args.accept_genetic_risk:
            print(
                "genetic risk acknowledgement required: rerun with --accept-genetic-risk",
                file=sys.stderr,
            )
            return 4
        input_path = Path(args.input)
        if not input_path.exists() or not input_path.is_file():
            print("genotype input was not found or is not a regular file", file=sys.stderr)
            return 4
        summary = import_raw_genotype_text_into_store(
            health_store,
            genomics_store,
            profile_id=profile,
            content=input_path.read_bytes(),
            source_kind=args.source_kind,
            clinical_grade=args.clinical_grade,
            accept_genetic_risk=args.accept_genetic_risk,
            store_dense_variants=args.store_dense_variants,
            accept_dense_genetic_storage=args.accept_dense_genetic_storage,
            include_research_markers=args.include_research_markers,
            run_crossref=True,
        )
        print("Matched genomic source")
        print(f"source_id: {summary.source.source_id}")
        print(f"source_kind: {summary.source.source_kind}")
        print(f"markers_scanned: {summary.source.marker_count}")
        print(f"stored_variant_scope: {summary.stored_variant_scope}")
        print(f"stored_variants: {summary.stored_variant_count}")
        print(f"call_rate: {summary.source.call_rate:.3f}")
        print("qc_notes: " + (", ".join(summary.qc.warnings) if summary.qc.warnings else "none"))
        print(f"stored_genomic_inferences: {summary.stored_inferences}")
        diagnostics = summary.match_diagnostics
        print(
            "research_marker_opt_in: "
            + ("yes" if diagnostics.get("include_research_markers") else "no")
        )
        print(
            "research_markers_checked: "
            f"{diagnostics.get('research_catalog_markers', 0)}"
        )
        print(
            "research_marker_matches: "
            f"{diagnostics.get('research_marker_matches', 0)}"
        )
        print(
            "research_effect_marker_matches: "
            f"{diagnostics.get('research_effect_marker_matches', 0)}"
        )
        print(
            "research_scopes: "
            f"{diagnostics.get('research_scope_summary', 'none')}"
        )
        print(
            "dyslexia_gwas_markers_checked: "
            f"{diagnostics.get('dyslexia_gwas_catalog_markers', 0)}"
        )
        print(
            "dyslexia_gwas_marker_matches: "
            f"{diagnostics.get('dyslexia_gwas_marker_matches', 0)}"
        )
        print(
            "dyslexia_gwas_effect_marker_matches: "
            f"{diagnostics.get('dyslexia_gwas_effect_marker_matches', 0)}"
        )
        print(
            "adhd_gwas_marker_matches: "
            f"{diagnostics.get('adhd_gwas_marker_matches', 0)}"
        )
        print(
            "autism_spectrum_gwas_marker_matches: "
            f"{diagnostics.get('autism_spectrum_gwas_marker_matches', 0)}"
        )
        print(f"research_match_note: {diagnostics.get('note', 'not reported')}")
        print(
            "privacy: raw genetic file path, browser filename, raw text, and dense genome-wide "
            "calls are not stored by default"
        )
        print("review_note: context only; confirm decision-relevant findings")
        return 0

    sources = genomics_store.sources(profile)
    variants = genomics_store.variants(profile)
    inferences = genomics_store.inferences(profile)

    if command == "status":
        print(render_sources(sources, len(variants), len(inferences)))
        return 0
    if command == "qc":
        qc_rows = [
            build_qc(source, genomics_store.variants(profile, source.source_id))
            for source in sources
        ]
        print(render_qc(qc_rows))
        return 0
    if command == "annotate":
        print(render_annotation_summary(variants))
        return 0
    if command == "crossref":
        include = {item.strip() for item in args.include.split(",") if item.strip()}
        cards = build_crossrefs_for_review(
            health_store,
            genomics_store,
            profile_id=profile,
            include=include,
        )
        stored = 0
        if not args.no_store:
            for card in cards:
                if genomics_store.upsert_inference(card):
                    stored += 1
        print(render_inferences(cards))
        print(f"stored_genomic_inferences: {stored}")
        return 0
    if command == "pgx":
        cards = build_crossrefs_for_review(
            health_store,
            genomics_store,
            profile_id=profile,
            include={"meds"},
        )
        pgx_cards = [card for card in cards if card.finding_type == "pgx"]
        for card in pgx_cards:
            genomics_store.upsert_inference(card)
        all_cards = genomics_store.inferences(profile) + pgx_cards
        dedup = {card.inference_id: card for card in all_cards}
        print(render_pgx(variants, list(dedup.values())))
        return 0
    if command == "confirm-list":
        print(render_confirm_list(inferences))
        return 0
    if command == "explain":
        print(render_explain(args.rsid, genomics_store.variants_by_rsid(profile, args.rsid)))
        return 0
    raise ValueError(f"unknown genomics command: {command}")

def cmd_capabilities(args: argparse.Namespace) -> int:
    kind = None if args.kind == "all" else args.kind
    if args.json:
        print(dumps_capabilities(kind))
        return 0
    print(render_capabilities(kind))
    return 0


def cmd_deid(args: argparse.Namespace) -> int:
    store = _private_store_from_args(args)
    text = load_text_input(args.input)
    result = deidentify_text(text, method=args.method)

    if args.deid_command == "extract":
        payload = {
            "backend": result.backend,
            "entity_count": result.entity_count,
            "entities": [entity.to_dict() for entity in result.entities],
        }
        output = (
            json.dumps(payload, indent=2, sort_keys=True)
            if args.json
            else render_extract(result)
        )
        print(output)
        return 0

    if args.deid_command == "preview":
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True) if args.json else result.text)
        return 0

    if args.deid_command == "apply":
        store.init()
        text_path, meta_path, staged = stage_deidentified_text(text, store.root, method=args.method)
        print(f"staged: {text_path.relative_to(store.root)}")
        print(f"metadata: {meta_path.relative_to(store.root)}")
        print(f"backend: {staged.backend}")
        print(f"entities: {staged.entity_count}")
        return 0

    raise ValueError(f"unknown deid command: {args.deid_command}")


def cmd_service(args: argparse.Namespace) -> int:
    if args.host not in LOCAL_HOSTS and not args.allow_nonlocal:
        print(
            "refusing non-local service bind without --allow-nonlocal; "
            "use --host 127.0.0.1 for local-only mode",
            file=sys.stderr,
        )
        return 4

    store = _private_store_from_args(args)
    store.init()

    if args.smoke:
        print(render_service_routes())
        print(f"host: {args.host}")
        print(f"port: {args.port}")
        print("status: smoke-ok")
        return 0

    try:
        print(f"starting llm-health local service on http://{args.host}:{args.port}")
        print(f"health_home: http://{args.host}:{args.port}/health/ui/")
        run_service(store, host=args.host, port=args.port)
        return 0
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 4


def cmd_operator(args: argparse.Namespace) -> int:
    store = _private_store_from_args(args)
    store.init()

    if args.operator_command == "draft":
        profile = _profile_for_store(args, store)
        draft = build_operator_draft(store, profile, args.intent)
        if not args.no_store:
            store.append_operator_draft(draft)
            store.append_audit_trace(
                trace_for_draft(draft, event="draft_created", status="draft")
            )
        output = (
            json.dumps(draft.to_dict(), indent=2, sort_keys=True)
            if args.json
            else render_operator_draft(draft)
        )
        print(output)
        return 0

    if args.operator_command == "list":
        profile = validate_profile_alias(args.profile) if args.profile else None
        drafts = store.operator_drafts(profile, status=args.status)
        drafts.sort(key=lambda item: item.created_at, reverse=True)
        if not drafts:
            print("No operator drafts found.")
            return 0
        for draft in drafts[: args.limit]:
            print(
                f"{draft.draft_id} · {draft.profile_id} · {draft.status} · "
                f"{draft.artifact_type} · {draft.intent}"
            )
        return 0

    if args.operator_command == "show":
        draft = store.operator_draft(args.draft_id)
        if draft is None:
            print("No operator draft found.", file=sys.stderr)
            return 4
        output = (
            json.dumps(draft.to_dict(), indent=2, sort_keys=True)
            if args.json
            else render_operator_draft(draft)
        )
        print(output)
        return 0

    if args.operator_command == "finalize":
        draft = store.operator_draft(args.draft_id)
        if draft is None:
            print("No operator draft found.", file=sys.stderr)
            return 4
        finalized = draft.with_status("finalized")
        store.append_operator_draft(finalized)
        store.append_audit_trace(
            trace_for_draft(finalized, event="draft_finalized", status="finalized")
        )
        print(f"finalized: {finalized.draft_id}")
        print(f"profile: {finalized.profile_id}")
        print(f"status: {finalized.status}")
        print(
            "note: lifecycle finalized only; downstream wiki/packet/protocol writes still need "
            "their own explicit command."
        )
        return 0

    if args.operator_command == "traces":
        profile = validate_profile_alias(args.profile) if args.profile else None
        traces = store.audit_traces(profile)
        traces.sort(key=lambda item: item.created_at, reverse=True)
        if not traces:
            print("No audit traces found.")
            return 0
        for index, trace in enumerate(traces[: args.limit]):
            if index:
                print()
            print(render_audit_trace(trace))
        return 0

    raise ValueError(f"unknown operator command: {args.operator_command}")


def cmd_specialists(args: argparse.Namespace) -> int:
    specs = list_specialists()
    if args.short:
        for spec in specs:
            print(f"{spec.specialist_id} · {spec.name}")
        return 0
    print(render_specialists(specs))
    return 0


def cmd_consult(args: argparse.Namespace) -> int:
    store = _private_store_from_args(args)
    store.init()
    profile_id = _profile_for_store(args, store)
    profile = _profile_record(store, profile_id)
    observations = store.observations(profile_id)
    gaps = _merged_gaps(store, profile_id, observations)
    context_notes = store.context_notes(profile_id)
    notes = create_specialist_notes(
        profile,
        observations,
        gaps,
        context_notes,
        specialist=args.specialist,
        topic=args.topic,
    )
    if not args.no_persist:
        for note in notes:
            store.append_specialist_note(note)
    print(render_specialist_notes(notes))
    if not args.no_persist:
        print(f"\nstored_specialist_notes: {len(notes)}")
    return 0


def cmd_specialist_notes(args: argparse.Namespace) -> int:
    store = _private_store_from_args(args)
    profile = _profile_for_store(args, store)
    specialist_id = resolve_specialist_id(args.specialist) if args.specialist else None
    notes = store.specialist_notes(profile, specialist_id=specialist_id)
    notes.sort(key=lambda item: item.created_at, reverse=True)
    print(render_specialist_notes(notes[: args.limit]))
    return 0


def cmd_least_harm(args: argparse.Namespace) -> int:
    _private_store_from_args(args)
    option = LeastHarmEngine().watchful_waiting_option(args.target)
    print(f"{option.option_type}: {option.target}")
    print(option.rationale)
    print("Track: " + ", ".join(option.track))
    print("Escalate if: " + ", ".join(option.escalate_if))
    return 0


def cmd_med_review(args: argparse.Namespace) -> int:
    _private_store_from_args(args)
    profile = validate_profile_alias(args.profile)
    review = LeastHarmEngine().medication_collateral_review(
        profile, args.active, args.indication
    )
    print(f"Medication collateral review: {review.active_or_class}")
    print(f"Indication: {review.indication}")
    print("Collateral lanes: " + ", ".join(review.collateral_damage))
    print("Avoidability questions:")
    for question in review.avoidability_questions:
        print(f"- {question}")
    return 0


def cmd_protocol_review(args: argparse.Namespace) -> int:
    _private_store_from_args(args)
    profile = validate_profile_alias(args.profile)
    review = LeastHarmEngine().preventive_protocol_review(profile, args.target)
    print(f"Preventive protocol review: {review.target}")
    print("Conclusion options: " + ", ".join(review.conclusion_options))
    print("Benefit questions:")
    for question in review.benefit_questions:
        print(f"- {question}")
    print("Harm questions:")
    for question in review.harm_questions:
        print(f"- {question}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        print(render_welcome())
        return 0
    commands = {
        "doctor": cmd_doctor,
        "init": cmd_init,
        "enroll": cmd_enroll,
        "profiles": cmd_profiles,
        "welcome": cmd_welcome,
        "data-wishlist": cmd_data_wishlist,
        "dr-visit": cmd_dr_visit,
        "config": cmd_config,
        "ui": cmd_ui,
        "report": cmd_report,
        "archive": cmd_archive,
        "source-vault": cmd_source_vault,
        "source-audit": cmd_source_audit,
        "agreement": cmd_agreement,
        "ingest-note": cmd_ingest_note,
        "sync-v2": cmd_sync_v2,
        "review": cmd_review,
        "self-report": cmd_self_report,
        "context": cmd_context,
        "family": cmd_family,
        "result": cmd_result,
        "close-gaps": cmd_close_gaps,
        "test-battery": cmd_test_battery,
        "plan-research": cmd_plan_research,
        "plugin-paths": cmd_plugin_paths,
        "genomics": cmd_genomics,
        "capabilities": cmd_capabilities,
        "deid": cmd_deid,
        "service": cmd_service,
        "operator": cmd_operator,
        "specialists": cmd_specialists,
        "consult": cmd_consult,
        "specialist-notes": cmd_specialist_notes,
        "least-harm": cmd_least_harm,
        "med-review": cmd_med_review,
        "protocol-review": cmd_protocol_review,
    }
    try:
        return commands[args.command](args)
    except RiskAgreementRequired as exc:
        print(f"agreement required: {exc}", file=sys.stderr)
        return 3
    except PrivacyError as exc:
        print(f"privacy error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
