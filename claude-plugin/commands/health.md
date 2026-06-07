---
description: "llm-health command: health. Route to the local-first health concierge workflow with alias-only privacy, typed artifacts, diagnostic gaps, and research queues."
argument-hint: "[natural language args]"
allowed-tools: Read, Write, Edit, Glob, Bash(pwd:*), Bash(ls:*), Bash(test:*), Bash(python:*), Bash(health:*), Bash(llm-health:*), Bash(health-v2:*)
---

Use the health skill at `skills/health-concierge/SKILL.md`. Resolve the local `llm-health` repo/store, activate `.venv` if present, and map this slash command to the equivalent `health health` or natural-language intent.

Privacy is mandatory: aliases only, no raw source paths/filenames, no legal names, no full DOBs, no emails, no raw Apple source/device names in generated artifacts.

Before profile-specific health work, ensure the selected HUB has accepted the own-risk agreement. If missing, show `health agreement show` and ask the user to accept with `health agreement accept --own-risk`; do not continue as medical advice or an emergency workflow.
