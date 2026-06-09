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
make daily-scan    # run daily sentiment scan and update recommendations

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
- `adapters/data/` — yfinance, RSS feeds, Google Trends, StockTwits, GDELT sentiment, SQLite store.
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
- Domain layer (models, ports, services, exceptions) — Signal, Sentiment, BacktestResult, RecommendationGrade, MultiHorizonPrediction, StockRecommendation, AccuracyRecord, EvaluationRun, WeeklyReport
- Domain ports — MarketDataPort, SentimentPort, TechnicalAnalysisPort, StockPredictorPort, FeatureEngineerPort, RecommendationStorePort, BacktestResultPort, BuzzDiscoveryPort, SourceReliabilityPort, HistoricalSentimentPort
- Domain services — validate_point_in_time_access(), grade_from_horizons(), validate_feature_matrix(), validate_data_freshness()
- Feature engineering — 45 features across 7 groups (technical, regime, stronger signals, sector, options, cross-correlation, macro)
- ML models — XGBoost + LightGBM + Ridge ensemble, one per horizon (2d/5d/10d)
- YFinance adapter — MarketDataPort + TechnicalAnalysisPort with caching mixin (ADR-017)
- SQLite store — RecommendationStorePort with recommendations, accuracy, evaluations, reports
- Application use cases — PretrainingUseCase, WeeklyTournamentUseCase, TrackRecommendationsUseCase
- Evaluation components — WalkForwardValidator, PermutationTester, TransactionCostModel, RegimeSplitter, DrawdownTracker
- CLI — pretrain, run-tournament, evaluate-last-week, show-report commands
- Config — us.yaml market config with macro symbols, sector ETFs, quality gates
- Test suite — 300 tests passing, Hypothesis property tests, full fake suite
- CI workflows (test + lint + security) — 3 GitHub Actions
- Pre-commit hooks — black, isort, mypy strict, ruff, gitleaks
- Makefile — test, lint, typecheck, setup, check targets
- Design spec + 17 Architecture Decision Records (docs/adr/)
- CLAUDE.md + AGENTS.md + CONTEXT.md — project orientation and standards

**Done (Phase 3A Completion — methodology gaps closed 2026-05-29):**
- Real-data backtest — 40 tickers, 2024-01 to 2026-05, 19 walk-forward folds. Result: ~50% accuracy (random baseline).
- SHAP feature importance — 32/45 features near-zero, only 3 stable+important (correlation_with_spy, macd, macd_histogram)
- Wire evaluation pipeline — FullEvaluationSuite connecting all 5 ADR-011 components
- Fix imputation — native NaN for XGBoost/LightGBM, stored medians for Ridge (ADR-018)
- Fix composite score — signed values for long-only ranking
- Naive baselines — momentum, low-vol, random, equal-weight (ADR-020)
- Ensemble disagreement confidence (ADR-019)
- Wire sector_relative_strength_6m
- Bug fixes: cache staleness, 2d weekend target bug, rate limit crash retry

**Done (Phase 3B — Code Complete 2026-05-30):**
- Keyword + Flan-T5 zero-shot parallel scorers (ADR-008)
- RSS, Google CSE, Reddit, StockTwits adapters
- 16 additional features (sentiment/buzz 11 + divergence 4 + sector_buzz_ratio 1)
- Ablation: technical-only vs sentiment-only vs combined
- Recursive learning with decay weighting

**Done (Phase 3.5 — Expanded Sentiment Sources 2026-06-01):**
- Google Trends adapter — historical interest back to 2004, weekly granularity, rate-limited (pytrends)
- StockTwits adapter — free API, message volume + bullish/bearish ratio
- GDELT historical sentiment adapter — DOC API, V2Tone normalization, 2015-present
- HistoricalSentimentPort added to domain/ports.py
- Ticker universe expanded to ~350 (S&P 500 + NASDAQ-100) via config/tickers/ files
- 10 new sentiment features (24 total): google_trends_current/change/spike, stocktwits_volume/bullish/change, news_avg/volume/momentum/negative_spike
- Daily scan pipeline wires all three new adapters
- Test suite — 262 tests passing

**Done (Phase 4A — Fundamental Valuation Features 2026-06-01):**
- FundamentalFeatureEngineer — 16 features (PEG, P/E, P/B, FCF yield, margins, debt, earnings, valuation_z_score)
- YFinance field_map expanded with pegRatio, freeCashflow, grossMargins, operatingMargins
- Sector-relative metrics (pe_vs_sector, valuation_z_score) — sector context wired with empty list (sector batching in future phase)
- Wired into pretraining and tournament pipelines (optional, backward compatible)
- Test suite — 300 tests passing

**Done (Phase 4B — Portfolio Tracking + Sell Signals 2026-06-01):**
- Holding + SellSignal domain models — frozen dataclasses with validation
- HoldingsPort protocol + SQLite CRUD (add/remove/get/list holdings)
- MonitorHoldingsUseCase — stop-loss (-8%), negative sentiment, technical breakdown detection
- 4 CLI commands: add-holding, list-holdings, remove-holding, monitor-holdings
- Risk config in us.yaml (stop_loss_threshold, sentiment_sell_threshold)
- Test suite — 334+ tests passing

**Done (Phase 4C — Cross-Asset Intelligence 2026-06-02):**
- CorrelationEdge domain model + CrossAssetPort protocol
- CorrelationAnalyzer adapter — rolling correlation matrix, hierarchical clustering, Granger causality with BH correction
- CrossAssetFeatureEngineer — 8 features (upstream leader returns, cluster momentum, lag signal, supply chain divergence, correlation regime shift, thematic activation, Granger lead signal)
- Supply chain YAML config — 10 groups (semiconductors, big tech, energy, pharma, space/defense, retail, AI, cloud/SaaS, financials, housing)
- Wired into pretraining and tournament pipelines (optional, backward compatible)
- Test suite — 370+ tests passing

**Done (Phase 4D — Event-Causal Learning 2026-06-02):**
- EventCategory enum (10 types) + ClassifiedEvent + EventSectorImpact domain models
- EventClassifierPort protocol + GeminiEventClassifier adapter (Gemini free tier, structured output)
- EventImpactAnalyzer — learns magnitude + half-life per category×sector from historical data
- EventCausalFeatureEngineer — 8 features (impact score/max, event count, sentiment direction, half-life avg, surprise factor, dominant category, decay phase)
- Event-sector mapping YAML (10 categories × affected sectors)
- Wired into pretraining and tournament pipelines (optional, backward compatible)
- Test suite — 410+ tests passing

**Done (Phase 5 — Decision Dashboard 2026-06-02):**
- 6-tab Streamlit dashboard (Command Center, Model Confidence, Signal Breakdown, Positions, Opportunities, Market Pulse)
- Shared Plotly chart builders (accuracy line, grade donut, sector heatmap, decay curve, SHAP bar, ablation bar)
- Dashboard formatters (grade colors, direction icons, urgency badges, percentages, freshness)
- Data loader with graceful degradation (empty states, missing DB/files)
- Watchlist SQLite table + 3 CLI commands (add-watchlist, list-watchlist, remove-watchlist)
- Metric card and action card Streamlit components
- Smoke + integration tests, all pre-commit hooks pass
- Test suite — 470+ tests passing

**Done (Phase 5.1 — Dashboard UI Overhaul 2026-06-02):**
- Renamed `pages/` → `tabs/` to fix Streamlit sidebar auto-discovery bug
- Global CSS module (`styles.py`) — Modern SaaS styling with cards, pills, badges, layer colors
- 6 HTML formatters: grade badges, status pills, signal pills, confidence bars, freshness pills, grade display names
- Fixed grade donut colors (enum → display name), human-readable ablation labels, SHAP layer-colored bars
- Styled metric cards with HTML containers, signal layer cards with colored borders, info sections with tooltips
- Action runner with progress-tracked `run_monitor_holdings`, `run_add_holding`, `run_add_watchlist`
- All 6 tabs rewritten: styled cards, convergence bars, inline forms, expanders
- Test suite — 496 tests passing

**Done (Phase 5.2 — Dashboard UX Overhaul 2026-06-03):**
- CSS overhaul: Inter font (Google Fonts CDN), `#2563EB` accent blue, hover lift effects, styled buttons/inputs
- Footer watermark: "Multi-Modal Stock Recommender · Hexagonal Architecture · Built by Tirth Joshi"
- Verdict-first pattern: every section answers a question in plain English before showing numbers
- 5 verdict generators: command center, model confidence, signal layer, pick, ablation
- Hero banner + verdict card + inline context components (replaces all `st.expander("Learn more")`)
- One-click actions: Run Full Cycle (chains scan→tournament→track), Run Tournament, Run Backtest
- Emoji-free content: urgency pills + freshness dots use CSS classes, no emoji in content areas
- Top 5 pick cards on Opportunities tab (no expanders for important data)
- Data pipeline status panel on Market Pulse (shows all 7 connected data sources)
- Supply chain groups expanded by default (no click to reveal)
- Test suite — 518 tests passing

**Done (Phase 7 — Opportunity Intelligence Foundation 2026-06-03):**
- ConvictionScore, ConvictionWeights, OpportunityCard, SmartMoneySignal domain models
- SmartMoneyPort protocol + validate_smart_money_signals temporal guard
- Conviction scoring service — weighted multi-signal aggregation, freshness decay, ranking
- SEC EDGAR adapter — 13D activist filings + Form 4 insider trades (free, no API key)
- Smart money feature engineer — 8 features (13D count, insider cluster, stake %, buy/sell counts)
- ConvictionScoringUseCase — orchestrates signal gathering → scoring → card generation
- Opportunity card HTML components — conviction badges, action badges, evidence/risk rendering
- Dashboard freshness header — last scan timestamp, market status, S&P 500 sparkline
- Command Center → Opportunity Feed tab with conviction-ranked cards
- Conviction weights + SEC EDGAR config in us.yaml
- ADR-032 documenting the reframe from direction prediction to opportunity surfacing
- Test suite — 660+ tests passing

**Done (Phase 8 — Outcome Tracking & Memory 2026-06-03):**
- TrackedTrade, TradeOutcome, SignalPerformance domain models
- Outcome tracking service — compute_outcome, compute_signal_performance, generate_report_card
- SQLite persistence — tracked_trades + trade_outcomes tables with CRUD
- OutcomeTrackingUseCase — record_buy, record_sell, get_signal_report, get_outcomes_summary
- Dashboard data loaders — load_trades, load_outcomes with graceful defaults
- Outcome Tracker tab (was Positions) — trade recording form, P&L display, outcomes table
- System Intelligence tab (was Model Confidence) — signal report card + learning progress
- Historical bootstrap engine — simulates past outcomes for cold-start learning
- ADR-033 documenting outcome tracking and signal learning
- Test suite — 735+ tests passing

**Done (Phase 9 — Adaptive Intelligence 2026-06-03):**
- PatternEntry, WeightAdjustment, LearnedRule domain models
- Pattern memory service — build_patterns_from_outcomes, compute_weight_adjustments, discover_rules
- SQLite persistence — weight_history + learned_rules tables
- LearningUseCase — orchestrates pattern analysis, weight adjustment, rule discovery
- System Intelligence tab — Run Learning Cycle button, weight history table, learned rules display
- Data loaders — load_weight_history, load_learned_rules
- ADR-034 documenting adaptive intelligence architecture
- Test suite — 785+ tests passing

**Done (Phase 5.3 — Dashboard Redesign 2026-06-03):**
- Complete CSS theme rewrite — DM Sans headings, Inter body, JetBrains Mono numbers, WealthSimple palette
- Smart scan cache — 15min market hours, 60min after hours, auto-scan on page load
- 3-panel hero section — Market Status (EST), Your Portfolio, Today's Signal
- Compact opportunity cards with conviction bars, action badges, freshness dots
- Guided 3-step onboarding for first-run experience
- Learning progress bar with milestone gamification
- 5-tab layout: Today's Opportunities, Watchlist, My Portfolio, How It Works, Market Context
- Killed tournament tab and signal breakdown tab (merged into card expand)
- Watchlist tab with add/remove and historical view
- How It Works tab — collapsible sections (Signal Performance, System Learning, Model Baseline)
- Market Context — data pipeline grid with 8 sources including SEC EDGAR
- ADR-035 documenting dashboard redesign decisions
- Test suite — 838+ tests passing

**Done (Phase 5.4 — SimplyWallSt-Grade Dashboard Redesign 2026-06-04):**
- SWST design language across all tabs: criteria cards, verdict bullets, charts
- Signal Radar — 6-axis chart (Technical/Sentiment/Fundamental/Cross-Asset/Event-Causal/Smart Money)
- Stock Analysis tab — full 7-section deep dive for any S&P 500/NASDAQ ticker
- Conviction engine fix — 3 placeholder sub-scores (sentiment, fundamentals, ML direction) wired to real data
- Live prices via yfinance batch cache (5min TTL market hours, 60min after)
- 15+ new Plotly chart builders (radar, gauge, comparison bars, ownership pie, insider bars, financials line, cluster bubble)
- Market overview fallback when conviction data is thin
- Scrolling ticker bar with major index prices
- Portfolio live P&L with position health cards
- Watchlist with live prices, remove button, structured add form
- Supply chain tags with live price change colors + cluster bubble chart
- How It Works: criteria cards, grade donut, sector heatmap, real accuracy distribution
- CSS tooltips with hover explainers on Signal Radar, Conviction, Valuation, Walk-Forward Accuracy
- Dead code cleanup — removed unused legacy helpers
- ADR-036 documenting redesign decisions
- Test suite — 996 tests passing

**Done (Leg-2 sub-project 1 — Opportunity Forward-Tracking 2026-06-05):**
- SurfacedCall + CallOutcome paper-call domain models (semantically separate from Phase 8 real-trade P&L)
- divergence_score — buzz-leads-price "early" signal (pure domain)
- UniverseProviderPort + SurfacedCallStorePort; UniverseEntry; config/universe/themes.yaml thematic spine
- HybridUniverseProvider — curated spine + BuzzDiscovery overlay (spine wins theme; discovery capped; spine-only fallback)
- SQLite surfaced_calls + call_outcomes tables (Phase 8 save_outcome/get_outcomes renamed to save_trade_outcome/get_trade_outcomes to disambiguate from call outcomes)
- OpportunityScanUseCase — layered trigger (conviction × divergence) + honest abstention
- ForwardTrackingUseCase — resolve 1w/1m/3m vs SPY + NDX(QQQ), feed Phase 8 compute_signal_performance
- CLI: scan-opportunities, resolve-calls, opportunity-report (6/8 conviction dims live in bulk scan; event_signal + analyst_signal held neutral to avoid per-ticker API/network cost)
- ADR-040 documenting the evidence-first forward-tracking decision
- Test suite — 1078 tests passing

**Done (Leg-2 sub-project A — Honest Opportunity Engine 2026-06-05):**
- StockTwits adapter deprecated and dropped from the pipeline (dead — HTTP 403 on every ticker)
- Keyless-first source strategy: GoogleNewsAdapter (per-ticker RSS, mid-cap news volume, BuzzDiscovery), WikipediaPageviewsAdapter (keyless daily history, AttentionSeriesPort), GoogleTrendsAdapter `get_attention_series` (AttentionSeriesPort), GDELT throttle fix (429 exponential backoff) + `get_historical_buzz` (honest article timestamps)
- RedditAdapter (PRAW) — pluggable, logged no-op without credentials
- Domain: AttentionPoint model + AttentionSeriesPort protocol (intensity shape, distinct from event-based BuzzDiscoveryPort); `intensity_acceleration()` + `blended_divergence_score()` blending event-acceleration (news/social) + intensity-acceleration (search/pageviews) into one [1,10] divergence with adaptive single-shape weights; Hypothesis property tests
- Store: `attention_series` (append-only, deduped on ticker+source+ts), `scan_candidates` (full candidate-distribution log), `signal_cache` (24h TTL get/put); `_to_naive_utc` tz normalization in attention_series + signal_cache to prevent naive/aware comparison crashes
- Application: BackfillHistoryUseCase (seeds divergence base window from honest GDELT/Trends/Wikipedia archives, per-ticker isolation, idempotent append-only); ConvictionSignalCache (cached event/analyst dims, compute-on-miss, failure → flagged neutral 5.0, never a silent pin); OpportunityScanUseCase extended to use blended divergence + log the FULL candidate distribution before the threshold cut
- CLI: `backfill-history`, `scan-opportunities --show-all` (full distribution + wired Wikipedia + Google Trends attention + ConvictionSignalCache), `daily-cycle` (scan → resolve → conditional weekly backfill)
- Scheduling: `docs/scheduling.md` launchd plist — local SQLite → local scheduler (intentional ADR-007 deviation)
- Deps: pytrends added; praw optional. Honest caveats: 7/8 conviction dims live in bulk scan (analyst wired live; event_signal held neutral — per-ticker Gemini cost/keys deferred); backfill is leakage-free for forward-tracking but NOT a backtest and is NOT evidence of edge; cmin/dmin empirically calibrated from the observed distribution (not hand-tuned); live sources rate-limited so the daily cycle tolerates partial source failure
- ADR-041 documenting the honest opportunity engine decisions
- Test suite — 1120 tests passing

**Done (Leg-2 sub-project B — Honest Ingestion & Source Health 2026-06-05):**
- Fixed the data layer so the no-joint-signal finding (finding 6) can be re-evaluated on clean inputs. Sub-project A live run had found GDELT silently failing, Google Trends unusable under burst load, rate-limited sources writing empty rows as if genuine, and the backfill universe mismatched against the scan universe — all confounding the edge question.
- **Prune, don't add** — no new model dimensions shipped; conviction combiner frozen until clean-data re-evaluation.
- **Throttle ≠ empty rule** — `SourceThrottledError` distinguishes rate-limits from genuine empty observations; a throttle never writes a zero to the base window (look-ahead-adjacent data-integrity rule).
- **Source consolidation** — Google News RSS + Wikipedia pageviews as primary; Google Trends secondary (slow-drip only); GDELT demoted to optional/off (free tier confirmed dead in sub-project A live run); Reddit unchanged (off without creds); StockTwits already retired.
- **`SourceHealth` value object** — per-source `attempts/ok/empty/throttled/failed` surfaced in every run report; sibling of `ConvictionSignalCache.flags`; never silent.
- **Resumable spine-first slow-drip backfill** — `DripBackfillUseCase` iterates scan universe (spine first), checkpoints via store (crash = resume for free), spaced/jittered under rate budgets. `DailyDeltaSweepUseCase` fetches only new days. No proxies / multi-account (ToS-evasion, contradicts the honesty thesis).
- **Minimum-history gate** — `has_min_history` domain predicate (~21 days) blocks day-1 noise spikes before a ticker is eligible to surface.
- **Discrimination audit** — `DiscriminationAuditUseCase` one-shot diagnostic: per-dim variance + neutral-share + conviction contribution; output drives principled pruning decisions (human decides, not auto-prune).
- **Honest empty-state** — when the engine abstains, dashboard shows full ranked candidate distribution + near-misses + source-health panel so abstention reads as rigor.
- **`caffeinate` constraint documented** — launchd will not fire on a sleeping laptop; `docs/scheduling.md` now includes a "Laptop sleep" subsection with a concrete `caffeinate -i` plist example and a `pmset` alternative.
- **Honest caveat:** this improves data reliability, not proven edge. ADR-039's no-OOS-edge finding stands. The no-joint-signal finding (sub-project A) was confounded by broken data and will be re-evaluated on clean inputs.
- Test suite — 1165 tests passing
- Spec: `docs/superpowers/specs/2026-06-05-leg2-subproject-b-honest-ingestion-design.md`
- Plan: `docs/superpowers/plans/2026-06-05-leg2-subproject-b-honest-ingestion.md`
- ADR-042: `docs/adr/042-honest-ingestion-source-health.md`

**Done (Leg-2 sub-project D — Divergence IC Validation 2026-06-06): VERDICT = KILL**
- Pre-registered cross-sectional IC falsification test of the intensity-divergence signal (the last untested "edge" hypothesis). Pre-registration LOCKED before any result: primary horizon 1m (21d); gate = bootstrap CI excludes 0, positive, AND |mean IC| ≥ 0.02; broad survivor-biased ~518 universe.
- **Phase 3 (signal + math + harness):** `intensity_divergence_raw` (continuous, intensity-only, sentiment-free signal under test); `application/ic_analysis.py` (Spearman cross-sectional rank-IC + aggregate, NaN-propagating); `DivergenceICBacktestUseCase` (point-in-time loop + reuses `precision_metrics` bootstrap/date-level significance); `validate-divergence-ic` CLI (locked gate, writes JSON report, PROCEED/KILL).
- **Phase 3.5 (attention-data unblocker — not in original plan):** the first live run was invalid (Wikipedia article-map covered 1.5% of the universe → noise stubs). Five hardening passes: R1 429 backoff + `SourceThrottledError` in pageviews adapter (throttle ≠ empty); R2 `WikipediaArticleResolver` (OpenSearch name→article + view-volume validation ≥50/day); R3 `resolve-wiki-articles` CLI + merged `_load_wiki_map` (curated aliases win); R4 throttle-≠-rejection (a 429 on validation must not false-reject); R5 yfinance legal-suffix normalization (raw-first/cleaned-fallback — "Apple Inc." stays the company, "AbbVie Inc."→"AbbVie"). Coverage 1.5% → **83% (430/518)**, 1.4M attention rows.
- **Verdict (2026-06-06, 430-ticker universe):** 1w IC=0.0072 (CI excludes 0 but ≪0.02), **1m IC=0.0040 (CI spans 0) → KILL**, 3m IC=−0.0046. n_dates 490–499. The signal has no economically meaningful cross-sectional edge at any horizon — falsified even on a flattering survivor-biased sample. Reports: `data/reports/divergence_ic_{1m,1w,3m}_20260606.json`.
- **No Phase 5.** Divergence-led surfacing (Tasks 8–9) was conditional on PROCEED; not built (would manufacture false confidence on a dead signal). Forward clock not started; no real-money path.
- **Kept as protected baseline:** the IC harness + article resolver + 83%-coverage attention map = a reusable honest falsification rig + clean data layer for the next candidate signal.
- Three independent honest tests now agree the "tradeable edge from public attention/conviction" thesis is unsupported: ADR-039 (no OOS conviction edge), ADR-043 (conviction dims dead), ADR-044 (no divergence IC). Defensible product = honest evidence-aggregator that abstains + the validation harness. Next move (pivot signal / reframe as research-monitoring tool / harden abstention) is a user decision.
- Test suite — 1201 tests passing
- Plan: `docs/superpowers/plans/2026-06-06-leg2-subproject-d-phase35-attention-resolver.md` (+ `2026-06-05-leg2-subproject-d-divergence-ic-validation.md`)
- ADR-044: `docs/adr/044-divergence-ic-verdict.md`

**PIVOT (2026-06-07, ADR-045): Return-Prediction → Exit-Discipline + Evidence-Bounded Screening**
- Three falsification tests (ADR-039/043/044) killed the "predict winners from public sentiment/attention/conviction" thesis. Convergent negative: no retail-accessible alpha in public attention.
- Reframe: **a retail edge is better PROCESS, not better PREDICTION.** User's picks are excellent (MU +863%, PLTR +447%); losses come from process (holding broken-trend names down 30–57%; mistimed exits). Behavior gap = avg investor lags S&P ~848 bps/yr (disposition effect).
- New direction: momentum + 200-day trend filter + ATR Chandelier trailing exit (rides runners, ejects breaks) + relative-momentum selection. Evidence-tier-bounded ambition (Tier 1 risk/behavior/factors; Tier 2 PEAD/revisions each falsified; Tier 3 = ignition-prediction/accuracy-compounding/SPY+20-30% explicitly OUT).
- Screening NOT prediction; "cheap false positives" not "no false positives"; calibrated + abstain; LLM narrates the why, never picks.
- Spec: `docs/superpowers/specs/2026-06-07-personal-momentum-exit-discipline-backtest-design.md`. Plan: `docs/superpowers/plans/2026-06-07-momentum-exit-discipline-phase1.md` (12 tasks). ADR-045.
- **NEXT SESSION (start LOW effort, conserve for implementation):** execute the Phase-1 plan via subagent-driven-development (Sonnet) — pure trend/metric primitives → MomentumExitBacktestUseCase → verdict gate → CLI → PortfolioVerdictUseCase. Then live backtest run → PROCEED/KILL. **THEN switch to MAX effort to dissect the findings.** Phase 2 (screener/daily feed) is gated on a PROCEED verdict — not yet planned. User provides `data/personal/holdings.csv` (gitignored) for the per-holding verdict.

**Done (Momentum/Exit Phase-1 — VERDICT = KILL, 2026-06-07, ADR-046):** Built via subagent-driven-development (Sonnet impl, Opus review), merged to develop. Corrected gate (Opus caught + fixed: look-ahead bias, transaction costs never charged, wrong gate statistic). Final OOS US+TSX 2018–2026, 570 names: strategy Sharpe 0.83 / maxDD 22.8% vs buy-hold 0.88 / 38.2%. Drawdown-cut **40% (passes ≥30%)** but Sharpe-diff CI spans 0 (point −0.05) → **KILL**. Risk-adjusted edge dead; drawdown reduction real. `portfolio-verdict` CLI shipped. Phase 2 (screener) NOT built (gated on PROCEED).

**Done (Holdings Discipline & Risk Engine — SHIPPED + MERGED, 2026-06-08, ADR-047):** Alpha-hunt declared COMPLETE → honest discipline/risk decision-support tool. Four pre-registered falsifications (ADR-039/043/044/046) + a forensic data audit (data is NOT the bottleneck — cleanest data killed hardest) + a cited deep-research pass settle it: no retail alpha in public signals; profitability = expectancy not hit-rate; stack small honest non-predictive edges (behavior-gap ~1%/yr, conditional vol-targeting TSX-safe, trend/stop drawdown-cut, decayed factors); LLM narrates never picks. Built via subagent-driven-development (Sonnet impl, 14 TDD tasks, phase-boundary verification): graded verdict (REDUCE/TRIM/REVIEW/HOLD/ADD_OK) + confidence + abstain-when-mixed; pure domain scorers (`trend_health`/`ma_slope`/`relative_strength`, `discipline.py`, `calibration.py`); `PositionRisk`/`PortfolioRisk`; `HoldingsRiskAssessmentUseCase`; `holdings_reader` (broker CSV→yfinance); local Ollama narrator (graceful template fallback, cloud-swappable); forward-calibration log + `resolve-discipline-flags`; historical point-in-time `backtest-discipline-flags` (day-1 evidence). CLIs: `holdings-risk` (masked stdout), `resolve-discipline-flags`, `holdings-risk-calibrate`, `backtest-discipline-flags`. Tax-loss leg dropped (user 65/66 registered accounts). Privacy: gitignored holdings, masked stdout, only tickers→yfinance. v1 = holdings; **Phase 2 (factor screening) deferred**, gated on v1 calibration.
- **Live run (66 real holdings):** 23 REDUCE / 23 TRIM / 8 HOLD / 12 ADD_OK; broken-trend share 39%, top concentration 20%. **Day-1 calibration (5462 point-in-time verdicts): flags discriminate** — REDUCE down-rate 58% / fwd −1.71% vs HOLD/ADD_OK 39% / positive. Honest caveat: TRIM's "down" assertion is miscalibrated (it's a winner-trim, fwd +1.85% → Brier 0.551). One real bug caught only by live data (tz-naive yfinance datetimes vs tz-aware bounds) fixed + regression-tested.
- **Test suite — 1282 passing, 93.48% coverage.** `make check` green. Spec: `docs/superpowers/specs/2026-06-08-holdings-discipline-risk-engine-design.md`. Plan: `docs/superpowers/plans/2026-06-08-holdings-discipline-risk-engine.md`. ADR-047.
- **MERGED + SYNCED (2026-06-08):** feat/holdings-discipline-risk-engine → develop; reconciled a develop/main divergence (32 main-only commits from sub-projects A/B pushed straight to main + 19 unpushed momentum Phase-1 commits) via union merge; synced develop → main. `origin/develop` ≡ `origin/main` (content-identical), all 3 CI workflows (Test/Lint/Security) green on **both** branches. Feature branch deleted.
- **NEXT SESSION:** use the tool ~2–4 weeks (`holdings-risk` on real holdings), then `resolve-discipline-flags` — forward "beats-your-behavior" calibration gates trust + the Phase-2 decision. KILL clause if flags no better than chance. Optional: `/schedule` a recurring resolve run.

**ENGINE CONSOLIDATION (2026-06-08, ADR-049): Two-Sided Forward-Accountable Decision-Support Engine**
- Grilling session widened the product from holdings-discipline-only to a unified engine: weekly evidence-ranked buy shortlist + holdings buy/sell/hold/why + directed economic-link research (Walmart→McKesson, Cohen-Frazzini) + accountability. Spine: SCREEN+RIDE never predict; every predictive claim falsification-gated; forward scorecard IS the product; modest ceiling stated everywhere. 6-layer hex architecture, ~55% reused (SurfacedCall/CallOutcome/discipline/CorrelationAnalyzer/analyst+fundamental adapters/falsification harness).
- Four self-checkpointing phase specs (each ends with pre-registered exit gate + next-phase entry/intercept): A evidence-screen → B weekly-brief → C economic-link research+drift → D conditional edge-graft (runs ONLY if A/C/discipline-July-gate passes; else engine ships research+discipline+abstaining-screen = pre-agreed honest terminal state). ADR-049; specs `docs/superpowers/specs/2026-06-08-engine-phase-{a,b,c,d}-*.md`.

**Done (Engine Phase A — Evidence Screen MVP, 2026-06-08, ADR-049):** Built via subagent-driven-development (Sonnet per task, Opus verification-before-completion phase gate), merged to develop. Pure-domain `factor_scores`/`screen`/`screen_models` (stdlib-only, equal-weight composite, flagged-neutral coverage), `EvidenceScreenUseCase` (rank-all→top-N, winsorized z-scores, percentiles, abstain-on-thin), `ScreenBacktestUseCase` (pre-registered IC gate ≤0 HALT / <0.02 INCONCLUSIVE / ≥0.02 PASS), `screen-candidates` + `backtest-screen` CLIs (masked stdout, full-distribution report), SurfacedCall forward-tracking wiring. **1324 tests, 93.61% cov, make check green.** Opus gate caught 2 real blockers (CLI wrote only top-N while claiming full distribution — ADR-042 violation; test mock-defeated it) + wired 3 dead helpers — all fixed. **DEFERRED (blocks live run):** bootstrap-CI gate + cost-aware top-decile secondary (spec §5, docstring-marked, not faked). Screen ships RESEARCH_ONLY until pre-registered test passes. Plan: `docs/superpowers/plans/2026-06-08-engine-phase-a-evidence-screen.md`. **NEXT SESSION:** implement deferred bootstrap-CI → run `backtest-screen` → set VALIDATED/RESEARCH_ONLY → Phase-B plan. Parallel to discipline July gate (ADR-048).

**Done (Trend-Following Sleeve Falsification — VERDICT = INCONCLUSIVE, 2026-06-08, ADR-050):** The one untested published strategy — 80% SPY core + 20% cross-asset 12-mo TSMOM sleeve (long/flat, inverse-vol, 7 liquid ETFs SPY/EFA/EEM/TLT/IEF/GLD/DBC), tested as a DIVERSIFIER not alpha (Hurst/Ooi/Pedersen). Built inline TDD (executing-plans): pure-domain `trend_following.py` (momentum/inverse-vol/turnover/blend/equity-curve) + `TrendSleeveBacktestUseCase` (point-in-time monthly loop, look-ahead-safe, reuses `sharpe_difference_bootstrap`/`DrawdownTracker`/`backtest_metrics`) + `backtest-trend-sleeve` CLI. Note: plan referenced a nonexistent `screen_ic_panels.monthly_closes_asof` — inlined a local point-in-time month-end helper instead (gate untouched). Opus gate-math review found NO bug (matches spec §5 verbatim). **1343 tests, 93.74% cov, make check green.**
- **Live (216 months, 2008–2026, net 10bps):** SPY-core Sharpe 0.748 / maxDD −46.1% / CAGR 11.5%; sleeve 0.723 / −8.0% / 3.8%; **blended80/20 0.780 / −38.2% / 10.1%**. Sharpe-diff point +0.032, **CI [−0.0011, +0.0583]** (spans 0 by a hair); **dd_reduction 17.1%** (<25% gate). 60/40 sensitivity (not gated): Sharpe 0.821 / maxDD −29.5% (best of all). Report: `data/reports/trend_sleeve_2026-06-08.json`.
- **INCONCLUSIVE, not PASS** (CI includes 0, DD-cut <25%) **and not KILL** (blended strictly worse on neither axis — higher Sharpe AND shallower DD). A real, literature-consistent diversifier that cut the worst (GFC) drawdown but under-cleared our own pre-registered bar at 20%. Regime caveat: TSMOM protects in slow grinding bears (2008), structurally too slow for V-crashes (2020); 2022 bonds fell with equities. 60/40 better but NOT pre-registered → cannot claim (would be retuning).
- **6th convergent no-clearing-edge result.** Trend-following OFF the table as a validated feature; **discipline engine (ADR-047/048) stays the terminal bet** (July forward-calibration gate unaffected). No product/brief surfacing built (PASS-gated). Sleeve rig kept as protected baseline for any future pre-registered re-test. ADR-050. Branch `feat/trend-following-sleeve-falsification` (unmerged). Housekeeping: superseded superpowers plans/specs (≤2026-06-05) moved to gitignored `archive/` + deletions committed to stop agent drift.

**Superseded (Phase 4 old plan):** ~~Tracking & Intelligence — accuracy trends, long-short ranking, conformal prediction, Canadian market, LLM analyst layer, risk management, position sizing~~ — the prediction-centric parts are abandoned per ADR-045; risk management + position sizing fold into the discipline engine; Canadian market (TSX) folds into the backtest universe.
