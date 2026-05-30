# ADR-004: Flan-T5 over FinBERT for financial sentiment

**Date:** 2026-05-23
**Status:** Accepted
**Deciders:** Tirth Joshi

## Context
Need NLP model for financial text sentiment scoring. Original plan used FinBERT. Research in May 2026 showed FinBERT limitations.

## Decision
Replace FinBERT with fine-tuned Flan-T5 as Step 2 in NLP ladder.

## Alternatives Considered
- **FinBERT (110M params)** — insensitive to numerical values, accuracy drops on complex sentences, trained on pre-2020 text.
- **FinGPT/FinLlama** — larger, harder to run on GitHub Actions free tier.
- **Claude/Gemini API** — costs money per call.

## Consequences
**Positive:**
- Outperforms FinBERT on benchmarks.
- Smaller than FinGPT (runs locally).
- Free.
- Well-documented fine-tuning.

**Negative:**
- Still may miss modern financial slang ("diamond hands").
- LLM tier (Claude/Gemini) remains available as Step 3 escalation.

## Phase 3B Update (2026-05-30)

**Deployment decision:** Run Flan-T5-base (250M params) locally on M2 MacBook Air via MPS (Metal Performance Shaders) backend. ~0.3s/article on Apple Silicon.

- **No fine-tuning for Phase 3B** — zero-shot classification only. Prompt: "Classify the sentiment of this financial news about {ticker} as positive, negative, or neutral: {text}"
- ~500 articles/day × 0.3s = ~2.5 minutes for daily scan. Acceptable.
- Model downloaded once (~1GB), cached locally. No API costs.
- If MPS unavailable, falls back to CPU (~1s/article, still viable).

## Superseded By
None
