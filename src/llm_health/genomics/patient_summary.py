from __future__ import annotations

from typing import Any

from llm_health.core.enums import VisibleTag
from llm_health.core.privacy import validate_profile_alias

from .models import GenomicInference, GenomicQC


def inference_payload_with_patient_summary(card: GenomicInference) -> dict[str, Any]:
    """Return a UI-safe inference payload with a patient-friendly one-liner.

    This keeps the browser generic: it renders the summary produced by the local
    genomics review pipeline instead of carrying profile-specific wording in JS.
    """

    payload = card.to_dict()
    payload["patient_summary"] = patient_card_summary(card)
    return payload


def build_patient_summary(
    *,
    profile_id: str,
    source_count: int,
    marker_count: int,
    qc_rows: list[GenomicQC] | list[dict[str, Any]],
    cards: list[GenomicInference],
) -> dict[str, Any]:
    """Build a simple review-panel summary from already-generated genomics cards."""

    validate_profile_alias(profile_id)
    if source_count <= 0:
        return {
            "tags": [VisibleTag.CONTEXT.value, VisibleTag.DATA_GAP.value],
            "lead": "No genotype file is loaded yet.",
            "bullets": [
                "Choose a local raw genotype text file when you are ready.",
                "The page sends text only to this localhost app, not to an outside server.",
                "Future matches are review notes for context and follow-up.",
            ],
        }

    research_cards = [card for card in cards if _is_research_context_card(card)]
    review_cards = [card for card in cards if not _is_research_context_card(card)]
    topics = patient_card_topics(review_cards, limit=4)
    research_topics = patient_card_topics(research_cards, limit=3)
    tags = [VisibleTag.CONTEXT.value, "CONFIRM_FIRST"]
    if research_cards:
        tags.insert(1, "RESEARCH_CONTEXT")
    if _has_consumer_or_low_quality_gap(qc_rows):
        tags.insert(1, VisibleTag.DATA_GAP.value)

    source_word = "source" if source_count == 1 else "sources"
    marker_word = "genetic marker" if marker_count == 1 else "genetic markers"
    card_count = len(cards)
    card_word = "card" if card_count == 1 else "cards"
    research_count = len(research_cards)
    research_card_word = "card" if research_count == 1 else "cards"

    bullets: list[str] = []
    if research_topics:
        bullets.append(
            f"Research-only context is shown separately: {_format_list(research_topics)}. "
            "This is not a diagnosis, screening result, prognosis, or polygenic score."
        )
    if topics:
        bullets.append(
            f"Matches below include {_format_list(topics)}. "
            "Use them as context; confirm anything decision-relevant."
        )
    else:
        bullets.append("No specific match topics are showing yet.")
    bullets.append(_quality_line(qc_rows))
    bullets.append(
        f"{card_count} discussion {card_word} "
        f"{'is' if card_count == 1 else 'are'} ready below for review."
        if card_count
        else "If there are useful matches, discussion cards will appear below."
    )
    bullets.append(_confirmation_line(qc_rows))

    return {
        "tags": tags,
        "lead": (
            f"This profile has {source_count} local genotype {source_word} loaded, "
            f"with {marker_count} {marker_word} saved for review."
            if not research_count
            else (
                f"This profile has {source_count} local genotype {source_word} loaded, "
                f"with {marker_count} {marker_word} saved for review, including "
                f"{research_count} research-context {research_card_word}."
            )
        ),
        "bullets": bullets,
    }


def patient_card_topics(cards: list[GenomicInference], *, limit: int = 4) -> list[str]:
    topics: list[str] = []
    for card in cards:
        topic = patient_card_topic(card)
        if topic and topic not in topics:
            topics.append(topic)
        if len(topics) >= limit:
            break
    return topics


def patient_card_topic(card: GenomicInference) -> str:
    summary = patient_card_summary(card)
    if " — " in summary:
        return summary.split(" — ", 1)[0]
    if " context" in summary:
        return summary.split(" context", 1)[0]
    return summary.rstrip(".")


def patient_card_summary(card: GenomicInference) -> str:
    """Small patient-facing summary for one genomics card.

    Rules are marker/topic agnostic where possible and fall back to finding type.
    The output remains a review prompt, not an interpretation of disease status.
    """

    hay = f"{card.title} {card.summary} {card.finding_type}".lower()
    if "dyslexia" in hay:
        return (
            "dyslexia GWAS research context — matched markers are research-only, "
            "not a diagnosis or polygenic score."
        )
    if "adhd" in hay or "attention-deficit" in hay or "attention deficit" in hay:
        return (
            "ADHD GWAS research context — matched markers are research-only, "
            "not a diagnosis or polygenic score."
        )
    if "autism" in hay or "autism spectrum" in hay:
        return (
            "autism spectrum GWAS research context — matched markers are research-only, "
            "not a diagnosis or polygenic score."
        )
    if "research_trait_context" in card.finding_type.lower():
        return (
            "research-only trait marker context — use for background only, not as a "
            "diagnosis or screening result."
        )
    if any(term in hay for term in ("ugt1a1", "bilirubin", "gilbert")):
        return (
            "bilirubin / possible Gilbert syndrome — may help explain a harmless bilirubin pattern "
            "or matter for a few medicines; check labs if relevant."
        )
    if any(term in hay for term in ("dpyd", "fluoropyrimidine")):
        return (
            "strong reactions to certain cancer medicines — only relevant if those medicines are "
            "being considered, and should be confirmed if decision-relevant."
        )
    if any(term in hay for term in ("cyp3a5", "tacrolimus")):
        return (
            "how the body handles tacrolimus — may matter only if transplant medicine or "
            "tacrolimus is relevant."
        )
    if "cyp2c19" in hay:
        return (
            "how the body handles some common medicines — may matter for medication review, "
            "not for changing anything by itself."
        )
    if any(term in hay for term in ("cyp2c9", "vkorc1", "warfarin")):
        return (
            "warfarin blood-thinner sensitivity — useful only for clinician-guided warfarin "
            "decisions."
        )
    if any(term in hay for term in ("slco1b1", "statin")):
        return "statin muscle side-effect risk — may help guide a medication discussion."
    if any(term in hay for term in ("hfe", "iron", "hemochromatosis")):
        return "iron overload risk — iron blood tests matter more than this marker alone."
    if any(term in hay for term in ("celiac", "hla")):
        return (
            "celiac disease risk — diagnosis depends on symptoms and blood tests "
            "while eating gluten."
        )
    if "g6pd" in hay:
        return "red-blood-cell sensitivity — check with an enzyme test if relevant."
    if any(term in hay for term in ("lpa", "lipoprotein")):
        return (
            "lipoprotein(a) screening — consider measured Lp(a) rather than acting "
            "on a raw match."
        )
    if "pgx" in card.finding_type.lower():
        return "medication-response context — keep as a clinician or pharmacist discussion prompt."
    return "genetic context note — use as a prompt for follow-up if relevant."


def _quality_line(qc_rows: list[GenomicQC] | list[dict[str, Any]]) -> str:
    call_rates = [_qc_value(row, "call_rate") for row in qc_rows]
    numeric = [float(value) for value in call_rates if isinstance(value, int | float)]
    if not numeric:
        return "The read quality is not known yet."
    call_rate = max(numeric)
    call_rate_text = f"{call_rate * 100:.1f}%"
    if call_rate >= 0.98:
        return f"The read quality looks high: {call_rate_text} of the checked spots were readable."
    if call_rate >= 0.95:
        return (
            f"The read quality looks usable: {call_rate_text} of the checked spots "
            "were readable."
        )
    return (
        f"The read quality may be limited: {call_rate_text} of the checked spots were readable, "
        "so missing data could matter."
    )


def _confirmation_line(qc_rows: list[GenomicQC] | list[dict[str, Any]]) -> str:
    if _has_consumer_warning(qc_rows):
        return (
            "Because this looks like consumer or unconfirmed data, confirm anything important "
            "before using it for decisions."
        )
    return (
        "Confirm important findings with a clinician or clinical lab if they would "
        "affect decisions."
    )


def _is_research_context_card(card: GenomicInference) -> bool:
    hay = " ".join([card.finding_type, card.title, *card.tags]).lower()
    return "research" in hay or "dyslexia" in hay or "adhd" in hay or "autism" in hay


def _has_consumer_or_low_quality_gap(qc_rows: list[GenomicQC] | list[dict[str, Any]]) -> bool:
    return _has_consumer_warning(qc_rows) or any(
        isinstance(_qc_value(row, "call_rate"), int | float)
        and float(_qc_value(row, "call_rate")) < 0.95
        for row in qc_rows
    )


def _has_consumer_warning(qc_rows: list[GenomicQC] | list[dict[str, Any]]) -> bool:
    return any(
        "consumer_or_unconfirmed" in str(warning)
        for row in qc_rows
        for warning in (_qc_value(row, "warnings") or [])
    )


def _qc_value(row: GenomicQC | dict[str, Any], key: str) -> Any:
    if isinstance(row, dict):
        return row.get(key)
    return getattr(row, key)


def _format_list(items: list[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return f"{', '.join(items[:-1])}, and {items[-1]}"
