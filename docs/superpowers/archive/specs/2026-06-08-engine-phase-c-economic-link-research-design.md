# Engine Phase C — Economic-Link Research + Drift Experiment — Design Spec

**Date:** 2026-06-08
**Status:** Draft for review
**Author:** Tirth Joshi (with Claude)
**Follows:** ADR-049 (engine architecture), Phase-B spec (weekly brief)
**Phase:** C of 4 (directed customer→supplier research scaffolding + one pre-registered drift test)

---

## 1. What this is — and what it is not

Two things, sharply separated:
1. **Research/alert scaffolding (ships, honest):** a **directed customer→supplier economic-link graph** that, given a move or news on a *customer* firm, surfaces the *linked supplier* + the relationship + a "go research this" prompt. Example: *Walmart advances healthcare → McKesson (supplies Walmart's pharmacy) → research.*
2. **A pre-registered prediction experiment (gated):** one honest OOS test of the **Cohen-Frazzini (2008) economic-link drift** — does a supplier's stock predictably drift after its customer's news? PASS → eligible for Phase D; else the link layer stays research-only.

**It is explicitly NOT:**
- statistical correlation (the user's own distinction: different *roles* in a value chain, not co-movement). This is a **directed, economically-motivated** graph.
- a real-time / "buy the supplier now before it reacts" tool — famous links price in seconds; the honest edge, if any, is the **slow multi-week drift on under-followed links** (the attention paradox).
- trusted as a buy signal before the drift test passes.

## 2. Evidence basis & the honest walls

- **Cohen & Frazzini (2008), *Economic Links and Predictable Returns*** (J. Finance): customer news predicts supplier returns over the following month because investors are **inattentive to the link.** This is the first project hypothesis with genuine published alpha backing.
- **Wall 1 — decay:** published 2008 → arbitraged; ~58% post-publication decay (McLean-Pontiff).
- **Wall 2 — the attention paradox (the killer):** the drift survives only where there is inattention → **obscure** links. Famous links (Walmart→McKesson, NVDA→TSMC) are priced. But obscure links are exactly where **free data does not exist**. *Where it's knowable it's priced; where edge remains it's unknowable.* The test must therefore **split famous vs obscure** links and report the edge separately — the prediction is that any residual edge concentrates in the obscure tail.
- **Data is the bottleneck, not theory:** real links come from 10-K customer-concentration disclosures (messy) or paid feeds (Bloomberg SPLC / FactSet Revere). v1 seeds **by hand**, acknowledging the seeded links are the *famous, priced* ones — so an honest null is the expected base case.

## 3. Data reality

- **Existing skeleton:** `config/relationships/supply_chain.yaml` already encodes directed `leaders → followers` with `typical_lag_days` + `inverse`, loaded by `CorrelationAnalyzer._merge_manual_overrides` into `CorrelationEdge(relationship_type="supply_chain")`. Today it holds **10 theme/bucket groups**, not true customer→supplier pairs.
- **Phase C adds** a distinct relationship type — **`economic_link`** (directed customer→supplier with a sourced rationale) — seeded with ~15 hand-curated pairs the user knows (Walmart→McKesson, the semis equipment/memory chain, etc.), each with a `source` (10-K citation or note) and an `attention` tag (`famous` | `obscure`).
- **Event trigger:** reuse `NewsHeadlinePort` + the Gemini `EventClassifierPort` to detect a material customer event; reuse `EventImpactAnalyzer` decay for the alert half-life. (Existing event propagation is sector-level; Phase C routes it through the **directed pair** instead.)

## 4. Architecture (hexagonal, reuse-heavy)

```
config/relationships/                domain/ (pure)                application/
 economic_links.yaml (new seed) ──►   econ_link (new): graph     ◄─ EconomicLinkResearchUseCase (new)
adapters/ (reuse)                     traversal, label, decay    ◄─ EconLinkDriftBacktestUseCase (new)
 news + Gemini classifier ────────►   models: EconomicLink,         (reuse) precision_metrics, costs,
 CorrelationAnalyzer (extend) ────►   LinkAlert                     point-in-time guards
```

- **`domain/econ_link.py`** (pure): load directed links; `linked_suppliers(customer) -> list[EconomicLink]`; `decay_weight(days_since_event, half_life)`; `LinkAlert(customer_event, supplier, relationship, attention_tag, why, label="RESEARCH_ONLY")`.
- **`EconomicLinkResearchUseCase`**: on a customer event (or a holdings/watchlist trigger), emit `LinkAlert`s for linked suppliers → feed the Phase-B brief's "RESEARCH LINKS" section. **No buy signal; research prompt only.**
- **`EconLinkDriftBacktestUseCase`**: the pre-registered test (Section 5) — point-in-time customer-event windows → supplier forward returns → reuse `precision_metrics` block-bootstrap + `TransactionCostModel`.
- **CLI:** `research-links [--ticker T]` (show linked names + why); `backtest-econ-link-drift` (pre-registered gate → JSON report + verdict).

## 5. Validation (pre-registered — LOCK before first run)

**Claim under test:** after a customer firm's material event, the linked supplier earns a positive forward excess return (the Cohen-Frazzini drift), net of costs, OOS.

**Pre-registration (frozen before any result):**
- **Window/horizon:** customer events 2015–2026 (uses available news/event history), supplier forward **1-month** excess vs SPY, point-in-time, costs charged.
- **Gate:** mean supplier excess return **> 0** with block-bootstrap **CI excluding 0**, net of costs (ADR-046 rigor). Report effect size, n events, and date-level significance.
- **Pre-registered split:** report the edge **separately for `famous` vs `obscure`** links. Prediction: edge (if any) lives in `obscure`; a positive result driven only by `famous` links is treated as **priced-in artifact / suspect**, not a tradeable edge.
- **No tuning:** half-life and event-materiality thresholds frozen before the run.

**Outcome → LABEL:**
- **PASS** (obscure-tail edge clears the gate): the drift is real → **eligible for Phase D graft** (sized for decay).
- **FAIL / NULL** (CI spans 0, or edge only in famous links): link layer ships **research-only** — still valuable as discovery scaffolding (maps what touches what, makes the user a faster researcher), explicitly **not** a signal.
- **HALT:** too few clean events / data can't support a clean test → record the data limitation honestly; keep research scaffolding, drop the edge claim.

**Honest non-claims:** the seeded famous links are expected to be priced; an honest null here is a *success of the method*, not a failure of the project. The scaffolding's value does not depend on the drift being real.

## 6. Privacy & honesty
- Links and alerts are public-company facts → no privacy surface; holdings-triggered alerts keep ADR-047 masking.
- Every `LinkAlert` is labelled `RESEARCH_ONLY` and renders as "go research," never "buy."
- The backtest prints the famous/obscure split so a priced-in artifact can never masquerade as edge.

## 7. Testing
- `domain/econ_link.py`: unit + Hypothesis (directed traversal returns only suppliers of the queried customer; `decay_weight` ∈ [0,1] and monotone decreasing; alert label always RESEARCH_ONLY).
- `EconLinkDriftBacktestUseCase`: planted-drift fixture (harness recovers it) + zero-drift fixture (no false PASS) + famous/obscure split correctness.
- YAML loader: malformed/missing-ticker rows skipped (mirror `_merge_manual_overrides`); economic_link kept distinct from supply_chain theme groups.
- `make check` green (mypy strict, 90% cov).

## 8. Open questions for reviewer
1. Seed list: which ~15 links does the user trust enough to hand-curate first? (Walmart→McKesson + the semis chain are givens; needs the user's own set.)
2. Event trigger source: Gemini-classified news (richer, API cost/keys) vs a simple price-move/volume threshold on the customer (free, cruder)? (Lean: price-move threshold v1, Gemini optional.)
3. Is 10-K customer-disclosure auto-extraction worth a later sub-project, given the auto-extracted *obscure* links are exactly where any real edge would live (but also where extraction is hardest)? (Flag for a future phase, not C.)

---

## 9. Phase Exit Gate → Phase D entry (validate-as-we-go)

**Before Phase D is even considered, confirm and record:**
- [ ] `backtest-econ-link-drift` run on the LOCKED pre-registration; verdict (PASS / FAIL / HALT) + the famous/obscure split recorded in `data/reports/`.
- [ ] Research/alert scaffolding ships into the Phase-B brief regardless of the verdict, labelled `RESEARCH_ONLY`.
- [ ] `make check` green.

**Intercept rule:** Phase D **only runs if at least one** of {Phase-A screen PASS, Phase-C drift PASS (obscure-tail), discipline July gate PASS (ADR-048)} produced a validated edge. If **all three are null** — the most likely outcome on the honest priors — **Phase D does not execute.** The engine then ships as **research + discipline + abstaining-screen**, which is a complete, honest product. Record this branch explicitly with the user; it is a pre-agreed success state, not a failure.

**Discovery checkpoint:** if the drift PASSES only on famous links, treat it as priced-in and *do not* graft it — note the temptation and resist it (this is exactly the p-hacking the gates exist to stop).
