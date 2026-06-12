# ADR-055: Cockpit Redesign — Two Surfaces on an Untouched Core

**Date:** 2026-06-12
**Status:** Accepted
**Deciders:** Tirth Joshi
**Builds on:** ADR-052 (alpha hunt closed — recommender ABSTAINS, RESEARCH_ONLY),
ADR-054 (portfolio-fit verdict: evidence + fit without prediction), ADR-048
(discipline forward-calibration gate), the dashboard v2 6-tab IA (PRs #46–#49)
**Supersedes (UX layer only):** the v2 six-tab dashboard. Domain/ and application/
layers are NOT changed by this decision.

## Context

The v2 dashboard reshuffled tabs without redesigning the experience. Investigation
of the running app (6 screenshots, 2026-06-12) found **six incoherent mini-apps**
with four different visual languages, dead/empty sections, and falsified-era
artifacts still leaking through (a `39.3` score gauge, divergence tables, a
penny-stock default). Two linked problems surfaced:

1. **Product incoherence** — the surface had no single reading order; the user
   opened it and did not know where to look.
2. **All defense, no offense** — the tool risk-checks and fit-checks names the user
   already supplies; it never answered *"what should I even look at next week?"*

A deeper split also emerged: a **family weekly-triage** audience and a **recruiter
methodology** audience want opposite things from the same pixels.

## Decision

**Two audiences → two surfaces, greenfield the cockpit on an untouched core.**

1. **Cockpit** (default) — a single-scroll family surface in strict priority order:
   **danger → your calls → how the week went → look into next → lookup**, with stock
   detail as an `st.dialog` drawer. One design system (one card primitive, one token
   set) — the concrete fix for the four-visual-languages problem. Implemented as
   `adapters/visualization/cockpit/`: an assembler (`cockpit.py`) + one renderer per
   section (`_danger`, `_calls`, `_retro`, `_discover`, `_lookup`) + `stock_detail.py`.

2. **Showcase** — the methodology / falsification / Trust content, relocated intact
   as the second surface (recruiter-facing). Its own coherent redesign is deferred
   (Project A2); until then it stays reachable via a router entry.

3. **One write only.** The cockpit gains exactly one write action: a **confirm-and-log**
   of the week's per-holding calls to the ADR-048 discipline forward gate, **idempotent
   per `as_of`**. This replaces the v2 My-Portfolio forms/sliders entirely. Everything
   else is read-only.

4. **Honest discovery** ("look into next") **splits two computations the old screen
   fused**:
   - **Factual rank** — present-day valuation/quality/health percentiles vs the
     universe. Pure arithmetic, zero prediction, **always computable → top-N always
     shows** (even when the gate abstains).
   - **Tradeable-edge verdict** — the pre-registered IC gate. It **stays abstaining**
     and is shown *as* the abstention, inline: *"the engine claims no predictive edge;
     these are research starting points only."*
   Framed **diversification-first**: rows lead with the gap vs the book's single
   dominant macro factor (correlation of candidate daily returns to that factor),
   factual rank as tiebreak. Capped at 3–5 rows.

5. **Legacy cruft deleted, not ported.** The `39.3` gauge, divergence tables, and
   penny-stock default contradict RESEARCH_ONLY and do not survive the rebuild.

## Architecture invariants held

- **Domain/ unchanged. Application/ gained exactly one module** — `diversification_query.py`,
  pure (stdlib only): the network/yfinance fetch lives in the adapter layer. Hexagonal
  boundary intact; the cockpit only *reads* existing, tested use cases.
- **RESEARCH_ONLY + FORBIDDEN_WORDS** (buy/sell/winner/conviction/predict/alpha/outperform)
  enforced on **every** cockpit surface via a package-wide source scan (`inspect.getsource`),
  not a convention — drift fails CI.
- Compute for the retired tabs stays in the core; only the Streamlit *render* files were
  deleted.

## What changed

- **New:** `adapters/visualization/cockpit/` (assembler + 5 sections + drawer);
  `application/diversification_query.py`; `price_cache.fetch_week_changes`; a universe
  guard test (delisted / foreign-suffix tickers pruned).
- **Deleted (render only):** `tabs/weekly_brief.py`, `tabs/research_candidates.py`,
  `tabs/positions.py`, `tabs/stock_analysis.py` + their tests.
- **Kept / relocated:** `tabs/risk.py` → the danger drill-down; `tabs/trust.py` → the
  Showcase surface.

## Consequences

- The weekly ritual is now one top-to-bottom scroll with a single log step; the
  family no longer navigates six tabs.
- Discovery survives gate abstention (the production reality) instead of going dark.
- The recruiter story is preserved but no longer dilutes the operational surface.
- **Verification:** `make check` = 1616 passing, 94% coverage, mypy strict clean.
  An Opus review sweep fixed two findings before merge: the diversification
  correlation is now **date-aligned** (joint dropna — was comparing different
  trading days), and the confirm-and-log **guards an empty `as_of`** (was a silent
  idempotency collapse).

## Deferred (tracked in STATUS.md, not blocking)

- `discipline_log.append_assessments` is non-atomic (a crash mid-write half-logs a
  week, which the `as_of` guard then treats as complete).
- Duplicate-ticker holdings overwrite rather than sum shares.
- Tighten the `cockpit.stock_detail` mypy `warn_return_any` override to one inline ignore.

## Follow-on projects (separate ADRs/specs when they start)

- **A2 — Showcase surface**: the recruiter falsification/methodology narrative as its
  own coherent design.
- **Project B — Alpha re-open**: keeping falsification gates open to keep testing
  (news/sentiment → next-week, cross-stock lead-lag). MUST go through pre-registration —
  not a re-run of the falsified ADR-044 divergence thesis. Run `ds-methodology-review`
  first.
