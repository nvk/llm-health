from __future__ import annotations

from typing import Any

from llm_health.core.privacy import PrivacyError, validate_profile_alias
from llm_health.stores import LocalHealthStore

from .models import GenomicInference
from .patient_summary import build_patient_summary, inference_payload_with_patient_summary
from .qc import build_qc
from .store import GenomicsStore


def genomics_sources_payload(
    store: LocalHealthStore,
    profile_id: str | None = None,
) -> dict[str, Any]:
    profile = validate_profile_alias(profile_id) if profile_id else None
    store.init()
    if profile and not store.profile_exists(profile):
        raise PrivacyError(f"profile alias {profile!r} is not enrolled")
    genomics_store = GenomicsStore(store.root)
    sources = genomics_store.sources(profile)
    variant_count = len(genomics_store.variants(profile))
    return {
        "count": len(sources),
        "variant_count": variant_count,
        "sources": [_source_payload(source) for source in sources],
        "privacy": (
            "source summaries and matched SNP findings only; raw genetic file paths "
            "and dense genome-wide calls are not stored by default"
        ),
    }


def genomics_qc_payload(store: LocalHealthStore, profile_id: str) -> dict[str, Any]:
    profile = validate_profile_alias(profile_id)
    store.init()
    if not store.profile_exists(profile):
        raise PrivacyError(f"profile alias {profile!r} is not enrolled")
    genomics_store = GenomicsStore(store.root)
    rows = [
        _qc_payload(build_qc(source, genomics_store.variants(profile, source.source_id)))
        for source in genomics_store.sources(profile)
    ]
    return {"profile_id": profile, "count": len(rows), "qc": rows}


def genomics_crossrefs_payload(
    store: LocalHealthStore,
    profile_id: str,
    *,
    limit: int = 50,
) -> dict[str, Any]:
    review = genomics_review_payload(store, profile_id, limit=limit)
    cards = review["crossrefs"]["cards"]
    return {
        "profile_id": review["profile_id"],
        "count": len(cards),
        "cards": cards,
        "patient_summary": review["patient_summary"],
        "notice": "genomic cards are context notes; confirm decision-relevant findings",
    }


def genomics_review_payload(
    store: LocalHealthStore,
    profile_id: str,
    *,
    limit: int = 50,
) -> dict[str, Any]:
    """Assemble the complete genomics review view model for UI/service clients.

    Browser and service layers should render this payload instead of interpreting markers,
    QC status, or patient wording themselves.
    """

    profile = validate_profile_alias(profile_id)
    store.init()
    if not store.profile_exists(profile):
        raise PrivacyError(f"profile alias {profile!r} is not enrolled")
    genomics_store = GenomicsStore(store.root)
    sources = genomics_store.sources(profile)
    variants = genomics_store.variants(profile)
    qc_rows = [
        build_qc(source, genomics_store.variants(profile, source.source_id))
        for source in sources
    ]
    cards = _sorted_cards(genomics_store.inferences(profile), limit=limit)
    return {
        "profile_id": profile,
        "sources": {
            "count": len(sources),
            "variant_count": len(variants),
            "sources": [_source_payload(source) for source in sources],
        },
        "qc": {
            "profile_id": profile,
            "count": len(qc_rows),
            "qc": [_qc_payload(row) for row in qc_rows],
        },
        "crossrefs": {
            "count": len(cards),
            "cards": [inference_payload_with_patient_summary(card) for card in cards],
        },
        "patient_summary": build_patient_summary(
            profile_id=profile,
            source_count=len(sources),
            marker_count=len(variants),
            qc_rows=qc_rows,
            cards=cards,
        ),
        "notice": "genomic cards are context notes; confirm decision-relevant findings",
    }


def _source_payload(source) -> dict[str, Any]:
    payload = source.to_dict()
    payload["call_rate"] = source.call_rate
    return payload


def _qc_payload(qc) -> dict[str, Any]:
    payload = qc.to_dict()
    payload["warning_details"] = [qc_warning_payload(warning) for warning in qc.warnings]
    return payload


def qc_warning_payload(warning: str) -> dict[str, str]:
    label_by_code = {
        "call_rate_below_95_percent": (
            "Some genotype calls were missing; missing data could matter."
        ),
        "duplicate_marker_ids_present": (
            "The source had repeated marker IDs; duplicates were handled locally."
        ),
        "genome_build_unknown": "The genome build was not clear from the file.",
        "consumer_or_unconfirmed_source_review": (
            "Consumer-style source: use as context; confirm decision-relevant findings."
        ),
        "complex_or_indel_like_calls_need_review": (
            "Some complex calls may need clinical review before interpretation."
        ),
    }
    return {"code": warning, "label": label_by_code.get(warning, warning.replace("_", " "))}


def _sorted_cards(cards: list[GenomicInference], *, limit: int) -> list[GenomicInference]:
    rows = list(cards)
    rows.sort(key=lambda item: item.created_at, reverse=True)
    return rows[:limit]
