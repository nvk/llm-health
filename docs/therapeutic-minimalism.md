# Therapeutic minimalism and least-harm options

Doing less can be an active intervention if it is explicit, monitored, and red-flag gated.

## Option ladder

1. Time/rest/observation.
2. Context fix: sleep, hydration, light, food, environment.
3. Home remedy or low-collateral intervention.
4. Targeted diagnostic test.
5. Narrow, reversible treatment.
6. Higher-collateral medication/procedure.

## Conservative-care card

```yaml
option_type: WATCHFUL_WAITING
target: mild self-limited symptom
allowed_if:
  - no red flags
  - function preserved
  - symptom trend stable or improving
track:
  - symptom severity
  - fever or systemic signs
  - sleep/function
review_after: 24-72h
escalate_if:
  - severe or worsening pain
  - fever/systemic signs
  - neurological symptoms
  - bleeding/discharge/swelling
labels: [LOW_INTERVENTION, RED_FLAG_GATED]
```

Home remedies are not treated as automatically safe. Each gets contraindications, stop rules,
expected benefit, and evidence lane.
