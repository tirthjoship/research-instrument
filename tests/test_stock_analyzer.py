"""Tests for stock_analyzer module — unit tests with mocked yfinance."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Fixtures / Helpers
# ---------------------------------------------------------------------------

MOCK_INFO = {
    "longName": "NVIDIA Corporation",
    "shortName": "NVIDIA",
    "currentPrice": 850.0,
    "regularMarketPrice": 850.0,
    "marketCap": 2_100_000_000_000,
    "sector": "Technology",
    "trailingPE": 55.0,
    "pegRatio": 1.8,
    "priceToBook": 35.0,
    "recommendationMean": 1.9,
    "targetMeanPrice": 1000.0,
    "freeCashflow": 20_000_000_000,
    "revenueGrowth": 0.22,
    "earningsGrowth": 0.35,
    "earningsQuarterlyGrowth": 0.40,
    "operatingMargins": 0.55,
    "returnOnEquity": 0.90,
    "grossMargins": 0.73,
    "profitMargins": 0.55,
    "debtToEquity": 42.0,
    "currentRatio": 4.2,
    "totalCash": 26_000_000_000,
    "totalDebt": 9_000_000_000,
    "ebitda": 50_000_000_000,
    "interestExpense": 300_000_000,
    "heldPercentInstitutions": 0.65,
    "heldPercentInsiders": 0.04,
    "institutionsCount": 3000,
    "numberOfAnalystOpinions": 50,
    "beta": 1.8,
    "fiftyTwoWeekLow": 400.0,
    "fiftyTwoWeekHigh": 1000.0,
}

MOCK_INSIDER_TXNS = [
    {"Transaction": "Buy", "Value": 1_000_000, "Date": "2026-01-15"},
    {"Transaction": "Buy", "Value": 500_000, "Date": "2026-02-20"},
    {"Transaction": "Sell", "Value": 200_000, "Date": "2026-03-05"},
]


# ---------------------------------------------------------------------------
# AnalysisResult dataclass
# ---------------------------------------------------------------------------


class TestAnalysisResultDataclass:
    def test_defaults_populated(self) -> None:
        from adapters.visualization.stock_analyzer import AnalysisResult

        result = AnalysisResult(
            ticker="NVDA",
            company_name="NVIDIA",
            current_price=850.0,
            change_pct=1.5,
            market_cap=2e12,
            sector="Technology",
        )
        assert result.ticker == "NVDA"
        assert result.signal_scores == {}
        assert result.valuation is None
        assert result.grade == "hold"
        assert result.conviction == 5.0
        assert result.hold_duration == "Monitor daily"

    def test_buzz_signals_defaults_empty(self) -> None:
        from adapters.visualization.stock_analyzer import AnalysisResult

        result = AnalysisResult(
            ticker="AAPL",
            company_name="Apple",
            current_price=180.0,
            change_pct=0.5,
            market_cap=3e12,
            sector="Technology",
        )
        assert result.buzz_signals == []
        assert result.insider_transactions == []
        assert result.peer_data == []


# ---------------------------------------------------------------------------
# SectionScore dataclass
# ---------------------------------------------------------------------------


class TestSectionScore:
    def test_section_score_fields(self) -> None:
        from adapters.visualization.stock_analyzer import SectionScore

        s = SectionScore(
            title="Valuation",
            score=4,
            max_score=6,
            summary="Good",
            verdicts=[("pass", "P/E is low")],
        )
        assert s.score == 4
        assert s.max_score == 6
        assert len(s.verdicts) == 1

    def test_verdict_status_values(self) -> None:
        from adapters.visualization.stock_analyzer import SectionScore

        s = SectionScore(
            title="Growth",
            score=3,
            max_score=6,
            summary="Mixed",
            verdicts=[("pass", "ok"), ("warn", "watch"), ("fail", "bad")],
        )
        statuses = [v[0] for v in s.verdicts]
        assert all(s in ("pass", "warn", "fail") for s in statuses)


# ---------------------------------------------------------------------------
# Scoring functions
# ---------------------------------------------------------------------------


class TestScoreValuation:
    def test_returns_section_score(self) -> None:
        from adapters.visualization.stock_analyzer import _score_valuation

        result = _score_valuation(MOCK_INFO, [])
        from adapters.visualization.stock_analyzer import SectionScore

        assert isinstance(result, SectionScore)
        assert result.max_score == 6

    def test_score_in_range(self) -> None:
        from adapters.visualization.stock_analyzer import _score_valuation

        result = _score_valuation(MOCK_INFO, [])
        assert 0 <= result.score <= result.max_score

    def test_empty_info_returns_zeros(self) -> None:
        from adapters.visualization.stock_analyzer import _score_valuation

        result = _score_valuation({}, [])
        assert result.score == 0
        assert result.max_score == 6

    def test_verdicts_count_equals_max_score(self) -> None:
        from adapters.visualization.stock_analyzer import _score_valuation

        result = _score_valuation(MOCK_INFO, [])
        assert len(result.verdicts) == result.max_score

    def test_high_quality_stock_scores_well(self) -> None:
        from adapters.visualization.stock_analyzer import _score_valuation

        good_info = {
            "trailingPE": 15.0,  # below sector avg
            "pegRatio": 1.0,
            "priceToBook": 2.0,
            "recommendationMean": 1.5,
            "currentPrice": 100.0,
            "targetMeanPrice": 130.0,
            "freeCashflow": 5_000_000_000,
            "marketCap": 50_000_000_000,
            "sector": "Technology",
        }
        result = _score_valuation(good_info, [])
        assert result.score >= 4

    def test_cad_ticker_shows_cad_symbol_in_target_verdict(self) -> None:
        from adapters.visualization.stock_analyzer import _score_valuation

        result = _score_valuation(MOCK_INFO, [], ticker="RY.TO")
        target_verdicts = [v for v in result.verdicts if "Analyst target" in v[1]]
        assert target_verdicts and "Analyst target C$1000.00" in target_verdicts[0][1]


class TestScoreGrowth:
    def test_returns_section_score(self) -> None:
        from adapters.visualization.stock_analyzer import _score_growth

        result = _score_growth(MOCK_INFO)
        from adapters.visualization.stock_analyzer import SectionScore

        assert isinstance(result, SectionScore)
        assert result.max_score == 6

    def test_score_in_range(self) -> None:
        from adapters.visualization.stock_analyzer import _score_growth

        result = _score_growth(MOCK_INFO)
        assert 0 <= result.score <= result.max_score

    def test_declining_revenue_reduces_score(self) -> None:
        from adapters.visualization.stock_analyzer import _score_growth

        bad_info = dict(MOCK_INFO)
        bad_info["revenueGrowth"] = -0.10
        bad_info["earningsGrowth"] = -0.15
        result = _score_growth(bad_info)
        # At least revenue and earnings growth checks fail
        assert result.score < 4


class TestScorePerformance:
    def test_returns_section_score(self) -> None:
        from adapters.visualization.stock_analyzer import _score_performance

        result = _score_performance(MOCK_INFO)
        assert result.max_score == 6

    def test_score_in_range(self) -> None:
        from adapters.visualization.stock_analyzer import _score_performance

        result = _score_performance(MOCK_INFO)
        assert 0 <= result.score <= result.max_score

    def test_high_roe_scores_well(self) -> None:
        from adapters.visualization.stock_analyzer import _score_performance

        result = _score_performance(MOCK_INFO)
        # MOCK_INFO has ROE=90% — both ROE checks should pass
        roe_verdicts = [v for v in result.verdicts if "ROE" in v[1]]
        assert all(v[0] == "pass" for v in roe_verdicts)


class TestScoreHealth:
    def test_returns_section_score(self) -> None:
        from adapters.visualization.stock_analyzer import _score_health

        result = _score_health(MOCK_INFO)
        assert result.max_score == 6

    def test_score_in_range(self) -> None:
        from adapters.visualization.stock_analyzer import _score_health

        result = _score_health(MOCK_INFO)
        assert 0 <= result.score <= result.max_score

    def test_strong_balance_sheet_scores_high(self) -> None:
        from adapters.visualization.stock_analyzer import _score_health

        # MOCK_INFO: cash > debt, FCF positive, low D/E
        result = _score_health(MOCK_INFO)
        assert result.score >= 4

    def test_indian_ticker_shows_rupee_symbol_in_cash_debt_verdict(self) -> None:
        from adapters.visualization.stock_analyzer import _score_health

        result = _score_health(MOCK_INFO, ticker="RELIANCE.NS")
        cash_verdicts = [v for v in result.verdicts if v[1].startswith("Cash (")]
        assert cash_verdicts and "₹" in cash_verdicts[0][1]
        assert "$" not in cash_verdicts[0][1]

    def test_empty_info_returns_zeros(self) -> None:
        from adapters.visualization.stock_analyzer import _score_health

        result = _score_health({})
        assert result.score == 0


class TestScoreOwnership:
    def test_returns_section_score(self) -> None:
        from adapters.visualization.stock_analyzer import _score_ownership

        result = _score_ownership(MOCK_INFO, MOCK_INSIDER_TXNS)
        assert result.max_score == 5

    def test_score_in_range(self) -> None:
        from adapters.visualization.stock_analyzer import _score_ownership

        result = _score_ownership(MOCK_INFO, MOCK_INSIDER_TXNS)
        assert 0 <= result.score <= result.max_score

    def test_net_insider_buying_passes(self) -> None:
        from adapters.visualization.stock_analyzer import _score_ownership

        # 2 buys vs 1 sell
        result = _score_ownership(MOCK_INFO, MOCK_INSIDER_TXNS)
        buying_verdicts = [
            v
            for v in result.verdicts
            if "buying" in v[1].lower() or "buys" in v[1].lower()
        ]
        assert len(buying_verdicts) > 0
        assert any(v[0] == "pass" for v in buying_verdicts)

    def test_no_insider_txns(self) -> None:
        from adapters.visualization.stock_analyzer import _score_ownership

        result = _score_ownership(MOCK_INFO, [])
        # No sells = pass for the velocity check
        assert result.score >= 1


class TestScoreSentiment:
    def test_empty_buzz_returns_zero_with_warning(self) -> None:
        from adapters.visualization.stock_analyzer import _score_sentiment

        result = _score_sentiment([])
        assert result.score == 0
        assert result.max_score == 5
        assert any(v[0] == "warn" for v in result.verdicts)

    def test_positive_buzz_scores_well(self) -> None:
        from adapters.visualization.stock_analyzer import _score_sentiment

        mock_buzz = [
            MagicMock(sentiment_raw=0.7, source="rss", mention_count=5),
            MagicMock(sentiment_raw=0.5, source="reddit", mention_count=8),
            MagicMock(sentiment_raw=0.6, source="rss", mention_count=6),
        ]
        result = _score_sentiment(mock_buzz)
        assert result.score >= 3

    def test_negative_buzz_scores_low(self) -> None:
        from adapters.visualization.stock_analyzer import _score_sentiment

        mock_buzz = [
            MagicMock(sentiment_raw=-0.8, source="rss", mention_count=2),
            MagicMock(sentiment_raw=-0.6, source="rss", mention_count=1),
        ]
        result = _score_sentiment(mock_buzz)
        assert result.score <= 2


class TestScoreSupplyChain:
    def test_none_group_returns_zero(self) -> None:
        from adapters.visualization.stock_analyzer import _score_supply_chain

        result = _score_supply_chain(None)
        assert result.score == 0
        assert result.max_score == 4

    def test_in_group_scores_at_least_one(self) -> None:
        from adapters.visualization.stock_analyzer import _score_supply_chain

        group = {
            "group": "semiconductors",
            "leaders": ["AMAT", "LRCX", "KLAC", "ASML"],
            "followers": ["MU", "WDC", "INTC", "AMD", "NVDA"],
            "typical_lag_days": 2,
            "notes": "Equipment makers lead chip producers",
            "_is_leader": False,
        }
        result = _score_supply_chain(group)
        assert result.score >= 1
        assert result.max_score == 4

    def test_large_group_scores_higher(self) -> None:
        from adapters.visualization.stock_analyzer import _score_supply_chain

        group = {
            "group": "big_tech",
            "leaders": ["AAPL", "MSFT", "GOOG", "AMZN", "META"],
            "followers": ["TSM", "AVGO", "QCOM", "TXN", "ADI"],
            "typical_lag_days": 1,
            "notes": "",
            "_is_leader": True,
        }
        result = _score_supply_chain(group)
        assert result.score >= 3


# ---------------------------------------------------------------------------
# Signal radar
# ---------------------------------------------------------------------------


class TestComputeSignalRadar:
    def test_returns_six_dimensions(self) -> None:
        from adapters.visualization.stock_analyzer import _compute_signal_radar

        scores = _compute_signal_radar(MOCK_INFO, [], None, None, [])
        assert len(scores) == 6
        assert set(scores.keys()) == {
            "Technical",
            "Sentiment",
            "Fundamental",
            "Cross-Asset",
            "Event-Causal",
            "Smart Money",
        }

    def test_all_scores_in_range(self) -> None:
        from adapters.visualization.stock_analyzer import _compute_signal_radar

        scores = _compute_signal_radar(MOCK_INFO, [], None, None, MOCK_INSIDER_TXNS)
        for dim, val in scores.items():
            assert 0.0 <= val <= 10.0, f"{dim} score {val} out of range [0, 10]"

    def test_empty_info_still_returns_scores(self) -> None:
        from adapters.visualization.stock_analyzer import _compute_signal_radar

        scores = _compute_signal_radar({}, [], None, None, [])
        assert len(scores) == 6
        for val in scores.values():
            assert 0.0 <= val <= 10.0

    def test_positive_buzz_raises_sentiment_score(self) -> None:
        from adapters.visualization.stock_analyzer import _compute_signal_radar

        pos_buzz = [MagicMock(sentiment_raw=0.9, source="rss")]
        neg_buzz = [MagicMock(sentiment_raw=-0.9, source="rss")]
        scores_pos = _compute_signal_radar(MOCK_INFO, pos_buzz, None, None, [])
        scores_neg = _compute_signal_radar(MOCK_INFO, neg_buzz, None, None, [])
        assert scores_pos["Sentiment"] > scores_neg["Sentiment"]


# ---------------------------------------------------------------------------
# analyze_ticker integration (mocked)
# ---------------------------------------------------------------------------


_PC = "adapters.visualization.price_cache"


class TestAnalyzeTicker:
    def test_returns_analysis_result(self) -> None:
        from adapters.visualization.stock_analyzer import AnalysisResult, analyze_ticker

        with (
            patch(f"{_PC}._fetch_ticker_info_impl", return_value=MOCK_INFO),
            patch(
                f"{_PC}._batch_fetch_prices_impl",
                return_value={"NVDA": {"price": 850.0, "change_pct": 1.5}},
            ),
            patch(
                f"{_PC}._fetch_quarterly_financials_impl",
                return_value=(None, None, None),
            ),
            patch(
                f"{_PC}._fetch_insider_transactions_impl",
                return_value=MOCK_INSIDER_TXNS,
            ),
            patch(
                "adapters.visualization.analysis.analyze.load_buzz_signals",
                return_value=[],
            ),
            patch(
                "adapters.visualization.analysis.analyze.load_recommendation",
                return_value=None,
            ),
            patch(
                "adapters.visualization.analysis.analyze.resolve_supply_chain_group",
                return_value=None,
            ),
            patch(
                "adapters.visualization.analysis.analyze.get_sector_peers",
                return_value=[],
            ),
        ):
            result = analyze_ticker("NVDA")

        assert isinstance(result, AnalysisResult)
        assert result.ticker == "NVDA"

    def _run_analyze(
        self, info: dict = MOCK_INFO, rec: object = None, prices: dict | None = None
    ) -> object:
        from adapters.visualization.stock_analyzer import analyze_ticker

        if prices is None:
            prices = {"NVDA": {"price": 850.0, "change_pct": 1.5}}
        with (
            patch(f"{_PC}._fetch_ticker_info_impl", return_value=info),
            patch(f"{_PC}._batch_fetch_prices_impl", return_value=prices),
            patch(
                f"{_PC}._fetch_quarterly_financials_impl",
                return_value=(None, None, None),
            ),
            patch(f"{_PC}._fetch_insider_transactions_impl", return_value=[]),
            patch(
                "adapters.visualization.analysis.analyze.load_buzz_signals",
                return_value=[],
            ),
            patch(
                "adapters.visualization.analysis.analyze.load_recommendation",
                return_value=rec,
            ),
            patch(
                "adapters.visualization.analysis.analyze.resolve_supply_chain_group",
                return_value=None,
            ),
            patch(
                "adapters.visualization.analysis.analyze.get_sector_peers",
                return_value=[],
            ),
        ):
            return analyze_ticker("NVDA")

    def test_all_sections_populated(self) -> None:
        result = self._run_analyze()
        assert result.valuation is not None
        assert result.growth is not None
        assert result.performance is not None
        assert result.health is not None
        assert result.ownership is not None
        assert result.sentiment is not None
        assert result.supply_chain is not None

    def test_signal_radar_populated(self) -> None:
        result = self._run_analyze()
        assert len(result.signal_scores) == 6
        for v in result.signal_scores.values():
            assert 0.0 <= v <= 10.0

    def test_ticker_normalized_to_uppercase(self) -> None:
        from adapters.visualization.stock_analyzer import analyze_ticker

        with (
            patch(f"{_PC}._fetch_ticker_info_impl", return_value=MOCK_INFO),
            patch(
                f"{_PC}._batch_fetch_prices_impl",
                return_value={"NVDA": {"price": 850.0, "change_pct": 1.5}},
            ),
            patch(
                f"{_PC}._fetch_quarterly_financials_impl",
                return_value=(None, None, None),
            ),
            patch(f"{_PC}._fetch_insider_transactions_impl", return_value=[]),
            patch(
                "adapters.visualization.analysis.analyze.load_buzz_signals",
                return_value=[],
            ),
            patch(
                "adapters.visualization.analysis.analyze.load_recommendation",
                return_value=None,
            ),
            patch(
                "adapters.visualization.analysis.analyze.resolve_supply_chain_group",
                return_value=None,
            ),
            patch(
                "adapters.visualization.analysis.analyze.get_sector_peers",
                return_value=[],
            ),
        ):
            result = analyze_ticker("nvda")

        assert result.ticker == "NVDA"

    def test_analyst_recommendation_derived(self) -> None:
        buy_info = dict(MOCK_INFO)
        buy_info["recommendationMean"] = 2.0
        result = self._run_analyze(info=buy_info)
        assert result.analyst_recommendation == "Buy"

    def test_supply_chain_group_gets_co_movement_wired(self) -> None:
        from adapters.visualization.stock_analyzer import analyze_ticker

        group = {
            "group": "AI semis",
            "leaders": ["NVDA"],
            "followers": ["AMD"],
            "typical_lag_days": 2,
            "_is_leader": True,
        }
        closes = {
            "NVDA": [100.0, 102.0, 101.0, 104.0],
            "AMD": [50.0, 51.0, 50.5, 52.0],
        }
        with (
            patch(f"{_PC}._fetch_ticker_info_impl", return_value=MOCK_INFO),
            patch(
                f"{_PC}._batch_fetch_prices_impl",
                return_value={
                    "NVDA": {"price": 850.0, "change_pct": 1.5},
                    "AMD": {"price": 150.0, "change_pct": -0.5},
                },
            ),
            patch(f"{_PC}._batch_fetch_closes_impl", return_value=closes),
            patch(
                f"{_PC}._fetch_quarterly_financials_impl",
                return_value=(None, None, None),
            ),
            patch(f"{_PC}._fetch_insider_transactions_impl", return_value=[]),
            patch(
                "adapters.visualization.analysis.analyze.load_buzz_signals",
                return_value=[],
            ),
            patch(
                "adapters.visualization.analysis.analyze.load_recommendation",
                return_value=None,
            ),
            patch(
                "adapters.visualization.analysis.analyze.resolve_supply_chain_group",
                return_value=group,
            ),
            patch(
                "adapters.visualization.analysis.analyze.get_sector_peers",
                return_value=[],
            ),
        ):
            result = analyze_ticker("NVDA")

        assert result.supply_chain_group is not None
        assert result.supply_chain_group["co_movement"] is not None
        assert isinstance(result.supply_chain_group["co_movement"], float)


# ---------------------------------------------------------------------------
# Hold duration derivation
# ---------------------------------------------------------------------------


class TestHoldDuration:
    def _make_rec(self, horizon_signals: dict) -> MagicMock:
        rec = MagicMock()
        rec.grade = "buy"
        rec.composite_score = 0.7
        rec.horizon_signals = horizon_signals
        return rec

    def _run(self, rec: object) -> object:
        from adapters.visualization.stock_analyzer import analyze_ticker

        with (
            patch(f"{_PC}._fetch_ticker_info_impl", return_value=MOCK_INFO),
            patch(
                f"{_PC}._batch_fetch_prices_impl",
                return_value={"NVDA": {"price": 850.0, "change_pct": 0.0}},
            ),
            patch(
                f"{_PC}._fetch_quarterly_financials_impl",
                return_value=(None, None, None),
            ),
            patch(f"{_PC}._fetch_insider_transactions_impl", return_value=[]),
            patch(
                "adapters.visualization.analysis.analyze.load_buzz_signals",
                return_value=[],
            ),
            patch(
                "adapters.visualization.analysis.analyze.load_recommendation",
                return_value=rec,
            ),
            patch(
                "adapters.visualization.analysis.analyze.resolve_supply_chain_group",
                return_value=None,
            ),
            patch(
                "adapters.visualization.analysis.analyze.get_sector_peers",
                return_value=[],
            ),
        ):
            return analyze_ticker("NVDA")

    def test_all_bullish_returns_long_hold(self) -> None:
        rec = self._make_rec({"2d": "bullish", "5d": "bullish", "10d": "bullish"})
        result = self._run(rec)
        assert "10+" in result.hold_duration

    def test_2d_only_bullish_returns_short_hold(self) -> None:
        rec = self._make_rec({"2d": "bullish", "5d": "bearish", "10d": "bearish"})
        result = self._run(rec)
        assert "Short" in result.hold_duration

    def test_no_rec_defaults_to_monitor_daily(self) -> None:
        result = self._run(None)
        assert result.hold_duration == "Monitor daily"


# ---------------------------------------------------------------------------
# Insider aggregation
# ---------------------------------------------------------------------------


class TestAggregateInsiderByQuarter:
    def test_basic_aggregation(self) -> None:
        from adapters.visualization.stock_analyzer import aggregate_insider_by_quarter

        txns = [
            {"Transaction": "Buy", "Value": 1_000_000, "Date": "2026-01-15"},
            {"Transaction": "Buy", "Value": 500_000, "Date": "2026-01-20"},
            {"Transaction": "Sell", "Value": 200_000, "Date": "2026-02-10"},
        ]
        result = aggregate_insider_by_quarter(txns)
        assert len(result) >= 1
        # All should be Q1 2026
        quarters = {r["quarter"] for r in result}
        assert "Q1 2026" in quarters

    def test_empty_transactions_returns_empty(self) -> None:
        from adapters.visualization.stock_analyzer import aggregate_insider_by_quarter

        result = aggregate_insider_by_quarter([])
        assert result == []

    def test_buy_value_accumulated(self) -> None:
        from adapters.visualization.stock_analyzer import aggregate_insider_by_quarter

        txns = [
            {"Transaction": "Buy", "Value": 1_000_000, "Date": "2026-01-15"},
            {"Transaction": "Buy", "Value": 2_000_000, "Date": "2026-01-20"},
        ]
        result = aggregate_insider_by_quarter(txns)
        q1 = next(r for r in result if r["quarter"] == "Q1 2026")
        assert q1["buy_value"] == 3_000_000
        assert q1["buys"] == 2

    def test_max_8_quarters_returned(self) -> None:
        from adapters.visualization.stock_analyzer import aggregate_insider_by_quarter

        txns = []
        for year in range(2020, 2030):
            for month in [1, 4, 7, 10]:
                txns.append(
                    {
                        "Transaction": "Buy",
                        "Value": 100_000,
                        "Date": f"{year}-{month:02d}-01",
                    }
                )
        result = aggregate_insider_by_quarter(txns)
        assert len(result) <= 8


# ---------------------------------------------------------------------------
# Supply chain finder
# ---------------------------------------------------------------------------


class TestFindSupplyChainGroup:
    def test_ticker_in_leaders_found(self) -> None:
        from adapters.visualization.stock_analyzer import _find_supply_chain_group

        with (
            patch("builtins.open", create=True) as mock_open,
            patch("os.path.exists", return_value=True),
        ):
            import io

            yaml_content = """
relationships:
  - group: semiconductors
    leaders: [AMAT, LRCX]
    followers: [NVDA, AMD]
    typical_lag_days: 2
    notes: "test"
"""
            mock_open.return_value.__enter__ = lambda self: io.StringIO(yaml_content)
            mock_open.return_value.__exit__ = MagicMock(return_value=False)

            import yaml

            with patch("yaml.safe_load", return_value=yaml.safe_load(yaml_content)):
                result = _find_supply_chain_group("AMAT")

            if result is not None:
                assert result["group"] == "semiconductors"
                assert result["_is_leader"] is True

    def test_ticker_not_in_any_group_returns_none(self) -> None:
        from adapters.visualization.stock_analyzer import _find_supply_chain_group

        with patch("os.path.exists", return_value=False):
            result = _find_supply_chain_group("UNKNOWN_TICKER_XYZ")

        assert result is None
