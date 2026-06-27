# ADR-045: Pivot from Return Prediction to Exit-Discipline + Evidence-Bounded Screening

**Date:** 2026-06-07
**Status:** Accepted
**Deciders:** Tirth Joshi

## Context

Three independent, pre-registered falsification tests have now killed the project's founding thesis — that public sentiment/attention/conviction signals predict returns:

- **ADR-039** — conviction has no out-of-sample edge (56%, p=0.13; validation slice fails 2018–23).
- **ADR-043** — 6/8 conviction dimensions are dead/degenerate; conviction ≈ data-freshness.
- **ADR-044** — intensity-divergence has no cross-sectional IC (1m=0.0040, CI spans 0) on a clean 430-ticker universe, all horizons.

This is a convergent negative: retail-accessible public attention/sentiment contains no detectable tradeable alpha (consistent with semi-strong efficiency). Continuing to bolt on signals would be the gambler's lever and risks p-hacking a spurious positive — the exact failure the pre-registration discipline exists to prevent.

Separately, the user's real trading history reframed the problem. His stock *selection* is excellent (MU +863%, PLTR +447%, AMD +195%); his losses come from *process* — holding broken-trend names down 30–57% (RIVN, NKE, SOUN, LSPD, FIGS), and mistiming exits (LULU: +27% round-tripped to −31%, anchored on an old price; MU: sold a winner too early). The documented behavior gap (avg equity investor lags the S&P ~848 bps/yr from the disposition effect — Barclays/DALBAR 2024) is the actual leak.

A June-2026 evidence review separated what is achievable from what is hype (sources in the spec): trend-following/time-series momentum (AQR; Antonacci dual momentum 17.4%/yr vs 8.85%, half the drawdown), regime detection, and behavior-gap closure have decades of out-of-sample support; LLM stock-pickers underperform and are regime-brittle (StockBench/KDD-2026); published anomalies decay ~58% post-publication (McLean & Pontiff 2016).

## Decision

**Pivot the engine from predicting winners to enforcing process**, with ambition bounded by an explicit evidence hierarchy.

1. **Core thesis: a retail edge is better PROCESS, not better PREDICTION.** The engine's primary job is disciplined entries/exits and risk management — trend filter (200-day) + volatility-scaled Chandelier trailing exit (rides MU-style runners, ejects LULU-style breaks) + relative-momentum selection.

2. **Evidence tiers bound what we will build:**
   - *Tier 1 (reliable, retail-accessible):* risk management, behavior-gap closure, factor premia (momentum/quality/value/low-vol).
   - *Tier 2 (earlier, modest, decaying — each independently falsified before use):* PEAD/earnings-revision drift, fundamental acceleration.
   - *Tier 3 (out of scope, no honest model delivers):* predicting ignition before it happens, a learning loop that compounds to high accuracy (non-stationary + adversarial markets, alpha decay), beating SPY by 20–30%.

3. **Screening, never prediction.** Candidate surfacing (Phase 2) ranks the universe by *falsified* factors and is framed as a filter ("names meeting evidence-backed criteria"), never a forecast. It rides speculative names only once a confirmed trend exists; it never calls them cold.

4. **"No false positives" is reframed as "cheap false positives."** The trailing-stop discipline makes wrong calls exit fast and small; the value is the asymmetry (wrong cheaply, right big), not predictive accuracy.

5. **"Learning over time" = regime-conditional weighting + self-calibration + abstention**, not accuracy-compounding. Extends ADR-039's abstention philosophy.

6. **Validation gates everything.** A pre-registered backtest (Phase 1) must pass a LOCKED bar — beat buy-and-hold on Sharpe (bootstrap CI excludes 0) AND cut max drawdown ≥30%, out of sample on US+TSX 2018–2026 — before any screener/recommendation layer (Phase 2) is built. KILL → stop, same as ADR-044.

## Consequences

- **The codebase repoints, it does not reset.** Reuses momentum features, `RegimeSplitter`, `DrawdownTracker`, `TransactionCostModel`, `precision_metrics` (bootstrap), the yfinance adapter, and point-in-time guards. New: `domain/trend_rules.py`, `domain/backtest_metrics.py`, `MomentumExitBacktestUseCase`, `PortfolioVerdictUseCase`, two CLIs.
- **The falsification harness (ADR-044) is the protected baseline** and is reused to vet every new factor.
- **Honest product identity:** a decision-support engine for disciplined entries/exits + risk, with calibrated confidence and abstention — explicitly NOT an alpha oracle. Real-money use is the user's own; the engine advises, it does not auto-trade.
- **Privacy:** the user's actual holdings live in a gitignored local file (`data/personal/`), never committed.
- **What is abandoned:** sentiment/attention/conviction as a *predictive* signal (kept only as possible future contrarian overlay), LLM/RL stock-picking, and any claim of predicting which name rises.

## Related

- ADR-039 (no OOS conviction edge), ADR-043 (conviction dims dead), ADR-044 (divergence IC verdict)
