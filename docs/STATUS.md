# STATUS — multi-modal-stock-recommender

> Tier-0 single source of truth. Read this FIRST and in FULL at session start.
> Keep it short (~45 lines). Overwrite, don't append — history goes to PHASE_LOG.md.

**Updated:** 2026-06-11 (session end — Unit C + Hardening sprint SHIPPED on branches)

**Direction (ADR-052):** Alpha hunt CLOSED. Product = honest deterministic CRO.
Unit B prediction permanently closed (ADR-053, INCONCLUSIVE_THIN_COVERAGE → KILL).
Wrap plan LOCKED: `docs/superpowers/specs/2026-06-10-strategic-wrap-plan-design.md`
(close ~Jun 29).

**✅ UNIT C — PR #37 open → develop (NOT yet merged).** Anti-overtrade throttle +
cash-buffer + adherence self-experiment. 44 tests, mypy clean, Opus-reviewed.

**✅ HARDENING SPRINT — branch `feat/hardening-sprint` (stacked on Unit C, NOT
merged).** Wrap plan §5 self-sustainability. 8 tasks:
- Venv reconciled: `pip install -e ".[dashboard,dev]"` → suite 1521→1541 pass,
  0 collection errors, `make check` green. (The 55 import failures are GONE.)
- Resilient fetch: stdlib retry/backoff + `PriceFetchError` tri-state. `load_
  price_series` gains `strict` (default False keeps 18 callers safe; weekly job
  opts in). Delisted prune-list (3-wk threshold, gitignored, reversible).
- Collect-then-fail health check: holdings-risk assesses ALL names, prints
  `fetched OK/no-data/FAILED/pruned`, exits non-zero only if real fetch errors.
  One flaky name never aborts the 66-name run. Shared-contract tasks Opus-reviewed.

**NEXT ACTION (fresh session):**
1) Merge PR #37 (Unit C) → develop, then merge/rebase hardening → develop
   (finishing-a-development-branch). Order matters: Unit C first.
2) Dashboard realignment — spec+plan already written/validated (on
   `feat/insider-cluster-falsification`). Preconditions NOW met: verdict DONE,
   venv FIXED. Task 1 (skill wiring) ungated. Bring its branch current first.
3) Refinement pass (Jun 17–29): README verdict-table rewrite, falsification
   write-up, commit/gitignore the 2 stray data/reports/*.json, final close.

**Hard caveats:** `.claude/settings.json` guardrails.sh blocks rm on data/ —
NEVER overwrite. EDIT `data/personal/cash.json` (placeholder cash_cad=0.0; buffer
check meaningless until real balance). KNOWN BUG (post-gate, out of scope):
`unrealized_pct` currency-polluted for USD names, feeds REDUCE verdicts. 65/66
accounts. No paid data. yfinance throttled — caches sacred.

**Pointers:** Unit C + hardening spec/plan → `docs/superpowers/{specs,plans}/
2026-06-10-{unit-c-adherence,hardening-sprint}*` · wrap plan → strategic wrap
spec · dashboard → its spec/plan pair · history → `docs/PHASE_LOG.md`.
