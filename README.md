# llm-health

`llm-health` is a package-first, local-first health intelligence scaffold for coding agents,
chat UIs, and reproducible Python workflows.

It is designed to sit above deterministic health data tools: ingest events, summarize new results,
open diagnostic gaps, queue deeper research, compare advice lenses, and preserve provenance.

## Initial scope

This scaffold implements the core contracts for:

- event-driven quick reviews after new results;
- smart deep-research job planning;
- diagnostic-gap and test-candidate cards;
- least-harm / conservative-care option cards;
- medication collateral-damage and preventive-protocol review models;
- local JSONL storage suitable for a package-native vault or future `llm-wiki` adapter;
- a dependency-light CLI that works before the analytics/UI stack is installed.

It intentionally does **not** diagnose, prescribe, order tests, or auto-change care. It creates
reviewable cards, tasks, and research jobs. Use is explicitly at the user's own risk; the CLI gates
health-facing HUB commands behind an initial own-risk agreement.

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
