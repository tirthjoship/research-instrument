# Unit A — Macro-Beta Scrubber (Design Spec)

**Date:** 2026-06-09
**ADR:** ADR-052 (CRO direction — alpha hunt closed; engine = deterministic risk/behavior CRO)
**Effort:** LOW build / MAX verify (Sonnet implement, Opus verify)
**Branch:** `feat/macro-beta-scrubber` (off `develop`)

## Problem

The 66-name book looks diversified by ticker count but may be a small number of
concentrated **macro factor bets** in disguise. "66 ideas" can really be "one
long-duration rate bet." The discipline pillar grades individual holdings; nothing
currently exposes the book's hidden *systematic* exposure. This is the Portfolio Risk
pillar of the CRO (ADR-052, Unit A).

Cluster/concentration flagging already exists in `domain/brief.py` (ticker-cluster
overlap at 0.20 threshold via `CorrelationAnalyzer`). Macro-beta is the **superior,
factor-level** form of hidden-concentration detection — a book can be cluster-diversified
yet be a single macro wager. We do **not** rebuild cluster caps here; the factor view
subsumes most of that value. Cluster-cap hardening is deferred (revisit in Unit C if a
gap remains).

## Scope

**In:**
1. Macro-beta scrubber: per-holding factor betas + dollar-weighted book net-beta per
   factor + systematic-vs-idiosyncratic variance split.
2. Flag policy folded into `weekly-brief`.
3. Fix stale screen universe (prune delisted tickers).

**Out (deferred):**
- Cluster exposure caps hardening (Unit C candidate).
- Behavior plumbing / throttles (Unit C).
- Rolling/EWMA beta time series (over-built for weekly cadence).

## Methodology decisions (locked)

- **Regress returns, not price levels.** Daily simple returns, de-meaned. Price-level
  regression is spurious (non-stationary, inflated R²).
- **Factor model:** `r_holding = α + Σ βₖ·r_factorₖ + ε`.
- **Factor set: SPY / TLT / UUP / XLE.**
  - SPY = market, TLT = rates (long-duration Treasuries), UUP = US dollar, XLE = energy.
  - **XLE chosen over USO** deliberately: USO tracks crude *futures* and is crippled by
    roll-yield/contango; it is not the energy-*equity* factor the equity book is exposed
    to. XLE is equity-energy — the correct factor.
- **Estimator: light-shrinkage Ridge** (alpha ≈ 0.1–0.3), `sklearn.linear_model.Ridge`
  fit on **raw de-meaned daily returns — NO `StandardScaler`.**
  - **Why no scaler (validation finding):** the existing `RidgePredictor` wraps a
    `StandardScaler` and never exposes `.coef_`, so it is unusable for beta extraction — a
    NEW adapter is required. We also fit on *raw* returns deliberately: standardizing X
    would make `.coef_` standardized-unit betas, contradicting the requirement to report
    raw dollar-interpretable betas. Daily factor returns are already on comparable scale,
    so a single `Ridge.fit(X=factor_returns, y=holding_returns)` yields `.coef_` that **is**
    the raw beta per factor (`.intercept_` ≈ 0 after de-meaning).
  - **Known trade-off (documented honestly):** Ridge shrinks coefficients toward zero, so
    reported betas are *conservative* (slightly understate true exposure). Acceptable for
    LOW build IF reported as "shrinkage-adjusted." **Escalation path:** if dogfood betas
    look implausibly small, switch the estimator adapter to **orthogonalized OLS**
    (residualize TLT/UUP/XLE against SPY, then OLS — unbiased, cleanly interpretable). The
    port boundary makes this swap touch only the adapter.
- **Windows:** headline = 252 trading days (~1yr); drift = 63 days (~1 quarter). Run
  estimator twice per holding.
- **Reporting unit:** raw daily-return betas (so they translate to dollar P&L sensitivity),
  not standardized betas.

## Architecture (hexagonal)

| Layer | Element | Responsibility |
|---|---|---|
| `domain/ports.py` | `MacroBetaEstimatorPort` | `estimate(holding_returns: list[float], factor_returns: dict[str, list[float]], alpha: float) -> EstimationResult` (betas per factor + r_squared). Pure interface. |
| `adapters/ml/macro_beta_analyzer.py` | `RidgeMacroBetaEstimator` | implements port; `sklearn.linear_model.Ridge` on raw de-meaned returns (NO StandardScaler), reads `.coef_`. Only place sklearn is imported for this feature. NOT a reuse of `RidgePredictor` (which hides `.coef_`). |
| `domain/macro_beta.py` | pure functions | dollar-weight per-holding betas → book net-beta per factor; book systematic share; flag policy. **stdlib only**, no sklearn. |
| `domain/models.py` | frozen dataclasses | `MacroFactorBeta`, `HoldingMacroExposure`, `BookMacroExposure`, `MacroBetaFlag` |
| `application/macro_beta_use_case.py` | `MacroBetaUseCase` | orchestrate: load prices → align → returns → estimate per holding (252d + 63d) → aggregate → `BookMacroExposure` |
| `domain/brief.py` | extend | add `macro: BookMacroExposure` to `WeeklyBrief` (class at L76); render in `to_markdown()` (L218) + `to_stdout_masked()` (L298). `assemble_brief()` at L122 |
| `application/cli.py` | `_build_weekly_brief()` (L2763, called L2904) | wire `MacroBetaUseCase` into pillar composition |
| `config/markets/us.yaml` | config | new `macro_beta:` block — factor tickers, thresholds, windows, alpha (independent of existing `macro_symbols`, which uses yield *indices* unsuitable for return-regression) |
| `config/tickers/{sp500,nasdaq100,tsx60}.txt` | prune | remove delisted tickers |

**Rationale:** regression (sklearn) lives in the adapter; the CRO *judgment* (weighting,
thresholds, flag emission) is pure domain — unit- and property-testable without sklearn,
and the estimator is swappable behind the port.

## Domain model

```python
@dataclass(frozen=True)
class MacroFactorBeta:
    factor: str            # "SPY" | "TLT" | "UUP" | "XLE"
    beta_headline: float   # 252d window
    beta_recent: float     # 63d window
    drift: float           # beta_recent - beta_headline

@dataclass(frozen=True)
class HoldingMacroExposure:
    ticker: str
    weight: float                          # fraction of book market value
    betas: tuple[MacroFactorBeta, ...]
    r_squared: float                       # systematic share for this holding (252d)

@dataclass(frozen=True)
class MacroBetaFlag:
    kind: str        # "SYSTEMATIC_DOMINANT" | "FACTOR_DOMINANCE" | "DRIFT"
    factor: str | None
    message: str
    value: float
    threshold: float

@dataclass(frozen=True)
class BookMacroExposure:
    as_of: str
    factors: tuple[str, ...]
    net_beta_by_factor: dict[str, float]   # dollar-weighted Σ wᵢ·βᵢₖ
    systematic_share: float                # book-level R² (macro-explained variance)
    idiosyncratic_share: float             # 1 - systematic_share
    dominant_factor: str | None
    flags: tuple[MacroBetaFlag, ...]
    holdings: tuple[HoldingMacroExposure, ...]
    coverage_holdings: int                 # n holdings used
    total_holdings: int
    coverage_value_frac: float             # fraction of book value covered
```

## Data flow

1. `read_holdings(path)` → `list[holdings_reader.Holding]` (fields: `ticker`, `shares`,
   `cost_basis`, `account_type`). NOTE: use `application/holdings_reader.Holding`, **not**
   `domain/models.Holding` (a different, unrelated class with symbol/quantity fields).
2. For each holding **and** each factor ETF: `load_price_series(ticker, start≈300d ago,
   end=now)`. Inner-join on common dates across holding + all factors → daily simple
   returns.
3. Market value `valueᵢ = sharesᵢ × latest_closeᵢ`; book weight `wᵢ = valueᵢ / Σ value`.
4. Estimator per holding twice (252d headline, 63d drift) → betas + r².
5. Pure aggregator: `net βₖ = Σᵢ wᵢ·βᵢₖ`; book systematic share = R² of dollar-weighted
   book return vs factor-fitted return; emit flags per policy.
6. `assemble_brief(..., macro=BookMacroExposure)`; formatters render macro pillar.

## Flag policy (thresholds — UN-VALIDATED HEURISTICS, configurable)

> **Honesty note (ADR-039/052 stance):** these thresholds are surfacing dials, **not**
> empirically validated statistical claims. They decide *when to show a line in the
> brief*, nothing more. Documented as such in `us.yaml` comments and the brief footer.

- **SYSTEMATIC_DOMINANT** — `systematic_share > 0.60` →
  "N% of book variance is macro-explained; you hold ~K factor bets, not 66 ideas."
- **FACTOR_DOMINANCE** — for any factor, `|net βₖ| × typical_factor_move` implies
  `> 0.25` of book daily P&L → "net {factor} exposure dominates the book."
  (`typical_factor_move` = factor's own daily return std over the headline window.)
- **DRIFT** — for any factor, `|drift| / max(|beta_headline|, ε) > 0.50` →
  "{factor} exposure climbing fast (recent β diverges from 1yr β)."

Default values live in a new block in `config/markets/us.yaml` (independent of the
existing `macro_symbols` block, which holds yield/index proxies for other features):
```yaml
macro_beta:
  factors: [SPY, TLT, UUP, XLE]
  headline_window_days: 252
  drift_window_days: 63
  ridge_alpha: 0.2
  systematic_share_threshold: 0.60
  factor_dominance_threshold: 0.25
  drift_threshold: 0.50
```

## Error handling (no silent failures)

- Holding with `< window + 10` days of history (recent IPO) → **excluded**; counted in
  `coverage_holdings` gap. Logged.
- Factor ETF fetch fails → that factor **dropped** from the model, logged loudly, omitted
  from `factors`; book computed on remaining factors.
- Insufficient date overlap after inner-join → skip holding, report.
- Brief states coverage explicitly: "macro-beta computed on 61/66 holdings = 92% of book
  value." Never silently report a partial book as if complete.

## Universe fix

Prune confirmed-delisted tickers from `config/tickers/`:
- `sp500.txt` / `nasdaq100.txt`: SIVB, PXD, SPLK, WBA, WRK.
- `tsx60.txt`: GIB.A.TO, RCI.B.TO, TECK.B.TO (delisted/consolidated).

Mechanical edit; verify each removal against a current listing before deleting. Improves
evidence-screen candidate quality (live dogfood returned n=0 partly due to junk symbols).

## Testing (TDD)

- **Pure aggregator (`domain/macro_beta.py`):**
  - Unit: known per-holding betas + weights → assert net β, systematic_share, dominant_factor, flags.
  - **Hypothesis invariants:** weights sum to 1 → preserved; `systematic_share ∈ [0,1]`;
    `systematic + idiosyncratic = 1`; `net βₖ = Σ wᵢ·βᵢₖ`; empty holdings → safe abstain
    (zeros, no flags, coverage 0).
- **Estimator adapter (`RidgeMacroBetaEstimator`):**
  - Synthetic recovery: construct `holding = 0.5·SPY + 0.3·TLT + small ε` → assert recovered
    betas ≈ true within shrinkage tolerance; r² high. Fake price provider, small fixtures.
  - Degenerate: constant series, single factor, collinear factors → no crash, finite betas.
- **Use case (`MacroBetaUseCase`):**
  - Fake price provider with controlled series → end-to-end `BookMacroExposure` correct;
    coverage accounting correct when one holding lacks history and one factor fails.
- **Brief integration:** macro pillar renders in markdown + masked-stdout; coverage line
  present; flags appear when thresholds crossed.
- Small fixtures only, never full datasets.

## Definition of done

- All checks pass (mypy strict, black, pre-commit — never `--no-verify`).
- `weekly-brief` dogfood on the real 66-name book renders the macro pillar with real betas,
  variance decomposition, coverage line, and any triggered flags.
- Stale tickers pruned; screen universe verified clean.
- ADR cross-reference added (ADR-052 Unit A complete).
- Opus verification pass before merge.

## Verification focus (MAX verify)

1. **Returns not levels** — confirm regression inputs are returns, de-meaned; no price-level
   leakage.
2. **Shrinkage honesty** — betas labeled shrinkage-adjusted; sanity-check magnitudes in
   dogfood; escalate to orthogonalized OLS if implausibly small.
3. **Dollar-weighting correctness** — net β aggregation uses market value (shares × latest
   close), weights sum to 1, coverage fraction honest.
4. **No silent failures** — dropped holdings/factors surfaced in coverage line and logs.
5. **Thresholds framed as heuristics** — no language implying validated edge.
6. **Universe pruning** — each deleted ticker verified delisted, not a live name mistyped.
