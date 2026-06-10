# STATUS — multi-modal-stock-recommender

> Tier-0 single source of truth. Read this FIRST and in FULL at session start.
> Keep it short (~45 lines). Overwrite, don't append — history goes to PHASE_LOG.md.

**Updated:** 2026-06-10 (session end — full run in flight, plans validated)

**Direction (ADR-052):** Alpha hunt CLOSED. Product = honest deterministic CRO.
Wrap plan LOCKED: `docs/superpowers/specs/2026-06-10-strategic-wrap-plan-design.md`
(pre-committed Unit B verdict tree, ≤5% sleeve cap behind PASS+paper gates,
INCONCLUSIVE→final KILL, self-sustainability = deterministic + fail-loud, close ~Jun 29).

**⏳ UNIT B FULL RUN IN FLIGHT (do NOT restart unless dead):** 2006–2024
falsification, M1/M2-AMENDED code, PID was 91498, log `/tmp/insider_full3.log`.
Detached (nohup) — survives session end. Writes verdict to
`data/reports/insider_cluster_falsification_2024.json`. Dead = no process AND
log stale >30 min AND no report → relaunch per plan Task 6 (caches make it cheap).

**This session shipped (all merged to develop + main, 9028ccd lineage):**
- C1 fix: insider CLI echo KeyError + end-to-end regression test (85f2eff).
- M1: joint Form-4 dedup — greedy distinct (insider, accession) matching. Opus-verified.
- M2: per-event expanding PIT terciles + MIN_TERCILE_POPULATION=30 disclosure. Opus-verified.
- NaN-ADV guard → no_price path. ADR-053 amendment recorded (count drop NOT guaranteed).
- README: Unit B findings + pre-committed tree, plain language.

**Committed on `feat/insider-cluster-falsification` (pushed, NOT yet re-merged):**
- Dashboard realignment spec + plan (BOTH Opus-validated, 8 fixes applied):
  `docs/superpowers/{specs,plans}/2026-06-10-dashboard-realignment*`. 7 honest tabs,
  ~1,400 lines deleted, skill-routing wiring (plan Task 1 = UNGATED, runnable now).

**NEXT ACTION (fresh session):**
1) Check `data/reports/insider_cluster_falsification_2024.json` — if present, execute
   the LOCKED verdict branch (wrap spec §2 / Unit B plan Task 7): fill ADR-053, STATUS,
   merge. NO judgment calls. If run dead + no report: relaunch (Unit B plan Task 6).
2) Then: Unit C plan (brainstorm→plan), hardening sprint (fixes venv — streamlit/plotly/
   mypy MISSING in shared venv), THEN dashboard plan (preconditions block enforces order).
3) Dashboard plan Task 1 (skill wiring) runnable anytime — no gates.

**Hard caveats:** `.claude/settings.json` has guardrails.sh (blocks rm on data/ —
NEVER overwrite it). 65/66 accounts registered. No FinBERT/LangChain/paid data.
yfinance throttled — runs are slow, caches are sacred.

**Pointers:** wrap plan + decision tree → strategic wrap spec · Unit B build →
`plans/2026-06-10-unit-b-m1-m2-rerun.md` · dashboard → its spec/plan pair ·
history → `docs/PHASE_LOG.md`.
