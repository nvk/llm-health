# Diagnostic Gap + Test Stewardship Layer

The system should suggest tests only as **test candidates** to discuss, not as orders.

## Gap types

- Confirmatory gap — repeat/verify an odd, pending, or abnormal result.
- Pattern gap — add a marker that disambiguates an observed pattern.
- Cause gap — several plausible causes remain open.
- Severity/staging gap — establish whether the finding is mild or meaningful.
- Confounder gap — fasting, exercise, illness, supplement, medication, specimen, or method context is missing.
- Monitoring gap — repeat after an intervention/window.
- Safety gap — before a higher-risk protocol, check baseline risk markers.

## Candidate scoring

```text
score = information_gain + actionability + risk_of_missing + fit_to_current_data
        - false_positive_risk - cost_burden - invasiveness - duplication
```

## Card shape

```yaml
gap: liver_pattern_unclear
type: pattern_gap
status: open
suggested_next:
  - candidate: repeat hepatic panel
    role: confirm persistence
  - candidate: GGT
    role: clarify liver/cholestatic contribution
  - candidate: direct + indirect bilirubin
    role: separate conjugated vs unconjugated bilirubin
label: TEST_CANDIDATE
```

The system should often ask context before suggesting more labs.
