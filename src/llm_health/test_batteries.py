from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal

from llm_health.core.models import (
    DiagnosticGap,
    EnrolledProfile,
    Observation,
    ResearchJob,
    stable_id,
)
from llm_health.core.privacy import assert_safe_payload

Priority = Literal["must-have", "high", "medium", "low", "nice-to-have"]
Difficulty = Literal["self-report", "home", "standard-lab", "specialty-lab", "imaging", "invasive"]

_PRIORITY_RANK: dict[str, int] = {
    "must-have": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
    "nice-to-have": 4,
}
_SCOPE_MAX_RANK = {"core": 1, "expanded": 3, "complete": 4}


@dataclass(frozen=True)
class TestBatteryCandidate:
    name: str
    category: str
    priority: Priority
    difficulty: Difficulty
    cadence: str
    why: str
    profile_fit: str
    status: str = "candidate"
    lens: str = "mainstream"
    source_hint: str = ""
    tags: tuple[str, ...] = ("TEST_CANDIDATE",)

    def __post_init__(self) -> None:
        assert_safe_payload(self)

    @property
    def priority_rank(self) -> int:
        return _PRIORITY_RANK[self.priority]


@dataclass(frozen=True)
class TestBattery:
    profile_id: str
    profile_summary: str
    scope: str
    category: str
    candidates: tuple[TestBatteryCandidate, ...]
    source_notes: tuple[str, ...]
    research_topics: tuple[str, ...] = field(default_factory=tuple)


class TestBatteryEngine:
    """Profile-aware test-battery candidates integrated with diagnostic gaps.

    This engine suggests reviewable TEST_CANDIDATE rows, not lab orders. It blends four lanes:
    profile completeness, broadly useful baseline domains, age/context screening domains, and the
    deterministic diagnostic-gap layer.
    """

    def generate(
        self,
        profile: EnrolledProfile,
        observations: list[Observation],
        gaps: list[DiagnosticGap],
        *,
        scope: str = "expanded",
        category: str = "all",
        include_gaps: bool = True,
    ) -> TestBattery:
        normalized_scope = _normalize_scope(scope)
        normalized_category = _normalize_category(category)
        age = _age_years(profile)
        observed = _observed_markers(observations)
        candidates: list[TestBatteryCandidate] = []

        candidates.extend(_profile_completeness(profile))
        if _is_child(profile, age):
            candidates.extend(_child_candidates(profile, age, observed))
        else:
            candidates.extend(_adult_candidates(profile, age, observed))
        candidates.extend(_contextual_candidates(profile, age, observed, observations))
        if include_gaps:
            candidates.extend(_gap_candidates(gaps))

        filtered = tuple(
            sorted(
                (
                    candidate
                    for candidate in candidates
                    if candidate.priority_rank <= _SCOPE_MAX_RANK[normalized_scope]
                    and _category_matches(candidate, normalized_category)
                ),
                key=lambda item: (
                    item.priority_rank,
                    _CATEGORY_ORDER.get(item.category.lower(), 99),
                    item.category.lower(),
                    item.difficulty,
                    item.name.lower(),
                ),
            )
        )
        return TestBattery(
            profile_id=profile.profile_id,
            profile_summary=_profile_summary(profile, age),
            scope=normalized_scope,
            category=normalized_category,
            candidates=filtered,
            source_notes=TEST_BATTERY_SOURCE_NOTES,
            research_topics=_research_topics(profile, normalized_scope, normalized_category),
        )

    def research_jobs_for(self, battery: TestBattery) -> list[ResearchJob]:
        jobs: list[ResearchJob] = []
        for topic in battery.research_topics:
            jobs.append(
                ResearchJob(
                    profile_id=battery.profile_id,
                    topic=topic,
                    rationale=(
                        "Refresh current evidence for a profile-aware test battery, separating "
                        "must-have, gap-driven, exposure-based, and nice-to-have candidates."
                    ),
                    status="queued",
                    priority=0.58,
                    triggers=["test_battery", battery.scope, battery.category],
                    job_id=stable_id(
                        "research", battery.profile_id, "test_battery", battery.scope, topic
                    ),
                )
            )
        return jobs


def render_test_battery(battery: TestBattery, *, sources: bool = False) -> str:
    lines = [
        f"# Test battery candidates for {battery.profile_id}",
        f"profile: {battery.profile_summary}",
        f"scope: {battery.scope} · category: {battery.category}",
        (
            "note: TEST_CANDIDATE artifacts only — candidates to review, prioritize, and discuss; "
            "not lab orders."
        ),
        "",
    ]
    if not battery.candidates:
        lines.append(
            "No candidates matched this scope/category. "
            "Try --scope complete --category all."
        )
    else:
        current_category = ""
        for candidate in battery.candidates:
            if candidate.category != current_category:
                current_category = candidate.category
                lines.append(f"## {current_category}")
            lines.append(
                "- "
                f"[{candidate.priority} · {candidate.difficulty} · {candidate.status}] "
                f"{candidate.name}"
            )
            lines.append(f"  why: {candidate.why}")
            lines.append(f"  fit: {candidate.profile_fit}")
            lines.append(f"  cadence: {candidate.cadence}")
            lines.append(f"  lens/source: {candidate.lens}; {candidate.source_hint}".rstrip())
    if battery.research_topics:
        lines.append("")
        lines.append("## Research refresh queue candidates")
        for topic in battery.research_topics:
            lines.append(f"- {topic}")
    if sources:
        lines.append("")
        lines.append("## Source/rationale notes")
        for note in battery.source_notes:
            lines.append(f"- {note}")
        lines.append("")
        lines.append("## Source links")
        for label, url in TEST_BATTERY_SOURCE_LINKS:
            lines.append(f"- {label}: {url}")
    return "\n".join(lines)


TEST_BATTERY_SOURCE_NOTES: tuple[str, ...] = (
    (
        "Preventive-screening recommendations such as USPSTF A/B items provide a mainstream "
        "minimum floor for age/risk triggers, but llm-health keeps them as one evidence lens."
    ),
    (
        "AHA Life's Essential 8 supports recurring cardiovascular domains: activity, nicotine, "
        "sleep, weight, lipids/non-HDL, glucose/A1c, and blood pressure."
    ),
    (
        "ADA Standards of Care are updated annually and should refresh the glucose/diabetes "
        "screening lane when the agent does deeper research."
    ),
    (
        "Lp(a) is largely genetic and increasingly recommended as an at-least-once adult test; "
        "family/cascade context matters."
    ),
    (
        "Hormone, heavy-metal, autoimmune, infectious, and imaging tests should be symptom-, "
        "risk-, exposure-, family-history-, or gap-driven rather than broad reflex panels."
    ),
)

TEST_BATTERY_SOURCE_LINKS: tuple[tuple[str, str], ...] = (
    (
        "USPSTF A/B preventive recommendations",
        "https://www.uspreventiveservicestaskforce.org/uspstf/recommendation-topics/"
        "uspstf-a-and-b-recommendations",
    ),
    (
        "American Heart Association Life's Essential 8",
        "https://www.heart.org/en/healthy-living/healthy-lifestyle/lifes-essential-8",
    ),
    (
        "ADA Standards of Care in Diabetes",
        "https://professional.diabetes.org/standards-of-care",
    ),
    (
        "AHA Lipoprotein(a)",
        "https://www.heart.org/en/health-topics/cholesterol/genetic-conditions/lipoprotein-a",
    ),
    (
        "Endocrine Society testosterone guideline",
        "https://www.endocrine.org/clinical-practice-guidelines/testosterone-therapy",
    ),
    ("CDC lead testing", "https://www.cdc.gov/lead-prevention/testing/index.html"),
)


def _normalize_scope(scope: str) -> str:
    normalized = scope.strip().lower()
    if normalized not in _SCOPE_MAX_RANK:
        raise ValueError("scope must be one of: core, expanded, complete")
    return normalized


def _normalize_category(category: str) -> str:
    normalized = category.strip().lower().replace("_", "-")
    return normalized or "all"


def _age_years(profile: EnrolledProfile) -> int | None:
    if profile.birth_year is None:
        return None
    age = date.today().year - profile.birth_year
    return max(0, age)


def _is_child(profile: EnrolledProfile, age: int | None) -> bool:
    role = (profile.role or "").lower()
    return "child" in role or (age is not None and age < 18)


def _profile_summary(profile: EnrolledProfile, age: int | None) -> str:
    age_label = f"~{age}y" if age is not None else "age unknown"
    role = profile.role or "role unknown"
    return f"birth {profile.birth_label}; {age_label}; {role}"


def _observed_markers(observations: list[Observation]) -> dict[str, str]:
    observed: dict[str, str] = {}
    for observation in observations:
        haystacks = {observation.marker.lower(), observation.category.lower()}
        for key in _MARKER_ALIASES:
            if any(alias in text for alias in _MARKER_ALIASES[key] for text in haystacks):
                observed.setdefault(key, observation.observed_on)
    return observed


def _status_for(key: str, observed: dict[str, str]) -> str:
    return f"seen {observed[key]}" if key in observed else "missing/currentness unknown"


def _profile_completeness(profile: EnrolledProfile) -> list[TestBatteryCandidate]:
    candidates: list[TestBatteryCandidate] = []
    if profile.birth_year is None:
        candidates.append(
            TestBatteryCandidate(
                name="profile birth year/month precision",
                category="profile completeness",
                priority="must-have",
                difficulty="self-report",
                cadence="once, then update only if wrong",
                why="age gates many screening and test-battery decisions",
                profile_fit="profile is missing birth year",
                status="missing",
                lens="context-first",
                source_hint="required before age-dependent batteries",
            )
        )
    if not profile.role:
        candidates.append(
            TestBatteryCandidate(
                name="role/relationship/context label",
                category="profile completeness",
                priority="high",
                difficulty="self-report",
                cadence="once, then update if context changes",
                why="child/adult/pregnancy/family-reference status changes test interpretation",
                profile_fit="profile role is missing",
                status="missing",
                lens="context-first",
                source_hint="enrollment layer",
            )
        )
    return candidates


def _adult_candidates(
    profile: EnrolledProfile, age: int | None, observed: dict[str, str]
) -> list[TestBatteryCandidate]:
    fit = _adult_fit(age)
    return [
        _candidate(
            "home blood pressure",
            "foundational vitals",
            "must-have",
            "home",
            "weekly/monthly if stable; more often when changing",
            "blood pressure is a high-signal, low-burden cardiovascular metric",
            fit,
            "bp",
            observed,
            "mainstream",
            "AHA/USPSTF cardiovascular screening lane",
        ),
        _candidate(
            "weight + waist circumference",
            "foundational vitals",
            "must-have",
            "home",
            "weekly/monthly trend, not obsessively daily unless useful",
            "anthropometrics anchor metabolic, sleep, liver, and medication-effect interpretation",
            fit,
            "weight",
            observed,
            "mainstream",
            "AHA/ADA metabolic-risk lane",
        ),
        _candidate(
            "CBC with differential",
            "foundational labs",
            "high",
            "standard-lab",
            "annual or when symptoms/results change",
            "screens anemia, infection/inflammation clues, platelets, and medication effects",
            fit,
            "cbc",
            observed,
            "mainstream",
            "general baseline + gap context",
        ),
        _candidate(
            "comprehensive metabolic panel (CMP)",
            "foundational labs",
            "high",
            "standard-lab",
            "annual or when liver/kidney/electrolyte context changes",
            "covers liver enzymes, bilirubin, kidney function, electrolytes, protein/albumin",
            fit,
            "cmp",
            observed,
            "mainstream",
            "general baseline + liver/kidney gap context",
        ),
        _candidate(
            "fasting lipid panel with non-HDL calculation",
            "cardiometabolic",
            "high",
            "standard-lab",
            "annual to every few years depending on risk/change",
            "lipids/non-HDL are core cardiovascular risk inputs",
            fit,
            "lipids",
            observed,
            "mainstream",
            "AHA Life's Essential 8 cholesterol lane",
        ),
        _candidate(
            "ApoB",
            "cardiometabolic",
            "medium",
            "standard-lab",
            "once for baseline; repeat when lipid strategy changes",
            "particle-number proxy that can clarify discordant LDL/non-HDL/triglyceride patterns",
            fit,
            "apob",
            observed,
            "frontier/mainstream",
            "advanced lipid risk refinement",
        ),
        _candidate(
            "Lipoprotein(a) [Lp(a)]",
            "cardiometabolic",
            "high",
            "standard-lab",
            "once in adulthood unless special context changes interpretation",
            "largely inherited risk marker; useful for family/cascade context",
            fit,
            "lpa",
            observed,
            "frontier/mainstream",
            "AHA/NLA/ACC once-in-adulthood lane",
        ),
        _candidate(
            "HbA1c + fasting glucose",
            "glucose metabolism",
            "high",
            "standard-lab",
            "annual to every 3 years depending on age, weight, and risk",
            "screens glycemic trend; A1c and fasting glucose catch different failure modes",
            fit,
            "a1c",
            observed,
            "mainstream",
            "ADA/USPSTF glucose screening lane",
        ),
        _candidate(
            "fasting insulin or HOMA-IR inputs",
            "glucose metabolism",
            "nice-to-have",
            "standard-lab",
            "baseline and after major metabolic interventions",
            "can reveal insulin-resistance direction before A1c moves, but interpretation is noisy",
            fit,
            "insulin",
            observed,
            "edge/frontier",
            "useful n-of-1 metabolic context, not a universal mainstream screen",
        ),
        _candidate(
            "urinalysis + urine albumin/creatinine ratio",
            "kidney/urine",
            "medium",
            "standard-lab",
            "annual if metabolic/BP risk; otherwise as context warrants",
            "kidney/urine signals can precede obvious serum creatinine changes",
            fit,
            "urine-acr",
            observed,
            "mainstream",
            "kidney/metabolic risk lane",
        ),
        _candidate(
            "TSH with reflex free T4 if abnormal",
            "thyroid/hormones",
            "medium",
            "standard-lab",
            "baseline, symptom-triggered, or every few years if risk/family history",
            "thyroid status can affect lipids, weight, mood, temperature tolerance, and fertility",
            fit,
            "tsh",
            observed,
            "mainstream",
            "symptom/family-history driven endocrine lane",
        ),
        _candidate(
            "ferritin + iron/TIBC/transferrin saturation",
            "nutrient/hematology",
            "medium",
            "standard-lab",
            "baseline; repeat when anemia, fatigue, bleeding, diet, or overload context exists",
            "iron deficiency/overload can affect energy, liver, hair, restless legs, and exercise",
            fit,
            "iron",
            observed,
            "mainstream",
            "hematology/nutrient context",
        ),
        _candidate(
            "vitamin B12 ± methylmalonic acid",
            "nutrient/hematology",
            "low",
            "standard-lab",
            "diet/symptom/medication-triggered; repeat after intervention",
            "neuropathy, cognition, anemia, metformin/PPI, or low-animal-food context can matter",
            fit,
            "b12",
            observed,
            "mainstream/frontier",
            "context-driven nutrient lane",
        ),
        _candidate(
            "25-OH vitamin D",
            "nutrient/hematology",
            "low",
            "standard-lab",
            "seasonal/baseline if low sun, bone risk, symptoms, or supplementation",
            "useful for supplementation calibration, but not a universal high-priority screen",
            fit,
            "vitamin-d",
            observed,
            "mainstream/frontier",
            "context-driven nutrient lane",
        ),
        _candidate(
            "hs-CRP",
            "inflammation",
            "low",
            "standard-lab",
            "baseline or when cardiovascular/inflammatory context warrants",
            "low-cost inflammation signal; nonspecific and confounded by recent illness/exercise",
            fit,
            "hscrp",
            observed,
            "frontier/mainstream",
            "risk-refinement context",
        ),
        _candidate(
            "sleep apnea screen → home sleep test if positive",
            "physiology/sleep",
            "medium",
            "home",
            "screen annually or when snoring, fatigue, BP, weight, or wearable clues appear",
            "sleep-disordered breathing can drive BP, glucose, fatigue, mood, and hormones",
            fit,
            "sleep",
            observed,
            "mainstream/frontier",
            "context questionnaire before device test",
        ),
        _candidate(
            "CAC scan",
            "cardiometabolic imaging",
            "nice-to-have",
            "imaging",
            "age/risk-triggered; not a frequent repeat test",
            "can reclassify cardiovascular risk when blood markers/family history are ambiguous",
            fit,
            "cac",
            observed,
            "frontier/mainstream",
            "adult risk-refinement, radiation/cost tradeoff",
        ),
    ]


def _child_candidates(
    profile: EnrolledProfile, age: int | None, observed: dict[str, str]
) -> list[TestBatteryCandidate]:
    fit = _child_fit(age)
    return [
        TestBatteryCandidate(
            name="growth curve + development/school/sleep interview",
            category="pediatric foundation",
            priority="must-have",
            difficulty="self-report",
            cadence="well-child cadence or when concerns change",
            why="growth/development context beats broad blood panels for many children",
            profile_fit=fit,
            status="candidate",
            lens="mainstream/context-first",
            source_hint="pediatric baseline lane",
        ),
        TestBatteryCandidate(
            name="vision, hearing, dental, and sleep/behavior screen",
            category="pediatric foundation",
            priority="high",
            difficulty="home",
            cadence="annual or concern-triggered",
            why=(
                "high-yield low-burden screens can explain school, behavior, fatigue, "
                "and growth issues"
            ),
            profile_fit=fit,
            status="candidate",
            lens="mainstream/context-first",
            source_hint="pediatric screening lane",
        ),
        _candidate(
            "blood lead level if exposure/risk or local requirement",
            "pediatric exposure",
            "high",
            "standard-lab",
            "risk-triggered; follow local pediatric rules",
            "lead can be silent; housing/water/soil/imported-products context matters",
            fit,
            "lead",
            observed,
            "mainstream/exposure-based",
            "CDC lead-testing lane",
        ),
        _candidate(
            "CBC/ferritin if fatigue, pallor, diet restriction, bleeding, or growth concern",
            "pediatric labs",
            "medium",
            "standard-lab",
            "symptom/risk-triggered",
            "anemia/iron context can affect energy, sleep, behavior, and growth",
            fit,
            "cbc",
            observed,
            "mainstream/context-first",
            "targeted pediatric lab lane",
        ),
        _candidate(
            "risk-based glucose/lipid screen",
            "pediatric cardiometabolic",
            "medium",
            "standard-lab",
            "risk-, age-, and family-history-triggered",
            "family history, weight trajectory, or symptoms can make metabolic screening useful",
            fit,
            "a1c",
            observed,
            "mainstream",
            "ADA/AHA pediatric risk lane",
        ),
    ]


def _contextual_candidates(
    profile: EnrolledProfile,
    age: int | None,
    observed: dict[str, str],
    observations: list[Observation],
) -> list[TestBatteryCandidate]:
    del profile, age
    categories = {obs.category.lower() for obs in observations}
    markers = {obs.marker.lower() for obs in observations}
    candidates: list[TestBatteryCandidate] = []
    if any("liver" in category for category in categories) or any(
        marker in {"alt", "ast", "bilirubin", "total bilirubin"} for marker in markers
    ):
        candidates.extend(
            [
                _candidate(
                    "GGT",
                    "liver/gap-aware",
                    "high",
                    "standard-lab",
                    "with repeat liver panel when liver pattern is unclear",
                    "adds cholestatic/alcohol/medication-context signal to ALT/AST/bilirubin",
                    "existing liver markers detected",
                    "ggt",
                    observed,
                    "gap-layer",
                    "DiagnosticGapEngine liver lane",
                ),
                _candidate(
                    "direct + indirect bilirubin",
                    "liver/gap-aware",
                    "high",
                    "standard-lab",
                    "with repeat liver panel when bilirubin is elevated or Gilbert context exists",
                    "separates conjugated vs unconjugated bilirubin",
                    "existing liver markers detected",
                    "bilirubin-fraction",
                    observed,
                    "gap-layer",
                    "DiagnosticGapEngine liver lane",
                ),
            ]
        )
    if any("heavy" in category or "metal" in category for category in categories) or any(
        metal in marker for marker in markers for metal in ["mercury", "lead", "arsenic", "cadmium"]
    ):
        candidates.append(
            _candidate(
                "specimen-specific heavy metals confirmation",
                "exposure/gap-aware",
                "high",
                "specialty-lab",
                "only after specimen, units, and exposure window are clear",
                "whole blood, urine, hair, and unit systems cannot be compared casually",
                "prior heavy-metal data detected",
                "heavy-metals",
                observed,
                "gap-layer/exposure-based",
                "DiagnosticGapEngine heavy-metals lane",
            )
        )
    return candidates


def _gap_candidates(gaps: list[DiagnosticGap]) -> list[TestBatteryCandidate]:
    candidates: list[TestBatteryCandidate] = []
    for gap in gaps:
        priority: Priority = "high" if gap.priority >= 0.65 else "medium"
        for candidate in gap.candidates:
            difficulty: Difficulty = (
                "self-report" if "context" in candidate.name.lower() else "standard-lab"
            )
            if "specimen" in candidate.name.lower() or "inventory" in candidate.name.lower():
                difficulty = "self-report"
            candidates.append(
                TestBatteryCandidate(
                    name=candidate.name,
                    category="gap-driven candidates",
                    priority=priority,
                    difficulty=difficulty,
                    cadence="until the diagnostic gap is closed",
                    why=candidate.role,
                    profile_fit=f"open gap: {gap.title}",
                    status=gap.status,
                    lens="gap-layer",
                    source_hint=gap.gap_type,
                )
            )
    return candidates


def _candidate(
    name: str,
    category: str,
    priority: Priority,
    difficulty: Difficulty,
    cadence: str,
    why: str,
    profile_fit: str,
    marker_key: str,
    observed: dict[str, str],
    lens: str,
    source_hint: str,
) -> TestBatteryCandidate:
    return TestBatteryCandidate(
        name=name,
        category=category,
        priority=priority,
        difficulty=difficulty,
        cadence=cadence,
        why=why,
        profile_fit=profile_fit,
        status=_status_for(marker_key, observed),
        lens=lens,
        source_hint=source_hint,
    )


def _adult_fit(age: int | None) -> str:
    if age is None:
        return "adult assumed; add birth year for age-gated recommendations"
    return f"adult profile, approximately {age} years old"


def _child_fit(age: int | None) -> str:
    if age is None:
        return "child role; add birth year/month for age-gated pediatric recommendations"
    return f"child profile, approximately {age} years old"


def _category_matches(candidate: TestBatteryCandidate, category: str) -> bool:
    if category == "all":
        return True
    haystack = f"{candidate.category} {candidate.name}".lower().replace("_", "-")
    aliases = _CATEGORY_ALIASES.get(category, (category,))
    return any(alias in haystack for alias in aliases)


def _research_topics(profile: EnrolledProfile, scope: str, category: str) -> tuple[str, ...]:
    base = (
        f"current best self-test battery ideas for {scope} {category} "
        f"profile {profile.profile_id}"
    )
    return (
        base,
        "diagnostic gap aware test stewardship: must-have vs nice-to-have panels",
    )


_MARKER_ALIASES: dict[str, tuple[str, ...]] = {
    "bp": ("blood pressure", "systolic", "diastolic"),
    "weight": ("weight", "body mass", "waist", "bmi"),
    "cbc": ("cbc", "hemoglobin", "hematocrit", "wbc", "platelet"),
    "cmp": ("cmp", "comprehensive metabolic", "alt", "ast", "creatinine", "albumin"),
    "lipids": ("lipid", "cholesterol", "ldl", "hdl", "triglyceride", "non-hdl"),
    "apob": ("apob", "apo b", "apolipoprotein b"),
    "lpa": ("lp(a)", "lipoprotein(a)", "lipoprotein a"),
    "a1c": ("a1c", "hba1c", "hemoglobin a1c", "fasting glucose", "glucose"),
    "insulin": ("insulin", "homa"),
    "urine-acr": ("urinalysis", "albumin/creatinine", "acr", "microalbumin"),
    "tsh": ("tsh", "thyroid", "free t4", "ft4"),
    "iron": ("ferritin", "iron", "tibc", "transferrin"),
    "b12": ("b12", "methylmalonic", "mma"),
    "vitamin-d": ("vitamin d", "25-oh", "25 hydroxy"),
    "hscrp": ("hs-crp", "hsc rp", "c-reactive", "crp"),
    "sleep": ("sleep", "apnea", "ahi"),
    "cac": ("cac", "coronary artery calcium"),
    "lead": ("lead",),
    "ggt": ("ggt", "gamma-glutamyl"),
    "bilirubin-fraction": ("direct bilirubin", "indirect bilirubin"),
    "heavy-metals": ("mercury", "lead", "arsenic", "cadmium", "heavy metals"),
}

_CATEGORY_ALIASES: dict[str, tuple[str, ...]] = {
    "foundation": ("foundational", "profile completeness", "pediatric foundation"),
    "vitals": ("vitals",),
    "cardio": ("cardiometabolic", "lipid", "cardiometabolic imaging"),
    "metabolic": ("cardiometabolic", "glucose", "weight"),
    "glucose": ("glucose", "diabetes"),
    "liver": ("liver",),
    "kidney": ("kidney", "urine"),
    "nutrient": ("nutrient", "hematology"),
    "hormone": ("hormone", "thyroid"),
    "inflammation": ("inflammation",),
    "exposure": ("exposure", "heavy", "lead", "metal"),
    "sleep": ("sleep", "physiology"),
    "pediatric": ("pediatric",),
    "gaps": ("gap",),
}

_CATEGORY_ORDER: dict[str, int] = {
    "profile completeness": 0,
    "pediatric foundation": 1,
    "foundational vitals": 2,
    "foundational labs": 3,
    "cardiometabolic": 4,
    "glucose metabolism": 5,
    "kidney/urine": 6,
    "liver/gap-aware": 7,
    "nutrient/hematology": 8,
    "thyroid/hormones": 9,
    "inflammation": 10,
    "physiology/sleep": 11,
    "exposure/gap-aware": 12,
    "gap-driven candidates": 13,
}
