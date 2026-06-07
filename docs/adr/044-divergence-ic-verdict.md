# ADR-044: Divergence IC Verdict — Intensity-Divergence Falsified (KILL)

**Date:** 2026-06-06
**Status:** Accepted
**Deciders:** Tirth Joshi

## Context

Sub-project D ran a **pre-registered cross-sectional Information Coefficient (IC) falsification test** on the intensity-divergence signal — the project's last untested "edge" hypothesis after ADR-039 (no OOS conviction edge) and ADR-043 (6/8 conviction dims dead, conviction ≈ data-freshness).

The signal under test (`intensity_divergence_raw`, ADR-041): attention acceleration (Wikipedia pageviews intensity) minus clamped recent up-price-move. Positive = attention rising faster than price (the thesis's "buzz leads price" lead). Continuous, intensity-only, sentiment-free.

### Pre-registration (LOCKED before any result was seen)

- **Primary horizon:** 1 month (21 trading days).
- **Gate:** mean rank-IC bootstrap CI excludes 0, positive, AND |mean IC| ≥ 0.02.
- **Universe:** broad ~518 (S&P 500 + NASDAQ-100), survivor-biased (a deliberately *flattering* sample — if the signal can't survive here, it's dead).
- **Secondary horizons:** 1w (5d), 3m (63d) — **exploratory only**, do not move the gate.

### Why this is the only honest validation path

The conviction backtest (ADR-039) failed OOS; forward-tracking is slow. A cross-sectional IC on point-in-time data can *cheaply falsify*: a non-positive IC on a survivor-biased sample kills the signal outright; a positive IC merely earns the right to forward-track (it is **not** itself proof of tradeable edge — costs, turnover, capacity unmodeled).

### Data integrity (the hard part — Phase 3.5)

The first live attempt was invalid: Wikipedia attention covered only **1.5% (8/518)** of the universe — unmapped tickers queried the raw symbol as an article title and got noise stubs. Fixing this took five hardening passes (R1–R5): 429 backoff + `SourceThrottledError` (throttle ≠ empty), an OpenSearch article resolver with view-volume validation, a resolved-map merge, a throttle-≠-rejection fix, and yfinance legal-suffix normalization (raw-first/cleaned-fallback so "Apple Inc." stays the company, "AbbVie Inc." → "AbbVie"). Final coverage: **430/518 (83%)**, 1.4M attention rows. The remaining ~88 are delisted/acquired (ATVI, SIVB, PXD, SPLK…) or deep name-mismatches. The test ran on clean, broadly-covered data.

## Decision

**KILL the intensity-divergence signal.** Observed cross-sectional rank-IC, run 2026-06-06 on the 430-ticker mapped universe:

| Horizon | mean IC | IC-IR | n_dates | bootstrap 95% CI | Gate result |
|---------|---------|-------|---------|------------------|-------------|
| 1w (5d) — exploratory | **0.0072** | 0.090 | 499 | [0.00122, 0.01542] | KILL (|IC| ≪ 0.02) |
| **1m (21d) — PRIMARY** | **0.0040** | 0.051 | 496 | [−0.00295, 0.01247] | **KILL** (CI spans 0; |IC| ≪ 0.02) |
| 3m (63d) — exploratory | **−0.0046** | −0.066 | 490 | [−0.01237, 0.00391] | KILL (negative) |

Reports: `data/reports/divergence_ic_21d.json` (primary), `divergence_ic_5d.json`, `divergence_ic_63d.json`.

### Reading the result plainly

- **Primary (1m):** mean IC 0.0040 is dead-center noise; the bootstrap CI spans zero. No predictive power.
- **1w:** the only horizon whose CI excludes zero — but |IC| = 0.0072 is an order of magnitude below the 0.02 economic-relevance bar. The pre-registration set 0.02 precisely so a statistically-detectable-but-economically-trivial effect could not be spun as "edge." It is noise we have enough dates (499) to measure.
- **3m:** faintly negative.

The signal is falsified **even on a survivor-biased sample** that should have flattered it. There is no intensity-divergence edge to forward-track.

## Consequences

- **No Phase 5.** Divergence-led surfacing (Tasks 8–9) was conditional on PROCEED. It is not built — building a surfacing engine on a falsified signal would manufacture false confidence, the exact failure mode ADR-039/043 warned against.
- **Forward clock not started.** No real-money path; nothing earned the right.
- **Infrastructure is kept** — `intensity_divergence_raw`, `ic_analysis` (Spearman cross-sectional IC), `DivergenceICBacktestUseCase`, the `validate-divergence-ic` CLI, the article resolver, and the 83%-coverage attention map are a reusable, honest falsification harness and a clean data layer. They are the protected baseline for testing the *next* candidate signal, not dead weight.
- **Survivorship caveat (stated, not hidden):** the universe is current S&P/NDX membership; delisted names are absent. This biases the test *toward* finding edge, which makes the null result stronger, not weaker.

### What this means for the project

Three independent honest tests now agree: conviction has no OOS edge (ADR-039), conviction dimensions are dead/degenerate on the spine (ADR-043), and intensity-divergence has no cross-sectional IC (this ADR). The product thesis "surface a tradeable edge from public attention/conviction signals" is **not supported by evidence.** The defensible product is what the engine already is: an honest evidence-aggregator that **abstains** when signals are absent, plus a rigorous, reusable validation harness. The next move is a decision for Tirth — pivot to a different primary signal, reframe as a research/monitoring tool, or stop adding signals and harden the abstention product.

## Related

- ADR-039 — no OOS conviction edge (evidence-first + abstention)
- ADR-041 — Honest Opportunity Engine (the divergence signal definition)
- ADR-043 — conviction dims dead → divergence-led surfacing (the hypothesis this test falsifies)
