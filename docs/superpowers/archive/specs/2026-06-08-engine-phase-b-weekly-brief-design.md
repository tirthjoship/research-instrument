# Engine Phase B — Unified Weekly Brief — Design Spec

**Date:** 2026-06-08
**Status:** Draft for review
**Author:** Tirth Joshi (with Claude)
**Follows:** ADR-049 (engine architecture), Phase-A spec (evidence screen)
**Phase:** B of 4 (the unified output — composes buys + holdings + research + scorecard)

---

## 1. What this is — and what it is not

**One decision-oriented weekly brief** that answers, in plain English with the backing: *what to research buying, what to do with what I hold, what's economically linked, am I over-concentrated, and how has the engine actually done.* It composes existing parts — the Phase-A evidence screen (buy side), the shipped Holdings Discipline engine (sell/hold side), per-name dossiers, a regime tilt, the concentration map, and the forward scorecard — into a single artifact.

**It is explicitly NOT:**
- a new signal — Phase B adds **no predictive claim**; it presents A and the discipline engine honestly.
- a real-time feed — it is a **weekly** brief (+ the existing daily discipline run for holdings alerts).
- a place where any candidate is labelled "buy" more strongly than Phase-A's validation label permits.

**Honest value proposition:** the thing the user actually asked to *see* — buy/sell/hold + why + track record in one place — assembled from validated parts, with every claim carrying its honest label.

## 2. The brief — concrete shape

```
WEEKLY BRIEF — <date>
REGIME: <risk-on/off + driver>  → screen tilt: <quality/low-vol | momentum/beta>

BUY CANDIDATES (top-10, <VALIDATED | evidence-ranked, not validated>)   [scorecard ↓]
  <TICKER>  mom <pctl> · est-rev <%/90d> · quality/value · trend✓   <why>   <⚠ already-held / concentration>
HOLDINGS VERDICTS (from discipline engine)
  <TICKER>  <+/-%>  <trend state>  <REDUCE/TRIM/REVIEW/HOLD/ADD_OK> — <why>
RESEARCH LINKS (research-only, Phase C — not a signal)
  <event/move on customer> → <linked supplier> (<relationship>) → go research
CONCENTRATION
  <sector> <%> of book — <names> = one bet, not diversified
SCORECARD (the part no chatbot has)
  screen <window>: top-10 <ret> vs SPY <ret> (n, p — <significant | abstaining>)
  discipline <window>: REDUCE down-rate <%> (n) — forward gate <status>
```

## 3. Architecture (composition, hexagonal)

```
application/                              adapters/visualization/
 WeeklyBriefUseCase (new) ──────────────►  brief_tab (new Streamlit tab)
   ├─ EvidenceScreenUseCase (Phase A)      brief_markdown (new exporter)
   ├─ HoldingsRiskAssessmentUseCase (ship) domain/
   ├─ RegimeReadUseCase (new, thin)         regime (new, pure): classify_regime(...)
   ├─ CrossAssetPort concentration (reuse)  brief (new, pure): assemble/format models
   └─ ForwardTracking scorecard (reuse)
```

- **`domain/regime.py`** (pure): `classify_regime(spy_trend, vix_level, breadth) -> Regime{RISK_ON, NEUTRAL, RISK_OFF}` + `screen_tilt(regime) -> dict` (factor-weight tilt — quality/low-vol in risk-off, momentum in risk-on). Frozen thresholds; **regime conditions the screen's presentation/tilt, it does not predict the macro** (no "good jobs → buy" rule — that relationship is non-stationary, ADR-049).
- **`domain/brief.py`** (pure): assembles `WeeklyBrief` (frozen): regime, screen candidates (with labels), holdings verdicts, research links, concentration, scorecard snapshot. Pure formatting/aggregation, no IO.
- **`WeeklyBriefUseCase`**: orchestrates the four sub-use-cases point-in-time, masks holdings per ADR-047, writes a gitignored full brief + a masked stdout summary, and a markdown export.
- **Delivery:** a new dashboard tab renders the brief; `weekly-brief` CLI generates + exports it; scheduled weekly via the existing launchd pattern (alongside the daily discipline run).

## 4. Concentration & cross-asset (reuse, honest framing)

Reuse `CorrelationAnalyzer` for the holdings + top candidates: cluster membership + top-N weight. **Framed as a warning, not a discovery to act on** — same-bucket names are correlated leverage on one thesis, not diversification (ADR-049). If adding a candidate pushes a sector past a threshold, the brief flags it (soft by default; hard-block is an open question below).

## 5. Validation (correctness, not prediction)

Phase B makes no new predictive claim, so its gate is **integrity**, not edge:
- **Reproducibility:** the same `--as-of` date yields the same brief (deterministic; point-in-time).
- **No look-ahead:** every figure in the brief passes `validate_point_in_time_access`.
- **Privacy:** holdings/values never leave the machine; stdout masked; full detail gitignored (assert in tests).
- **Scorecard honesty:** the scorecard numbers match the underlying `CallOutcome`/discipline-log records exactly (no rounding that flatters; significance label matches the CI).
- **Label fidelity:** a `RESEARCH_ONLY` screen never renders "buy" language in the brief.

## 6. Testing
- `domain/regime.py` + `domain/brief.py`: unit + Hypothesis (regime monotone in trend/vix; tilt weights sum to 1; brief assembly total/ordered; `RESEARCH_ONLY` suppresses buy language).
- `WeeklyBriefUseCase`: fakes for all four sub-use-cases; assert masking, determinism, point-in-time, scorecard-record equality.
- Dashboard/CLI: masked-output + gitignore-safety tests; markdown export snapshot.
- `make check` green (mypy strict, 90% cov).

## 7. Open questions for reviewer
1. Concentration: **soft flag** (surface + warn) or **hard block** (refuse to present an N+1 name in an already-heavy bucket)? (Lean: soft — the engine advises, the user decides, per ADR-047.)
2. Regime inputs: SPY-trend + VIX only (simple, robust) or add breadth/credit spreads (richer, more failure surface)? (Lean: SPY+VIX v1.)
3. Brief cadence: pure weekly, or weekly brief + a daily one-line "anything changed on holdings" from the discipline run? (Lean: weekly brief + daily holdings delta.)

---

## 8. Phase Exit Gate → Phase C entry (validate-as-we-go)

**Before Phase C begins, confirm and record:**
- [ ] The brief renders end-to-end (CLI + dashboard) on real holdings + the Phase-A screen, deterministically and point-in-time-safe.
- [ ] Privacy asserts pass (masked stdout, gitignored detail, only tickers to yfinance).
- [ ] The scorecard in the brief matches source records exactly; the screen's honest label is carried through with no "buy" language when `RESEARCH_ONLY`.
- [ ] `make check` green.

**Intercept rule:** Phase C (economic links) is **independent research scaffolding** — it does not require Phase A to have PASSED, only Phase B to be shippable. But if the brief surfaces a *new* problem (e.g. the discipline July gate has resolved KILL, or the screen is `RESEARCH_ONLY` and the brief feels like noise to the user), **pause and re-decide scope with the user** before investing in C. Capture the user's reaction to the first real brief — that reaction is the strongest signal of whether C/D are worth building at all.

**Discovery checkpoint:** note which brief sections the user actually reads/acts on. If holdings-verdicts + scorecard carry all the value and candidates are ignored, that is a finding — it may redirect effort from C/D toward deepening the discipline side instead.
