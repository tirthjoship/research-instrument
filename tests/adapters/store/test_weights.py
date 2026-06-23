"""Tests for WeightsMixin."""

from __future__ import annotations

import pytest

from adapters.data.sqlite_store import SQLiteStore
from domain.pattern_memory import LearnedRule, WeightAdjustment


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
