# Dashboard v2 — Premium Light Terminal + 6-Tab IA

**Date:** 2026-06-12
**Status:** Approved (user, 2026-06-12 — "approve B")
**Builds on:** dashboard realignment (PR #39), UX pass (PR #42), fit verdict (ADR-054,
PR #40), yfinance fix (PR #44)
**Driven by:** user round-2 feedback (7 screenshots, 2026-06-11) + SimplyWallSt MSFT
page as the quality bar. Decision: Streamlit pushed hard, LIGHT theme (user choice).

## Purpose

Close the gap between the project's substance (honest, falsification-backed engine)
and its presentation (pale admin tool). SWST sells polish on descriptive data; we sell
polish on **verified honesty** — the design must make abstention, verdicts, and
receipts feel premium, not apologetic.

## Hard constraints (unchanged)

- RESEARCH_ONLY everywhere. The FORBIDDEN_WORDS domain invariant (`domain/fit.py`)
  applies to ALL new surfaces (scoreboard rows, snowflake labels, hero banners) —
  extend the existing source-scan test pattern to every new renderer.
- Dashboard = visualization ADAPTER. New computation goes in application/ (batch fit)
  or domain/ (nothing new expected); tabs render only. Stock Analysis + the new
  Screener upload are the only user-initiated live-network surfaces.
- Existing 1593 tests stay green; new tests follow tab conventions (render-no-raise +
  pure-helper units + vocabulary scans).

## §1 Design language — "Premium Light Terminal"

Single source: upgrade `adapters/visualization/components/styles.py` tokens.

- Base: warm white `#FAFAF8` page, white `#FFFFFF` cards, ink `#1A1D27` text,
  muted `#5C6370`.
- Accent: deep cobalt `#1D4ED8` (replaces `#2563EB`; one accent, used sparingly).
- Semantic (verdicts ONLY — never decoration): green `#15803D`, amber `#B45309`,
  red `#B91C1C`.
- Cards: 12px radius, layered shadow (`0 1px 2px rgba(16,24,40,.06), 0 4px 12px
  rgba(16,24,40,.04)`), **hover elevation + 1px accent border-glow** on every card
  (CSS transition ~150ms). The existing `.ws-card` class is upgraded in place so all
  tabs inherit.
- Type scale: 28px page title / 18px section / 14px body / 12px caption; tabular
  numerals (`font-variant-numeric: tabular-nums`) on all figures.
- Section headers: numbered chip pattern (`① Verdict`) — a small `.section-chip`
  CSS class (cobalt circle, white numeral) + title, SWST-style.
- Tooltips: every metric/term gets a hover definition. Mechanism: `st.metric(help=)`
  where native; elsewhere a `.tip` CSS class (dotted underline, `::after` hover
  bubble) fed from ONE shared dict `GLOSSARY` in a new
  `components/glossary.py` (definitions copied from the Methodology `_BODY` table —
  that module becomes the single source; README stays in sync as today).

## §2 IA — 7 tabs → 6

| v2 tab | Was | Change |
|---|---|---|
| Home | Weekly Brief | verdict-first landing (§3) |
| Screener | Research Candidates | + upload scoreboard (§4), screen history |
| Risk | Risk | reskin + layout only |
| My Portfolio | My Portfolio | scorecard treatment, reskin |
| Stock Analysis | Stock Analysis | section nav + snowflake (§5) |
| Trust | Falsification Lab + Methodology | merged trophy wall (§6) |

`methodology.py` tab is deleted from the router; its 4 rules + glossary move to
Trust; definitions feed §1 tooltips. `falsification_lab.py` becomes `trust.py`
(rename with git mv; tests follow).

## §3 Home — verdict-first landing

Target: half a screen before any scrolling decision.

1. **Book Health hero** (full-width card): holdings count + week regime (from brief
   summary — it carries NO dollar value; do not invent one or add IO), an inline
   systematic-share mini-gauge (Plotly indicator, 120px), and the headline: "N things
   need attention this week" (N = REDUCE+TRIM count). Background: subtle
   cobalt-tinted gradient band — the one decorative moment on the page.
2. **Attention row**: up to 5 cards (red/amber left border) — ticker, verdict pill,
   unrealized %, one-line why. Remainder in "view all" expander (existing dataframe).
3. **Week strip**: 3 small cards — screen result one-liner ("512 screened · 0 passed
   · abstained"), adherence streak ("N weekly reviews logged"), gate countdown
   ("forward gate resolves ~mid-July").
4. Everything else (full grade table, adherence detail, markdown brief) stays in
   existing expanders below the fold.

Data: all from `brief_summary.json` + existing loaders — no new IO.

## §4 Screener — upload scoreboard + never-empty

1. **Weekly screen section** (existing abstention card + candidates path, reskinned).
2. **Screen history strip**: parse ALL `data/reports/screen_*.json` (excl. `screen_ic_`)
   → small table/sparkline: date · universe · candidates · abstained. Shows the
   system alive even when this week is empty. New loader `load_screen_history()` in
   `data_loader.py` (same defensive pattern as `load_latest_screen`).
3. **"Check your own list" scoreboard** (the new feature):
   - Input: `st.text_area` (comma/newline tickers) AND `st.file_uploader` (CSV —
     first column or a `Symbol`/`Ticker` column; reuse holdings_reader's tolerant
     header matching idea but implement standalone simple parser in application).
   - Engine: new `application/batch_fit_use_case.py` —
     `batch_fit(tickers, ...) -> list[BatchFitRow]`. Per ticker, reuse
     `gather_and_assess` + `default_beta_fn` (the ADR-054 machinery, unchanged).
     `BatchFitRow` = frozen dataclass: ticker, FitVerdict, fetch_ok. Sequential with
     `st.progress` (1 live beta fetch per name — cap input at 25 tickers per run,
     loudly stated). Per-ticker failure → row with DATA_GAP verdict, never aborts
     the batch. Results cached in session_state keyed by the sorted ticker tuple.
   - Output: ranked scorecard rows (new `components/scorecard.py` renderer):
     rank · ticker · evidence pill (grade colors) · composite mini-bar · fit-flag
     icons (⚠ beta, ◔ concentration, ◆ trend — CSS glyphs with `.tip` hover showing
     the flag message) · one-line summary. Sort: STRONG>MODERATE>WEAK>UNKNOWN, then
     composite rank desc. Footer caption: "Evidence + fit vs your book — this engine
     does not make buy/sell calls (see Trust)."
   - Vocabulary guard test on the scorecard renderer source.

## §5 Stock Analysis — perfection pass

Keep all 8 sections + fit card. Add:
1. **Section chip nav** at top: ① Verdict ② Fit ③ Valuation ④ Growth ⑤ Performance
   ⑥ Health ⑦ Ownership ⑧ Sentiment ⑨ Supply chain — anchor links
   (`st.markdown('<a href="#...">')` against Streamlit's auto header anchors).
2. **Evidence snowflake** in the verdict section: Plotly `Scatterpolar`, 5 axes —
   Valuation, Quality, Health, Trend, Book-fit — each a 0–100 DESCRIPTIVE percentile
   already computed (screen factor percentiles; trend_health scaled; book-fit =
   100 − penalty per fit WARNING/CAUTION). Filled cobalt, labeled "Evidence
   snowflake — factual percentiles, not a prediction" (this is NOT the falsified
   conviction radar; axes are present-tense facts; caption says so). New
   `components/snowflake.py` builder, pure function fig-from-dict, unit-tested.
3. **52-week range bar** in the header (existing `price_range_bar` component —
   verify it's wired; wire if not).
4. Peer-context one-liners where data exists in `AnalysisResult` (e.g. "PE {x} vs
   sector {y}") — render only when both numbers present; no new fetches.

## §6 Trust — trophy wall

1. Hero: "Seven ideas. Seven honest verdicts." + one-line creed.
2. **Trophy grid**: `st.columns(3)` cards per hypothesis — big verdict pill, the
   question, one-line what-it-means; click = expander with test description + ADR
   link + (for Unit B) the live-report verdict row. Reuses `_SCOREBOARD` data +
   `_unit_b_row` unchanged.
3. **The 4 rules** as icon cards (pre-registration ⚖, point-in-time ⏱, costs 💰→
   no, use CSS glyphs not emoji — match formatters' no-emoji convention: use the
   section-chip numbering instead).
4. Gate strip + exhibits expander: keep as is.
5. Glossary reference table at bottom (source of truth moves to
   `components/glossary.py`; this table renders FROM it; Methodology tab deleted).

## §7 Engineering shape

New: `components/glossary.py` (GLOSSARY dict + tip helper), `components/snowflake.py`,
`components/scorecard.py`, `application/batch_fit_use_case.py`,
`tests/test_batch_fit_use_case.py`, `tests/test_snowflake.py`,
`tests/test_scorecard.py`. Renamed: `tabs/falsification_lab.py` → `tabs/trust.py`,
`tabs/weekly_brief.py` content rebuilt in place (keep filename — loaders/tests
anchor to it). Deleted: `tabs/methodology.py` (+ router entry; its test retargets
Trust's glossary render). Router: 6 labels.

Out of scope: dark theme, React components, new data sources, any predictive
computation, correlation fit input (stays parked in HYPOTHESIS_BACKLOG).

## §8 Definition of done

- All 6 tabs render against today's real artifacts without warnings looking broken.
- Upload scoreboard: paste "NVDA, AAPL, KO" → 3 ranked rows with pills + hover flags.
- Vocabulary-guard tests cover scorecard, snowflake, home hero sources.
- Suite green; pre-commit clean; live click-through on :8501 before PR.
