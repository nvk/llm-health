from __future__ import annotations

from llm_health.core.enums import VisibleTag
from llm_health.core.models import stable_id
from llm_health.stores import LocalHealthStore

from .knowledge import FAMILY_KEYWORDS, LAB_KEYWORDS, MARKERS, MED_KEYWORDS, MarkerKnowledge
from .models import GenomicInference, VariantCall
from .store import GenomicsStore


def effect_allele_count(variant: VariantCall, knowledge: MarkerKnowledge) -> int:
    effect = knowledge.effect_allele.upper()
    return sum(1 for allele in variant.normalized_alleles if allele == effect)


def _observation_text(row) -> str:
    return " ".join(
        str(part or "")
        for part in [row.marker, row.category, row.flag, row.interpretation, row.note]
    ).lower()


def _context_text(row) -> str:
    return " ".join(str(part or "") for part in [row.subject, row.status, row.note]).lower()


def _family_text(row) -> str:
    return " ".join(
        str(part or "") for part in [row.condition, row.status, row.evidence, row.note]
    ).lower()


def _matching_observations(store: LocalHealthStore, profile_id: str, topic: str) -> list:
    keywords = LAB_KEYWORDS.get(topic, ())
    if not keywords:
        return []
    matches = []
    for observation in store.observations(profile_id):
        text = _observation_text(observation)
        if any(keyword in text for keyword in keywords):
            matches.append(observation)
    return matches


def _family_contexts(store: LocalHealthStore, profile_id: str, topic: str) -> list:
    keywords = FAMILY_KEYWORDS.get(topic, ())
    if not keywords:
        return []
    relationships = store.family_relationships(profile_id)
    relatives = {relationship.other_alias(profile_id) for relationship in relationships}
    matches = []
    for event in store.family_history_events():
        if event.profile_id != profile_id and event.profile_id not in relatives:
            continue
        text = _family_text(event)
        if any(keyword in text for keyword in keywords):
            matches.append(event)
    return matches


def _med_contexts(store: LocalHealthStore, profile_id: str, topic: str) -> list:
    keywords = MED_KEYWORDS.get(topic, ())
    if not keywords:
        return []
    matches = []
    for note in store.context_notes(profile_id):
        text = _context_text(note)
        if any(keyword in text for keyword in keywords):
            matches.append(note)
    return matches


def build_cross_references(
    health_store: LocalHealthStore,
    genomics_store: GenomicsStore,
    profile_id: str,
    *,
    include: set[str] | None = None,
) -> list[GenomicInference]:
    include = include or {"labs", "meds", "family"}
    inferences: list[GenomicInference] = []
    for variant in genomics_store.variants(profile_id):
        knowledge = MARKERS.get(variant.rsid)
        if not knowledge or not variant.is_called:
            continue
        count = effect_allele_count(variant, knowledge)
        if count <= 0:
            continue
        evidence = [
            f"{variant.rsid} {knowledge.gene} effect allele observed: {count}",
            knowledge.evidence_gate,
        ]
        related_observation_ids: list[str] = []
        tags = [VisibleTag.INFERENCE.value, VisibleTag.DATA_GAP.value]
        confidence = knowledge.confidence
        summary = knowledge.summary
        title = knowledge.label
        if knowledge.finding_type == "pgx":
            med_contexts = _med_contexts(health_store, profile_id, knowledge.topic)
            if med_contexts and "meds" in include:
                evidence.append(f"Medication/context notes matched: {len(med_contexts)}")
                summary += " Medication context exists in llm-health; review with a clinician."
                confidence = "medium"
            else:
                evidence.append("No matching active medication context found in stored notes.")
                summary += " Keep for future medication reconciliation rather than action now."
            discussion_target = knowledge.discussion_target
        else:
            observations = _matching_observations(health_store, profile_id, knowledge.topic)
            if observations and "labs" in include:
                related_observation_ids = [row.observation_id for row in observations[:20]]
                evidence.append(f"Related lab/context observations matched: {len(observations)}")
                summary += " Existing observations make this worth a confirmation-first review."
                confidence = "medium"
            else:
                evidence.append(
                    "No matching lab context found yet; this remains background context."
                )
            discussion_target = knowledge.discussion_target
        family_contexts = (
            _family_contexts(health_store, profile_id, knowledge.topic)
            if "family" in include
            else []
        )
        if family_contexts:
            evidence.append(f"Family history/context matched: {len(family_contexts)}")
            summary += (
                " Family history/context is present; keep inherited and shared-household "
                "explanations separate."
            )
            if confidence == "low":
                confidence = "medium"
        inference_id = stable_id(
            "ginf",
            profile_id,
            knowledge.finding_type,
            variant.rsid,
            variant.reported_genotype,
            related_observation_ids,
        )
        inferences.append(
            GenomicInference(
                profile_id=profile_id,
                finding_type=knowledge.finding_type,
                title=title,
                summary=summary,
                evidence=evidence,
                source_ids=[variant.source_id],
                variant_ids=[variant.variant_id or ""],
                related_observation_ids=related_observation_ids,
                required_confirmation=True,
                discussion_target=discussion_target,
                confidence=confidence,
                tags=tags,
                inference_id=inference_id,
            )
        )
    return inferences
