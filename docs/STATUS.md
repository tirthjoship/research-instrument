# STATUS — multi-modal-stock-recommender

> Tier-0 single source of truth. Read this FIRST and in FULL at session start.
> Keep it short (~40 lines). Overwrite, don't append — history goes to PHASE_LOG.md.
> Older memory can be stale: verify code symbols against the repo before acting.

**Updated:** 2026-06-09 (post-merge, end of session)

**Direction (ADR-052):** Alpha hunt CLOSED (6 falsifications). Product = honest
deterministic CRO — risk mitigation + behavior-gap closure + abstaining
RESEARCH_ONLY screen. Recommender ABSTAINS, never predicts.

**Current phase:** Unit A (macro-beta scrubber) MERGED — PR #34 + PR #35 (context
architecture) merged to develop; **develop ≡ main, both @ `bbbdd81`**, CI green.
1442 tests, 94.13% cov. No open PRs.

**NEXT ACTION:** Start **Unit B** = sub-$1B non-routine insider-cluster IC
falsification (SEC Form-4, market-cap-tercile split, pre-registered). Killable,
low odds, last sanctioned predictive swing (KILL ⇒ prediction permanently off).
**MAX effort throughout** (danger is a false positive, not build difficulty).
First commit of the Unit B branch should refresh this STATUS.md. Then Unit C =
behavior gates (LOW build).

**Workflow that works here:** brainstorm → spec (validate vs code) → plan
(validate vs code) → subagent-driven (Sonnet per phase, Opus phase-gate verify)
→ live dogfood → finish-branch. LOW build / MAX verify.

**Open follow-ups (logged, not blocking):**
- TSX dot→dash symbol bug: config has `GIB.A`/`RCI.B`/`TECK.B`; yfinance wants
  `GIB-A.TO` etc. Live names (CGI/Rogers/Teck), NOT delisted. Data-layer fix.
- ANSS still in screen universe (delisted, acq. Synopsys) — minor prune.

**Background (no build):** weekly-Saturday discipline job
(`com.tirthjoshi.stockrec.discipline-weekly`) accrues ADR-048/051 forward gate →
resolves ~mid-July 2026. Read `data/reports/discipline_weekly_review.log` Saturdays.

**Hard caveats:** 65/66 accounts REGISTERED → tax-loss/wash-sale MOOT. No
FinBERT (ADR-004) / LangChain / Neo4j / paid data. `domain/brief.py` fuses
pillars — EXTEND don't rebuild. holdings.csv gitignored.

**Pointers:** detail history → `docs/PHASE_LOG.md` · decisions → `docs/adr/` ·
cross-project memory → `.claude/.../memory/MEMORY.md`.
