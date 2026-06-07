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



## One-command local UI

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
then asks for an alias-only profile, data dumps to import, and a data-poor questionnaire when the
user does not have much history yet.
Periodic check-ins use the cheeky-but-useful Dr Visit prompts:

```sh
health agreement show
health agreement accept --own-risk
health enroll --alias sol --birth-year 2018 --role child
health data-wishlist
health dr-visit --profile sol --cadence onboarding
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
