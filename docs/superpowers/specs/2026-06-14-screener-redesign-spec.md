# Screener (Research Candidates) Redesign — Design Spec

**Date:** 2026-06-14
**Branch:** `feat/dashboard-legibility-redesign`
**Status:** DESIGN LOCKED (brainstorm + grill + visual-companion pass, user-approved)
**Canonical mockup:** `.superpowers/brainstorm/screener-FINAL-v2.html` (open in a browser; every UI
claim below pins to an element in it)
**Supersedes/extends:** `docs/superpowers/specs/2026-06-13-screener-legibility-design.md`

---

## 1. Problem & North Star

The Research Candidates tab (`adapters/visualization/tabs/research_candidates.py`, 443 lines) is the
"screener." It currently renders a wall of ~10 bespoke rich cards over up to 304 cleared names, in an
inline-hex visual language divorced from the redesigned Home tab. A non-expert cannot tell which name
matters, what the metrics mean, or how much to trust them — the same legibility failure that produced
**0 trades** on Home (memory `dashboard-trust-legibility`).

**North star:** non-expert **legibility + earned trust**, visually consistent with the Home redesign.
The screener describes **current evidence standing**, never predicts — consistent with the project's
falsified-return-forecast thesis (Trust tab) and the honesty invariants in `domain/fit.py`.

This spec is **one combined build** (no phased Track-1/Track-2 split in the product). It includes UI
changes **and** scoring/factor changes; the scoring changes therefore carry the backtest-gate,
look-ahead, and methodology guardrails (§9). Internally the build is ordered so a factor is computed
before any UI renders its row (§10).

---

## 2. Non-Goals & Honesty Invariants (hard stops)

- **No prediction / no forecast.** No surface may present any factor or composite as a predicted return.
  Timeframe line + tiles must say "current evidence, not a forecast" (mockup: tile 2, disclosure box).
- **Attributed, never adopted** (memory `attributed-not-predicted`). The Google-AI read is a companion
  beside the score; it is **never** an input to the score. No LLM output mutates a factor or composite.
- **FORBIDDEN_WORDS** (`domain/fit.py:13-21`: buy, sell, winner, conviction, predict, alpha, outperform)
  — source-scanned per new module; rendered output asserted clean in tests.
- **No look-ahead bias.** Any new factor (Low-vol) and any factor recomputation for arbitrary tickers
  (§7) must use only point-in-time / trailing data (`domain/services.validate_point_in_time_access`).
- **DATA-GAP is never faked** — missing data renders as an explicit gap, never a fabricated number.
- **Do not reset** `scan-history.tsv` (memory `never-reset-scan-history`).

---

## 3. Validated Codebase Facts (anchors — verified this session)

| Fact | Anchor |
|------|--------|
| Tab entry | `adapters/visualization/dashboard.py:38-43` (tab1 → `research_candidates.render`) |
| Live factors = momentum, revision, quality, value (all 4 populated) | `domain/factor_scores.py:26` `FACTOR_KEYS`; live `screen_2026-06-14.json` 100/99/100/100% coverage |
| Composite = equal-weight mean of z-scores, denom always 4, missing=0 | `domain/factor_scores.py:39-45` |
| Momentum = trailing 12-1 month return | `domain/trend_rules.py:50-59` `momentum_12_1` |
| **Revision is mislabeled** — computes `(target_high−target_low)/|target_low|` (target *spread*), NOT estimate drift; yfinance gives one snapshot only | `domain/factor_scores.py:29-36`; `application/cli.py:2534-2546`; `adapters/.../yfinance_adapter.py:203-213` |
| Quality = ROE or profit_margins | `application/cli.py:2554-2556` |
| Value = inverse trailing P/E | `application/cli.py:2558-2561` |
| Percentile = rank of factor z vs the **trend-eligible cohort** (304 this week), not 512, not sector | `application/evidence_screen_use_case.py:119-141` |
| Grades = STRONG (≥0.80) / MODERATE (0.50–0.80) / WEAK (<0.50) / UNKNOWN | `domain/fit.py:47-65` `composite_rank` + `_grade` |
| `as_of = date.today()`, **zero forward projection** anywhere in screen path | `application/cli.py:2613-2615` (grep forecast/predict/next_week/horizon → none) |
| IC backtest infra exists; momentum-only by necessity (no PIT fundamentals) | `application/screen_ic_panels.py`, `application/ic_analysis.py`, `application/screen_backtest_use_case.py`; CLI `backtest-screen` `application/cli.py:2702` |
| **Momentum has no proven edge**: mean IC 0.011, 95% CI −0.029…+0.043, INCONCLUSIVE | `data/reports/screen_ic_2026-06-08.json` |
| GeminiNarratorAdapter SHIPPED; summarizes facts+news → ≤5 in-favor/≤5 to-watch; **no access to scores**; fails safe to data_gap; forbidden-words negated in prompt | `adapters/ml/gemini_narrator.py:14-19,44-58` |
| `batch_fit` returns `BatchFitRow{ticker, verdict: FitVerdict, fetch_ok}`; `FitVerdict` has only `evidence_grade, fit_flags, summary, label` — **no per-factor scores** | `application/batch_fit_use_case.py:16-20`; `domain/fit.py:38-44` |
| Scorecard renders grade badge only | `adapters/visualization/components/scorecard.py:46-56` |
| Design tokens (Home): Fraunces serif headline, DM Sans headings, Inter body, IBM Plex/JetBrains Mono labels+nums; color vars | `adapters/visualization/components/styles.py:8-32` |
| Glossary has factor defs ("Momentum/Revision/Quality/Value factor", "Trend filter", "Cleared the bar") | `adapters/visualization/components/glossary.py` (45 terms) |
| Home tiles use `proof_tile.render_tile` | `adapters/visualization/tabs/weekly_brief.py:17,159-210` |

---

## 4. Feature Overview (the locked end state)

Three zones, in Home's design system (Fraunces/DM Sans/Inter/Plex-Mono + color tokens + footer ledger):

**Zone ① — This week's research shortlist**
- 4 tiles (proof_tile): Showing `15 of 304` · As-of `Jun 14` "current evidence, not a forecast" ·
  Factors `5` · Trust `Inconclusive→Re-tested`.
- "How to read these ratings" expander (single legend; replaces per-cell percentile tooltips).
- Honest disclosure box (momentum no-edge; some factors can't be back-tested; not a forecast).
- View toggle: **Group by reason ⇄ Rank only** (`st.session_state`).
- **5 reason buckets**, exclusive-primary assignment with **repeats allowed** (badge), priority order:
  🌟 All-rounder (3+ factors top-quartile) → 🚀 Momentum leaders (momentum+revision) →
  💎 Quality at a fair price (quality+value) → 📈 Value with a catalyst (value+revision) →
  ⭐ Quality compounders (quality, not cheap) → 🛡️ Low-vol defensives (low-vol).
  An empty bucket renders an explicit honest "empty this week" panel (mockup: 🚀).
- Each name is a **collapsible row** → expands to the **5-factor detail card**: factor name + glossary
  "i" + plain-language **band** + diverging bar + percentile, **plain read**, **Google-AI read**
  (attributed), **Do next**. "Rank only" view = the same rows, flat, ranked by composite.

**Zone ② — Have your own names? Check them** (full parity with the shortlist)
- Paste/CSV → each name gets the **same expandable 5-factor card** + percentile-vs-cohort + Google-AI
  read + fit-vs-book verdict + STRONG/MODERATE/WEAK grade (with "i").
- In-screen names reuse stored `factor_scores`; off-universe names live-computed; **DATA-GAP** where thin.

**Zone ③ — Track record** → one-line link; history table relocated to the **Trust tab**.

---

## 5. Subsystems

### S1 — Factor model: add Low-vol, fix Revision, fold asset-growth, re-run IC
- **Low-Volatility factor (#5):** trailing N-day return volatility from yfinance prices (PIT-safe).
  Add to `FACTOR_KEYS`, z-scored/winsorized in `evidence_screen_use_case.py` like the others; composite
  denominator becomes 5. Lower vol → higher (inverted) z. Glossary entry added.
- **Revision fix (must resolve honestly):** today's "revision" measures analyst *target spread*, not
  estimate drift (§3). Two acceptable resolutions, decided by a data spike (§11):
  (a) **Source real time-series estimate revisions** from an adapter that exposes them PIT → keep the
  name "Revision factor"; or (b) **Honest rename** to "Analyst spread / target dispersion" with a
  truthful glossary def. **Fallback if the spike fails = (b).** The factor must not claim to measure
  drift it doesn't.
- **Asset-growth into Quality:** fold `(1 / YoY asset-growth)` (PIT-safe from balance sheets) into the
  quality sub-score; glossary updated. Optional if data thin → leave Quality as-is, note in spec log.
- **Re-run IC gate:** after factor-set change, re-run `backtest-screen`; persist a fresh
  `screen_ic_<date>.json`. The Trust tile reflects the new gate verdict honestly (PASS/INCONCLUSIVE/HALT).
  **No factor may be presented as predictive unless the gate PASSes; otherwise it stays descriptive +
  disclosed.** Momentum stays descriptive-only unless/until it passes.

### S2 — Bucket assignment engine (new `domain/screen_buckets.py`, pure, property-tested)
- Input: a candidate's factor percentiles. Output: ordered list of buckets it belongs to.
- Top-quartile = percentile ≥ 0.75 on the named factor(s). Signatures per §4.
- **Assignment:** every bucket independently takes its **top 5** by bucket-fit; a name may appear in
  several (repeats allowed, marked). Priority order governs which bucket is a name's *primary* (for the
  hero/`also` badge), but membership is per-bucket-independent.
- Empty bucket → explicit empty state. Deterministic; no randomness; total distinct names surfaced ≤ a
  configured cap (default mirrors current top-15 spirit; log if truncated, never silently).

### S3 — Screener tab UI rewrite (`research_candidates.py`)
- Reskin to Home tokens (§3): Fraunces headline + italic subhead, mono eyebrow/labels, JetBrains-Mono
  numbers, Inter body, `ws-card` borders/shadow/hover, color vars, mono footer ledger.
- 4 tiles via `proof_tile.render_tile`. How-to-read expander. View toggle via `st.session_state`.
- Collapsible rows (`st.expander` or a custom details block) → 5-factor card. Retire all bespoke inline
  hex; reuse `tooltip()`/glossary for every "i". Factor "i" pulls the existing glossary defs.
- Keep the abstention/funnel path (existing `ScreenDiagnostics`/`classify_screen`) but reskinned and
  honest; the "Cleared 304/512" + "ranking is the selective part" framing replaces "locked bar."

### S4 — Plain-language band mapping (new `domain/factor_bands.py`, pure, property-tested)
- Pure function percentile/z → band ∈ {Exceptional, Strong, Flat, Weak} with thresholds
  (Exceptional ≥0.90, Strong ≥0.75, Flat ≥0.40, Weak <0.40 — exact cutoffs locked in tests).
- Per-name **plain read** = deterministic template from the band profile (e.g. quality+value high &
  momentum flat → "value setup"). No LLM. New glossary entries: "Evidence score", "Percentile".

### S5 — Zone ② parity (`batch_fit` enrichment + arbitrary-ticker factor compute)
- Extend `FitVerdict` (or a new `BatchFitRow.factor_scores`) to carry the 5 factor scores + percentiles.
- New use-case path: for a pasted ticker, **reuse the screen's factor computation**; if in this week's
  screen, read stored `factor_scores`; else live-compute factors and rank vs the persisted cohort
  z-distribution to derive percentiles. **No new scoring logic** — reuse `evidence_screen_use_case`
  primitives. DATA-GAP per factor where yfinance lacks the input. Cap 25/run unchanged.
- Render the same card component as Zone ①.

### S6 — Google-AI read on the screener (reuse `GeminiNarratorAdapter`, attributed)
- On row expand (lazy), call `GeminiNarratorAdapter.summarize_case` with the name's already-fetched
  facts+news; render ≤5 in-favor / ≤5 to-watch as an attributed companion line. **Never** passed to or
  derived-into any score. Fails safe to data_gap (hidden or "Google-AI read unavailable"). Local-only /
  privacy guard consistent with the v9 card (`is_local_runtime` fail-safe). Forbidden-words asserted.

### S7 — History → Trust tab
- Move the screen-history table render to the Trust tab; leave a one-line link on the screener.
  Reuse `load_screen_history`. No data change.

---

## 6. Data Contracts

- Factor scores per candidate: `{name, value (z), percentile (0–1 vs cohort)}` — unchanged shape, +Low-vol.
- Composite: equal-weight mean over the (now 5) `FACTOR_KEYS`, missing=0 (`factor_scores.composite_score`).
- Grades (Zone ②): `domain/fit.py` STRONG/MODERATE/WEAK/UNKNOWN — unchanged thresholds.
- Bucket signature thresholds and band cutoffs: locked in §5 S2/S4, asserted in property tests.

---

## 7. UI ↔ mockup pin map (`screener-FINAL-v2.html`)

| UI element | Mockup anchor |
|------------|---------------|
| Eyebrow + Fraunces headline + italic subhead | `.eyebrow`, `.headline`, `.subhead` |
| 4 tiles | `.tiles .tile` (Showing / As of / Factors / Trust) |
| How-to-read legend | `#lg .legend` |
| Honest disclosure | `.disclose` |
| View toggle | `.seg` (`setView`) |
| Reason buckets + empty state | `.bkthd`, `.empty` |
| Collapsible row + 5-factor card | `.row`, `.frow`, `.band`, `.pp` |
| Plain read / Do next | `.donext` + row body text |
| Google-AI read | `.gai` |
| Zone ② full-matrix rows | `② Have your own names` rows (NVDA expanded) |
| Footer ledger | `.ledger` |
| (mockup-only) T2 chip | `.t2` — **NOT built**; phasing marker only, never in product |

---

## 8. Testing (TDD; small fixtures; no live APIs)

- **S1:** unit tests for Low-vol z/winsorize; composite over 5 factors; Revision resolution (spike test
  or rename test); IC gate re-run produces a verdict. Property: composite ∈ expected range; missing
  factor dilutes not excludes.
- **S2:** property tests — exclusive-primary + repeats; priority order; empty bucket; determinism;
  top-quartile boundary (p=0.75 inclusive); cap/truncation logged.
- **S4:** property tests — band monotonic in percentile; boundary cutoffs; plain-read template covers
  all band profiles without KeyError.
- **S5:** in-screen lookup vs off-universe compute; DATA-GAP path; cap 25; `FitVerdict` carries factors.
- **S6:** Gemini fail-safe → data_gap; rendered output has **no FORBIDDEN_WORDS**; never feeds score.
- **S3/S7:** render smoke tests; glossary "i" terms all resolve (no `tooltip()` KeyError); history on Trust.
- **CI tripwires:** FORBIDDEN_WORDS source scan on new modules; a test asserting no screener surface
  presents 512→0 (or any funnel) as EMH/discipline/forecast; `git checkout data/reports/` before verify
  (trailing-newline tracked JSONs).

---

## 9. Methodology guardrails (because scoring changes are in scope)

- Invoke `ds-methodology-review` for S1 before locking factor math (Low-vol definition, Revision
  resolution, asset-growth, leakage).
- Every new factor PIT-validated; `LookAheadBiasError` path exercised.
- IC gate is the arbiter of "predictive" vs "descriptive." Default = descriptive + disclosed.
- context7 verify (§11) for yfinance APIs before writing fetch code.

---

## 10. Build order (one spec, sequenced internally)

S4 bands (pure, no deps) → S1 factors (+IC re-run) → S2 buckets → S3 UI (consumes S1/S2/S4) →
S5 zone-② parity → S6 Gemini read → S7 history move. UI subsystems depend on the data subsystems
landing first.

---

## 11. Open risks / spikes / context7-verify

- **Revision data spike (blocking S1 choice):** can any available adapter expose PIT time-series EPS
  estimate revisions? If no → honest rename (fallback locked). Do this spike first.
- **yfinance** (context7 before code): volatility inputs / history window (S1), balance-sheet asset
  series (S1), `info`/analyst fields (S5).
- **streamlit** (context7): `st.session_state` toggle pattern, `st.expander` vs custom for collapsible
  rows, `st.fragment` for lazy Google-AI read (S6), proof_tile reuse (S3).
- **Low-vol bucket may be empty** in weeks without qualifying names — same honest empty-state as 🚀.
- **Cap/coverage:** if distinct names across buckets exceed the cap, log what was dropped (no silent
  truncation).

---

## 12. Definition of Done

- Screener renders in Home's design system; 4 tiles, legend, toggle, 5 buckets (+empty states),
  collapsible 5-factor cards, attributed Google-AI read, Zone ② parity, history on Trust.
- 5-factor scoring live; Revision honestly resolved; IC gate re-run + Trust tile reflects it truthfully.
- All honesty invariants (§2) hold; FORBIDDEN_WORDS clean; DATA-GAP never faked; no forecast wording.
- `make check` green (mypy strict, tests, coverage); property tests for S2/S4 pass; no `tooltip()` KeyError.
