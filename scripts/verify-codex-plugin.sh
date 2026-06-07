#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VALIDATOR="${CODEX_PLUGIN_VALIDATOR:-}"
PYTHON="${PYTHON:-python3}"
if [ -x "$ROOT/.venv/bin/python" ]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
if [ -f "$VALIDATOR" ]; then
  "$PYTHON" "$VALIDATOR" "$ROOT/plugins/llm-health"
else
  test -f "$ROOT/plugins/llm-health/.codex-plugin/plugin.json"
  test -f "$ROOT/plugins/llm-health/skills/health/SKILL.md"
  echo "Codex validator not found; structural plugin check passed"
fi
