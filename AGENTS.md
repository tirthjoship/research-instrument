# Coding Standards

## Python

- Python 3.12+
- Formatting: `black` (line-length 88)
- Type checking: `mypy` with strict mode enabled
- Linting: `ruff`
- Import sorting: `isort` (profile: black)
- No bare `except` — use specific exception types
- Type hints on all public function signatures
- Prefer `X | None` over `Optional[X]` (Python 3.12 syntax)

## Naming Conventions

- **Variables and functions**: `snake_case` (e.g., `get_trending_tickers`, `compute_divergence_score`)
- **Classes**: `PascalCase` (e.g., `YFinanceAdapter`, `WeeklyTournamentUseCase`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `FUTURE_LEAKAGE_COLUMNS`, `RECOMMENDATION_GRADES`)
- **Modules**: `snake_case` (e.g., `yfinance_adapter.py`, `use_cases.py`)
- **Test functions**: `test_<description>` (e.g., `test_divergence_bullish_when_sentiment_exceeds_technical`)
- **Private methods**: prefix with `_` (e.g., `_normalize_score`, `_validate_ticker`)

## Architecture Rules (NON-NEGOTIABLE)

- Hexagonal architecture: `domain/` → `adapters/` → `application/`
- `domain/` has ZERO imports from `adapters/`, `application/`, or external frameworks
- `domain/` imports ONLY: `typing`, `dataclasses`, `datetime`, `enum`, `collections.abc`
- Adapters implement domain port `Protocol` interfaces from `domain/ports.py`
- `application/` orchestrates domain + adapters — it is the composition root
- New external tool = new adapter. Never put framework code in `domain/`
- Domain models use `@dataclass(frozen=True)` for immutable entities
- `config/markets/` contains market-specific YAML configs (not code)
- Each data source = one adapter implementing one port Protocol

## Data Integrity Rules (NON-NEGOTIABLE)

- NEVER use future-dated features: `next_day_return`, `next_week_return`, `future_earnings_surprise`, `forward_pe_ratio`
- These are post-prediction data — using them is look-ahead bias
- `FUTURE_LEAKAGE_COLUMNS` constant is the single source of truth (to be placed in feature engineering module)
- All adapters must filter data to `timestamp <= prediction_time` before returning
- `validate_point_in_time_access()` in `domain/services.py` enforces temporal boundaries
- When adding new data sources, audit every field for temporal leakage before use
- Evaluate models with Sharpe ratio, precision, recall on directional predictions — NEVER raw returns or accuracy alone
- Always benchmark against SPY (S&P 500 ETF) for the same time period

## Testing Rules (NON-NEGOTIABLE)

- Tests use small fixtures — NEVER hit real yfinance, Reddit, or news APIs in CI
- All external adapters have corresponding fakes in `tests/fakes/`
- Integration tests that hit real APIs are marked `@pytest.mark.slow` — skipped in CI
- Property-based tests with Hypothesis for domain invariants
- Every port has a fake implementation for testing
- pytest with `-v --tb=short` default
- Test categories to cover:
  - **Happy path**: valid input, expected output
  - **Error path**: invalid input, correct exception raised
  - **Boundary**: exact edge of a condition
  - **Edge case**: extreme but valid input
- One logical assertion per test function
- Use `pytest.raises` for expected exceptions
- Use `pytest.approx` for float comparisons
- Use `tmp_path` fixture for file I/O tests

## Project Layout

```
domain/                 Pure business logic (ZERO external imports)
├── models.py           Dataclasses: Signal, Sentiment, BacktestResult, TechnicalIndicators,
│                       DivergenceSignal, StockRecommendation, RecommendationGrade,
│                       WeeklyReport, AccuracyRecord
├── ports.py            Protocols: MarketDataPort, SentimentPort, StockPredictorPort,
│                       BacktestResultPort, NewsDiscoveryPort, BuzzScorerPort,
│                       SentimentScorerPort, RecommendationStorePort, TechnicalAnalysisPort
├── services.py         Business rules: validate_point_in_time_access(),
│                       compute_divergence_score(), grade_recommendation()
└── exceptions.py       DomainError, InvalidMarketDataError, InvalidPredictionError,
                        LookAheadBiasError, InsufficientDataError, StaleDataError

adapters/               External connections
├── data/
│   ├── yfinance_adapter.py       MarketDataPort + TechnicalAnalysisPort
│   ├── reddit_adapter.py         BuzzScorerPort (PRAW)
│   ├── stocktwits_adapter.py     BuzzScorerPort
│   ├── rss_adapter.py            NewsDiscoveryPort (6 publisher feeds)
│   ├── google_search_adapter.py  NewsDiscoveryPort (Custom Search API)
│   └── sqlite_store.py           RecommendationStorePort
├── ml/
│   ├── keyword_scorer.py         SentimentScorerPort (baseline)
│   ├── flan_t5_scorer.py         SentimentScorerPort (upgraded)
│   ├── xgboost_predictor.py      StockPredictorPort
│   ├── lightgbm_predictor.py     StockPredictorPort
│   └── ensemble_predictor.py     StockPredictorPort (XGB + LGBM)
└── visualization/                Phase 5 — Streamlit dashboard

application/            Orchestration
├── use_cases.py        WeeklyTournamentUseCase, TrackRecommendationsUseCase, BacktestUseCase
└── cli.py              CLI entry point for pipeline execution

config/markets/         Market-specific configuration
└── us.yaml             US market: RSS feeds, search targets, subreddits, sector ETFs

tests/                  Test suite with fakes
├── test_domain_models.py
├── test_domain_services.py
├── test_properties.py          Hypothesis property-based tests
├── test_weekly_tournament.py   Use case tests with fakes
├── test_track_recommendations.py
├── test_backtest.py
├── test_keyword_scorer.py
├── test_sqlite_store.py
├── test_rss_adapter.py
├── test_google_search_adapter.py
└── fakes/                      Fake adapter implementations
    ├── fake_market_data.py
    ├── fake_news_discovery.py
    ├── fake_buzz_scorer.py
    ├── fake_sentiment_scorer.py
    └── fake_store.py

notebooks/              Exploration and EDA only — no production logic
data/raw/               Untouched source data (gitignored)
data/interim/           Intermediate artifacts (gitignored)
data/processed/         Model-ready data (gitignored)
```

## Git (NON-NEGOTIABLE)

- Commit format: `feat:` / `fix:` / `docs:` / `chore:` / `test:` followed by lowercase description, no period
- Keep commits small and focused
- Never commit directly to `main` or `dev` — use feature branches
- Branch naming: `feat/<slug>` or `fix/<slug>`
- PR target: `dev` (confirm with user before targeting `main`)
- Never commit secrets, raw data, model artifacts, or `.env` files
- Prefer new commits over `--amend` on pushed branches

## Commands

```bash
# Environment
conda activate multi-modal-stock-ml

# Test
pytest -v --tb=short
pytest -v --cov=domain --cov=adapters --cov=application --tb=short

# Lint and format
pre-commit run --all-files

# Type check
mypy domain/ adapters/ application/ --strict

# Setup
make setup
```

## Strong Preferences

These are not hard stops but should be followed unless there is a clear reason not to:

- Use structured logging over `print()` (loguru when added)
- Avoid heavyweight dependencies without justification
- Prefer `X | None` over `Optional[X]` for modern Python 3.12 annotations
- Type hints on private functions too when practical
- Config-driven market selection over hardcoded market logic
- Progressive NLP sophistication — always measure lift before upgrading (keyword → Flan-T5 → LLM)
- Every new data source adapter gets a corresponding fake before integration tests
