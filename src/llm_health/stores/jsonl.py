from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from llm_health.core.models import (
    ContextNote,
    DiagnosticGap,
    EnrolledProfile,
    NewResultEvent,
    Observation,
    QuickReviewCard,
    ResearchJob,
    SpecialistNote,
)
from llm_health.core.privacy import (
    DEFAULT_PROFILE_ALIASES,
    assert_safe_payload,
    validate_profile_alias,
)

COLLECTIONS = {
    "observations": "observations.jsonl",
    "review_events": "review_events.jsonl",
    "quick_review_cards": "quick_review_cards.jsonl",
    "diagnostic_gaps": "diagnostic_gaps.jsonl",
    "research_jobs": "research_jobs.jsonl",
    "specialist_notes": "specialist_notes.jsonl",
    "context_notes": "context_notes.jsonl",
    "profiles": "profiles.jsonl",
    "operator_drafts": "operator_drafts.jsonl",
    "audit_traces": "audit_traces.jsonl",
}


class LocalHealthStore:
    """Dependency-light JSONL store for scaffold and agent artifacts."""

    def __init__(self, root: str | Path = ".llm-health") -> None:
        self.root = Path(root)

    def init(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        for filename in COLLECTIONS.values():
            (self.root / filename).touch(exist_ok=True)
        manifest = self.root / "manifest.json"
        if not manifest.exists():
            manifest.write_text(
                json.dumps(
                    {
                        "schema": "llm-health-jsonl-v0",
                        "collections": COLLECTIONS,
                        "privacy": "alias-only; no raw source paths or filenames",
                        "agreement": "health-facing commands require agreement.json acceptance",
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            )

    def path_for(self, collection: str) -> Path:
        if collection not in COLLECTIONS:
            raise KeyError(f"unknown collection {collection!r}")
        return self.root / COLLECTIONS[collection]

    def append(self, collection: str, record: dict[str, Any]) -> None:
        self.init()
        assert_safe_payload(record, field_name=collection)
        with self.path_for(collection).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")

    def append_unique(self, collection: str, record: dict[str, Any], key: str) -> bool:
        """Append a record only if no existing row has the same key value."""

        self.init()
        key_value = record.get(key)
        if key_value is None:
            self.append(collection, record)
            return True
        for existing in self.read(collection):
            if existing.get(key) == key_value:
                return False
        self.append(collection, record)
        return True

    def upsert_unique(self, collection: str, record: dict[str, Any], key: str) -> bool:
        """Insert or replace one record by key.

        Observations are upserted so schema enrichments from a later sync, such as reference
        ranges or specimen context, can backfill existing private HUB rows without duplicating
        observations.
        """

        self.init()
        assert_safe_payload(record, field_name=collection)
        key_value = record.get(key)
        if key_value is None:
            self.append(collection, record)
            return True

        rows = self.read(collection)
        changed = False
        replaced = False
        updated: list[dict[str, Any]] = []
        for existing in rows:
            if existing.get(key) == key_value:
                replaced = True
                if existing != record:
                    changed = True
                updated.append(record)
            else:
                updated.append(existing)
        if not replaced:
            updated.append(record)
            changed = True
        if changed:
            with self.path_for(collection).open("w", encoding="utf-8") as handle:
                for row in updated:
                    handle.write(json.dumps(row, sort_keys=True) + "\n")
        return changed

    def read(self, collection: str) -> list[dict[str, Any]]:
        path = self.path_for(collection)
        if not path.exists():
            return []
        records: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return records

    def read_profile(self, collection: str, profile_id: str) -> list[dict[str, Any]]:
        profile = validate_profile_alias(profile_id)
        return [row for row in self.read(collection) if row.get("profile_id") == profile]

    def append_observation(self, observation: Observation) -> None:
        self.upsert_unique("observations", observation.to_dict(), "observation_id")

    def append_observations(self, observations: Iterable[Observation]) -> None:
        for observation in observations:
            self.append_observation(observation)

    def observations(self, profile_id: str | None = None) -> list[Observation]:
        rows = (
            self.read("observations")
            if profile_id is None
            else self.read_profile("observations", profile_id)
        )
        return [Observation.from_dict(row) for row in rows]

    def enroll_profile(self, profile: EnrolledProfile) -> None:
        self.upsert_unique("profiles", profile.to_dict(), "profile_id")

    def enrolled_profiles(self, *, include_defaults: bool = True) -> list[EnrolledProfile]:
        profiles = [EnrolledProfile.from_dict(row) for row in self.read("profiles")]
        if include_defaults:
            existing = {profile.profile_id for profile in profiles}
            for profile_id in sorted(DEFAULT_PROFILE_ALIASES - existing):
                profiles.append(EnrolledProfile(profile_id=profile_id, role="built-in"))
        return sorted(profiles, key=lambda item: item.profile_id)

    def profile_ids(self) -> set[str]:
        return {profile.profile_id for profile in self.enrolled_profiles(include_defaults=True)}

    def profile_exists(self, profile_id: str) -> bool:
        profile = validate_profile_alias(profile_id)
        return profile in self.profile_ids()

    def append_review_event(self, event: NewResultEvent) -> None:
        self.append_unique("review_events", event.to_dict(), "event_id")

    def append_quick_review_card(self, card: QuickReviewCard) -> None:
        self.append_unique("quick_review_cards", card.to_dict(), "card_id")

    def quick_review_cards(self, profile_id: str | None = None) -> list[QuickReviewCard]:
        rows = (
            self.read("quick_review_cards")
            if profile_id is None
            else self.read_profile("quick_review_cards", profile_id)
        )
        return [QuickReviewCard.from_dict(row) for row in rows]

    def append_diagnostic_gap(self, gap: DiagnosticGap) -> None:
        self.append_unique("diagnostic_gaps", gap.to_dict(), "gap_id")

    def diagnostic_gaps(self, profile_id: str | None = None) -> list[DiagnosticGap]:
        rows = (
            self.read("diagnostic_gaps")
            if profile_id is None
            else self.read_profile("diagnostic_gaps", profile_id)
        )
        return [DiagnosticGap.from_dict(row) for row in rows]

    def append_research_job(self, job: ResearchJob) -> None:
        self.append_unique("research_jobs", job.to_dict(), "job_id")

    def research_jobs(self, profile_id: str | None = None) -> list[ResearchJob]:
        rows = (
            self.read("research_jobs")
            if profile_id is None
            else self.read_profile("research_jobs", profile_id)
        )
        return [ResearchJob.from_dict(row) for row in rows]

    def append_specialist_note(self, note: SpecialistNote) -> None:
        self.append_unique("specialist_notes", note.to_dict(), "note_id")

    def specialist_notes(
        self, profile_id: str | None = None, *, specialist_id: str | None = None
    ) -> list[SpecialistNote]:
        rows = (
            self.read("specialist_notes")
            if profile_id is None
            else self.read_profile("specialist_notes", profile_id)
        )
        if specialist_id:
            needle = specialist_id.strip().lower()
            rows = [
                row
                for row in rows
                if needle in str(row.get("specialist_id", "")).strip().lower()
            ]
        return [SpecialistNote.from_dict(row) for row in rows]

    def append_context_note(self, note: ContextNote) -> None:
        self.upsert_unique("context_notes", note.to_dict(), "context_id")

    def context_notes(
        self, profile_id: str | None = None, *, subject: str | None = None
    ) -> list[ContextNote]:
        rows = (
            self.read("context_notes")
            if profile_id is None
            else self.read_profile("context_notes", profile_id)
        )
        if subject:
            needle = subject.strip().lower()
            rows = [row for row in rows if needle in str(row.get("subject", "")).lower()]
        return [ContextNote.from_dict(row) for row in rows]

    def append_operator_draft(self, draft) -> None:
        self.upsert_unique("operator_drafts", draft.to_dict(), "draft_id")

    def operator_drafts(
        self, profile_id: str | None = None, *, status: str | None = None
    ) -> list:
        from llm_health.operator_runtime import OperatorDraft

        rows = (
            self.read("operator_drafts")
            if profile_id is None
            else self.read_profile("operator_drafts", profile_id)
        )
        if status:
            rows = [row for row in rows if row.get("status") == status]
        return [OperatorDraft.from_dict(row) for row in rows]

    def operator_draft(self, draft_id: str):
        for row in self.read("operator_drafts"):
            if row.get("draft_id") == draft_id:
                from llm_health.operator_runtime import OperatorDraft

                return OperatorDraft.from_dict(row)
        return None

    def append_audit_trace(self, trace) -> None:
        self.append_unique("audit_traces", trace.to_dict(), "trace_id")

    def audit_traces(self, profile_id: str | None = None) -> list:
        from llm_health.operator_runtime import AuditTrace

        rows = (
            self.read("audit_traces")
            if profile_id is None
            else self.read_profile("audit_traces", profile_id)
        )
        return [AuditTrace.from_dict(row) for row in rows]
