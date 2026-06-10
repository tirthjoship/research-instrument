# STATUS — multi-modal-stock-recommender

> Tier-0 single source of truth. Read this FIRST and in FULL at session start.
> Keep it short (~45 lines). Overwrite, don't append — history goes to PHASE_LOG.md.
> Older memory can be stale: verify code symbols against the repo before acting.

**Updated:** 2026-06-10 (mid-session handoff — background run in flight)

**Direction (ADR-052):** Alpha hunt CLOSED (6 falsifications). Product = honest
deterministic CRO. Recommender ABSTAINS, never predicts. Unit A (macro-beta) MERGED.

**Current phase:** **Unit B = sub-$1B insider-cluster IC falsification — BUILT, code-
reviewed, committed; verdict pending.** Branch `feat/insider-cluster-falsification`
(**18 commits ahead of develop, NOT merged**). 27 tests green. Spec/plan in
`docs/superpowers/{specs,plans}/2026-06-09-insider-cluster-falsification*`.
Gate = **event-study abnormal return** (amended from rank-IC: binary signal):
Leg-1 gross `CI_low>0`, Leg-2 net-of-slippage `CI_low>0`; 3-state PASS/INCONCLUSIVE/KILL;
guards THIN_N (<100 bottom-tercile events) / THIN_COVERAGE (<80%). Slippage 150/75/40 bps
by ADV tercile. Data = SEC DERA Form-345 (new adapter) + yfinance.

**⏳ BACKGROUND RUN IN FLIGHT (do NOT restart it):** full 2006–2024 falsification is
running as a detached process (slow — yfinance throttling). It WRITES THE VERDICT TO
`data/reports/insider_cluster_falsification_2024.json` on completion (independent of any
Claude session). Smoke (2021–24, PRE-C1-fix) gave **INCONCLUSIVE**: gross info real
(+1.62%/21d, CI_low +0.41%), net FAIL after 150bps (CI_low −1.09%) — info real, untradeable.

**NEXT ACTION (resume):** 1) check the report JSON exists + read `verdict` (+ honest
`coverage`, now C1-fixed — may legitimately be `INCONCLUSIVE_THIN_COVERAGE`). 2) Fill the
`[PENDING]` full-window table + verdict in `docs/adr/053-insider-cluster-falsification-verdict.md`
(DRAFT, committed). 3) Overwrite this STATUS + append PHASE_LOG. 4) Finish branch
(PR → develop) via superpowers:finishing-a-development-branch. If the run died/empty:
rerun smoke window (2021–24) with C1-fixed code (~15–30 min) for the honest verdict.

**Code review (done this session):** C1 (survivorship coverage denominator now counts
delisted/unpriceable bottom-tercile events — was a false-positive vector), I1 (PIT
`LookAheadBiasError` guard), I2 (excluded-codes foot-gun), I3 (fixed cache window) — ALL FIXED.

**Branch hygiene note:** branched off `chore/status-refresh` (itself +1 over develop, an
earlier STATUS refresh). Two unrelated follow-ups are bundled in this branch and can be
split if desired: **TSX dot→dash symbol fix (GIB.A→GIB-A.TO) + ANSS prune — both DONE.**

**Background (no build):** weekly-Saturday discipline job
(`com.tirthjoshi.stockrec.discipline-weekly`) accrues ADR-048/051 forward gate →
resolves ~mid-July 2026. Read `data/reports/discipline_weekly_review.log` Saturdays.

**Hard caveats:** 65/66 accounts REGISTERED → tax-loss/wash-sale MOOT. No FinBERT
(ADR-004)/LangChain/Neo4j/paid data. `domain/brief.py` fuses pillars — EXTEND don't rebuild.
holdings.csv gitignored. yfinance heavily throttled today (many runs) — expect slow crawls.

**Pointers:** history → `docs/PHASE_LOG.md` · decisions → `docs/adr/` · Unit B verdict →
ADR-053 + `data/reports/insider_cluster_falsification_2024.json`.
