from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from llm_health.core.privacy import PrivacyError, validate_profile_alias
from llm_health.stores import LocalHealthStore

from .crossref import build_cross_references
from .importers import parse_raw_genotype_text
from .knowledge import MATCHABLE_MARKERS
from .models import GenomicInference, GenomicQC, GenomicSource
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

    def to_dict(self) -> dict[str, Any]:
        source = self.source.to_dict()
        source["call_rate"] = self.source.call_rate
        return {
            "source": source,
            "qc": self.qc.to_dict(),
            "stored_variant_scope": self.stored_variant_scope,
            "stored_variant_count": self.stored_variant_count,
            "stored_inferences": self.stored_inferences,
            "inferences": [inference.to_dict() for inference in self.inferences],
            "privacy": (
                "raw genetic text, file path, browser filename, and dense genome-wide calls "
                "are not stored by default"
            ),
            "notice": "genomic artifacts are context only, not diagnosis or prescribing",
        }


def matched_allowlist_variants(variants):
    """Return sparse, called variants that can drive bundled SNP findings."""

    return [
        variant
        for variant in variants
        if variant.is_called and variant.rsid in MATCHABLE_MARKERS
    ]


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
    stored_variants = (
        result.variants if store_dense_variants else matched_allowlist_variants(result.variants)
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
    )


def run_crossrefs_into_store(
    health_store: LocalHealthStore,
    genomics_store: GenomicsStore,
    *,
    profile_id: str,
    include: set[str] | None = None,
) -> dict[str, Any]:
    profile = validate_profile_alias(profile_id)
    health_store.init()
    if not health_store.profile_exists(profile):
        raise PrivacyError(f"profile alias {profile!r} is not enrolled; run `health enroll` first")
    genomics_store.init()
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
        "cards": [card.to_dict() for card in cards],
        "notice": "genomic cards are review artifacts, not diagnosis or prescribing",
    }
