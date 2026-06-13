# Research Instrument Redesign — Design Spec

**Project:** multi-modal-stock-recommender
**Date:** 2026-06-12
**Status:** Approved direction (validated via live Streamlit spikes); ready for implementation plan
**Author:** Tirth Joshi (with Fable main loop)
**Supersedes scope of:** the rolled-back "cockpit redesign" (PR #50 → reverted PR #52)

---

## 1. Problem & Goal

The v2 6-tab dashboard is **substance-rich but presentation-flat and unintuitive**. Concretely:
- Looks like a default Streamlit app — off-white, default Plotly, walls of small gray text, no hierarchy, no brand.
- The project's *greatest* asset — intellectual honesty (falsification, abstention, process-over-prediction) — is buried in gray text, so it reads as "empty/broken" instead of "rigorous."
- Not intuitive: no "start here," kitchen-sink density (Home, My Portfolio), disconnected tabs (no drill-down), overlapping tab purposes, and **no per-term explanations**.
- User benchmark: **SimplyWall.st** ("padding, intuitiveness, multi-source evidence").

**Goal:** Transform the dashboard into a distinctive, SWST-grade, *intuitive* "research instrument" — **without** adding any return prediction (ADR-044/045 hold) and **without** the cockpit failure mode (ship invisible change). Every gain comes from presenting honest evidence better, not from manufacturing confidence.

This addresses all four axes the user named: visual polish, new features, new tech, and legibility/employer-impact.

---

## 2. Locked Decisions (with rationale)

| # | Decision | Why |
|---|---|---|
| D1 | **Stay on Streamlit** — no Dash, no Next.js rewrite | Flatness was unspent CSS, not a framework ceiling. Proven by a live spike that hit the SWST bar in pure Streamlit. Dash = rewrite for the same problem; the Next.js repo = wrong domain + stack. |
| D2 | **No return predictions** | The engine's own data killed return prediction (ADR-044, rank-IC 0.004). "Re-add predictions" was a recurring pull; the honest substitute is **bold evidence/risk/trend verdicts** (Option 3). SWST itself doesn't predict returns either. |
| D3 | **Art direction: "Research Instrument"** — white/cool base, petrol-teal owned accent, editorial serif | Earlier warm-paper read as *Anthropic/Claude* branding; white gives the project its own identity and lets semantic color pop. Validated by spike. |
| D4 | **Three strands:** Visual · IA/intuitiveness · Honest-confidence | "Flat AND not intuitive" = both presentation and IA problems; both Streamlit-fixable. |
| D5 | **Comprehensive hover-tooltip glossary** on every metric/term, every tab | The biggest single intuitiveness win; SWST does exactly this. Sourced from `glossary.py` (currently 12 terms → expand). |
| D6 | **Click-a-stock = BOTH** in-app drill-down to Stock Analysis + external ↗ Yahoo Finance link | Keeps users in-product (the intuitiveness win) while offering raw-data escape. |
| D7 | **Stock Analysis becomes an attributed multi-source evidence dossier** (E1–E3, E5; E4/DCF deferred) | The "single SMA-200 flag is tunnel vision" critique resolves into a rich, *attributed* dossier — honest because it shows third-party views as theirs, not as our forecast. |
| D8 | **Staged rollout, show-before-ship** — build Home first → screenshot/run → user approves → then each remaining tab | The cockpit failed precisely because it shipped before the user saw it run. Never again. |

---

## 3. Non-Goals / Out of Scope

- ❌ No return/price predictions, buy/sell calls, win-probability, or "AI stock-pick" anything.
- ❌ No framework migration. No SWST scraping (no free API; ToS risk).
- ❌ No DCF fair-value model in v1 (E4 is a **flagged stretch** for a later phase — only with range + sensitivity + strict framing).
- ❌ No changes to the modeling/falsification record. No re-opening ADR-044/045.
- ❌ No deletion/consolidation of working surfaces sold as "progress" (the cockpit anti-pattern).

---

## 4. Design System — "Research Instrument"

All tokens live in `adapters/visualization/components/styles.py` (`inject_global_css`, already exists — extend it). Reference render: the approved Home spike.

**Palette (CSS variables):**
```
--app:#F4F6F8;  --card:#FFFFFF;  --ink:#14181F;  --ink2:#3A4250;  --muted:#717885;
--line:#E3E7EC; --hair:#EDF0F3;
--teal:#0F6E80;     /* OWNED primary (petrol) — structural/validated */
--crimson:#CE2F26;  /* falsified / trend-broken / danger — used sparingly */
--amber:#C9810E;    /* abstain / caution / concentration */
--green:#1F9254;    /* pass / trend-intact / healthy */
```
Semantic colors are **bold and scarce** — instant good-vs-bad legibility. Crimson appears only on genuinely negative/falsified states.

**Typography (3-font pairing, via Google Fonts @import):**
- **Fraunces** (display serif) — headlines, big metric numbers. Editorial, premium, *not* generic Inter.
- **IBM Plex Sans** — body. Technical-but-readable.
- **IBM Plex Mono** — the ledger, labels, metrics, stamps. Forensic/lab character.

**Spacing & surfaces:** generous padding (cards ≥ 1.5rem), `border-radius:14–16px`, soft cool-tinted shadows, hairline borders, even vertical rhythm. Streamlit header/menu/footer hidden via CSS.

**Signature components (new, in `components/`):**
- **Evidence Ledger strip** — persistent monospace bar under H1 on every tab: `state · universe · cleared · net β · book · as-of`. Real numbers.
- **Anti-KPI proof tile** — big Fraunces number + colored left rule + rubber-stamp badge (`FALSIFIED` / `= EMH` / `ABSTAINED`).
- **Verdict card** — colored left border + mono verdict head + plain-English finding + score dots (`●●●●○○`).
- **Book-health ring** — inline SVG, petrol arc (no default-Plotly look).
- **Section rule heading** — mono uppercase + hairline.
- **Abstention funnel** — Screener exhibit (see §7).

**Charts:** one shared Plotly template (`components/charts.py`, new): transparent bg, gridlines off/faint, graphite axis text, semantic colors, threshold annotations, Plex fonts. Kills the default-Plotly fingerprint.

---

## 5. The Tooltip-Glossary System (D5)

A first-class, reusable hover-tooltip ("cloud") on **every** metric, label, and verdict across all tabs.

- **Behavior:** appears on hover, disappears on leave; dark bubble, plain-English, explains *meaning AND implication* (e.g., Net β → "moves ~1.37× the S&P; most risk is one market bet").
- **Affordance:** hoverable terms get a subtle dotted underline.
- **Source of truth:** extend `glossary.py` (12 → ~40 terms) as the single dictionary; a `tooltip(term)` helper wraps any label and pulls copy from the glossary. No copy duplicated in tabs.
- **Coverage requirement:** ledger fields, anti-KPI metrics, factor axes, verdict heads, discipline flags (REDUCE/TRIM/HOLD/ADD-ON), screen terms, risk terms — all documented.
- Copy must respect the FORBIDDEN_WORDS guard (§9).

---

## 6. Interaction — Drill-down + External (D6)

- **In-app drill-down:** clicking a ticker anywhere (Home cards, Portfolio rows, Screener) sets `st.session_state` and routes to the **Stock Analysis** tab for that ticker (Streamlit 1.58 dataframe-selection / button nav). Keeps users in-product.
- **External link:** a small `↗` on each ticker opens `finance.yahoo.com/quote/<T>` in a new tab (raw-data escape; honest external reference).

---

## 7. Per-Tab Treatments (visual + IA; all 6)

1. **Home (weekly_brief)** — thesis hero ("learned when not to predict") + 3 anti-KPI proof tiles (Rank-IC 0.004 / ~50%=EMH / 512→0) + Evidence Ledger + book-health ring + honest verdict cards (trend/risk) + discipline flag chips. *Trend chip relabeled "Trend filter" — one labeled process signal, not "the verdict."*
2. **Screener (research_candidates)** — replace the gray "512 → none cleared" text with a designed **abstention funnel** (Universe 512 → filters → 0), using the existing candidate-distribution data. Keep check-your-own-list + history, restyled.
3. **Risk** — restyle macro-beta scrubber + factor chart + risk-source donut to the system; add a plain-English **conclusion band** ("64% one market bet — another name won't diversify").
4. **My Portfolio** — de-densify the kitchen sink: progressive disclosure (positions hero → expandable closed/all-attention/watchlist), drill-down rows, restyle.
5. **Stock Analysis** — restyle to the system + full tooltip coverage + the **evidence dossier** (§8) + drill-down target + an "Evidence Status: not a forecast" framing header.
6. **Trust** — anti-KPI hero row (0.004 / ~50% / hypotheses-killed) + Claim→Test→Result→Decision **experiment cards** replacing text walls + restyled ablation/SHAP exhibits.

---

## 8. Stock Analysis — Attributed Evidence Dossier (D7)

Builds on what already exists (`stock_analysis.py`: Valuation/Growth/Performance/Health/Ownership/Sentiment/Supply-chain sections, 6-axis snowflake, analyst-consensus card). Adds, in scope:

- **E1 — Industry-relative scoring.** Every axis shown as a percentile **vs GICS sector peers** (sector/industry from yfinance `info`; sector ETFs / supply-chain groups already present). Honest relative facts. *Requires a clean peer-set; no spurious peers.*
- **E2 — Attributed analyst-estimate panel.** Surface the existing `revision` factor (EPS-estimate drift) as a *trend* + dispersion (mean/high/low/count/as-of) from yfinance. Labeled "Wall Street expects…", attributed, never adopted.
- **E3 — News/event CONTEXT panel.** Attributed GDELT + Google News themes (both live, keyless), labeled "context, not signal" (consistent with the existing falsified-sentiment disclaimer).
- **E5 — Differentiators surfaced on the page:** portfolio-fit verdict (`fit.py`) + a falsification badge — the things SWST structurally can't show.
- **E4 — DEFERRED stretch:** transparent DCF fair-value **range** (bull/base/bear) + sensitivity. Only later, only with strict "valuation estimate, not a price prediction" framing.

Snowflake/dossier framing stays: *"a description of today, not a forecast."*

---

## 9. Honesty Guardrails (hard rules)

The vocabulary guard `domain/fit.py:13` forbids: `buy, sell, winner, conviction, predict, alpha, outperform` — enforced on source text (`test_scorecard.py`, snowflake source scan) and rendered output (`test_fit.py:118`). Therefore:
- All new verdict/tooltip/dossier copy must avoid those 7 words; phrase verdicts as evidence ("trend filter: below 200-day," "ranks 78th pct vs sector").
- Third-party data (analyst, news, sentiment) is **attributed** ("the Street / GDELT / sentiment reads…"), shows dispersion, and is **never** presented as the engine's own claim.
- Factors (`momentum`, `revision`, `quality`, `value`) stay **descriptive percentiles**, not predictive. Per ADR-045 a Tier-2 signal used predictively must be falsification-tested first — out of scope here.
- Every on-screen number traces to a real computation. No fabrication. Abstention stays visible and is framed as rigor.
- `RESEARCH_ONLY` / `NOT INVESTMENT ADVICE` remains on relevant surfaces.

---

## 10. Architecture & Code Layout (hexagonal — preserved)

- **All presentation in `adapters/visualization/`.** `domain/` stays framework-free.
- Theme + components: extend `components/styles.py`; new `components/charts.py` (Plotly template), `components/ledger.py`, `components/tiles.py`, `components/verdict_card.py`, `components/funnel.py`, `components/tooltip.py`.
- E1–E3 read logic: pure functions in `domain/` (e.g., `peer_relative.py` percentile math) + orchestration in `application/` + fetch in `adapters/data/` (analyst/news adapters already exist). New tool = new adapter, never new domain coupling.
- Glossary expansion in `components/glossary.py` (or `domain` if pure data).
- No deletion of working tabs/logic; additive + restyle only.

---

## 11. Testing

- Keep the **full suite green** (1628 → grows). Run `make check` (lint + mypy strict + tests ≥90% cov).
- **Vocab guards must stay green** on all new components (source + output scans).
- **Add snapshot/structure tests for the honest UI states** (abstention, falsified, degraded-data, concentrated-risk) — the regression guard that would have caught the cockpit. (ChatGPT's suggestion; adopted.)
- Per `STATUS.md`: `git checkout data/reports/` before any pre-commit/CI verify (tests strip trailing newlines from 2 tracked JSONs).

---

## 12. Staged Rollout (show-before-ship — D8)

Each stage: build → launch app → **screenshot the running tab** → user sees it → approve → next. Nothing merges before the user has launched it. Guards/tests green each stage.

- **Stage 0 — Foundation + Home:** design system (tokens, fonts, chart template, components) + tooltip system + Home tab. → screenshot → approve.
- **Stage 1 — Screener + Risk:** abstention funnel; risk restyle + conclusion band.
- **Stage 2 — My Portfolio + Trust:** de-densify portfolio; Trust anti-KPI hero + experiment cards.
- **Stage 3 — Stock Analysis:** restyle + tooltips + drill-down wiring + evidence dossier (E1–E3, E5).
- **Stage 4 — Hardening:** snapshot tests for honest states; glossary completeness; full `make check`; docs (STATUS/PHASE_LOG/ADR for the redesign + the honesty reasoning).

Tooltip-glossary coverage advances with each stage.

---

## 13. Success Criteria

1. On launch, the dashboard is **unmistakably different** and reads as a designed product, not default Streamlit (the cockpit failure inverted).
2. A first-time viewer can hover any metric and understand what it means **and implies**.
3. The honesty (falsification, abstention, process) is **legible in the first 10 seconds**, framed as rigor.
4. Stock Analysis shows an attributed, multi-source, SWST-grade evidence dossier — **zero** return predictions, all FORBIDDEN_WORDS guards green.
5. Clicking a stock drills into its analysis (and offers ↗ Yahoo).
6. Full test suite + vocab guards + mypy green; honest-state snapshot tests added.

---

## 14. Risks & Open Questions

- **Streamlit theming brittleness** across upgrades (CSS injection). Mitigate: centralize tokens; verify against Streamlit 1.58 via context7 during build.
- **"Predict" pull resurfacing** — the user circled prediction twice this session. Guardrails (§9) + attribution discipline are the defense; revisit only via a pre-registered falsification, never via UI vibes.
- **yfinance analyst data quality** (laggy/scraped) — always show dispersion + count + as-of; attribute.
- **Peer classification** for E1 — needs a sane sector/industry source; spurious peers are a credibility risk.
- **Scope creep** — E4/DCF explicitly deferred to keep blast radius small and shippable.

---

### Appendix — session provenance
Direction validated through three live Streamlit spikes (warm→white pivot, bold semantic color, clickable yfinance, comprehensive hover tooltips). External triangulation: Gemini + ChatGPT both independently endorsed the design-system / abstention-exhibit / Trust-anti-KPI direction and (after inoculation) suggested no prediction features. Methodology review (`ds-methodology-review`) confirmed SWST is honest-evidence (not return-prediction), that ~80% of its surfaces already exist in code, and scoped the honest evidence-dossier additions (E1–E3, E5; E4 deferred).
