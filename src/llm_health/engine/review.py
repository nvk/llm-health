from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median

from llm_health.core.enums import ReviewTrigger, VisibleTag
from llm_health.core.models import (
    NewResultEvent,
    Observation,
    QuickReviewCard,
    ResearchJob,
    stable_id,
)
from llm_health.core.privacy import validate_profile_alias
from llm_health.research.workflow import default_retrieval_ladder
from llm_health.stores import LocalHealthStore


@dataclass(frozen=True)
class ReviewResult:
    event: NewResultEvent
    cards: list[QuickReviewCard] = field(default_factory=list)
    research_jobs: list[ResearchJob] = field(default_factory=list)
    interest_score: float = 0.0


class ReviewEngine:
    """Creates quick review cards and smart deep-research jobs for new observations."""

    def __init__(self, store: LocalHealthStore, *, interest_threshold: float = 0.60) -> None:
        self.store = store
        self.interest_threshold = interest_threshold

    def review_new_observations(
        self,
        profile_id: str,
        observations: list[Observation],
        *,
        persist: bool = True,
    ) -> ReviewResult:
        profile = validate_profile_alias(profile_id)
        prior = self.store.observations(profile) if self.store.root.exists() else []
        triggers = self._detect_triggers(observations, prior)
        observation_ids = [obs.observation_id for obs in observations]
        trigger_values = sorted(trigger.value for trigger in triggers)
        event = NewResultEvent(
            profile_id=profile,
            observation_ids=observation_ids,
            source_id=observations[0].source_id if observations else "user_note",
            triggers=trigger_values,
            event_id=stable_id(
                "event",
                profile,
                observations[0].source_id if observations else "user_note",
                sorted(observation_ids),
                trigger_values,
            ),
        )
        cards = self._make_cards(profile, observations, prior, triggers)
        interest = self._interest_score(triggers, observations)
        jobs = self._make_research_jobs(profile, observations, triggers, interest)

        if persist:
            self.store.append_review_event(event)
            for card in cards:
                self.store.append_quick_review_card(card)
            for job in jobs:
                self.store.append_research_job(job)
        return ReviewResult(event=event, cards=cards, research_jobs=jobs, interest_score=interest)

    def _detect_triggers(
        self, observations: list[Observation], prior: list[Observation]
    ) -> set[ReviewTrigger]:
        triggers: set[ReviewTrigger] = {ReviewTrigger.NEW_RESULT}
        prior_categories = {obs.category.lower() for obs in prior}
        for obs in observations:
            if obs.category.lower() not in prior_categories:
                triggers.add(ReviewTrigger.NEW_CATEGORY)
            if obs.is_pending:
                triggers.add(ReviewTrigger.PENDING_RESULT)
            if obs.is_flagged:
                triggers.add(ReviewTrigger.FLAGGED_RESULT)
            previous_values = [
                p.value
                for p in prior
                if p.profile_id == obs.profile_id
                and p.marker.lower() == obs.marker.lower()
                and p.unit == obs.unit
                and p.value is not None
            ]
            if obs.value is not None and previous_values:
                baseline = median(previous_values[-5:])
                if baseline != 0 and abs(obs.value - baseline) / abs(baseline) >= 0.25:
                    triggers.add(ReviewTrigger.LARGE_DELTA)
        return triggers

    def _make_cards(
        self,
        profile: str,
        observations: list[Observation],
        prior: list[Observation],
        triggers: set[ReviewTrigger],
    ) -> list[QuickReviewCard]:
        if not observations:
            return []
        categories = sorted({obs.category for obs in observations})
        flagged = [obs for obs in observations if obs.is_flagged]
        pending = [obs for obs in observations if obs.is_pending]
        cards = [
            QuickReviewCard(
                profile_id=profile,
                title=f"New results ingested · {len(observations)} observation(s)",
                summary=(
                    f"Categories: {', '.join(categories)}. "
                    f"Flagged: {len(flagged)}. Pending/non-numeric: {len(pending)}."
                ),
                priority=0.55,
                triggers=sorted(trigger.value for trigger in triggers),
                related_observation_ids=[obs.observation_id for obs in observations],
                tags=[VisibleTag.OBSERVED.value, VisibleTag.INFERENCE.value],
                card_id=stable_id(
                    "card",
                    profile,
                    "new_results",
                    sorted(obs.observation_id for obs in observations),
                ),
            )
        ]
        if flagged:
            flagged_ids = sorted(obs.observation_id for obs in flagged)
            summary = "; ".join(
                _flagged_summary(obs)
                for obs in flagged[:5]
                if obs.value is not None
            )
            cards.append(
                QuickReviewCard(
                    profile_id=profile,
                    title="Flagged result(s) need review",
                    summary=summary or "One or more observations carried source flags.",
                    priority=0.85,
                    triggers=[ReviewTrigger.FLAGGED_RESULT.value],
                    related_observation_ids=[obs.observation_id for obs in flagged],
                    tags=[VisibleTag.INFERENCE.value, VisibleTag.QA_ISSUE.value],
                    card_id=stable_id("card", profile, "flagged_results", flagged_ids),
                )
            )
        if ReviewTrigger.LARGE_DELTA in triggers:
            cards.append(
                QuickReviewCard(
                    profile_id=profile,
                    title="Large change detected",
                    summary=(
                        "At least one marker moved >=25% versus recent same-unit "
                        "history; confirm units, context, and same-lab/method "
                        "before overinterpreting."
                    ),
                    priority=0.75,
                    triggers=[ReviewTrigger.LARGE_DELTA.value],
                    related_observation_ids=[obs.observation_id for obs in observations],
                    tags=[VisibleTag.INFERENCE.value, VisibleTag.QA_ISSUE.value],
                    card_id=stable_id(
                        "card",
                        profile,
                        "large_delta",
                        sorted(obs.observation_id for obs in observations),
                    ),
                )
            )
        if pending:
            pending_ids = sorted(obs.observation_id for obs in pending)
            cards.append(
                QuickReviewCard(
                    profile_id=profile,
                    title="Pending/non-numeric result not plotted",
                    summary=(
                        "A pending or non-numeric row should remain a source/status "
                        "item until a numeric result arrives."
                    ),
                    priority=0.7,
                    triggers=[ReviewTrigger.PENDING_RESULT.value],
                    related_observation_ids=[obs.observation_id for obs in pending],
                    tags=[VisibleTag.QA_ISSUE.value],
                    card_id=stable_id("card", profile, "pending_results", pending_ids),
                )
            )
        return cards

    def _interest_score(
        self, triggers: set[ReviewTrigger], observations: list[Observation]
    ) -> float:
        score = 0.15
        weights = {
            ReviewTrigger.FLAGGED_RESULT: 0.30,
            ReviewTrigger.LARGE_DELTA: 0.25,
            ReviewTrigger.NEW_CATEGORY: 0.15,
            ReviewTrigger.PENDING_RESULT: 0.10,
            ReviewTrigger.QA_ISSUE: 0.15,
            ReviewTrigger.CONTEXT_COLLISION: 0.20,
            ReviewTrigger.OPEN_GAP_MATCH: 0.20,
        }
        for trigger in triggers:
            score += weights.get(trigger, 0.0)
        categories = {obs.category.lower() for obs in observations}
        if len(categories) > 1:
            score += 0.05
        if any(
            category in {"heavy metals", "liver", "liver profile", "hormones", "thyroid"}
            for category in categories
        ):
            score += 0.25
        return min(1.0, score)

    def _make_research_jobs(
        self,
        profile: str,
        observations: list[Observation],
        triggers: set[ReviewTrigger],
        interest_score: float,
    ) -> list[ResearchJob]:
        if interest_score < self.interest_threshold:
            return []
        categories = sorted({obs.category for obs in observations})
        markers = sorted({obs.marker for obs in observations})
        topic = f"New-result review: {', '.join(categories)} ({', '.join(markers[:6])})"
        rationale = (
            "Queued because new results crossed the smart-review interest threshold. "
            f"Use retrieval ladder: {', '.join(default_retrieval_ladder()[:5])}, "
            "then user-provided PDFs if needed."
        )
        return [
            ResearchJob(
                profile_id=profile,
                topic=topic,
                rationale=rationale,
                priority=interest_score,
                related_ids=[obs.observation_id for obs in observations],
                triggers=sorted(trigger.value for trigger in triggers),
                job_id=stable_id(
                    "research",
                    profile,
                    topic,
                    sorted(obs.observation_id for obs in observations),
                ),
            )
        ]


def _flagged_summary(observation: Observation) -> str:
    value = f"{observation.value:g}" if observation.value is not None else "pending"
    if observation.unit:
        value = f"{value} {observation.unit}"
    details = [str(observation.flag)] if observation.flag else []
    if observation.reference_range:
        details.append(f"ref {observation.reference_range}")
    suffix = f" ({'; '.join(details)})" if details else ""
    return f"{observation.marker} {value}{suffix}".strip()
