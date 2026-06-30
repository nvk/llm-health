from __future__ import annotations

from collections import defaultdict

from llm_health.core.models import DiagnosticGap, Observation, TestCandidate, stable_id
from llm_health.core.privacy import validate_profile_alias


class DiagnosticGapEngine:
    """Turns observed patterns into reviewable diagnostic gaps and test/context candidates."""

    def create_gaps(self, profile_id: str, observations: list[Observation]) -> list[DiagnosticGap]:
        profile = validate_profile_alias(profile_id)
        by_category: dict[str, list[Observation]] = defaultdict(list)
        for obs in observations:
            by_category[obs.category.lower()].append(obs)

        gaps: list[DiagnosticGap] = []
        if self._has_liver_signal(by_category):
            related = by_category.get("liver", []) + by_category.get("liver profile", [])
            gaps.append(self._liver_gap(profile, related))
        if self._has_heavy_metal_signal(by_category):
            related = by_category.get("heavy metals", []) + by_category.get("metals", [])
            gaps.append(self._heavy_metals_gap(profile, related))
        flagged = [obs for obs in observations if obs.is_flagged]
        if flagged:
            gaps.append(self._context_gap(profile, flagged))
        return gaps

    def _has_liver_signal(self, by_category: dict[str, list[Observation]]) -> bool:
        markers = {
            obs.marker.lower()
            for key in ["liver", "liver profile", "chemistry"]
            for obs in by_category.get(key, [])
        }
        return bool(markers & {"alt", "ast", "bilirubin", "total bilirubin", "indirect bilirubin"})

    def _has_heavy_metal_signal(self, by_category: dict[str, list[Observation]]) -> bool:
        markers = {obs.marker.lower() for obs in by_category.get("heavy metals", [])}
        return any(
            any(target in marker for target in {"mercury", "lead", "arsenic", "cadmium"})
            for marker in markers
        )

    def _liver_gap(self, profile: str, related: list[Observation]) -> DiagnosticGap:
        related_ids = [obs.observation_id for obs in related]
        return DiagnosticGap(
            profile_id=profile,
            title="Liver-pattern interpretation gap",
            gap_type="pattern_gap",
            rationale=(
                "Liver markers are present; interpretation often depends on "
                "confirming persistence, "
                "separating bilirubin fractions, and checking cholestatic/context markers."
            ),
            priority=0.72,
            candidates=[
                TestCandidate(
                    name="repeat hepatic panel",
                    role="confirm whether the pattern persists before deeper inference",
                    information_gain=0.75,
                    actionability=0.65,
                    false_positive_risk=0.25,
                    burden=0.25,
                ),
                TestCandidate(
                    name="GGT",
                    role=(
                        "add cholestatic/alcohol/medication-context signal when "
                        "ALT/AST/bilirubin are hard to read"
                    ),
                    information_gain=0.70,
                    actionability=0.55,
                    false_positive_risk=0.30,
                    burden=0.25,
                ),
                TestCandidate(
                    name="direct + indirect bilirubin",
                    role=(
                        "separate conjugated versus unconjugated bilirubin, "
                        "especially with Gilbert-context questions"
                    ),
                    information_gain=0.80,
                    actionability=0.60,
                    false_positive_risk=0.20,
                    burden=0.25,
                ),
            ],
            context_questions=[
                "Was the draw fasting?",
                (
                    "Any heavy exercise, alcohol, illness, fasting, or calorie "
                    "restriction in the prior 72h?"
                ),
                "Any medication/supplement changes near the draw?",
                "Same lab/method and units as prior results?",
            ],
            related_observation_ids=related_ids,
            gap_id=stable_id("gap", profile, "liver_pattern", sorted(related_ids)),
        )

    def _heavy_metals_gap(self, profile: str, related: list[Observation]) -> DiagnosticGap:
        related_ids = [obs.observation_id for obs in related]
        return DiagnosticGap(
            profile_id=profile,
            title="Heavy-metals specimen/context gap",
            gap_type="confirmatory_gap",
            rationale=(
                "Heavy-metal interpretation is specimen- and unit-sensitive. "
                "Confirm specimen type, units, "
                "result status, and exposure timing before comparing across reports."
            ),
            priority=0.68,
            candidates=[
                TestCandidate(
                    name="confirm specimen type + unit normalization",
                    role=(
                        "avoid comparing whole blood, urine, hair, or different "
                        "unit systems as one line"
                    ),
                    information_gain=0.85,
                    actionability=0.70,
                    false_positive_risk=0.10,
                    burden=0.05,
                ),
                TestCandidate(
                    name="exposure inventory",
                    role=(
                        "identify fish, dental, occupational, water, supplement, "
                        "or environmental exposure windows"
                    ),
                    information_gain=0.65,
                    actionability=0.70,
                    false_positive_risk=0.15,
                    burden=0.10,
                ),
            ],
            context_questions=[
                "What specimen type was used?",
                "Was this a pending result, below-detection result, or numeric value?",
                "Any exposure change in the last 30-90 days?",
            ],
            related_observation_ids=related_ids,
            gap_id=stable_id("gap", profile, "heavy_metals_specimen_context", sorted(related_ids)),
        )

    def _context_gap(self, profile: str, flagged: list[Observation]) -> DiagnosticGap:
        categories = sorted({obs.category for obs in flagged})
        flagged_ids = [obs.observation_id for obs in flagged]
        return DiagnosticGap(
            profile_id=profile,
            title="Source-note context gap",
            gap_type="confounder_gap",
            rationale=(
                "At least one source-noted result lacks enough context to interpret confidently. "
                "Ask context first; do not reflexively order a broad panel."
            ),
            priority=0.62,
            candidates=[
                TestCandidate(
                    name="context questionnaire before more testing",
                    role=(
                        "fasting, illness, exercise, medications, supplements, "
                        "exposure, and lab-method context can close false gaps"
                    ),
                    information_gain=0.70,
                    actionability=0.80,
                    false_positive_risk=0.05,
                    burden=0.05,
                )
            ],
            context_questions=[
                f"For categories {', '.join(categories)}: what changed in the 7/30/90-day windows?",
                (
                    "Was the source flag based on this lab's reference range or "
                    "a custom/derived range?"
                ),
            ],
            related_observation_ids=flagged_ids,
            gap_id=stable_id("gap", profile, "flagged_result_context", sorted(flagged_ids)),
        )
