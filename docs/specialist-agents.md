# Specialist/category agents

`llm-health` treats “specialists” as broad category agents, not rigid medical silos or
independent chatbots with private memory. The concierge/router builds a privacy-safe context pack,
routes to one or more category agents, then stores `SPECIALIST_NOTE` artifacts for synthesis.

The CLI command remains `health specialists` for compatibility, but the implementation is category
first: agents own common health data domains, capabilities, triggers, and handoff questions.

## Commands

```sh
health specialists
health specialists --short
health consult --profile rod --specialist auto
health consult --profile rod --specialist internal_medicine --topic "baseline synthesis"
health consult --profile rod --specialist toxins_exposures --topic mercury
health consult --profile rod --specialist toxicology_heavy_metals --topic mercury  # legacy alias
health specialist-notes --profile rod
```

## Default category agent: Whole-Person / Internal Medicine Synthesis

`internal_medicine` remains the compatibility id, but the role is broader than a narrow specialty.
It is the default whole-person synthesizer/router and the first category agent in `auto` routing.
It is responsible for:

- whole-profile problem representation;
- active vs historical/resolved issue separation;
- timeline/confounder map;
- red-flag screen;
- medication/supplement/habit reconciliation;
- prioritizing must-have vs nice-to-have next steps;
- deciding which category agents should go deeper;
- preserving visible disagreement instead of blending it into false consensus.

## Registered category agents

- `internal_medicine` — whole-person synthesis, prioritization, routing, and handoff questions.
- `labs_data_quality` — units, reference ranges, specimen/method QA, flagged/pending rows.
  Legacy alias: `lab_interpreter`.
- `cardiometabolic` — lipids, glucose, BP, weight, ApoB/Lp(a), CAC risk refinement.
- `liver_biliary_gi` — ALT/AST/bilirubin, Gilbert context, liver/biliary/GI confounders.
  Legacy alias: `liver_gi`.
- `kidney_urine_hydration` — creatinine/eGFR, BUN, electrolytes, urinalysis, hydration context.
- `hormones_endocrine` — thyroid, sex hormones, adrenal/cortisol and timing context.
- `immune_inflammation` — CBC pattern, CRP/ESR, infection/inflammation, allergy/autoimmune clues.
- `nutrients_hematology` — iron/ferritin, B12/folate, vitamin D, minerals, anemia/CBC patterns.
- `toxins_exposures` — mercury/lead/arsenic/cadmium, specimen/unit/exposure review.
  Legacy alias: `toxicology_heavy_metals`.
- `meds_supplements` — medication/supplement necessity, side effects, interactions, collateral lanes.
  Legacy alias: `medication_collateral`.
- `habits_lifestyle` — smoking, alcohol, drugs, food, activity, light, work/travel rhythm.
  Legacy alias: `lifestyle_habits`.
- `sleep_circadian` — sleep duration/quality, snoring/apnea clues, light timing, recovery.
- `neuro_mood_cognition` — neuro symptoms, mood/energy, cognition, exposure/medication confounders.
- `family_hereditary` — family history, household comparisons, inherited risk clues.
- `pediatric_growth` — child profiles, growth/development, pediatric test stewardship.
  Legacy alias: `pediatrics`.
- `test_gap_steward` — context questions and test candidates for uncertainty.
  Legacy alias: `diagnostic_gap_steward`.
- `research_librarian` — source retrieval and queued research jobs.
- `research_skeptic` — endpoint quality, conflicts, capture, uncertainty, cascade risk.
  Legacy alias: `evidence_skeptic`.
- `red_flag_checker` — escalation thresholds and do-not-miss patterns.

## Artifact contract

A category-agent note stores:

- category agent id in the `specialist_id` compatibility field;
- summary;
- key findings;
- uncertainties;
- candidate tests;
- research topics;
- red flags/escalation checks;
- related observation/gap ids;
- visible tags, including `SPECIALIST_NOTE` and `INFERENCE`.

Category-agent notes are review artifacts. They do not diagnose, prescribe, or order tests.
