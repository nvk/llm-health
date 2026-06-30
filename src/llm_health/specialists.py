from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from llm_health.core.models import (
    ContextNote,
    DiagnosticGap,
    EnrolledProfile,
    Observation,
    SpecialistNote,
    stable_id,
)
from llm_health.core.privacy import PrivacyError, assert_safe_payload


@dataclass(frozen=True)
class SpecialistSpec:
    specialist_id: str
    name: str
    role: str
    when_to_call: tuple[str, ...]
    focuses: tuple[str, ...]
    categories: tuple[str, ...] = ()
    agent_kind: str = "category_agent"
    default_lenses: tuple[str, ...] = (
        "mainstream",
        "frontier",
        "edge",
        "capture",
        "risk",
    )
    aliases: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        assert_safe_payload(self)


SPECIALISTS: tuple[SpecialistSpec, ...] = (
    SpecialistSpec(
        specialist_id="internal_medicine",
        name="Whole-Person / Internal Medicine Synthesis",
        role=(
            "Whole-profile synthesis and routing agent: adult multi-system review, "
            "prioritization, red flags, medication/supplement/habit reconciliation, "
            "diagnostic gap triage, and category-agent handoffs."
        ),
        when_to_call=(
            "default category agent for adult or unclear profiles",
            "multi-system symptoms, conflicting signals, or broad reviews",
            "before choosing which category agents should go deeper",
            "when several domains conflict or need prioritization",
        ),
        focuses=(
            "problem representation",
            "timeline and confounder map",
            "red-flag screen",
            "medication/supplement/habit reconciliation",
            "must-have vs nice-to-have next steps",
            "category-agent handoff questions",
        ),
        categories=("whole-person", "synthesis", "triage", "routing"),
        aliases=("internal", "im", "generalist", "adult", "primary", "whole_person", "synthesis"),
    ),
    SpecialistSpec(
        specialist_id="labs_data_quality",
        name="Labs / Data Quality",
        role=(
            "Lab data quality and interpretation context: units, reference ranges, "
            "specimen/method comparability, pending/flagged rows, deltas, and source QA."
        ),
        when_to_call=("new labs", "flagged rows", "unit/specimen uncertainty", "pending results"),
        focuses=("unit normalization", "source ranges", "method/specimen QA", "delta review"),
        categories=("labs", "data quality", "qa"),
        aliases=("lab_interpreter", "labs", "lab", "qa", "data_quality"),
    ),
    SpecialistSpec(
        specialist_id="cardiometabolic",
        name="Cardiometabolic / Energy",
        role="Lipids, glucose, BP, weight, insulin resistance, ApoB/Lp(a), CAC risk refinement.",
        when_to_call=("lipids/glucose/BP/weight", "family cardiac risk", "metabolic testing"),
        focuses=("blood pressure", "lipids", "glucose", "body composition", "risk refinement"),
        categories=("cardiovascular", "metabolic", "body composition"),
        aliases=("cardio", "metabolic", "heart", "lipids", "glucose", "weight"),
    ),
    SpecialistSpec(
        specialist_id="liver_biliary_gi",
        name="Liver / Biliary / GI",
        role=(
            "ALT/AST/bilirubin, Gilbert context, biliary clues, stool/GI symptoms, "
            "liver confounders."
        ),
        when_to_call=("ALT/AST/bilirubin", "GI context", "Gilbert", "stool/GI markers"),
        focuses=("liver pattern", "bilirubin fraction", "GGT", "GI symptoms", "draw confounders"),
        categories=("liver", "biliary", "gastrointestinal"),
        aliases=("liver_gi", "liver", "gi", "gastro", "bilirubin", "biliary"),
    ),
    SpecialistSpec(
        specialist_id="kidney_urine_hydration",
        name="Kidney / Urine / Hydration",
        role="Creatinine/eGFR, BUN, electrolytes, urinalysis, hydration and kidney-stress context.",
        when_to_call=("kidney markers", "urine markers", "electrolytes", "hydration context"),
        focuses=("eGFR/creatinine", "urinalysis", "albumin/protein", "electrolytes", "hydration"),
        categories=("kidney", "urine", "hydration", "electrolytes"),
        aliases=("kidney", "renal", "urine", "hydration", "electrolytes"),
    ),
    SpecialistSpec(
        specialist_id="hormones_endocrine",
        name="Hormones / Endocrine",
        role="Thyroid, sex hormones, adrenal/cortisol context, glucose-regulatory hormones.",
        when_to_call=("thyroid", "sex hormones", "fertility/libido", "cortisol/adrenal context"),
        focuses=(
            "thyroid axis",
            "sex-hormone context",
            "timing/cycle",
            "medication/supplement effects",
        ),
        categories=("hormones", "endocrine", "thyroid", "adrenal"),
        aliases=("hormones", "endocrine", "thyroid", "testosterone", "estrogen", "cortisol"),
    ),
    SpecialistSpec(
        specialist_id="immune_inflammation",
        name="Immune / Inflammation",
        role="CBC pattern, CRP/ESR, infection/inflammation context, allergy/autoimmune clues.",
        when_to_call=("CBC shifts", "CRP/ESR", "infection/inflammation", "immune symptoms"),
        focuses=(
            "CBC differential",
            "inflammatory markers",
            "infection timing",
            "immune/allergy clues",
        ),
        categories=("immune", "inflammation", "infection", "autoimmune"),
        aliases=("immune", "inflammation", "inflammatory", "infection", "allergy", "autoimmune"),
    ),
    SpecialistSpec(
        specialist_id="nutrients_hematology",
        name="Nutrients / Hematology",
        role="Iron/ferritin, B12/folate, vitamin D, minerals, anemia/CBC-nutrient patterns.",
        when_to_call=("nutrient labs", "anemia", "CBC pattern", "diet/supplement context"),
        focuses=("iron/ferritin", "B12/folate", "vitamin D", "minerals", "CBC pattern"),
        categories=("nutrients", "hematology", "minerals", "vitamins"),
        aliases=("nutrients", "nutrition", "hematology", "iron", "ferritin", "b12", "vitamin_d"),
    ),
    SpecialistSpec(
        specialist_id="toxins_exposures",
        name="Toxins / Exposures",
        role=(
            "Mercury/lead/arsenic/cadmium, specimen/unit normalization, exposure "
            "inventory, repeat strategy."
        ),
        when_to_call=("heavy metals", "mercury/lead/arsenic/cadmium", "exposure inventory"),
        focuses=("specimen type", "unit normalization", "exposure windows", "repeat strategy"),
        categories=("toxins", "exposures", "heavy metals", "environment"),
        aliases=(
            "toxicology_heavy_metals",
            "toxicology",
            "heavy_metals",
            "metals",
            "mercury",
            "lead",
            "arsenic",
            "cadmium",
            "exposures",
        ),
    ),
    SpecialistSpec(
        specialist_id="meds_supplements",
        name="Meds / Supplements / Collateral",
        role=(
            "Medication and supplement necessity, side effects, interactions, "
            "microbiome/gut/liver/kidney/cascade risks."
        ),
        when_to_call=(
            "new medication",
            "supplement stack",
            "antibiotic/NSAID/acetaminophen",
            "side effects",
        ),
        focuses=("avoidability", "collateral lanes", "interactions", "monitoring windows"),
        categories=("medications", "supplements", "collateral damage"),
        aliases=(
            "medication_collateral",
            "medication",
            "medications",
            "meds",
            "supplements",
            "drugs",
            "collateral",
        ),
    ),
    SpecialistSpec(
        specialist_id="habits_lifestyle",
        name="Habits / Lifestyle / Environment",
        role=(
            "Smoking, alcohol, drugs, food, activity, light, stress, work/travel "
            "rhythm, household/environment context."
        ),
        when_to_call=(
            "habits/substances",
            "activity/food/light",
            "exposure confounders",
            "work/travel rhythm",
        ),
        focuses=("dose/frequency/route", "food", "movement", "substances", "environment"),
        categories=("habits", "lifestyle", "environment", "substances"),
        aliases=("lifestyle_habits", "lifestyle", "habits", "substances", "environment"),
    ),
    SpecialistSpec(
        specialist_id="sleep_circadian",
        name="Sleep / Circadian",
        role=(
            "Sleep duration/quality, snoring/apnea clues, light timing, "
            "shift/travel rhythm, recovery signals."
        ),
        when_to_call=("sleep", "fatigue", "snoring/apnea", "shift work", "travel/light timing"),
        focuses=("sleep timing", "sleep quality", "light exposure", "recovery", "apnea clues"),
        categories=("sleep", "circadian", "recovery"),
        aliases=("sleep", "circadian", "fatigue", "recovery"),
    ),
    SpecialistSpec(
        specialist_id="neuro_mood_cognition",
        name="Neuro / Mood / Cognition",
        role=(
            "Headache, dizziness, neuropathy, cognition, mood/energy, "
            "medication/exposure confounders."
        ),
        when_to_call=(
            "neurological symptoms",
            "mood/cognition",
            "headache/dizziness",
            "neuropathy",
        ),
        focuses=("neuro symptoms", "mood/energy", "cognition", "exposure/medication confounders"),
        categories=("neurology", "mood", "cognition"),
        aliases=("neuro", "neurology", "mood", "cognition", "brain", "headache", "neuropathy"),
    ),
    SpecialistSpec(
        specialist_id="family_hereditary",
        name="Family / Hereditary Context",
        role=(
            "Family history, household comparisons, inherited risk clues, "
            "alias-only family enrollment prompts."
        ),
        when_to_call=(
            "family history",
            "hereditary concern",
            "household comparison",
            "family enrollment",
        ),
        focuses=("family history", "household patterns", "genetic clues", "alias-only references"),
        categories=("family", "hereditary", "household"),
        aliases=("family", "hereditary", "genetic", "genetics", "household"),
    ),
    SpecialistSpec(
        specialist_id="pediatric_growth",
        name="Pediatric / Growth Context",
        role="Child profiles, growth/development context, pediatric screening/test stewardship.",
        when_to_call=("child profile", "growth/development", "pediatric family context"),
        focuses=(
            "growth curve",
            "development",
            "sleep/behavior",
            "lead exposure",
            "family context",
        ),
        categories=("pediatric", "growth", "development"),
        aliases=("pediatrics", "pediatric", "child", "children", "kids", "growth"),
    ),
    SpecialistSpec(
        specialist_id="test_gap_steward",
        name="Test Gap Steward",
        role=(
            "Converts uncertainty into context questions and test candidates with actionability, "
            "burden, false-positive, and cascade-risk tradeoffs."
        ),
        when_to_call=("open diagnostic gaps", "what to test next", "broad panel pressure"),
        focuses=("context-first gaps", "test candidates", "false positives", "actionability"),
        categories=("diagnostic gaps", "test candidates", "stewardship"),
        aliases=("diagnostic_gap_steward", "gaps", "gap", "tests", "test_steward", "testing"),
    ),
    SpecialistSpec(
        specialist_id="research_librarian",
        name="Research Librarian",
        role="Queues literature/product/protocol research and separates retrieval from synthesis.",
        when_to_call=("deep research", "current best ideas", "paper retrieval", "claim updates"),
        focuses=("retrieval ladder", "source quality", "research jobs", "claim extraction"),
        categories=("research", "retrieval", "papers"),
        aliases=("research", "papers", "librarian"),
    ),
    SpecialistSpec(
        specialist_id="research_skeptic",
        name="Research Skeptic / Capture Auditor",
        role=(
            "Endpoint quality, conflicts, capture, mechanism gaps, uncertainty, "
            "external validity, cascade risk."
        ),
        when_to_call=(
            "high-stakes conclusion",
            "guideline conflict",
            "weak endpoint",
            "capture risk",
        ),
        focuses=("absolute effects", "funding", "endpoint games", "external validity", "risk"),
        categories=("evidence", "skepticism", "capture", "methods"),
        aliases=("evidence_skeptic", "skeptic", "capture", "auditor", "evidence", "methods"),
    ),
    SpecialistSpec(
        specialist_id="red_flag_checker",
        name="Red-Flag / Escalation Checker",
        role="Do-not-miss symptom/lab patterns and escalation thresholds for conservative care.",
        when_to_call=("acute symptoms", "watchful waiting", "severe/worsening signs"),
        focuses=("red flags", "stop rules", "urgent escalation", "safety thresholds"),
        categories=("safety", "red flags", "escalation"),
        aliases=("red_flags", "safety", "escalation", "urgent"),
    ),
)

_SPEC_BY_ID = {spec.specialist_id: spec for spec in SPECIALISTS}
_ALIAS_TO_ID = {
    alias: spec.specialist_id
    for spec in SPECIALISTS
    for alias in (spec.specialist_id, *spec.aliases)
}


def list_specialists() -> tuple[SpecialistSpec, ...]:
    return SPECIALISTS


def resolve_specialist_id(value: str) -> str:
    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    if normalized == "auto":
        return "auto"
    specialist_id = _ALIAS_TO_ID.get(normalized)
    if not specialist_id:
        valid = ", ".join(["auto", *sorted(_SPEC_BY_ID)])
        raise PrivacyError(f"unknown category agent {value!r}; choose one of: {valid}")
    return specialist_id


def route_specialists(
    profile: EnrolledProfile,
    observations: list[Observation],
    gaps: list[DiagnosticGap],
    context_notes: list[ContextNote],
    *,
    topic: str | None = None,
) -> list[str]:
    topic_text = (topic or "").lower()
    marker_text = " ".join(
        f"{obs.marker} {obs.category} {obs.flag or ''} {obs.note or ''}".lower()
        for obs in observations
    )
    gap_text = " ".join(
        f"{gap.title} {gap.rationale} {gap.gap_type} ".lower()
        + " ".join(candidate.name for candidate in gap.candidates).lower()
        for gap in gaps
    )
    context_text = " ".join(
        f"{note.subject} {note.status} {note.note}".lower() for note in context_notes
    )
    haystack = " ".join([topic_text, marker_text, gap_text, context_text])
    routed = ["internal_medicine"]

    if observations or any(token in haystack for token in ["lab", "range", "unit", "flag"]):
        routed.append("labs_data_quality")
    if any(
        token in haystack
        for token in [
            "lipid",
            "cholesterol",
            "ldl",
            "hdl",
            "triglyceride",
            "glucose",
            "a1c",
            "insulin",
            "bp",
            "blood pressure",
            "weight",
        ]
    ):
        routed.append("cardiometabolic")
    if any(token in haystack for token in ["alt", "ast", "bilirubin", "ggt", "liver", "gi"]):
        routed.append("liver_biliary_gi")
    if any(
        token in haystack
        for token in [
            "kidney",
            "renal",
            "creatinine",
            "egfr",
            "bun",
            "urine",
            "urinalysis",
            "electrolyte",
        ]
    ):
        routed.append("kidney_urine_hydration")
    if any(
        token in haystack
        for token in [
            "thyroid",
            "tsh",
            "t3",
            "t4",
            "hormone",
            "testosterone",
            "estrogen",
            "cortisol",
        ]
    ):
        routed.append("hormones_endocrine")
    if any(
        token in haystack
        for token in [
            "crp",
            "esr",
            "cbc",
            "wbc",
            "neutrophil",
            "lymphocyte",
            "immune",
            "inflammation",
            "infection",
        ]
    ):
        routed.append("immune_inflammation")
    if any(
        token in haystack
        for token in [
            "iron",
            "ferritin",
            "b12",
            "folate",
            "vitamin",
            "mineral",
            "magnesium",
            "anemia",
        ]
    ):
        routed.append("nutrients_hematology")
    if any(
        token in haystack
        for token in ["mercury", "lead", "arsenic", "cadmium", "heavy metal", "toxin"]
    ):
        routed.append("toxins_exposures")
    if _is_child(profile):
        routed.append("pediatric_growth")
    if any(
        token in haystack
        for token in [
            "antibiotic",
            "nsaid",
            "acetaminophen",
            "albendazole",
            "med",
            "supplement",
            "drug",
        ]
    ):
        routed.append("meds_supplements")
    if any(
        token in haystack
        for token in [
            "smok",
            "nicotine",
            "alcohol",
            "cannabis",
            "habit",
            "food",
            "exercise",
            "travel",
            "environment",
        ]
    ):
        routed.append("habits_lifestyle")
    if any(
        token in haystack
        for token in ["sleep", "circadian", "fatigue", "snoring", "apnea", "shift"]
    ):
        routed.append("sleep_circadian")
    if any(
        token in haystack
        for token in ["headache", "dizziness", "neuropathy", "neuro", "mood", "cognition", "brain"]
    ):
        routed.append("neuro_mood_cognition")
    if any(
        token in haystack for token in ["family", "hereditary", "genetic", "genetics", "household"]
    ):
        routed.append("family_hereditary")
    if gaps or any(token in haystack for token in ["gap", "test", "screen", "battery"]):
        routed.append("test_gap_steward")
    if any(
        token in haystack
        for token in ["research", "paper", "study", "evidence", "current best", "pubmed"]
    ):
        routed.append("research_librarian")
    if any(
        token in haystack for token in ["capture", "skeptic", "guideline", "conflict", "endpoint"]
    ):
        routed.append("research_skeptic")
    if any(token in haystack for token in ["urgent", "severe", "worsening", "red flag", "acute"]):
        routed.append("red_flag_checker")

    return _unique(routed)


def create_specialist_notes(
    profile: EnrolledProfile,
    observations: list[Observation],
    gaps: list[DiagnosticGap],
    context_notes: list[ContextNote],
    *,
    specialist: str = "auto",
    topic: str | None = None,
) -> list[SpecialistNote]:
    specialist_id = resolve_specialist_id(specialist)
    specialist_ids = (
        route_specialists(profile, observations, gaps, context_notes, topic=topic)
        if specialist_id == "auto"
        else [specialist_id]
    )
    return [
        _consult_one(
            _SPEC_BY_ID[item],
            profile,
            observations,
            gaps,
            context_notes,
            topic=topic,
            routed_by="auto" if specialist_id == "auto" else "manual",
        )
        for item in specialist_ids
    ]


def render_specialists(specs: tuple[SpecialistSpec, ...] = SPECIALISTS) -> str:
    lines = ["# llm-health category agents", ""]
    lines.append(
        "These are broad category agents, not rigid medical silos. "
        "The `specialists` command remains for compatibility."
    )
    lines.append("")
    for spec in specs:
        aliases = f" aliases: {', '.join(spec.aliases)}" if spec.aliases else ""
        lines.append(f"## {spec.name} (`{spec.specialist_id}`){aliases}")
        lines.append(f"kind: {spec.agent_kind}")
        if spec.categories:
            lines.append("categories: " + ", ".join(spec.categories))
        lines.append(f"role: {spec.role}")
        lines.append("when to call:")
        for item in spec.when_to_call:
            lines.append(f"- {item}")
        lines.append("focuses: " + ", ".join(spec.focuses))
        lines.append("lenses: " + ", ".join(spec.default_lenses))
        lines.append("")
    return "\n".join(lines).rstrip()


def render_specialist_notes(notes: list[SpecialistNote]) -> str:
    if not notes:
        return "No specialist notes found."
    lines: list[str] = []
    for index, note in enumerate(notes):
        if index:
            lines.append("")
        lines.append(f"# {note.title}")
        lines.append(f"category_agent: {note.specialist_id} · profile: {note.profile_id}")
        lines.append(f"tags: {', '.join(note.tags)}")
        lines.append(f"summary: {note.summary}")
        _append_section(lines, "key findings", note.key_findings)
        _append_section(lines, "uncertainties", note.uncertainties)
        _append_section(lines, "candidate tests", note.candidate_tests)
        _append_section(lines, "research topics", note.research_topics)
        _append_section(lines, "red flags / escalation", note.red_flags)
        if note.triggers:
            lines.append("triggers: " + ", ".join(note.triggers))
    return "\n".join(lines)


def _consult_one(
    spec: SpecialistSpec,
    profile: EnrolledProfile,
    observations: list[Observation],
    gaps: list[DiagnosticGap],
    context_notes: list[ContextNote],
    *,
    topic: str | None,
    routed_by: str,
) -> SpecialistNote:
    relevant_observations = _relevant_observations(spec.specialist_id, observations)
    relevant_gaps = _relevant_gaps(spec.specialist_id, gaps)
    related_ids = [obs.observation_id for obs in relevant_observations] + [
        gap.gap_id for gap in relevant_gaps
    ]
    summary, findings, uncertainties, tests, research, red_flags = _specialist_output(
        spec, profile, relevant_observations, relevant_gaps, context_notes, topic=topic
    )
    tags = ["SPECIALIST_NOTE", "INFERENCE"]
    if uncertainties:
        tags.append("DATA_GAP")
    if tests:
        tags.append("TEST_CANDIDATE")
    return SpecialistNote(
        profile_id=profile.profile_id,
        specialist_id=spec.specialist_id,
        title=f"{spec.name} consult",
        summary=summary,
        key_findings=findings,
        uncertainties=uncertainties,
        candidate_tests=tests,
        research_topics=research,
        red_flags=red_flags,
        related_ids=related_ids,
        triggers=[routed_by, *(topic and [f"topic:{topic}"] or [])],
        tags=tags,
        note_id=stable_id(
            "specialist",
            profile.profile_id,
            spec.specialist_id,
            topic or "auto",
            sorted(related_ids),
        ),
    )


def _specialist_output(
    spec: SpecialistSpec,
    profile: EnrolledProfile,
    observations: list[Observation],
    gaps: list[DiagnosticGap],
    context_notes: list[ContextNote],
    *,
    topic: str | None,
) -> tuple[list[str] | str, list[str], list[str], list[str], list[str], list[str]]:
    profile_fit = _profile_fit(profile)
    obs_count = len(observations)
    gap_count = len(gaps)
    context_count = len(context_notes)
    topic_text = f" Topic: {topic}." if topic else ""
    summary = (
        f"{spec.name} reviewed {obs_count} relevant observation(s), {gap_count} gap(s), "
        f"and {context_count} context note(s) for {profile_fit}.{topic_text}"
    )
    findings = _generic_findings(spec, observations, gaps, context_notes)
    uncertainties = _generic_uncertainties(spec, observations, gaps, context_notes)
    tests = _generic_tests(spec.specialist_id, gaps)
    research = _generic_research(spec, topic)
    red_flags = _generic_red_flags(spec.specialist_id)

    if spec.specialist_id == "internal_medicine":
        summary = (
            f"Whole-Person / Internal Medicine synthesis for {profile_fit}: organize the "
            "profile into an active problem list, timeline/confounder map, "
            "medication/supplement/habit reconciliation, red-flag screen, and prioritized "
            "category-agent handoffs."
        )
        findings = [
            f"Whole-profile context available: {len(observations)} observation(s), "
            f"{len(gaps)} open/computed gap(s), {len(context_notes)} context note(s).",
            "Start broad, then narrow: separate confirmed findings, uncertain memories, and gaps.",
            "Use category-agent consults as inputs; do not hide disagreement during synthesis.",
        ]
        uncertainties = [
            "Which symptoms/problems are active versus historical or resolved?",
            (
                "Are habits, substances, medications, supplements, family history, "
                "and exposures current?"
            ),
            "Which next test would change a decision rather than merely add data?",
        ]
        tests = [
            "profile completeness and test-battery review before broad panels",
            *tests,
        ]
        research = [
            "whole-person synthesis: profile-specific must-have vs nice-to-have next steps",
            *research,
        ]
        red_flags = [
            (
                "new severe/worsening symptoms, neurological deficits, chest pain, "
                "severe abdominal pain, syncope, major bleeding, or rapidly progressive "
                "illness should bypass routine review"
            ),
            *red_flags,
        ]
    return summary, findings, uncertainties, tests, research, red_flags


def _generic_findings(
    spec: SpecialistSpec,
    observations: list[Observation],
    gaps: list[DiagnosticGap],
    context_notes: list[ContextNote],
) -> list[str]:
    findings: list[str] = []
    if observations:
        latest = max(observations, key=lambda obs: (obs.observed_on, obs.marker))
        findings.append(
            f"Latest relevant observation: {latest.marker} on {latest.observed_on}; "
            f"status {'flagged' if latest.is_flagged else 'not source-noted/pending-aware'}."
        )
    else:
        findings.append(
            "No directly relevant observations found yet; context-first review remains useful."
        )
    if gaps:
        findings.append(f"Open relevant gaps: {', '.join(gap.title for gap in gaps[:3])}.")
    if context_notes:
        findings.append(
            "Self-reported context exists and should be checked before trend conclusions."
        )
    findings.append(f"Primary focus: {', '.join(spec.focuses[:3])}.")
    return findings


def _generic_uncertainties(
    spec: SpecialistSpec,
    observations: list[Observation],
    gaps: list[DiagnosticGap],
    context_notes: list[ContextNote],
) -> list[str]:
    uncertainties = [
        "Are timeline, dose/frequency, route, and recent changes known for relevant exposures?",
    ]
    if observations and spec.specialist_id in {
        "labs_data_quality",
        "liver_biliary_gi",
        "kidney_urine_hydration",
        "toxins_exposures",
        "hormones_endocrine",
    }:
        uncertainties.append(
            "Are units, specimen, lab method, and reference ranges comparable over time?"
        )
    if gaps:
        uncertainties.extend(question for gap in gaps for question in gap.context_questions[:2])
    if not context_notes:
        uncertainties.append("No self-reported context notes were found for this consult.")
    return _unique(uncertainties)[:6]


def _generic_tests(specialist_id: str, gaps: list[DiagnosticGap]) -> list[str]:
    tests = [candidate.name for gap in gaps for candidate in gap.candidates]
    if specialist_id == "labs_data_quality":
        tests.extend(["source range/specimen/method reconciliation", "unit-normalized trend table"])
    elif specialist_id == "cardiometabolic":
        tests.extend(["home blood pressure", "lipid panel + ApoB/Lp(a)", "HbA1c + fasting glucose"])
    elif specialist_id == "liver_biliary_gi":
        tests.extend(["repeat hepatic panel", "GGT", "direct + indirect bilirubin"])
    elif specialist_id == "kidney_urine_hydration":
        tests.extend(["CMP with creatinine/eGFR", "urinalysis", "urine albumin/creatinine ratio"])
    elif specialist_id == "hormones_endocrine":
        tests.extend(["TSH + free T4", "timed hormone panel matched to question/context"])
    elif specialist_id == "immune_inflammation":
        tests.extend(["CBC with differential", "CRP/ESR matched to symptom timing"])
    elif specialist_id == "nutrients_hematology":
        tests.extend(["CBC + ferritin/iron studies", "B12/folate", "25-OH vitamin D"])
    elif specialist_id == "toxins_exposures":
        tests.extend(["specimen/unit confirmation before repeat heavy-metal testing"])
    elif specialist_id == "pediatric_growth":
        tests.extend(["growth/development context", "vision/hearing/dental/sleep screen"])
    elif specialist_id == "meds_supplements":
        tests.extend(
            [
                "active medication/supplement stack inventory",
                "interaction and monitoring-window review",
            ]
        )
    elif specialist_id == "habits_lifestyle":
        tests.extend(["7-day sleep/food/activity/substance context log"])
    elif specialist_id == "sleep_circadian":
        tests.extend(["sleep diary or wearable sleep window review", "snoring/apnea risk screen"])
    elif specialist_id == "neuro_mood_cognition":
        tests.extend(["symptom timeline with trigger/relief map"])
    elif specialist_id == "family_hereditary":
        tests.extend(["alias-only family history inventory", "household comparison context"])
    elif specialist_id == "test_gap_steward":
        tests.append("health test-battery --category gaps")
    return _unique(tests)[:8]


def _generic_research(spec: SpecialistSpec, topic: str | None) -> list[str]:
    base = topic or spec.name
    return [f"{base}: current evidence across mainstream/frontier/edge/capture/risk lenses"]


def _generic_red_flags(specialist_id: str) -> list[str]:
    if specialist_id == "liver_biliary_gi":
        return [
            "jaundice with dark urine/pale stool, severe abdominal pain, confusion, or bleeding"
        ]
    if specialist_id == "cardiometabolic":
        return ["chest pain, syncope, severe shortness of breath, or stroke-like symptoms"]
    if specialist_id == "kidney_urine_hydration":
        return ["markedly reduced urination, severe dehydration, confusion, or severe flank pain"]
    if specialist_id == "immune_inflammation":
        return ["high fever with deterioration, breathing trouble, confusion, sepsis signs"]
    if specialist_id == "toxins_exposures":
        return ["neurological symptoms or known acute high-dose exposure"]
    if specialist_id == "meds_supplements":
        return [
            "allergic reaction signs, severe side effects, black stools, jaundice, or confusion"
        ]
    if specialist_id == "sleep_circadian":
        return [
            "falling asleep while driving, severe breathing pauses, or sudden dangerous sleepiness"
        ]
    if specialist_id == "neuro_mood_cognition":
        return ["new weakness, facial droop, seizure, worst headache, or suicidal thoughts"]
    if specialist_id == "pediatric_growth":
        return ["developmental regression, dehydration, respiratory distress, or severe lethargy"]
    if specialist_id == "red_flag_checker":
        return [
            "severe, rapidly worsening, neurological, bleeding, chest, breathing, or sepsis signs"
        ]
    return []


def _relevant_observations(
    specialist_id: str, observations: list[Observation]
) -> list[Observation]:
    if specialist_id in {"internal_medicine", "labs_data_quality"}:
        return observations[-50:]
    tokens = _SPECIALIST_TOKENS.get(specialist_id, ())
    if not tokens:
        return observations[-20:]
    return [obs for obs in observations if _has_any(f"{obs.marker} {obs.category}", tokens)]


def _relevant_gaps(specialist_id: str, gaps: list[DiagnosticGap]) -> list[DiagnosticGap]:
    if specialist_id in {"internal_medicine", "test_gap_steward"}:
        return gaps
    tokens = _SPECIALIST_TOKENS.get(specialist_id, ())
    return [gap for gap in gaps if _has_any(f"{gap.title} {gap.rationale} {gap.gap_type}", tokens)]


def _has_any(text: str, tokens: tuple[str, ...]) -> bool:
    haystack = text.lower()
    return any(token in haystack for token in tokens)


def _is_child(profile: EnrolledProfile) -> bool:
    if profile.role and "child" in profile.role.lower():
        return True
    if profile.birth_year is None:
        return False
    return date.today().year - profile.birth_year < 18


def _profile_fit(profile: EnrolledProfile) -> str:
    if profile.birth_year is None:
        age = "age unknown"
    else:
        age = f"~{max(0, date.today().year - profile.birth_year)}y"
    role = profile.role or "role unknown"
    return f"{profile.profile_id} ({profile.birth_label}, {age}, {role})"


def _append_section(lines: list[str], title: str, values: list[str]) -> None:
    if not values:
        return
    lines.append(f"{title}:")
    for value in values:
        lines.append(f"- {value}")


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


_SPECIALIST_TOKENS: dict[str, tuple[str, ...]] = {
    "labs_data_quality": ("lab", "unit", "range", "flag", "pending"),
    "cardiometabolic": (
        "lipid",
        "cholesterol",
        "ldl",
        "hdl",
        "triglyceride",
        "glucose",
        "a1c",
        "insulin",
        "weight",
        "blood pressure",
    ),
    "liver_biliary_gi": ("alt", "ast", "bilirubin", "ggt", "liver", "gi", "stool"),
    "kidney_urine_hydration": (
        "kidney",
        "renal",
        "creatinine",
        "egfr",
        "bun",
        "urine",
        "albumin",
        "electrolyte",
    ),
    "hormones_endocrine": (
        "thyroid",
        "tsh",
        "t3",
        "t4",
        "hormone",
        "testosterone",
        "estrogen",
        "cortisol",
    ),
    "immune_inflammation": (
        "crp",
        "esr",
        "cbc",
        "wbc",
        "neutrophil",
        "lymphocyte",
        "immune",
        "inflammation",
        "infection",
    ),
    "nutrients_hematology": (
        "iron",
        "ferritin",
        "b12",
        "folate",
        "vitamin",
        "mineral",
        "magnesium",
        "anemia",
    ),
    "toxins_exposures": ("mercury", "lead", "arsenic", "cadmium", "metal", "toxin"),
    "pediatric_growth": ("child", "pediatric", "growth", "development"),
    "meds_supplements": (
        "medication",
        "supplement",
        "antibiotic",
        "nsaid",
        "acetaminophen",
        "albendazole",
    ),
    "habits_lifestyle": (
        "smok",
        "nicotine",
        "alcohol",
        "cannabis",
        "drug",
        "habit",
        "food",
        "exercise",
        "environment",
    ),
    "sleep_circadian": ("sleep", "circadian", "fatigue", "snoring", "apnea", "shift"),
    "neuro_mood_cognition": (
        "headache",
        "dizziness",
        "neuropathy",
        "neuro",
        "mood",
        "cognition",
        "brain",
    ),
    "family_hereditary": ("family", "hereditary", "genetic", "genetics", "household"),
    "test_gap_steward": ("gap", "test", "candidate", "unclear"),
    "research_librarian": ("research", "paper", "study", "evidence", "pubmed"),
    "research_skeptic": ("capture", "bias", "conflict", "guideline", "endpoint"),
    "red_flag_checker": ("urgent", "severe", "worsening", "acute", "red flag"),
}
