---
description: "llm-health command: dr-visit. Run cadence-aware health check-in questions for an enrolled alias."
argument-hint: "<alias> [weekly|monthly|quarterly|annual|pre-lab|post-result|onboarding]"
allowed-tools: Read, Write, Edit, Glob, Bash(pwd:*), Bash(ls:*), Bash(test:*), Bash(python:*), Bash(health:*), Bash(llm-health:*), Bash(health-v2:*)
---

Use the health skill at `skills/health-concierge/SKILL.md`. Resolve the local `llm-health`
repo/store, activate `.venv` if present, and map this slash command to:

```sh
health dr-visit --profile <alias> --cadence <cadence> --sources
```

Default cadence is `monthly` unless the user says onboarding, weekly, quarterly, annual, pre-lab,
or post-result. Keep the tone lightly cheeky but useful. Store any user answers as `CONTEXT`
artifacts only after confirming the alias and avoiding raw identifiers/source paths.

Before profile-specific health work, ensure the selected HUB has accepted the own-risk agreement. If missing, show `health agreement show` and ask the user to accept with `health agreement accept --own-risk`; do not continue as medical advice or an emergency workflow.
