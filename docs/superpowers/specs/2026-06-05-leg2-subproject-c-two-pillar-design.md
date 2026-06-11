# Leg-2 Sub-Project C — Two-Pillar Surfacing (Divergence + Free Event Signal) Design Spec

**Date:** 2026-06-05
**Status:** Draft (pending user review)
**Branch:** `feat/leg2-subproject-c-two-pillar`
**Predecessors:** ADR-039 (no OOS edge), ADR-041 (opportunity engine), ADR-042 (honest ingestion), ADR-043 (conviction dims dead → divergence-led).

---

## 1. Goal

Turn the engine into an honest **two-pillar surfacer**: **divergence** (attention-acceleration vs price — the live, varying, thesis-core signal) + **event_signal** (catalyst classification, now revivable **for free**). Prune the conviction dims that are structurally dead on the mid-cap spine. Keep min-history + honest abstention; let **forward-tracking** be the arbiter of edge.

This is NOT "add more signals." It revives exactly one dim — the most thesis-relevant one for catalyst-driven thematic names — using infrastructure already built (GoogleNewsAdapter) + a free Gemini key, and **deletes** the dead dims. Net dimensionality goes *down*, honesty goes *up*.

---

## 2. Context — why now

ADR-043's discrimination audit (63 warmed-spine candidates) proved conviction is freshness-dominated: only `temporal_freshness` (var 2.65) and `fundamental_basis` (0.25) vary; 6 dims are dead. Two of the dead dims have **no free data** for mid-caps (`smart_money` — no 13D/Form-4; `analyst_signal` — no coverage) and two aren't computed in bulk (`ml_direction`, `sentiment_momentum`). But **`event_signal` is dead only because of a stale wiring gap**: the bulk scan never fed it headlines (old code assumed a paid AlphaVantage source). We now have:
- `GoogleNewsAdapter` — keyless per-ticker Google News RSS (built in sub-project A).
- `GeminiEventClassifier.classify(headline, date) -> ClassifiedEvent` — free tier, 15 RPM (built in Phase 4D).
- A user-provided free `GEMINI_API_KEY` (in local `.env`, gitignored).

So `event_signal` can go live at zero marginal cost.

---

## 3. Scope

### In scope
1. **GoogleNewsAdapter.get_headlines(ticker, scan_time) -> list[tuple[str, str]]** — return `(title, iso_date)` per article (it currently only counts entries; the titles are already in the parsed feed, just discarded). Keep `scan_sources` unchanged.
2. **EventSignalService / use case** — headlines → `GeminiEventClassifier.classify_batch` → aggregate the classified events into a `[1,10]` event score per ticker. Reuse the existing event→impact mapping if `EventCausalFeatureEngineer` (Phase 4D) already provides one; otherwise define a simple, documented aggregation (e.g. score scales with count × category-impact of positive catalysts, capped). Pure-ish: classification is an injected port; aggregation is testable in isolation.
3. **Cache it** — wrap the event computation in the existing `ConvictionSignalCache` (24h TTL, flagged failures). Free tier is 15 RPM → spine-only, daily cache, `classify_batch` to batch. A Gemini throttle/failure → flagged neutral (never silent), consistent with sub-project A/B.
4. **Wire `event_signal` into the scan's `conviction_provider`** (replace the hardcoded neutral 5.0 at cli.py:851).
5. **Prune the dead dims** — `smart_money`, `analyst_signal`, `ml_direction`, `sentiment_momentum` set to weight 0 in the conviction weighting (config-driven if weights are configurable; else remove from the bulk-scan sub-score computation with a documented comment). Keep `fundamental_basis` (live-weak), down-weight `temporal_freshness` (it's recency, not opportunity — keep as a minor freshness nudge only), and add `event_signal` as a primary conviction input.
6. **Two-pillar surfacing** — divergence stays the primary gate (`dmin`); the rebuilt event-led conviction is the second pillar (`cmin`). Keep `has_min_history` eligibility + honest abstention + full-distribution logging.
7. **Recalibrate `cmin`/`dmin`** on the new two-pillar distribution (warmed spine), record via the discrimination audit (event_signal should now show var>0, neutral_share<1).

### Out of scope (deferred / rejected)
- Reviving `smart_money` / `analyst_signal` (no free data for mid-caps) — pruned, not revived.
- `ml_direction` / `sentiment_momentum` bulk inference — pruned for now.
- Paid news/data sources. Full 350 universe. Intraday tier.
- Any claim of edge — forward-tracking remains the only arbiter.

---

## 4. Architecture

Hexagonal, consistent with A/B. Classification is an injected port (`EventClassifierPort`, exists). New small pieces:

- `adapters/data/google_news_adapter.py` — add `get_headlines`.
- `application/event_signal_service.py` (or domain service if pure) — aggregate `list[ClassifiedEvent]` → `[1,10]` score. Pure function + a thin use case that wires GoogleNews → Gemini → aggregation, cached via `ConvictionSignalCache`.
- `application/cli.py` — build the event provider (GoogleNews + Gemini from `GEMINI_API_KEY`), pass a real `_compute_event(ticker, now)` into `ConvictionSignalCache.get_or_compute`; reweight conviction (prune dead dims).
- Conviction weighting: prefer config in `config/markets/us.yaml` under `opportunity_engine` (a `conviction_weights` block) so pruning is declarative and auditable.

Data flow (per spine ticker, daily, cached):
```
GoogleNews RSS headlines --> GeminiEventClassifier.classify_batch --> aggregate --> event_signal [1,10]
                                                                                   |
divergence (attention accel vs price, live) ----+----------------------------------+--> two-pillar surface/abstain
                                                  (min-history gate, full-distribution log, forward-track)
```

---

## 5. Risks & pitfalls

1. **Gemini free 15 RPM / daily token cap** — spine-only (~40), `classify_batch`, 24h cache; a throttle → flagged neutral (visible, never silent). Don't run on the 350 universe.
2. **GoogleNews RSS headline quality / wrong-company matches** — use the ticker alias map (themes.yaml) for the query; cap headlines per ticker (e.g. top 10).
3. **event_signal could dominate falsely** — it has no proven edge (ADR-039 event-causal had none). Weight it as a *peer* of fundamental_basis, not an oracle; divergence stays the primary gate; forward-tracking judges.
4. **Look-ahead** — headlines must be dated by article publish date (provenance rule from sub-project B); classification uses only headlines ≤ scan_time.
5. **Key handling** — `GEMINI_API_KEY` from env only; never logged, never committed (gitleaks enforces).
6. **Pruning hides a future-useful dim** — pruned dims are weight-0/documented, not deleted from the model code, so they can be re-enabled if a free data source appears.

---

## 6. Acceptance Criteria (v1)

- `event_signal` live: discrimination audit shows `var>0` and `neutral_share<1` for it on the warmed spine.
- Dead dims (`smart_money`/`analyst_signal`/`ml_direction`/`sentiment_momentum`) weight-0 and documented.
- Two-pillar surfacing in effect; `cmin`/`dmin` recalibrated on the new distribution.
- Engine surfaces names that clear both pillars **or** honestly abstains with the full distribution shown.
- Gemini path cached + throttle-flagged; spine-only; no key in logs/commits.
- `make check` green, mypy strict, ≥90% coverage; feature → develop → main, green CI.
- **Not required:** proven edge, 350 coverage, reviving the no-free-data dims.

---

## 7. Docs

- Amend **ADR-043**: note that **free** event_signal revival (GoogleNews + Gemini) is in-scope for sub-project C; the "reject revival" decision stands only for *paid* revival of the no-free-data dims.
- New **ADR-044**: two-pillar surfacing + conviction pruning (weights, rationale, honest caveat).
- Update CLAUDE.md status + CONTEXT.md glossary (event_signal live, two-pillar, conviction_weights).

---

## 8. Open questions for review

- Event-score aggregation: reuse `EventCausalFeatureEngineer`'s mapping, or a fresh simple aggregation? (Proposal: reuse if it already yields a [1,10]-able score; else simple count × category-impact, capped.)
- Conviction weights after pruning (proposal: event_signal 0.45, fundamental_basis 0.35, temporal_freshness 0.20; dead dims 0).
- Headlines per ticker cap (proposal: 10).
