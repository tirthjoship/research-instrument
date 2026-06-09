# ADR-052: Course of Action — Deterministic Risk/CRO Engine (Alpha Hunt Closed by 3-Model Convergence)

**Date:** 2026-06-09
**Status:** Accepted
**Deciders:** Tirth Joshi
**Builds on:** ADR-045 (predict→discipline pivot), ADR-047 (discipline tool), ADR-048 (forward gate), ADR-049 (engine consolidation), ADR-050 (trend-following INCONCLUSIVE), ADR-051 (calibration-readiness)

## Context

Six pre-registered falsifications (ADR-039/043/044/046/049/050) killed predictive alpha from public signals. This session added three confirmations that the alpha hunt is over:

1. **Live dogfood of the weekly brief** (`weekly-brief` on the real 66-name book): the **discipline/holdings side rendered real, actionable output** (21 REDUCE / 22 TRIM / 9 HOLD / 14 ADD_OK); the **evidence-screen/buy side returned n=0 — it abstained.** The tool already tells the truth: deterministic risk/discipline works, prediction abstains. (It also exposed a real bug: the screen universe is stale — SIVB, PXD, SPLK, WBA, WRK, several `.TO` names delisted.)
2. **Independent strategic review from ChatGPT and Gemini**, each given an honest ground-truth prompt (the built + falsified lists embedded so the model could not hallucinate our stack — Gemini's prior round had invented "FinBERT," which we rejected in ADR-004). **Both converged with our own analysis:** the deterministic risk/behavior tool is the ceiling; there are no credible new public-data alpha bets; *"your code needs to become your CRO."*

Three independent honest assessments now agree. The convergence is the finding: a retail-accessible predictive edge in public data does not exist (semi-strong efficiency; the cleanest data killed hardest — data is not the bottleneck).

## Decision

**Adopt the deterministic risk / CRO engine as the product direction.** Profitability for one retail investor = risk mitigation + behavior-gap closure (~848 bps/yr disposition effect) + not overtrading — **not** market-beating prediction. The "recommender" stays an **abstaining evidence screen (RESEARCH_ONLY), never a predictor.** Any predictive claim remains pre-registration-gated.

### Salvaged-idea triage (from the ChatGPT/Gemini slates)

- **BUILD (deterministic, high-EV, novel):**
  - **Macro-beta exposure scrubber** (Gemini G2) — Ridge-regress the book against TLT (rates), UUP (dollar), USO/XLE (energy), SPY (market) to expose hidden macro bets ("66 diversified names = one rate-duration bet"). The standout new idea.
  - **Cluster exposure caps / hidden concentration** (ChatGPT C2) — correlation + `supply_chain.yaml` graph → explicit exposure-budget policy ("NVDA+MU+WDC+AMD = one 22% cluster").
  - Together = the **Portfolio Risk pillar** (the CRO function), reusing existing Ridge + `correlation_analyzer` + `supply_chain.yaml` + networkx.
- **ONE sanctioned predictive swing:** **sub-$1B non-routine insider clusters** (Gemini G5) — the only idea with a *structural* non-arbitrage argument (institutions cannot fit into $300M names; retail size is a real execution advantage there). Never tested in isolation, market-cap-tercile-split. Cheaply falsifiable on the existing SEC Form-4 + IC/bootstrap harness. **Low odds — likely KILL like the other six; even a positive IC may not survive small-cap slippage.** It is the last sanctioned swing; if it KILLs, prediction is permanently off the table.
- **REJECT:** tax-loss harvesting / wash-sale optimizer (ChatGPT C1, Gemini G3) — **moot: 65/66 accounts are registered** (no cap-gains/wash-sale to harvest; both models missed this); 13F drift (low EV); index-deletion (arbitraged, episodic); Shannon's-demon vol-harvest (real but small in an all-equity book — defer).

### Execution order

- **Unit A — Portfolio Risk pillar (CRO):** macro-beta scrubber → cluster exposure caps → fold into the weekly brief + fix the stale screen universe.
- **Unit B — insider sub-$1B IC falsification** (pre-registered, killable).
- **Unit C — behavior plumbing:** anti-overtrade throttle (ChatGPT C4) + cash-buffer/deployment policy (ChatGPT C6), folded into the discipline engine.
- **Background (no build):** the weekly-Saturday discipline job (`com.tirthjoshi.stockrec.discipline-weekly`, ADR-048/051) accrues the forward gate sample; the gate resolves ~mid-July and decides whether the *holds* side is validated.

Rationale: deterministic value before the speculative swing (A is useful regardless of B's outcome); dependencies respected (cockpit fold needs the pillar); the edge question (B) resolves *after* value is banked, so a likely KILL is closure, not loss.

## Consequences

- The alpha hunt is **formally closed** — three independent honest assessments agree. The product is an honest CRO (risk + behavior + abstaining screen + discipline), not a market-beater.
- The disposition-auditor idea both external models proposed is **already built** — it is `resolve-discipline-flags` + the ADR-048 forward gate; do not rebuild it.
- Each Unit follows the established flow: brainstorm → spec → plan → Sonnet implementers → Opus verification-before-completion; LOW effort for mechanical build, MAX for verdict/verification.
- Honesty rails locked: recommender abstains; no FinBERT / LangChain / Neo4j / paid data; deterministic ideas claim no alpha; predictive ideas are pre-registered and killable.

## Unit A — Macro-Beta Scrubber (DONE 2026-06-09)

Shipped the macro-beta scrubber: per-holding Ridge betas on SPY/TLT/UUP/XLE (raw
de-meaned daily returns, NO StandardScaler, so coefficients are raw,
dollar-interpretable betas), dollar-weighted book net-beta, book
systematic-vs-idiosyncratic variance split, three heuristic flags
(SYSTEMATIC_DOMINANT / FACTOR_DOMINANCE / DRIFT), folded into `weekly-brief`
(markdown full detail + ADR-047-masked stdout aggregates).

Methodology note (honest): the Ridge `alpha` is scaled internally by mean
factor-return variance, making it a scale-invariant relative shrinkage fraction
rather than a literal sklearn penalty (raw daily-return variance ~1e-4 would make
a literal alpha=0.05 over-shrink true betas ~57%). Betas remain raw/interpretable;
only the penalty is rescaled. `ridge_alpha=0.2` in config = light shrinkage.

Universe fix: pruned 5 genuinely-delisted US screen tickers (SIVB/PXD/SPLK/WBA/WRK,
all 0 rows from yfinance). The TSX names GIB.A/RCI.B/TECK.B were NOT pruned — they
are live (CGI/Rogers/Teck); their dogfood failure is a dot-vs-dash symbol-format
mapping issue (yfinance wants GIB-A.TO), a separate data-layer bug logged as a
follow-up, not a delisting.

Thresholds are heuristic surfacing dials, not validated edges. Cluster caps
deferred (factor view subsumes them). Next: Unit B (sub-$1B insider-cluster IC).
