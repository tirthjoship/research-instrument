"""Tests for Phase 5 tab imports and helpers."""

from __future__ import annotations

from datetime import datetime, timedelta


def test_model_confidence_importable() -> None:
    from adapters.visualization.tabs.model_confidence import render

    assert callable(render)


def test_market_pulse_importable() -> None:
    from adapters.visualization.tabs.market_pulse import render

    assert callable(render)


def test_format_last_run_recent() -> None:
    """_format_last_run returns 'min ago' for a datetime less than 1h ago."""
    from adapters.visualization.tabs.market_pulse import _format_last_run

    dt = datetime.now() - timedelta(minutes=30)
    result = _format_last_run(dt)
    assert "min ago" in result


def test_format_last_run_hours() -> None:
    """_format_last_run returns 'h ago' for a datetime between 1h and 24h ago."""
    from adapters.visualization.tabs.market_pulse import _format_last_run

    dt = datetime.now() - timedelta(hours=5)
    result = _format_last_run(dt)
    assert "h ago" in result


def test_format_last_run_days() -> None:
    """_format_last_run returns 'd ago' for a datetime more than 24h ago."""
    from adapters.visualization.tabs.market_pulse import _format_last_run

    dt = datetime.now() - timedelta(days=3)
    result = _format_last_run(dt)
    assert "d ago" in result


def test_format_last_run_none() -> None:
    """_format_last_run returns empty string for None."""
    from adapters.visualization.tabs.market_pulse import _format_last_run

    assert _format_last_run(None) == ""


def test_format_last_run_iso_string() -> None:
    """_format_last_run handles ISO string input."""
    from adapters.visualization.tabs.market_pulse import _format_last_run

    dt = datetime.now() - timedelta(hours=2)
    result = _format_last_run(dt.isoformat())
    assert "h ago" in result


def test_ticker_tag_positive_change() -> None:
    """_ticker_tag uses green border for positive price change."""
    from adapters.visualization.tabs.market_pulse import _ticker_tag

    prices = {"AAPL": {"price": 150.0, "change_pct": 1.5}}
    html = _ticker_tag("AAPL", "#DBEAFE", prices)
    assert "#16A34A" in html
    assert "+1.5%" in html


def test_ticker_tag_negative_change() -> None:
    """_ticker_tag uses red border for negative price change."""
    from adapters.visualization.tabs.market_pulse import _ticker_tag

    prices = {"TSLA": {"price": 200.0, "change_pct": -2.3}}
    html = _ticker_tag("TSLA", "#FFEDD5", prices)
    assert "#DC2626" in html
    assert "-2.3%" in html


def test_ticker_tag_missing_ticker() -> None:
    """_ticker_tag shows gray border and no change for unknown ticker."""
    from adapters.visualization.tabs.market_pulse import _ticker_tag

    html = _ticker_tag("UNKNOWN", "#DBEAFE", {})
    assert "#D1D5DB" in html
    assert "UNKNOWN" in html
