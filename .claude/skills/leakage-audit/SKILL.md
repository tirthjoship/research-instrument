---
name: leakage-audit
description: Audit the codebase for look-ahead bias — verify FUTURE_LEAKAGE_COLUMNS are excluded from all feature pipelines, no future-dated data reaches models or predictions.
---

Audit the multi-modal-stock-recommender project for look-ahead bias violations.

## What is look-ahead bias in this project?

In quantitative finance, look-ahead bias occurs when a model uses information that would not have been available at prediction time. This makes backtests look profitable while the live system fails.

**FUTURE_LEAKAGE_COLUMNS** that must never appear in feature matrices:
- `next_day_return` — future price data
- `next_week_return` — future price data
- `future_earnings_surprise` — post-event data
- `forward_pe_ratio` — uses future earnings estimates

**Point-in-time rule:** All data (signals, sentiment, news) must have timestamps <= prediction_time. Enforced by `validate_point_in_time_access()` in `domain/services.py` and `LookAheadBiasError` in `domain/exceptions.py`.

## Audit steps

### 1. Verify FUTURE_LEAKAGE_COLUMNS constant

```bash
grep -rn "FUTURE_LEAKAGE_COLUMNS" adapters/ application/ domain/
```

Confirm it contains all four columns. If missing any — **critical violation**.

### 2. Scan all adapters for leakage column access

```bash
grep -rn "next_day_return\|next_week_return\|future_earnings_surprise\|forward_pe_ratio" adapters/ application/ domain/
```

Any hit outside the constant definition = potential leakage. Investigate each match.

### 3. Point-in-time enforcement in adapters

For every data adapter in `adapters/data/`:
- Verify it accepts `prediction_time` parameter
- Verify it filters data to `timestamp <= prediction_time` before returning
- For yfinance: verify `end` date is set to prediction_time, not current date
- For RSS/news: verify `published_date` filter is applied
- For Reddit/StockTwits: verify post timestamps are checked

### 4. Feature engineering scan

For every file that constructs feature matrices:
- List ALL feature names
- Cross-reference against FUTURE_LEAKAGE_COLUMNS
- Check for subtle temporal leakage:
  - Rolling averages computed with future data points
  - Sentiment aggregation windows extending past prediction_time
  - Technical indicators using price data after prediction_time
  - Target variable (actual_5d_return) leaking into training features

### 5. Backtest integrity

```bash
grep -rn "BacktestUseCase\|backtest" application/ tests/
```

Verify:
- Backtesting iterates week-by-week, never peeking ahead
- Features are re-computed at each prediction_time
- Model is not retrained on future outcomes
- Tournament results from week N are not used to influence week N predictions

### 6. Scan notebooks for leakage

```bash
grep -rn "next_day\|next_week\|future_earnings\|forward_pe" notebooks/
```

EDA notebooks may reference these for analysis (OK). But if used in feature engineering — **flag as violation**.

### 7. Check evaluation metrics

```bash
grep -rn "accuracy_score\|accuracy" adapters/ application/ tests/
```

Flag accuracy as primary metric. This project requires:
- Sharpe ratio (risk-adjusted returns vs SPY)
- Directional precision/recall (did we predict direction correctly?)
- Per-grade accuracy (are Strong Buy picks better than Hold picks?)

### 8. Verify test coverage for leakage

```bash
grep -rn "LookAheadBias\|point_in_time\|leakage\|LEAKAGE\|future_dated" tests/
```

Verify tests exist that:
- Confirm future-dated signals raise LookAheadBiasError
- Confirm adapters filter by prediction_time
- Confirm feature matrices exclude FUTURE_LEAKAGE_COLUMNS
- Property test: no feature timestamp > prediction_time for any generated input

## Output format

```
## Look-Ahead Bias Audit — <date>

### FUTURE_LEAKAGE_COLUMNS constant
✅ All 4 columns present and enforced / ❌ Missing: <column>

### Adapter temporal filtering
- yfinance_adapter.py: ✅ filters by prediction_time / ❌ <issue>
- rss_adapter.py: ✅ / ❌
- reddit_adapter.py: ✅ / ❌
- google_search_adapter.py: ✅ / ❌
- stocktwits_adapter.py: ✅ / ❌

### Feature engineering
✅ No leakage in feature construction / ❌ <file>:<line> — <feature> leaks future data

### Backtest integrity
✅ Week-by-week iteration, no look-ahead / ❌ <concern>

### Notebook scan
✅ No leakage in feature engineering cells / ⚠️ <notebook>: <concern>

### Evaluation metrics
✅ Sharpe + precision/recall used / ❌ Accuracy-only at <file>:<line>

### Test coverage
✅ Leakage regression tests exist / ❌ Missing test for <scenario>

### Verdict
✅ No look-ahead bias detected
⚠️ WARN — <N> concerns to review
❌ FAIL — <N> violations must be fixed before any model training
```
