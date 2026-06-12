# Multi-Modal Stock Recommender

A weekly research cockpit for one family's portfolio. It flags risk concentrations,
tracks whether we follow our own discipline rules, and ranks stocks by factual evidence.
It does NOT predict returns — we tested that across 18 years of data and every idea
failed.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-1583%20passing-success)](./tests/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![mypy: strict](https://img.shields.io/badge/mypy-strict-blue.svg)](http://mypy-lang.org/)

---

## The verdict table

Seven independent questions were tested. Each was pre-registered (meaning the
pass/fail bar was locked in writing before any data was examined). Results:

| Question | Answer | How we know |
|---|---|---|
| Does community conviction predict returns? | No | Pre-registered out-of-sample backtest, 2006–2024 ([ADR-039](docs/adr/039-conviction-validation-findings.md)) |
| Do conviction sub-dimensions carry signal? | No | Dimension-by-dimension IC audit ([ADR-043](docs/adr/043-conviction-dims-dead-divergence-led-surfacing.md)) |
| Does sentiment-vs-price divergence predict returns? | No | Cross-sectional IC, clean 430-ticker universe ([ADR-044](docs/adr/044-divergence-ic-verdict.md)) |
| Do momentum exits beat buy-and-hold? | No | Sharpe-difference bootstrap, CI spans zero ([ADR-046](docs/adr/046-momentum-discipline-phase1-verdict.md)) |
| Does the evidence screen's top decile outperform? | Unproven | Forward IC test, still accruing ([ADR-049](docs/adr/049-decision-support-engine-architecture.md)) |
| Does a trend-following sleeve clear its bar? | Unproven | Pre-registered backtest vs locked gate ([ADR-050](docs/adr/050-trend-following-sleeve-verdict.md)) |
| Do insider buying clusters predict returns? | Can't tell — too little clean data (treated as No) | Event study with survivorship-honest coverage guard ([ADR-053](docs/adr/053-insider-cluster-falsification-verdict.md)) |
| Does the discipline tool beat your own behavior? | Verdict ~mid-July 2026 | Live forward gate, thresholds locked in advance ([ADR-048](docs/adr/048-discipline-forward-calibration-gate.md), [ADR-051](docs/adr/051-calibration-readiness-date-diversity.md)) |

---

## What the tool DOES do

**Weekly brief** — a plain-English Saturday morning summary: which macro factors are
driving the portfolio, what the evidence screen says about current holdings, and
whether any discipline rules were broken this week.

**Risk scrubber (macro-beta)** — fits a simple statistical model to expose how much
of the portfolio's movement is really just one big bet on the overall market; as of
the last real-book run, 63% of variance was one market factor (66 names, mostly one
leveraged market bet).

**Portfolio-fit verdict** — for any stock you look up, shows where it ranks on
factual evidence (valuation, quality, financial health) relative to the ~430-stock
universe, and flags whether adding it would deepen a risk concentration that already
exists in the book.

**Discipline tracker** — records whether the household followed its own stated rules
week by week; the forward calibration gate (ADR-048) will resolve in mid-July 2026
and tell us honestly whether the tool improved adherence.

**Falsification lab** — the full history of hypotheses tested, the exact pre-registered
thresholds, and the mechanically-executed kill decisions; archived in `docs/adr/`
(ADRs 039–053). The portfolio-fit verdict's honest-boundary design is recorded in
[ADR-054](docs/adr/054-portfolio-fit-verdict.md).

---

## How to run it

```bash
# Install
pip install -e ".[dev,dashboard]"
pre-commit install

# Launch the dashboard
streamlit run adapters/visualization/dashboard.py

# Run the Saturday discipline review job
bash scripts/discipline_weekly_review.sh

# Generate the weekly brief from the CLI
python -m application.cli weekly-brief --market us
```

---

## Glossary

Plain-English definitions for every term used in this project.

| Term | Meaning |
|------|---------|
| **Confidence interval (CI)** | The range the true average plausibly sits in. "CI low > 0" = even the pessimistic read is a profit. |
| **Slippage** | The hidden cost of actually buying a thinly-traded stock — you move the price against yourself. |
| **Tercile** | Split into thirds. "Bottom liquidity tercile" = the third of stocks that are hardest to trade. |
| **Abnormal return** | A stock's return minus what a comparable index did over the same days — the part the stock did "on its own." |
| **IC (information coefficient)** | Correlation between a signal's ranking and what actually happened next. Zero = the signal knows nothing. |
| **Sharpe ratio** | Return earned per unit of risk taken. Higher is better — it rewards steady gains, not lucky volatile ones. |
| **Bootstrap** | Re-running a test on thousands of resampled versions of the data to see how much of the result is just luck. A confidence interval that "spans zero" means the edge could easily be nothing. |
| **Pre-registration** | Locking the test rules before seeing results, so you can't move the goalposts. |
| **Look-ahead bias** | Accidentally letting future data leak into a prediction — makes backtests look great and live trading fail. |

---

## Architecture

Hexagonal (ports and adapters): the core business logic in `domain/` has zero
external library imports. Any data source, ML model, or dashboard can be swapped
without touching the rules. See [AGENTS.md](AGENTS.md) for coding standards and the
dependency contract.

```
domain/                          # Pure business logic (stdlib only)
  models.py                      # Signal, Sentiment, BuzzSignal, Holding, ...
  ports.py                       # MarketDataPort, SentimentPort, HoldingsPort, ...
  services.py                    # Grading, leakage detection, freshness
  exceptions.py                  # LookAheadBiasError, InsufficientDataError
  fit.py                         # Portfolio-fit verdict (evidence grade + fit flags)

adapters/
  data/                          # yfinance, RSS, Google Trends, StockTwits, GDELT,
                                 #   SEC EDGAR, SQLite store
  ml/                            # Feature engineers (101 features across 5 layers),
                                 #   XGBoost/LightGBM/Ridge/ensemble predictors,
                                 #   macro-beta Ridge estimator
  visualization/                 # Streamlit dashboard (multi-tab), data loader,
                                 #   chart builders, CSS components

application/
  cli.py                         # Click CLI (weekly-brief, screen-candidates, ...)
  weekly_brief_use_case.py       # Weekly brief orchestration
  macro_beta_use_case.py         # Book macro-factor exposure
  fit_use_case.py                # Portfolio-fit verdict input gathering
  evidence_screen_use_case.py    # Evidence screen (RESEARCH_ONLY, never a predictor)
  discipline_use_case.py         # Discipline / adherence tracking

config/
  markets/us.yaml                # US market configuration + locked gate thresholds
  tickers/sp500.txt              # ~503 S&P 500 constituents
  tickers/nasdaq100.txt          # ~101 NASDAQ-100 constituents
```

**Dependency rule:** All arrows point inward. `domain/` imports nothing from
`adapters/` or `application/`. Swapping a data source means writing a new adapter,
never touching business rules.

---

## The story

This project started as an attempt to beat the market using public data. The core
hypothesis was that when news sentiment and stock prices disagree — one bullish, the
other falling — that divergence predicts which way the price would resolve. A
reasonable idea. It was wrong.

Seven independent tests were run across 18 years of price history (2006–2024), each
with the exact pass/fail bar written down and locked before the data was examined.
Conviction signals: no edge. Sentiment divergence: no edge. Momentum exits: no edge
(the confidence interval on the improvement straddled zero — meaning the observed
gain could easily be noise). Insider buying clusters: the result was
"INCONCLUSIVE_THIN_COVERAGE" — 46.6% of the 28,866 events in the study had no
usable price history because those companies had since been delisted. The coverage
guard counted every unpriceable event against the test rather than silently dropping
it; that honest accounting fired the kill switch.

Why trust the kills? Three reasons. First, all thresholds were pre-registered — no
goalpost moved after the result was visible. Second, point-in-time discipline was
enforced in code: any prediction that accidentally touched future data raised a
`LookAheadBiasError` and halted the pipeline. Third, trading costs were included
in every backtest; a signal that looks profitable before costs and disappears after
them is not an edge, and we modeled the real cost of trading thinly-traded stocks
(called slippage).

What survived is not a predictor — it is a cockpit. The macro-beta scrubber showed
that the real family portfolio was, at the time of analysis, 63% driven by a single
market factor: 66 positions that looked diversified were mostly one leveraged market
bet. That finding is actionable and requires no forecasting. The discipline tracker
surfaces whether stated investment rules are actually followed week to week; that gap
between intention and behavior is the honest problem the tool now addresses. The
evidence screen ranks stocks by factual, point-in-time metrics (valuation, quality,
financial health) and explicitly labels its output RESEARCH_ONLY — it does not
recommend buying or selling.

The forward calibration gate (ADR-048) is the one open verdict: a pre-registered
test of whether the discipline tool improves adherence, resolving mid-July 2026. The
thresholds were locked before any live data accrued. The result will be reported
honestly, whatever it is.

For a recruiter: this project demonstrates pre-registered hypothesis testing, rigorous
negative-result reporting, point-in-time enforcement as a code invariant, hexagonal
architecture applied to a real data pipeline, and 1,583 tests covering domain logic,
adapters, use cases, and integration paths. The negative findings are the portfolio
piece — a system that falsified its own thesis honestly is more credible than one that
never tested it.

---

## Setup

### Prerequisites

- Python 3.12+
- Conda (recommended)

### Installation

```bash
git clone https://github.com/tirthjoship/multi-modal-stock-recommender.git
cd multi-modal-stock-recommender

conda create -n multi-modal-stock-ml python=3.12 -y
conda activate multi-modal-stock-ml

pip install -e ".[dev,dashboard]"
pre-commit install
```

### Verify

```bash
# Full suite (1583 tests, ~28 s)
pytest tests/ -q

# With coverage gate (90% required)
pytest tests/ --cov=domain --cov=adapters --cov=application --cov-fail-under=90

# Full quality check (lint + type-check + tests)
make check
```

---

## Risk disclaimer

This project is for educational and research purposes only. Nothing generated by this
system is financial advice. Past performance does not guarantee future results. Always
consult a licensed financial advisor before making investment decisions.

---

## Author

**Tirth Joshi** — UBC Master of Data Science

---

## License

MIT License. See `LICENSE` file for details.
