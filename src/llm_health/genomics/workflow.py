from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from llm_health.core.privacy import PrivacyError, validate_profile_alias
from llm_health.stores import LocalHealthStore

from .crossref import build_cross_references, effect_allele_count
from .importers import parse_raw_genotype_text
from .knowledge import MARKERS, MATCHABLE_MARKERS, MarkerKnowledge, markers_for_matching
from .models import GenomicInference, GenomicQC, GenomicSource, VariantCall
from .patient_summary import build_patient_summary, inference_payload_with_patient_summary
from .qc import build_qc
from .store import GenomicsStore


@dataclass(frozen=True)
class GenomicsImportSummary:
    source: GenomicSource
    qc: GenomicQC
    stored_inferences: int
    inferences: list[GenomicInference]
    stored_variant_scope: str
    stored_variant_count: int
    match_diagnostics: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        source = self.source.to_dict()
        source["call_rate"] = self.source.call_rate
        return {
            "source": source,
            "qc": self.qc.to_dict(),
            "stored_variant_scope": self.stored_variant_scope,
            "stored_variant_count": self.stored_variant_count,
            "stored_inferences": self.stored_inferences,
            "match_diagnostics": self.match_diagnostics,
            "inferences": [
                inference_payload_with_patient_summary(inference)
                for inference in self.inferences
            ],
            "patient_summary": build_patient_summary(
                profile_id=self.source.profile_id,
                source_count=1,
                marker_count=self.stored_variant_count,
                qc_rows=[self.qc],
                cards=self.inferences,
            ),
            "privacy": (
                "raw genetic text, file path, browser filename, and dense genome-wide calls "
                "are not stored by default"
            ),
            "notice": "genomic artifacts are context notes; confirm decision-relevant findings",
        }


def matched_allowlist_variants(
    variants,
    *,
    marker_catalog: dict[str, MarkerKnowledge] | None = None,
):
    """Return sparse, called variants that can drive bundled SNP findings."""

    markers = marker_catalog or MATCHABLE_MARKERS
    return [
        variant
        for variant in variants
        if variant.is_called and variant.rsid in markers
    ]


def _research_scope_key(knowledge: MarkerKnowledge) -> str:
    return knowledge.match_scope or knowledge.topic or "research_trait"


def _research_scope_rollup(
    scope_counts: dict[str, dict[str, int]],
    prefix: str,
) -> dict[str, int]:
    matched = {
        scope: counts for scope, counts in scope_counts.items() if scope.startswith(prefix)
    }
    return {
        "catalog_markers": sum(counts["catalog_markers"] for counts in matched.values()),
        "marker_matches": sum(counts["marker_matches"] for counts in matched.values()),
        "effect_marker_matches": sum(
            counts["effect_marker_matches"] for counts in matched.values()
        ),
        "effect_alleles": sum(counts["effect_alleles"] for counts in matched.values()),
    }


def match_diagnostics_for_import(
    variants: list[VariantCall],
    *,
    include_research_markers: bool,
) -> dict[str, Any]:
    """Return privacy-safe matching diagnostics for opt-in research marker lists."""

    research_markers = {
        rsid: knowledge for rsid, knowledge in MARKERS.items() if knowledge.is_research
    }
    scope_markers: dict[str, dict[str, MarkerKnowledge]] = {}
    for rsid, knowledge in research_markers.items():
        scope_markers.setdefault(_research_scope_key(knowledge), {})[rsid] = knowledge
    scope_counts = {
        scope: {
            "catalog_markers": len(markers),
            "marker_matches": 0,
            "effect_marker_matches": 0,
            "effect_alleles": 0,
        }
        for scope, markers in sorted(scope_markers.items())
    }
    called_variants = [variant for variant in variants if variant.is_called]
    if include_research_markers:
        research_variants = [
            variant for variant in called_variants if variant.rsid in research_markers
        ]
    else:
        research_variants = []

    research_effect_marker_matches = 0
    research_effect_alleles = 0
    for variant in research_variants:
        knowledge = research_markers[variant.rsid]
        scope = _research_scope_key(knowledge)
        count = effect_allele_count(variant, knowledge)
        scope_counts[scope]["marker_matches"] += 1
        scope_counts[scope]["effect_alleles"] += count
        research_effect_alleles += count
        if count > 0:
            scope_counts[scope]["effect_marker_matches"] += 1
            research_effect_marker_matches += 1

    dyslexia_rollup = _research_scope_rollup(scope_counts, "dyslexia_gwas")
    adhd_rollup = _research_scope_rollup(scope_counts, "adhd_gwas")
    autism_rollup = _research_scope_rollup(scope_counts, "autism_spectrum_gwas")

    matched_scope_summary = [
        (
            f"{scope}: {counts['marker_matches']} marker row(s), "
            f"{counts['effect_marker_matches']} effect-allele row(s), "
            f"{counts['effect_alleles']} effect allele(s)"
        )
        for scope, counts in scope_counts.items()
        if counts["marker_matches"] > 0
    ]
    scope_summary = "; ".join(matched_scope_summary) if matched_scope_summary else "none"

    if not include_research_markers:
        note = (
            "Research marker lists were not included. Check the opt-in box or pass "
            "--include-research-markers to run dyslexia, ADHD, and autism-spectrum "
            "GWAS matching."
        )
    elif not research_variants:
        note = (
            "Research marker matching was enabled; no called rsIDs overlapped the bundled "
            "dyslexia, ADHD, or autism-spectrum GWAS lead-SNP lists."
        )
    elif not research_effect_marker_matches:
        note = (
            "Research marker matching was enabled; research GWAS lead rsIDs were present, "
            "but no listed effect alleles were observed, so no aggregate research card "
            "was generated."
        )
    else:
        note = (
            "Research marker matching was enabled; lead-SNP effect-allele matches can "
            "generate separate aggregate research-context cards."
        )

    return {
        "include_research_markers": include_research_markers,
        "research_catalog_markers": len(research_markers),
        "research_marker_matches": len(research_variants),
        "research_effect_marker_matches": research_effect_marker_matches,
        "research_effect_alleles": research_effect_alleles,
        "research_scope_matches": scope_counts,
        "research_scope_summary": scope_summary,
        "dyslexia_gwas_catalog_markers": dyslexia_rollup["catalog_markers"],
        "dyslexia_gwas_marker_matches": dyslexia_rollup["marker_matches"],
        "dyslexia_gwas_effect_marker_matches": dyslexia_rollup["effect_marker_matches"],
        "dyslexia_gwas_effect_alleles": dyslexia_rollup["effect_alleles"],
        "adhd_gwas_catalog_markers": adhd_rollup["catalog_markers"],
        "adhd_gwas_marker_matches": adhd_rollup["marker_matches"],
        "adhd_gwas_effect_marker_matches": adhd_rollup["effect_marker_matches"],
        "adhd_gwas_effect_alleles": adhd_rollup["effect_alleles"],
        "autism_spectrum_gwas_catalog_markers": autism_rollup["catalog_markers"],
        "autism_spectrum_gwas_marker_matches": autism_rollup["marker_matches"],
        "autism_spectrum_gwas_effect_marker_matches": autism_rollup[
            "effect_marker_matches"
        ],
        "autism_spectrum_gwas_effect_alleles": autism_rollup["effect_alleles"],
        "note": note,
    }


def import_raw_genotype_text_into_store(
    health_store: LocalHealthStore,
    genomics_store: GenomicsStore,
    *,
    profile_id: str,
    content: str | bytes,
    source_kind: str = "auto",
    clinical_grade: bool = False,
    accept_genetic_risk: bool = False,
    store_dense_variants: bool = False,
    accept_dense_genetic_storage: bool = False,
    run_crossref: bool = True,
    include: set[str] | None = None,
    include_research_markers: bool = False,
) -> GenomicsImportSummary:
    """Run SNP matching against raw genotype text and store sparse findings by default."""

    if not accept_genetic_risk:
        raise PrivacyError("genetic risk acknowledgement required")
    if store_dense_variants and not accept_dense_genetic_storage:
        raise PrivacyError("dense genetic storage requires --accept-dense-genetic-storage")
    profile = validate_profile_alias(profile_id)
    health_store.init()
    if not health_store.profile_exists(profile):
        raise PrivacyError(f"profile alias {profile!r} is not enrolled; run `health enroll` first")
    genomics_store.init()

    result = parse_raw_genotype_text(
        content,
        profile_id=profile,
        source_kind=source_kind,
        clinical_grade=clinical_grade,
    )
    qc = build_qc(result.source, result.variants)
    match_markers = (
        MATCHABLE_MARKERS
        if not include_research_markers
        else markers_for_matching(include_research=True)
    )
    stored_variants = (
        result.variants
        if store_dense_variants
        else matched_allowlist_variants(result.variants, marker_catalog=match_markers)
    )
    match_diagnostics = match_diagnostics_for_import(
        stored_variants,
        include_research_markers=include_research_markers,
    )
    stored_scope = "dense_genome_wide_calls" if store_dense_variants else "matched_allowlist_only"
    source = replace(
        result.source,
        stored_variant_scope=stored_scope,
        stored_variant_count=len(stored_variants),
    )
    genomics_store.upsert_source(source)
    genomics_store.replace_variants(source.source_id or "", stored_variants)

    inferences: list[GenomicInference] = []
    stored = 0
    if run_crossref:
        inferences = build_cross_references(
            health_store,
            genomics_store,
            profile,
            include=include or {"labs", "meds", "family"},
        )
        for inference in inferences:
            if genomics_store.upsert_inference(inference):
                stored += 1
    return GenomicsImportSummary(
        source=source,
        qc=qc,
        stored_inferences=stored,
        inferences=inferences,
        stored_variant_scope=stored_scope,
        stored_variant_count=len(stored_variants),
        match_diagnostics=match_diagnostics,
    )


def run_crossrefs_into_store(
    health_store: LocalHealthStore,
    genomics_store: GenomicsStore,
    *,
    profile_id: str,
    include: set[str] | None = None,
) -> dict[str, Any]:
    profile = _validated_genomics_profile(health_store, genomics_store, profile_id)
    cards = build_cross_references(
        health_store,
        genomics_store,
        profile,
        include=include or {"labs", "meds", "family"},
    )
    stored = 0
    for card in cards:
        if genomics_store.upsert_inference(card):
            stored += 1
    return {
        "profile_id": profile,
        "count": len(cards),
        "stored_inferences": stored,
        "cards": [inference_payload_with_patient_summary(card) for card in cards],
        "patient_summary": build_patient_summary(
            profile_id=profile,
            source_count=len(genomics_store.sources(profile)),
            marker_count=len(genomics_store.variants(profile)),
            qc_rows=[
                build_qc(source, genomics_store.variants(profile, source.source_id))
                for source in genomics_store.sources(profile)
            ],
            cards=cards,
        ),
        "notice": "genomic cards are context notes; confirm decision-relevant findings",
    }


def build_crossrefs_for_review(
    health_store: LocalHealthStore,
    genomics_store: GenomicsStore,
    *,
    profile_id: str,
    include: set[str] | None = None,
) -> list[GenomicInference]:
    """Validate stores/profile, then build deterministic genomics review cards."""

    profile = _validated_genomics_profile(health_store, genomics_store, profile_id)
    return build_cross_references(
        health_store,
        genomics_store,
        profile,
        include=include or {"labs", "meds", "family"},
    )


def _validated_genomics_profile(
    health_store: LocalHealthStore,
    genomics_store: GenomicsStore,
    profile_id: str,
) -> str:
    profile = validate_profile_alias(profile_id)
    health_store.init()
    if not health_store.profile_exists(profile):
        raise PrivacyError(f"profile alias {profile!r} is not enrolled; run `health enroll` first")
    genomics_store.init()
    return profile
