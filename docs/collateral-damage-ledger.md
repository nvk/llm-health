# Medication and preventive-protocol collateral-damage ledger

`llm-health` treats medication and preventive protocols as net-benefit reviews, not as default
compliance checklists.

## Medication exposure review

For antibiotics, NSAIDs, acetaminophen/paracetamol, antihistamines, steroids, and other exposures,
record:

- active/class, route, dose, duration, timing;
- indication and evidence that the exposure was necessary;
- avoidability questions: watchful waiting, delayed prescription, narrower option, shorter duration,
  diagnostic test first;
- collateral-damage lanes: microbiome, gut barrier, liver, kidney, GI bleeding, cardiovascular,
  nutrient depletion, rebound/withdrawal, interactions;
- monitoring markers and symptom windows.

## Preventive protocol review

For vaccines or other preventive protocols, use absolute benefit/harm and subgroup fit:

- age/sex, prior infection/immunity, exposure risk, comorbidities, prior adverse events;
- endpoint moved: infection, symptoms, hospitalization, death, transmission, or surrogate;
- absolute risk reduction, duration, number-needed metrics when available;
- acute, serious, delayed, or undertracked adverse signals;
- alternatives: defer, decline, timing, exposure control, nutrition/sleep/light/ventilation/hygiene,
  high-risk-only or post-exposure strategies where applicable.

Conclusion options are explicit:

- `accept`
- `defer`
- `decline`
- `only_if_exposed_or_high_risk`
- `needs_more_research`

The system should not hard-code an agency schedule or a contrarian conclusion. It should make the
ledger strong enough that low-value/high-collateral protocols can be rejected on the evidence.
