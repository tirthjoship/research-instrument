# ADR-058: Lazy Prices (10-K text-change) signal — IC verdict: INCONCLUSIVE / does not pass

- **Status:** Accepted (verdict recorded; signal NOT promoted)
- **Date:** 2026-06-28
- **Pre-registration:** ADR-057 (hypothesis, locked gates, one-shot evaluation — no tuning after the run)
- **Report:** `data/reports/lazy_prices_ic_63d_2026-06-28.json` (full run; `smoke_limit: 0`, universe 512)

## Context

ADR-057 pre-registered the Lazy Prices hypothesis (Cohen, Malloy & Nguyen 2020): firms that *change* their 10-K language quarter-over-quarter subsequently underperform, so a low-text-change cohort should earn positive forward excess returns. We locked the gates in advance and committed to a single, one-shot evaluation — read the verdict once, write this ADR, no re-runs or tuning. The supervised full run completed 2026-06-28.

**Locked gates (ADR-057):** `ic_bar = 0.02`, `coverage_floor = 0.80`, `min_cohorts = 20`, `min_events = 1000`, `slippage_bps = 50`.

## Result (read once, no tuning)

| Metric | Value | Gate | Pass? |
|---|---|---|---|
| Mean IC (63d horizon) | **+0.0156** | ≥ 0.02 | **No** (below bar) |
| IC bootstrap 95% CI | **[−0.00097, +0.0350]** | excludes 0 | **No** (crosses 0) |
| IC IR | 0.281 | — | weak |
| Net long–short after 50bps slippage | **−0.0093**, CI [−0.0148, −0.0026], p(≥0)=0.995 | > 0 | **No** (significantly negative) |
| Coverage | 89.65% | ≥ 0.80 | Yes |
| Cohorts / events | 40 / 18,360 | ≥ 20 / ≥ 1,000 | Yes |
| Date-level t-stat | 1.78 (p=0.041) | — | marginal (parametric only) |
| Wilcoxon / sign-test | p=0.103 / p=0.437 | — | **not significant** |
| Concentration (top-3 of 40 dates) | 32.97% of the signal | — | fragile |

## Decision

**Verdict: INCONCLUSIVE — the hypothesis does NOT clear its pre-registered gate. The Lazy Prices signal is NOT promoted to a production factor.**

Rationale — the evidence points the wrong way once held to the locked, cost-aware standard:
1. **Below the bar.** Raw mean IC (+0.0156) is under the pre-registered `ic_bar` of 0.02.
2. **Not distinguishable from zero.** The IC bootstrap CI crosses zero; the non-parametric date-level tests (Wilcoxon, sign-test) are non-significant. Only the parametric t-test is marginal (p=0.04), and the signal is concentrated in a handful of dates (top-3 ≈ 33%) — fragile, not broad.
3. **Negative after costs.** The tradeable net long–short return after 50bps slippage is significantly **negative** (p(≥0)=0.995). Whatever marginal cross-sectional ordering exists does not survive realistic implementation.

This is the honest, pre-registered outcome: a weak, cost-fragile, statistically-ambiguous result on a deliberately survivor-biased universe. We label it INCONCLUSIVE rather than a clean null (the raw point estimate is marginally positive, parametric p≈0.03) — but it falls short of PASS, and the post-cost long–short is adverse, so there is **no actionable edge**.

## Consequences

- **No production wiring.** The Lazy Prices factor is not added to the screener/ensemble. The scaffolding remains for the record but is not promoted.
- **No further tuning.** Per the ADR-057 pre-registration this was one-shot; we do not re-run with adjusted parameters (doing so would invalidate the registration).
- **Honesty-as-product.** Recorded as a falsified-style negative result alongside ADR-044 (sentiment IC) and ADR-053 (insider-cluster) — candour about what does *not* work is the product.
- **Re-opening criterion (future, would require a NEW pre-registration):** a survivorship-free point-in-time universe + a cost model under 50bps + an out-of-sample window would be needed before this hypothesis could be revisited; absent those, it stays closed.

## Links

- ADR-057 — pre-registration + locked gates
- ADR-044 — divergence/sentiment IC verdict (falsified)
- ADR-053 — insider-cluster falsification verdict
- Runbook: `docs/runbooks/lazy-prices.md`
- Verdict report: `data/reports/lazy_prices_ic_63d_2026-06-28.json`
