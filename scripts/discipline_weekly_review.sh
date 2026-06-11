#!/usr/bin/env bash
# Weekly (Saturday) discipline review for the ADR-048/051 forward-calibration gate.
#
# Three steps, all appended to data/reports/discipline_weekly_review.log with a
# dated header:
#   1. holdings-risk  -> banks this week's as_of snapshot into discipline_log.jsonl
#      (date diversity for the gate; fixed 66-name panel for clean forward-tracking).
#   2. resolve-discipline-flags -> forward-scores any flags whose 21d horizon elapsed
#      (REDUCE-only gate input + INCONCLUSIVE_THIN_DATES guard label, ADR-051).
#   3. discipline-calibration-status -> readiness toward the gate + dead-cron freshness.
#   4. adherence-report -> holdings-diff trades, discretionary throttle, cash
#      buffer, 21d counterfactual adherence gap (Unit C, spec 2026-06-10).
#
# Read the appended block each Saturday: how did the week's flagged names react, what
# resolved, and does the approach need revision. The log/holdings are gitignored.
#
# Fail-loud (hardening sprint, spec 2026-06-10): holdings-risk fetches with
# strict=True and exits non-zero if any ticker hard-fails (after retry/backoff).
# Under `set -euo pipefail` that aborts the Saturday job loudly. Delisted names
# (>=3 wks no data) are pruned + skipped, not failed. A health summary line
# (fetched OK / no-data / FAILED / pruned) precedes the verdict output.
set -euo pipefail
REPO="/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/multi-modal-stock-recommender"
cd "$REPO"
PYTHON="${DISCIPLINE_PYTHON:-python}"           # adjust to your venv python if not on PATH
HOLDINGS="${DISCIPLINE_HOLDINGS:-data/personal/holdings-report-2026-06-07.csv}"
LOG="data/personal/discipline_log.jsonl"
OUT="data/reports/discipline_weekly_review.log"

{
  echo "======================================================================"
  echo "WEEKLY DISCIPLINE REVIEW  $(date '+%Y-%m-%d %H:%M %Z')"
  echo "======================================================================"
  echo "--- 1. log this week's snapshot (holdings-risk) ---"
  "$PYTHON" -m application.cli holdings-risk --holdings "$HOLDINGS" --log "$LOG"
  echo "--- 2. resolve matured flags (REDUCE-only gate + diversity guard) ---"
  "$PYTHON" -m application.cli resolve-discipline-flags --log "$LOG"
  echo "--- 3. readiness toward the gate ---"
  "$PYTHON" -m application.cli discipline-calibration-status --log "$LOG"
  echo "--- 4. adherence report (Unit C: trades, throttle, buffer, gap) ---"
  "$PYTHON" -m application.cli adherence-report --log "$LOG"
  echo ""
} >> "$OUT" 2>&1
