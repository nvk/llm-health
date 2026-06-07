#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
# Release-blocking literal identifiers and private local paths. Code may contain generic privacy regexes,
# so this scan focuses on actual dox-like strings rather than test pattern examples.
PATTERN='nvk/Library/Mobile Documents|Rodolfo|CARA ZAX|ROD SMITH|apple_health_export|blood-tests|heatlth-data|Health Number:|Date of Birth:|sourceName:'
if grep -RInE "$PATTERN" . \
  --exclude-dir=.git \
  --exclude-dir=.venv \
  --exclude-dir=.pytest_cache \
  --exclude-dir=.ruff_cache \
  --exclude-dir=data \
  --exclude='*.egg-info/*' \
  --exclude='verify-privacy.sh'; then
  echo "Privacy release check failed" >&2
  exit 1
fi
# Local data directories must not be tracked.
if git ls-files | grep -E '^(data/|\.llm-health/|.*\.(pdf|xml|cda|xlsx?|duckdb|parquet|sqlite3?))$'; then
  echo "Private/generated data appears tracked" >&2
  exit 1
fi
echo "privacy release check ok"
