from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from llm_health.core.enums import VisibleTag
from llm_health.core.models import Observation, stable_id, utc_now_iso
from llm_health.core.privacy import assert_safe_payload, validate_profile_alias
from llm_health.core.serialization import to_jsonable
from llm_health.stores import LocalHealthStore

FIRST_DEGREE_RELATIONS = {
    "father",
    "mother",
    "parent",
    "son",
    "daughter",
    "child",
    "brother",
    "sister",
    "sibling",
}
SECOND_DEGREE_RELATIONS = {
    "grandfather",
    "grandmother",
    "grandparent",
    "grandson",
    "granddaughter",
    "grandchild",
    "uncle",
    "aunt",
    "nephew",
    "niece",
    "half-brother",
    "half-sister",
    "half-sibling",
}
THIRD_DEGREE_RELATIONS = {"cousin", "great-grandparent", "great-grandchild"}
NON_BIOLOGICAL_RELATIONS = {"spouse", "partner", "step-parent", "step-child", "guardian"}

REVERSE_RELATION = {
    "father": "child",
    "mother": "child",
    "parent": "child",
    "son": "parent",
    "daughter": "parent",
    "child": "parent",
    "brother": "sibling",
    "sister": "sibling",
    "sibling": "sibling",
    "grandfather": "grandchild",
    "grandmother": "grandchild",
    "grandparent": "grandchild",
    "grandson": "grandparent",
    "granddaughter": "grandparent",
    "grandchild": "grandparent",
    "uncle": "niece/nephew",
    "aunt": "niece/nephew",
    "nephew": "aunt/uncle",
    "niece": "aunt/uncle",
    "cousin": "cousin",
    "spouse": "spouse",
    "partner": "partner",
}

HEREDITARY_KEYWORDS = {
    "cancer",
    "colon",
    "breast",
    "ovarian",
    "prostate",
    "melanoma",
    "gilbert",
    "hemochromatosis",
    "thalassemia",
    "sickle",
    "familial hypercholesterolemia",
    "hypercholesterolemia",
    "diabetes",
    "thyroid",
    "autoimmune",
    "celiac",
    "bipolar",
    "schizophrenia",
    "dementia",
    "alzheim",
    "cardiomyopathy",
    "arrhythmia",
    "aneurysm",
    "gout",
    "kidney stone",
}
HOUSEHOLD_CONTEXT_KEYWORDS = {
    "mercury",
    "lead",
    "arsenic",
    "mold",
    "water",
    "parasite",
    "pinworm",
    "infection",
    "diet",
    "sleep",
    "smoke",
    "secondhand",
}


def normalize_relation(relation: str) -> str:
    relation = relation.strip().lower().replace("_", "-")
    if not relation:
        raise ValueError("relation is required")
    return relation


def default_degree(relation: str) -> int | None:
    relation = normalize_relation(relation)
    if relation in FIRST_DEGREE_RELATIONS:
        return 1
    if relation in SECOND_DEGREE_RELATIONS:
        return 2
    if relation in THIRD_DEGREE_RELATIONS:
        return 3
    if relation in NON_BIOLOGICAL_RELATIONS:
        return None
    return None


@dataclass(frozen=True)
class FamilyRelationship:
    profile_id: str
    relative_id: str
    relation: str
    degree: int | None = None
    lineage: str = "unknown"
    shared_household: bool | None = None
    note: str | None = None
    tags: list[str] = field(default_factory=lambda: [VisibleTag.FAMILY_HISTORY.value])
    relationship_id: str | None = None
    created_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        profile = validate_profile_alias(self.profile_id)
        relative = validate_profile_alias(self.relative_id)
        relation = normalize_relation(self.relation)
        if profile == relative:
            raise ValueError("profile_id and relative_id must be different aliases")
        degree = self.degree if self.degree is not None else default_degree(relation)
        if degree is not None and not 0 <= degree <= 5:
            raise ValueError("degree must be between 0 and 5 when provided")
        lineage = self.lineage.strip().lower().replace("_", "-") if self.lineage else "unknown"
        relationship_id = self.relationship_id or stable_id("family", profile, relative, relation)
        normalized_tags = sorted(
            {str(tag) for tag in self.tags} | {VisibleTag.FAMILY_HISTORY.value}
        )
        object.__setattr__(self, "profile_id", profile)
        object.__setattr__(self, "relative_id", relative)
        object.__setattr__(self, "relation", relation)
        object.__setattr__(self, "degree", degree)
        object.__setattr__(self, "lineage", lineage)
        object.__setattr__(self, "relationship_id", relationship_id)
        object.__setattr__(self, "tags", normalized_tags)
        assert_safe_payload(self)

    def relation_from(self, profile_id: str) -> str:
        profile = validate_profile_alias(profile_id)
        if profile == self.profile_id:
            return self.relation
        if profile == self.relative_id:
            return REVERSE_RELATION.get(self.relation, f"reverse-{self.relation}")
        raise ValueError("profile is not part of this relationship")

    def other_alias(self, profile_id: str) -> str:
        profile = validate_profile_alias(profile_id)
        if profile == self.profile_id:
            return self.relative_id
        if profile == self.relative_id:
            return self.profile_id
        raise ValueError("profile is not part of this relationship")

    def to_dict(self) -> dict[str, Any]:
        return to_jsonable(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FamilyRelationship:
        return cls(**data)


@dataclass(frozen=True)
class FamilyHistoryEvent:
    profile_id: str
    condition: str
    status: str = "reported"
    evidence: str = "self_report"
    onset_age: int | None = None
    note: str | None = None
    related_profile_ids: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=lambda: [VisibleTag.FAMILY_HISTORY.value])
    event_id: str | None = None
    created_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        profile = validate_profile_alias(self.profile_id)
        related = [validate_profile_alias(item) for item in self.related_profile_ids]
        condition = self.condition.strip()
        if not condition:
            raise ValueError("condition is required")
        status = self.status.strip().lower().replace("_", "-")
        evidence = self.evidence.strip().lower().replace("_", "-")
        if self.onset_age is not None and not 0 <= self.onset_age <= 125:
            raise ValueError("onset_age must be between 0 and 125 when provided")
        event_id = self.event_id or stable_id(
            "family_history", profile, condition.lower(), status, evidence, self.onset_age
        )
        normalized_tags = sorted(
            {str(tag) for tag in self.tags} | {VisibleTag.FAMILY_HISTORY.value}
        )
        object.__setattr__(self, "profile_id", profile)
        object.__setattr__(self, "related_profile_ids", related)
        object.__setattr__(self, "condition", condition)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "evidence", evidence)
        object.__setattr__(self, "event_id", event_id)
        object.__setattr__(self, "tags", normalized_tags)
        assert_safe_payload(self)

    def to_dict(self) -> dict[str, Any]:
        return to_jsonable(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FamilyHistoryEvent:
        return cls(**data)


@dataclass(frozen=True)
class HereditaryRiskNote:
    profile_id: str
    title: str
    summary: str
    priority: float = 0.5
    signals: list[str] = field(default_factory=list)
    suggested_questions: list[str] = field(default_factory=list)
    candidate_tests: list[str] = field(default_factory=list)
    related_ids: list[str] = field(default_factory=list)
    tags: list[str] = field(
        default_factory=lambda: [
            VisibleTag.FAMILY_HISTORY.value,
            VisibleTag.HEREDITARY_RISK.value,
            VisibleTag.FAMILY_PATTERN.value,
            VisibleTag.INFERENCE.value,
        ]
    )
    note_id: str | None = None
    created_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        profile = validate_profile_alias(self.profile_id)
        priority = max(0.0, min(1.0, float(self.priority)))
        note_id = self.note_id or stable_id("family_risk", profile, self.title, self.summary)
        normalized_tags = sorted(
            {str(tag) for tag in self.tags}
            | {
                VisibleTag.FAMILY_HISTORY.value,
                VisibleTag.INFERENCE.value,
            }
        )
        object.__setattr__(self, "profile_id", profile)
        object.__setattr__(self, "priority", priority)
        object.__setattr__(self, "note_id", note_id)
        object.__setattr__(self, "tags", normalized_tags)
        assert_safe_payload(self)

    def to_dict(self) -> dict[str, Any]:
        return to_jsonable(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HereditaryRiskNote:
        return cls(**data)


def _is_active_history(event: FamilyHistoryEvent) -> bool:
    return event.status not in {"absent", "none", "negative", "unknown"}


def _is_hereditary_condition(condition: str) -> bool:
    needle = condition.lower()
    return any(keyword in needle for keyword in HEREDITARY_KEYWORDS)


def _is_household_condition(condition: str) -> bool:
    needle = condition.lower()
    return any(keyword in needle for keyword in HOUSEHOLD_CONTEXT_KEYWORDS)


def _bilirubin_signals(observations: list[Observation]) -> list[Observation]:
    return [obs for obs in observations if "bilirubin" in obs.marker.lower() and obs.is_flagged]


def create_family_risk_notes(store: LocalHealthStore, profile_id: str) -> list[HereditaryRiskNote]:
    profile = validate_profile_alias(profile_id)
    relationships = store.family_relationships(profile)
    events = store.family_history_events()
    observations = store.observations(profile)
    relatives_by_id = {
        relationship.other_alias(profile): relationship for relationship in relationships
    }
    notes: list[HereditaryRiskNote] = []

    for relative_id, relationship in sorted(relatives_by_id.items()):
        relative_events = [
            event
            for event in events
            if event.profile_id == relative_id and _is_active_history(event)
        ]
        for event in relative_events:
            relation = relationship.relation_from(profile)
            tags = [VisibleTag.FAMILY_HISTORY.value, VisibleTag.INFERENCE.value]
            questions = [
                f"Is {event.condition} confirmed, suspected, or ruled out for {relative_id}?",
                "Are there earlier-onset, severe, bilateral, or multiple-family-member patterns?",
                "Are there shared household/environment factors that could explain clustering?",
            ]
            tests: list[str] = []
            priority = 0.45
            if relationship.degree == 1:
                priority += 0.15
            elif relationship.degree == 2:
                priority += 0.08
            if _is_hereditary_condition(event.condition):
                tags.extend([VisibleTag.HEREDITARY_RISK.value, VisibleTag.FAMILY_PATTERN.value])
                priority += 0.15
            if relationship.shared_household or _is_household_condition(event.condition):
                tags.append(VisibleTag.HOUSEHOLD_CONTEXT.value)
                questions.append(
                    "Did the household share diet, water, supplements, exposures, pets, "
                    "or infections?"
                )
            if "gilbert" in event.condition.lower():
                questions.extend(
                    [
                        "Do bilirubin elevations fractionate mostly indirect/unconjugated?",
                        "Do bilirubin spikes track fasting, illness, stress, or dehydration?",
                    ]
                )
                tests.extend(
                    [
                        "repeat hepatic panel with direct/indirect bilirubin if future "
                        "bilirubin is flagged",
                        "consider UGT1A1 context only if it would change decisions",
                    ]
                )
            notes.append(
                HereditaryRiskNote(
                    profile_id=profile,
                    title=f"Family history: {event.condition}",
                    summary=(
                        f"{relation} {relative_id} has {event.condition} marked {event.status}. "
                        "Treat as a risk/context clue, not a diagnosis."
                    ),
                    priority=priority,
                    signals=[f"{relation} {relative_id}: {event.condition} ({event.status})"],
                    suggested_questions=questions,
                    candidate_tests=tests,
                    related_ids=[relationship.relationship_id or "", event.event_id or ""],
                    tags=tags,
                )
            )

    self_events = [
        event for event in events if event.profile_id == profile and _is_active_history(event)
    ]
    bilirubin = _bilirubin_signals(observations)
    if any("gilbert" in event.condition.lower() for event in self_events) and bilirubin:
        notes.append(
            HereditaryRiskNote(
                profile_id=profile,
                title="Gilbert context for bilirubin interpretation",
                summary=(
                    "Profile has Gilbert-syndrome family/history context plus flagged "
                    "bilirubin rows. "
                    "Prioritize fractionated bilirubin/context before overcalling liver injury."
                ),
                priority=0.78,
                signals=[
                    f"{len(bilirubin)} flagged bilirubin observation(s)",
                    "Gilbert context recorded",
                ],
                suggested_questions=[
                    "Were flagged bilirubin rows mostly indirect/unconjugated?",
                    "Was the draw after fasting, illness, stress, dehydration, or heavy exertion?",
                    "Do ALT/AST/ALP/GGT move with bilirubin or stay comparatively separate?",
                ],
                candidate_tests=[
                    "fractionated bilirubin on repeat hepatic panel when clinically useful",
                    "GGT/ALP/ALT/AST context for cholestatic vs hepatocellular pattern",
                ],
                related_ids=[event.event_id or "" for event in self_events]
                + [obs.observation_id for obs in bilirubin],
                tags=[
                    VisibleTag.FAMILY_HISTORY.value,
                    VisibleTag.HEREDITARY_RISK.value,
                    VisibleTag.FAMILY_PATTERN.value,
                    VisibleTag.INFERENCE.value,
                ],
            )
        )

    return notes


def render_family_tree(profile_id: str, relationships: list[FamilyRelationship]) -> str:
    profile = validate_profile_alias(profile_id)
    lines = [f"# Family tree for {profile}"]
    if not relationships:
        lines.append("No family relationships found.")
        return "\n".join(lines)
    for relationship in sorted(
        relationships,
        key=lambda item: (
            item.degree if item.degree is not None else 99,
            item.relation,
            item.relative_id,
        ),
    ):
        other = relationship.other_alias(profile)
        relation = relationship.relation_from(profile)
        household = " · shared household" if relationship.shared_household else ""
        degree = (
            f"degree {relationship.degree}"
            if relationship.degree is not None
            else "non-biological/unknown degree"
        )
        lineage = f" · {relationship.lineage}" if relationship.lineage != "unknown" else ""
        lines.append(f"- {other}: {relation} · {degree}{lineage}{household}")
        if relationship.note:
            lines.append(f"  note: {relationship.note}")
    return "\n".join(lines)


def render_family_history(events: list[FamilyHistoryEvent]) -> str:
    if not events:
        return "No family history events found."
    lines = ["# Family history events"]
    for event in sorted(events, key=lambda item: (item.profile_id, item.condition.lower())):
        onset = f" · onset_age={event.onset_age}" if event.onset_age is not None else ""
        lines.append(
            f"- {event.profile_id}: {event.condition} · {event.status} · "
            f"evidence={event.evidence}{onset}"
        )
        if event.note:
            lines.append(f"  note: {event.note}")
    return "\n".join(lines)


def render_family_risks(notes: list[HereditaryRiskNote], profile_id: str) -> str:
    profile = validate_profile_alias(profile_id)
    lines = [f"# Family risk review for {profile}"]
    if not notes:
        lines.append("No family-history risk notes generated yet.")
        lines.append(
            "Add relatives with `health family add` and history with "
            "`health family condition`."
        )
        return "\n".join(lines)
    for note in sorted(notes, key=lambda item: item.priority, reverse=True):
        lines.append("")
        lines.append(f"[{note.priority:.2f}] {note.title}")
        lines.append(f"Tags: {', '.join(note.tags)}")
        lines.append(note.summary)
        if note.signals:
            lines.append("Signals:")
            for signal in note.signals:
                lines.append(f"- {signal}")
        if note.suggested_questions:
            lines.append("Questions:")
            for question in note.suggested_questions:
                lines.append(f"- {question}")
        if note.candidate_tests:
            lines.append("Candidate tests/context checks:")
            for test in note.candidate_tests:
                lines.append(f"- {test}")
    return "\n".join(lines)
