# ADR-049: Consolidate into a Two-Sided, Forward-Accountable Decision-Support Engine

**Date:** 2026-06-08
**Status:** Accepted
**Deciders:** Tirth Joshi (with Claude)
**Builds on:** ADR-039 (no OOS conviction edge), ADR-044 (no divergence IC), ADR-046 (momentum/exit KILL — drawdown-cut real), ADR-047 (alpha hunt complete → discipline/risk co-pilot), ADR-048 (discipline forward-calibration gate)

## Context

The project has, across four pre-registered falsifications, established that **no retail-accessible public signal predicts returns** (semi-strong efficiency holds for what we can reach). ADR-047 settled the product identity — a discipline/risk decision-support co-pilot that abstains — and shipped its first slice (the Holdings Discipline & Risk Engine), explicitly **deferring** a candidate-screening "find new names" layer until v1 calibration proves out.

A grilling session (2026-06-08) surfaced what the user actually wants from the project, and it is broader than the holdings co-pilot alone:

1. A **weekly shortlist** of names to research, ranked by **evidence-backed financial principles**, not hype.
2. **Buy / sell / hold / how-long / why** guidance on both held positions *and* new candidates, each with its backing.
3. A **research layer** that maps *what touches what* — supply-chain and **directed customer→supplier economic links** (e.g. Walmart → McKesson), so a move/news on one name points him at the economically-linked names to investigate.
4. The whole thing **honest and accountable** — it must track its own calibration and tell him when *not* to trust it.

Each desire collides with the efficiency result in the same place: **anticipating a move before the market reacts is the falsified prophecy and stays out of scope.** But the honest residue — evidence-ranked *screening*, riding documented *under-reaction* (momentum, PEAD/analyst-revision drift, Cohen-Frazzini economic-link drift), discipline on holdings, and research scaffolding — is real, mostly already built in pieces, and assembles into one coherent engine.

This ADR records that consolidation and the **self-checkpointing phase sequence** that builds it without re-opening the alpha hunt.

## Decision

**Consolidate every honest capability the project has learned into one two-sided, forward-accountable decision-support engine**, organised as six hexagonal layers, delivered in four pre-registered phases with intercept gates between them.

### The spine (non-negotiable — what makes this not another stock-tip list)

1. **Screen + ride, never predict.** Surface names *already* in evidence-backed trend/drift; never forecast ignition. No "before the market reacts."
2. **Every predictive claim is falsification-gated** through the protected ADR-044/046 harness (block-bootstrap, Sharpe-diff CI, cross-sectional IC, transaction costs, point-in-time guards) before it earns a "signal" label. Until it passes → **research-only**.
3. **Accountability is the product.** Every surfaced call is forward-tracked vs SPY/NDX (`CallOutcome`); the engine publishes its own scorecard and **abstains / labels "not significant"** when the evidence is thin. This is the one thing a chatbot or a Motley-Fool list structurally cannot do.
4. **Honest ceiling, stated in every output:** a modest factor tilt + behaviour-gap closure + drawdown reduction. No alpha claim anywhere in the UI or reports.

### The six layers (≈55% already built)

| Layer | Components | Status |
|---|---|---|
| 1. Data / universe | 350+ hybrid universe, yfinance, analyst (Finnhub/yfinance), news (RSS/GNews), fundamentals, source-health (ADR-042) | BUILT |
| 2. Evidence (per-name) | momentum 12-1 · analyst-revision momentum/PEAD · quality · value · trend-health (200d/Chandelier) · conditional-vol | trend/vol BUILT; factors+revision NEW |
| 3. Research scaffolding | per-name dossier (evidence + narration) · directed economic-link graph · concentration/discovery (CorrelationAnalyzer) | graph skeleton BUILT; links SEED; dossier NEW |
| 4. Decision | BUY screen (rank → weekly top-N) · SELL/HOLD discipline · regime conditioner · abstention | discipline SHIPPED; screen/regime NEW |
| 5. Accountability | forward scorecard (`CallOutcome`) · per-signal calibration (Brier/IC) · falsification harness | scorecard+harness BUILT; per-signal NEW |
| 6. Delivery | weekly brief (unified output) · Streamlit dashboard · CLI · scheduled runs (launchd) | dashboard/CLI/cron BUILT; brief NEW |

The new work is mostly **orchestration** — the buy-screen, per-signal calibration, the research dossier, and the unified weekly brief that ties holdings + candidates + research + scorecard together.

### Phasing (self-checkpointing — each phase validates before the next begins)

- **Phase A — Evidence Screen MVP** (buy-side): factor + analyst-revision evidence → weekly ranked shortlist with backing + forward scorecard. Pre-registered OOS edge test sets the screen's **label** (validated-signal vs research-only-filter); a significantly *negative* edge or broken data **halts** it.
- **Phase B — Unified Weekly Brief**: compose buys (A) + holdings verdicts (discipline) + per-name dossiers + regime tilt + concentration map into one decision-oriented brief. Gate is correctness/usability/point-in-time-safety, not prediction.
- **Phase C — Economic-Link Research + drift experiment**: seed ~15 directed customer→supplier links; ship research/alert scaffolding; run a pre-registered Cohen-Frazzini drift test. PASS → eligible for D; else research-only (still useful for discovery).
- **Phase D — Edge graft (conditional)**: graft *only* a validated edge (from A, C, or the discipline July gate) into screen weighting/sizing. **If nothing passes, D does not execute and the engine ships as honest research + discipline + abstaining-screen — an acceptable, pre-agreed outcome.**

### Relationship to ADR-047's deferral

ADR-047 deferred the screener until discipline-v1 calibration proves useful. This ADR refines, not contradicts, that: we **build the screen's infrastructure and run its own falsification test in parallel** (honest by construction — it ranks by evidence and shows its scorecard), but **trusting the screen as a position-sizing signal** and the conditional **Phase-D edge-graft** remain gated on a passed forward gate (the discipline July read, ADR-048, or Phase-A/C's own OOS tests). Parallel build, gated trust. The user explicitly directed this parallelism and the validate-as-we-go cadence.

## Consequences

- The product identity from ADR-047 is unchanged — an evidence-aggregator + risk/discipline co-pilot that abstains. This ADR widens it from *holdings-only* to *holdings + candidate research*, with the same honesty spine.
- The discipline engine becomes the **sell/hold side** of the unified engine; the new screen is the **buy side**; both feed one brief.
- The ADR-044/046 falsification harness and the `SurfacedCall`/`CallOutcome` forward-tracking infrastructure are **reused as the protected baseline** for every new signal — no new validation rig is invented.
- **Portfolio/career value:** a two-sided engine that forward-tracks its own calibration and abstains, built atop four documented falsifications, is a stronger DS artifact than any "70% accuracy" claim a reviewer would (correctly) distrust.
- **Scope risk is managed by the gates:** phases do not build on unvalidated phases; the intercept points are pre-registered so a pivot is a planned branch, not a surprise.
- **Honest non-claims, recorded:** this is not a predictor, not an alpha engine, not an auto-trader, not a "beat SPY by 20–30%" tool. It surfaces evidence, disciplines decisions, and reports its own (likely modest, possibly null) track record.

## Phase-A Outcome (2026-06-08)

**Phase A (Evidence Screen MVP) BUILT and verified** on `feat/engine-phase-a-evidence-screen` (9 commits), merged to `develop`. Sonnet subagent-per-task TDD; Opus `verification-before-completion` as the phase gate.

- **Delivered:** pure-domain `factor_scores`/`screen`/`screen_models` (stdlib-only, equal-weight composite, flagged-neutral coverage), `EvidenceScreenUseCase` (rank-all → top-N, winsorized z-scores, cross-sectional percentiles, abstain-on-thin-coverage), `ScreenBacktestUseCase` (pre-registered IC gate: ≤0 HALT / <0.02 INCONCLUSIVE / ≥0.02 PASS), `screen-candidates` + `backtest-screen` CLIs (masked stdout, full-distribution report), `SurfacedCall` forward-tracking wiring. **1324 tests, 93.61% coverage, `make check` green.**
- **Opus gate earned its keep:** caught two real blockers a self-review missed — the CLI wrote only the top-N while *claiming* the full ranked distribution (a silent ADR-042 truncation), and the test mock-defeated that bug into a false green. Both fixed and re-verified against fresh evidence; three dead helpers (abstain/winsorize/percentile) were wired in the same pass.
- **Honest deferral (must close before any "it works" claim):** the **bootstrap-CI gate** (CI-excludes-0 on per-date ICs) and the **cost-aware top-decile Sharpe-diff secondary** (spec §5) are NOT yet implemented — docstring-marked as deferred, never faked. The IC-threshold branching is live and tested; the live `backtest-screen` run that sets the screen's VALIDATED-vs-RESEARCH_ONLY label is **blocked on implementing these first.**
- **Phasing intact:** Phase B (weekly brief) planning is deferred to a new session and remains gated on the Phase-A backtest verdict. The screen ships `RESEARCH_ONLY` until the pre-registered test passes.

## Phase-A Validation Outcome (2026-06-08, second session) — VERDICT = INCONCLUSIVE → screen ships RESEARCH_ONLY

The deferred gate is now closed and the pre-registered test has been run on `feat/engine-phase-a-backtest-gate`.

- **Gate implemented (TDD, Sonnet):** `ScreenBacktestUseCase` now runs the full LOCKED gate — primary = `moving_block_bootstrap` CI on per-date ICs (PASS needs CI excludes 0 **and** mean IC ≥ 0.02, the ADR-044 bar) and secondary = cost-aware top-decile-minus-SPY `sharpe_difference_bootstrap` net of `TransactionCostModel` (the ADR-046 bar). HALT reserved for IC CI entirely < 0. Planted-edge fixture recovers PASS; zero-edge fixture does not false-PASS.
- **Real point-in-time run (US+TSX, 2018-01→2026-01, monthly, 21d horizon, costs charged):** 570-name universe, **545 with clean leakage-safe price history**, 104 evaluation dates. `application/screen_ic_panels.py` builds the panels point-in-time from prices only.
- **Result:** `mean_IC = 0.0107`, bootstrap **CI = [-0.029, +0.043] (spans 0)**; secondary top-decile Sharpe-diff `point = -0.0019`, **CI = [-0.39, +0.19] (spans 0)**. `primary_pass=False`, `secondary_pass=False` → **INCONCLUSIVE**. Report: `data/reports/screen_ic_2026-06-08.json`. Screen auto-labels `RESEARCH_ONLY` via `label_from_verdict_file`.
- **Hard honesty constraint on scope:** only the **momentum (12-1) leg** is point-in-time testable for 2018-2026. Revision/quality/value need point-in-time fundamentals yfinance cannot supply — using current snapshots at past dates would be catastrophic look-ahead (project rule #2), so they were flagged-neutral throughout. **The composite's "evidence" claim is therefore only 1/4 validated, and the validated quarter is the most-arbitraged factor.** Caveat is printed on every run and embedded in the report JSON.
- **Dissection:** (a) point IC is positive but **half the 0.02 bar and statistically indistinguishable from 0** (t≈0.6); (b) the universe is **current index membership = survivor-biased**, which *inflates* apparent momentum — the flattering sample still couldn't clear the bar, mirroring ADR-044's logic; (c) net-of-cost top-decile **tracks SPY** (Sharpe-diff ≈ 0), so there is no gross edge for costs to erode — consistent with the ADR-046 momentum KILL; (d) the harness is trusted (validated rig, planted/zero-edge unit tests, 545 names × 104 dates = adequate power to detect a 0.02+ IC).
- **This is the FIFTH convergent negative** (ADR-039/043/044/046 + this) — all five say the same thing: no economically meaningful, cost-robust, OOS edge in retail-accessible public signals. **This was the pre-agreed honest terminal state in this very ADR:** the screen ships as an honest evidence-ranker that abstains and shows its scorecard, NOT a validated alpha. Phase-D edge-graft stays gated OFF.
- **Decision:** per spec §5, INCONCLUSIVE (not HALT — CI not entirely negative, data integrity clean) → **proceed to Phase B as a `RESEARCH_ONLY` research/transparency tool**; the brief labels candidates "evidence-ranked, not validated" and prints IC/CI on every output. No "buy" language, no alpha claim.

## Phase-B Outcome (2026-06-08, second session) — BUILT, ships as RESEARCH_ONLY composition

Built via subagent-driven-development (Sonnet implementer per group, Opus spec + code-quality review each group, all fixes folded). Branch `feat/engine-phase-a-backtest-gate` (continues from the Phase-A gate work above).

- **What shipped (composition, no new predictive claim):** pure `domain/regime.py` (`classify_regime` from SPY-trend ATR-distance + VIX; `screen_tilt` display-only factor weights, import-time invariant vs FACTOR_KEYS) + `domain/brief.py` (6 frozen models, `assemble_brief`, `to_markdown` full detail, `to_stdout_masked` holdings-masked) + `RegimeReadUseCase` + `WeeklyBriefUseCase` (composes Phase-A screen + shipped discipline holdings-risk + regime + concentration via CorrelationAnalyzer cluster-overlap + forward scorecards) + `weekly-brief` CLI (masked stdout, gitignored markdown to `data/personal/`) + a read-only "Weekly Brief" dashboard tab. `_build_evidence_screen(deps)` extracted and shared with `screen-candidates` (DRY).
- **v1 scoping decisions (spec §7 leans):** regime tilt is **display-only** (does NOT re-rank candidates — re-ranking would be a soft predictive act); concentration is a **soft flag**; research-links section is a **Phase-C stub**; regime inputs are **SPY-trend + VIX only** (no breadth — none exists). These keep "Phase B adds no predictive claim" literally true.
- **Review caught real bugs (Opus quality gate earned its keep):** a `None`-float crash in `to_markdown` when the forward scorecard has records but no resolved returns (`screen_n>0` yet returns `None`); an ADR-047 leak where the masked stdout printed `[already held]` next to a held candidate ticker (stripped — the tag now lives only in the gitignored markdown); discipline-scorecard down-rate now returns `None` (renders "n/a") instead of a misleading `0%` when `n=0`. Plus test-hardening (field-iterating masking guarantee, two-instance determinism test).
- **Phase-Exit Gate met (real end-to-end smoke on 66 real holdings, bounded universe):** brief renders end-to-end; deterministic on a fixed `as_of`; masked stdout shows only aggregate verdict counts (no holding ticker / P&L / "already held" — a flagged "NKE leak" was a substring false-positive inside "EVIDENCE-RANKED"); regime read live from `^VIX`/`SPY`; discipline scorecard wired (n=0 → PENDING, honest); screen abstained on the tiny slice (full universe yields candidates); `RESEARCH_ONLY` label carried through with header "EVIDENCE-RANKED CANDIDATES", no "buy" language. **1378 tests, 93.78% cov, `make check` green.** Plan: `docs/superpowers/plans/2026-06-08-engine-phase-b-weekly-brief.md`.
- **Phase-C intercept (spec §8 — the real decision):** Phase C (economic-link research) is **not auto-greenlit.** The strongest signal is the user's reaction to the FIRST real full brief and which sections they actually read/act on. If holdings-verdicts + scorecard carry all the value and candidates are ignored, redirect effort from C/D toward deepening the discipline side. **NEXT SESSION:** run the full `weekly-brief` live → user reads it → decide C vs deepen-discipline. Parallel: discipline July gate (ADR-048).

## Related

- ADR-039/043/044/046 (the four falsifications), ADR-047 (alpha hunt complete), ADR-048 (forward-calibration gate)
- Specs: `docs/superpowers/specs/2026-06-08-engine-phase-{a,b,c,d}-*.md`
- Evidence basis: Cohen & Frazzini (2008) *Economic Links and Predictable Returns*; McLean & Pontiff (2016) post-publication decay; Jegadeesh-Titman momentum; StockBench (arXiv 2510.02209) LLMs predict badly.
