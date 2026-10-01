#!/usr/bin/env bash
# Run this: sets up on first use, updates the index, opens the search UI.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -f .venv/.setup-complete ]; then
  echo "First run: setting everything up. This takes a few minutes..."
  bash setup.sh
fi

echo
# run.py updates the index (only new or changed files), then opens the app - even if indexing fails.
exec .venv/bin/python run.py "$@"
