# Test battery layer

`llm-health` now has a profile-aware test-battery lane. It produces **TEST_CANDIDATE** artifacts,
not lab orders.

```sh
health test-battery --profile rod --scope core
health test-battery --profile rod --scope expanded --category cardio --sources
health test-battery --profile rod --scope complete --category all --queue-research
health test-battery --profile rod --category gaps
```

## Scope levels

| Scope | Meaning |
|---|---|
| `core` | Must-have and high-priority candidates: profile completeness, vital signs, foundational labs, high-yield gap candidates. |
| `expanded` | Adds medium/low candidates useful for context, trend interpretation, or common gaps. |
| `complete` | Adds nice-to-have/edge candidates that may be useful for high-responsibility n-of-1 tracking but have more burden/noise. |

Every row includes:

- category;
- priority: `must-have`, `high`, `medium`, `low`, `nice-to-have`;
- difficulty: `self-report`, `home`, `standard-lab`, `specialty-lab`, `imaging`, `invasive`;
- current status, e.g. missing/currentness unknown vs seen date;
- why it exists;
- profile fit;
- cadence;
- lens/source hint.

## Categories

- `foundation` / `vitals`
- `cardio` / `metabolic` / `glucose`
- `liver` / `kidney`
- `nutrient` / `hormone` / `inflammation`
- `exposure`
- `sleep`
- `pediatric`
- `gaps`

## Gap-layer integration

The battery command merges stored diagnostic gaps with freshly computed gaps from observations.
For example, liver signals can surface repeat hepatic panel, GGT, and bilirubin-fraction candidates;
heavy-metal rows can surface specimen/unit/exposure confirmation candidates. These are tagged and
rendered as `gap-driven candidates` so users can see what came from the deterministic gap layer.

## Research refresh

`--queue-research` appends research jobs so an agent can periodically refresh “best current ideas”
for the selected profile/scope/category. The research job should compare:

- mainstream preventive-screening floors;
- frontier/advanced biomarker ideas;
- edge/n-of-1 usefulness;
- capture/conflict incentives;
- false-positive, cost, invasiveness, and downstream cascade risk;
- whether the candidate closes a real diagnostic gap.

## Source/rationale posture

These sources shape candidate domains. They are not hard-coded authority, and they do not replace
profile-specific reasoning.

- USPSTF A/B recommendations: mainstream adult preventive-screening floor.
  <https://www.uspreventiveservicestaskforce.org/uspstf/recommendation-topics/uspstf-a-and-b-recommendations>
- American Heart Association Life's Essential 8: activity, nicotine, sleep, weight, lipids,
  glucose, and blood-pressure domains.
  <https://www.heart.org/en/healthy-living/healthy-lifestyle/lifes-essential-8>
- ADA Standards of Care in Diabetes: annually refreshed glucose/diabetes screening lens.
  <https://professional.diabetes.org/standards-of-care>
- AHA Lipoprotein(a): inherited lipid-risk context.
  <https://www.heart.org/en/health-topics/cholesterol/genetic-conditions/lipoprotein-a>
- Endocrine Society testosterone guideline: hormone testing should be symptom/context driven.
  <https://www.endocrine.org/clinical-practice-guidelines/testosterone-therapy>
- CDC lead testing: exposure/risk-triggered lead testing context, especially pediatrics.
  <https://www.cdc.gov/lead-prevention/testing/index.html>
