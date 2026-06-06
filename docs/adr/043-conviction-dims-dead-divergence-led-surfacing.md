# ADR-043: Conviction Dimensions Dead on Mid-Cap Spine → Divergence-Led Surfacing

**Date:** 2026-06-05
**Status:** Accepted
**Deciders:** Tirth Joshi

## Context

Sub-project B (ADR-042) shipped a discrimination audit (`DiscriminationAuditUseCase`) to evaluate conviction once the data layer was clean (throttle ≠ empty rule, spine-aligned backfill, `cap_tier` fix). The audit ran against 63 warmed thematic spine candidates on 2026-06-05.

### Discrimination Audit Results (`data/reports/dim_audit_20260605.txt`)

| Dimension | Variance | Neutral Share | Status |
|-----------|----------|---------------|--------|
| `temporal_freshness` | 2.649 | 0.00 | **Varying — but measures data recency, not opportunity** |
| `fundamental_basis` | 0.250 | 0.02 | **Weakly live** |
| `smart_money` | 0.000 | 0.00 | **DEAD** — mid-caps rarely have 13D/Form-4; SEC EDGAR returns nothing |
| `signal_agreement` | 0.000 | 0.00 | **DEAD** — derived from the other dead dims |
| `sentiment_momentum` | 0.000 | 1.00 | **DEAD** — not computed in bulk scan |
| `ml_direction` | 0.000 | 1.00 | **DEAD** — no per-ticker model inference in bulk |
| `event_signal` | 0.000 | 1.00 | **DEAD** — Gemini/headline port not wired (cost) |
| `analyst_signal` | 0.000 | 1.00 | **DEAD** — no analyst coverage for thematic mid-caps |

**6 of 8 conviction dimensions are completely non-discriminating on the thematic mid-cap spine.** The remaining 2 are `temporal_freshness` (strong variation, var=2.649) and `fundamental_basis` (weak, var=0.250). Because `temporal_freshness` dominates, conviction effectively ranks names by how recently their data was fetched — not by opportunity quality.

**Result:** The engine honestly abstains (0 surfaced) even on warmed, cap-tier-fixed data. This is not confounded by the data-layer bugs that sub-project B fixed. It is a genuine structural finding: conviction is non-discriminating for free-data thematic mid-caps.

This result is consistent with ADR-039's finding: no statistically significant out-of-sample edge in the backtestable slice of conviction (large-cap, p=0.13; all p > 0.05). The discrimination audit on the spine makes the mechanism explicit — the dims the backtest favored (smart-money + analyst) return nothing on mid-caps because the underlying data sources (SEC EDGAR 13D, analyst ratings) simply do not cover this universe.

## Decision

Four decisions, locked for implementation as sub-project C ("divergence-led surfacing"):

1. **Reject reviving the 6 dead dims via paid APIs.** The instinct to add more signals (Gemini event classifier per ticker in bulk, paid analyst feeds, paid social data) is the "add more signals" reflex that ADR-039's evidence already rejected out-of-sample. Paid APIs add cost and key management; they do not change the validated finding that the full 8-dim conviction engine has no demonstrated OOS edge. This option is rejected.

2. **Prune / mark the 6 dead dims explicitly.** Rather than silently carrying dimensions that contribute nothing, the engine will mark `smart_money`, `signal_agreement`, `sentiment_momentum`, `ml_direction`, `event_signal`, and `analyst_signal` as inactive on the thematic mid-cap spine. Conviction continues to compute from whatever dims are live (currently `temporal_freshness` + `fundamental_basis`), but the honest caveat is that conviction on this universe reflects data freshness and basic valuation — not opportunity conviction in the classic sense.

3. **Divergence-led surfacing: divergence becomes PRIMARY, conviction demoted to tiebreaker.** Divergence (attention-acceleration vs price) is live, varying, and embodies the core thesis: *attention leads price*. It is computed from Wikipedia pageviews, Google News RSS, and Google Trends — all free, no per-ticker API cost, and already wired (sub-project A). Conviction (using only the 1–2 live dims) becomes a light tiebreaker for names that already clear the divergence bar. The minimum-history gate (`has_min_history`, ~21 days) and honest abstention are retained. The layered trigger `conviction × divergence` inverts to `divergence (primary) × conviction (tiebreaker)`.

4. **Forward-tracking is the arbiter.** The daily scan + resolve loop (scan-opportunities → resolve-calls → conditional backfill, ADR-041) accumulates resolved out-of-sample outcomes at 1w/1m/3m vs SPY + NDX. This is the only mechanism that can produce honest evidence of edge on this universe and this thesis. Surface on divergence so the loop finally generates resolved calls — the wall-clock evidence accumulation starts immediately once names are surfaced.

## Alternatives Considered

- **Add paid API coverage for the dead dims** — rejected: cost + key management; contradicts the free-data-first, honest-abstention design; ADR-039 already found no OOS edge on the backtestable dims (smart-money + analyst); adding the others is not the move.
- **Lower conviction thresholds to force surfacing on large-caps instead** — rejected: re-runs the failed conviction-heavy setup on a universe where that has already been tested. The point is to test the attention-leads-price thesis on thematic mid-caps.
- **Wait for more spine data before deciding** — rejected: 63 warmed candidates with 0.000 variance on 6 dims is conclusive. More data will not revive dims where the underlying source (SEC EDGAR, analyst ratings) structurally returns nothing for this universe.
- **Abandon the mid-cap spine entirely** — rejected: the thesis lives here. Mega-cap attention is priced in. Mid-cap thematic names (space tech, SMR, memory) are the opportunity surface.

## Consequences

**Positive:**

- The engine stops lying to itself. Conviction was ranking by data freshness; that is worse than a uniform prior. Making divergence primary aligns the surfacing trigger with the actual thesis.
- Divergence is **already live and varying** — the transition to sub-project C does not require new data sources or new adapters, only a reordering of the trigger logic.
- Once divergence-led surfacing produces resolved calls, the forward-tracking loop generates honest out-of-sample evidence. This is the only path to knowing whether the attention-leads-price thesis holds on this spine.
- The pruning decision is **evidence-based**: the audit numbers (var=0.000, neutral_share=1.00 for 6 dims) come from the clean post-sub-project-B data layer, not from confounded inputs.

**Limitations & risks (do not oversell):**

- **This does not prove edge.** Divergence-led surfacing improves honesty and unblocks the forward-tracking loop. It does not demonstrate that divergence predicts returns on the thematic mid-cap spine. That evidence does not exist yet — it will accrue over weeks of forward-tracking.
- **Conviction may simply not be measurable for free-data thematic mid-caps.** SEC EDGAR, analyst ratings, and event classification all require either paid data or per-ticker API cost that is not viable for bulk scanning of 350+ tickers. The 2 live dims (`temporal_freshness`, `fundamental_basis`) are honest but thin. Conviction may remain a weak tiebreaker indefinitely on this universe.
- **Implementation is pending.** Sub-project C is not yet built. The current codebase still uses the `conviction × divergence` layered trigger; divergence-primary logic is locked as a decision here, not shipped code.
- **The `temporal_freshness` dimension is not removed.** It still contributes to conviction (as a tiebreaker). It should be understood as a data-hygiene signal (how recently was this ticker's data fetched), not an opportunity quality signal.
