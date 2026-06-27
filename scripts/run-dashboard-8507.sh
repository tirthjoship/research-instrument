#!/usr/bin/env bash
# Start the stock recommender dashboard on port 8507 (local-only holdings upload).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="/Users/tirthjoshi/My Data Science Projects/.venv"
PORT=8507
LOG="/tmp/stockrec-${PORT}.log"

if [[ ! -f "${VENV}/bin/activate" ]]; then
  echo "venv not found: ${VENV}/bin/activate" >&2
  exit 1
fi

# shellcheck source=/dev/null
source "${VENV}/bin/activate"
cd "${ROOT}"

if lsof -ti:"${PORT}" >/dev/null 2>&1; then
  echo "Stopping existing process on port ${PORT}..."
  lsof -ti:"${PORT}" | xargs kill -9 2>/dev/null || true
  sleep 1
fi

echo "Starting dashboard on http://127.0.0.1:${PORT} (log: ${LOG})"
echo "Press Ctrl+C to stop."
exec env STOCKREC_LOCAL_ONLY=1 streamlit run adapters/visualization/dashboard.py \
  --server.port "${PORT}" \
  --server.headless true \
  --server.address 127.0.0.1 \
  2>&1 | tee -a "${LOG}"
