"""Use cases: orchestration of domain and adapters.

Each use case depends only on port interfaces, never on concrete adapters.
"""

import time
from datetime import datetime, timedelta
from typing import Any

from loguru import logger

from domain.models import (
    AccuracyRecord,
    EvaluationRun,
    MultiHorizonPrediction,
    Signal,
    StockRecommendation,
    WeeklyReport,
)
from domain.ports import (
    FeatureEngineerPort,
    MarketDataPort,
    RecommendationStorePort,
    StockPredictorPort,
    TechnicalAnalysisPort,
)
from domain.services import grade_from_horizons, validate_feature_matrix


class PretrainingUseCase:
    """Walk-forward pretraining on 2-3 years of historical data.

    For each month M after min_train:
      1. Collect features for all tickers for months before M
      2. Train ensembles (one per horizon) on collected data
      3. Predict month M, record results
    """

    def __init__(
        self,
        market_data: MarketDataPort,
        technical_analysis: TechnicalAnalysisPort,
        feature_engineer: FeatureEngineerPort,
        predictors: dict[str, StockPredictorPort],
        store: RecommendationStorePort,
        tickers: list[str],
        macro_symbols: dict[str, str],
        fundamental_engineer: Any | None = None,  # Phase 4A
        cross_asset_engineer: Any | None = None,  # Phase 4C
        event_causal_engineer: Any | None = None,  # Phase 4D
    ) -> None:
        self._market_data = market_data
        self._tech = technical_analysis
        self._fe = feature_engineer
        self._predictors = predictors
        self._store = store
        self._tickers = tickers
        self._macro_symbols = macro_symbols
        self._fundamental = fundamental_engineer
        self._cross_asset = cross_asset_engineer
        self._event_causal = event_causal_engineer

    def execute(
        self,
        start_month: str = "2024-01",
        end_month: str = "2026-05",
    ) -> None:
        """Run walk-forward pretraining."""
        months = self._generate_months(start_month, end_month)
        if len(months) < 3:
            logger.warning("Too few months for walk-forward training")
            return

        # Validate feature names
        validate_feature_matrix(self._fe.get_feature_names())

        # Collect all features and targets
        all_features, all_targets = self._collect_features_and_targets(months)

        if not all_features:
            logger.warning("No training data collected")
            return

        # Walk-forward training
        min_train = max(2, len(months) // 3)
        for i in range(min_train, len(months)):
            train_features: list[dict[str, float]] = []
            train_targets: dict[str, list[float]] = {"2d": [], "5d": [], "10d": []}

            for j in range(i):
                month = months[j]
                if month in all_features:
                    train_features.extend(all_features[month])
                    for h in ("2d", "5d", "10d"):
                        train_targets[h].extend(all_targets[month][h])

            if not train_features:
                continue

            # Train each horizon
            for horizon in ("2d", "5d", "10d"):
                self._predictors[horizon].fit(train_features, train_targets[horizon])

            # Evaluate on test month
            test_month = months[i]
            if test_month in all_features and all_features[test_month]:
                for horizon in ("2d", "5d", "10d"):
                    preds = self._predictors[horizon].predict(all_features[test_month])
                    actuals = all_targets[test_month][horizon]
                    if preds and actuals:
                        correct = sum(
                            1
                            for p, a in zip(preds, actuals)
                            if (p > 0 and a > 0) or (p < 0 and a < 0)
                        )
                        accuracy = correct / len(preds)
                        self._store.save_evaluation_run(
                            EvaluationRun(
                                run_date=test_month,
                                eval_type="walk_forward",
                                horizon=horizon,
                                metric_name="directional_accuracy",
                                metric_value=accuracy,
                            )
                        )

        logger.info(f"Pretraining complete: {len(months)} months processed")

    def _collect_features_and_targets(
        self, months: list[str]
    ) -> tuple[dict[str, list[dict[str, float]]], dict[str, dict[str, list[float]]]]:
        all_features: dict[str, list[dict[str, float]]] = {}
        all_targets: dict[str, dict[str, list[float]]] = {}

        for month in months:
            month_features: list[dict[str, float]] = []
            month_targets: dict[str, list[float]] = {"2d": [], "5d": [], "10d": []}

            # Parse month to get date range
            year, m = int(month[:4]), int(month[5:7])
            if m == 12:
                month_end = datetime(year + 1, 1, 1) - timedelta(days=1)
            else:
                month_end = datetime(year, m + 1, 1) - timedelta(days=1)

            # Fetch macro data once per month
            macro_signals = self._fetch_macro(month_end)

            # Cache signals for cross-asset features
            if self._cross_asset is not None:
                self._signals_cache: dict[str, list] = {}  # type: ignore[type-arg]
                for t in self._tickers:
                    try:
                        start = month_end - timedelta(days=365)
                        sigs = self._market_data.get_signals(
                            t, month_end, start_date=start
                        )
                        if len(sigs) >= 20:
                            self._signals_cache[t] = sigs
                    except Exception:
                        continue
                # Build graph with cached signals
                self._cross_asset._graph.build_graph(
                    self._signals_cache, window_days=60
                )

            for ticker_idx, ticker in enumerate(self._tickers):
                try:
                    features, targets = self._compute_ticker_features(
                        ticker, month_end, macro_signals
                    )
                    if features:
                        month_features.append(features)
                        for h in ("2d", "5d", "10d"):
                            month_targets[h].append(targets.get(h, 0.0))
                except Exception as e:  # pragma: no cover
                    logger.debug(f"Skipping {ticker} for {month}: {e}")
                    if "rate" in str(e).lower() or "429" in str(e):
                        time.sleep(10)
                    continue
                # Throttle API calls
                if ticker_idx % 5 == 4:  # pragma: no cover
                    time.sleep(1)

            if month_features:
                all_features[month] = month_features
                all_targets[month] = month_targets

        return all_features, all_targets

    def _compute_ticker_features(
        self,
        ticker: str,
        prediction_time: datetime,
        macro_signals: dict[str, list],  # type: ignore[type-arg]
    ) -> tuple[dict[str, float], dict[str, float]]:
        start = prediction_time - timedelta(days=365)
        signals = self._market_data.get_signals(
            ticker, prediction_time, start_date=start
        )
        if len(signals) < 20:
            return {}, {}

        indicators = self._tech.compute_indicators(signals)
        ticker_info = self._market_data.get_ticker_info(ticker)
        options = self._market_data.get_options_summary(ticker, prediction_time)
        analyst = self._market_data.get_analyst_data(ticker, prediction_time)

        features = self._fe.compute(
            signals=signals,
            indicators=indicators,
            ticker_info=ticker_info,
            options_summary=options,
            analyst_data=analyst,
            macro_signals=macro_signals,
            sector_signals=None,
        )

        # Phase 4A: Add fundamental features
        if self._fundamental is not None:
            fundamental_features = self._fundamental.compute(
                ticker_info=ticker_info,
                sector_ticker_infos=[],  # Sector context added in future phase
                analyst_data=analyst,
            )
            features.update(fundamental_features)

        # Phase 4C: Add cross-asset features
        if self._cross_asset is not None:
            cross_features = self._cross_asset.compute(
                ticker=ticker,
                signals=signals,
                signals_by_ticker=getattr(self, "_signals_cache", {}),
            )
            features.update(cross_features)

        # Phase 4D: Add event-causal features
        if self._event_causal is not None:
            sector = ticker_info.get("sector", "") if ticker_info else ""
            if sector:
                event_features = self._event_causal.compute(
                    sector=sector,
                    current_date=prediction_time.strftime("%Y-%m-%d"),
                    recent_events=getattr(self, "_recent_events", []),
                    actual_sector_return_5d=0.0,
                )
                features.update(event_features)

        # Compute target returns (actual future returns)
        # Use last trading day's price as base (not month_end which may be weekend)
        last_price = signals[-1].price
        targets: dict[str, float] = {}
        for h_label, h_days in [("2d", 2), ("5d", 5), ("10d", 10)]:
            # Add buffer for weekends/holidays so yfinance window captures enough trading days
            future_time = prediction_time + timedelta(days=h_days + 5)
            future_signals = self._market_data.get_signals(
                ticker, future_time, start_date=prediction_time
            )
            future_prices = [
                s.price for s in future_signals if s.timestamp > prediction_time
            ]
            if len(future_prices) >= h_days:
                # Use the h_days-th trading day price (not the last in window)
                targets[h_label] = (future_prices[h_days - 1] / last_price) - 1
            elif future_prices:
                targets[h_label] = (future_prices[-1] / last_price) - 1
            else:
                targets[h_label] = 0.0

        return features, targets

    def _fetch_macro(
        self, prediction_time: datetime
    ) -> dict[str, list]:  # type: ignore[type-arg]
        macro: dict[str, list] = {}  # type: ignore[type-arg]
        start = prediction_time - timedelta(days=365)
        for name, symbol in self._macro_symbols.items():
            for attempt in range(3):
                try:
                    macro[symbol] = self._market_data.get_signals(
                        symbol, prediction_time, start_date=start
                    )
                    break
                except Exception as e:  # pragma: no cover
                    logger.warning(f"Macro fetch {symbol} attempt {attempt + 1}: {e}")
                    time.sleep(5 * (attempt + 1))
            else:  # pragma: no cover
                logger.warning(f"Macro fetch {symbol} failed after 3 attempts")
                macro[symbol] = []
        return macro

    @staticmethod
    def _generate_months(start: str, end: str) -> list[str]:
        months: list[str] = []
        y, m = int(start[:4]), int(start[5:7])
        ey, em = int(end[:4]), int(end[5:7])
        while (y, m) <= (ey, em):
            months.append(f"{y:04d}-{m:02d}")
            m += 1
            if m > 12:
                m = 1
                y += 1
        return months


class WeeklyTournamentUseCase:
    """Weekly stock tournament: predict, grade, rank, and store top 15."""

    def __init__(
        self,
        market_data: MarketDataPort,
        technical_analysis: TechnicalAnalysisPort,
        feature_engineer: FeatureEngineerPort,
        predictors: dict[str, StockPredictorPort],
        store: RecommendationStorePort,
        tickers: list[str],
        macro_symbols: dict[str, str],
        market: str = "us",
        sentiment_scorer: Any | None = None,
        stage2_predictor: Any | None = None,
        buzz_store: Any | None = None,
        fundamental_engineer: Any | None = None,  # Phase 4A
        cross_asset_engineer: Any | None = None,  # Phase 4C
        event_causal_engineer: Any | None = None,  # Phase 4D
    ) -> None:
        self._market_data = market_data
        self._tech = technical_analysis
        self._fe = feature_engineer
        self._predictors = predictors
        self._store = store
        self._tickers = tickers
        self._macro_symbols = macro_symbols
        self._market = market
        self._sentiment = sentiment_scorer
        self._stage2 = stage2_predictor
        self._buzz_store = buzz_store
        self._fundamental = fundamental_engineer
        self._cross_asset = cross_asset_engineer
        self._event_causal = event_causal_engineer

    def execute(self, prediction_date: datetime) -> WeeklyReport:
        """Run weekly tournament and return report."""
        week_start = prediction_date.strftime("%Y-%m-%d")

        # Fetch macro once
        macro_signals = self._fetch_macro(prediction_date)

        # Cache signals for cross-asset features
        if self._cross_asset is not None:
            self._signals_cache: dict[str, list] = {}  # type: ignore[type-arg]
            for t in self._tickers:
                try:
                    start = prediction_date - timedelta(days=365)
                    sigs = self._market_data.get_signals(
                        t, prediction_date, start_date=start
                    )
                    if len(sigs) >= 20:
                        self._signals_cache[t] = sigs
                except Exception:
                    continue
            # Build graph with cached signals
            self._cross_asset._graph.build_graph(self._signals_cache, window_days=60)

        # Score all tickers
        candidates: list[StockRecommendation] = []
        for ticker in self._tickers:
            try:
                rec = self._score_ticker(
                    ticker, prediction_date, week_start, macro_signals
                )
                if rec is not None:
                    candidates.append(rec)
            except Exception as e:
                logger.debug(f"Skipping {ticker}: {e}")
                continue

        # Rank by composite score, take top 15
        candidates.sort(key=lambda r: r.composite_score, reverse=True)
        top_picks = candidates[:15]

        # Store recommendations
        for rec in top_picks:
            self._store.save_recommendation(rec)

        report = WeeklyReport(
            report_date=week_start,
            market=self._market,
            recommendations=top_picks,
        )
        self._store.save_weekly_report(report)

        logger.info(
            f"Tournament complete: {len(top_picks)} picks from {len(candidates)} candidates"
        )
        return report

    def _score_ticker(
        self,
        ticker: str,
        prediction_time: datetime,
        week_start: str,
        macro_signals: dict[str, list],  # type: ignore[type-arg]
    ) -> StockRecommendation | None:
        start = prediction_time - timedelta(days=365)
        signals = self._market_data.get_signals(
            ticker, prediction_time, start_date=start
        )
        if len(signals) < 20:
            return None

        indicators = self._tech.compute_indicators(signals)
        ticker_info = self._market_data.get_ticker_info(ticker)
        options = self._market_data.get_options_summary(ticker, prediction_time)
        analyst = self._market_data.get_analyst_data(ticker, prediction_time)

        features = self._fe.compute(
            signals=signals,
            indicators=indicators,
            ticker_info=ticker_info,
            options_summary=options,
            analyst_data=analyst,
            macro_signals=macro_signals,
            sector_signals=None,
        )

        # Phase 4A: Add fundamental features
        if self._fundamental is not None:
            fundamental_features = self._fundamental.compute(
                ticker_info=ticker_info,
                sector_ticker_infos=[],  # Sector context added in future phase
                analyst_data=analyst,
            )
            features.update(fundamental_features)

        # Phase 4C: Add cross-asset features
        if self._cross_asset is not None:
            cross_features = self._cross_asset.compute(
                ticker=ticker,
                signals=signals,
                signals_by_ticker=getattr(self, "_signals_cache", {}),
            )
            features.update(cross_features)

        # Phase 4D: Add event-causal features
        if self._event_causal is not None:
            sector = ticker_info.get("sector", "") if ticker_info else ""
            if sector:
                event_features = self._event_causal.compute(
                    sector=sector,
                    current_date=prediction_time.strftime("%Y-%m-%d"),
                    recent_events=getattr(self, "_recent_events", []),
                    actual_sector_return_5d=0.0,
                )
                features.update(event_features)

        # Predict each horizon with confidence
        feature_row = [features]
        pred_2d, conf_2d = self._predict_with_confidence("2d", feature_row)
        pred_5d, conf_5d = self._predict_with_confidence("5d", feature_row)
        pred_10d, conf_10d = self._predict_with_confidence("10d", feature_row)

        prediction = MultiHorizonPrediction(
            predicted_return_2d=pred_2d,
            predicted_return_5d=pred_5d,
            predicted_return_10d=pred_10d,
            confidence_2d=conf_2d,
            confidence_5d=conf_5d,
            confidence_10d=conf_10d,
        )

        grade, horizon_signals = grade_from_horizons(prediction)

        # Composite score for ranking
        composite = pred_2d * 0.2 + pred_5d * 0.3 + pred_10d * 0.5

        # Stage 2 sentiment blend (ADR-014)
        composite = self._blend_with_sentiment(ticker, prediction_time, composite)

        return StockRecommendation(
            symbol=ticker,
            week_start=week_start,
            grade=grade,
            composite_score=composite,
            prediction=prediction,
            horizon_signals=horizon_signals,
            reasoning=f"Multi-horizon: 2d={pred_2d:.3f}, 5d={pred_5d:.3f}, 10d={pred_10d:.3f}",
            sources=["yfinance"],
            rsi_14=indicators.get("rsi_14"),
            macd=indicators.get("macd"),
        )

    def _blend_with_sentiment(
        self, ticker: str, prediction_time: datetime, stage1_composite: float
    ) -> float:
        """Blend Stage 1 composite with sentiment via Stage 2 (ADR-014)."""
        if self._sentiment is None or self._stage2 is None:
            return stage1_composite

        from adapters.ml.sentiment_feature_engineer import SentimentFeatureEngineer
        from domain.models import SourceReliability

        sfe = SentimentFeatureEngineer()

        # Get buzz signals from store
        buzz_current: list[Any] = []
        buzz_prior: list[Any] = []
        if self._buzz_store is not None:
            week_ago = prediction_time - timedelta(days=7)
            two_weeks_ago = prediction_time - timedelta(days=14)
            buzz_current = self._buzz_store.get_buzz_signals(
                ticker=ticker, start_date=week_ago, end_date=prediction_time
            )
            buzz_prior = self._buzz_store.get_buzz_signals(
                ticker=ticker, start_date=two_weeks_ago, end_date=week_ago
            )

        # Extract scorer averages from buzz signals
        kw_scores = [s.sentiment_raw for s in buzz_current if s.scorer == "keyword"]
        ft_scores = [s.sentiment_raw for s in buzz_current if s.scorer == "flan_t5"]
        kw_avg = sum(kw_scores) / len(kw_scores) if kw_scores else float("nan")
        ft_avg = sum(ft_scores) / len(ft_scores) if ft_scores else float("nan")

        # Get sentiments from sentiment scorer
        sentiments = self._sentiment.get_sentiment(ticker, prediction_time)

        # Get source reliability
        reliability = SourceReliability(
            source="aggregate", ticker=ticker, correct_calls=0, total_calls=0
        )
        if self._buzz_store is not None and hasattr(
            self._buzz_store, "get_source_reliability"
        ):
            reliability = self._buzz_store.get_source_reliability("aggregate", ticker)

        features = sfe.compute(
            keyword_sentiment=kw_avg,
            flan_t5_sentiment=ft_avg,
            sentiments=sentiments,
            buzz_signals_current=buzz_current,
            buzz_signals_prior=buzz_prior,
            sector_buzz_total=max(len(buzz_current), 1),
            reliability=reliability,
            price_return_5d=stage1_composite,
        )
        features["stage1_pred"] = stage1_composite

        preds = self._stage2.predict([features])
        return float(preds[0])

    def _predict_with_confidence(
        self, horizon: str, feature_row: list[dict[str, float]]
    ) -> tuple[float, float]:
        """Predict return and confidence for a single horizon."""
        predictor = self._predictors[horizon]
        if hasattr(predictor, "predict_with_confidence"):
            preds, confs = predictor.predict_with_confidence(feature_row)
            return preds[0], confs[0]
        preds = predictor.predict(feature_row)
        return preds[0], 0.5

    def _fetch_macro(self, prediction_time: datetime) -> dict[str, list]:  # type: ignore[type-arg]
        macro: dict[str, list] = {}  # type: ignore[type-arg]
        start = prediction_time - timedelta(days=365)
        for name, symbol in self._macro_symbols.items():
            for attempt in range(3):
                try:
                    macro[symbol] = self._market_data.get_signals(
                        symbol, prediction_time, start_date=start
                    )
                    break
                except Exception as e:  # pragma: no cover
                    logger.warning(f"Macro fetch {symbol} attempt {attempt + 1}: {e}")
                    time.sleep(5 * (attempt + 1))
            else:  # pragma: no cover
                macro[symbol] = []
        return macro


class TrackRecommendationsUseCase:
    """Evaluate last week's recommendations against actual returns."""

    def __init__(
        self,
        market_data: MarketDataPort,
        store: RecommendationStorePort,
    ) -> None:
        self._market_data = market_data
        self._store = store

    def execute(self, evaluation_date: datetime) -> list[AccuracyRecord]:
        """Compare predictions from last week with actual outcomes."""
        week_start = (evaluation_date - timedelta(days=7)).strftime("%Y-%m-%d")
        recs = self._store.get_recommendations(week_start=week_start)
        records: list[AccuracyRecord] = []

        for rec in recs:
            try:
                # Get actual returns
                signals = self._market_data.get_signals(
                    rec.symbol,
                    evaluation_date,
                    start_date=datetime.strptime(rec.week_start, "%Y-%m-%d"),
                )
                if len(signals) < 2:
                    continue

                base_price = signals[0].price

                actual_2d = self._get_return(signals, base_price, 2)
                actual_5d = self._get_return(signals, base_price, 5)
                actual_10d = self._get_return(signals, base_price, 10)

                record = AccuracyRecord(
                    symbol=rec.symbol,
                    week_start=rec.week_start,
                    predicted_grade=rec.grade.value,
                    predicted_return_2d=rec.prediction.predicted_return_2d,
                    predicted_return_5d=rec.prediction.predicted_return_5d,
                    predicted_return_10d=rec.prediction.predicted_return_10d,
                    actual_return_2d=actual_2d,
                    actual_return_5d=actual_5d,
                    actual_return_10d=actual_10d,
                    direction_correct_2d=self._same_direction(
                        rec.prediction.predicted_return_2d, actual_2d
                    ),
                    direction_correct_5d=self._same_direction(
                        rec.prediction.predicted_return_5d, actual_5d
                    ),
                    direction_correct_10d=self._same_direction(
                        rec.prediction.predicted_return_10d, actual_10d
                    ),
                )
                self._store.save_accuracy_record(record)
                records.append(record)
            except Exception as e:
                logger.debug(f"Could not evaluate {rec.symbol}: {e}")
                continue

        return records

    @staticmethod
    def _get_return(
        signals: list[Signal],
        base_price: float,
        days: int,
    ) -> float:
        if len(signals) > days:
            return float(signals[days].price / base_price - 1)
        return float(signals[-1].price / base_price - 1)

    @staticmethod
    def _same_direction(predicted: float, actual: float) -> bool:
        return (predicted > 0 and actual > 0) or (predicted < 0 and actual < 0)


class EvaluationUseCase:
    """Run full evaluation suite: walk-forward, permutation, costs, regime, drawdown."""

    def __init__(self, store: RecommendationStorePort) -> None:
        self._store = store

    def execute(
        self,
        eval_type: str = "full",
        **kwargs: Any,
    ) -> list[EvaluationRun]:
        """Run evaluation on stored walk-forward results."""
        from application.evaluation import FullEvaluationSuite

        runs = self._store.get_evaluation_runs(eval_type="walk_forward")
        if not runs:
            logger.warning("No walk-forward results to evaluate")
            return []

        predictions = [r.metric_value for r in runs if r.metric_name == "prediction"]
        actuals = [r.metric_value for r in runs if r.metric_name == "actual"]

        if not predictions or not actuals:
            logger.warning("No prediction/actual pairs found")
            return []

        suite = FullEvaluationSuite()
        report = suite.evaluate(
            predictions=predictions,
            actuals=actuals,
            spy_monthly_returns=kwargs.get(
                "spy_monthly_returns", [0.01] * len(predictions)
            ),
        )

        result_runs: list[EvaluationRun] = []
        run_date = kwargs.get("run_date", "unknown")
        for metric_name, value in report.items():
            if isinstance(value, (int, float)):
                run = EvaluationRun(
                    run_date=str(run_date),
                    eval_type="full_evaluation",
                    horizon="all",
                    metric_name=str(metric_name),
                    metric_value=float(value),
                )
                self._store.save_evaluation_run(run)
                result_runs.append(run)

        logger.info(f"Evaluation complete: {len(result_runs)} metrics computed")
        return result_runs
