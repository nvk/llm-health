# llm-health Agent Instructions

This repo is a package-first, local-first health intelligence scaffold. Treat all health data as private.

## Privacy and data handling

- Health-facing work must respect the local own-risk agreement gate. Use `health agreement show`
  and `health agreement accept --own-risk` (or setup with `--accept-risk`) before profile-specific
  workflows.
- Never commit raw PDFs, Apple Health XML/CDA files, raw source filenames, source filesystem paths, legal names, full birth dates, health numbers, emails, or raw Apple source/device names.
- Never commit raw genotype files, browser-selected genotype filenames/paths, or dense genome-wide
  genotype-call stores. Non-local/cloud LLMs must not read raw genotype text or
  `genomics/variants/` JSONL directly; use rendered `health genomics` outputs and matched SNP
  analysis cards instead. Dense calls are only for explicitly approved local FOSS/no-network
  workflows.
- Use aliases only for built-in/demo profiles: `rod` and `cara`.
- Keep raw inputs outside Git. Use environment variables or local config for private paths.
- Generated data under `data/` and `.llm-health/` is ignored by default.

## Implementation style

- Prefer Python-first, deterministic, typed, reviewable code before LLM summaries.
- Keep LLM/research outputs as queued jobs and durable artifacts; do not hide them in chat memory.
- Every inference-like output must preserve visible tags: `OBSERVED`, `DERIVED`, `WEARABLE_CONTEXT`, `CONTEXT`, `INFERENCE`, `DATA_GAP`, `QA_ISSUE`, `TEST_CANDIDATE`, `LOW_INTERVENTION`, `COLLATERAL_DAMAGE`, `PROTOCOL_REVIEW`.
- Use a skeptical/capture-aware evidence model, but do not hard-code conclusions. Compare mainstream, frontier, edge, contrarian, capture, and risk lenses claim-by-claim.
- Prefer least-harm, reversible, monitored options where appropriate; always include red-flag/escalation thresholds for conservative-care protocols.
- Medication, vaccine, supplement, and home-remedy discussions must be framed as review/protocol artifacts, not autonomous medical instructions.
- Add tests for profile exclusivity, PII guards, event trigger semantics, diagnostic-gap scoring, and serialization.
