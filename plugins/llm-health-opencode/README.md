# llm-health for OpenCode and Pi

Load this skill as an instruction file in OpenCode or any compatible coding agent. It uses the same
behavior contract as the Claude Code plugin and Codex plugin, backed by the `health` CLI.

## Prerequisite

Install `llm-health` first so the `health` command is on PATH:

```sh
brew tap nvk/tap
brew install llm-health
health agreement show
health config hub-path ~/health --init --accept-risk
health doctor
```

## OpenCode quick install

Add this to your project's `opencode.json`:

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

If your health HUB lives somewhere else, allow that path instead of `~/health/**`.

For a local checkout:

```sh
cp plugins/llm-health-opencode/skills/health/SKILL.md ~/.config/opencode/AGENTS.md
```

## Pi / generic instruction-file agents

Point the agent at the same skill file:

```sh
pi --instructions path/to/llm-health/plugins/llm-health-opencode/skills/health/SKILL.md
```

## Usage

Talk naturally:

- "@health review my latest results"
- "Run a monthly Dr Visit for profile alex"
- "Close diagnostic gaps for this profile"
- "Compare this medication against lower-collateral alternatives"
- "Queue deep research for the flagged liver markers"

## Generated mirror

This directory is generated from `claude-plugin/skills/health-concierge/SKILL.md` by
`scripts/sync-agent-plugins.sh`. Do not edit the skill here by hand.

Health-facing work requires the local own-risk agreement (`health agreement show`, then `health agreement accept --own-risk`).
