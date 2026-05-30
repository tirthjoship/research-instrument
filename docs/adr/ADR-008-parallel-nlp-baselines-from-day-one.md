# ADR-008: Parallel NLP baselines from day one (keyword + Flan-T5 zero-shot)

**Date:** 2026-05-25
**Status:** Accepted (supersedes ADR-005 partially)
**Deciders:** Tirth Joshi

## Context
Original plan: keyword scorer first, upgrade to Flan-T5 later if keyword plateaus. Risk identified during design review: keyword scoring may be too crude to detect real sentiment, causing a false negative on the divergence thesis. If divergence appears to have no signal, it's ambiguous — thesis problem or scorer problem?

VanEck BUZZ ETF comparison showed that even sophisticated NLP on 15M data points monthly fails to beat S&P 500 risk-adjusted. The signal quality isn't the only variable — how you use it (divergence vs popularity) matters. But we need to isolate variables.

## Decision
Run keyword scorer AND Flan-T5 zero-shot (no fine-tuning) in parallel from Phase 3B launch. Both score the same texts. Both produce divergence signals. Compare divergence signal quality from each.

- If both show no divergence signal → thesis problem
- If Flan-T5 shows signal but keywords don't → scorer problem, upgrade
- If both show signal → keyword is sufficient, Flan-T5 is insurance

## Alternatives Considered
- **Sequential ladder (original plan)** — risk of killing valid thesis due to crude scorer. Rejected.
- **Start with Flan-T5 only** — loses the baseline comparison. Rejected.
- **Start with LLM API** — too expensive before proving thesis. Deferred to Phase 4.

## Consequences
**Positive:**
- Eliminates ambiguity on sentiment quality vs thesis validity.
- Flan-T5 zero-shot is free (local inference), no fine-tuning needed.
- Built-in A/B test from day one.

**Negative:**
- Slightly more compute per run (two scorers).
- Accepted: both are fast, not a bottleneck.

## Relationship to ADR-005
ADR-005's ladder structure remains valid. This ADR moves Step 2 (Flan-T5) to run alongside Step 1 (keyword) rather than after it. Step 3 (LLM API) still deferred to Phase 4 and reframed as LLM-as-analyst (causal reasoning, not just sentiment classification).

## Phase 3B Update (2026-05-30)

**Implementation refined during grilling session:**

Both scorers produce a `sentiment_agreement` feature (1.0 if both agree on direction, 0.0 if they disagree). This meta-feature itself is predictive — high agreement = higher confidence in sentiment signal.

**Sources:** RSS feeds (6 publishers) + Reddit (PRAW, pending API approval). Google CSE and StockTwits deferred — tight rate limits and unstable API respectively.

**Scoring flow per article:**
1. RSS adapter extracts article text + ticker mentions
2. KeywordScorer: instant, rule-based, bullish/bearish keyword counting → score in [-1, 1]
3. FlanT5Scorer: ~0.3s, zero-shot classification → "positive"/"negative"/"neutral" mapped to score
4. Both scores stored in `buzz_signals` SQLite table with `scorer` column distinguishing them
5. `sentiment_agreement` computed at feature engineering time

**Source reliability integration (ADR-021):** Each scorer's directional predictions are tracked per-source. Over time, `source_weighted_sentiment` uses reliability to discount noisy sources.

## Superseded By
None
