---
description: "llm-health command: onboard. Welcome a new user, enroll alias-only profiles, request data dumps, and run the data-poor questionnaire."
argument-hint: "[alias/profile context]"
allowed-tools: Read, Write, Edit, Glob, Bash(pwd:*), Bash(ls:*), Bash(test:*), Bash(python:*), Bash(health:*), Bash(llm-health:*), Bash(health-v2:*)
---

Use the health skill at `skills/health-concierge/SKILL.md`. Resolve the local `llm-health`
repo/store, activate `.venv` if present, then map this slash command to:

```sh
health welcome
health enroll --alias <alias> --birth-year <yyyy> [--birth-month <1-12>] --role <context>
health data-wishlist
health dr-visit --profile <alias> --cadence onboarding
```

If alias/birth-year are not known, ask concise follow-up questions. Privacy is mandatory: aliases
only, no raw source paths/filenames, no legal names, no full DOBs, no emails, no raw Apple
source/device names in generated artifacts.

Before profile-specific health work, ensure the selected HUB has accepted the own-risk agreement. If missing, show `health agreement show` and ask the user to accept with `health agreement accept --own-risk`; do not continue as medical advice or an emergency workflow.
