# ADR-005: Progressive NLP ladder with measured lift

**Date:** 2026-05-23
**Status:** Accepted
**Deciders:** Tirth Joshi

## Context
Multiple NLP approaches available at different cost/complexity levels. Needed strategy for which to use and when to upgrade.

## Decision
Three-step ladder: (1) Keyword baseline → (2) Flan-T5 fine-tuned → (3) Claude/Gemini API. Upgrade only when measured precision lift > 2%.

## Alternatives Considered
- **Start with best model (LLM API)** — expensive, can't prove it adds value vs simpler approach.
- **Start with FinBERT** — shown to underperform Flan-T5 in 2026 research.

## Consequences
**Positive:**
- Each step is a measurable A/B test.
- Interview story: "I measured marginal lift at each sophistication level."
- Cheapest approach first.

**Negative:**
- Keyword baseline is crude — may confuse "crashed but buy the dip" scenarios.
- Accepted: Flan-T5 upgrade path addresses this.

## Superseded By
None
