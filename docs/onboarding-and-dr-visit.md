# Onboarding and periodic Dr Visit prompts

`llm-health` should feel like `llm-wiki` on first run: friendly, local-first, and useful before
any fancy dashboard is configured. A first run should welcome the user, enroll an alias-only profile,
request useful data dumps, and fall back to a strong questionnaire when the user has little data.
The first run must show the own-risk disclaimer before collecting health data.

## Commands

```sh
health                 # no args: prints the welcome/intake flow
health welcome
health agreement show
health agreement accept --own-risk
health enroll --alias <alias> --birth-year <yyyy> [--birth-month <1-12>] --role <context>
health data-wishlist
health dr-visit --profile <alias> --cadence onboarding
health dr-visit --profile <alias> --cadence monthly --sources
```

## Data wishlist

Ask for data in descending usefulness:

1. **Clinical/lab records** — lab reports, portal exports, medication/allergy lists, procedures,
   imaging summaries, pathology, consult notes, discharge summaries.
2. **Apple Health / wearable exports** — activity, sleep, body measurements, vitals, symptoms,
   workouts, HR/HRV, weight, blood pressure, glucose/CGM when present.
3. **Human context dump** — goals, symptoms, suspected/known diagnoses, meds/supplements,
   exposures, travel, pets/mold/work, family history, and what not to optimize for.
4. **Prose memory dump** — paragraph-form recollection of what happened, approximate timing,
   suspected triggers, what helped, what hurt, and what is uncertain.
5. **Family/hereditary references** — family-history prose plus alias-only enrollment for close
   relatives when ongoing data can help compare hereditary/context patterns.
6. **Habits/substances** — nicotine/tobacco, alcohol, cannabis, recreational substances,
   prescription/non-prescription use patterns, caffeine, light/screens, sleep, food, movement,
   work/travel rhythm.
7. **Adaptive fact finding** — the agent keeps digging across timeline, dose, route, frequency,
   triggers, confounders, negative clues, and uncertainty instead of accepting thin answers.
8. **Data-poor questionnaire** — top concerns, timeline, baseline metrics, exposure changes,
   intake timeline, body-system sweep, constraints, and escalation thresholds.

The CLI text intentionally says what to collect without storing raw source paths or filenames.
Health-facing commands are gated behind the own-risk agreement described in
`docs/own-risk-agreement.md`.


## Prose-first interview rule

The system should ask users to write like they are talking to a good doctor, not filling a sterile
spreadsheet. Encourage paragraphs, approximate timelines, uncertain memories, old events, things
that helped or hurt, and negative clues. The interview should explicitly say that fuzzy memories are
useful when tagged as uncertain.

The stance is nonjudgmental fact finding. Ask plainly about smoking/nicotine, alcohol, cannabis,
other substances, caffeine, sleep, light/screens, diet, fasting, exercise, work/travel rhythm, sex,
sauna/cold/sun, and medication/supplement habits. Capture current and past use, amount, frequency,
route, timing, start/stop dates, benefits, side effects, tolerance/withdrawal, and whether absences
are true negatives. The agent should keep digging in all directions until the timeline and major
confounders are clear.

For hereditary context, ask users to enroll close family with alias-only profiles when they have
ongoing data or permission:

```sh
health enroll --alias <relative_alias> --birth-year <yyyy> --role <relation>
```

Use those profiles as references for hereditary/context patterns. Do not store legal names, full
birth dates, or identifying family details; if a relative is only background context, record relation
plus rough age/onset instead of creating a profile.

## Cadence matrix

| Cadence | Use when | Main questions |
|---|---|---|
| Onboarding | New profile or data-poor profile | alias, birth year/month, goals, prose memory dump, family references, habits/substances, data dumps, minimum viable questionnaire |
| Weekly | Active change, intervention, acute concern, or unstable trend | new/worse/better, exposure/intake changes, symptom 0-10 trend, red flags |
| Monthly | Stable but worth tracking | 30-day changes, meds/supplements, new records, stale concerns, one research question |
| Quarterly | Trend review and gap closure | labs/wearables domains, supplement/med reconcile, diagnostic gaps, family/hereditary changes, exposures, target changes |
| Annual | Full profile audit | goals, family history, med/supplement/allergy/protocol reconciliation, records refresh, high-leverage next tests/questions |
| Pre-lab | 1-7 days before a draw | fasting/exercise/alcohol/illness/supplement context, decision the lab informs, specimen/method constraints |
| Post-result | After new rows land | normalize units/specimen/method, compare windows, quick-vs-deep review, next tracking target |

The system should be contextual: a noisy wearable metric can be daily/weekly; a stable family-history
field is annual-or-changed; a new abnormal lab gets immediate post-result review.

## Research/source posture

These sources shape question domains and frequency scaffolding; they do **not** define automatic
medical advice or protocol conclusions. `llm-health` still keeps mainstream, frontier, edge,
contrarian, capture, inversion, and risk lenses separate.

- American Heart Association Life's Essential 8: diet, physical activity, nicotine, sleep, weight,
  lipids, glucose, and blood pressure domains.
  <https://www.heart.org/en/healthy-living/healthy-lifestyle/lifes-essential-8>
- PROMIS Health Organization / Global Health domains: broad physical, mental, social, pain, fatigue,
  and sleep self-report domains.
  <https://www.promishealth.org/57461-2/>
- PHQ/GAD screeners: brief symptom-severity monitoring instruments, not standalone diagnoses.
  <https://www.phqscreeners.com/>
- NIAAA AUDIT-C overview: frequency, quantity, and heavy-use alcohol questions for adults when relevant.
  <https://www.niaaa.nih.gov/health-professionals-communities/core-resource-on-alcohol/screen-and-assess-use-quick-effective-methods>
- NIDA TAPS / WHO ASSIST: nonjudgmental screening domains across tobacco/nicotine, alcohol,
  cannabis, prescription-medication misuse, and other substances.
  <https://nida.nih.gov/taps2/> and <https://www.who.int/publications/i/item/978924159938-2>
- Medication reconciliation review: recurring medication/adverse-reaction review is a patient-safety
  primitive, especially when meds/supplements start or stop.
  <https://www.ncbi.nlm.nih.gov/books/NBK2648/>
- Family health history: collect initially and update because relatives develop late-onset conditions.
  <https://www.cdc.gov/family-health-history/about/index.html>
- Apple HealthKit and Apple Health Records: useful source families for activity, vitals, sleep,
  symptoms, clinical labs, conditions, allergies, medications, immunizations, procedures.
  <https://developer.apple.com/documentation/healthkit/data-types>
  <https://support.apple.com/guide/iphone/get-started-with-health-iphcae7451f3/ios>
  <https://support.apple.com/guide/iphone/view-health-records-iph2b3a37ddd/ios>
