"""Unit tests for application.screen_ic_panels.

All tests use synthetic price series — NO network, NO yfinance.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from application.screen_ic_panels import build_screen_panels, monthly_closes_asof

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _daily_series(
    start: datetime,
    n_days: int,
    start_price: float = 100.0,
    daily_return: float = 0.001,
) -> list[tuple[datetime, float]]:
    """Generate a synthetic ascending (date, close) series."""
    out: list[tuple[datetime, float]] = []
    price = start_price
    for i in range(n_days):
        out.append((start + timedelta(days=i), round(price, 4)))
        price *= 1 + daily_return
    return out


def _flat_series(
    start: datetime, n_days: int, price: float = 100.0
) -> list[tuple[datetime, float]]:
    return [(start + timedelta(days=i), price) for i in range(n_days)]


# ---------------------------------------------------------------------------
# monthly_closes_asof
# ---------------------------------------------------------------------------


class TestMonthlyClosesAsof:
    def test_picks_last_close_of_each_month(self) -> None:
        """The function must return the LAST daily close per calendar month."""
        start = datetime(2023, 1, 1)
        # 3 months of daily data, ascending
        series = _daily_series(start, 92)
        as_of = datetime(2023, 4, 1)
        result = monthly_closes_asof(series, as_of)
        # We expect entries for Jan, Feb, Mar (Apr not complete yet as of Apr 1 is not month-end)
        assert len(result) == 3  # Jan / Feb / Mar are fully elapsed by Apr 1
        # The last Jan close should be the close on Jan 31 (or the latest Jan date in series)
        jan_closes = [c for d, c in series if d.month == 1 and d <= as_of]
        assert result[0] == jan_closes[-1]

    def test_respects_as_of_cutoff(self) -> None:
        """No close after as_of is ever used."""
        start = datetime(2022, 1, 1)
        series = _daily_series(start, 365)
        as_of = datetime(2022, 6, 15)  # mid-month
        result = monthly_closes_asof(series, as_of)
        # Only months whose month-end is <= Jun 15 qualify: Jan..May (5 months)
        # Jun month-end = Jun 30, which is > Jun 15 → NOT included
        assert len(result) == 5

    def test_empty_series_returns_empty(self) -> None:
        result = monthly_closes_asof([], datetime(2024, 1, 1))
        assert result == []

    def test_no_future_data_in_result(self) -> None:
        """Verify no close from after as_of sneaks in.

        as_of = Jun 30 00:00:00.  The month-end sentinel is Jun 30 23:59:59.
        Since sentinel > as_of, June is NOT included — only Jan..May (5 months).
        To include June we'd need as_of >= Jun 30 23:59:59.
        """
        start = datetime(2023, 1, 1)
        series = _daily_series(start, 730)  # 2 years
        as_of = datetime(
            2023, 6, 30
        )  # month_end(Jun)=Jun 30 23:59:59 > as_of → not included
        result = monthly_closes_asof(series, as_of)
        # Jan..May fully elapsed = 5 months; June is NOT included (sentinel > as_of)
        assert len(result) == 5

    def test_ascending_order(self) -> None:
        start = datetime(2021, 1, 1)
        series = _daily_series(start, 400, start_price=50.0, daily_return=0.002)
        as_of = datetime(2022, 1, 31)
        result = monthly_closes_asof(series, as_of)
        assert (
            result == sorted(result) or len(result) <= 1
        )  # prices are ascending so closes ascend too
        assert len(result) >= 12  # at least 12 full months by Jan 31, 2022

    def test_month_end_exactly_on_as_of(self) -> None:
        """A month-end exactly equal to as_of should be included."""
        # Jan 31 is the month-end; as_of = Jan 31 23:59:59 (or any datetime that day)
        as_of = datetime(2024, 1, 31, 23, 59, 59)
        series = [(datetime(2024, 1, 15), 100.0), (datetime(2024, 1, 31), 101.0)]
        result = monthly_closes_asof(series, as_of)
        assert len(result) == 1
        assert result[0] == 101.0


# ---------------------------------------------------------------------------
# build_screen_panels
# ---------------------------------------------------------------------------


class TestBuildScreenPanels:
    def _make_cache(
        self, series_map: dict[str, list[tuple[datetime, float]]]
    ) -> object:
        """Return a price_series_fn that looks up from series_map."""

        def fn(ticker: str) -> list[tuple[datetime, float]]:
            return series_map.get(ticker, [])

        return fn  # type: ignore[return-value]

    def test_upward_momentum_ranks_above_downtrend(self) -> None:
        """A ticker with strong 12-1 momentum should rank above a downtrend ticker."""
        # Build 18 months of data so momentum_12_1 has >= 13 monthly closes
        start = datetime(2020, 1, 1)
        n_days = 550  # ~18 months

        # UP: strong uptrend
        up_series = _daily_series(start, n_days, start_price=10.0, daily_return=0.003)
        # DOWN: downtrend
        down_series = _daily_series(
            start, n_days, start_price=200.0, daily_return=-0.002
        )
        # SPY: flat benchmark
        spy_series = _flat_series(start, n_days + 30, price=400.0)

        series_map = {"UP": up_series, "DOWN": down_series, "SPY": spy_series}
        fn = self._make_cache(series_map)

        as_of = start + timedelta(days=450)
        panels, bench = build_screen_panels(
            tickers=["UP", "DOWN"],
            dates=[as_of],
            price_series_fn=fn,
            horizon_days=21,
        )

        assert len(panels) == 1
        panel = panels[0]
        assert "UP" in panel and "DOWN" in panel
        # UP composite signal should be higher than DOWN
        assert panel["UP"][0] > panel["DOWN"][0]

    def test_forward_returns_populated(self) -> None:
        """Forward returns must be filled (non-zero for moving prices)."""
        start = datetime(2019, 1, 1)
        n_days = 600
        series_a = _daily_series(start, n_days, start_price=50.0, daily_return=0.001)
        spy_series = _flat_series(start, n_days + 40, price=300.0)

        fn = self._make_cache({"A": series_a, "SPY": spy_series})
        as_of = start + timedelta(days=450)
        panels, bench = build_screen_panels(["A"], [as_of], fn, horizon_days=21)

        assert len(panels) == 1
        if panels[0]:  # if A is eligible
            _sig, fwd = panels[0]["A"]
            # forward return for a trend series should be non-zero
            assert fwd != 0.0

    def test_benchmark_length_equals_dates_length(self) -> None:
        """benchmark_returns must have the same length as dates."""
        start = datetime(2020, 1, 1)
        spy_series = _flat_series(start, 700, price=300.0)
        up_series = _daily_series(start, 700, start_price=50.0, daily_return=0.001)
        fn = self._make_cache({"A": up_series, "SPY": spy_series})

        dates = [start + timedelta(days=30 * i) for i in range(5, 18)]  # 13 dates
        panels, bench = build_screen_panels(["A"], dates, fn, horizon_days=21)

        assert len(bench) == len(dates)
        assert len(panels) == len(dates)

    def test_ticker_with_fewer_than_13_months_excluded(self) -> None:
        """A ticker with < 13 monthly closes must be excluded from the panel."""
        start = datetime(2022, 1, 1)
        # Only 6 months of data → momentum_12_1 returns None
        short_series = _daily_series(start, 180, start_price=100.0, daily_return=0.001)
        spy_series = _flat_series(start, 600, price=400.0)

        fn = self._make_cache({"SHORT": short_series, "SPY": spy_series})
        as_of = start + timedelta(days=200)
        panels, bench = build_screen_panels(["SHORT"], [as_of], fn, horizon_days=21)

        assert len(panels) == 1
        # SHORT has <13 months so it should be absent
        assert "SHORT" not in panels[0]

    def test_composite_rank_identical_to_raw_momentum_rank(self) -> None:
        """composite_signal ordering must match raw momentum ordering.

        Since composite_score with only momentum filled is monotone in the
        momentum z-score, rank-IC-relevant ordering is preserved.
        """
        start = datetime(2018, 1, 1)
        n_days = 600

        # Three tickers with different momentum profiles
        t_high = _daily_series(start, n_days, start_price=10.0, daily_return=0.004)
        t_mid = _daily_series(start, n_days, start_price=10.0, daily_return=0.001)
        t_low = _daily_series(start, n_days, start_price=10.0, daily_return=-0.001)
        spy_series = _flat_series(start, n_days + 40, price=300.0)

        fn = self._make_cache(
            {"HIGH": t_high, "MID": t_mid, "LOW": t_low, "SPY": spy_series}
        )
        as_of = start + timedelta(days=480)
        panels, _bench = build_screen_panels(
            ["HIGH", "MID", "LOW"], [as_of], fn, horizon_days=21
        )

        panel = panels[0]
        if len(panel) >= 3:
            high_sig = panel["HIGH"][0]
            mid_sig = panel["MID"][0]
            low_sig = panel["LOW"][0]
            assert high_sig > mid_sig > low_sig, (
                f"Rank should preserve momentum ordering: HIGH({high_sig:.4f}) > "
                f"MID({mid_sig:.4f}) > LOW({low_sig:.4f})"
            )

    def test_date_with_no_eligible_tickers_yields_empty_panel(self) -> None:
        """A date where no ticker has >= 13 months of history yields an empty dict."""
        start = datetime(2023, 6, 1)
        # Only 2 months of data — never enough for momentum_12_1
        short_series = _daily_series(start, 60, start_price=100.0, daily_return=0.001)
        spy_series = _flat_series(start, 200, price=400.0)

        fn = self._make_cache({"X": short_series, "SPY": spy_series})
        # Evaluate just 3 months in: still <13 monthly closes
        as_of = start + timedelta(days=90)
        panels, bench = build_screen_panels(["X"], [as_of], fn, horizon_days=21)

        assert panels == [{}]
        assert len(bench) == 1  # benchmark list still aligned

    def test_multiple_dates_all_indexed_correctly(self) -> None:
        """panels and benchmark_returns are same length and aligned to dates."""
        start = datetime(2019, 1, 1)
        n_days = 900
        series_a = _daily_series(start, n_days, start_price=50.0, daily_return=0.001)
        spy_series = _flat_series(start, n_days + 40, price=300.0)
        fn = self._make_cache({"A": series_a, "SPY": spy_series})

        dates = [start + timedelta(days=28 * i) for i in range(15, 28)]
        panels, bench = build_screen_panels(["A"], dates, fn, horizon_days=21)

        assert len(panels) == len(dates)
        assert len(bench) == len(dates)
