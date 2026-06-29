from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Literal

CapabilityKind = Literal["core", "data", "review", "research", "ui", "agent", "privacy", "service"]


@dataclass(frozen=True)
class Capability:
    """Public, alias-safe feature registry row for docs, agents, and UIs."""

    capability_id: str
    name: str
    kind: CapabilityKind
    command: str
    summary: str
    module: str
    privacy: str = "alias-only local artifacts"
    external_calls: str = "none"
    dependencies: list[str] = field(default_factory=list)
    status: str = "stable"
    tests: list[str] = field(default_factory=list)
    docs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


CAPABILITIES: tuple[Capability, ...] = (
    Capability(
        capability_id="doctor",
        name="Runtime doctor",
        kind="core",
        command="health doctor",
        summary="Check resolved HUB, config, agreement, Python, and package status.",
        module="llm_health.cli:cmd_doctor",
        privacy="prints local config/HUB status only",
        tests=["tests/test_cli.py::CliTests::test_doctor"],
        docs=["README.md", "docs/hub-setup.md"],
    ),
    Capability(
        capability_id="agreement",
        name="Own-risk agreement",
        kind="core",
        command="health agreement show/accept",
        summary="Gate health-facing commands behind an explicit local own-risk acknowledgement.",
        module="llm_health.agreement",
        privacy="stores agreement metadata only",
        tests=["tests/test_cli.py::CliTests::test_agreement_required_and_acceptance"],
        docs=["docs/own-risk-agreement.md"],
    ),
    Capability(
        capability_id="onboarding",
        name="Welcome, wishlist, Dr Visit",
        kind="core",
        command="health welcome; health data-wishlist; health dr-visit",
        summary="Alias-only enrollment prompts, import wishlist, and cadence-aware fact finding.",
        module="llm_health.onboarding",
        privacy="prompts only; no raw dumps stored",
        tests=[
            "tests/test_cli.py::CliTests::test_first_run_welcome_and_data_prompts",
            "tests/test_cli.py::CliTests::test_dr_visit_cadence_questions",
        ],
        docs=["docs/onboarding-and-dr-visit.md"],
    ),
    Capability(
        capability_id="profiles",
        name="Alias enrollment",
        kind="data",
        command="health enroll; health profiles",
        summary=(
            "Store alias-only profiles with year/month precision, role labels, "
            "and no legal identifiers."
        ),
        module="llm_health.core.models:EnrolledProfile",
        privacy="alias-only; no full birth dates or legal names",
        tests=["tests/test_cli.py::CliTests::test_enroll_profiles_flow"],
        docs=["README.md", "docs/hub-setup.md"],
    ),
    Capability(
        capability_id="ingest-note",
        name="Manual observation ingest",
        kind="data",
        command="health ingest-note",
        summary="Append one de-identified observation and trigger quick review plus gap checks.",
        module="llm_health.cli:cmd_ingest_note",
        privacy="source paths, raw filenames, emails blocked before storage",
        tests=[
            "tests/test_cli.py::CliTests::test_ingest_review_gap_flow",
            "tests/test_cli.py::CliTests::test_cli_privacy_error",
        ],
        docs=["docs/event-driven-review.md", "docs/diagnostic-gap-layer.md"],
    ),
    Capability(
        capability_id="sync-v2",
        name="Assessment v2 sync",
        kind="data",
        command="health sync-v2",
        summary="Import de-identified canonical Assessment v2 rows into the private HUB.",
        module="llm_health.assessment_v2.bridge",
        privacy="reads de-identified exports; blocks raw paths in stored rows",
        dependencies=["llm-health[v2-core]"],
        tests=["tests/test_v2_bridge.py"],
        docs=["docs/v2-repackaging.md"],
    ),
    Capability(
        capability_id="review",
        name="Quick review cards",
        kind="review",
        command="health review; health result",
        summary="Show latest observations with source ranges and event-driven quick review cards.",
        module="llm_health.engine.review",
        privacy="alias-scoped private HUB reads",
        tests=["tests/test_cli.py::CliTests::test_ingest_review_gap_flow"],
        docs=["docs/event-driven-review.md"],
    ),
    Capability(
        capability_id="context",
        name="Self-reported context",
        kind="data",
        command="health self-report; health context",
        summary=(
            "Persist user-corrected context as CONTEXT artifacts instead of "
            "numeric observations."
        ),
        module="llm_health.core.models:ContextNote",
        privacy="alias-only prose; privacy guard blocks identifiers",
        tests=["tests/test_cli.py::CliTests::test_self_report_context_flow"],
        docs=["docs/onboarding-and-dr-visit.md"],
    ),
    Capability(
        capability_id="family-history",
        name="Family history and kinship graph",
        kind="data",
        command="health family add/condition/tree/history/risks",
        summary=(
            "Track alias-only relationships, family conditions, household context, "
            "and hereditary-pattern risk notes."
        ),
        module="llm_health.family",
        privacy="alias-only family graph; no legal names or full birth dates",
        status="scaffold",
        tests=["tests/test_cli.py::CliTests::test_family_history_tree_and_risk_notes"],
        docs=["docs/family-history.md", "docs/recipes.md"],
    ),

    Capability(
        capability_id="genomics",
        name="Genomics and SNP cross-reference layer",
        kind="data",
        command="health genomics import/status/qc/annotate/crossref/pgx",
        summary=(
            "Import local raw genotype files by fingerprint, run QC, summarize bundled "
            "SNP annotations, and create confirmation-first lab/med/family review cards."
        ),
        module="llm_health.genomics",
        privacy=(
            "raw genetic file paths are never stored; dense calls stay local under the "
            "private HUB and are excluded from normal archives"
        ),
        external_calls="none; bundled annotation scaffold only",
        status="scaffold",
        tests=["tests/test_genomics.py"],
        docs=["docs/genomics.md", "docs/feature-map.md"],
    ),
    Capability(
        capability_id="diagnostic-gaps",
        name="Gap and test-candidate layer",
        kind="review",
        command="health close-gaps; health test-battery",
        summary="Create DATA_GAP and TEST_CANDIDATE cards with context-first questions.",
        module="llm_health.engine.gaps; llm_health.test_batteries",
        privacy="alias-scoped generated cards",
        tests=["tests/test_cli.py::CliTests::test_test_battery_foundation_and_gap_awareness"],
        docs=["docs/diagnostic-gap-layer.md", "docs/test-battery-layer.md"],
    ),
    Capability(
        capability_id="specialists",
        name="Category-agent consults",
        kind="research",
        command="health specialists; health consult; health specialist-notes",
        summary="Run broad category agents and persist SPECIALIST_NOTE artifacts.",
        module="llm_health.specialists",
        privacy="alias-scoped notes; no raw dumps or source paths",
        tests=[
            "tests/test_cli.py::CliTests::test_specialists_and_internal_medicine_consult",
            "tests/test_cli.py::CliTests::test_auto_consult_routes_gap_specialists",
        ],
        docs=["docs/specialist-agents.md"],
    ),
    Capability(
        capability_id="least-harm",
        name="Least-harm reviews",
        kind="review",
        command="health least-harm; health med-review; health protocol-review",
        summary=(
            "Draft low-intervention, medication-collateral, and "
            "preventive-protocol review cards."
        ),
        module="llm_health.engine.least_harm",
        privacy="review text only; no autonomous treatment instructions",
        tests=["tests/test_least_harm.py"],
        docs=["docs/therapeutic-minimalism.md", "docs/collateral-damage-ledger.md"],
    ),
    Capability(
        capability_id="research-plan",
        name="Research queue planning",
        kind="research",
        command="health plan-research",
        summary="Show queued jobs and the paper/product research retrieval contract.",
        module="llm_health.research.workflow",
        privacy="queued topics are alias-scoped and de-identified",
        external_calls="none by default; future research adapters are explicit",
        tests=["tests/test_research_workflow.py"],
        docs=["docs/research-lenses.md"],
    ),
    Capability(
        capability_id="ui",
        name="Assessment board export",
        kind="ui",
        command="health ui",
        summary=(
            "Regenerate the static local Assessment board from de-identified "
            "canonical exports."
        ),
        module="llm_health.assessment_v2.export.v2_web",
        privacy="writes local static files under the HUB; alias-only data.js contract",
        dependencies=["llm-health[v2-core]"],
        tests=["tests/test_cli.py::CliTests::test_ui_exports_static_dashboard_with_configured_wiki_root"],
        docs=["docs/v2-repackaging.md", "docs/agentic-ui-design-packet.md"],
    ),
    Capability(
        capability_id="reports",
        name="Doctor/family PDF reports",
        kind="ui",
        command="health report --profile <alias> --audience doctor|family|both",
        summary=(
            "Generate nice local PDF exports with doctor-facing clinician briefs "
            "and family-facing plain-language summaries."
        ),
        module="llm_health.reports",
        privacy="dependency-free PDF writer; alias-only content; no raw source paths/filenames",
        tests=[
            "tests/test_reports.py",
            "tests/test_cli.py::CliTests::test_report_exports_doctor_and_family_pdfs",
        ],
        docs=["README.md", "docs/reports.md"],
    ),
    Capability(
        capability_id="agent-templates",
        name="Agent plugin templates",
        kind="agent",
        command="health plugin-paths",
        summary="Expose packaged Claude, Codex, OpenCode, and portable AGENTS templates.",
        module="llm_health.plugin_templates",
        privacy="templates only; no private data included",
        tests=["tests/test_cli.py::CliTests::test_plugin_paths_cover_agent_runtimes"],
        docs=["docs/plugin-distribution.md"],
    ),
    Capability(
        capability_id="capabilities",
        name="Capability registry",
        kind="core",
        command="health capabilities",
        summary="Print machine-readable and human-readable feature maps for agents and users.",
        module="llm_health.registry",
        privacy="public metadata only",
        tests=["tests/test_cli.py::CliTests::test_capabilities_registry"],
        docs=["docs/feature-map.md", "docs/recipes.md"],
    ),
    Capability(
        capability_id="source-vault-audit",
        name="Source vault and source audit",
        kind="privacy",
        command="health source-vault; health source-audit",
        summary=(
            "Catalog optional raw originals by hash, map them to de-identified source IDs, "
            "and audit medium-confidence rows with multipass extraction summaries."
        ),
        module="llm_health.source_vault",
        privacy=(
            "manifest stores no raw paths or filenames; copied raw blobs are hash-named and "
            "excluded from normal archives"
        ),
        dependencies=["pdftotext optional", "llm-health[source-audit] optional"],
        status="scaffold",
        tests=[
            "tests/test_source_vault.py",
            "tests/test_cli.py::CliTests::test_source_vault_and_audit_cli",
        ],
        docs=["docs/source-vault-audit.md"],
    ),
    Capability(
        capability_id="archive",
        name="Compressed HUB archives",
        kind="privacy",
        command="health archive create/list/verify",
        summary="Create privacy-scanned compressed snapshots of the resolved local HUB.",
        module="llm_health.archive",
        privacy="allowlisted HUB files only; raw-source-looking files are skipped or strict-failed",
        tests=[
            "tests/test_archive.py",
            "tests/test_cli.py::CliTests::test_archive_create_list_verify_and_privacy_skip",
        ],
        docs=["docs/archives.md", "docs/recipes.md"],
    ),
    Capability(
        capability_id="deid",
        name="De-identification adapter",
        kind="privacy",
        command="health deid extract/preview/apply",
        summary="Preview and stage de-identified text before anything enters the private HUB.",
        module="llm_health.deid",
        privacy="raw input is redacted in memory; apply writes redacted staging text only",
        status="scaffold",
        tests=[
            "tests/test_cli.py::CliTests::test_deid_preview_extract_and_apply",
            "tests/test_privacy.py::PrivacyTests::test_deidentify_text_removes_common_identifiers",
        ],
        docs=["docs/feature-map.md", "docs/recipes.md"],
    ),
    Capability(
        capability_id="local-service",
        name="Local service skeleton",
        kind="service",
        command="health service --local",
        summary="Start or smoke-test a localhost-only API shell for future GUI/chat integrations.",
        module="llm_health.service",
        privacy="local bind by default; no remote exposure unless explicitly allowed",
        dependencies=["llm-health[service]"],
        status="scaffold",
        tests=["tests/test_cli.py::CliTests::test_service_smoke_routes"],
        docs=["docs/feature-map.md", "docs/recipes.md"],
    ),
    Capability(
        capability_id="operator-runtime",
        name="Visible operator runtime",
        kind="agent",
        command="health operator draft/list/show/finalize/traces",
        summary=(
            "Turn an alias-safe intent into a visible plan, draft artifact, "
            "explicit finalize step, and fingerprint-first audit trace."
        ),
        module="llm_health.operator_runtime",
        privacy="stores alias-safe intent, counts, plans, statuses, and fingerprints only",
        status="scaffold",
        tests=["tests/test_cli.py::CliTests::test_operator_runtime_draft_finalize_trace"],
        docs=["docs/operator-runtime.md", "docs/recipes.md"],
    ),
)


def iter_capabilities(kind: str | None = None) -> tuple[Capability, ...]:
    if kind is None or kind == "all":
        return CAPABILITIES
    needle = kind.strip().lower()
    return tuple(capability for capability in CAPABILITIES if capability.kind == needle)


def capabilities_json(kind: str | None = None) -> list[dict[str, object]]:
    return [capability.to_dict() for capability in iter_capabilities(kind)]


def render_capabilities(kind: str | None = None) -> str:
    rows = list(iter_capabilities(kind))
    if not rows:
        return f"No capabilities found for kind: {kind}"

    lines = ["# llm-health capabilities"]
    if kind and kind != "all":
        lines.append(f"kind: {kind}")
    lines.append("")
    lines.append("id | kind | command | privacy | deps | external")
    lines.append("--- | --- | --- | --- | --- | ---")
    for capability in rows:
        deps = ", ".join(capability.dependencies) if capability.dependencies else "base"
        lines.append(
            " | ".join(
                [
                    capability.capability_id,
                    capability.kind,
                    capability.command,
                    capability.privacy,
                    deps,
                    capability.external_calls,
                ]
            )
        )
    lines.append("")
    lines.append("Use `health capabilities --json` for agent-readable metadata.")
    return "\n".join(lines)


def dumps_capabilities(kind: str | None = None) -> str:
    return json.dumps(capabilities_json(kind), indent=2, sort_keys=True)
