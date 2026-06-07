# LLM Health — Portable Agent Instructions

Use this file when an agent does not support native Claude Code, Codex, or OpenCode plugins. It is a
portable protocol for working with `llm-health` through the `health` CLI.

## What this is

`llm-health` is a local-first health intelligence package. It creates typed, reviewable artifacts:
observations, context notes, quick-review cards, diagnostic gaps, test candidates, conservative-care
cards, medication/protocol reviews, category-agent consult notes, and research jobs.

It does not diagnose, prescribe, or order tests. It helps users organize data, ask better questions,
track uncertainty, and prepare safer reviews. Health-facing HUB commands require explicit own-risk
acceptance.

## Privacy rules

- Use alias-only profiles.
- Do not write legal names, full birth dates, health numbers, emails, source file paths, raw medical
  filenames, raw Apple source/device names, PDFs, XML/CDA files, or other private dumps into output.
- Store raw inputs outside Git. Store only de-identified rows/artifacts in the `llm-health` HUB.
- Preserve visible tags where applicable: `OBSERVED`, `DERIVED`, `WEARABLE_CONTEXT`, `CONTEXT`,
  `INFERENCE`, `DATA_GAP`, `QA_ISSUE`, `TEST_CANDIDATE`, `LOW_INTERVENTION`,
  `COLLATERAL_DAMAGE`, `PROTOCOL_REVIEW`, `SPECIALIST_NOTE`, `RED_FLAG_GATED`.

## Runtime setup

Prefer an installed package:

```sh
health doctor
health agreement show
health config hub-path ~/health --init --accept-risk
```

Resolution order is explicit `--store`, then `LLM_HEALTH_HUB`, then
`~/.config/llm-health/config.json`, then local `.llm-health/`.

## Core workflows

```sh
health welcome
health agreement show
health agreement accept --own-risk
health enroll --alias alex --birth-year 1983 --role adult
health data-wishlist
health dr-visit --profile alex --cadence onboarding
health ingest-note --profile alex --marker ALT --value 76 --unit U/L --category liver --flag high
health review --profile alex
health result --profile alex --marker mercury
health context --profile alex
health self-report --profile alex --subject GI --status "self-reported fine" --note "Current GI status is fine."
health close-gaps --profile alex
health test-battery --profile alex --scope expanded --sources
health specialists --short
health consult --profile alex --specialist auto
health plan-research --profile alex --topic "flagged liver markers"
health med-review --profile alex --active antibiotic --indication unknown
health protocol-review --profile alex "flu shot"
```

## Operating style

1. Confirm the HUB has accepted the own-risk agreement before profile-specific work.
2. Run deterministic CLI reads before interpreting.
3. State what is observed versus derived or inferred.
4. Use current context notes before trend conclusions.
5. Keep mainstream, frontier, edge, contrarian, capture, inversion, and risk lenses separated.
6. For high-stakes or current medical claims, use current primary/authoritative sources and cite them.
7. Suggest tests as `TEST_CANDIDATE` cards, not orders.
8. Include red-flag/escalation thresholds for conservative-care or watchful-waiting options.
9. Queue deep research when a result is flagged, changing fast, high leverage, or conflicts with context.

## Fuzzy intent examples

- "@health what's my mercury" → `health result --profile <alias> --marker mercury`
- "@health current concerns based on trends" → read context, results, quick reviews, then summarize.
- "@health GI is fine" → store `health self-report` as `CONTEXT`.
- "@health close gaps" → `health close-gaps` and explain context-first questions plus candidates.
- "@health run liver consult" → `health consult --specialist liver_biliary_gi`.
