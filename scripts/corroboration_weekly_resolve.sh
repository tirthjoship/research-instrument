#!/usr/bin/env bash
# SP5 weekly corroboration resolution — runs every Sunday after market close.
# Resolves STRONG-tier snapshots ≥21d old against realized prices.
# Accrues GateSamples and evaluates Hypothesis #9 gate (ADR-064) when n ≥ 30.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== corroboration-weekly-resolve: $(date '+%Y-%m-%d %H:%M:%S') ==="
uv run python -m application.cli resolve-corroboration
uv run python -m application.cli corroboration-calibration-status
echo "=== done ==="
