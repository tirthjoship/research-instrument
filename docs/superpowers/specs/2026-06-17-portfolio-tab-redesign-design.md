# My Portfolio Tab — Redesign Design Spec

**Date:** 2026-06-17
**Branch:** `feat/portfolio-tab-redesign` (worktree off `origin/develop`)
**Status:** LIVING DOC — sections locked one at a time. `[LOCKED]` = agreed, `[OPEN]` = still to finalize.
**Tab:** index 3, `adapters/visualization/tabs/positions.py` (full redesign)

---

## 1. Goal & North-Star  `[LOCKED]`

Redesign the My Portfolio tab to match the Research-Instrument language of the other redesigned tabs (Home/Screener/Risk) and to **scale cleanly to ~60 holdings**.

North-star (carried from dashboard redesign): **non-expert legibility + "what needs my attention"**, surfaced through *attributed evidence*, never prediction. A great tracker tells you what to fix / where risk hides — not just displays numbers.

**Chosen spine:** Review-queue-first (layout "B") with the allocation treemap promoted to a full-width showpiece high on the page (best trait grafted from layout "A"). Rejected: A (map-first, makes non-expert hunt for action) and C (analyst grid, decoration over discipline).

---

## 2. Page Structure  `[LOCKED]`

Top → bottom:

1. **Hero metrics (4)** — Book value · Total P&L (with vs-SPY badge) · Needs review (N of total) · Concentration (top-5 = X% of book).
2. **⚠ Needs review (N)** — full decision-card rows for holdings whose verdict ∈ {REDUCE, TRIM, REVIEW}, sorted by urgency. Bounded by *problems*, not book size.
3. **Your book at a glance** — full-width treemap grouped by sector. Size = weight, color = realized P&L.
4. **Healthy holdings (rest)** — dense sortable / filterable / paginated ledger table.
5. **Portfolio vs SPY** — full-width line, attributed actual.
6. **Admin (collapsed expanders)** — Trade history & outcomes · Closed positions · Watchlist · Record a trade.

---

## 3. Verdict Engine & Review-Card Reuse  `[LOCKED]`

**Same engine as Home — confirmed in code.** Verdicts come from `grade_position()` (`domain/discipline.py:69`) → `Verdict` enum {REDUCE, TRIM, REVIEW, HOLD, ADD_OK} → serialized to `data/personal/brief_summary.json` by `application/brief_summary.py`. Home's "Needs review" (`weekly_brief.py:217`, `_NEEDS_REVIEW = {REDUCE,TRIM,REVIEW}`) uses the identical source.

**Decision (chosen):** **Reuse the `decision_card` component on both surfaces.**
- Home = weekly digest moment. Portfolio = always-on book manager.
- Portfolio review cards reuse `render_collapsed_row` + `render_expanded_card` (`adapters/visualization/components/decision_card.py`) — NOT a copy.
- Expanded depth (meaning box, 4 metrics, 5 RAG signals, 5-verdict rubric, Google-AI case) is **fetched live on expand** via the same `_fetch_card()` path Home uses (`weekly_brief.py:310-361`). Works for any ticker, holdings included → real RAG, no fabricated dots.
- Interlinks per card: "↗ Open in Weekly Brief", "↗ Analyze in Stock Analysis" (pre-fills `session_state["analyze_ticker"]`).

**No new verdict logic.** UI/reuse only.

---

## 4. Honesty Guards  `[LOCKED]`

Carried, non-negotiable:
- Treemap color = **realized** P&L only, never predicted return (ref memory `attributed-not-predicted`).
- SPY comparison = attributed actual series, no projection.
- **DATA-GAP, never fabricate**: if `brief_summary.json` lacks a holding → DATA-GAP verdict/why; RAG shown only when live-fetched on expand.
- Verdict framed as a discipline *review prompt*, not a forecast or buy/sell instruction.

---

## 5. Data Additions  `[OPEN — to finalize]`

Identified, details pending:
- **`sector` per holding** — source `yfinance info["sector"]` (already fetched in watchlist via `fetch_ticker_info`), cached. Gates treemap grouping + table sector column + sector chips. *Open: domain model change vs adapter-side enrichment; cache strategy; fallback when sector missing.*
- **Top-5 weight** (concentration metric) — computed from holdings + live prices. *Open: exact definition (top-5 %? add HHI?).*
- **SPY return series** — from existing price fetch. *Open: time window + computation method (see §8).*
- **Live RAG/case on expand** — same path as Home; lazy, only on expand (60-holding perf). *Open: confirm lazy-fetch behavior + caching.*

---

## 6. Treemap Spec  `[OPEN — next up]`

Full-width, grouped by sector; size = weight, color = realized P&L; ticker label on big tiles + hover (sparkline + verdict + P&L) for small. *Open: grouping/sizing algorithm, color-scale thresholds, small-tile label threshold, "+N" bucket, no-sector fallback, small-portfolio (<~5 holdings) behavior, plotly `go.Treemap` vs custom HTML.*

---

## 7. Healthy Holdings Table  `[OPEN]`

Dense sortable / filterable / paginated ledger. *Open: columns, default sort, page size, sortable columns, filter/chip behaviors, how verdict pill renders inline.*

---

## 8. Portfolio vs SPY Chart  `[OPEN]`

Full-width attributed line. *Open: time window (since-first-buy vs YTD), simple vs money-weighted return, how rebuilt on trade changes, chart builder (reuse `charts.py`).*

---

## 9. Empty / Small-Portfolio States  `[OPEN]`

*Open: behavior at 0 / 1–5 holdings — does sector treemap still make sense, does the review queue / table collapse, keep current empty-state card?*

---

## 10. Admin Section  `[OPEN]`

Trade history, closed positions, watchlist, record-trade — carried from current tab. *Open: keep as-is or restyle to match new chrome.*

---

## Out of Scope (later ADR)

- Shrinking Home's "Needs review" to a teaser that deep-links into Portfolio (only relevant if Portfolio becomes canonical book view).
- 9-factor / proper FF-AQR factor work (lives in Risk-tab backlog).

---

## Decision Log

- 2026-06-17 — Scope = full redesign (not additive). Spine = B + A's full-width treemap. Review cards reuse Home's `decision_card` at identical depth (option A: reuse on both surfaces). Engine confirmed shared (`grade_position`).
