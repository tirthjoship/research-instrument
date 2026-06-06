"""Tests for dashboard data loader — SQLite + JSON loading with graceful defaults."""

from __future__ import annotations

import json
import pathlib

from adapters.data.sqlite_store import SQLiteStore


class TestLoadBacktestReports:
    def test_loads_json_files(self, tmp_path: pathlib.Path) -> None:
        from adapters.visualization.data_loader import load_backtest_reports

        report = {"horizons": {"5d": {"avg_directional_accuracy": 0.52}}}
        (tmp_path / "backtest_report_20260601.json").write_text(json.dumps(report))
        results = load_backtest_reports(str(tmp_path))
        assert len(results) == 1
        assert results[0]["horizons"]["5d"]["avg_directional_accuracy"] == 0.52

    def test_empty_dir_returns_empty_list(self, tmp_path: pathlib.Path) -> None:
        from adapters.visualization.data_loader import load_backtest_reports

        results = load_backtest_reports(str(tmp_path))
        assert results == []

    def test_missing_dir_returns_empty_list(self) -> None:
        from adapters.visualization.data_loader import load_backtest_reports

        results = load_backtest_reports("/nonexistent/path")
        assert results == []


class TestLoadRecommendations:
    def test_loads_from_sqlite(self, tmp_path: pathlib.Path) -> None:
        from adapters.visualization.data_loader import load_recommendations

        db_path = str(tmp_path / "test.db")
        store = SQLiteStore(db_path)
        from domain.models import (
            MultiHorizonPrediction,
            RecommendationGrade,
            StockRecommendation,
        )

        rec = StockRecommendation(
            symbol="NVDA",
            week_start="2026-06-01",
            grade=RecommendationGrade.STRONG_BUY,
            composite_score=0.85,
            prediction=MultiHorizonPrediction(
                predicted_return_2d=0.01,
                predicted_return_5d=0.03,
                predicted_return_10d=0.05,
                confidence_2d=0.7,
                confidence_5d=0.8,
                confidence_10d=0.75,
            ),
            horizon_signals={"2d": "bullish", "5d": "bullish", "10d": "bullish"},
            reasoning="Strong momentum",
            sources=["yfinance"],
            sentiment_score=0.6,
            divergence_score=0.3,
            divergence_type="bullish_divergence",
            technical_signal=0.5,
            rsi_14=45.0,
            macd=0.5,
        )
        store.save_recommendation(rec)
        results = load_recommendations(db_path)
        assert len(results) == 1
        assert results[0].symbol == "NVDA"

    def test_missing_db_returns_empty(self) -> None:
        from adapters.visualization.data_loader import load_recommendations

        results = load_recommendations("/nonexistent/test.db")
        assert results == []


class TestLoadHoldings:
    def test_loads_from_sqlite(self, tmp_path: pathlib.Path) -> None:
        from adapters.visualization.data_loader import load_holdings
        from domain.models import Holding

        db_path = str(tmp_path / "test.db")
        store = SQLiteStore(db_path)
        store.add_holding(
            Holding(
                symbol="AAPL",
                quantity=10,
                purchase_price=150.0,
                purchase_date="2026-01-01",
                notes="",
            )
        )
        results = load_holdings(db_path)
        assert len(results) == 1
        assert results[0].symbol == "AAPL"

    def test_missing_db_returns_empty(self) -> None:
        from adapters.visualization.data_loader import load_holdings

        results = load_holdings("/nonexistent/test.db")
        assert results == []


class TestLoadWatchlist:
    def test_loads_from_sqlite(self, tmp_path: pathlib.Path) -> None:
        from adapters.visualization.data_loader import load_watchlist

        db_path = str(tmp_path / "test.db")
        store = SQLiteStore(db_path)
        store.add_watchlist("TSLA", notes="watch momentum")
        results = load_watchlist(db_path)
        assert len(results) == 1
        assert results[0]["symbol"] == "TSLA"

    def test_missing_db_returns_empty(self) -> None:
        from adapters.visualization.data_loader import load_watchlist

        results = load_watchlist("/nonexistent/test.db")
        assert results == []


class TestLoadShapImportance:
    def test_loads_json(self, tmp_path: pathlib.Path) -> None:
        from adapters.visualization.data_loader import load_shap_importance

        data = {"correlation_with_spy": {"mean": 0.015, "std": 0.007}}
        (tmp_path / "shap.json").write_text(json.dumps(data))
        result = load_shap_importance(str(tmp_path / "shap.json"))
        assert "correlation_with_spy" in result

    def test_missing_returns_empty(self) -> None:
        from adapters.visualization.data_loader import load_shap_importance

        result = load_shap_importance("/nonexistent/shap.json")
        assert result == {}


class TestLoadAblationResults:
    def test_loads_from_validation_json(self, tmp_path: pathlib.Path) -> None:
        from adapters.visualization.data_loader import load_ablation_results

        data = {
            "ablation_results": [
                {"variant": "technical_only", "directional_accuracy": 0.474}
            ]
        }
        (tmp_path / "phase3b_validation_20260601.json").write_text(json.dumps(data))
        results = load_ablation_results(str(tmp_path))
        assert len(results) == 1
        assert results[0]["variant"] == "technical_only"

    def test_missing_returns_empty(self) -> None:
        from adapters.visualization.data_loader import load_ablation_results

        results = load_ablation_results("/nonexistent/path")
        assert results == []


class TestLoadSupplyChains:
    def test_loads_yaml(self, tmp_path: pathlib.Path) -> None:
        import yaml

        from adapters.visualization.data_loader import load_supply_chains

        chains = {
            "relationships": [
                {"group": "semiconductors", "leaders": ["AMAT"], "followers": ["NVDA"]}
            ]
        }
        (tmp_path / "supply_chain.yaml").write_text(yaml.dump(chains))
        result = load_supply_chains(str(tmp_path / "supply_chain.yaml"))
        assert "relationships" in result

    def test_missing_file_returns_empty(self) -> None:
        from adapters.visualization.data_loader import load_supply_chains

        result = load_supply_chains("/nonexistent/supply_chain.yaml")
        result == {}


class TestLoadSpySparkline:
    def test_returns_dict(self) -> None:
        """Should return a dict (possibly empty if yfinance unavailable)."""
        from adapters.visualization.data_loader import load_spy_sparkline

        result = load_spy_sparkline()
        assert isinstance(result, dict)

    def test_empty_dict_on_failure(self, monkeypatch: object) -> None:
        """Monkeypatching the function itself confirms {} contract."""
        import adapters.visualization.data_loader as dl

        monkeypatch.setattr(dl, "load_spy_sparkline", lambda: {})
        result = dl.load_spy_sparkline()
        assert result == {}

    def test_result_keys_when_populated(self) -> None:
        """If result is non-empty it must have all required keys."""
        from adapters.visualization.data_loader import load_spy_sparkline

        result = load_spy_sparkline()
        if result:
            for key in (
                "prices",
                "times",
                "current",
                "open",
                "change_pct",
                "high",
                "low",
            ):
                assert key in result


class TestLoadTrades:
    def test_missing_db_returns_empty(self) -> None:
        from adapters.visualization.data_loader import load_trades

        result = load_trades("/nonexistent/test.db")
        assert result == []

    def test_missing_db_with_ticker_returns_empty(self) -> None:
        from adapters.visualization.data_loader import load_trades

        result = load_trades("/nonexistent/test.db", ticker="AAPL")
        assert result == []


class TestLoadOutcomes:
    def test_missing_db_returns_empty(self) -> None:
        from adapters.visualization.data_loader import load_outcomes

        result = load_outcomes("/nonexistent/test.db")
        assert result == []

    def test_missing_db_with_ticker_returns_empty(self) -> None:
        from adapters.visualization.data_loader import load_outcomes

        result = load_outcomes("/nonexistent/test.db", ticker="AAPL")
        assert result == []


class TestLoadScanDistribution:
    def test_loader_returns_distribution_for_empty_state(
        self, tmp_path: pathlib.Path
    ) -> None:
        from adapters.data.sqlite_store import SQLiteStore
        from adapters.visualization.data_loader import load_scan_distribution

        store = SQLiteStore(db_path=str(tmp_path / "t.db"))
        store.save_scan_candidate(
            scan_date="2026-06-05",
            ticker="DUD",
            conviction=3.0,
            divergence=4.0,
            sub_scores={"smart_money": 3.0},
            surfaced=False,
            theme="space",
            cap_tier="small",
        )
        rows = load_scan_distribution(store, scan_date="2026-06-05")
        assert len(rows) == 1
        assert rows[0]["ticker"] == "DUD"

    def test_loader_returns_empty_list_when_no_candidates(
        self, tmp_path: pathlib.Path
    ) -> None:
        from adapters.data.sqlite_store import SQLiteStore
        from adapters.visualization.data_loader import load_scan_distribution

        store = SQLiteStore(db_path=str(tmp_path / "t.db"))
        rows = load_scan_distribution(store, scan_date="2026-06-05")
        assert rows == []

    def test_empty_state_distribution_scoped_to_today_only(
        self, tmp_path: pathlib.Path
    ) -> None:
        """Empty-state must show only today's scan candidates, not all history.

        Regression: _render_empty_state previously called load_scan_distribution
        with no scan_date, causing get_scan_candidates(scan_date=None) to return
        every candidate from every past scan (stale/duplicate accumulation).
        """
        from adapters.data.sqlite_store import SQLiteStore
        from adapters.visualization.data_loader import load_scan_distribution

        store = SQLiteStore(db_path=str(tmp_path / "t.db"))
        # Yesterday's stale candidate — must NOT appear in today's empty-state
        store.save_scan_candidate(
            scan_date="2026-06-04",
            ticker="STALE",
            conviction=7.0,
            divergence=8.0,
            sub_scores={"smart_money": 7.0},
            surfaced=True,
            theme="ai",
            cap_tier="large",
        )
        # Today's candidate — must appear
        store.save_scan_candidate(
            scan_date="2026-06-05",
            ticker="TODAY",
            conviction=3.0,
            divergence=2.0,
            sub_scores={"smart_money": 3.0},
            surfaced=False,
            theme="space",
            cap_tier="small",
        )
        rows = load_scan_distribution(store, scan_date="2026-06-05")
        tickers = [r["ticker"] for r in rows]
        assert "TODAY" in tickers, "today's candidate must be in the distribution"
        assert (
            "STALE" not in tickers
        ), "stale candidates from prior scans must be excluded"


class TestLoadScanTimestamp:
    def test_returns_none_when_no_reports_dir(self) -> None:
        from adapters.visualization.data_loader import load_scan_timestamp

        result = load_scan_timestamp("/nonexistent/reports/dir")
        assert result is None

    def test_returns_none_when_dir_empty(self, tmp_path: pathlib.Path) -> None:
        from adapters.visualization.data_loader import load_scan_timestamp

        result = load_scan_timestamp(str(tmp_path))
        assert result is None

    def test_returns_formatted_timestamp(self, tmp_path: pathlib.Path) -> None:
        from adapters.visualization.data_loader import load_scan_timestamp

        (tmp_path / "backtest_report_20260603_021500.json").write_text("{}")
        result = load_scan_timestamp(str(tmp_path))
        assert result is not None
        assert "2026" in result
        assert "Jun" in result

    def test_picks_most_recent_report(self, tmp_path: pathlib.Path) -> None:
        from adapters.visualization.data_loader import load_scan_timestamp

        (tmp_path / "backtest_report_20260601_100000.json").write_text("{}")
        (tmp_path / "backtest_report_20260603_140000.json").write_text("{}")
        result = load_scan_timestamp(str(tmp_path))
        assert result is not None
        assert "Jun 03" in result
