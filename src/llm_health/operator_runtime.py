from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, replace
from typing import Any, Literal

from llm_health.core.enums import VisibleTag
from llm_health.core.models import new_id, stable_id, utc_now_iso
from llm_health.core.privacy import assert_safe_payload, validate_profile_alias
from llm_health.core.serialization import to_jsonable
from llm_health.stores import LocalHealthStore

DraftStatus = Literal["draft", "reviewed", "finalized", "archived"]


@dataclass(frozen=True)
class OperatorStep:
    title: str
    tool: str
    status: str = "planned"
    reads: list[str] = field(default_factory=list)
    writes: list[str] = field(default_factory=list)
    privacy_note: str = "alias-only; no raw source payloads"
    step_id: str | None = None

    def __post_init__(self) -> None:
        if self.step_id is None:
            object.__setattr__(self, "step_id", stable_id("step", self.title, self.tool))
        assert_safe_payload(self)

    def to_dict(self) -> dict[str, Any]:
        return to_jsonable(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OperatorStep:
        return cls(**data)


@dataclass(frozen=True)
class OperatorDraft:
    profile_id: str
    intent: str
    title: str
    summary: str
    artifact_type: str = "review"
    status: DraftStatus = "draft"
    steps: list[OperatorStep] = field(default_factory=list)
    read_scope: list[str] = field(default_factory=list)
    write_scope: list[str] = field(default_factory=list)
    approval_required: bool = True
    tags: list[str] = field(default_factory=lambda: [VisibleTag.INFERENCE.value])
    draft_id: str = field(default_factory=lambda: new_id("draft"))
    created_at: str = field(default_factory=utc_now_iso)
    finalized_at: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "profile_id", validate_profile_alias(self.profile_id))
        normalized_tags = sorted({str(tag) for tag in self.tags} | {VisibleTag.INFERENCE.value})
        object.__setattr__(self, "tags", normalized_tags)
        assert_safe_payload(self)

    def with_status(self, status: DraftStatus) -> OperatorDraft:
        finalized_at = utc_now_iso() if status == "finalized" else self.finalized_at
        return replace(self, status=status, finalized_at=finalized_at)

    def to_dict(self) -> dict[str, Any]:
        return to_jsonable(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OperatorDraft:
        merged = dict(data)
        merged["steps"] = [OperatorStep.from_dict(item) for item in data.get("steps", [])]
        return cls(**merged)


@dataclass(frozen=True)
class AuditTrace:
    profile_id: str
    event: str
    action: str
    status: str
    draft_id: str | None = None
    fingerprints: dict[str, str] = field(default_factory=dict)
    tags: list[str] = field(default_factory=lambda: [VisibleTag.CONTEXT.value])
    trace_id: str = field(default_factory=lambda: new_id("trace"))
    created_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        object.__setattr__(self, "profile_id", validate_profile_alias(self.profile_id))
        normalized_tags = sorted({str(tag) for tag in self.tags} | {VisibleTag.CONTEXT.value})
        object.__setattr__(self, "tags", normalized_tags)
        assert_safe_payload(self)

    def to_dict(self) -> dict[str, Any]:
        return to_jsonable(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AuditTrace:
        return cls(**data)


def _classify_intent(intent: str) -> tuple[str, str]:
    needle = intent.lower()
    def has(*terms: str) -> bool:
        return any(re.search(rf"\b{re.escape(term)}\b", needle) for term in terms)

    if has("packet", "clinician", "doctor visit", "bring"):
        return "packet", "Draft review packet"
    if has("med", "drug", "protocol", "vaccine", "supplement"):
        return "protocol_review", "Draft intervention/protocol review"
    if has("research", "paper", "evidence", "source"):
        return "research_plan", "Draft research workflow"
    if has("gap", "gaps", "test", "tests", "battery", "missing"):
        return "diagnostic_gap_review", "Draft diagnostic-gap review"
    return "review", "Draft health review"


def _fingerprint_payload(payload: object) -> str:
    text = json.dumps(to_jsonable(payload), sort_keys=True, separators=(",", ":"))
    return stable_id("fp", text)


def build_operator_draft(store: LocalHealthStore, profile_id: str, intent: str) -> OperatorDraft:
    profile = validate_profile_alias(profile_id)
    observations = store.observations(profile)
    cards = store.quick_review_cards(profile)
    gaps = store.diagnostic_gaps(profile)
    context_notes = store.context_notes(profile)
    artifact_type, title = _classify_intent(intent)

    read_scope = [
        f"profile={profile}",
        f"observations={len(observations)}",
        f"quick_review_cards={len(cards)}",
        f"diagnostic_gaps={len(gaps)}",
        f"context_notes={len(context_notes)}",
    ]
    steps = [
        OperatorStep(
            title="Resolve alias profile and own-risk gate",
            tool="LocalHealthStore.profile_exists",
            status="completed",
            reads=["profiles"],
        ),
        OperatorStep(
            title="Read observations and context without changing canonical data",
            tool="LocalHealthStore.observations/context_notes",
            status="completed",
            reads=["observations", "context_notes"],
        ),
        OperatorStep(
            title="Read review cards and open diagnostic gaps",
            tool="LocalHealthStore.quick_review_cards/diagnostic_gaps",
            status="completed",
            reads=["quick_review_cards", "diagnostic_gaps"],
        ),
        OperatorStep(
            title="Draft artifact for user review",
            tool="llm_health.operator_runtime.build_operator_draft",
            status="completed",
            reads=["fingerprints", "counts"],
            writes=["operator_drafts", "audit_traces"],
            privacy_note="draft stores counts, plan, and alias-safe intent only",
        ),
        OperatorStep(
            title="Wait for explicit finalize approval before downstream writes",
            tool="health operator finalize --approve",
            status="planned",
            writes=["operator_drafts.status", "audit_traces"],
            privacy_note="no wiki/packet/protocol commit happens during draft creation",
        ),
    ]
    summary = (
        f"Visible operator draft for {profile}: {intent}. "
        f"Read {len(observations)} observation(s), {len(cards)} quick card(s), "
        f"{len(gaps)} diagnostic gap(s), and {len(context_notes)} context note(s). "
        "No downstream health artifact is finalized until explicit approval."
    )
    return OperatorDraft(
        profile_id=profile,
        intent=intent,
        title=title,
        summary=summary,
        artifact_type=artifact_type,
        steps=steps,
        read_scope=read_scope,
        write_scope=["operator_drafts", "audit_traces", "downstream writes require finalize"],
    )


def trace_for_draft(draft: OperatorDraft, *, event: str, status: str) -> AuditTrace:
    step_fingerprints = {
        step.step_id
        or stable_id("step", step.title, step.tool): _fingerprint_payload(step.to_dict())
        for step in draft.steps
    }
    return AuditTrace(
        profile_id=draft.profile_id,
        draft_id=draft.draft_id,
        event=event,
        action=draft.artifact_type,
        status=status,
        fingerprints={
            "draft": _fingerprint_payload(
                {
                    "draft_id": draft.draft_id,
                    "profile_id": draft.profile_id,
                    "intent": draft.intent,
                    "artifact_type": draft.artifact_type,
                    "read_scope": draft.read_scope,
                }
            ),
            **step_fingerprints,
        },
    )


def render_operator_draft(draft: OperatorDraft) -> str:
    lines = [
        f"# {draft.title}",
        f"draft_id: {draft.draft_id}",
        f"profile: {draft.profile_id}",
        f"status: {draft.status}",
        f"artifact_type: {draft.artifact_type}",
        f"approval_required: {str(draft.approval_required).lower()}",
        f"intent: {draft.intent}",
        "",
        draft.summary,
        "",
        "## Read scope",
    ]
    for item in draft.read_scope:
        lines.append(f"- {item}")
    lines.extend(["", "## Write scope"])
    for item in draft.write_scope:
        lines.append(f"- {item}")
    lines.extend(["", "## Visible plan"])
    for index, step in enumerate(draft.steps, start=1):
        reads = f" reads={','.join(step.reads)}" if step.reads else ""
        writes = f" writes={','.join(step.writes)}" if step.writes else ""
        lines.append(f"{index}. [{step.status}] {step.title} · {step.tool}{reads}{writes}")
        lines.append(f"   privacy: {step.privacy_note}")
    if draft.status == "draft":
        lines.extend(
            [
                "",
                "Finalize command:",
                f"health operator finalize --draft-id {draft.draft_id} --approve",
            ]
        )
    return "\n".join(lines)


def render_audit_trace(trace: AuditTrace) -> str:
    lines = [
        f"trace_id: {trace.trace_id}",
        f"profile: {trace.profile_id}",
        f"draft_id: {trace.draft_id or '[none]'}",
        f"event: {trace.event}",
        f"action: {trace.action}",
        f"status: {trace.status}",
        f"created_at: {trace.created_at}",
        "fingerprints:",
    ]
    for key, value in sorted(trace.fingerprints.items()):
        lines.append(f"- {key}: {value}")
    return "\n".join(lines)
