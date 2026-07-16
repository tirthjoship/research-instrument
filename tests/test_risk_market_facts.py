"""TDD tests for application/risk_market_facts.py — real regime label + real
SPY/VIX/sector-proxy news for the Risk tab's second-opinion, shared by the
weekly-brief CLI's only call site (Risk has no separate dashboard live path).
"""

from __future__ import annotations

import pytest

from application.news_context import NewsItem
from domain.regime import Regime


def test_risk_regime_fact_formats_each_regime_value() -> None:
    from application.risk_market_facts import risk_regime_fact

    assert risk_regime_fact(Regime.RISK_ON) == "Regime: RISK_ON"
    assert risk_regime_fact(Regime.NEUTRAL) == "Regime: NEUTRAL"
    assert risk_regime_fact(Regime.RISK_OFF) == "Regime: RISK_OFF"


def test_dominant_sector_picks_max_weight() -> None:
    from application.risk_market_facts import dominant_sector

    weights = {"Information Technology": 0.45, "Financials": 0.30, "Energy": 0.25}
    assert dominant_sector(weights) == "Information Technology"


def test_dominant_sector_none_on_empty() -> None:
    from application.risk_market_facts import dominant_sector

    assert dominant_sector({}) is None


def test_risk_market_news_always_fetches_spy_and_vix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from application import risk_market_facts as rmf

    calls: list[str] = []

    def _fake(ticker: str, **kw: object) -> list[dict[str, str]]:
        calls.append(ticker)
        return [
            {"source": "Reuters", "title": f"{ticker} headline", "date": "", "url": ""}
        ]

    monkeypatch.setattr(rmf, "_fetch_recent_news_impl", _fake)

    items = rmf.risk_market_news(None)

    assert calls == ["SPY", "^VIX"]
    assert items == [
        NewsItem(source="Reuters", title="SPY headline", date="", url=""),
        NewsItem(source="Reuters", title="^VIX headline", date="", url=""),
    ]


def test_risk_market_news_adds_sector_proxy_when_known(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from application import risk_market_facts as rmf

    calls: list[str] = []

    def _fake(ticker: str, **kw: object) -> list[dict[str, str]]:
        calls.append(ticker)
        return [{"source": "AP", "title": f"{ticker} headline", "date": "", "url": ""}]

    monkeypatch.setattr(rmf, "_fetch_recent_news_impl", _fake)

    items = rmf.risk_market_news("Information Technology")

    assert calls == ["SPY", "^VIX", "XLK"]
    assert items[-1] == NewsItem(source="AP", title="XLK headline", date="", url="")


def test_risk_market_news_uses_configured_benchmark_ticker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """risk_market_news(benchmark_ticker=...) fetches that ticker instead of the
    hardcoded "SPY" — needed so a CA/India Risk-tab read shows real benchmark
    news, not a US-only proxy."""
    from application import risk_market_facts as rmf

    calls: list[str] = []
    monkeypatch.setattr(
        rmf, "_fetch_recent_news_impl", lambda ticker, **kw: calls.append(ticker) or []
    )

    rmf.risk_market_news(None, benchmark_ticker="NIFTYBEES.NS")

    assert calls == ["NIFTYBEES.NS", "^VIX"]


def test_risk_market_news_omits_sector_when_unrecognized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from application import risk_market_facts as rmf

    calls: list[str] = []
    monkeypatch.setattr(
        rmf, "_fetch_recent_news_impl", lambda ticker, **kw: calls.append(ticker) or []
    )

    rmf.risk_market_news("Not A Real Sector")

    assert calls == ["SPY", "^VIX"]
