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

## 3a. Cross-Cutting Styling Consistency  `[LOCKED]`

Every component on this tab matches the other redesigned tabs (Home/Screener/Risk) for intuitiveness:
- **Binned color coding** — discrete bins (NOT a smooth gradient), same palette as other tabs. Treemap heat capped at ±25% realized P&L.
- **ⓘ cloud tooltips** — reuse existing `tooltip()` + `glossary.py` (`adapters/visualization/components/`); same `ⓘ` badge + hover cloud. Applied where a term needs explaining: Concentration, Needs review, treemap color-scale legend, Portfolio-vs-SPY. One glossary as single source of truth — add any new terms there.
- **Chrome** — Fraunces `ri-sec` section headers, verdict pills (`_VERDICT_COLORS`), IBM Plex Mono numerics, `ri-*` CSS tokens.

## 4. Honesty Guards  `[LOCKED]`

Carried, non-negotiable:
- Treemap color = **realized** P&L only, never predicted return (ref memory `attributed-not-predicted`).
- SPY comparison = attributed actual series, no projection.
- **DATA-GAP, never fabricate**: if `brief_summary.json` lacks a holding → DATA-GAP verdict/why; RAG shown only when live-fetched on expand.
- Verdict framed as a discipline *review prompt*, not a forecast or buy/sell instruction.

---

## 5. Data Additions  `[LOCKED — approach; exact code at plan time]`

- **`sector` per holding** — source `yfinance info["sector"]` (already fetched in watchlist via `fetch_ticker_info`), cached. Enrich **adapter-side** (do NOT pollute the pure `Holding` domain model — attach via a view/DTO in the visualization adapter or data_loader). Missing → "Unknown" (DATA-GAP).
- **Top-5 weight** (concentration metric) — sum of the 5 largest holding weights by market value. (HHI considered, deferred — top-5 reads more intuitively for a non-expert.)
- **SPY return series** — from existing price fetch; simple time-weighted per window (§8).
- **Live RAG/case on expand** — reuse Home's `_fetch_card()`; **lazy, only on click**, cached per ticker (never fetch all 60 upfront).

---

## 6. Treemap Spec  `[LOCKED]`

Full-width "Your book at a glance" — the showpiece + concentration read.

**Layout — squarified treemap (custom, NOT flexbox, NOT plotly).**
- Two-level squarified packing: level 1 = sectors into the canvas, level 2 = holdings into each sector rectangle. Squarified keeps every tile near-square → a dominant sector renders as one big block (never thin slivers), and the layout rebalances as dominance shifts (verified in mock across balanced / Tech-70%-dominant / one-mega-position scenarios).
- **Rectangles computed in Python** from holding weights and emitted as absolute-positioned divs — no client-side layout JS (clean for Streamlit). Rejected `plotly go.Treemap` (theming + hover-card integration cost) and flexbox (slivers under dominance).

**Encoding.**
- Size = weight (always positive, sums to 100%). Cannot size by gains (negatives have no area + would hide concentration).
- Color = the active **lens** (see §6a). Discrete **bins**, capped ±25% so an outlier (+75% NVDA) can't wash out the scale.

**Labels / overflow.**
- Ticker label shown only above a tile-area threshold (mock used ~area>1300px²); larger tiles (~>4500px²) also show the lens value. Below threshold → no label, hover-only.
- Every tile `overflow:hidden` + text-ellipsis + `white-space:nowrap` → a ticker can NEVER spill its tile.

**Sector handling.**
- No-sector holding (yfinance returns none) → grouped under an **"Unknown"** sector block (DATA-GAP, honest, never guessed).
- Sector header shows sector name + combined weight % (= sector concentration).

**Demo-only (NOT in build):** the mock's scenario dropdown was a demonstration aid for dominant-sector behavior; the real tab renders live holdings only.

## 6a. Treemap Interaction Model  `[LOCKED]`

- **3-lens color toggle** (`st.radio`-style pills, recolor server-side on rerun): **P&L (lifetime)** · **Today** (intraday %) · **Verdict** (REDUCE/TRIM red shades, REVIEW amber, HOLD/ADD_OK green). Each lens has an ⓘ cloud explaining it; legend updates per lens.
- **Hover** (any tile size) → peek cloud: weight, lifetime P&L, today %, verdict. Exact numbers always one hover away (covers approximate-area concern).
- **Click** (any tile size) → opens the **shared detail panel** below the treemap = the SAME `decision_card` expanded depth (§3): meaning, metrics incl. today, 5 live RAG signals, rubric, interlinks. Detail never renders inside the tile → a 0.3% tile expands exactly as well as a 12% one → scales to 60+. RAG/case fetched **live + lazy** on click (not upfront for all holdings).
- Clicking a treemap tile and expanding a Needs-review card land in the **same** detail component (one detail surface, two entry points).

---

## 7. Healthy Holdings Table  `[LOCKED]`

Dense ledger for non-flagged holdings (verdict ∈ {HOLD, ADD_OK}). Heading shows count ("Healthy holdings — N of total").

**Columns — Lean default + "⊕ more columns" toggle.**
- Lean (default): Ticker · Sector · Weight (inline bar + %) · Value · Lifetime P&L % · Today % · Verdict pill.
- Toggle "⊕ more columns" reveals: **Div Yield · Beta · Cost basis** (the fundamentals from the web-scan gap analysis). Yield/Beta from yfinance `info`; **DATA-GAP "—" when provider returns none — never faked.** ⓘ glossary clouds on Beta and Div-Yield headers.

**Behavior.**
- **Sort:** click any header to sort; toggle asc/desc; arrow indicator. Default sort = Weight desc.
- **Filter:** chips All / Gainers / Losers + ticker search box. Page size 10, pager.
- **Row click → opens the shared detail panel** (same `decision_card` depth as a treemap tile / review card — one detail surface, three entry points: review card, treemap tile, table row).
- Verdict pill rendered inline (same `_VERDICT_COLORS`).

**Build note:** sort/filter/paging via Streamlit-native state (rerun); table emitted as styled HTML (consistent with current `positions.py` table approach) or `st.dataframe` with column config — decide at plan time, but row-click→detail needs the HTML/`st.button` path, not raw `st.dataframe`.

---

## 8. Portfolio vs SPY Chart  `[LOCKED]`

Full-width "Portfolio vs SPY" — closes the CLAUDE.md-mandated benchmark gap.

- **Treatment:** filled-area portfolio line + dashed SPY benchmark line + **alpha callout** ("▲ +X% vs SPY") in the section header.
- **Window toggle pills:** YTD · All (since first buy) · 1Y — recolor/redraw + recompute alpha + window label per pill (consistent with the treemap's lens-toggle interaction model).
- **Return basis:** simple time-weighted return for **v1**. **Money-weighted** (handles mid-window buys/sells correctly) is a flagged later upgrade — ⓘ cloud states this.
- **Honesty:** lines + alpha computed from **actual** trade history & prices, no projection. Any window segment predating the first buy → **DATA-GAP, never back-filled**.
- **Build:** reuse/extend `charts.py` (transparent `apply_dossier_template`); window state via Streamlit rerun.

---

## 9. Empty / Small-Portfolio States  `[LOCKED]`

- **0 holdings:** hide hero/treemap/table/SPY; show empty card ("No positions yet — record your first trade") + Record-a-trade form. (Carries current behavior.)
- **Holdings exist, none flagged:** "Needs review" renders a calm green ✓ "Nothing needs review" (all HOLD) — never an empty/broken section. Treemap/table/SPY render normally.
- **Small book (≤ ~5 holdings):** treemap renders **flat (C1)** — sector grouping switches off below the threshold; tiles still sized/colored/hover/click via the same component. (Rejected C2 skip-treemap — extra code path, loses centerpiece consistency.)
- **brief_summary.json missing a holding:** verdict/why = DATA-GAP (per §4).

---

## 10. Admin Section  `[LOCKED]`

Trade history & outcomes · Closed positions (P&L chart + table) · Watchlist · Record a trade — **carried from current `positions.py`**, kept as collapsed expanders at the bottom. Restyle to ri-chrome (section headers, pills, tokens); **no behavior change**. Watchlist keeps its live PE/PEG/mcap fetch.

---

## Out of Scope (later ADR)

- Shrinking Home's "Needs review" to a teaser that deep-links into Portfolio (only relevant if Portfolio becomes canonical book view).
- 9-factor / proper FF-AQR factor work (lives in Risk-tab backlog).

---

## Decision Log

- 2026-06-17 — Scope = full redesign (not additive). Spine = B + A's full-width treemap. Review cards reuse Home's `decision_card` at identical depth (option A: reuse on both surfaces). Engine confirmed shared (`grade_position`).
- 2026-06-17 — §3a styling consistency locked (binned color, ⓘ glossary clouds, ri-chrome).
- 2026-06-17 — §6 + §6a locked: squarified custom treemap (Python-computed rects), size=weight / color=lens, capped ±25% bins, label-on-big + hover-small + overflow-clip, Unknown-sector fallback. 3-lens toggle (P&L/Today/Verdict), hover peek, click → shared `decision_card` detail panel (lazy live RAG). Rejected plotly + flexbox. Scenario dropdown was mock-only.
- 2026-06-17 — §7 locked: healthy table = Lean default cols + "⊕ more columns" toggle (yield/beta/cost, DATA-GAP when absent). Sort/filter/search/page; row-click → shared detail panel (3rd entry point).
- 2026-06-17 — §8 locked: Portfolio-vs-SPY = filled-area + SPY line + alpha callout + window toggle (YTD/All/1Y). Simple-return v1; money-weighted deferred. DATA-GAP before first buy.
- 2026-06-17 — §5 locked (approach): sector via yfinance adapter-side enrichment (Unknown fallback), top-5 weight concentration, simple SPY series, lazy per-click RAG. §9 locked: 0-state / calm-no-flag / flat-treemap-small-book (C1). §10 locked: admin carried over, restyled, collapsed. **All sections locked — ready for full assembled mockup + spec sign-off.**
