# Own-risk agreement and disclaimer

`llm-health` is experimental local-first software for organizing health data, calculations,
questions, and research artifacts. It is not a clinician and does not create a clinician-patient
relationship.

Before a HUB can be initialized or used for health-facing commands, the user must explicitly accept
one own-risk agreement per local HUB:

```sh
health agreement show
health agreement accept --own-risk
# or during setup:
health config hub-path ~/health --init --accept-risk
```

Acceptance writes only `agreement.json` in the selected HUB with the agreement version and timestamp.
It does not store legal identity or profile data.

## Required user-facing points

Agent and UI surfaces should make these points visible during onboarding and easy to redisplay later:

- `llm-health` does not diagnose, prescribe, order tests, treat disease, or replace qualified care.
- The user is responsible for decisions, actions, delays, purchases, experiments, and omissions.
- Outputs may be wrong, incomplete, stale, overconfident, or mismatched to the profile.
- Do not use it for emergencies or urgent red-flag symptoms.
- Do not start, stop, combine, or change medications, supplements, procedures, devices, or
  preventive protocols solely because an agent suggested or questioned something.
- Children, pregnancy, serious illness, abnormal vitals, major symptoms, and high-risk interventions
  need extra caution and appropriate professional review.
- Research summaries are not proof; keep disagreement, uncertainty, conflicts, and endpoint quality
  visible.
- Raw medical documents and source paths stay out of Git, public chats, and exported artifacts.
- The package is provided as-is with no warranty.

## CLI enforcement

The CLI gates health-facing HUB commands. Commands such as `doctor`, `welcome`, `data-wishlist`,
`plugin-paths`, `specialists`, and `agreement show/status` remain available without acceptance so a
new user can inspect the package and read the disclaimer. Commands that read, write, or generate
profile-specific health artifacts require either an accepted HUB or a one-time setup flag such as
`--accept-risk`.

Use `health doctor` to inspect current agreement status.
