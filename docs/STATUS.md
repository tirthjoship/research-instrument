# STATUS — multi-modal-stock-recommender

> Tier-0 single source of truth. Read this FIRST and in FULL at session start.
> Keep it short (~45 lines). Overwrite, don't append — history goes to PHASE_LOG.md.

**Updated:** 2026-06-11 (session end — Unit C + hardening MERGED, main synced)

**Direction (ADR-052):** Alpha hunt CLOSED. Product = honest deterministic CRO.
Unit B prediction permanently closed (ADR-053, INCONCLUSIVE_THIN_COVERAGE → KILL).
Wrap plan LOCKED: `docs/superpowers/specs/2026-06-10-strategic-wrap-plan-design.md`
(close ~Jun 29).

**✅ MERGED to develop AND main (2026-06-11):**
- Unit C adherence (PR #37) + hardening sprint (PR #38). 1542 tests, mypy strict,
  CI green. main = develop (716dd06). Branches deleted local+remote.
- Stray leg2-subproject-C two-pillar spec rescued (cherry-pick) — branch audit
  confirms NO unmerged work anywhere (leg2-c branch tip is patch-equivalent).
- README freshness: counts 1442→1542, Unit C+hardening in roadmap, ADR 001–053.
- Venv fix: CI's pinned stubs (types-PyYAML, pandas-stubs, types-requests,
  types-click) installed into shared .venv — local `make check` green again.

**NEXT ACTION (fresh session):**
1) Dashboard realignment — spec+plan written/validated on
   `feat/insider-cluster-falsification`. Preconditions met (verdict DONE, venv
   FIXED). Bring that branch current vs develop first, then Task 1 (skill wiring).
2) Refinement pass (Jun 17–29): README verdict-table rewrite, falsification
   write-up, commit/gitignore the 2 stray data/reports/*.json
   (divergence_ic_21d.json, momentum_discipline.json), final close.

**Hard caveats:** `.claude/settings.json` guardrails.sh blocks rm on data/ —
NEVER overwrite. EDIT `data/personal/cash.json` (placeholder cash_cad=0.0; buffer
check meaningless until real balance). KNOWN BUG (post-gate, out of scope):
`unrealized_pct` currency-polluted for USD names, feeds REDUCE verdicts. 65/66
accounts. No paid data. yfinance throttled — caches sacred.

**Pointers:** Unit C + hardening spec/plan → `docs/superpowers/{specs,plans}/
2026-06-10-{unit-c-adherence,hardening-sprint}*` · wrap plan → strategic wrap
spec · dashboard → its spec/plan pair · history → `docs/PHASE_LOG.md`.
