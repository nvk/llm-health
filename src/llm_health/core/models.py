from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any
from uuid import uuid4

from .enums import EvidenceLens, ReviewLane, VisibleTag
from .privacy import assert_safe_payload, validate_profile_alias
from .serialization import to_jsonable


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def stable_id(prefix: str, *parts: object) -> str:
    """Create a deterministic artifact id from privacy-safe parts."""

    payload = json.dumps(to_jsonable(parts), sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


def normalize_tag(tag: VisibleTag | str) -> str:
    return tag.value if isinstance(tag, VisibleTag) else str(tag)


@dataclass(frozen=True)
class Observation:
    profile_id: str
    marker: str
    value: float | None = None
    unit: str | None = None
    category: str = "uncategorized"
    observed_on: str = field(default_factory=lambda: date.today().isoformat())
    flag: str | None = None
    reference_range: str | None = None
    comparator: str | None = None
    specimen: str | None = None
    interpretation: str | None = None
    source_id: str = "user_note"
    tags: list[str] = field(default_factory=lambda: [VisibleTag.OBSERVED.value])
    observation_id: str = field(default_factory=lambda: new_id("obs"))
    note: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "profile_id", validate_profile_alias(self.profile_id))
        normalized_tags = sorted(
            {normalize_tag(tag) for tag in self.tags} | {VisibleTag.OBSERVED.value}
        )
        object.__setattr__(self, "tags", normalized_tags)
        assert_safe_payload(self)

    @property
    def is_pending(self) -> bool:
        text = " ".join(str(x).lower() for x in [self.flag, self.note, self.value])
        return "pending" in text or self.value is None

    @property
    def is_flagged(self) -> bool:
        if self.is_pending:
            return False
        if not self.flag:
            return False
        return self.flag.strip().lower() not in {"normal", "none", "ok", ""}

    def to_dict(self) -> dict[str, Any]:
        return to_jsonable(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Observation:
        return cls(**data)


@dataclass(frozen=True)
class NewResultEvent:
    profile_id: str
    observation_ids: list[str]
    source_id: str = "user_note"
    event_id: str = field(default_factory=lambda: new_id("event"))
    created_at: str = field(default_factory=utc_now_iso)
    triggers: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        object.__setattr__(self, "profile_id", validate_profile_alias(self.profile_id))
        assert_safe_payload(self)

    def to_dict(self) -> dict[str, Any]:
        return to_jsonable(self)


@dataclass(frozen=True)
class ContextNote:
    profile_id: str
    subject: str
    status: str
    note: str
    observed_on: str = field(default_factory=lambda: date.today().isoformat())
    source: str = "self_report"
    tags: list[str] = field(default_factory=lambda: [VisibleTag.CONTEXT.value])
    context_id: str = field(default_factory=lambda: new_id("context"))
    created_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        object.__setattr__(self, "profile_id", validate_profile_alias(self.profile_id))
        normalized_tags = sorted(
            {normalize_tag(tag) for tag in self.tags} | {VisibleTag.CONTEXT.value}
        )
        object.__setattr__(self, "tags", normalized_tags)
        assert_safe_payload(self)

    def to_dict(self) -> dict[str, Any]:
        return to_jsonable(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContextNote:
        return cls(**data)


@dataclass(frozen=True)
class EnrolledProfile:
    profile_id: str
    birth_year: int | None = None
    birth_month: int | None = None
    role: str | None = None
    note: str | None = None
    tags: list[str] = field(default_factory=lambda: [VisibleTag.CONTEXT.value])
    created_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        object.__setattr__(self, "profile_id", validate_profile_alias(self.profile_id))
        if self.birth_year is not None and not 1900 <= self.birth_year <= 2100:
            raise ValueError("birth_year must use year precision and be between 1900 and 2100")
        if self.birth_month is not None and not 1 <= self.birth_month <= 12:
            raise ValueError("birth_month must be 1-12 when provided")
        normalized_tags = sorted(
            {normalize_tag(tag) for tag in self.tags} | {VisibleTag.CONTEXT.value}
        )
        object.__setattr__(self, "tags", normalized_tags)
        assert_safe_payload(self)

    @property
    def birth_label(self) -> str:
        if self.birth_year is None:
            return "[not set]"
        if self.birth_month is None:
            return f"{self.birth_year:04d}"
        return f"{self.birth_year:04d}-{self.birth_month:02d}"

    def to_dict(self) -> dict[str, Any]:
        return to_jsonable(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EnrolledProfile:
        return cls(**data)


@dataclass(frozen=True)
class QuickReviewCard:
    profile_id: str
    title: str
    summary: str
    lane: str = ReviewLane.QUICK.value
    priority: float = 0.5
    triggers: list[str] = field(default_factory=list)
    related_observation_ids: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=lambda: [VisibleTag.INFERENCE.value])
    card_id: str = field(default_factory=lambda: new_id("card"))
    created_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        object.__setattr__(self, "profile_id", validate_profile_alias(self.profile_id))
        assert_safe_payload(self)

    def to_dict(self) -> dict[str, Any]:
        return to_jsonable(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QuickReviewCard:
        return cls(**data)


@dataclass(frozen=True)
class TestCandidate:
    __test__ = False

    name: str
    role: str
    information_gain: float = 0.5
    actionability: float = 0.5
    false_positive_risk: float = 0.3
    burden: float = 0.2
    tags: list[str] = field(default_factory=lambda: [VisibleTag.TEST_CANDIDATE.value])

    def score(self) -> float:
        raw = self.information_gain + self.actionability - self.false_positive_risk - self.burden
        return max(0.0, min(1.0, raw / 2.0 + 0.5))

    def to_dict(self) -> dict[str, Any]:
        return to_jsonable(self)


@dataclass(frozen=True)
class DiagnosticGap:
    profile_id: str
    title: str
    gap_type: str
    rationale: str
    status: str = "open"
    priority: float = 0.5
    candidates: list[TestCandidate] = field(default_factory=list)
    context_questions: list[str] = field(default_factory=list)
    related_observation_ids: list[str] = field(default_factory=list)
    tags: list[str] = field(
        default_factory=lambda: [VisibleTag.DATA_GAP.value, VisibleTag.TEST_CANDIDATE.value]
    )
    gap_id: str = field(default_factory=lambda: new_id("gap"))
    created_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        object.__setattr__(self, "profile_id", validate_profile_alias(self.profile_id))
        assert_safe_payload(self)

    def to_dict(self) -> dict[str, Any]:
        return to_jsonable(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DiagnosticGap:
        candidates = [TestCandidate(**item) for item in data.get("candidates", [])]
        merged = dict(data)
        merged["candidates"] = candidates
        return cls(**merged)


@dataclass(frozen=True)
class ResearchJob:
    profile_id: str
    topic: str
    rationale: str
    lenses: list[str] = field(
        default_factory=lambda: [
            EvidenceLens.MAINSTREAM.value,
            EvidenceLens.FRONTIER.value,
            EvidenceLens.EDGE.value,
            EvidenceLens.CONTRARIAN.value,
            EvidenceLens.CAPTURE.value,
            EvidenceLens.RISK.value,
        ]
    )
    status: str = "queued"
    priority: float = 0.5
    related_ids: list[str] = field(default_factory=list)
    triggers: list[str] = field(default_factory=list)
    job_id: str = field(default_factory=lambda: new_id("research"))
    created_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        object.__setattr__(self, "profile_id", validate_profile_alias(self.profile_id))
        assert_safe_payload(self)

    def to_dict(self) -> dict[str, Any]:
        return to_jsonable(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ResearchJob:
        return cls(**data)


@dataclass(frozen=True)
class SpecialistNote:
    profile_id: str
    specialist_id: str
    title: str
    summary: str
    key_findings: list[str] = field(default_factory=list)
    uncertainties: list[str] = field(default_factory=list)
    candidate_tests: list[str] = field(default_factory=list)
    research_topics: list[str] = field(default_factory=list)
    red_flags: list[str] = field(default_factory=list)
    related_ids: list[str] = field(default_factory=list)
    triggers: list[str] = field(default_factory=list)
    tags: list[str] = field(
        default_factory=lambda: [VisibleTag.SPECIALIST_NOTE.value, VisibleTag.INFERENCE.value]
    )
    note_id: str = field(default_factory=lambda: new_id("specialist"))
    created_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        object.__setattr__(self, "profile_id", validate_profile_alias(self.profile_id))
        normalized_tags = sorted(
            {normalize_tag(tag) for tag in self.tags}
            | {VisibleTag.SPECIALIST_NOTE.value, VisibleTag.INFERENCE.value}
        )
        object.__setattr__(self, "tags", normalized_tags)
        assert_safe_payload(self)

    def to_dict(self) -> dict[str, Any]:
        return to_jsonable(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SpecialistNote:
        return cls(**data)


@dataclass(frozen=True)
class ConservativeCareOption:
    target: str
    option_type: str
    rationale: str
    allowed_if: list[str]
    track: list[str]
    escalate_if: list[str]
    review_after: str = "24-72h"
    tags: list[str] = field(
        default_factory=lambda: [VisibleTag.LOW_INTERVENTION.value, VisibleTag.RED_FLAG_GATED.value]
    )

    def __post_init__(self) -> None:
        assert_safe_payload(self)

    def to_dict(self) -> dict[str, Any]:
        return to_jsonable(self)


@dataclass(frozen=True)
class MedicationExposureReview:
    profile_id: str
    active_or_class: str
    indication: str
    necessity_score: str = "unknown"
    collateral_damage: list[str] = field(default_factory=list)
    avoidability_questions: list[str] = field(default_factory=list)
    evidence_tags: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=lambda: [VisibleTag.COLLATERAL_DAMAGE.value])

    def __post_init__(self) -> None:
        object.__setattr__(self, "profile_id", validate_profile_alias(self.profile_id))
        assert_safe_payload(self)

    def to_dict(self) -> dict[str, Any]:
        return to_jsonable(self)


@dataclass(frozen=True)
class PreventiveProtocolReview:
    profile_id: str
    target: str
    conclusion_options: list[str]
    benefit_questions: list[str]
    harm_questions: list[str]
    alternatives: list[str]
    tags: list[str] = field(default_factory=lambda: [VisibleTag.PROTOCOL_REVIEW.value])

    def __post_init__(self) -> None:
        object.__setattr__(self, "profile_id", validate_profile_alias(self.profile_id))
        assert_safe_payload(self)

    def to_dict(self) -> dict[str, Any]:
        return to_jsonable(self)
