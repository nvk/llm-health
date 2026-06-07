---
description: "llm-health command: consult. Run bounded specialist/category-agent consults that produce SPECIALIST_NOTE artifacts."
argument-hint: "<alias> [auto|internal_medicine|liver_biliary_gi|toxins_exposures|...] [topic]"
allowed-tools: Read, Write, Edit, Glob, Bash(pwd:*), Bash(ls:*), Bash(test:*), Bash(python:*), Bash(health:*), Bash(llm-health:*), Bash(health-v2:*)
---

Use the health skill at `skills/health-concierge/SKILL.md`. Resolve the local `llm-health`
repo/store, activate `.venv` if present, and map this slash command to:

```sh
health consult --profile <alias> --specialist <auto|category_agent_id> --topic <optional topic>
```

Default to `--specialist auto`. Use `internal_medicine` when the user wants whole-profile synthesis,
triage, red-flag screen, or prioritization. Use category ids such as `liver_biliary_gi`,
`toxins_exposures`, `meds_supplements`, and `test_gap_steward` for focused work; legacy ids such as
`liver_gi`, `toxicology_heavy_metals`, `medication_collateral`, and `diagnostic_gap_steward` remain
aliases. Use `health specialists --short` to list ids and `health specialist-notes --profile <alias>`
to review stored artifacts.

Privacy is mandatory. Specialist/category-agent consults are `SPECIALIST_NOTE` review artifacts,
not diagnoses, prescriptions, or orders.

Before profile-specific health work, ensure the selected HUB has accepted the own-risk agreement. If missing, show `health agreement show` and ask the user to accept with `health agreement accept --own-risk`; do not continue as medical advice or an emergency workflow.
