# ADR-056: "Context, Not Signal" — Universal Attribution Label for News and Buzz

**Status:** Accepted (backfilled 2026-07-17 — implemented earlier, never written up)
**Related:** ADR-044 (divergence IC verdict — the falsification this decision follows from), ADR-055 (the same rule applied to analyst consensus)

## Context

ADR-044 tested whether sentiment-vs-price divergence predicts returns and
falsified it: signal-return IC was ≈0 across the tested window. Before
this decision, buzz/news panels risked implying predictive weight simply
by being displayed prominently next to price and technical data — even
though the underlying signal had already been proven to carry none.

## Decision

Every news/buzz surface in the dashboard carries the same fixed label,
verbatim: **"context, not signal"** (or, where richer captioning fits,
"Attributed, linked — context, not signal"), plus an explicit pointer to
the ADR-044 falsification when the surface is directly downstream of the
tested divergence signal. Implemented in `application/news_context.py`'s
`NewsContext.label` (a fixed constant, not a computed field — it cannot
drift per-ticker or per-run) and echoed in
`adapters/visualization/tabs/stock_analysis/buzz_view.py`'s headline
caption block.

`NewsContext` mirrors `AnalystPanel`'s shape (ADR-055): items sorted
newest-first, `data_gap=True` when no headlines exist for the window, and
attribution by source only — headlines are never re-framed as a
forward-looking claim.

## Consequences

**Positive:** A tested-and-falsified signal (ADR-044) cannot quietly
re-enter the dashboard's persuasive surface just because it's still
useful as descriptive context — the label travels with the data
everywhere it's shown, not just in the one place the test was run.

**Negative:** None identified — this is the direct, mechanical
consequence of taking ADR-044's falsification seriously rather than
quietly continuing to imply predictive value in the UI after the
backing signal was killed.
