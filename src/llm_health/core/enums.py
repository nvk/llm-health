from __future__ import annotations

from enum import Enum


class TextEnum(str, Enum):
    """String enum that serializes cleanly to JSON."""

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


class VisibleTag(TextEnum):
    OBSERVED = "OBSERVED"
    DERIVED = "DERIVED"
    WEARABLE_CONTEXT = "WEARABLE_CONTEXT"
    CONTEXT = "CONTEXT"
    INFERENCE = "INFERENCE"
    DATA_GAP = "DATA_GAP"
    QA_ISSUE = "QA_ISSUE"
    TEST_CANDIDATE = "TEST_CANDIDATE"
    LOW_INTERVENTION = "LOW_INTERVENTION"
    COLLATERAL_DAMAGE = "COLLATERAL_DAMAGE"
    PROTOCOL_REVIEW = "PROTOCOL_REVIEW"
    RED_FLAG_GATED = "RED_FLAG_GATED"
    SPECIALIST_NOTE = "SPECIALIST_NOTE"


class EvidenceLens(TextEnum):
    MAINSTREAM = "mainstream"
    FRONTIER = "frontier"
    EDGE = "edge"
    CONTRARIAN = "contrarian"
    CAPTURE = "capture"
    INVERSION = "inversion"
    RISK = "risk"


class ReviewLane(TextEnum):
    QUICK = "quick"
    DEEP_RESEARCH = "deep_research"


class ReviewTrigger(TextEnum):
    NEW_RESULT = "new_result"
    NEW_CATEGORY = "new_category"
    FLAGGED_RESULT = "flagged_result"
    LARGE_DELTA = "large_delta"
    PENDING_RESULT = "pending_result"
    QA_ISSUE = "qa_issue"
    CONTEXT_COLLISION = "context_collision"
    OPEN_GAP_MATCH = "open_gap_match"
