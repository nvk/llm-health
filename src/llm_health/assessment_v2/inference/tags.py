"""Visible tags used by the inference and dashboard layers."""

from __future__ import annotations

from enum import StrEnum


class EvidenceTag(StrEnum):
    OBSERVED = "OBSERVED"
    DERIVED = "DERIVED"
    WEARABLE_CONTEXT = "WEARABLE_CONTEXT"
    CONTEXT = "CONTEXT"
    INFERENCE = "INFERENCE"
    DATA_GAP = "DATA_GAP"
    QA_ISSUE = "QA_ISSUE"
