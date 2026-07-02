from __future__ import annotations

from llm_health.core.enums import VisibleTag
from llm_health.core.models import stable_id
from llm_health.stores import LocalHealthStore

from .knowledge import FAMILY_KEYWORDS, LAB_KEYWORDS, MARKERS, MED_KEYWORDS, MarkerKnowledge
from .models import GenomicInference, VariantCall
from .store import GenomicsStore


def effect_allele_count(variant: VariantCall, knowledge: MarkerKnowledge) -> int:
    effects = knowledge.match_alleles
    if not effects:
        return 0
    return sum(1 for allele in variant.normalized_alleles if allele in effects)


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


def _is_polygenic_research_marker(knowledge: MarkerKnowledge) -> bool:
    return (
        knowledge.finding_type == "research_trait_context"
        or knowledge.reporting_tier == "research_polygenic_trait_marker"
        or knowledge.is_research
    )


def _research_topic_key(knowledge: MarkerKnowledge) -> str:
    hay = " ".join(
        [knowledge.topic, knowledge.match_scope, knowledge.source_family, knowledge.label]
    ).lower()
    if "dyslexia" in hay or "reading disability" in hay:
        return "dyslexia"
    if "adhd" in hay or "attention-deficit" in hay or "attention deficit" in hay:
        return "adhd"
    if "autism" in hay or "asd" in hay:
        return "autism_spectrum"
    return knowledge.topic or knowledge.match_scope or "research_trait"


def _research_topic_label(topic_key: str) -> str:
    if topic_key == "dyslexia":
        return "Dyslexia"
    if topic_key == "adhd":
        return "ADHD"
    if topic_key == "autism_spectrum":
        return "Autism spectrum"
    return topic_key.replace("_", " ").title()


def _research_card_title(topic_key: str) -> str:
    return f"{_research_topic_label(topic_key)} GWAS research marker coverage"


def _research_source_line(
    topic_key: str,
    items: list[tuple[VariantCall, MarkerKnowledge, int]],
) -> str:
    if topic_key == "dyslexia":
        return (
            "Source: Mountford et al. 2025 Translational Psychiatry multivariate GWAS "
            "(80 independent loci; 13 conservatively novel regions)."
        )
    if topic_key == "adhd":
        return "Source: Demontis et al. 2023 Nature Genetics ADHD GWAS (27 loci)."
    if topic_key == "autism_spectrum":
        return "Source: Grove et al. 2019 Nature Genetics ASD GWAS direct GWAS Catalog rows."
    source_family = sorted(
        {knowledge.source_family for _, knowledge, _ in items if knowledge.source_family}
    )
    if source_family:
        return f"Source: {source_family[0]}."
    return "Source: bundled opt-in research GWAS marker list."


def _research_summary(topic_key: str) -> str:
    if topic_key == "dyslexia":
        return (
            "Opt-in dyslexia-associated GWAS marker matches are present. Treat this "
            "only as research context: dyslexia risk is polygenic and strongly shaped "
            "by development, language, instruction, and environment; use family history "
            "and reading/language assessment for any real-world question."
        )
    if topic_key == "adhd":
        return (
            "Opt-in ADHD GWAS marker matches are present. Treat this only as research "
            "context: ADHD traits and impairment are polygenic, developmental, and "
            "strongly shaped by context; use clinical history, impairment, and qualified "
            "assessment for any real-world question."
        )
    if topic_key == "autism_spectrum":
        return (
            "Opt-in autism spectrum GWAS marker matches are present. Treat this only as "
            "research context: autism-spectrum traits are polygenic, heterogeneous, and "
            "developmental; use developmental history, adaptive/communication assessment, "
            "and qualified clinical evaluation for any real-world question."
        )
    return (
        "Opt-in research GWAS marker matches are present. Treat this only as background "
        "research context, not as a diagnosis, screening result, prognosis, or decision rule."
    )


def _research_discussion_target(topic_key: str) -> str:
    if topic_key in {"dyslexia", "adhd", "autism_spectrum"}:
        return (
            "qualified clinician, genetic counselor, psychologist, or developmental "
            "specialist if the research context is decision-relevant"
        )
    return "qualified clinician or genetic counselor if the research context is decision-relevant"


def _build_polygenic_research_cards(
    profile_id: str,
    variants: list[VariantCall],
) -> tuple[list[GenomicInference], set[str]]:
    grouped: dict[str, list[tuple[VariantCall, MarkerKnowledge, int]]] = {}
    skipped_variant_ids: set[str] = set()
    for variant in variants:
        knowledge = MARKERS.get(variant.rsid)
        if not knowledge or not variant.is_called or not _is_polygenic_research_marker(knowledge):
            continue
        count = effect_allele_count(variant, knowledge)
        if count <= 0:
            continue
        group_key = knowledge.match_scope or _research_topic_key(knowledge)
        grouped.setdefault(group_key, []).append((variant, knowledge, count))
        if variant.variant_id:
            skipped_variant_ids.add(variant.variant_id)

    cards: list[GenomicInference] = []
    for group_key, items in grouped.items():
        topic = _research_topic_key(items[0][1])
        label = _research_topic_label(topic)
        allele_total = sum(count for _, _, count in items)
        examples = [
            f"{variant.rsid} {knowledge.gene} reported effect allele count: {count}"
            for variant, knowledge, count in items[:25]
        ]
        hidden = len(items) - len(examples)
        if hidden > 0:
            examples.append(
                f"...and {hidden} additional opt-in {label} GWAS marker matches"
            )
        source_ids = sorted({variant.source_id for variant, _, _ in items if variant.source_id})
        variant_ids = sorted(
            {variant.variant_id or "" for variant, _, _ in items if variant.variant_id}
        )
        evidence = [
            (
                f"Opt-in {label} GWAS research marker list matched "
                f"{len(items)} lead-SNP row(s) with {allele_total} observed reported "
                "effect allele(s)."
            ),
            (
                "This is not a polygenic score, diagnosis, screening result, or reassurance; "
                "individual GWAS lead SNPs have tiny effects."
            ),
            _research_source_line(topic, items),
            *examples,
        ]
        cards.append(
            GenomicInference(
                profile_id=profile_id,
                finding_type="research_trait_context",
                title=_research_card_title(topic),
                summary=_research_summary(topic),
                evidence=evidence,
                source_ids=source_ids,
                variant_ids=variant_ids,
                required_confirmation=True,
                discussion_target=_research_discussion_target(topic),
                confidence="low",
                tags=[
                    VisibleTag.INFERENCE.value,
                    VisibleTag.DATA_GAP.value,
                    "CONFIRM_FIRST",
                    "RESEARCH_CONTEXT",
                ],
                inference_id=stable_id(
                    "ginf",
                    profile_id,
                    "research_trait_context",
                    "dyslexia" if topic == "dyslexia" else group_key,
                    variant_ids,
                ),
            )
        )
    return cards, skipped_variant_ids


def build_cross_references(
    health_store: LocalHealthStore,
    genomics_store: GenomicsStore,
    profile_id: str,
    *,
    include: set[str] | None = None,
) -> list[GenomicInference]:
    include = include or {"labs", "meds", "family"}
    inferences: list[GenomicInference] = []
    variants = genomics_store.variants(profile_id)
    research_cards, research_variant_ids = _build_polygenic_research_cards(profile_id, variants)
    inferences.extend(research_cards)
    for variant in variants:
        if variant.variant_id in research_variant_ids:
            continue
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
        if knowledge.clinical_reference:
            evidence.append(f"Clinical reference: {knowledge.clinical_reference}")
        related_observation_ids: list[str] = []
        tags = sorted(
            {VisibleTag.INFERENCE.value, VisibleTag.DATA_GAP.value, *knowledge.output_tags}
        )
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
