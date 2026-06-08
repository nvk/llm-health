---
description: "llm-health command: report. Generate doctor/family de-identified PDF packets."
argument-hint: "--profile <alias> [--audience doctor|family|both] [--range all|30d|90d|ytd|18mo] [--output-dir <dir>]"
allowed-tools: Read, Bash(pwd:*), Bash(ls:*), Bash(test:*), Bash(python:*), Bash(health:*), Bash(llm-health:*)
---

Use the health skill at `skills/health-concierge/SKILL.md`. Resolve the local `llm-health`
repo/store, activate `.venv` if present, and map this slash command to `health report`.

Default to `health report --profile <alias> --audience both` unless the user asks for only a
clinician brief or only a family/plain-language packet. Reports are alias-only local PDFs; do not add
raw source filenames, source paths, legal names, full birth dates, emails, or raw Apple source/device
names. Remind users the packet is own-risk discussion material, not medical advice, and source records
must be verified before decisions.
