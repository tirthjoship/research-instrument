# ADR-066: Aggregate Holdings by Ticker Before Building the Weekly Brief

**Date:** 2026-07-19
**Status:** Accepted
**Deciders:** Tirth Joshi

## Context

`application/cli/brief_commands.py`'s `weekly-brief` command read holdings via
`application/holdings_reader.py::read_holdings()` and passed them straight into
the risk/discipline pipeline — one row **per account/lot**, never aggregated by
ticker. A real book holds the same stock across several accounts (FHSA, TFSA, a
non-registered account, ...), so a ticker split across two accounts produced
two separate entries in `brief.holdings`.

This was latent until the Home tab's Needs Review rows started using an
explicit, ticker-derived `st.session_state` key (`nr_open_{ticker}`) for a
merged-row UI component (this session's earlier work). Two holdings sharing a
ticker collided on that key: `streamlit.errors.StreamlitDuplicateElementKey`,
confirmed live. The same un-aggregated data also made Home's flagged/total
counts diverge from My Portfolio's — the Portfolio tab already aggregates via
`aggregate_to_book()`, so its 42-flagged/59-total was correct while Home's
46-flagged/66-total (inflated by duplicate tickers) was not, even though both
read from the same uploaded CSV.

## Decision

Add `application/holdings_reader.py::aggregate_holdings_by_ticker()` — sums
`shares`/`cost_basis` per ticker across accounts, same pattern as
`aggregate_to_book()`, but returns the original `Holding` type (ticker/shares/
cost_basis/account_type) instead of converting to `domain.models.Holding`, so
it drops directly into the weekly-brief pipeline without touching any
downstream consumer's contract. Wired in immediately after `read_holdings()`
in the `weekly-brief` CLI command.

**Mixed-account tax-narrative honesty:** `application/narrator.py` only
emits "In a {account}, there is no capital-gains tax friction on selling."
when `account_type` is exactly `TFSA`/`RRSP`/`FHSA`. When a ticker's lots span
more than one distinct account type, the aggregated row's `account_type`
becomes `""` (not an arbitrary pick of one account) — so the claim is
correctly suppressed for the whole position rather than falsely asserted for
whichever portion is actually in a non-matching (e.g. non-registered) account.
`aggregate_to_book()` sidesteps this question entirely (its target type has no
`account_type` field at all); this decision keeps the field but makes it
honest under aggregation rather than dropping it.

## Consequences

**Positive:**
- Fixes a real, live production crash (`StreamlitDuplicateElementKey`) at its
  root cause, not by making the UI tolerant of duplicate keys.
- Home's Needs-Review/total counts now match My Portfolio's — both tabs read
  the same aggregated reality instead of two different ones.
- The weekly `.md` report and `brief_summary.json` also benefit — a holding
  split across accounts now shows one combined P&L line instead of two
  partial, confusing ones.

**Negative:**
- Per-account granularity is lost in `brief.holdings` (e.g. "60 shares in
  FHSA, 40 in TFSA" collapses to "100 shares, cost-basis-weighted average
  price"). This mirrors a tradeoff `aggregate_to_book()` already made for My
  Portfolio, so it's not a new class of information loss — just extended to
  the weekly-brief/Home pipeline for consistency.
- A ticker held across a registered and non-registered account now gets no
  capital-gains-tax note at all (rather than a note that's only correct for
  part of the position). This is the honest choice, but it does mean that
  specific narrative detail disappears rather than becoming more granular.
