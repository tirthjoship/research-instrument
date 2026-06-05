"""Tests for SQLite recommendation store (in-memory)."""

from datetime import datetime

import pytest

from adapters.data.sqlite_store import SQLiteStore
from domain.models import (
    AccuracyRecord,
    BuzzSignal,
    EvaluationRun,
    MultiHorizonPrediction,
    RecommendationGrade,
    StockRecommendation,
    WeeklyReport,
)


@pytest.fixture
def store() -> SQLiteStore:
    return SQLiteStore(":memory:")


@pytest.fixture
def sample_rec() -> StockRecommendation:
    pred = MultiHorizonPrediction(
        predicted_return_2d=0.03,
        predicted_return_5d=0.04,
        predicted_return_10d=0.06,
        confidence_2d=0.8,
        confidence_5d=0.7,
        confidence_10d=0.6,
    )
    return StockRecommendation(
        symbol="AAPL",
        week_start="2026-05-19",
        grade=RecommendationGrade.STRONG_BUY,
        composite_score=0.85,
        prediction=pred,
        horizon_signals={"2d": "bullish", "5d": "bullish", "10d": "bullish"},
        reasoning="Strong momentum",
        sources=["yfinance"],
        rsi_14=65.0,
        macd=1.2,
    )


def test_save_and_get_recommendation(
    store: SQLiteStore, sample_rec: StockRecommendation
) -> None:
    store.save_recommendation(sample_rec)
    results = store.get_recommendations(week_start="2026-05-19")
    assert len(results) == 1
    assert results[0].symbol == "AAPL"
    assert results[0].grade == RecommendationGrade.STRONG_BUY
    assert results[0].prediction.predicted_return_10d == 0.06


def test_get_recommendations_by_symbol(
    store: SQLiteStore, sample_rec: StockRecommendation
) -> None:
    store.save_recommendation(sample_rec)
    assert len(store.get_recommendations(symbol="AAPL")) == 1
    assert len(store.get_recommendations(symbol="GOOG")) == 0


def test_upsert_recommendation(
    store: SQLiteStore, sample_rec: StockRecommendation
) -> None:
    """Same symbol+week_start overwrites."""
    store.save_recommendation(sample_rec)
    store.save_recommendation(sample_rec)
    results = store.get_recommendations(week_start="2026-05-19")
    assert len(results) == 1


def test_save_and_get_accuracy_record(store: SQLiteStore) -> None:
    record = AccuracyRecord(
        symbol="AAPL",
        week_start="2026-05-12",
        predicted_grade="strong_buy",
        predicted_return_2d=0.03,
        predicted_return_5d=0.04,
        predicted_return_10d=0.06,
        actual_return_2d=0.025,
        actual_return_5d=0.035,
        actual_return_10d=0.055,
        direction_correct_2d=True,
        direction_correct_5d=True,
        direction_correct_10d=True,
    )
    store.save_accuracy_record(record)
    results = store.get_accuracy_records(week_start="2026-05-12")
    assert len(results) == 1
    assert results[0].actual_return_5d == 0.035


def test_save_and_get_evaluation_run(store: SQLiteStore) -> None:
    run = EvaluationRun(
        run_date="2026-05-25",
        eval_type="walk_forward",
        horizon="5d",
        metric_name="directional_accuracy",
        metric_value=0.58,
        p_value=0.03,
    )
    store.save_evaluation_run(run)
    results = store.get_evaluation_runs(run_date="2026-05-25")
    assert len(results) == 1
    assert results[0].p_value == 0.03


def test_save_and_get_weekly_report(
    store: SQLiteStore, sample_rec: StockRecommendation
) -> None:
    report = WeeklyReport(
        report_date="2026-05-19",
        market="us",
        recommendations=[sample_rec],
        spy_return_same_period=0.012,
        sharpe_ratio=1.5,
    )
    store.save_weekly_report(report)
    loaded = store.get_weekly_report("2026-05-19")
    assert loaded is not None
    assert loaded.market == "us"
    assert loaded.sharpe_ratio == 1.5


def test_get_missing_weekly_report_returns_none(store: SQLiteStore) -> None:
    assert store.get_weekly_report("2026-01-01") is None


def test_save_and_get_buzz_signals(tmp_path: pytest.TempPathFactory) -> None:
    store = SQLiteStore(str(tmp_path / "test.db"))  # type: ignore[arg-type]
    bs = BuzzSignal(
        ticker="AAPL",
        source="reuters_rss",
        mention_count=10,
        sentiment_raw=0.6,
        scorer="keyword",
        fetched_at=datetime(2026, 5, 30, 9, 0),
        article_hash="hash1",
    )
    store.save_buzz_signal(bs)
    results = store.get_buzz_signals(ticker="AAPL")
    assert len(results) == 1
    assert results[0].ticker == "AAPL"
    assert results[0].sentiment_raw == 0.6


def test_buzz_signal_dedup_by_hash(tmp_path: pytest.TempPathFactory) -> None:
    store = SQLiteStore(str(tmp_path / "test.db"))  # type: ignore[arg-type]
    bs = BuzzSignal(
        ticker="AAPL",
        source="reuters_rss",
        mention_count=10,
        sentiment_raw=0.6,
        scorer="keyword",
        fetched_at=datetime(2026, 5, 30, 9, 0),
        article_hash="hash1",
    )
    store.save_buzz_signal(bs)
    store.save_buzz_signal(bs)  # duplicate
    results = store.get_buzz_signals(ticker="AAPL")
    assert len(results) == 1


def test_get_buzz_signals_date_filter(tmp_path: pytest.TempPathFactory) -> None:
    store = SQLiteStore(str(tmp_path / "test.db"))  # type: ignore[arg-type]
    bs1 = BuzzSignal(
        ticker="AAPL",
        source="reuters_rss",
        mention_count=5,
        sentiment_raw=0.3,
        scorer="keyword",
        fetched_at=datetime(2026, 5, 28, 9, 0),
        article_hash="h1",
    )
    bs2 = BuzzSignal(
        ticker="AAPL",
        source="reuters_rss",
        mention_count=15,
        sentiment_raw=0.8,
        scorer="keyword",
        fetched_at=datetime(2026, 5, 30, 9, 0),
        article_hash="h2",
    )
    store.save_buzz_signal(bs1)
    store.save_buzz_signal(bs2)
    results = store.get_buzz_signals(ticker="AAPL", start_date=datetime(2026, 5, 29))
    assert len(results) == 1
    assert results[0].article_hash == "h2"


def test_save_and_get_source_reliability(tmp_path: pytest.TempPathFactory) -> None:
    store = SQLiteStore(str(tmp_path / "test.db"))  # type: ignore[arg-type]
    store.record_source_outcome(
        "reuters_rss", "AAPL", 0.5, 0.3
    )  # correct (both positive)
    store.record_source_outcome("reuters_rss", "AAPL", -0.2, 0.1)  # incorrect
    rel = store.get_source_reliability("reuters_rss", "AAPL")
    assert rel.correct_calls == 1
    assert rel.total_calls == 2


def test_get_source_reliability_missing(tmp_path: pytest.TempPathFactory) -> None:
    store = SQLiteStore(str(tmp_path / "test.db"))  # type: ignore[arg-type]
    rel = store.get_source_reliability("unknown_source", "AAPL")
    assert rel.correct_calls == 0
    assert rel.total_calls == 0


def test_get_source_reliability_aggregate(tmp_path: pytest.TempPathFactory) -> None:
    store = SQLiteStore(str(tmp_path / "test.db"))  # type: ignore[arg-type]
    store.record_source_outcome("reuters_rss", "AAPL", 0.5, 0.3)
    store.record_source_outcome("reuters_rss", "GOOG", -0.2, -0.1)
    rel = store.get_source_reliability("reuters_rss", None)
    assert rel.total_calls == 2
    assert rel.ticker is None


def test_get_all_source_reliabilities(tmp_path: pytest.TempPathFactory) -> None:
    store = SQLiteStore(str(tmp_path / "test.db"))  # type: ignore[arg-type]
    store.record_source_outcome("reuters_rss", "AAPL", 0.5, 0.3)
    store.record_source_outcome("reddit_wsb", "TSLA", -0.2, -0.1)
    all_rels = store.get_all_source_reliabilities()
    assert len(all_rels) == 2


# ---------------------------------------------------------------------------
# TrackedTrade + TradeOutcome persistence
# ---------------------------------------------------------------------------

from domain.outcome import TrackedTrade, TradeAction, TradeOutcome  # noqa: E402


def _make_trade(trade_id: str = "t1", ticker: str = "AAPL") -> TrackedTrade:
    return TrackedTrade(
        trade_id=trade_id,
        ticker=ticker,
        action=TradeAction.BUY,
        price=150.0,
        quantity=10,
        trade_date="2026-06-03",
        conviction_at_trade=0.82,
        signals_at_trade=["rsi_oversold", "macd_cross"],
        opportunity_card_id="opp-001",
        notes="Test trade",
    )


def _make_outcome(buy_id: str = "t1", sell_id: str = "t2") -> TradeOutcome:
    return TradeOutcome(
        ticker="AAPL",
        buy_trade_id=buy_id,
        sell_trade_id=sell_id,
        buy_price=150.0,
        sell_price=165.0,
        quantity=10,
        buy_date="2026-06-03",
        sell_date="2026-06-13",
        holding_days=10,
        return_pct=10.0,
        return_dollar=150.0,
        signals_at_entry=["rsi_oversold", "macd_cross"],
        conviction_at_entry=0.82,
    )


def test_save_and_load_trade(tmp_path: pytest.TempPathFactory) -> None:
    store = SQLiteStore(str(tmp_path / "trades.db"))  # type: ignore[arg-type]
    trade = _make_trade()
    store.save_trade(trade)
    results = store.get_trades()
    assert len(results) == 1
    loaded = results[0]
    assert loaded.trade_id == "t1"
    assert loaded.ticker == "AAPL"
    assert loaded.action == TradeAction.BUY
    assert loaded.price == 150.0
    assert loaded.quantity == 10
    assert loaded.signals_at_trade == ["rsi_oversold", "macd_cross"]
    assert loaded.conviction_at_trade == 0.82
    assert loaded.opportunity_card_id == "opp-001"
    assert loaded.notes == "Test trade"


def test_save_and_load_outcome(tmp_path: pytest.TempPathFactory) -> None:
    store = SQLiteStore(str(tmp_path / "outcomes.db"))  # type: ignore[arg-type]
    outcome = _make_outcome()
    store.save_trade_outcome(outcome)
    results = store.get_trade_outcomes()
    assert len(results) == 1
    loaded = results[0]
    assert loaded.ticker == "AAPL"
    assert loaded.return_pct == 10.0
    assert loaded.return_dollar == 150.0
    assert loaded.holding_days == 10
    assert loaded.signals_at_entry == ["rsi_oversold", "macd_cross"]
    assert loaded.conviction_at_entry == 0.82


def test_get_trades_all(tmp_path: pytest.TempPathFactory) -> None:
    store = SQLiteStore(str(tmp_path / "filter.db"))  # type: ignore[arg-type]
    store.save_trade(_make_trade("t1", "AAPL"))
    store.save_trade(_make_trade("t2", "GOOG"))
    # All trades
    all_trades = store.get_trades()
    assert len(all_trades) == 2
    # Filter by ticker
    aapl_trades = store.get_trades(ticker="AAPL")
    assert len(aapl_trades) == 1
    assert aapl_trades[0].ticker == "AAPL"
    goog_trades = store.get_trades(ticker="GOOG")
    assert len(goog_trades) == 1
    assert goog_trades[0].ticker == "GOOG"


# ---------------------------------------------------------------------------
# WeightAdjustment + LearnedRule persistence
# ---------------------------------------------------------------------------

from domain.pattern_memory import LearnedRule, WeightAdjustment  # noqa: E402


def test_save_and_load_weight_adjustment(tmp_path: pytest.TempPathFactory) -> None:
    store = SQLiteStore(str(tmp_path / "weights.db"))  # type: ignore[arg-type]
    adj = WeightAdjustment(
        dimension="sentiment",
        old_weight=0.3,
        new_weight=0.4,
        reason="Sentiment outperformed last 30 days",
        adjusted_date="2026-06-03",
    )
    store.save_weight_adjustment(adj)
    results = store.get_weight_history()
    assert len(results) == 1
    loaded = results[0]
    assert loaded.dimension == "sentiment"
    assert loaded.old_weight == 0.3
    assert loaded.new_weight == 0.4
    assert loaded.reason == "Sentiment outperformed last 30 days"
    assert loaded.adjusted_date == "2026-06-03"


def test_get_weight_history_filter_by_dimension(
    tmp_path: pytest.TempPathFactory,
) -> None:
    store = SQLiteStore(str(tmp_path / "weights2.db"))  # type: ignore[arg-type]
    adj1 = WeightAdjustment(
        dimension="sentiment",
        old_weight=0.3,
        new_weight=0.4,
        reason="Reason A",
        adjusted_date="2026-06-01",
    )
    adj2 = WeightAdjustment(
        dimension="technical",
        old_weight=0.5,
        new_weight=0.45,
        reason="Reason B",
        adjusted_date="2026-06-02",
    )
    store.save_weight_adjustment(adj1)
    store.save_weight_adjustment(adj2)
    all_results = store.get_weight_history()
    assert len(all_results) == 2
    sentiment_results = store.get_weight_history(dimension="sentiment")
    assert len(sentiment_results) == 1
    assert sentiment_results[0].dimension == "sentiment"


def test_save_and_load_learned_rule(tmp_path: pytest.TempPathFactory) -> None:
    store = SQLiteStore(str(tmp_path / "rules.db"))  # type: ignore[arg-type]
    rule = LearnedRule(
        rule_id="rule-001",
        description="RSI oversold + MACD cross = buy signal in tech",
        signal_combination=("rsi_oversold", "macd_cross"),
        sector="technology",
        action="boost",
        confidence=0.78,
        supporting_outcomes=42,
        learned_date="2026-06-03",
    )
    store.save_learned_rule(rule)
    results = store.get_learned_rules()
    assert len(results) == 1
    loaded = results[0]
    assert loaded.rule_id == "rule-001"
    assert loaded.description == "RSI oversold + MACD cross = buy signal in tech"
    assert loaded.signal_combination == ("rsi_oversold", "macd_cross")
    assert loaded.sector == "technology"
    assert loaded.action == "boost"
    assert loaded.confidence == 0.78
    assert loaded.supporting_outcomes == 42
    assert loaded.learned_date == "2026-06-03"


def test_attention_series_roundtrip(tmp_path: pytest.TempPathFactory) -> None:
    from adapters.data.sqlite_store import SQLiteStore
    from domain.models import AttentionPoint

    store = SQLiteStore(str(tmp_path / "t.db"))  # type: ignore[arg-type]
    pts = [
        AttentionPoint("ASTS", datetime(2026, 6, 1), 10.0, "google_trends"),
        AttentionPoint("ASTS", datetime(2026, 6, 2), 80.0, "wikipedia"),
    ]
    store.save_attention_points(pts)
    got = store.get_attention_series("ASTS", datetime(2026, 5, 1), datetime(2026, 7, 1))
    assert len(got) == 2


def test_attention_series_dedupe(tmp_path: pytest.TempPathFactory) -> None:
    from adapters.data.sqlite_store import SQLiteStore
    from domain.models import AttentionPoint

    store = SQLiteStore(str(tmp_path / "t.db"))  # type: ignore[arg-type]
    p = AttentionPoint("ASTS", datetime(2026, 6, 1), 10.0, "google_trends")
    store.save_attention_points([p])
    store.save_attention_points([p])  # re-run, must not duplicate
    got = store.get_attention_series("ASTS", datetime(2026, 5, 1), datetime(2026, 7, 1))
    assert len(got) == 1


def test_save_learned_rule_upsert(tmp_path: pytest.TempPathFactory) -> None:
    """INSERT OR REPLACE: same rule_id overwrites existing row."""
    store = SQLiteStore(str(tmp_path / "rules2.db"))  # type: ignore[arg-type]
    rule = LearnedRule(
        rule_id="rule-001",
        description="Original",
        signal_combination=("rsi_oversold",),
        sector="any",
        action="suppress",
        confidence=0.6,
        supporting_outcomes=10,
        learned_date="2026-06-01",
    )
    store.save_learned_rule(rule)
    updated = LearnedRule(
        rule_id="rule-001",
        description="Updated with more data",
        signal_combination=("rsi_oversold",),
        sector="any",
        action="suppress",
        confidence=0.75,
        supporting_outcomes=25,
        learned_date="2026-06-03",
    )
    store.save_learned_rule(updated)
    results = store.get_learned_rules()
    assert len(results) == 1
    assert results[0].confidence == 0.75
    assert results[0].supporting_outcomes == 25
