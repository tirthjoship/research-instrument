# Cockpit Redesign — Design Spec (Project A1)

**Date:** 2026-06-12
**Status:** DRAFT — brainstormed, awaiting user validation before writing-plans.
**Supersedes (UX layer only):** the v2 6-tab dashboard shipped 2026-06-12 (PRs #46/#47).
Domain/ and application/ layers are NOT touched by this work.

---

## Why

The v2 dashboard reshuffled tabs but did not redesign the experience. Investigation of
the running app (6 screenshots, 2026-06-12) found six incoherent mini-apps with four
different visual languages (text-walls on Home, clean charts on Risk, SimplyWallSt cards
on Stock Analysis, tables+forms on My Portfolio), several dead/empty sections, and
legacy falsified-era artifacts still leaking through (a `39.3` score gauge, divergence
tables, a penny-stock default). The user is dissatisfied with both the product (UX
incoherence) and how it is built (bolt-on tabs over years), and confirmed they are linked.

A second, deeper gap surfaced: the tool is **all defense**. It risk-checks and fit-checks
stocks the user already names; it never answers *"what should I even be looking at next
week?"* The user opens it and has no idea which names to research.

## Decisions locked in this brainstorm

1. **Two audiences, two surfaces.** A fast family cockpit (weekly triage) and a separate
   recruiter-facing showcase (the falsification/rigor story) want opposite things and must
   not share pixels. They are split.
2. **Scope = greenfield the cockpit first** (the weekly-value surface), on top of an
   untouched hexagonal core. The showcase is a later pass (A2). The alpha re-open is a
   separate research project (B). See *Out of scope*.
3. **Cockpit shape = single-scroll, strict priority order**, with stock detail as a drawer.
   One consistent card primitive. This directly kills the "6 mini-apps" problem.
4. **Honest discovery** ("what to look into next") is built by *splitting two things the
   current screen fuses*: factual rank (always shown) vs tradeable-edge verdict (stays
   abstaining, shown inline). Framed **diversification-first**.

---

## Surfaces

| Surface | Audience | This spec? |
|---------|----------|-----------|
| **Cockpit** (default) | Family, weekly | YES — Project A1 |
| **Stock detail** (drawer off the cockpit) | Family, ad-hoc | YES — Project A1 |
| **Showcase** (falsification/methodology/Trust, relocated intact) | Recruiter, once | NO — deferred A2 |

## The single-scroll cockpit (strict priority order)

A user opens it on a Saturday and reads top-to-bottom; the order is the ritual.

### 1. Book danger (top strip)
One compact strip, red only when real:
- Concentration / hidden macro bet (e.g. "64% one macro bet · SPY β 1.37").
- Discipline status (breaches this week, gate countdown to mid-July 2026).
Tap → Risk drill-down (the existing beta-bars + systematic-share donut, relocated as a
detail view, not a top-level tab).
Data: `macro_beta_use_case`, `brief.py`, `discipline_use_case`.

### 2. Your calls (this week + log)
This week's per-holding REDUCE/TRIM/HOLD with the one-line why, as a consistent card list.
A single **[confirm all]** action logs the week's calls to the ADR-048 discipline forward
gate. **This replaces the My Portfolio forms/sliders entirely** — one clean log step, no
per-ticker form sprawl.
Data: `brief.py` (verdicts), `discipline_use_case` (the log write).
Note: the dashboard gains exactly ONE write action (the log). Everything else is read-only.

### 3. Look into next (honest discovery feed)
The new capability. **Diversification-first framing.** Each row leads with the book-gap and
uses factual rank as the tiebreak:

> **KO** — Reduces your 64% macro bet · also screens cheap + quality

**Honesty model (the crux):** the engine separates two computations the current screen
wrongly fuses —
- **Factual rank** — where a name sits *today* on valuation/quality/health percentiles vs
  the universe. Pure arithmetic on present facts, zero prediction. **Always computable, so
  top-N always shows.**
- **Tradeable-edge verdict** — the pre-registered IC gate ("is there an exploitable edge?").
  **Stays abstaining and is shown *as* the abstention, inside the feed:** *"The engine
  claims no predictive edge (screen abstains). These are research starting points, not
  buys."*

Two lenses, layered (diversification primary):
- **Would diversify you** — names with low correlation to the user's dominant macro factor
  (from the risk engine). Honest by construction — about the user's concentration, not a
  forecast. PRIMARY sort.
- **Screens well now** — top factual composite (value + quality + health). Secondary/tiebreak.

**Prerequisite fix:** the screen universe is stale (delisted SIVB / PXD / SPLK / WBA, plus
`.TO` artifacts leaking in). Clean it so rankings are real. (This is why discovery feels
dead today — the screen abstains AND the universe is rotten.)

Data: `evidence_screen_use_case` (factual rank), `macro_beta_use_case` +
`correlation_analyzer` (diversification lens). One small new application query: correlation
of candidate names to the user's dominant factor (composes existing pieces — no new domain).

### 4. Lookup (bottom)
Search / paste a ticker (or a list, reusing the v2 upload path) → opens the stock drawer.
Data: `fit_use_case`, `batch_fit_use_case`.

## Stock detail drawer
Opens on any cockpit row click or a lookup. Contains: portfolio-fit verdict + evidence grade
+ evidence snowflake + the honest valuation/quality/health facts.
**Legacy cruft DELETED** (all falsified-era artifacts): the `39.3` score gauge, the
divergence tables, the penny-stock (`Sundial`) default. These contradict RESEARCH_ONLY and
must not survive the rebuild.

---

## Architecture (the "how it's built" fix)

- New package `adapters/visualization/cockpit/`: one assembler (`cockpit.py`) + one
  section-renderer per block (`_danger.py`, `_calls.py`, `_discover.py`, `_lookup.py`) +
  `stock_detail.py` (the drawer).
- **One design system.** Collapse the heterogeneous styling into a single token set, one
  card primitive, consistent typography. This is the concrete fix for the four-visual-
  languages problem. Reuse the v2 `components/{glossary,snowflake,scorecard}.py` where they
  already fit; consolidate `styles.py` to one source of truth.
- **Domain/ + application/ untouched.** The cockpit only *reads* existing use cases (listed
  per-section above). The one addition is an application-level query for the diversification
  lens — it composes `correlation_analyzer` + `macro_beta_use_case` outputs; no new domain
  types.
- **Retire vs relocate the old render code:**
  - Retired (render replaced; compute stays in core): `tabs/weekly_brief.py`,
    `tabs/research_candidates.py`, `tabs/positions.py`, `tabs/stock_analysis.py`.
  - Relocated as drill-downs: Risk charts → danger drill-down; full positions table → a
    drawer.
  - Relocated wholesale to the deferred Showcase (A2): `tabs/trust.py` + the methodology /
    falsification content (kept intact, just moved under a Showcase entry; until A2 ships it
    stays reachable as-is).
- New router: Cockpit (default) + Stock-detail drawer + a Showcase entry pointing at the
  existing Trust content until A2.

## Data flow
All reads compose existing, tested use cases. No new look-ahead surface, no new predictor.
The single write is the discipline log (`confirm all`). The diversification query and the
factual-rank read are both point-in-time over already-fetched data.

## Degraded / error states
- Screen abstains (current production reality) → STILL show the factual top-N (that is the
  entire point — discovery must not go dark on abstention). The abstention banner shows.
- No holdings file → cockpit shows an "add your book" empty state (not a crash).
- No brief → graceful empty danger/calls sections; discovery + lookup still work.
- Stale/missing screen → discovery falls back to the diversification lens (always computable
  from the book).

## Testing
- Headless fake-`st` renderer tests for each cockpit section (the existing pattern).
- Fixture-tested application diversification query.
- RESEARCH_ONLY + FORBIDDEN_WORDS guards (scoped) on ALL new cockpit copy — especially the
  "Look into next" feed, where the honesty caveat must be present and the recommendation
  vocabulary absent.
- Regression: domain/application suites unchanged and green.

---

## Out of scope (separate specs)

- **A2 — Showcase surface.** The recruiter-facing falsification/methodology/Trust narrative,
  designed as its own coherent surface. Deferred. Until then, Trust content stays reachable
  as-is, just relocated.
- **Project B — Alpha re-open.** The user wants the falsification gates kept open to keep
  testing for alpha (news/sentiment → next-week moves, cross-stock lead-lag). This is a
  research project, not a dashboard feature. **It must go through the pre-registration bar:**
  re-running the already-falsified divergence thesis (ADR-044, clean 430-ticker universe, IC
  ≈ 0.004, CI spans zero) hoping for a greener result is p-hacking. Honest re-entry requires
  a genuinely NEW hypothesis (e.g. event-study around discrete news shocks ≠ continuous
  divergence-IC; or cross-stock lead-lag / supply-chain propagation, touched by ADR-029 but
  never falsification-gated) OR a named, specific flaw in ADR-044's method — pre-registered
  before looking. Recommend a `ds-methodology-review` pass before any build. Its own spec.

## Open questions for validation
1. Does the single write action (confirm-and-log) belong in the cockpit, or should logging
   stay CLI/cron-only and the cockpit stay 100% read-only?
2. Diversification lens: correlate candidates to the single dominant factor, or to the full
   macro-factor set (SPY/TLT/UUP/USO/XLE)? Affects the "would diversify you" math.
3. How many discovery rows is "useful, not a buy list"? (Proposal: 3–5.)
4. Showcase relocation: does Trust stay reachable from the cockpit during A1, or go dark
   until A2 ships?
