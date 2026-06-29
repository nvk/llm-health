# llm-health

```text
 _ _                 _                _ _   _
| | |_ __ ___       | |__   ___  __ _| | |_| |__
| | | '_ ` _ \ _____| '_ \ / _ \/ _` | | __| '_ \
| | | | | | | |_____| | | |  __/ (_| | | |_| | | |
|_|_|_| |_| |_|     |_| |_|\___|\__,_|_|\__|_| |_|

        Your private, own-risk health concierge.
```

`llm-health` is a package-first, local-first health intelligence system for private labs,
wearables, records, self-reported context, timelines, reviews, diagnostic gaps, and research
queues.

It sits above deterministic health data tools: ingest events, summarize new results, open diagnostic
gaps, queue deeper research, compare advice lenses, and preserve provenance. Agent and chat surfaces
are interfaces, not the product story.

## Initial scope

This scaffold implements the core contracts for:

- event-driven quick reviews after new results;
- alias-only family history and kinship graph context;
- smart deep-research job planning;
- diagnostic-gap and test-candidate cards;
- least-harm / conservative-care option cards;
- medication collateral-damage and preventive-protocol review models;
- local JSONL storage suitable for a package-native vault or future `llm-wiki` adapter;
- a dependency-light CLI that works before the analytics/UI stack is installed.

It intentionally does **not** diagnose, prescribe, order tests, or auto-change care. It creates
reviewable cards, tasks, and research jobs. Use is explicitly at the user's own risk; the CLI gates
health-facing HUB commands behind an initial own-risk agreement.

## Release notes

Compressed changelog; see `CHANGELOG.md` for full test/privacy details.

| Version | Notes |
|---|---|
| **0.0.29** | Adds `health genomics` for local SNP/genotype import, QC, bundled annotation summaries, lab/med/family cross-reference cards, and confirmation-first PGx context. |
| **0.0.28** | First-run onboarding now points users to `health ui` early so the local board is not hidden. |
| **0.0.27** | Adds Ask parents interview template for long-form hereditary and family-pattern outreach. |
| **0.0.26** | Adds copyable Profile interview modal for baseline, follow-up-gap, and family-history outreach drafts. |
| **0.0.25** | Adds `health report` doctor/family PDF exports with flags, gaps, mini-trends, context, and privacy notes. |
| **0.0.24** | Adds Patient Profile tab with profile facts, family/history context, diagnostic gaps, research jobs, and source-vault timeline. |
| **0.0.23** | Assessment board now surfaces context-only profiles with notes, specialist cards, and source-vault counts. |
| **0.0.22** | Adds private source-vault cataloging and multipass source-audit for OCR/medium-confidence rows. |
| **0.0.21** | Fixes archive binary scanning so sanitized DuckDB/Parquet files are included instead of false-skipped. |
| **0.0.20** | Adds privacy-scanned `health archive` snapshots and scrubs v2 DuckDB/Parquet source-file/provider fields. |
| **0.0.19** | Dashboard export privacy: source filenames/provider aliases are scrubbed from `data.js`. |
| **0.0.18** | Superseded pending rows: later numeric follow-up removes old pending placeholders from active pending counts. |
| **0.0.17** | Fixes normalization QA edge cases for CBC percent rows, nucleated RBC, and thyroid unit symbols. |
| **0.0.16** | Broader unit normalization for CBC/thyroid/vitals and cleaner unitless-marker QA. |
| **0.0.15** | English/canonical display normalization plus QA review for translated labs and unit conversions. |
| **0.0.14** | Resolved-flag UI: later normal follow-up demotes old abnormal rows from active alerts. |
| **0.0.13** | Family graph: `health family`, hereditary/household tags, family risk notes, service/docs/plugin coverage. |
| **0.0.12** | Visible operator runtime: draft/list/show/finalize/traces plus fingerprint-first audit records. |
| **0.0.11** | Capability map, de-id preview/staging, and localhost service smoke surface. |
| **0.0.10** | Smarter chart overlay/stack defaults: domains, flagged-first, recent movement, context groups. |
| **0.0.9** | Assessment board polish: removed hero swoop and fixed badge contrast. |
| **0.0.8** | Squarer Basecamp-like UI texture and readable UI tags instead of raw enum labels. |
| **0.0.7** | Static dashboard fixed for direct `file://` open in Chrome/Safari, with regression test. |
| **0.0.6** | React + Mantine + Recharts Assessment board with cards, timelines, tables, themes, and privacy tests. |
| **0.0.5** | One-command `health ui` flow with saved wiki root, HUB export, open/no-open modes. |
| **0.0.4** | Assessment v2 compactness pass: fewer decorative rails, clickable chips/cards, source-row focus. |
| **0.0.3** | Profile/export hardening for alias-only enrollment and malformed v2 source rows. |
| **0.0.2** | Review-board UX, dynamic profile selectors, dark amber theme, and enrolled-profile exports. |
| **0.0.1** | Initial package: CLI/store, review/gaps/research cards, v2 bridge, agent surfaces, own-risk gate. |

## Runtime surfaces

| Host | Entry point | Notes |
|---|---|---|
| Claude Code | `/health`, `/review`, `/ingest`, `/research`, `/consult` | Primary command UX. |
| OpenAI Codex | `@health` | Marketplace plugin skill. |
| OpenCode | instruction file | Use `plugins/llm-health-opencode/skills/health/SKILL.md`. |
| Pi / generic agents | instruction file or `AGENTS.health.md` | Portable fallback when plugins are unavailable. |
| Terminal/Python | `health`, `llm-health`, `health-v2` | Deterministic CLI and local analytics. |

## Homebrew install

Public tap install target:

```sh
brew tap nvk/tap
brew install llm-health
health agreement show
health config hub-path ~/health --init --accept-risk
health doctor
```

Use any private local/synced directory for the HUB. Keep raw medical dumps outside Git.

See `docs/homebrew.md`.

## Virtualenv-first development

Use a local virtual environment for all work:

```sh
make install-v2
. .venv/bin/activate
```

For core-only work:

```sh
make install
```

## HUB setup

`llm-health` supports a default HUB/store path in `~/.config/llm-health/config.json`.

```sh
health agreement show
health config hub-path ~/health --init --accept-risk
health doctor
```

Then commands such as `health review --profile rod` and `health sync-v2 ...` use that HUB by default unless `--store` is supplied.




## Genomics and SNP context

`health genomics` imports local raw genotype text files by fingerprint and keeps raw genetic file
paths out of the HUB. It can show source QC, bundled marker annotations, confirmation-first
lab/med/family cross-reference cards, and PGx context prompts:

```sh
health genomics import ./synthetic-genotype.txt --profile rod --accept-genetic-risk
health genomics qc --profile rod
health genomics crossref --profile rod
health genomics pgx --profile rod
health genomics confirm-list --profile rod
```

Genomic cards are own-risk review artifacts only: not diagnosis, not prescribing, not test ordering,
and high-impact findings require clinical confirmation. See `docs/genomics.md`.

## Source vault and source audit

For private source re-audit, catalog originals by hash and run extraction/consistency checks against
canonical rows:

```sh
health source-vault init
health source-vault add <file-or-folder> --wiki-root <health-assessments-topic-root>
health source-vault add <file-or-folder> --wiki-root <health-assessments-topic-root> --copy --accept-raw-storage
health source-audit run --profile rod --focus medium
```

The vault manifest stores no raw paths or filenames. Copied raw blobs are hash-named and excluded
from normal `health archive` snapshots. See `docs/source-vault-audit.md`.

## HUB archives

Create a compressed, privacy-scanned snapshot of the private HUB:

```sh
health archive create
health archive list
health archive verify <archive.tar.gz>
```

Archives go to `<resolved HUB>/archives/` and include a manifest with checksums plus any privacy
skips. This is a de-identified HUB snapshot, not a raw PDF/XML/Apple-export backup. See
`docs/archives.md`.


## PDF reports

Create local, de-identified PDFs for two audiences:

```sh
health report --profile rod --audience both
health report --profile rod --audience doctor --range 18mo
health report --profile cara --audience family --output-dir ~/Desktop/health-packets
```

Doctor reports are concise clinician briefs with source ranges, active flags, pending rows,
diagnostic gaps, family/context notes, mini-trends, and a recent source-row appendix. When the
health-assessments wiki root is configured, reports use the full v2 canonical history like the GUI.
Family reports are plain-language summaries with watch items and questions to ask. Reports are
own-risk discussion packets, not medical advice; see `docs/reports.md`.

## One-command local UI

The Profile tab includes a **Draft interview** modal that creates copyable text questionnaires for baseline intake, follow-up gaps, family-history outreach, and a longer ask-your-parents hereditary questionnaire. Use it to email/chat relatives or profile holders, then record replies as context notes or new source data.

After the HUB and health-assessments wiki root are configured once, users can regenerate and open the
static Assessment v2 UI with a single command:

```sh
health config hub-path ~/health --init --accept-risk
health config wiki-root <health-assessments-topic-root>
health ui
```

`health ui` exports to `<resolved HUB>/v2-web/` and opens `index.html`. Use `--no-open` for scripts or
`--output <dir>` to write somewhere else. The command requires the local own-risk agreement and uses
only de-identified canonical CSV exports. The packaged static board is prebuilt from React + Mantine +
Recharts assets, so end users do not need Node or a web server.

## First-run onboarding

Run `health` or `health welcome` for the first-run flow. It starts with the own-risk disclaimer,
then asks for an alias-only profile, data dumps to import, points users to the local UI early, and a data-poor questionnaire when the
user does not have much history yet.
Periodic check-ins use the cheeky-but-useful Dr Visit prompts:

```sh
health agreement show
health agreement accept --own-risk
health enroll --alias sol --birth-year 2018 --role child
health data-wishlist
health dr-visit --profile sol --cadence onboarding
health ui  # open the local Assessment Board after setup/import
health dr-visit --profile sol --cadence monthly --sources
health test-battery --profile sol --scope expanded --sources
health consult --profile sol --specialist auto
health specialists --short  # broad category agents
```

See `docs/onboarding-and-dr-visit.md` and `docs/test-battery-layer.md`.

## Quick start

```sh
cd llm-health
PYTHONPATH=src python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m llm_health doctor
PYTHONPATH=src python3 -m llm_health init --store .llm-health --accept-risk
PYTHONPATH=src python3 -m llm_health ingest-note --profile rod --marker ALT --value 76 --unit U/L --category liver --flag high
PYTHONPATH=src python3 -m llm_health review --profile rod
PYTHONPATH=src python3 -m llm_health close-gaps --profile rod
```

If installed as a package:

```sh
pip install .
health doctor
health result --profile rod --marker mercury
health review --profile rod
```

## Capability map and recipes

For a live map of commands, modules, dependencies, privacy contracts, and test coverage:

```sh
health capabilities
health capabilities --json
health capabilities --kind privacy
```

See `docs/feature-map.md`, `docs/recipes.md`, `docs/family-history.md`, and `docs/operator-runtime.md` for copy/paste flows, including family history, de-id staging, local service smoke tests, and visible draft/finalize workflows.

## health-assessment-v2 included

The former `health-assessment-v2` code is repackaged under `llm_health.assessment_v2` and exposed as `health-v2`.
The Homebrew formula installs the package CLI plus `v2-core` analytics/static-export support; live Panel serving remains an optional `llm-health[v2]` dev extra. See `docs/v2-repackaging.md`.

## Agent plugins and adapters

First-class agent surfaces are included, modelled after `llm-wiki`:

- Claude Code native plugin and slash-command docs: `claude-plugin/`
- Codex marketplace plugin and `@health` skill: `plugins/llm-health/`
- OpenCode/Pi instruction file: `plugins/llm-health-opencode/`
- Portable fallback for any agent: `adapters/agents/AGENTS.health.md`
- Marketplace files: `.agents/plugins/marketplace.json` and `.claude-plugin/marketplace.json`

Installed wheels/Homebrew also include templates discoverable with:

```sh
health plugin-paths
health plugin-paths --kind claude
health plugin-paths --kind codex
health plugin-paths --kind opencode
health plugin-paths --kind agents
```

See `docs/plugin-distribution.md`.

## Design posture

- **Deterministic first**: calculations and source rows before LLM prose.
- **Capture-aware**: mainstream, frontier, edge, contrarian, capture, and risk lenses are kept separate.
- **Least-harm aware**: doing less, watchful waiting, home remedies, and symptom tolerance are valid protocol options when red-flag gated.
- **Collateral-damage aware**: medication/vaccine/preventive protocols are evaluated by absolute benefit, absolute harm, subgroup fit, alternatives, and unknowns.
- **Own-risk gated**: health-facing commands require a local agreement acceptance per HUB.
- **Local/private by default**: no raw medical documents or source paths in Git.

## Repo layout

```text
src/llm_health/         Python package
  core/                 typed models, constants, privacy guard
  engine/               review trigger, gap detection, least-harm planning
  research/             research job contracts and retrieval ladder skeleton
  stores/               local JSONL store
  adapters/             llm-wiki and agent adapter skeletons
docs/                   design docs
configs/                example config
data/                   ignored local data workspace
tests/                  stdlib unittest suite
```

See `docs/implementation-roadmap.md` for the next build phases.

## Design docs

- `docs/architecture.md`
- `docs/event-driven-review.md`
- `docs/diagnostic-gap-layer.md`
- `docs/test-battery-layer.md`
- `docs/specialist-agents.md` (broad specialist/category-agent routing)
- `docs/therapeutic-minimalism.md`
- `docs/collateral-damage-ledger.md`
- `docs/research-lenses.md`
- `docs/implementation-roadmap.md`

## License

MIT. Copyright (c) 2026 nvk.
