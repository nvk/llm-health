# Agentic UI Design Packet: llm-health GUIs

llm-health GUIs should behave like private **health review boards**, not generic dashboards. They package de-identified data into reviewable packets with source evidence, deterministic tags, and own-risk disclaimers.

## Jobs to be done

1. Show what needs review now.
2. Show domain coverage and gaps.
3. Explain what the chart is doing before the user interprets it.
4. Keep source rows/export one click away.
5. Preserve local-first privacy and alias-only profile boundaries.

## Required workflow

```text
Review queue → domain map → timeline evidence → matching source rows/export
```

Controls are secondary. The default screen must already be useful.

## Design principles

- Scientific, dense, calm, text-first.
- Meaning is carried by stable tags and concise copy, not color alone.
- Dark mode uses amber accent; light mode may use blue.
- All-category overview by default; focused-category packets for deeper review.
- Rod/Cara and future profiles must be mutually exclusive unless a comparison view is deliberately built and labeled.

## Required visible tags

`OBSERVED`, `DERIVED`, `WEARABLE_CONTEXT`, `CONTEXT`, `INFERENCE`, `DATA_GAP`, `QA_ISSUE`, `TEST_CANDIDATE`, `LOW_INTERVENTION`, `COLLATERAL_DAMAGE`, `PROTOCOL_REVIEW`.

## Static v2 dashboard requirements

- Own-risk notice in the shell.
- Profile-state strip: selected alias, plotted-capable row count, source notes, pending count.
- Domain map before charts.
- Review cards that include explicit no-wearable-data states.
- View brief above timelines that explains scope, plot semantics, source state, and overlays.
- Stack = raw units; overlay = normalized comparison, visibly tagged `INFERENCE` / normalized.
- Pending/non-numeric rows are never plotted as dots.
- Source note rings are labeled as source notes.

## Privacy release checklist

Do not ship raw PDFs/XML/CDA, generated private data, source filesystem paths, source filenames, legal names, full DOBs, emails, health numbers, or raw Apple source/device names.
