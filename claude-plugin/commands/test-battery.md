---
description: "llm-health command: test-battery. Suggest profile-aware TEST_CANDIDATE batteries by priority, difficulty, category, and diagnostic gaps."
argument-hint: "<alias> [core|expanded|complete] [category]"
allowed-tools: Read, Write, Edit, Glob, Bash(pwd:*), Bash(ls:*), Bash(test:*), Bash(python:*), Bash(health:*), Bash(llm-health:*), Bash(health-v2:*)
---

Use the health skill at `skills/health-concierge/SKILL.md`. Resolve the local `llm-health`
repo/store, activate `.venv` if present, and map this slash command to:

```sh
health test-battery --profile <alias> --scope <core|expanded|complete> --category <category> --sources
```

Default scope is `expanded` and category is `all`. If the user asks for gap closure, use
`--category gaps`. If the user asks for a current best-ideas refresh, add `--queue-research` and
then inspect `health plan-research --profile <alias>`.

Privacy is mandatory. These are `TEST_CANDIDATE` artifacts, not orders or prescriptions.

Before profile-specific health work, ensure the selected HUB has accepted the own-risk agreement. If missing, show `health agreement show` and ask the user to accept with `health agreement accept --own-risk`; do not continue as medical advice or an emergency workflow.
