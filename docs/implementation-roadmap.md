# Implementation roadmap

## Phase 0 — scaffold

- Dependency-light Python package.
- CLI with `doctor`, `init`, `ingest-note`, `review`, `close-gaps`, `plan-research`.
- JSONL local store.
- Core models and unit tests.

## Phase A — data adapters

- Import de-identified canonical CSV/Parquet from health-assessment-v2.
- Export raw notes, research notes, claim cards, and log entries to `llm-wiki`.
- Add source-row/chart deep links.

## Phase B — chat/agent shell

- `@health` skill/instruction adapter.
- `/health` command aliases where supported.
- MCP tool server.
- Durable threads and answer cards.

## Phase C — deterministic engines

- Calculation specs and formula tests.
- Frequency resolver.
- Diagnostic gap engine v1.
- Medication/protocol collateral-damage ledger.

## Phase D — research agents

- Bounded multi-agent research workflows.
- Paper retrieval ladder: PubMed, PMC, Europe PMC, Crossref, OpenAlex, Unpaywall,
  Semantic Scholar, ClinicalTrials.gov, and user-provided PDFs.
- Claim graph and capture scoring.

## Phase E — UX

- Review landing page.
- New-results timeline.
- Gap closure board.
- Option/protocol cards.
- Clinician/self-experiment packets.
