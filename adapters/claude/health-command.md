# Claude Code adapter

Claude Code is the primary native command surface for `llm-health`.

Source tree:

```text
claude-plugin/
```

Commands map to the same CLI-backed intent families:

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

Examples:

```text
/health review alex
/consult alex auto baseline synthesis
/research alex flagged liver markers
```

The skill source of truth is `claude-plugin/skills/health-concierge/SKILL.md`. Run
`scripts/sync-agent-plugins.sh` after edits to regenerate Codex and OpenCode mirrors.

Health-facing commands require the local own-risk agreement. If missing, show `health agreement show` and accept with `health agreement accept --own-risk` before profile-specific work.
