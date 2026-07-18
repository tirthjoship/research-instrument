# ADR-055: Third-Party Analyst Consensus Is Attributed, Never Adopted

**Status:** Accepted (backfilled 2026-07-17 — implemented earlier, never written up)
**Related:** ADR-056 (context-not-signal labeling, the general form of this rule)

## Context

Analyst price targets and ratings (via yfinance's consensus data) are
third-party opinions, not this engine's own output. Displaying them
without clear attribution risks the dashboard implicitly co-signing a
Wall Street analyst's forecast as if it were the project's own claim —
directly contradicting the project's central discipline: it does not
predict returns, and it does not launder someone else's prediction as its
own either.

## Decision

`application/analyst_panel.py::AnalystPanel` is a pure data-transfer
object: `count`, `mean_rating`, `target_mean/high/low`, `as_of`,
`attribution`, and `data_gap` — every field sourced from and labeled as
third-party consensus. No field is ever computed, adjusted, or reframed
by this project's own models. When yfinance has no analyst data for a
ticker, `data_gap=True` is returned — never a silently substituted
default or an inferred value.

## Consequences

**Positive:** A user reading the Analyst panel always knows they're
looking at Wall Street's opinion, not this project's. Matches the
project's honest-DATA-GAP philosophy (confirmed again this session:
India's analyst-consensus gap has no free-tier solution across three
independent providers — surfaced honestly rather than backfilled with a
weaker proxy).

**Negative:** None identified — this is a labeling/provenance
discipline, not a feature trade-off.
