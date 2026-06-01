# ADR-028: Event-Causal Learning — News to Sector Impact with Decay

**Date:** 2026-06-01
**Status:** Accepted
**Deciders:** Tirth Joshi

## Context

Market-moving events (Fed rate decisions, tariff announcements, geopolitical events, earnings surprises, FDA approvals) follow recognizable patterns: a specific event category reliably moves a specific sector in a predictable direction, with an impact that peaks quickly and decays over days to weeks.

The current system treats all news as undifferentiated sentiment (positive/negative score). It cannot distinguish between a Fed rate hike (bad for growth tech, good for banks, 7-day decay) and a tariff announcement (bad for supply-chain-exposed industrials, 14-day decay with escalation risk). These distinctions are where the real alpha lies — the user missed several sector rotation opportunities because the sentiment layer lacked this causal structure.

Standard NLP sentiment scores react to events but don't explain them. A sentence like "Fed raises rates by 50bps" scores neutral on Flan-T5 (factual, not opinionated), but has a very specific and predictable sector impact.

## Decision

Build an event-causal layer with three components: event taxonomy, LLM-based event classifier, and a learned event-impact model.

### Event taxonomy (10 categories)
1. `monetary_policy` — Fed decisions, central bank statements, interest rate changes
2. `fiscal_policy` — government spending, tax policy, budget announcements
3. `trade_policy` — tariffs, sanctions, trade agreements
4. `geopolitical` — wars, elections, diplomatic events with market impact
5. `earnings_surprise` — beats/misses relative to consensus estimates
6. `regulatory` — FDA approvals/rejections, SEC actions, antitrust decisions
7. `macro_data` — CPI, jobs report, GDP, PMI releases
8. `corporate_action` — M&A, spinoffs, CEO changes, bankruptcy filings
9. `sector_catalyst` — technology breakthroughs, commodity price shocks, supply disruptions
10. `analyst_action` — upgrades, downgrades, price target changes

### LLM event classifier
- Input: article headline + first paragraph
- Output: `{event_type, confidence, affected_sectors[], direction (positive/negative/neutral per sector), urgency (immediate/days/weeks)}`
- Implementation: Flan-T5 zero-shot prompt (consistent with ADR-004). Falls back to keyword rules if confidence < 0.6.
- Runs in the daily scan pipeline (ADR-022) alongside existing sentiment scoring

### Historical impact model (learned)
- Training data: GDELT events (ADR-024) + yfinance sector ETF returns, 2018–2025
- For each (event_type, sector) pair, fit a simple exponential decay model: `impact(t) = magnitude * exp(-t / half_life)`
- Store fitted parameters in `config/event_impacts/impact_model.json`: `{event_type: {sector: {direction, magnitude, half_life_days, n_observations, confidence_interval}}}`
- This gives the system a learned prior: "monetary_policy tightening historically moves XLF +1.2% day 1, decaying to zero by day 7"

### Live pipeline integration
- When an event is classified with confidence > 0.6, generate an `EventAlert`:
  ```
  Event: Fed raises rates 25bps (monetary_policy, high confidence)
  Expected sector impacts:
    XLF (Financials): +1.1% ± 0.4% over 3 days
    QQQ (Tech): -1.8% ± 0.6% over 7 days
    XLU (Utilities): -0.9% ± 0.3% over 5 days
  Historical basis: 12 similar events since 2018
  ```
- Alerts surface in the weekly report and trigger `MonitorHoldingsUseCase` checks (ADR-026)
- Event-adjusted sentiment score: standard sentiment + event impact prior, weighted by confidence and time elapsed since event

### Impact model updating
- After each event, measure actual vs predicted sector impact at T+1, T+3, T+7
- Update impact model with new observation (rolling window, older observations down-weighted)
- This is the "learning" component — the model improves as it observes more events

## Alternatives Considered

- **Pure rule-based event mapping** — hardcode: "if Fed hikes rates, sell tech, buy financials." Simple, explainable. But cannot adapt to new patterns (what does a novel tariff structure do?), cannot quantify magnitude or decay, cannot update from new data. Rejected.
- **Real-time NLP sentiment only (no event taxonomy)** — current approach. Misses causal structure. Treats "Fed hikes 50bps" as neutral sentiment. Cannot generate specific sector impact forecasts. Rejected as sufficient.
- **Fine-tuned financial event classifier** — train a BERT-based model specifically on financial events (FinEvent dataset). Higher accuracy than zero-shot. Out of scope for current phase; Flan-T5 zero-shot is good enough for 10 broad categories. Deferred to Phase 5. Rejected now.
- **EventRegistry / RavenPack API** — commercial event detection APIs with pre-classified events. Expensive ($500+/month). Rejected for portfolio project.
- **GPT-4 for event classification** — higher accuracy than Flan-T5 for nuanced events. Adds API cost and latency to the daily scan. Flan-T5 local inference is faster and free. Revisit if zero-shot accuracy is insufficient. Rejected as primary.

## Consequences

**Positive:**
- Addresses the specific user pain point: missed sector rotation opportunities because causation wasn't detected fast enough
- Generates human-readable event alerts with expected sector impacts and historical basis — directly actionable
- Impact model learns from new events, improving over time without manual rule updates
- Event features add a qualitatively different signal to the ensemble that pure technical and sentiment features cannot replicate
- Decay modeling correctly reduces the impact of old events rather than treating them as permanently relevant

**Negative:**
- Flan-T5 zero-shot accuracy on 10-category classification is unknown without evaluation. A confusion matrix study is required before trusting high-confidence classifications
- Historical impact model trained on 2018–2025 data assumes regime stationarity: the same event type has the same sector impact across different macro regimes. This is empirically false (rate hikes in a zero-rate environment differ from hikes in an already-tight environment). Mitigated by storing confidence intervals and flagging low-n-observations categories
- `impact_model.json` must be versioned — model drift as new events update parameters must be trackable
- Daily scan latency increases: event classification adds ~0.5s/article for Flan-T5 inference (same as sentiment scoring). Acceptable within the 2.5-minute daily scan budget

## Superseded By
None
