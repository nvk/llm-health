#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_SKILL="$ROOT/claude-plugin/skills/health-concierge/SKILL.md"
CODEX_SKILL="$ROOT/plugins/llm-health/skills/health/SKILL.md"
OPENCODE_SKILL="$ROOT/plugins/llm-health-opencode/skills/health/SKILL.md"

if [ ! -f "$SOURCE_SKILL" ]; then
  echo "Missing Claude source skill: $SOURCE_SKILL" >&2
  exit 1
fi

mkdir -p "$(dirname "$CODEX_SKILL")" "$(dirname "$OPENCODE_SKILL")" "$ROOT/plugins/llm-health/skills/health/agents"

python3 - "$SOURCE_SKILL" "$CODEX_SKILL" "$OPENCODE_SKILL" <<'PY'
import sys
from pathlib import Path

source, codex, opencode = map(Path, sys.argv[1:4])
text = source.read_text()
start = text.find("---\n")
end = text.find("\n---\n", start + 4)
if start != 0 or end == -1:
    raise SystemExit(f"Unexpected frontmatter in {source}")
body = text[end + 5 :]

source_runtime = """## Runtime integration

Claude Code is the primary command UX. Native slash-command docs live in `claude-plugin/commands/`
and map `/health`, `/review`, `/ingest`, `/research`, `/close-gaps`, `/med-review`,
`/protocol-review`, `/sync-v2`, `/ui`, `/dr-visit`, `/test-battery`, and `/consult` to the same CLI-backed
intent families. Treat `@health` and natural-language health requests as the same concierge intent.
Generated Codex, OpenCode, Pi, and portable AGENTS mirrors adapt invocation wording; they do not fork
the behavior contract.
"""

codex_runtime = """## Codex integration notes

Codex plugins package skills and metadata. They do not register Claude-style custom slash commands.
Treat `/health`, `/review`, `/ingest`, and other slash-command examples as shorthand for the same
workflow expressed in natural language or through explicit `@health` invocation. Use the installed
`health` CLI for deterministic reads/writes, and keep durable artifacts alias-only.
"""

opencode_runtime = """## OpenCode / Pi integration notes

This skill is loaded as an instruction file. OpenCode and Pi do not have Claude-style slash commands
or Codex-style `@health` plugin mentions by default. Treat `@health`, `/health`, and command examples
as natural-language shorthand for the same CLI-backed workflow. The `health` CLI should be installed
and on PATH. OpenCode sandboxes external directories; allow the health HUB and `~/.config/llm-health/`
in `opencode.json` when the store is outside the project.
"""

if source_runtime not in body:
    raise SystemExit("Claude runtime section not found; update sync script")

codex_fm = """---
name: health
description: >
  Local-first health intelligence manager for Codex. Use it when the user says
  @health, /health, llm-health, asks to review health results, ingest labs,
  sync health-assessment-v2 data, close diagnostic gaps, suggest tests, compare
  conservative/least-harm options, review medication collateral damage,
  evaluate preventive protocols, queue deep paper/product research, or package
  de-identified health artifacts without doxing.
---
"""

opencode_fm = """---
name: health
description: >
  Local-first health intelligence manager for OpenCode and Pi. Use it when the user says
  @health, /health, llm-health, asks to review health results, ingest labs,
  sync health-assessment-v2 data, close diagnostic gaps, suggest tests, compare
  conservative/least-harm options, review medication collateral damage,
  evaluate preventive protocols, queue deep paper/product research, or package
  de-identified health artifacts without doxing.
---
"""

codex.write_text(codex_fm + body.replace(source_runtime, codex_runtime))
opencode.write_text(opencode_fm + body.replace(source_runtime, opencode_runtime))
PY

cat > "$ROOT/plugins/llm-health/skills/health/agents/openai.yaml" <<'EOF'
interface:
  display_name: "LLM Health"
  short_description: "Local-first health reviews, diagnostic gaps, least-harm protocols, and research queues."
  brand_color: "#B45309"
  default_prompt: "Review the latest health results and show quick summary plus diagnostic gaps."

policy:
  allow_implicit_invocation: true
EOF

echo "Synced Codex and OpenCode health skills from Claude source."
