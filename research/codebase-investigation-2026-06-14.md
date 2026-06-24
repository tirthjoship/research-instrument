# Codebase Investigation Report — 2026-06-14

Six targeted questions answered with file:line anchors. Live code findings only.

---

## 1. SCORECARD GRADES

### Where grades are defined

`domain/fit.py` contains the sole authoritative grade definition.

**Constants (domain/fit.py:23-24):**
```python
_GRADE_STRONG   = 0.80
_GRADE_MODERATE = 0.50
```

**Grade function (domain/fit.py:58-65):**
```python
def _grade(rank: float | None) -> str:
    if rank is None:
        return "UNKNOWN"
    if rank >= _GRADE_STRONG:      # rank >= 0.80
        return "STRONG"
    if rank >= _GRADE_MODERATE:    # rank >= 0.50
        return "MODERATE"
    return "WEAK"                  # rank < 0.50
```

### What `rank` is

`rank` = output of `composite_rank()` (`domain/fit.py:47-55`):
```python
def composite_rank(composite, universe_composites):
    beaten = sum(1 for c in universe_composites if c < composite)
    return beaten / max(n - 1, 1)
```
It is the **fraction of the screened universe the ticker beats** on composite score
(a percentile fraction [0,1] relative to all candidates in the latest `screen_*.json`).

### Full grade scale

| Rank range     | Letter displayed | Meaning in summary text                                    |
|----------------|------------------|------------------------------------------------------------|
| rank is None   | UNKNOWN          | "not in the latest screen"                                 |
| rank >= 0.80   | STRONG           | "top fifth of the screened universe on factual evidence"   |
| 0.50 <= rank < 0.80 | MODERATE    | "upper half of the screened universe on factual evidence"  |
| rank < 0.50    | WEAK             | "lower half of the screened universe on factual evidence"  |

*(Summary text: `domain/fit.py:186-199`)*

### Grade display in scorecard

`adapters/visualization/components/scorecard.py:16-22` defines rendering order and colors:
```python
_GRADE_ORDER = {"STRONG": 0, "MODERATE": 1, "WEAK": 2, "UNKNOWN": 3}
_GRADE_COLOR = {
    "STRONG": "#15803D",   # green
    "MODERATE": "#B45309", # amber
    "WEAK": "#B91C1C",     # red
    "UNKNOWN": "#5C6370",  # grey
}
```
Rows are sorted by `_GRADE_ORDER` in `rank_rows()` (`scorecard.py:31-32`).

### Batch-fit error path

When a ticker fetch fails (`application/batch_fit_use_case.py:76-93`), `evidence_grade` is forced
to `"UNKNOWN"` with a `DATA_GAP` `FitFlag`. The production `fit_fn` calls
`gather_and_assess()` (`application/fit_use_case.py:50-116`), which reads
`universe_composites` from the latest `data/reports/screen_*.json` and passes
them to `assess_fit()` → `_grade()`.

**"Evidence grade" is not named separately in domain/ — it is the `evidence_grade` field on
`FitVerdict` (`domain/fit.py:39-45`), set by `_grade(rank)`.**

There are NO letter grades (B+, C+, A) anywhere in the codebase. The system uses exactly four
word labels: STRONG / MODERATE / WEAK / UNKNOWN.

---

## 2. PERCENTILE SOURCE

### Where percentile is computed

`application/evidence_screen_use_case.py:119-141` — cross-sectional percentile per factor,
computed inline during the screen `run()` method.

**Algorithm (evidence_screen_use_case.py:129-141):**
```python
for k in FACTOR_KEYS:
    z_list = factor_z_lists[k]
    present_vals = sorted((v for v in z_list if v is not None), reverse=False)
    n_present = len(present_vals)
    per_item: list[float] = []
    for v in z_list:
        if v is None or n_present == 0:
            per_item.append(0.0)
        else:
            rank = sum(1 for pv in present_vals if pv < v)
            per_item.append(rank / max(n_present - 1, 1))
    factor_percentiles[k] = per_item
```

### What the percentile represents

- **Population**: all tickers that passed eligibility in the CURRENT screen run (trend-filtered subset of
  the 512-ticker universe). In `screen_2026-06-14.json` that is **304 candidates** out of 512 scanned.
- **Variable ranked**: the **winsorized z-score** of that factor (not the raw value), cross-sectionally
  across those 304 present tickers.
- **Formula**: `rank_below / (n_present - 1)` — fraction of present z-scores strictly below this
  ticker's z-score, scaled to [0, 1].
- **p95 meaning**: The ticker's factor z-score is higher than 95% of all z-scores for that factor
  among the current cohort of trend-eligible tickers. It does NOT refer to the broader 512-ticker
  universe or any sector sub-group.
- Tickers whose factor value is `None` get `percentile = 0.0` (flagged-neutral).

---

## 3. FACTOR SET

### Canonical factor keys

`domain/factor_scores.py:26`:
```python
FACTOR_KEYS = ("momentum", "revision", "quality", "value")
```

### Where each factor is computed

**MOMENTUM**
- Function: `momentum_12_1(monthly_closes)` — `domain/trend_rules.py:50-59`
- Formula: `monthly_closes[-2] / monthly_closes[-13] - 1.0`
- Raw inputs: monthly closing prices from the price adapter; requires ≥13 monthly closes; skips the
  most recent month (avoids bid-ask noise).
- Called in screen: `evidence_screen_use_case.py:90` via `trend_rules.momentum_12_1(self._price.monthly_closes(t))`

**REVISION**
- Function: `revision_momentum(estimate_series)` — `domain/factor_scores.py:29-36`
- Formula: `(last - first) / abs(first)` — normalized drift from oldest to newest analyst EPS estimate.
- Raw inputs: `analyst.estimate_series(ticker)` → `list[float]` of EPS estimate snapshots over time.
  Requires ≥2 estimates. Returns `None` if series is None or has < 2 entries, or if `first == 0`.
- Called in screen: `evidence_screen_use_case.py:91`

**QUALITY**
- No dedicated domain function; raw value obtained from `fundamentals.quality_value(ticker)["quality"]`.
- Live wiring (`application/cli.py:2554-2555`): `quality = info.get("return_on_equity") or info.get("profit_margins") or 0.0`
- Raw inputs: return on equity (preferred) or profit margins, sourced from yfinance `get_ticker_info()`.

**VALUE**
- No dedicated domain function; raw value from `fundamentals.quality_value(ticker)["value"]`.
- Live wiring (`application/cli.py:2558-2563`): `value = 1.0 / info["trailing_pe"] if trailing_pe > 0 else 0.0`
- Raw inputs: inverse trailing P/E ratio from yfinance.

### Composite formula

`domain/factor_scores.py:39-45`:
```python
def composite_score(sub_scores: dict[str, float | None]) -> float:
    """Equal-weight mean over the 4 factor keys. None = flagged-neutral (0.0)."""
    total = 0.0
    for k in FACTOR_KEYS:
        v = sub_scores.get(k)
        total += 0.0 if v is None else v
    return total / len(FACTOR_KEYS)   # denominator always 4
```

**Equal-weight mean of z-scores. Missing factors contribute 0.0 (pull composite toward center).
Denominator is always 4, so a missing factor dilutes the composite rather than being excluded.**

Each factor is first winsorized at 5th/95th percentile then z-scored cross-sectionally
(`evidence_screen_use_case.py:251-260`, calling `winsorize()` and `zscore()` from `domain/factor_scores.py:6-23`).

---

## 4. MOMENTUM / IC BACKTEST INFRA

### Infrastructure exists and is complete

`application/screen_ic_panels.py` — point-in-time panel builder (full file read above).
`application/ic_analysis.py` — Spearman rank-IC computation (stdlib only).
`application/screen_backtest_use_case.py` — gate logic (PASS / INCONCLUSIVE / HALT).

### Honesty constraint (documented explicitly)

`screen_ic_panels.py:1-11` (module docstring):
> "Only the MOMENTUM factor has clean point-in-time history derivable from prices. The other three
> composite factors (revision/quality/value) require point-in-time fundamentals / analyst snapshots
> that yfinance cannot supply for 2018-2026. Using current values at past dates would be catastrophic
> look-ahead bias."

The backtest therefore tests **MOMENTUM ONLY**; revision/quality/value are set to `None` throughout,
making the composite mathematically equivalent to momentum/4.

### CLI command to run

`application/cli.py:2702`:
```
python -m application.cli backtest-screen \
    --market us \
    --start 2018-01-01 \
    --end 2026-01-01 \
    --horizon-days 21 \
    --report-dir data/reports/
```

### Existing IC results

`data/reports/screen_ic_2026-06-08.json` — only existing IC report:
```json
{
  "as_of": "2026-06-08",
  "universe_size": 570,
  "n_tickers_with_data": 545,
  "decision": "INCONCLUSIVE",
  "mean_ic": 0.010689,
  "n_dates": 104,
  "ic_ci_low": -0.02927,
  "ic_ci_high": 0.042821,
  "sharpe_diff_point": -0.001856,
  "sharpe_diff_ci_low": -0.390778,
  "sharpe_diff_ci_high": 0.193838,
  "primary_pass": false,
  "secondary_pass": false,
  "horizon_days": 21,
  "start": "2018-01-01",
  "end": "2026-01-01",
  "caveat": "Composite tested on MOMENTUM leg only..."
}
```

**Interpretation:** mean IC = 0.011 (near zero). Bootstrap 95% CI = [-0.029, +0.043] — straddles
zero. Neither primary gate (CI must exclude 0 AND mean >= 0.02) nor secondary gate (Sharpe-diff CI
must exclude 0) fired. Decision: **INCONCLUSIVE** (not HALT — CI is not entirely negative).

This is the only backtest run on record. No per-sector or per-factor IC breakdowns exist in
`data/reports/`.

### Gate thresholds (screen_backtest_use_case.py:38-43)

- PASS: `ic_ci_low > 0 AND mean_ic >= 0.02` OR `sharpe_diff_ci_low > 0`
- HALT: `ic_ci_high < 0` (entirely negative CI)
- INCONCLUSIVE: neither fires

---

## 5. GEMINI ADAPTER

### Code status: SHIPPED (exists as live code)

`adapters/ml/gemini_narrator.py` exists and is fully implemented (59 lines, read above).

**It was planned in** `docs/superpowers/plans/2026-06-14-S2-gemini-cited-case.md` and the code
matches the plan exactly (Tasks 1–5 all stubbed out with checkboxes still unchecked in the plan,
but the actual implementation file is present).

### What it does

- Class: `GeminiNarratorAdapter` (`adapters/ml/gemini_narrator.py:39-58`)
- Model: `gemini-2.0-flash` (constant `_MODEL`, line 13)
- Port: implements `CaseSummarizerPort.summarize_case(ctx: CaseContext) -> CaseResult`
- Input: `CaseContext` (ticker, facts from RAG, news title/source pairs)
- Output: `CaseResult` (up to 5 `CasePoint` each for `in_favor` and `to_watch`)

### Honesty invariant (explicitly specified)

**Prompt constraint (`gemini_narrator.py:17`):**
> "Do NOT use the words buy, sell, predict, winner, conviction, alpha, or outperform."
> "This informs the reader; it is NOT a recommendation."

**Failure behavior (`gemini_narrator.py:44-58`):**
- No API key → `CaseResult((), (), True)` immediately (data_gap=True)
- Any exception (network, quota, parse) → `CaseResult((), (), True)` (data_gap=True, never faked)
- `parse_case_json()` on garbage → `CaseResult((), (), True)` (line 35)

**The adapter is explicitly NOT permitted to mutate or set evidence scores.** Its only output is
`CaseResult` (narrative text, source tags, data_gap flag). It has no access to `FactorScore`,
`composite_score`, `FitVerdict`, or `evidence_grade` — these live in separate domain objects.
The plan spec states (S2 Self-Review §4): "failure → data_gap=True (never faked); rendered-output
forbidden scan; prompt forbids trade verbs + 'informs, not a recommendation'."

### FORBIDDEN_WORDS in domain/fit.py

`domain/fit.py:13-21`:
```python
FORBIDDEN_WORDS: tuple[str, ...] = (
    "buy",
    "sell",
    "winner",
    "conviction",
    "predict",
    "alpha",
    "outperform",
)
```
These seven words are the domain invariant. The Gemini prompt negates them by listing them verbatim
(the plan notes the source-scan exemption for the prompt file; honesty is asserted on rendered output
instead, via `test_template_case_output_has_no_forbidden_words`).

---

## 6. ABSTENTION / COMPOSITE HONESTY

### Memory claim vs live data

The memory note ("screener was silently dead... 512→0 abstention") referred to a historical bug
where `s.close` vs `s.price` caused 0 candidates. **That bug is now fixed.**

### Live screen_2026-06-14.json facts

```
abstained: False
universe_size: 512
scanned: 512
had_history: 494
above_trend: 304  (trend filter applied here)
cleared: 304      (304 candidates passed into ranking)
```

### Factor population across all 304 candidates

| Factor   | Non-zero count | Out of 304 |
|----------|----------------|------------|
| momentum | 304            | 100%       |
| revision | 302            | 99.3%      |
| quality  | 304            | 100%       |
| value    | 304            | 100%       |

**All four factors are populated for virtually every candidate in the live 2026-06-14 run.**

### Example candidates showing all four live factors

SPG: momentum z=-0.117 (p59), revision z=+1.235 (p92), quality z=+2.827 (p95), value z=+1.295 (p87), composite=+1.310
APA: momentum z=+1.952 (p92), revision z=+0.208 (p50), quality z=+0.345 (p75), value z=+2.045 (p95), composite=+1.138

### Conclusion

The "momentum-only" claim in memory was true for the **IC backtest** (screen_ic_panels.py can only
backtest momentum due to point-in-time data constraints) but is NOT true for the **live composite**.
The live composite genuinely uses all four factors. The IC backtest result (mean_ic=0.011,
INCONCLUSIVE) applies to momentum alone and cannot be interpreted as measuring the full composite.

---

## Cross-component data flow summary

```
yfinance adapter
  ├── monthly_closes()  → momentum_12_1()        → z-score → factor_scores["momentum"]
  ├── trend_health()    → eligible() filter
  └── get_ticker_info() → ROE / profit_margins    → z-score → factor_scores["quality"]
                          1/trailing_pe            → z-score → factor_scores["value"]

analyst adapter
  └── estimate_series() → revision_momentum()     → z-score → factor_scores["revision"]

composite_score() = equal-weight mean(z-scores) / 4   [domain/factor_scores.py:39-45]

composite_rank() = fraction of universe beaten         [domain/fit.py:47-55]

_grade(rank):                                          [domain/fit.py:58-65]
  >= 0.80 → STRONG
  >= 0.50 → MODERATE
  <  0.50 → WEAK
  None    → UNKNOWN

GeminiNarratorAdapter: summarizes cited news only → CaseResult (narrative)
  → never touches composite, grade, or factor_scores
```
