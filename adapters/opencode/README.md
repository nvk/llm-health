# OpenCode adapter

The generated OpenCode/Pi instruction-file adapter lives at:

```text
plugins/llm-health-opencode/skills/health/SKILL.md
```

Use the raw URL from the public repo in `opencode.json`:

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

If your health HUB lives elsewhere, allow that directory instead of `~/health/**`.

Health-facing work requires the local own-risk agreement (`health agreement show`, then `health agreement accept --own-risk`).
