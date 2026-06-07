#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
V2_TESTS="${V2_TESTS:-$ROOT/../health-assessment-v2/tests}"
if [ ! -d "$V2_TESTS" ]; then
  echo "Skipping upstream v2 compatibility tests; missing $V2_TESTS"
  exit 0
fi
if [ -d "$ROOT/.venv" ]; then
  # shellcheck disable=SC1091
  . "$ROOT/.venv/bin/activate"
fi
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
rsync -a "$V2_TESTS/" "$TMP/tests/"
mkdir -p "$TMP/src/llm_health/assessment_v2"
rsync -a "$ROOT/src/llm_health/assessment_v2/web_static" "$TMP/src/llm_health/assessment_v2/"
python - "$TMP/tests" <<'PY'
from pathlib import Path
import sys
root = Path(sys.argv[1])
for path in root.glob('*.py'):
    text = path.read_text().replace('health_assessment_v2', 'llm_health.assessment_v2')
    text = text.replace('"llm_health.assessment_v2"', '"llm_health" / "assessment_v2"')
    path.write_text(text)
PY
PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}" pytest -q "$TMP/tests"
