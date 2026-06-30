from __future__ import annotations

from .knowledge import MARKERS
from .models import GenomicInference, GenomicSource, VariantCall


def render_sources(sources: list[GenomicSource], variant_count: int, inference_count: int) -> str:
    lines = ["# Genomics status", ""]
    lines.append(f"sources: {len(sources)}")
    lines.append(f"variants: {variant_count}")
    lines.append(f"inferences: {inference_count}")
    lines.append("genetic_data_notice: context only; not diagnostic; confirm before action")
    lines.append("")
    for source in sources:
        lines.append(f"source_id: {source.source_id}")
        lines.append(f"kind: {source.source_kind}")
        lines.append(f"assay: {source.assay_type}")
        lines.append(f"genome_build: {source.genome_build}")
        lines.append(f"markers: {source.marker_count}")
        lines.append(f"stored_variant_scope: {source.stored_variant_scope}")
        lines.append(f"stored_variants: {source.stored_variant_count}")
        lines.append(f"call_rate: {source.call_rate:.3f}")
        lines.append(f"clinical_grade: {str(source.clinical_grade).lower()}")
        lines.append("")
    return "\n".join(lines).rstrip()


def render_inferences(inferences: list[GenomicInference]) -> str:
    lines = ["# Genomics cross-reference review", ""]
    if not inferences:
        lines.append("No genomic cross-reference cards found.")
        return "\n".join(lines)
    for item in inferences:
        lines.append(f"## {item.title}")
        lines.append(f"finding_type: {item.finding_type}")
        lines.append(f"confidence: {item.confidence}")
        lines.append(f"confirmation_required: {str(item.required_confirmation).lower()}")
        lines.append(f"discussion_target: {item.discussion_target}")
        lines.append("tags: " + ", ".join(item.tags))
        lines.append(item.summary)
        lines.append("Evidence:")
        for evidence in item.evidence:
            lines.append(f"- {evidence}")
        lines.append("")
    lines.append("This is not medical advice, diagnosis, prescribing, or test ordering.")
    return "\n".join(lines).rstrip()


def render_explain(rsid: str, variants: list[VariantCall]) -> str:
    key = rsid.strip().lower()
    knowledge = MARKERS.get(key)
    lines = [f"# Genomics explain {key}", ""]
    if knowledge:
        lines.append(f"gene: {knowledge.gene}")
        lines.append(f"label: {knowledge.label}")
        lines.append(f"finding_type: {knowledge.finding_type}")
        lines.append(f"effect_allele: {knowledge.effect_allele}")
        lines.append(f"runtime_default: {knowledge.runtime_default}")
        lines.append(f"reporting_tier: {knowledge.reporting_tier}")
        lines.append(f"summary: {knowledge.summary}")
        lines.append(f"gate: {knowledge.evidence_gate}")
        if knowledge.confirmation_tests:
            lines.append(f"confirmation_tests: {knowledge.confirmation_tests}")
        if knowledge.source_url:
            lines.append(f"source_url: {knowledge.source_url}")
    else:
        lines.append("No bundled annotation for this marker yet.")
    lines.append("")
    if variants:
        lines.append("Observed calls:")
        for variant in variants:
            lines.append(
                f"- source {variant.source_id}: {variant.reported_genotype} "
                f"({variant.call_status}, build {variant.genome_build})"
            )
    else:
        lines.append("No observed call stored for this profile.")
    lines.append("")
    lines.append("genetic_data_notice: context only; not diagnostic; confirm before action")
    return "\n".join(lines)


def render_confirm_list(inferences: list[GenomicInference]) -> str:
    lines = ["# Genomics confirmation list", ""]
    items = [item for item in inferences if item.required_confirmation]
    if not items:
        lines.append("No confirmation-first genomic review items found.")
        return "\n".join(lines)
    for item in items:
        lines.append(f"- {item.title} · {item.discussion_target} · {item.confidence}")
    lines.append("")
    lines.append("Confirm high-impact findings with clinical-grade testing before action.")
    return "\n".join(lines)


def render_annotation_summary(variants: list[VariantCall]) -> str:
    known = [variant for variant in variants if variant.rsid in MARKERS and variant.is_called]
    lines = ["# Genomics annotation summary", ""]
    lines.append("annotation_sources: bundled release-pinned clinical marker catalog")
    lines.append(f"known_marker_matches: {len(known)}")
    for variant in known:
        knowledge = MARKERS[variant.rsid]
        lines.append(f"- {variant.rsid}: {knowledge.gene} · {knowledge.label}")
    lines.append("")
    lines.append("No external annotation calls were made.")
    return "\n".join(lines).rstrip()


def render_pgx(variants: list[VariantCall], inferences: list[GenomicInference]) -> str:
    pgx_variants = [
        variant
        for variant in variants
        if MARKERS.get(variant.rsid, None)
        and MARKERS[variant.rsid].finding_type == "pgx"
    ]
    pgx_cards = [item for item in inferences if item.finding_type == "pgx"]
    lines = ["# Pharmacogenomics context", ""]
    lines.append(f"pgx_variant_markers: {len(pgx_variants)}")
    lines.append(f"pgx_review_cards: {len(pgx_cards)}")
    for card in pgx_cards:
        lines.append(f"- {card.title}: {card.summary}")
    lines.append("")
    lines.append("PGx cards are discussion prompts only; do not change medication without review.")
    return "\n".join(lines).rstrip()
