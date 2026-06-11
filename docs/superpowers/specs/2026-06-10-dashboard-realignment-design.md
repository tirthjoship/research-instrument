# Dashboard Realignment — "Three-Pillar Cockpit" + Skill Routing Wiring

**Date:** 2026-06-10
**Status:** Approved (user, 2026-06-10)
**Builds on:** ADR-052 (CRO direction), strategic wrap spec
(`2026-06-10-strategic-wrap-plan-design.md` §5.5 plain-language, §7 timeline),
ADR-045→051 (discipline/forward gate), Unit A (macro-beta scrubber)

## Purpose

The Streamlit dashboard still presents prediction-era machinery (conviction
scoring, model confidence, opportunity cards) that six pre-registered
falsifications killed — it OVERSTATES capability. Realign it to what the project
honestly does: risk exposure, discipline flags, factual research, and the
falsification record itself. Audience: the user's Saturday decision ritual
first, employers/reviewers second — one layout serves both.

**Build window:** AFTER the Unit B full-window verdict lands (scoreboard content
+ possible PASS paper-trade panel depend on it) and after the hardening sprint
fixes the shared-venv drift (plotly/streamlit/feedparser/networkx missing — the
dashboard test suite cannot run until then). Slot: Jun 17–29 refinement.

## §1 Layout + routing

`adapters/visualization/dashboard.py`: 7 tabs → 7 NEW tabs (different seven),
decision-flow ordered:

**Weekly Brief · Research Candidates · Risk · My Portfolio · Stock Analysis ·
Falsification Lab · Methodology**

Decision loop: Brief (act on holdings) → Candidates (what to research) → Stock
Analysis (research it) → Portfolio (track it). Lazy per-tab imports stay
(current pattern). Title and global CSS (`components/styles.py`, SWST design
language per `docs/design-references/REFERENCE_NOTES.md`) unchanged.

**Core data rule (all tabs):** the dashboard RENDERS artifacts written by CLI
jobs; it never computes domain logic and never makes network calls. (One
existing exception: Stock Analysis calls `analyze_ticker` live on demand —
retained as-is, it is user-initiated research, not a scheduled surface.)

## §2 Tabs

### 1. Weekly Brief (home)

Expand the 26-line stub into the cockpit:
- Verdict banner: book-level state + date of last Saturday run.
- Discipline flag table grouped REDUCE → TRIM → REVIEW → HOLD → ADD_OK, one
  plain-English reason per row.
- Abstention shown honestly ("evidence screen: n=0 buys this week").
- Adherence tracker placeholder section (fills when Unit C lands).
- Staleness warning if the brief artifact is >8 days old (fail-loud, wrap spec §5).
- Data: **new structured artifact** `data/personal/brief_summary.json` (gitignored,
  same dir as the existing `weekly_brief.md`): discipline flags by grade with
  reasons, run date, macro-beta block (net beta, factor betas, variance split,
  flags), screen counts/abstention. BUILD ITEM in this spec's plan: the
  `weekly-brief` CLI writes this JSON alongside the markdown (validated: today it
  writes markdown ONLY — `application/cli.py` `weekly_brief`, out default
  `data/personal/weekly_brief.md`). The tab renders the JSON; the full markdown
  stays available in an expander via the existing `load_weekly_brief`.

### 2. Research Candidates (new)

The honest replacement for "recommend me stocks":
- Top: evidence-screen verdict — qualifying names if the bar is met, else a
  proud abstention banner ("no name met the evidence bar — the tool working,
  not failing").
- Main: **Top 15 by factual composite** (valuation + quality + health,
  descriptive only) regardless of bar — ranked cards: ticker, composite score,
  factor chips, one-line plain-English "why it surfaced," pointer to Stock
  Analysis for the deep dive.
- Permanent header disclaimer: "Ranked by current factual evidence, NOT
  predicted returns — prediction was tested 2006–2024 and falsified (see
  Falsification Lab)."
- Data: `data/reports/screen_<date>.json` — the FULL ranked distribution the
  `screen-candidates` CLI already writes (validated; honesty rule: full
  distribution, never just top-N). The tab loads the most recent file and
  slices the top 15 client-side. The weekly Saturday job gains the
  `screen-candidates` step in the hardening plan. Stale-report warning same
  as Weekly Brief.

### 3. Risk (new)

Unit A macro-beta scrubber promoted from CLI markdown:
- Net-β hero metric; factor exposure bars (SPY/TLT/UUP/XLE dollar betas);
  systematic-vs-idiosyncratic variance donut (the "63% one bet" finding);
  flag cards (SYSTEMATIC_DOMINANT / FACTOR_DOMINANCE / DRIFT) each with a
  plain-English "what this means / what you might do" block.
- Permanent caption: "Heuristic surfacing dials, not validated edges"
  (ADR-052 honesty rail).
- Data: the macro-beta block of `data/personal/brief_summary.json` (validated:
  macro-beta has NO standalone artifact today — it is computed inside the
  weekly-brief use case and embedded in the markdown; the new JSON carries the
  structured numbers).

### 4. My Portfolio

Existing positions tab kept as-is; Watchlist folded in as a collapsible
section (delete `tabs/watchlist.py` after merge). No new features.

### 5. Stock Analysis (kept, reframed)

Free-ticker search + Run Analysis retained (this is the "search new stocks"
ability — it already exists).
- KEEP untouched: Valuation, Growth, Performance, Financial Health, Ownership,
  Supply Chain — six factual sections, SWST design language intact.
- REFRAME `_render_verdict`: descriptive summary card ("what the data shows"),
  no Buy/Sell grade, RESEARCH_ONLY banner. If the radar/snowflake is
  conviction-driven, re-axis to factual dimensions only (Value / Growth /
  Health / Performance / Ownership) or drop it.
- Sentiment section: keep the display, add caption "Descriptive buzz only —
  predictive value falsified (ADR-044)."
- `stock_analyzer.py` survives as the data layer; only conviction-grade
  outputs are reframed.

### 6. Falsification Lab (new)

- Top: verdict scoreboard — 7 rows (6 falsifications + Unit B), columns:
  Hypothesis (plain question, §5.5 style) · How tested · Verdict chip
  (KILL / INCONCLUSIVE / final state) · ADR link. Unit B row reads
  `data/reports/insider_cluster_falsification_2024.json`; PENDING fallback if
  absent.
- Middle: 2–3 exhibits — selected conviction/model-confidence chart builders
  reused with "FALSIFIED — kept as exhibit" banners. No new chart code.
- Bottom: forward-gate progress strip (weeks accrued vs needed, from
  `data/personal/discipline_log.jsonl` — validated, exists) — the one live
  experiment.
- If Unit B verdict = PASS: add a paper-trade log panel (reads
  `insider_paper_log.jsonl`). Only built in that branch.

### 7. Methodology

Replaces How It Works: pre-registration flow (markdown), PIT enforcement
explainer, glossary (CI, slippage, tercile, abnormal return, IC — wrap spec
§5.5 plain-language home). Static content, zero data dependencies.

## §3 Deletions

- `tabs/command_center.py` (~636 lines — conviction opportunity cards, pure
  falsified machinery).
- `tabs/market_pulse.py` (~277 — macro context absorbed by Risk).
- `tabs/model_confidence.py` as a tab (~482 — salvage 2–3 chart builders into
  Lab exhibits first).
- `tabs/watchlist.py` (~153 — merged into My Portfolio).
- Tests for deleted tabs removed/updated in the same commits.
- Net ≈ 1,400+ lines out. Less surface to rot = self-sustainability (wrap §5).

## §4 Error handling

Fail-loud everywhere (wrap spec §5): every artifact read that is missing or
stale renders a visible warning card naming the command to run — never a
silent empty chart. No network calls from scheduled surfaces; only Stock
Analysis fetches on explicit user action.

## §5 Testing

- Per-tab smoke tests (existing pattern: import + `render` callable).
- Unit tests: scoreboard row builder (verdict JSON → rows; PENDING fallback),
  staleness check, candidates-card builder (screen JSON → cards; abstention
  path).
- Precondition: hardening sprint fixes the shared venv so the dashboard suite
  actually runs in CI/`make check`.

## §6 Sequencing

1. Unit B verdict lands (separate plan, in flight).
2. Hardening sprint (separate plan) — venv fix is this spec's hard dependency.
3. This spec → writing-plans → subagent-driven-development (Sonnet build, Opus
   review); `frontend-design` skill for tab layout polish during build.
4. Inside Jun 17–29 refinement window.

## §7 Skill-routing wiring (repo-level, build immediately — not gated on Unit B)

Mirror the `product-experimentation-analytics` pattern:

**Create `docs/SKILL_ROUTING.md`:**
- Phase → skill table projected onto the wrap plan:

| Phase | Gate to enter | Invoke | Model |
|-------|---------------|--------|-------|
| Unit B verdict | report JSON exists | execute LOCKED §2 tree (no judgment); `verification-before-completion` on ADR-053 numbers | Opus |
| Unit C build | Unit B merged | `brainstorming` → `writing-plans` → `subagent-driven-development` | Opus plan / Sonnet build |
| Hardening sprint | Unit C merged | `writing-plans` → `subagent-driven-development`; `systematic-debugging` on any failure | Sonnet |
| Dashboard realign | hardening done (venv fixed) + Unit B verdict | this spec → `writing-plans` → `subagent-driven-development`; `frontend-design` for layouts | Sonnet build / Opus review |
| Docs refinement | build complete | `humanizer` on the write-up; §5.5 plain-language test | Sonnet |
| Ship/wrap | review clean | `requesting-code-review` → `finishing-a-development-branch` → `caveman-commit` | Opus review |
| Maintenance (post-Jun 29) | — | read-only; `systematic-debugging` ONLY on breakage; ~1 hr/quarter budget | Sonnet |

- Always-on triggers table: `context7` (yfinance/streamlit/click docs),
  `smart-explore` (structure), `mem-search` ("solved before?"),
  `verification-before-completion` (any "done" claim),
  `ds-methodology-review` (methodology doubts), `grill-me` (understanding).
- Hard constraints section mirroring CLAUDE.md non-negotiables + wrap-specific:
  NO new signal hunting (ADR-052), NO auto-retraining loops (wrap §5), Unit D
  stays parked, PIT/LookAheadBiasError, no domain framework imports, locked
  pre-registered gates, feature branches only, fixtures-only tests, never
  `--no-verify`.

**Edit `CLAUDE.md`:** one pointer line in the Phase Status section →
`docs/SKILL_ROUTING.md`.

**Create `.claude/settings.json`:** copy the PreToolUse Bash hook from
`product-experimentation-analytics` (denies `--no-verify`, `push --force`,
`push -f`) verbatim.

## Out of scope

- Any new predictive feature or buy/sell language (ADR-052).
- New chart libraries / framework moves (Streamlit + Plotly stay).
- Mobile layout, auth, deployment.
- Rebuilding deleted tabs' functionality elsewhere.
