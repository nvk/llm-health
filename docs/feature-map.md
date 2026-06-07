# llm-health feature map

`health capabilities` is the live command for this table. It gives agents and users a quick map of
what the package can do, which module owns it, what privacy contract applies, and which tests/docs
cover it.

```sh
health capabilities
health capabilities --kind privacy
health capabilities --json
```

## Capability classes

| Class | What it covers | Commands |
|---|---|---|
| Core | Setup, agreement, onboarding, runtime checks, public registry | `health doctor`, `health agreement`, `health welcome`, `health capabilities` |
| Data | Alias profiles, observations, self-reported context, v2 sync | `health enroll`, `health profiles`, `health ingest-note`, `health self-report`, `health sync-v2` |
| Review | Quick reviews, result lookup, diagnostic gaps, test candidates, least-harm cards | `health review`, `health result`, `health close-gaps`, `health test-battery`, `health least-harm` |
| Research | Research queues and broad category-agent consults | `health plan-research`, `health specialists`, `health consult` |
| UI | Static local Assessment board | `health ui` |
| Agent | Packaged templates and visible draft/finalize runtime | `health plugin-paths`, `health operator` |
| Privacy | De-identification adapter and privacy guards | `health deid extract`, `health deid preview`, `health deid apply` |
| Service | Local API skeleton for future GUI/chat clients | `health service --local` |

## Privacy contracts

- Health-facing commands require the local own-risk agreement.
- Durable artifacts must stay alias-only and must not contain raw source paths, raw file names,
  legal names, full birth dates, emails, health numbers, or raw Apple source/device names.
- `health deid` is the pre-HUB adapter: raw input is redacted in memory, and `apply` writes only
  redacted staging text plus entity metadata hashes.
- `health service` binds localhost by default and refuses non-local binds unless the user explicitly
  passes `--allow-nonlocal`.

## Current scaffolds

Two capabilities are intentionally marked as scaffolds:

1. **De-identification adapter** — local regex backend, safe entity metadata, preview/apply staging.
   Future adapters can add OCR/PDF parsers, NER, or user-supplied de-id services without changing the
   command shape.
2. **Local service** — route contract and optional FastAPI/uvicorn server. The smoke command works
   without optional service dependencies, so packaging and agents can validate the surface cheaply.
3. **Visible operator runtime** — draft/finalize lifecycle plus fingerprint-first traces for chat or
   agent workflows that need a visible plan before writes.

Run this anytime after install:

```sh
health capabilities --json | python -m json.tool | head
```
