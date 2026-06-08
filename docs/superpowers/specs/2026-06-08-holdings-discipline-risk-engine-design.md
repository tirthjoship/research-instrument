# Holdings Discipline & Risk Engine — Design Spec

**Date:** 2026-06-08
**Status:** Draft for review
**Author:** Tirth Joshi (with Claude)
**Follows:** ADR-045 (pivot to discipline), ADR-046 (momentum/exit KILL — drawdown-cut real, prediction dead)
**Phase:** Leg-3, sub-project 1 (the first honest, impact-driving slice after 4 falsifications)

---

## 1. What this is — and what it is not

A **decision-support co-pilot for the holdings you already own.** It reads each position's risk state from price history, interrupts the specific behavioral mistakes that cost you money (holding broken-trend losers, riding winners past their stop), surfaces book-level concentration risk, and calibrates its own trustworthiness over time. A free local LLM narrates *why* — it never picks or scores.

**It is explicitly NOT:**
- a return predictor or stock picker (falsified 4× — ADR-039/043/044/046)
- an alpha / "beat the market" engine
- an auto-trader (report + log only; you act)
- a tax-loss-harvesting tool (your accounts are 65/66 registered — TLH is worthless here)
- a new-name screener (that is Phase 2, gated on this proving useful)

**The honest value proposition:** *make your already-excellent picks survive better and your mistakes smaller.* Impact is on **risk, behavior, decision quality, and position sizing** — real but modest (~1%/yr behavior-gap closure + materially lower drawdowns), **not** on prediction. If the goal were "win more / pick winners," this is not that, and nothing we have found is.

## 2. Evidence basis (why these components, not others)

Every component maps to a peer-reviewed or decades-OOS-validated effect (see the 2026-06-08 deep-research findings):

- **Behavior gap is real and capturable:** the average investor lags the index ~115–122 bps/yr (Morningstar 10-yr; academic), more for active traders — driven by the disposition effect. Discipline that interrupts it is the single largest honest lever. ([Morningstar/DALBAR], [Barclays])
- **Conditional volatility targeting** lifts US-equity Sharpe ~0.40→0.50 and cuts tail risk — but **conventional** vol-targeting *backfires in Canada/UK/Australia* (bigger drawdowns); only the **conditional** form is safe. Critical because ~half the book is TSX. ([CFA Institute, Conditional Volatility Targeting, 2020])
- **Trend / trailing-stop discipline** reliably cuts drawdown (our own ADR-046: 38%→23% maxDD, cost-robust) though its return edge is not significant in a bull window — so we use it as a **risk overlay**, not a timing oracle.
- **Factors decay** 58% post-publication (McLean-Pontiff 2016) — so factor tilts are deferred to Phase 2 and will be sized small.
- **LLMs explain well, predict badly** (StockBench, arXiv 2510.02209, Oct 2025: most LLM agents fail to beat a simple baseline) → LLM is a **narrator only**.

## 3. Data reality (drives the validation design)

From the user's brokerage export (`data/personal/holdings-report-2026-06-07.csv`, gitignored):
- **Has** per-position cost basis (Book Value), market value, unrealized P&L, account type, exchange.
- **No** trade dates / transaction history → we **cannot backtest the discipline against the user's past timing.** Validation is **forward-tracked** from launch.
- Account mix: TFSA 38, FHSA 20, RRSP 7, Non-registered 1 → **registered-dominant.** Consequences: (a) no tax-loss-harvesting leg; (b) **no capital-gains friction on selling** → disciplined exits are *easier* to follow than for a taxable investor (a tailwind for the tool's usefulness).
- **History we DO have:** ~8 years of clean yfinance daily prices for liquid US + TSX names → enough to **warm-start** every signal and the base-rate calibration on day 1.

## 4. Architecture (hexagonal, reuse-heavy)

```
adapters/                domain/  (pure, stdlib)          application/
 OllamaNarrator   ───►   trend_rules (extend)      ◄───   HoldingsRiskAssessmentUseCase
 yfinance (reuse) ───►   discipline (new)          ◄───   WarmStartCalibrationUseCase
 holdings CSV reader ►   calibration (new)         ◄───   (reuse) outcome tracking (Phase 8)
                         models: PositionRisk,
                         PortfolioRisk, DisciplineVerdict
```

Domain stays pure (stdlib only — no numpy, per the hard rule). Adapters and use cases may import libs. Look-ahead guards (`validate_point_in_time_access`, `LookAheadBiasError`) apply to every historical computation.

### 4.1 Domain — pure scorers & models

**Extend `domain/trend_rules.py`** (already has sma/atr/chandelier_stop/momentum_12_1/above_trend):
- `ma_slope(closes, window) -> float` — normalized slope of the moving average (trend direction/strength).
- `relative_strength(asset_closes, benchmark_closes, window) -> float` — excess return vs benchmark over window.
- `trend_health(price, sma_value, atr_value) -> float` — continuous distance from trend in ATR units (e.g. `(price - sma)/atr`), the graded replacement for the binary above/below.

**New `domain/discipline.py`** (pure):
- `conditional_vol_signal(recent_vol, baseline_vol, trend_health) -> float` — de-risk weight in [0,1], non-zero ONLY when vol elevated AND trend deteriorating (the TSX-safe conditional form; never de-risks on high vol alone).
- `risk_asymmetry(price, trailing_stop, recent_high) -> dict` — downside-if-trend-continues vs upside-given-up (expectancy framing, not a forecast).
- `is_disposition_risk(trend_health, unrealized_pct) -> bool` — broken trend held at a loss (the RIVN pattern).
- `is_winner_past_stop(trend_health, price, trailing_stop) -> bool` — in-trend winner that breached its trailing stop.
- `grade_position(sub_scores) -> DisciplineVerdict` — combines sub-scores into a graded verdict + confidence; **ABSTAINS to REVIEW when sub-scores conflict** (e.g. name weak but whole market weak too).

**New `domain/calibration.py`** (pure):
- `base_rate_from_history(trend_state_buckets) -> dict` — point-in-time empirical "when a name was in this trend state, distribution of what followed" (warm-start priors; no look-ahead).
- `brier_score(predicted_probs, outcomes) -> float` and `calibration_bins(...)` — track whether flags prove out.

**New domain models** (frozen dataclasses, validated):
- `DisciplineVerdict` — enum {REDUCE, TRIM, REVIEW, HOLD, ADD_OK} + `confidence: float` + `sub_scores: dict` + `why: str` (filled by narrator) + `abstained: bool`.
- `PositionRisk` — ticker, price, verdict, trend_health, vol_signal, relative_strength, risk_asymmetry, behavior_flags, cost_basis_context (unrealized %, account type, tax-friction flag).
- `PortfolioRisk` — book-level: % broken-trend, concentration (top-N weight), pairwise correlation clusters, count by verdict.

### 4.2 Application — orchestration

- `HoldingsRiskAssessmentUseCase(price_provider, narrator, benchmark="SPY")`:
  - per holding → fetch point-in-time history → compute sub-scores → `grade_position` → fold in cost-basis/account context → `PositionRisk`.
  - aggregate → `PortfolioRisk` (concentration via existing CorrelationAnalyzer if cheap; else simple top-N weight + broken-trend share).
  - returns a structured report; **never sends holdings/values anywhere — only ticker symbols reach yfinance.**
- `WarmStartCalibrationUseCase(price_provider)` — computes base-rate priors from history once, persists them.
- **Forward calibration:** reuse Phase-8 outcome tracking — log `verdict → user_action → outcome`; recompute Brier/calibration over time.

### 4.3 Adapters

- `NarratorPort` (domain port): `narrate(verdict, context) -> str`. Input is the **already-computed** verdict — the port **cannot influence** the score, only explain it (structural guarantee LLM never picks).
- `OllamaNarratorAdapter`: calls a local Ollama model over HTTP; **no-op graceful default** if Ollama is not running (returns a templated why-string), mirroring the existing Reddit/Gemini optional-adapter pattern. Zero API cost.
- `HoldingsReader`: reads the gitignored brokerage CSV; maps Symbol→yfinance ticker (TSX `.TO`, class-share dot→dash), extracts shares + cost basis + account type; skips non-numeric/blank rows. (Generalizes the sanitizer already written.)

### 4.4 CLI & cadence

- New command `holdings-risk --holdings <csv> [--narrate]` → graded report; writes full detail to a **gitignored** local file, prints a masked summary (counts + verdict distribution) to stdout by default.
- `holdings-risk-calibrate` → warm-start base rates from history.
- Daily (morning) + hourly (trading hours) via the existing scheduler/`daily-cycle`. **Report + log only — no orders.**
- Legacy `portfolio-verdict` (binary v1) kept but marked superseded.

## 5. Validation (ds-methodology — pre-registered, honest)

**Claim under test:** the discipline layer reduces drawdown / interrupts disposition mistakes **vs the user's own behavior** — NOT vs the market.

Because we have **no trade history**, validation is staged:
1. **Warm-start priors** from 2.5–8 yr history (point-in-time base rates) — grounds confidence on day 1.
2. **Forward-track** `verdict → action → outcome` from launch.
3. **Calibration metric (primary):** are REDUCE/TRIM flags followed by drawdowns more often than HOLD/ADD_OK? Track **Brier score + reliability curve** over ≥8 weeks before any "it works" claim.
4. **Behavior contrast:** on the same positions, compare *"disciplined-you"* (acted on flags) vs *"actual-you"* (what you did) — terminal P&L and max drawdown.

**Honest non-claims (stated up front):** we will NOT claim it predicts returns, beats the market, or has alpha. Success = **better-calibrated risk flags + measurable drawdown/behavior improvement vs your own baseline**, accrued over weeks. If calibration is no better than chance after the forward window → KILL this layer too, honestly.

**Anti-overfitting guard:** base rates computed strictly point-in-time; no tuning of thresholds to the current book; the conditional-vol and trend params reuse ADR-046's FROZEN values (200/22/3.0) — no re-tuning.

## 6. Scope

**v1 (this spec):** graded per-holding verdict + behavior interruption + conditional-vol/trailing-stop sizing signal + relative-strength/regime context + portfolio concentration + abstention + cost-basis/account context + LLM narrator (Ollama, graceful no-op) + warm-start calibration + forward outcome tracking + daily/hourly report-only cadence.

**Phase 2 (deferred, decide after using v1):** factor-tilted candidate **screening** (the "find me new names" engine) — momentum/quality/trend filter, framed as a filter never a forecast, sized for decay.

**Explicit non-goals:** prediction, auto-trading, tax-loss harvesting, sentiment/attention signals, screening-in-v1.

## 7. Privacy (hard requirements)

- Holdings CSV and all derived/output files stay under `data/personal/` (gitignored) — never committed, never to memory.
- Only **ticker symbols** ever leave the machine (to yfinance for prices). Shares, cost basis, account info, account numbers never transmitted.
- Local LLM = on-device, zero external calls for narration.
- CLI defaults to **masked** stdout (counts/distribution); full per-ticker detail only in the local gitignored file.

## 8. Testing

- Domain scorers: unit + Hypothesis property tests (e.g. trend_health monotonic in price; conditional_vol_signal zero when trend healthy; grade_position abstains on conflict). Small fixtures, no live APIs.
- Use case: fakes for price_provider + narrator; assert graded verdicts, portfolio aggregation, no-look-ahead.
- Narrator: fake adapter asserts it receives a computed verdict and cannot mutate it; Ollama adapter graceful-degradation test.
- CLI: masked-output test; gitignore-safety assertion.
- `make check` green (mypy strict, 90% cov) before any live run.

## 9. Open questions for reviewer

1. Portfolio concentration: reuse the existing `CorrelationAnalyzer` (heavier) or a lightweight top-N-weight + broken-trend-share for v1? (Lean: lightweight for v1.)
2. Ollama model choice (e.g. llama3.1:8b vs qwen2.5) — defer to implementation; port works with any.
3. Verdict taxonomy: REDUCE/TRIM/REVIEW/HOLD/ADD_OK — right granularity, or simpler?
