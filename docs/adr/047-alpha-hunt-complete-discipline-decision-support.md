# ADR-047: Alpha-Hunt Declared Complete → Build an Honest Discipline / Risk Decision-Support Tool

**Date:** 2026-06-08
**Status:** Accepted
**Deciders:** Tirth Joshi
**Builds on:** ADR-039 (no conviction edge), ADR-043 (conviction dims dead), ADR-044 (no divergence IC), ADR-045 (pivot to discipline), ADR-046 (momentum/exit KILL)

## Context

Four independent, pre-registered falsification tests have now rejected every variant of the project's founding thesis — that retail-accessible public signals predict returns:

- ADR-039 — conviction aggregation: no out-of-sample edge (56%, p=0.13).
- ADR-043 — 6/8 conviction dimensions dead/degenerate.
- ADR-044 — intensity-divergence: no cross-sectional IC on a clean 430-ticker universe.
- ADR-046 — momentum + trailing-exit: no risk-adjusted edge net of costs (Sharpe-diff CI spans 0); drawdown-cut real (40%).

### Two questions were raised and investigated before accepting the conclusion

**1. "Is our data the bottleneck, not the theses?"** A forensic data-layer audit (2026-06-08) answered **no**:
- The two tests on the *cleanest* data killed *hardest*: ADR-046 used only yfinance daily prices (finance's gold standard); ADR-044 ran on the clean 83%-coverage Wikipedia attention map. Neither verdict is rescuable by better data.
- Genuinely dead/noisy sources exist (StockTwits 403; GDELT free-tier 429 — plus a real silent-`""` bug; Google Trends throttled; SEC EDGAR structurally empty for mid-caps) but **none were load-bearing** for the kills.
- The one untested thread (full 8-dim conviction on a clean universe) is untestable because 6/8 dims need data that *structurally does not exist* for mid-caps (no 13D filings on small thematic names) — an economic reality, not a hygiene problem.
- Conclusion: **semi-strong market efficiency holds for retail-accessible public signals.** The edge isn't in the pipeline; it isn't there.

**2. "What actually works for retail, then?"** A cited deep-research pass (2026-06-08) established the realistic landscape:
- ~70% directional accuracy is fantasy (Renaissance Medallion runs ~50.75% per trade); 50% is the losing null. **Profitability = expectancy (asymmetry), not hit-rate.**
- LLMs explain well, predict badly (StockBench, arXiv 2510.02209) → narrator, never picker.
- Real, retail-accessible, non-predictive effects: behavior-gap closure (~115–122 bps/yr, Morningstar/academic — the disposition effect), conditional volatility targeting (Sharpe ~0.40→0.50; conventional form *backfires on TSX/Canada* — use conditional), trend/stop drawdown reduction (ADR-046: 38→23% maxDD, cost-robust), factor premia (decayed 58% post-publication, McLean-Pontiff).
- **No single edge — a stack of small, honest, non-predictive edges that compound.**

## Decision

**Declare the alpha hunt complete.** Stop trying to predict/select winners from public signals — four pre-registered tests is sufficient evidence; continuing would be p-hacking.

**Build an honest discipline / risk decision-support tool for held positions** — the first slice (Leg-3, sub-project 1): the **Holdings Discipline & Risk Engine**.

1. **Identity:** decision-support co-pilot, **not** prediction/alpha. Impact on risk, behavior, decision quality, and position sizing — real but modest (~1%/yr behavior-gap + materially lower drawdowns). Measured against the **user's own behavior**, never the market.
2. **Components, each tied to evidence:** graded trend-health + conditional vol signal (TSX-safe) + relative-strength/regime context + trailing-stop expectancy + disposition/winner-past-stop behavior flags → a graded verdict (REDUCE/TRIM/REVIEW/HOLD/ADD_OK) with confidence that **abstains when signals conflict.**
3. **LLM = narrator only.** Free, local (Ollama), on-device, graceful template fallback; structurally cannot influence the verdict. A `NarratorPort` allows a cloud adapter swap later for heavier Phase-2 features — narration only.
4. **Validation is forward-tracked** (no trade-history exists to backtest against the user's past timing): warm-start base-rate priors from price history (point-in-time), then log verdicts and forward-score flag calibration (Brier) over ≥8 weeks. **KILL clause:** if flags are no better than chance, this layer is dropped too — honestly.
5. **Data realities locked in:** tax-loss-harvesting leg **dropped** (user is 65/66 in registered accounts; TLH worthless, and registered = no sell-tax friction, a discipline tailwind). Holdings stay local/gitignored; only ticker symbols ever reach yfinance.
6. **Scope discipline:** v1 = discipline/risk on existing holdings. **Phase 2 (factor-tilted candidate screening — "find new names") is deferred,** gated on v1 proving useful — same conditional discipline as ADR-044/046.

## Consequences

- The product's honest identity is settled: an **evidence-aggregator + risk/discipline co-pilot that abstains**, consistent with ADR-039/041. No alpha claim is made anywhere in the UI/output.
- The validation harness from ADR-044/046 (block-bootstrap, Sharpe-diff CI, cost model, look-ahead guards) is retained as a protected baseline for any future pre-registered candidate.
- Reopening the alpha search requires a *new* pre-registered hypothesis with its own locked gate and ADR — not tuning a dead one.
- **Honest framing to the user, recorded:** this is a "lose less / mess up less" tool, not a "win more" engine; its largest leg (behavior) only pays off if the user acts on the flags, and proof accrues over weeks of forward-tracking.
