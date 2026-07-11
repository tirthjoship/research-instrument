"""Tests for adapters.visualization.analysis.corroboration_bridge — no network, no Streamlit."""

from __future__ import annotations

import json
from types import SimpleNamespace

from adapters.visualization.analysis.corroboration_bridge import (
    build_readout_from_analysis,
)
from domain.corroboration_models import TrendHealth


def _result(**overrides: object) -> SimpleNamespace:
    base = {
        "ticker": "NVDA",
        "price_history": None,
        "peer_percentiles": {},
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_missing_price_history_gives_none_trend_no_crash() -> None:
    readout = build_readout_from_analysis(
        _result(price_history=None), holdings_path="/nonexistent/holdings.csv"
    )
    assert readout.trend_health is None
    assert readout.divergence_flag is False


def test_healthy_trend_from_price_history(tmp_path) -> None:
    # price above the 200-day SMA by more than 1 ATR => HEALTHY
    result = _result(price_history={"closes": [100.0], "ma200": 90.0, "atr": 2.0})
    readout = build_readout_from_analysis(
        result, holdings_path=str(tmp_path / "missing.csv")
    )
    assert readout.trend_health == TrendHealth.HEALTHY


def test_broken_trend_from_price_history(tmp_path) -> None:
    # price far below the 200-day SMA => BROKEN (< -2.0 ATR units)
    result = _result(price_history={"closes": [50.0], "ma200": 90.0, "atr": 2.0})
    readout = build_readout_from_analysis(
        result, holdings_path=str(tmp_path / "missing.csv")
    )
    assert readout.trend_health == TrendHealth.BROKEN


def test_empty_closes_list_gives_none_trend(tmp_path) -> None:
    result = _result(price_history={"closes": [], "ma200": 90.0, "atr": 2.0})
    readout = build_readout_from_analysis(
        result, holdings_path=str(tmp_path / "missing.csv")
    )
    assert readout.trend_health is None


def test_divergence_flag_always_false_deferred(tmp_path) -> None:
    readout = build_readout_from_analysis(
        _result(), holdings_path=str(tmp_path / "missing.csv")
    )
    assert readout.divergence_flag is False


def test_not_held_ticker_gets_clear_discipline_flag(tmp_path) -> None:
    holdings_path = tmp_path / "holdings.csv"
    holdings_path.write_text(
        "Symbol,Quantity,Exchange,Book Value (CAD),Account Type\n"
        "AAPL,10,NASDAQ,1000,TFSA\n"
    )
    readout = build_readout_from_analysis(
        _result(ticker="NVDA"), holdings_path=str(holdings_path)
    )
    assert readout.discipline_flag == "clear"


def test_held_ticker_leaves_discipline_flag_as_data_gap(tmp_path) -> None:
    holdings_path = tmp_path / "holdings.csv"
    holdings_path.write_text(
        "Symbol,Quantity,Exchange,Book Value (CAD),Account Type\n"
        "NVDA,10,NASDAQ,1000,TFSA\n"
    )
    readout = build_readout_from_analysis(
        _result(ticker="NVDA"), holdings_path=str(holdings_path)
    )
    assert readout.discipline_flag is None


def test_factor_percentile_from_screen_file(tmp_path) -> None:
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    screen = {
        "candidates": [
            {
                "ticker": "NVDA",
                "factor_scores": [
                    {"name": "momentum", "percentile": 0.9},
                    {"name": "value", "percentile": 0.7},
                ],
            }
        ]
    }
    (reports_dir / "screen_2026-07-01.json").write_text(json.dumps(screen))
    readout = build_readout_from_analysis(
        _result(ticker="NVDA"),
        holdings_path=str(tmp_path / "missing.csv"),
        reports_dir=str(reports_dir),
    )
    assert readout.factor_percentile is not None
    assert abs(readout.factor_percentile - 80.0) < 1e-9


def test_factor_percentile_falls_back_to_peer_percentiles_mean(tmp_path) -> None:
    result = _result(
        ticker="NVDA", peer_percentiles={"P/E": 60.0, "EV/EBITDA": 40.0, "gap": None}
    )
    readout = build_readout_from_analysis(
        result,
        holdings_path=str(tmp_path / "missing.csv"),
        reports_dir=str(tmp_path / "no_reports"),
    )
    assert readout.factor_percentile is not None
    assert abs(readout.factor_percentile - 50.0) < 1e-9


def test_factor_percentile_none_when_nothing_available(tmp_path) -> None:
    readout = build_readout_from_analysis(
        _result(peer_percentiles={}),
        holdings_path=str(tmp_path / "missing.csv"),
        reports_dir=str(tmp_path / "no_reports"),
    )
    assert readout.factor_percentile is None
