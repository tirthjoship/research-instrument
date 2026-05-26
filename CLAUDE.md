# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository. Read `AGENTS.md` for all coding standards, architecture rules, and testing requirements before touching any code.

## Project Context

Multi-modal stock recommendation engine combining structured market data (yfinance) with unstructured sentiment signals (news, Reddit, StockTwits) to generate weekly Top 15 stock picks. Core hypothesis: **sentiment leads price by 1-48 hours**, and when technical indicators diverge from sentiment signals, the divergence predicts 5-day directional returns.

The project uses hexagonal architecture (ports & adapters) so the domain logic stays pure and any data source, ML model, or UI can be swapped without touching business rules.

## Commands

```bash
# Full quality check (lint + typecheck + test with coverage)
make check

# Individual targets
make test          # pytest -v --tb=short
make test-cov      # pytest with --cov-fail-under=90
make lint          # pre-commit run --all-files
make typecheck     # mypy strict on domain/ adapters/ application/
make setup         # pip install + pre-commit install

# Single test
pytest tests/test_domain_models.py::test_signal_valid_creation -v
```

## Architecture

**Hexagonal (Ports & Adapters) with inward-pointing dependencies.**

```
adapters/     →  domain/  ←  application/
(external)       (pure)      (orchestration)
```

- `domain/` — Business rules, models, port interfaces, exceptions. ZERO external framework imports.
- `adapters/data/` — yfinance, RSS feeds, Google Custom Search, Reddit (PRAW), StockTwits, Quiver Quantitative, SQLite store.
- `adapters/ml/` — Keyword scorer, Flan-T5 sentiment, XGBoost predictor, LightGBM predictor, ensemble.
- `adapters/visualization/` — Streamlit dashboard (Phase 5).
- `application/` — Use case orchestration (WeeklyTournament, TrackRecommendations, Backtest).
- `config/markets/` — Market-specific configuration (us.yaml, future: ca.yaml, in.yaml).

Port interfaces in `domain/ports.py` define contracts. Adapters implement them. New tool = new adapter, never new domain code.

## Critical Domain Knowledge

**Look-ahead bias — the biggest risk in this project.**

Point-in-time enforcement is non-negotiable. All data accessed during prediction must have timestamps <= prediction_time. Violations are catastrophic — they make backtests look profitable while the live system fails.

Enforced via:
- `LookAheadBiasError` in `domain/exceptions.py` — halts pipeline on violation
- `validate_point_in_time_access()` in `domain/services.py` — checks all signal/sentiment timestamps
- Every adapter must filter data to prediction_time before returning

**FUTURE_LEAKAGE_COLUMNS** (must never appear in feature matrices):
- `next_day_return` — future price data
- `next_week_return` — future price data
- `future_earnings_surprise` — post-event data
- `forward_pe_ratio` — uses future earnings estimates

**Sentiment-price dynamics (from thesis):**
- Sentiment leads price by 1-48 hours (hypothesis under test)
- Cross-modal divergence (technicals disagree with sentiment) is the primary predictive signal
- Buzz alone does not equal returns — the model must learn which buzz patterns precede moves

**5-tier grading system:**
- Strong Buy (top 3, high confidence)
- Buy (rank 4-8)
- Hold (rank 9-12)
- May Sell (rank 13-15, declining signals)
- Immediate Sell (held stock with negative divergence flip)

**Evaluation — always compare against SPY benchmark:**
- Never claim "model beats the market" without risk-adjusted comparison
- Sharpe ratio, not raw returns
- Precision/recall on directional predictions, not accuracy alone

## Non-Negotiable Rules

Five hard stops — see `AGENTS.md` for full details:

1. **No framework imports in domain/** — domain/ imports only typing, dataclasses, datetime, enum
2. **No look-ahead bias** — all data timestamps must be <= prediction_time. LookAheadBiasError enforced.
3. **Evaluate with Sharpe ratio + precision/recall** — never raw returns or accuracy alone
4. **No direct commits to main or dev** — feature branches only, PR to dev
5. **Tests use small fixtures** — never hit real APIs (yfinance, Reddit) in CI tests. Use fakes.

## Phase Status

**Done:**
- Domain layer (models, ports, services, exceptions) — Signal, Sentiment, BacktestResult
- Domain ports — MarketDataPort, SentimentPort, StockPredictorPort, BacktestResultPort
- Point-in-time validation — validate_point_in_time_access() with LookAheadBiasError
- Test suite (7 tests passing) — domain models + services
- CI workflows (test + lint + security) — 3 GitHub Actions
- Pre-commit hooks — black, isort, mypy strict, ruff, gitleaks
- Makefile — test, lint, typecheck, setup, check targets
- Agent Development Kit — code-reviewer, test-writer, leakage-auditor agents
- CLAUDE.md + AGENTS.md + CONTEXT.md — project orientation and standards
- Design spec — Phase 3 core engine (docs/superpowers/specs/2026-05-23-stock-recommender-phase3-design.md)
- 7 Architecture Decision Records (docs/adr/)

**In Progress (Phase 3 — Core Engine):**
- Data adapters (yfinance, RSS, Google CSE, Reddit, StockTwits, Quiver)
- Sentiment scoring (keyword baseline → Flan-T5)
- Feature engineering (44 features across 7 groups)
- ML models (XGBoost + LightGBM ensemble)
- Weekly tournament pipeline (GitHub Actions cron)
- SQLite storage for recommendations + accuracy tracking
- CLI entry point

**Planned:**
- Phase 4: Tracking & Intelligence (accuracy trends, Canadian market, LSTM-Transformer)
- Phase 5: Dashboard & Polish (Streamlit, watchlist, Indian market)
