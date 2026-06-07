from __future__ import annotations

from llm_health.core.models import (
    ConservativeCareOption,
    MedicationExposureReview,
    PreventiveProtocolReview,
)


class LeastHarmEngine:
    """Builds low-intervention and collateral-damage review artifacts."""

    def watchful_waiting_option(self, target: str) -> ConservativeCareOption:
        return ConservativeCareOption(
            target=target,
            option_type="WATCHFUL_WAITING",
            rationale=(
                "Doing less can be an active protocol when symptoms are mild, "
                "function is preserved, "
                "and red-flag thresholds are explicit."
            ),
            allowed_if=[
                "no red flags",
                "symptoms mild to moderate and stable/improving",
                "hydration, sleep, and basic function acceptable",
            ],
            track=[
                "symptom severity 0-10",
                "temperature/systemic signs",
                "sleep/function",
                "trend",
            ],
            escalate_if=[
                "severe or worsening symptoms",
                "fever/systemic signs",
                "neurological symptoms",
                "bleeding, discharge, swelling, or loss of function",
                "symptoms persist beyond the chosen review window",
            ],
        )

    def medication_collateral_review(
        self, profile_id: str, active_or_class: str, indication: str
    ) -> MedicationExposureReview:
        lower = active_or_class.lower()
        collateral: list[str]
        if "antibiotic" in lower:
            collateral = ["microbiome disruption", "resistance", "C. difficile risk", "GI effects"]
        elif lower in {"ibuprofen", "advil", "nsaid", "naproxen"} or "nsaid" in lower:
            collateral = [
                "GI bleeding/ulcer risk",
                "gut-barrier effects",
                "kidney stress",
                "blood pressure",
            ]
        elif lower in {"acetaminophen", "paracetamol", "tylenol"} or "tylenol" in lower:
            collateral = [
                "liver dose ceiling",
                "alcohol/fasting interaction",
                "overlap with combination products",
            ]
        else:
            collateral = [
                "unknown collateral profile; research by active/class, dose, route, and duration"
            ]
        return MedicationExposureReview(
            profile_id=profile_id,
            active_or_class=active_or_class,
            indication=indication,
            necessity_score="unknown_until_context",
            collateral_damage=collateral,
            avoidability_questions=[
                "What confirmed diagnosis or benefit threshold justified exposure?",
                (
                    "Was watchful waiting, a diagnostic test, narrower option, "
                    "or shorter duration reasonable?"
                ),
                "What markers/symptoms should be monitored after exposure?",
            ],
            evidence_tags=["LABEL_LISTED", "LITERATURE_SIGNAL", "UNDER_DISCLOSED_REVIEW_NEEDED"],
        )

    def preventive_protocol_review(self, profile_id: str, target: str) -> PreventiveProtocolReview:
        return PreventiveProtocolReview(
            profile_id=profile_id,
            target=target,
            conclusion_options=[
                "accept",
                "defer",
                "decline",
                "only_if_exposed_or_high_risk",
                "needs_more_research",
            ],
            benefit_questions=[
                "What is the absolute risk reduction for this profile and season/exposure context?",
                (
                    "Which endpoint moves: infection, symptoms, hospitalization, "
                    "death, transmission, or surrogate?"
                ),
                "How long does benefit plausibly last?",
            ],
            harm_questions=[
                (
                    "What acute, serious, delayed, or undertracked adverse "
                    "signals exist for this subgroup?"
                ),
                "How reversible is the intervention if wrong?",
                "Are harms measured actively or through passive reporting?",
            ],
            alternatives=[
                "defer/decline as active option",
                "targeted exposure avoidance or timing",
                "nutrition/sleep/light/ventilation/hygiene strategy",
                "post-exposure or high-risk-only strategy where applicable",
            ],
        )
