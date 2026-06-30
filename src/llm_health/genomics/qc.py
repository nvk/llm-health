from __future__ import annotations

from .models import GenomicQC, GenomicSource, VariantCall


def build_qc(source: GenomicSource, variants: list[VariantCall]) -> GenomicQC:
    warnings: list[str] = []
    if source.call_rate < 0.95:
        warnings.append("call_rate_below_95_percent")
    if source.duplicate_marker_count:
        warnings.append("duplicate_marker_ids_present")
    if source.genome_build == "unknown":
        warnings.append("genome_build_unknown")
    if not source.clinical_grade:
        warnings.append("consumer_or_unconfirmed_source_review")
    if any("complex_or_indel_like_call" in variant.quality_flags for variant in variants):
        warnings.append("complex_or_indel_like_calls_need_review")
    return GenomicQC(
        profile_id=source.profile_id,
        source_id=source.source_id or "",
        marker_count=source.marker_count,
        called_count=source.called_count,
        no_call_count=source.no_call_count,
        duplicate_marker_count=source.duplicate_marker_count,
        call_rate=source.call_rate,
        warnings=warnings,
    )


def render_qc(qc_rows: list[GenomicQC]) -> str:
    lines = ["# Genomics QC", ""]
    if not qc_rows:
        lines.append("No genomic sources found.")
        return "\n".join(lines)
    for qc in qc_rows:
        lines.append(f"source_id: {qc.source_id}")
        lines.append(f"markers: {qc.marker_count}")
        lines.append(f"called: {qc.called_count}")
        lines.append(f"no_calls: {qc.no_call_count}")
        lines.append(f"call_rate: {qc.call_rate:.3f}")
        lines.append(f"duplicates: {qc.duplicate_marker_count}")
        lines.append("qc_notes: " + (", ".join(qc.warnings) if qc.warnings else "none"))
        lines.append("")
    lines.append("review_note: context only; confirm decision-relevant findings")
    return "\n".join(lines).rstrip()
