# Agent and plugin distribution

`llm-health` mirrors the `llm-wiki` distribution model: one behavior contract, thin runtime
packaging layers.

## Runtime matrix

| Host | Surface | Source tree | Install path |
|---|---|---|---|
| Claude Code | Native slash commands and skill | `claude-plugin/` | `claude plugin install health@llm-health` once public marketplace is live |
| OpenAI Codex | Marketplace plugin, `@health` skill | `plugins/llm-health/` | `codex plugin marketplace add nvk/llm-health` once public marketplace is live |
| OpenCode | Instruction file | `plugins/llm-health-opencode/` | Add raw `SKILL.md` URL to `opencode.json` |
| Pi / instruction-file agents | Instruction file | `plugins/llm-health-opencode/skills/health/SKILL.md` | `pi --instructions ...` |
| Any LLM agent | Portable protocol | `adapters/agents/AGENTS.health.md` | Copy into project/context |

## Source of truth

Claude Code is the primary UX. Edit:

```text
claude-plugin/skills/health-concierge/SKILL.md
```

Then regenerate runtime mirrors:

```sh
scripts/sync-agent-plugins.sh
scripts/sync-plugin-templates.sh
```

Generated mirrors:

- `plugins/llm-health/skills/health/SKILL.md` for Codex.
- `plugins/llm-health-opencode/skills/health/SKILL.md` for OpenCode/Pi.
- packaged copies under `src/llm_health/plugin_templates/` for installed wheels/Homebrew.

## Claude Code

Repo plugin source:

```text
claude-plugin/
```

Marketplace file:

```text
.claude-plugin/marketplace.json
```

Packaged template path after install:

```sh
health plugin-paths --kind claude
```

Primary command UX:

```text
/health
/review
/ingest
/research
/close-gaps
/med-review
/protocol-review
/sync-v2
/dr-visit
/test-battery
/consult
```

## Codex

Repo plugin source:

```text
plugins/llm-health/
```

Marketplace file:

```text
.agents/plugins/marketplace.json
```

Packaged template path after install:

```sh
health plugin-paths --kind codex
```

Validate locally when the Codex plugin validator is available:

```sh
CODEX_PLUGIN_VALIDATOR=/path/to/validate_plugin.py scripts/verify-codex-plugin.sh
```

Without a validator the script performs a structural check.

## OpenCode / Pi

Instruction-file source:

```text
plugins/llm-health-opencode/skills/health/SKILL.md
```

Packaged template path after install:

```sh
health plugin-paths --kind opencode
```

Example `opencode.json`:

```json
{
  "instructions": ["https://raw.githubusercontent.com/nvk/llm-health/main/plugins/llm-health-opencode/skills/health/SKILL.md"],
  "permission": {
    "external_directory": {
      "~/health/**": "allow",
      "~/.config/llm-health/**": "allow"
    }
  }
}
```

## Portable AGENTS

Portable instruction file:

```sh
health plugin-paths --kind agents
```

Copy `AGENTS.health.md` into agents that do not support plugins or skill frontmatter.

## Command parity

All surfaces must respect the same initial own-risk gate. If a HUB is not accepted, route the user
to `health agreement show` and `health agreement accept --own-risk`, or use
`health config hub-path ~/health --init --accept-risk` during setup.

All surfaces route to the same intent families:

- `@health review alex`
- `/health review alex`
- `health review --profile alex`
- `health sync-v2 --profile alex --wiki-root <deidentified-topic-root>`

All releases must pass privacy checks before public publishing.
