from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QuestionBlock:
    title: str
    cadence: str
    questions: tuple[str, ...]
    tags: tuple[str, ...] = ("CONTEXT",)


DATA_DUMP_REQUESTS: tuple[QuestionBlock, ...] = (
    QuestionBlock(
        title="Apple / phone / wearable dumps",
        cadence="onboarding, then refresh when devices/apps change",
        questions=(
            "Apple Health full export or app-specific clean CSV/JSON export if available.",
            (
                "Apple Health Records / clinical records export when connected: allergies, "
                "conditions, medications, immunizations, labs, procedures, vitals."
            ),
            (
                "Wearable exports from Garmin/Oura/Fitbit/Whoop/CGM/BP cuff/scale apps "
                "if they are not already in Apple Health."
            ),
            (
                "A simple note listing which device/app is trusted for steps, sleep, heart "
                "rate, HRV, weight, BP, glucose, and workouts."
            ),
        ),
        tags=("CONTEXT", "WEARABLE_CONTEXT"),
    ),
    QuestionBlock(
        title="Doctor / clinic / lab records",
        cadence="onboarding, then after each new visit/result",
        questions=(
            "Recent and historical lab reports, ideally as PDFs or portal export files.",
            (
                "Problem list, procedures/surgeries, imaging/radiology summaries, pathology, "
                "consult notes, and discharge summaries."
            ),
            (
                "Medication list, allergies/adverse reactions, immunization/protocol history, "
                "and pharmacy fills if available."
            ),
            (
                "Specialty records that explain context: dental, vision, GI, dermatology, "
                "fertility/hormones, pediatrics, etc."
            ),
        ),
        tags=("CONTEXT", "OBSERVED"),
    ),
    QuestionBlock(
        title="Human context dump",
        cadence="onboarding, then update when something changes",
        questions=(
            (
                "Current goals, top concerns, known diagnoses, suspected conditions, and "
                "what you do not want optimized for."
            ),
            (
                "Current medications, supplements, peptides/hormones, dose/frequency, "
                "start/stop dates, perceived benefit, and side effects."
            ),
            (
                "Food pattern, alcohol/nicotine/cannabis/other exposures, travel, pets, "
                "mold/water/occupational exposures, and major stressors."
            ),
            (
                "Family history at a useful granularity: relation, condition, rough age of "
                "onset, and whether it changed recently."
            ),
        ),
        tags=("CONTEXT",),
    ),
)


NARRATIVE_MEMORY_BLOCKS: tuple[QuestionBlock, ...] = (
    QuestionBlock(
        title="Prose memory dump: tell it like a real visit",
        cadence="onboarding, then whenever old memories resurface",
        questions=(
            (
                "Write paragraphs, not just bullet points: what have you had, what happened, "
                "what seemed to trigger it, and what changed afterward?"
            ),
            (
                "Try to remember childhood patterns, recurring infections, injuries, dental "
                "work, gut issues, skin issues, sleep problems, allergies, medications, "
                "procedures, travel, moves, water/mold exposures, pets, and major stressors."
            ),
            (
                "Add approximate timing even if fuzzy: childhood, teens, 20s, before/after a "
                "pregnancy/birth, before/after a move, before/after a medication, or rough year."
            ),
            (
                "Include negative clues too: things you tried that did nothing, things that "
                "made you worse, and symptoms you expected but never had."
            ),
            (
                "Uncertainty is allowed. Say 'I vaguely remember', 'maybe', or 'family says' "
                "instead of forcing fake precision."
            ),
        ),
        tags=("CONTEXT", "DATA_GAP"),
    ),
)


FAMILY_REFERENCE_BLOCKS: tuple[QuestionBlock, ...] = (
    QuestionBlock(
        title="Family history and hereditary references",
        cadence="onboarding, annual, and whenever a relative has new information",
        questions=(
            (
                "List family patterns in prose: relation, condition/trait, rough age of onset, "
                "severity, cause of death if known, and whether multiple relatives share it."
            ),
            (
                "Ask about parents, siblings, children, grandparents, aunts/uncles, nieces/"
                "nephews, and half-siblings when relevant; incomplete information is still useful."
            ),
            (
                "Flag possible hereditary clusters: early cardiovascular disease, diabetes, "
                "autoimmune disease, dementia, psychiatric/addiction patterns, cancers, clotting, "
                "kidney/liver disease, thyroid, allergies/asthma, connective-tissue signs."
            ),
            (
                "Enroll close family with alias-only profiles when you have ongoing data or "
                "permission: `health enroll --alias <relative_alias> --birth-year <yyyy> "
                "--role <relation>`."
            ),
            (
                "Use family profiles as references for hereditary/context patterns, not as a "
                "reason to expose legal names, full birth dates, or other identifiers."
            ),
        ),
        tags=("CONTEXT", "DATA_GAP"),
    ),
)


HABITS_AND_SUBSTANCES_BLOCKS: tuple[QuestionBlock, ...] = (
    QuestionBlock(
        title="Smoking, alcohol, drugs, and habits: no judgment, just facts",
        cadence="onboarding, monthly if changing, annual if stable",
        questions=(
            (
                "Nicotine/tobacco: current or past smoking, vaping, pouches, cigars, secondhand "
                "smoke; amount, start/stop dates, cravings, and quit attempts?"
            ),
            (
                "Alcohol: how often, how much on a typical day, biggest days, timing, sleep/"
                "recovery effects, hangovers, liver/GI/mood effects, and dry spells?"
            ),
            (
                "Cannabis and other substances: type, route, dose/frequency, reason, benefits, "
                "downsides, tolerance, withdrawal, interactions, and last use?"
            ),
            (
                "Prescription/non-prescription use patterns: stimulants, sedatives, opioids, "
                "antihistamines, NSAIDs, acetaminophen, antibiotics, hormones/peptides, and "
                "anything used off-label or borrowed?"
            ),
            (
                "Habit stack: caffeine, screens/light, bedtime/wake time, meals/fasting, ultra-"
                "processed food, exercise, sauna/cold, sun, sex, work schedule, and travel rhythm?"
            ),
            (
                "Tell the truth even when it is messy. The goal is fact finding, pattern matching, "
                "and confounder detection — not moral scoring."
            ),
        ),
        tags=("CONTEXT", "DATA_GAP"),
    ),
)


ADAPTIVE_FACT_FINDING_BLOCKS: tuple[QuestionBlock, ...] = (
    QuestionBlock(
        title="Adaptive digging rules for the agent",
        cadence="always during interview and review",
        questions=(
            (
                "Keep asking directional follow-ups: timeline, dose, frequency, route, intensity, "
                "duration, triggers, what changed before/after, and what stopped or improved it."
            ),
            (
                "For any symptom, dig across sleep, food, hydration, light, activity, stress, "
                "infection, dental, gut, skin, environment, family history, meds, supplements, "
                "substances, and recent travel/exposures."
            ),
            (
                "For any lab outlier, ask about fasting, exercise, alcohol, illness, sleep debt, "
                "dehydration, supplements/meds, specimen type, lab method, and timing."
            ),
            (
                "Ask about absences too: no smoking, no alcohol, no recreational drugs, no recent "
                "antibiotics, no NSAIDs, no symptoms, no family history. Negative clues are data."
            ),
            (
                "When the answer is fuzzy, capture uncertainty visibly instead of forcing a fake "
                "clean data point."
            ),
        ),
        tags=("CONTEXT", "DATA_GAP"),
    ),
)


DATA_POOR_BLOCKS: tuple[QuestionBlock, ...] = (
    QuestionBlock(
        title="No dumps yet? Minimum viable questionnaire",
        cadence="onboarding, then revisit when answers change",
        questions=(
            (
                "Top concerns: what changed, when did it start, what improves/worsens it, "
                "and what is the current 0-10 burden?"
            ),
            (
                "Current baselines: weight, waist if known, resting blood pressure, resting "
                "heart rate, sleep timing, and usual steps/activity."
            ),
            (
                "Exposure timeline: recent illness, travel, dental work, "
                "antibiotics/NSAIDs/acetaminophen, alcohol, mold/water, pets, work, or "
                "unusual foods."
            ),
            (
                "Intake timeline: meds, supplements, hormones/peptides, dose/frequency, "
                "start/stop dates, intended reason, benefit, side effects."
            ),
            (
                "Body-system sweep: energy, mood, cognition, libido, gut, skin, pain, "
                "breathing, urination, infections, and heat/cold tolerance."
            ),
            (
                "Decision constraints: what interventions are off-limits, what level of "
                "uncertainty is acceptable, and what would force escalation?"
            ),
        ),
        tags=("CONTEXT", "DATA_GAP"),
    ),
)


INTAKE_BLOCKS: tuple[QuestionBlock, ...] = (
    QuestionBlock(
        title="Start here, human",
        cadence="onboarding",
        questions=(
            "What alias should I use for this profile?",
            "What is the birth year, and birth month only if useful? No full birth date.",
            "What are the top 3 outcomes you care about most right now?",
            "What are the top 3 symptoms or concerns that keep recurring?",
            "What would make this system annoying or wrong for you?",
        ),
    ),
    QuestionBlock(
        title="Baseline health story",
        cadence="onboarding, then annually or when changed",
        questions=(
            (
                "Known diagnoses, surgeries/procedures, hospitalizations, major infections, "
                "injuries, or pregnancies/births?"
            ),
            "Current meds/supplements and recent starts/stops in the last 90 days?",
            "Allergies, intolerances, paradoxical reactions, or meds/supplements that went badly?",
            (
                "Family history changes: heart disease, diabetes, stroke, dementia, "
                "autoimmune, cancers, psychiatric/addiction, genetic conditions?"
            ),
        ),
    ),
    QuestionBlock(
        title="Vitals and home metrics",
        cadence="weekly to monthly if actively changing; quarterly if stable",
        questions=(
            "Current weight, waist if tracked, resting BP if available, and any outliers?",
            (
                "Sleep duration/quality, waking time, naps, snoring/apnea clues, and "
                "wearable sleep confidence?"
            ),
            (
                "Training/activity: steps, zone/cardio, strength, pain-limited movements, "
                "and recovery?"
            ),
            (
                "Energy, mood, libido, cognition, gut, skin, pain, and infection symptoms "
                "on a 0-10 scale?"
            ),
        ),
        tags=("CONTEXT", "WEARABLE_CONTEXT"),
    ),
)


DR_VISIT_BLOCKS: dict[str, tuple[QuestionBlock, ...]] = {
    "onboarding": (
        *INTAKE_BLOCKS,
        *NARRATIVE_MEMORY_BLOCKS,
        *FAMILY_REFERENCE_BLOCKS,
        *HABITS_AND_SUBSTANCES_BLOCKS,
        *ADAPTIVE_FACT_FINDING_BLOCKS,
        *DATA_DUMP_REQUESTS,
        *DATA_POOR_BLOCKS,
    ),
    "weekly": (
        QuestionBlock(
            title="Tiny check-in, because future-you is nosy",
            cadence="weekly when actively changing; skip if boring and stable",
            questions=(
                "Anything new, weird, better, or worse since last check-in?",
                (
                    "Any med/supplement/food/nicotine/alcohol/cannabis/drug/exposure/"
                    "travel/illness changes?"
                ),
                "Sleep, energy, mood, gut, pain, and training recovery: quick 0-10 trend?",
                "Any red-flag symptoms that should not be normalized?",
            ),
        ),
    ),
    "monthly": (
        QuestionBlock(
            title="Monthly Dr Visit: no waiting room, still judgmental about missing context",
            cadence="monthly",
            questions=(
                (
                    "What changed in the last 30 days: symptoms, sleep, weight, activity, "
                    "diet, stress, substances, habits, exposures?"
                ),
                (
                    "Any medication/supplement starts, stops, dose changes, side effects, "
                    "or surprisingly good effects?"
                ),
                (
                    "Any new labs, records, imaging, dental/GI/skin/eye visits, or portal "
                    "messages to ingest?"
                ),
                (
                    "Which open concern should be downgraded, upgraded, or marked resolved "
                    "from self-report?"
                ),
                "What one question should the system research deeper before the next check-in?",
            ),
        ),
    ),
    "quarterly": (
        QuestionBlock(
            title="Quarterly Dr Visit: spreadsheet goblin edition",
            cadence="every 3 months",
            questions=(
                (
                    "Review trend domains: liver/metabolic, lipids, glucose, thyroid/hormones, "
                    "kidney, inflammation, heavy metals, GI, sleep/activity."
                ),
                "Reconcile meds/supplements and ask: keep, stop, cycle, test, or monitor?",
                "Check diagnostic gaps: which missing data would actually change decisions?",
                (
                    "Review family history/context changes, enrolled relatives, hereditary "
                    "clusters, and new exposures."
                ),
                "Review substance/habit changes and whether any confound current trends.",
                "Are current goals still correct, or did the target move while no one was looking?",
            ),
        ),
    ),
    "annual": (
        QuestionBlock(
            title="Annual Dr Visit: the grand audit, but with fewer clipboards",
            cadence="annual",
            questions=(
                (
                    "Update profile basics: alias, birth year/month precision, goals, "
                    "constraints, and emergency context."
                ),
                (
                    "Refresh family history, enrolled relative references, and major life/"
                    "exposure changes."
                ),
                (
                    "Reconcile all medications, supplements, allergies/adverse reactions, "
                    "procedures, and preventive protocols."
                ),
                (
                    "Reconcile nicotine/tobacco, alcohol, cannabis/other substances, caffeine, "
                    "sleep/activity/food habits, and any major changes."
                ),
                (
                    "Review all major trend domains and decide what is active, stable, "
                    "stale/resolved, or needs data."
                ),
                (
                    "Gather/refresh Apple Health, clinical records, labs, imaging/procedures, "
                    "and wearable exports."
                ),
                (
                    "Pick the next 1-3 high-leverage tests/questions; avoid broad panels "
                    "without a decision path."
                ),
            ),
        ),
    ),
    "pre-lab": (
        QuestionBlock(
            title="Pre-lab Dr Visit: do not sabotage the draw, champ",
            cadence="1-7 days before labs",
            questions=(
                (
                    "Fasting plan, recent exercise, alcohol, illness, sleep disruption, "
                    "supplements/meds that may affect results?"
                ),
                "What is the decision this lab should inform?",
                "Any specimen/unit/method constraints that matter for comparability?",
                "What context note should be attached to the lab event before interpretation?",
            ),
        ),
    ),
    "post-result": (
        QuestionBlock(
            title="Post-result Dr Visit: panic later, normalize units first",
            cadence="after new results arrive",
            questions=(
                "Which results are new, flagged, pending, or large deltas?",
                "Are units/specimen/lab method comparable to prior rows?",
                "What changed in the 7/30/90-day windows before the draw?",
                "Which findings need quick context versus deeper research?",
                (
                    "What should be tracked next: symptom, wearable, repeat test, or "
                    "no-action watch window?"
                ),
            ),
        ),
    ),
}


SOURCE_NOTES: tuple[str, ...] = (
    (
        "AHA Life's Essential 8 supports recurring diet, physical activity, nicotine, sleep, "
        "weight, lipids, glucose, and blood-pressure domains."
    ),
    (
        "PROMIS Global Health and PROMIS domains support periodic physical, mental, social, "
        "pain, fatigue, and sleep self-report domains."
    ),
    (
        "GAD-7/PHQ-style instruments are useful as brief symptom severity screens/monitors, "
        "not diagnoses by themselves."
    ),
    (
        "AUDIT-C-style alcohol questions capture frequency, quantity, and heavy-use occasions "
        "for adults when relevant."
    ),
    (
        "TAPS/ASSIST-style substance-use screens support nonjudgmental fact-finding across "
        "tobacco/nicotine, alcohol, cannabis, prescription medications, and other substances."
    ),
    (
        "Medication reconciliation and adverse-reaction review should happen whenever new "
        "meds/supplements start/stop and at recurring visits."
    ),
    (
        "Family history should be collected initially and updated periodically because relatives "
        "develop new late-onset conditions over time."
    ),
    (
        "Family-history collection should capture close and extended relatives, age of onset, "
        "cause of death when known, and repeated patterns because shared genes, behaviors, and "
        "environment can all matter."
    ),
    (
        "Apple Health/HealthKit and Apple Health Records can provide activity, vitals, sleep, "
        "symptoms, clinical labs, medications, allergies, immunizations, procedures, and "
        "conditions when available."
    ),
)

SOURCE_LINKS: tuple[tuple[str, str], ...] = (
    (
        "American Heart Association Life's Essential 8",
        "https://www.heart.org/en/healthy-living/healthy-lifestyle/lifes-essential-8",
    ),
    ("PROMIS Health Organization", "https://www.promishealth.org/57461-2/"),
    ("PHQ/GAD screeners", "https://www.phqscreeners.com/"),
    (
        "NIAAA AUDIT-C overview",
        "https://www.niaaa.nih.gov/health-professionals-communities/core-resource-on-alcohol/"
        "screen-and-assess-use-quick-effective-methods",
    ),
    (
        "NIDA TAPS substance-use screening tool",
        "https://nida.nih.gov/taps2/",
    ),
    (
        "WHO ASSIST substance-use screening tool",
        "https://www.who.int/publications/i/item/978924159938-2",
    ),
    ("Medication reconciliation review", "https://www.ncbi.nlm.nih.gov/books/NBK2648/"),
    (
        "Family health history",
        "https://www.cdc.gov/family-health-history/about/index.html",
    ),
    (
        "Apple HealthKit data types",
        "https://developer.apple.com/documentation/healthkit/data-types",
    ),
    (
        "Apple Health app overview",
        "https://support.apple.com/guide/iphone/get-started-with-health-iphcae7451f3/ios",
    ),
    (
        "Apple Health Records overview",
        "https://support.apple.com/guide/iphone/view-health-records-iph2b3a37ddd/ios",
    ),
)


def render_blocks(blocks: tuple[QuestionBlock, ...]) -> str:
    lines: list[str] = []
    for block in blocks:
        lines.append(f"## {block.title}")
        lines.append(f"cadence: {block.cadence}")
        lines.append(f"tags: {', '.join(block.tags)}")
        for question in block.questions:
            lines.append(f"- {question}")
        lines.append("")
    return "\n".join(lines).rstrip()


def render_welcome() -> str:
    from llm_health.agreement import render_disclaimer

    welcome = (
        "# Welcome to llm-health\n"
        "Local-first, alias-only, no raw identifiers. First we enroll aliases; then we ask "
        "for data dumps; then we become politely annoying about missing context."
    )
    commands = (
        "## First commands\n"
        "- health agreement show\n"
        "- health agreement accept --own-risk\n"
        "- health enroll --alias <alias> --birth-year <yyyy> "
        "[--birth-month <1-12>] --role <context>\n"
        "- health profiles\n"
        "- health data-wishlist\n"
        "- health dr-visit --profile <alias> --cadence onboarding\n"
        "- health ui  # open the local Assessment Board once a HUB/data exists\n"
        "- health dr-visit --profile <alias> --cadence monthly --sources"
    )
    return "\n\n".join(
        [
            render_disclaimer(),
            welcome,
            commands,
            (
                "## See the UI early\n"
                "After setup or any data import, run `health ui` to export and open the "
                "local Assessment Board. It shows profiles, source rows, timelines, "
                "context notes, family/history clues, flags, gaps, reports, and the "
                "copyable interview drafts. Use `health ui --no-open` in scripts."
            ),
            render_blocks(INTAKE_BLOCKS),
            render_blocks(NARRATIVE_MEMORY_BLOCKS),
            render_blocks(FAMILY_REFERENCE_BLOCKS),
            render_blocks(HABITS_AND_SUBSTANCES_BLOCKS),
            render_blocks(ADAPTIVE_FACT_FINDING_BLOCKS),
            render_blocks(DATA_POOR_BLOCKS),
        ]
    )


def render_data_wishlist() -> str:
    return render_blocks(DATA_DUMP_REQUESTS)


def render_dr_visit(cadence: str) -> str:
    normalized = cadence.strip().lower()
    blocks = DR_VISIT_BLOCKS.get(normalized)
    if blocks is None:
        valid = ", ".join(sorted(DR_VISIT_BLOCKS))
        raise ValueError(f"unknown cadence {cadence!r}; choose one of: {valid}")
    return render_blocks(blocks)
