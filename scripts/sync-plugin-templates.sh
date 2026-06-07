#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
scripts/sync-agent-plugins.sh
mkdir -p \
  src/llm_health/plugin_templates/codex \
  src/llm_health/plugin_templates/claude \
  src/llm_health/plugin_templates/opencode \
  src/llm_health/plugin_templates/agents
rsync -a --delete plugins/llm-health/ src/llm_health/plugin_templates/codex/llm-health/
rsync -a --delete claude-plugin/ src/llm_health/plugin_templates/claude/health/
rsync -a --delete plugins/llm-health-opencode/ src/llm_health/plugin_templates/opencode/llm-health/
rsync -a --delete adapters/agents/ src/llm_health/plugin_templates/agents/
echo "plugin templates synced"
