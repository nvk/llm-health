"""Core typed records for v2."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from llm_health.assessment_v2.inference.tags import EvidenceTag

ProfileId = Literal["rod", "cara"]


class SourceRef(BaseModel):
    """A de-identified source pointer."""

    kind: str
    ref: str


class InferenceEvent(BaseModel):
    """Reviewable finding, context item, derived result, gap, or QA issue."""

    id: str
    tag: EvidenceTag
    profile_id: ProfileId
    subject_area: str
    statement: str
    event_date: date | None = None
    inputs: list[str] = Field(default_factory=list)
    confidence: Literal["low", "medium", "high"] = "low"
    review_status: str = "draft"
    caveats: list[str] = Field(default_factory=list)
    sources: list[SourceRef] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class QAIssue(BaseModel):
    """A data-quality issue to review before plotting or inference."""

    id: str
    severity: Literal["info", "warning", "error"] = "warning"
    table: str
    row_ref: str | None = None
    metric: str | None = None
    message: str
    action: str = "review"
