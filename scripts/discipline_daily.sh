#!/usr/bin/env bash
# Daily discipline-risk logging for the ADR-048/051 forward-calibration gate.
# Appends one as_of snapshot per run to data/personal/discipline_log.jsonl.
# Requires a real holdings CSV at data/personal/holdings.csv (gitignored).
set -euo pipefail
REPO="/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/research-instrument"
cd "$REPO"
# Adjust the python path to your venv if not on PATH.
PYTHON="${DISCIPLINE_PYTHON:-python}"
"$PYTHON" -m application.cli holdings-risk \
  --holdings data/personal/holdings.csv \
  >> data/reports/discipline_daily.log 2>&1
