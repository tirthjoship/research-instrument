# Engine Phase A — Evidence Screen MVP — Design Spec

**Date:** 2026-06-08
**Status:** Draft for review
**Author:** Tirth Joshi (with Claude)
**Follows:** ADR-049 (decision-support engine architecture)
**Phase:** A of 4 (buy-side screen — the first new slice of the unified engine)

---

## 1. What this is — and what it is not

A **weekly, evidence-ranked shortlist of names to research**, drawn from the 350+ universe, scored by financial-principle factors that have real (if decayed) out-of-sample support, each name carrying its **evidence backing** and a **forward scorecard vs SPY/NDX**. It is the buy-side complement to the shipped Holdings Discipline engine (the sell/hold side).

**It is explicitly NOT:**
- a return predictor or a "this will pop 10–20%" engine (falsified 4× — ADR-039/043/044/046)
- a real-time / news-reaction tool (the speed game is unwinnable retail — ADR-049 spine)
- a position-sizing signal **yet** — that trust is gated on this phase's exit test
- an auto-trader (report + log only; the user acts)

**Honest value proposition:** surface the names that *currently* score highest on evidence-backed factors, show the *why* and the *track record*, and **abstain from a "buy" label whenever the screen has no validated edge.** Even with no significant edge, an evidence-transparent, forward-scored ranker is materially more honest than a stock-tip list — and it is the scaffold Phases B–D build on.

## 2. Evidence basis (why these factors, not others)

Every ranked factor maps to a documented effect; all are sized for decay (McLean-Pontiff 2016: ~58% post-publication):
- **Cross-sectional & time-series momentum** (Jegadeesh-Titman; AQR) — winners persist 3–12mo. Our `momentum_12_1` already exists in `trend_rules.py`.
- **Analyst earnings-revision momentum / PEAD** — estimate up-revisions drift positive over weeks (the honest "early"; Tier-2 in ADR-045). Analyst ports already exist (Finnhub/yfinance).
- **Quality** (profitability, low accruals, low leverage) — robust premium; fields in `fundamental_feature_engineer`.
- **Value** (earnings yield / `valuation_z_score`) — decayed but real; already computed.
- **Trend filter** (200-day, `above_trend`) — only rank names in a confirmed uptrend (screen + ride, never call cold).

Sentiment / attention / conviction / divergence are **excluded** — each independently falsified as a predictor.

## 3. Data reality (drives the validation design)

- **Prices:** ~8yr clean yfinance daily for liquid US + TSX → enough for point-in-time factor computation and OOS backtest.
- **Analyst revisions:** available per-ticker (Finnhub/yfinance) but rate-limited → batch + cache (reuse `ConvictionSignalCache` pattern); a throttle is **never** written as a zero (ADR-042 `SourceThrottledError` rule).
- **Fundamentals:** quarterly, point-in-time-lagged to filing availability (no look-ahead on `forward_pe_ratio` etc. — `FUTURE_LEAKAGE_COLUMNS` rule stands).
- **Universe:** existing 350+ hybrid provider; survivorship is acknowledged and reported (the OOS test uses the broad set and labels the bias, as in ADR-044).

## 4. Architecture (hexagonal, reuse-heavy)

```
adapters/                 domain/  (pure, stdlib)        application/
 yfinance (reuse)  ───►    factor_scores (new, pure)  ◄─  EvidenceScreenUseCase (new)
 analyst (reuse)   ───►    trend_rules (reuse)        ◄─  ScreenBacktestUseCase (new)
 fundamentals(reuse) ►     screen (new, pure)         ◄─  (reuse) ic_analysis + precision_metrics
 narrator (reuse)  ───►    models: ScreenCandidate,
                           ScreenResult, FactorScore
```

Domain stays pure (stdlib only — no numpy in `domain/`). Look-ahead guards (`validate_point_in_time_access`, `LookAheadBiasError`) apply to every factor computation. Costs charged via the existing `TransactionCostModel`.

### 4.1 Domain — pure scorers & models
- **New `domain/factor_scores.py`** (pure): `zscore(values)`, `winsorize(...)`, `revision_momentum(estimate_series)`, `quality_score(fundamentals)`, `value_score(fundamentals)`, `composite_score(sub_scores, weights)` — combines z-scored factors into one rank score; **frozen default weights** (no tuning to the current universe).
- **New `domain/screen.py`** (pure): `rank_universe(scored_names) -> list[ScreenCandidate]`; `eligible(trend_health, has_min_history)` (only rank confirmed-uptrend names with ≥ N days history — reuse `has_min_history`); `abstain_if_thin(result)` → flags the whole result research-only when factor coverage is poor.
- **New models** (frozen dataclasses): `FactorScore(name, value, percentile, contribution)`; `ScreenCandidate(ticker, composite, factor_scores, trend_health, why, label)` where `label ∈ {VALIDATED, RESEARCH_ONLY}`; `ScreenResult(as_of, candidates, universe_size, regime, scorecard_ref)`.

### 4.2 Application — orchestration
- `EvidenceScreenUseCase(price, analyst, fundamentals, narrator)`: point-in-time fetch → factor scores → composite → rank → top-N `ScreenCandidate`s → narrate the *why* (narrator explains the already-computed scores; cannot change them). Surfaces results as `SurfacedCall`s so the existing `ForwardTrackingUseCase` scores them vs SPY/NDX for free.
- `ScreenBacktestUseCase(price, analyst, fundamentals)`: the pre-registered OOS test (Section 5) — reuses `ic_analysis.py` (cross-sectional rank-IC) and `precision_metrics` (block-bootstrap, date-level significance) and `TransactionCostModel`.

### 4.3 CLI & cadence
- New `screen-candidates [--top N] [--as-of DATE] [--narrate]` → weekly shortlist; writes full distribution to a report file (the FULL ranked distribution, not just top-N — ADR-042 honesty rule), masked summary to stdout.
- New `backtest-screen` → runs the pre-registered gate, writes `data/reports/screen_ic_<date>.json`, prints PASS / INCONCLUSIVE / HALT verdict.
- Cadence: **weekly** (factors do not change intraday). No hourly. Forward resolution rides the existing daily `resolve-calls`.

## 5. Validation (pre-registered — LOCK before first run)

**Claim under test:** the composite evidence rank predicts forward cross-sectional returns with an economically meaningful, cost-robust edge.

**Pre-registration (frozen before any result):**
- **Universe / window:** US + TSX, OOS 2018–2026, point-in-time, costs charged.
- **Primary gate — cross-sectional rank-IC** of composite vs forward **1-month** return: block-bootstrap CI **excludes 0**, positive, **AND mean IC ≥ 0.02** (same bar as ADR-044).
- **Secondary — top-decile minus SPY** forward excess: block-bootstrap **Sharpe-diff CI excludes 0**, net of costs (same bar as ADR-046).
- **Frozen weights / params:** composite weights and the 200-day/min-history params set before the run; **no re-tuning to improve the result** (anti-p-hacking, the ADR-046 discipline).

**Outcome → the screen's LABEL (not a project KILL):**
- **PASS** (primary or secondary clears): screen earns `VALIDATED`; proceed to Phase B as a trusted ranker; begin forward-tracking with confidence.
- **INCONCLUSIVE** (IC positive but < 0.02, or CI spans 0): screen ships `RESEARCH_ONLY` — evidence ranker + scorecard, abstains from "buy" language; **proceed to Phase B anyway** (the research/transparency value stands; the brief labels candidates "evidence-ranked, not validated").
- **HALT (hard intercept):** IC significantly **negative** (CI entirely < 0) **OR** the source-health audit fails → do **not** ship the screen; fix data or pivot. Shipping a negative-edge ranker as "names to consider" would actively mislead — the one outcome that stops the phase.

**Honest non-claims:** we will not call this alpha, will not claim it beats SPY unless the gate clears, and will print the IC/CI/p-value on every output so the label is never stronger than the evidence.

## 6. Privacy & honesty (hard requirements)
- Screen runs on the public universe (no holdings) → no privacy surface, but the **brief** (Phase B) that overlays holdings keeps the ADR-047 masking rules.
- Every report prints the **full ranked distribution** + the validation label + the scorecard reference — abstention reads as rigor, never a silent top-N cut.

## 7. Testing
- Domain scorers: unit + Hypothesis property tests (z-score mean≈0/var≈1 on non-degenerate input; `composite_score` monotonic in a factor holding others fixed; `rank_universe` stable/total order; `eligible` False below min-history).
- Use case: fakes for price/analyst/fundamentals/narrator; assert point-in-time access, narrator cannot mutate scores, full-distribution logged.
- Backtest: synthetic fixtures with a *known* planted IC to prove the harness recovers it, and a *zero-IC* fixture to prove it does not false-PASS.
- `make check` green (mypy strict, 90% cov) before any live run.

## 8. Open questions for reviewer
1. Top-N for the weekly shortlist — **10** (matches the user's ask) or surface the full ranked deciles and let the brief pick 10? (Lean: rank all, present 10.)
2. Composite weights — equal-weight the four factors for v1 (honest, no tuning), or literature-prior weights (momentum-heavy)? (Lean: equal-weight v1; revisit only via a pre-registered change.)
3. Revision-momentum coverage: accept partial analyst coverage with a flagged-neutral default (ConvictionSignalCache pattern), or restrict the screen to names with full coverage? (Lean: flagged-neutral, never a silent pin.)

---

## 9. Phase Exit Gate → Phase B entry (validate-as-we-go)

**Before Phase B begins, confirm and record:**
- [ ] `backtest-screen` has been run on the LOCKED pre-registration and a verdict recorded (PASS / INCONCLUSIVE / HALT) with the IC, CI, Sharpe-diff, and n in `data/reports/`.
- [ ] The screen's `label` (VALIDATED vs RESEARCH_ONLY) is set from that verdict and surfaced in `ScreenResult`.
- [ ] `make check` green; the screen's `SurfacedCall`s resolve correctly through existing forward-tracking (one end-to-end check vs SPY).

**Intercept rule:** if the verdict is **HALT** (negative IC or broken data), **stop here** — do not build Phase B on a misleading screen. Branch to a data-repair task (ADR-042 playbook) or a pivot decision, and update ADR-049's phasing. If **PASS** or **INCONCLUSIVE**, proceed to Phase B carrying the honest label forward.

**Discovery checkpoint:** record any surprise from the backtest (a factor that dominates, a regime where the screen inverts, a coverage cliff). These feed Phase B's regime conditioner and Phase D's graft decision — capture them now, while the evidence is fresh.
