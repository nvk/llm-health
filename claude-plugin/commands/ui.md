---
description: "llm-health command: ui. Regenerate and open the local Assessment v2 static dashboard."
argument-hint: "[--wiki-root <path>] [--output <dir>] [--no-open]"
---

Use the health skill at `skills/health-concierge/SKILL.md`. Resolve the local `llm-health` repo/store, activate `.venv` if present, and map this slash command to the equivalent `health ui` workflow.

The command should prefer the configured HUB and `health config wiki-root` value. If the wiki root is missing, ask the user to configure it once with `health config wiki-root <health-assessments-topic-root>` or pass `--wiki-root` for this run. Keep output alias-only and do not store raw source paths in durable artifacts.
