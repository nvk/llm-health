#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [ -d .venv ]; then
  # shellcheck disable=SC1091
  . .venv/bin/activate
fi
scripts/sync-plugin-templates.sh
scripts/verify-codex-plugin.sh
python -m compileall -q src
python -m pytest -q
python -m ruff check .
scripts/verify-privacy.sh
python -m build --wheel --sdist >/tmp/llm-health-build.log 2>&1 || {
  cat /tmp/llm-health-build.log >&2
  exit 1
}
tail -20 /tmp/llm-health-build.log
echo "release verification ok"
