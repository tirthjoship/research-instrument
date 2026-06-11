# STATUS — multi-modal-stock-recommender

> Tier-0 single source of truth. Read this FIRST and in FULL at session start.
> Keep it short (~45 lines). Overwrite, don't append — history goes to PHASE_LOG.md.

**Updated:** 2026-06-10 (session end — Unit C SHIPPED on feature branch)

**Direction (ADR-052):** Alpha hunt CLOSED. Product = honest deterministic CRO.
Unit B prediction permanently closed (ADR-053, INCONCLUSIVE_THIN_COVERAGE → KILL).
Wrap plan LOCKED: `docs/superpowers/specs/2026-06-10-strategic-wrap-plan-design.md`
(close ~Jun 29).

**✅ UNIT C SHIPPED (branch `feat/unit-c-adherence`, NOT yet merged):**
Anti-overtrade throttle + cash-buffer + adherence self-experiment. 8 TDD tasks,
44 Unit C tests pass, mypy clean. Spec v4 + plan committed.
- Pure `domain/adherence.py`: diff_holdings (forward-split guard, DRIP band),
  throttle (discretionary-only — obeying tool can't trip it), CAD cash buffer,
  obligations (one-per-ticker, 21d), canonical f=0.5 gap formula + bps/annualize.
- `application/adherence.py` use case: snapshots-by-date, tz-robust same-day
  dedup, idempotent `(ticker, flag_date)` adherence_log, survivorship disclosure.
- PositionRisk + log rows carry quantity + market_value_cad (FX via USDCAD=X).
- CLI `adherence-report` + Saturday cron step 4. Each task Opus-reviewed for drift
  (caught + fixed: reverse-split misclassification, currency bug, 21d seam test).

**NEXT ACTION (fresh session):**
1) Review/merge `feat/unit-c-adherence` → develop (use finishing-a-development-branch).
2) Hardening sprint (§5): fix shared venv — networkx/feedparser/streamlit/plotly/
   praw MISSING (55 pre-existing test failures, unrelated to Unit C); health
   checks, auto-prune delisted, retry/backoff on fetches.
3) THEN dashboard plan (preconditions: verdict DONE, venv still broken).
   Dashboard plan Task 1 (skill wiring) runnable anytime — no gates.

**Hard caveats:** `.claude/settings.json` guardrails.sh blocks rm on data/ —
NEVER overwrite it. EDIT `data/personal/cash.json` (placeholder cash_cad=0.0
created — buffer check is meaningless until real balance entered; gitignored).
KNOWN BUG (out of Unit C scope): `unrealized_pct` in holdings_risk currency-
polluted for USD names, feeds REDUCE verdicts — fix post-gate (would break
ADR-048 continuity mid-window). 65/66 accounts registered. No paid data.
yfinance throttled — runs slow, caches sacred.

**Pointers:** Unit C spec/plan → `docs/superpowers/{specs,plans}/2026-06-10-unit-c-
adherence*` · wrap plan → strategic wrap spec · dashboard → its spec/plan pair ·
history → `docs/PHASE_LOG.md`.
