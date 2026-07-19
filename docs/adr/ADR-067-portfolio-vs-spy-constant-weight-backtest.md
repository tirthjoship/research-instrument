# ADR-067: Portfolio vs. SPY — Constant-Weight Backtest, Not Fabricated Interpolation

**Date:** 2026-07-19
**Status:** Accepted
**Deciders:** Tirth Joshi

## Context

My Portfolio's "Portfolio vs SPY" chart (`adapters/visualization/tabs/positions.py::_perf_series`)
was, by its own docstring, a **"v1 linear ramp"**: a straight-line
interpolation from 0% to the current total P&L%, plotted against fixed,
hardcoded labels ("Jan"/"Mar"/"Jun") regardless of when anything was actually
bought. It contained no real historical data point between the start and end
of the line. This directly contradicts this project's own "never fabricate a
series" discipline (see the sparkline component's "no projection" comment,
and the RESEARCH_ONLY/attribution labeling used everywhere else in the
dashboard).

The natural fix — anchor the chart to each position's real purchase date —
turned out not to be buildable: the uploaded holdings CSV format this project
reads (`application/holdings_reader.py::read_holdings()`) has no trade/purchase
date column at all (verified against the actual broker export header:
`Account Name, Account Type, ..., Symbol, Exchange, ..., Quantity, ...,
Book Value (CAD), ..., Market Value, ...` — no date field anywhere). There is
no per-lot timing information anywhere in this project's data model to
reconstruct a literal trade-by-trade timeline from.

## Decision

Replace the fabricated ramp with a **constant-weight backtest**: for the
selected window, fetch each currently-held ticker's real historical closes
(`adapters/visualization/price_cache.py::fetch_price_history`, already used
elsewhere for sparklines/technicals — extended to also return `dates`
alongside `closes`, purely additively), weight each ticker's daily return by
its **current** portfolio weight (not cost, not value), normalize every series
to start at 0% at the window's first real date, and compare against SPY's
real closes over the same dates. The UI caption discloses the simplification
explicitly: *"Constant-weight backtest: today's holdings and weights, priced
historically — not your literal trade-by-trade timeline (purchase dates
aren't in the uploaded holdings file)."* When some held tickers lack cached
price history, the caption additionally discloses what fraction of book
weight the chart actually covers, rather than silently treating a partial
subset as if it were the whole portfolio.

This is the same category of decision as ADR-055/ADR-056 (analyst consensus
attributed-not-adopted; news/buzz labeled "context, not signal"): where this
project can't show a ground-truth number, it shows the closest honest
approximation it can build from real data, labeled clearly as such — never a
fabricated stand-in presented as if it were real.

## Consequences

**Positive:**
- No fabricated data point survives anywhere in the chart — every plotted
  value is computed from a real historical close, for a real currently-held
  ticker, on a real calendar date.
- Consistent with this project's existing corpus of "attribution, not
  invention" decisions (ADR-055, ADR-056) rather than a one-off exception.
- Degrades honestly: renders nothing (a plain "not enough price history"
  message) rather than a misleading chart when zero held tickers have cached
  history, and discloses partial coverage when some do.

**Negative:**
- Still not a literal trade-by-trade performance history — a user who bought
  a position last week and one three years ago sees them both weighted
  identically at "today's weight" across the whole window, which is a real
  simplification with a real cost to precision. This is disclosed in the UI
  caption, not hidden, but it means the chart answers "how would today's
  book have performed over this window" rather than "how did my actual
  trades perform" — a materially different (though still honest) question.
- Would become buildable as literal trade history only if a future change
  adds purchase-date capture to the holdings CSV format or an equivalent
  trade-log source — out of scope for this decision.
