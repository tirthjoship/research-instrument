# Per-Stock Decision Card — Design Spec

**Date:** 2026-06-13
**Status:** Draft for review
**Author:** Tirth Joshi (brainstormed w/ Claude)
**Branch:** `feat/per-stock-decision-card`
**Mockups:** `.superpowers/brainstorm/22693-1781372142/content/per-stock-v9.html` (final), v1–v8 show the iteration path. Screenshots: `/tmp/card_v6..v9.png`.

---

## 1. Problem & North-Star

The shipped Research-Instrument dashboard (ADR-055/056) is honest and visually polished but **not legible to its own non-expert operator**. On 2026-06-13 Tirth reported making **zero transactions this week** despite live discipline flags — because *"I couldn't tell what to trust"* and the app *"feels gibberish to someone who doesn't know everything about financial calls."*

**North-star:** make the per-stock view legible and trust-projecting to a non-expert, so the user can act — by making the **attributed evidence we already compute** readable, **not** by inventing predictive confidence. (See memory `feedback_dashboard_trust_legibility`.)

Success criterion: Tirth can confidently decide keep-vs-trim on a single holding from this card alone.

## 2. Non-Negotiable Honesty Rails

These are derived from shipped decisions and a live experiment; the card must not violate them. They were stress-tested ~6× during brainstorming — every "just add a buy/sell %" request was redirected and the user ultimately chose the honest design.

1. **No predictive buy/sell verdict, no forecast %.** Per-stock return prediction was falsified (IC ≈ 0, ADR-044/052). The card never emits BUY/SELL or "78% it drops." A confident-but-hollow number is the exact theatre that broke the user's trust.
2. **Verdict = transparent rule only.** TRIM/HOLD/REDUCE/ADD_OK comes from the pre-registered discipline rule (`domain/discipline.py`), framed as *"a prompt to review, not a forecast."* No multi-factor model drives it.
3. **Confidence = measured calibration only.** The only number called "confidence" is the rule's **measured forward hit-rate** (ADR-048/051 gate). Until enough cases resolve it shows **"calibrating…"**, never a fabricated number. It is the **rule's** track record, never per-stock return odds.
4. **Third-party views are attributed, never adopted.** Analysts and any LLM ("Google AI Mode") are shown as cited outside opinions that inform the *user* — they never feed the verdict or the calibration. (Memory `feedback_attributed_not_predicted`.)
5. **Do not contaminate the live gate.** The discipline rule stays frozen while ADR-048/051 measures it (~mid-July). "Learning" happens by *new pre-registered rule experiments*, not by live re-weighting.
6. **No fabricated data.** Where a feed is missing (e.g. revenue beat/miss estimates), show an explicit DATA-GAP, never invent values.
7. **RESEARCH_ONLY + FORBIDDEN_WORDS guard** apply to every string on this surface, same as existing surfaces.

## 3. Card Anatomy (top → bottom)

Reference: v9 mockup. Each zone lists **what it shows / source / honesty framing**.

1. **Verdict + meaning** — rule verdict (e.g. `TRIM`) labelled *"trend-break rule (v1) — review prompt, not a forecast"* + an `evidence: strong/mixed/thin` badge. A one-line plain-English **"What this means"** synthesis (describe, don't prescribe).
2. **Position** — current price, user cost basis, unrealized $/% , trailing returns 7/30/90/180d as signed % chips, a 1-yr sparkline. Pure arithmetic + observed history.
3. **The case — Google AI, cited** — two columns: **5 in its favor / 5 to watch out for**, each point cited to a fetched source. Badge: *"informs you, not the verdict."* Balanced by construction (both sides, equal weight).
4. **Evidence detail** — per-dimension RAG tiles, each a colored square **with a letter (R/A/G) and text** (color-blind safe) + a one-line factual descriptor: Technicals, Valuation, Financials, **Earnings (last 4Q EPS beat/miss)**, Analysts (3rd-party). No composite score.
5. **How the verdict learns + Reliability** — explains rule evolves by validated experiment (candidate rules adopted only when they beat v1 on resolved outcomes; hold v1 steady to measure it). Reliability line surfaces the calibration gate state ("0 of N scored, ~mid-July → eventually e.g. 64% of 80, TP/FP ledger").
6. **Your options** — Hold-the-winner vs Trim-to-lock-gains, each with case **and** risk; a "what I'd watch" trigger. Choice is logged → feeds the track record.
7. **Footer** — sources + "Research only … not a buy/sell signal."

## 4. Key Design Decisions (the reconciliations)

- **"Confidence %" = calibration, not forecast.** The user wanted a confidence number that "learns from true/false positives." That is exactly the ADR-048/051 calibration gate (rule hit-rate from resolved 21-day outcomes). We surface it; we never fabricate it pre-gate. This reconciles the user's desire with the falsification stance.
- **"Google AI verdict" = attributed 5-for/5-against case, grounded + cited.** The LLM **summarizes real fetched articles** (no free-association), shown as balanced context. It must cite sources and must not output a single buy/sell or feed any score. ("Not adopted" ≠ "ignored" — it is shown prominently.)
- **"Adaptive/learning verdict" = staged rule experiments, not a black box.** Multi-evidence rules (e.g. trend-break AND earnings-miss) are candidate experiments measured against outcomes and adopted only when they beat the incumbent. Live re-weighting is rejected: *to learn whether a rule works you must hold it still long enough to measure it* (also the data-leakage guardrail).
- **Per-dimension RAG, never a composite.** Validated by research (Simply Wall St "not a Buy recommendation", Morningstar separated pillars; the TipRanks single-score and Robinhood action-proximity are the documented failure modes). See research dump in session notes.
- **Describe, don't prescribe; accessibility.** "Momentum negative 90 days" not "consider selling"; RAG color always paired with letter + sign.

## 5. Architecture (hexagonal mapping)

Reuse first; new code is a new adapter/port, never new domain prediction.

**Reuse (already exists):**
- `adapters/visualization/stock_analyzer.py::analyze_ticker` → `AnalysisResult` (price, info, valuation/growth/health/ownership/sentiment, peer_data).
- `domain/peer_relative.py` (sector percentiles), `application/analyst_panel.py` (attributed analysts), `application/news_context.py` (attributed news).
- `application/fit_use_case.py::gather_and_assess` + `domain/discipline.py` (verdict, trend rule) for the rule verdict + evidence flags.
- Calibration surfacing: the `discipline-calibration-status` use case (reliability state) + `data/personal/discipline_log.jsonl` / `application/adherence.py` (choice logging → track record).

**New (this spec):**
- **Earnings beat/miss**: a `domain` model `EarningsTrackRecord` + an adapter method (yfinance `get_earnings_dates`) behind a port; returns last-4Q EPS surprise (beat/miss). Revenue surprise = explicit DATA-GAP until an estimates feed exists.
- **AI evidence case** (Google AI 5/5): a port `EvidenceCaseProvider` + adapter that (a) fetches real cited articles, (b) has the LLM **summarize the fetched text** into ≤5 pro / ≤5 con points **each carrying a source ref**, (c) returns a `BalancedCase` value object. Adapter is RESEARCH_ONLY-guarded; output is attributed and never fed to verdict/calibration. Hallucination guard: a point with no resolvable source ref is dropped.
- **RAG mapping** (`domain`): pure functions mapping each evidence dimension's facts → {RED, AMBER, GREEN} via explicit, documented thresholds (no fitting).
- **Card component** (`adapters/visualization/components/decision_card.py` + a tab/section): renders the zones using the RI design tokens.

**Dependency direction unchanged:** adapters → domain ← application. The LLM/earnings live only in adapters behind ports; `domain/` stays stdlib-only.

## 6. Error Handling & Data Gaps

- **Calibrating state**: when 0 resolved cases, reliability shows "calibrating…" + progress, never a number.
- **Missing analyst / news / AI case**: per-panel DATA-GAP, card still renders.
- **Revenue beat/miss**: explicit "needs an estimates feed" note.
- **LLM unavailable or ungrounded**: the case panel degrades to the existing attributed news list; never blocks the card.
- **`analyze_ticker` failure / abstain**: surface the error/abstention honestly (existing pattern).

## 7. Testing Strategy (TDD)

- Snapshot tests for both reliability states (calibrating vs earned) and evidence: strong/mixed/thin.
- `FORBIDDEN_WORDS` guard test over every static + dynamic string on the surface (incl. AI-case output).
- RAG threshold unit tests (pure domain).
- Earnings adapter test with a fake provider (no live yfinance in CI); beat/miss + DATA-GAP cases.
- AI-case adapter tests: every returned point carries a source ref; ungrounded points dropped; output never reaches verdict/calibration (assert wiring).
- Calibration-surfacing test: card reads gate state, shows no number when thin.
- Accessibility test: each RAG tile has a non-color label.
- Property test (Hypothesis) on RAG mapping monotonicity where defined.

## 8. Scope

**Phase 1 (this spec):** the per-stock decision card (v9).
**Phase 2 (separate specs, queued):**
- **Home 3-second triage** — a scannable, de-duplicated sibling that drills into this card (addresses "Home is repetitive"; REDUCE/TRIM currently render 3×).
- **Risk rubric** — good/bad/average benchmark framing for net beta + systematic share (currently raw numbers, no rubric).
- **Screener legibility** — make the by-design 0-cleared abstention legible to a non-expert (it is correct behavior, not a bug; ADR-045/047/052).

## 9. Open Questions

- The rule-experiment framework (candidate multi-evidence rules → calibrate → adopt) is described but not yet specced — does it become an ADR after the mid-July gate resolves?
- Which LLM/provider backs the "Google AI Mode" case, and the exact fetch→summarize→cite grounding pipeline (separate small spec; must be cost- and hallucination-bounded).
- Revenue beat/miss: source an estimates feed, or drop the revenue half permanently?

## 10. Out of Scope / Won't Do

- Any predictive buy/sell verdict or fused confidence score.
- Letting the LLM or any multi-factor blend drive the verdict or the calibration number.
- Live/adaptive re-weighting of the discipline rule.
