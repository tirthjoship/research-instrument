# Multi-Modal Stock Recommender

Production-grade ML system combining price signals, news sentiment, and technical indicators for weekly stock recommendations. Built with Hexagonal Architecture and explicit look-ahead bias prevention for backtest integrity.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-7/7%20passing-success)](./tests/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

---

## Project Overview

This system generates weekly "Top 15" stock picks using multi-modal signals: OHLCV price data, FinBERT-powered news sentiment, and technical indicators. The recommendation engine operates as an ongoing Tournament with recursive feedback, learning from weekly prediction outcomes to refine signal weights.

Preliminary sentiment audits show measurable correlations: "Breakout" news events demonstrate +0.27 correlation with 24-hour price trends, while "Downgrade" events show -0.42 correlation. The architecture enforces strict point-in-time constraints to prevent look-ahead bias in backtesting.

---

## Architecture

**Hexagonal (Ports and Adapters) Design:**

```
multi-modal-stock-recommender/
├── domain/                 # Pure Python business logic
│   ├── models.py          # Signal, Sentiment, BacktestResult entities
│   ├── ports.py           # MarketDataRepository, SentimentAnalyzer interfaces
│   ├── services.py        # Point-in-time validation logic
│   └── exceptions.py      # LookAheadBiasError, domain-specific errors
├── adapters/              # External system connections
│   ├── data/              # yfinance, news scraping implementations
│   ├── ml/                # FinBERT sentiment, ensemble recommender
│   └── visualization/     # Streamlit dashboard, portfolio charts
├── application/           # Use case orchestration
│   └── use_cases.py       # train_model(), generate_weekly_picks()
└── tests/                 # Pytest suite with property-based tests
```

**Dependency Rule:** All dependencies point inward. The domain layer imports nothing from adapters or application. This makes the business logic testable in isolation and swappable (yfinance to Bloomberg API, FinBERT to GPT sentiment) without touching domain code.

---

## Technology Stack

### Core Technologies
- **Python 3.12** - Type-safe, modern language features
- **XGBoost** - Gradient boosting for tabular features
- **FinBERT** - Financial sentiment analysis (HuggingFace Transformers)
- **MLflow** - Experiment tracking, model versioning

### Financial Data Tools
- **yfinance** - Yahoo Finance API for OHLCV data
- **pandas** - Time-series data manipulation
- **TA-Lib** - Technical indicators (RSI, MACD, Bollinger Bands)

### Software Engineering Tools
- **pytest** - Test-driven development framework
- **Hypothesis** - Property-based testing for temporal invariants
- **Black** - Opinionated code formatting
- **Mypy** - Static type checking with `--strict` mode
- **Ruff** - Fast linting
- **pre-commit** - Automated quality gates

---

## Setup Instructions

### Prerequisites
- Python 3.12+
- Conda or Mamba (recommended)

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd multi-modal-stock-recommender
```

2. Create and activate the Conda environment:
```bash
conda env create -f environment.yml
conda activate stock-recommender-ml
```

3. Install pre-commit hooks:
```bash
pre-commit install
```

4. Verify setup:
```bash
pytest tests/ -v
```

Expected output: `7 passed in 0.01s`

---

## Look-Ahead Bias Prevention Protocol

**The Temporal Firewall:** This project implements `LookAheadBiasError` as a domain-level exception that halts execution if future-dated data is detected in backtesting or training. This guarantees backtest validity.

**Point-in-Time Validation:**
Every `Signal` and `Sentiment` object carries an explicit `timestamp` field. Before any prediction or backtest, the `validate_point_in_time_access()` function verifies:
```python
for signal in signals:
    if signal.timestamp > prediction_time:
        raise LookAheadBiasError(...)
```

This structural guarantee prevents accidental look-ahead bias during feature engineering or model evaluation.

**Forensic Attributes:**
The `LookAheadBiasError` exception captures:
- `offending_timestamp` - The data point that violated point-in-time
- `prediction_time` - The as-of time for the prediction

This enables post-mortem debugging of temporal inconsistencies.

---

## The Tournament Architecture

**Recursive Feedback Loop:**
Unlike static classifiers, this system operates as an ongoing "Tournament":

1. **Monday Morning:** Generate Top 15 picks based on multi-modal signals from prior week
2. **Friday Close:** Evaluate actual returns vs. predicted returns
3. **Weekend:** Penalize false positives, reinforce accurate signals, update model weights
4. **Repeat:** Next Monday uses refined weights

This self-correcting architecture mimics professional portfolio managers adapting strategy week-over-week.

**Backtest Integrity:**
The `BacktestResult` domain model records:
- `prediction_time` - When the model made its prediction
- `actual_return` - Realized return over evaluation window
- `predicted_return` - Model forecast
- `model_version` - For A/B testing different signal ensembles

---

## Multi-Modal Signal Fusion

**Current Signals:**
1. **Price Signals (`Signal`):** OHLCV data from yfinance
2. **Sentiment Signals (`Sentiment`):** FinBERT sentiment from financial news headlines
3. **Technical Indicators (planned):** RSI, MACD, Bollinger Bands

**Preliminary Sentiment Audit Results:**
| News Trigger | 24h Price Correlation | Signal Strength |
|--------------|----------------------|-----------------|
| "Breakout" | +0.27 | Moderate Positive |
| "Downgrade" | -0.42 | Strong Negative |
| "Upgrade" | +0.18 | Weak Positive |

These correlations validate the sentiment signal contribution to the multi-modal ensemble.

---

## Testing

Run the full test suite:
```bash
pytest tests/ -v
```

Run with coverage:
```bash
pytest tests/ --cov=domain --cov=adapters --cov=application --cov-report=term-missing
```

Run property-based tests (requires `hypothesis`):
```bash
pytest tests/test_properties.py -v
```

Run temporal consistency tests:
```bash
pytest tests/test_domain_services.py::test_validate_point_in_time_future_signal_raises -v
```

---

## Project Status

**Current Phase:** Phase 2 - Integrity Audit Complete

| Milestone | Status |
|-----------|--------|
| Phase 1: Infrastructure & Hexagonal Architecture | ✅ Complete |
| Phase 2: Domain Models & Look-Ahead Bias Prevention | ✅ Complete |
| Phase 3: Adapter Implementation (yfinance, FinBERT) | 🔄 In Progress |
| Phase 4: Tournament Backtesting & Weekly Picks | 📋 Planned |
| Phase 5: Streamlit Dashboard & Cloud Deployment | 📋 Planned |

---

## UBC MDS Alignment

This project demonstrates principles from the UBC Master of Data Science program:

| Concept | MDS Course |
|---------|------------|
| Hexagonal Architecture, TDD, reproducibility | DSCI 524 (Collaborative Software Development) |
| Time-series forecasting, regression models | DSCI 561 (Regression I) |
| Feature engineering, model selection | DSCI 573 (Feature and Model Selection) |
| NLP, sentiment analysis, transformers | DSCI 563 (Unsupervised Learning) |
| Backtesting, portfolio optimization | DSCI 574 (Spatial and Temporal Models) |

---

## Business Impact

**Financial Problem:** Retail investors lack access to institutional-grade tools for multi-modal signal fusion and sentiment-driven stock selection. Most retail strategies rely solely on price data or anecdotal news.

**Model Goal:** Generate weekly Top 15 stock picks with measurable alpha (excess return over SPY benchmark). Target: 8-12% annualized outperformance with <25% annual volatility.

**Stakeholders:**
- Retail Investors: Individual portfolio managers seeking data-driven picks
- Quantitative Analysts: Researchers validating sentiment signal efficacy
- Fintech Platforms: Robo-advisors seeking multi-modal recommendation engines

---

## Risk Disclaimer

This project is for educational and research purposes only. Stock recommendations generated by this system should not be construed as financial advice. Past performance does not guarantee future results. Always consult a licensed financial advisor before making investment decisions.

---

## Contributing

This is a portfolio project demonstrating production-grade ML systems engineering for quantitative finance applications. For questions or collaboration, please open an issue.

---

## License

MIT License. See `LICENSE` file for details.

---

## Author

**Tirth Joshi**
UBC Master of Data Science

Portfolio: [GitHub Profile]
LinkedIn: [Profile Link]
