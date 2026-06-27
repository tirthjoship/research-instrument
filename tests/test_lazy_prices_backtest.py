"""Tests for the pre-registered Lazy-Prices backtest gate logic.

Focus: the LOCKED decision tree (classify_lazy_prices) and the execute() loop with
injected fakes — no real SEC/EDGAR calls (project rule #5).
"""

from __future__ import annotations

from datetime import datetime

from application.lazy_prices_backtest import (
    LazyPricesBacktestUseCase,
    _tercile_long_short_net,
    classify_lazy_prices,
)

# --- guard precedence -------------------------------------------------------


def test_thin_coverage_guard_fires_first() -> None:
    # Even with a great IC, coverage below 0.80 defers the verdict.
    assert (
        classify_lazy_prices(
            mean_ic=0.05,
            ic_ci_low=0.03,
            ic_ci_high=0.07,
            ls_net_ci_low=0.01,
            n_cohorts=40,
            n_events=5000,
            coverage=0.5,
        )
        == "INCONCLUSIVE_THIN_COVERAGE"
    )


def test_thin_n_guard_on_too_few_cohorts_or_events() -> None:
    assert (
        classify_lazy_prices(
            mean_ic=0.05,
            ic_ci_low=0.03,
            ic_ci_high=0.07,
            ls_net_ci_low=0.01,
            n_cohorts=10,
            n_events=5000,
            coverage=0.9,
        )
        == "INCONCLUSIVE_THIN_N"
    )
    assert (
        classify_lazy_prices(
            mean_ic=0.05,
            ic_ci_low=0.03,
            ic_ci_high=0.07,
            ls_net_ci_low=0.01,
            n_cohorts=40,
            n_events=500,
            coverage=0.9,
        )
        == "INCONCLUSIVE_THIN_N"
    )


# --- verdict logic ----------------------------------------------------------


def test_halt_on_significant_negative_ic() -> None:
    assert (
        classify_lazy_prices(
            mean_ic=-0.03,
            ic_ci_low=-0.06,
            ic_ci_high=-0.01,
            ls_net_ci_low=None,
            n_cohorts=40,
            n_events=5000,
            coverage=0.9,
        )
        == "HALT_NEGATIVE"
    )


def test_pass_requires_both_primary_and_secondary() -> None:
    assert (
        classify_lazy_prices(
            mean_ic=0.03,
            ic_ci_low=0.01,
            ic_ci_high=0.05,
            ls_net_ci_low=0.004,
            n_cohorts=40,
            n_events=5000,
            coverage=0.9,
        )
        == "PASS"
    )


def test_conditional_pass_when_net_basket_does_not_confirm() -> None:
    # Primary IC gate passes, but the net-of-cost long-short CI includes 0.
    assert (
        classify_lazy_prices(
            mean_ic=0.03,
            ic_ci_low=0.01,
            ic_ci_high=0.05,
            ls_net_ci_low=-0.001,
            n_cohorts=40,
            n_events=5000,
            coverage=0.9,
        )
        == "CONDITIONAL_PASS_PRIMARY_ONLY"
    )


def test_inconclusive_when_ic_below_economic_bar() -> None:
    # CI excludes 0 but mean IC is below the 0.02 economic-relevance floor (ADR-044 lesson).
    assert (
        classify_lazy_prices(
            mean_ic=0.008,
            ic_ci_low=0.002,
            ic_ci_high=0.014,
            ls_net_ci_low=0.001,
            n_cohorts=40,
            n_events=5000,
            coverage=0.9,
        )
        == "INCONCLUSIVE"
    )


def test_inconclusive_when_ic_ci_spans_zero() -> None:
    assert (
        classify_lazy_prices(
            mean_ic=0.03,
            ic_ci_low=-0.01,
            ic_ci_high=0.07,
            ls_net_ci_low=0.01,
            n_cohorts=40,
            n_events=5000,
            coverage=0.9,
        )
        == "INCONCLUSIVE"
    )


# --- long-short helper ------------------------------------------------------


def test_tercile_long_short_charges_both_legs() -> None:
    # top tercile fwd=+0.10, bottom=-0.10 -> gross 0.20; minus 2*50bps = 0.19.
    signals = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    fwds = [-0.10, -0.10, 0.0, 0.0, 0.10, 0.10]
    net = _tercile_long_short_net(signals, fwds, slippage_bps=50)
    assert net is not None
    assert abs(net - (0.20 - 0.01)) < 1e-9


def test_tercile_returns_none_when_cohort_too_small() -> None:
    assert _tercile_long_short_net([1.0, 2.0], [0.1, 0.2], slippage_bps=50) is None


# --- end-to-end execute() with fakes ---------------------------------------


def _make_universe(tickers: list[str]):
    return lambda _date: list(tickers)


def test_execute_positive_signal_yields_pass_shape() -> None:
    """Construct fakes where similarity perfectly ranks forward returns -> strong IC."""
    tickers = [
        f"T{i}" for i in range(50)
    ]  # 50 names x 25 cohorts = 1250 events > MIN_EVENTS
    # similarity = i/50; forward excess return monotonically increasing in similarity.
    sim_map = {t: i / 50.0 for i, t in enumerate(tickers)}
    fwd_map = {t: (i - 25) * 0.01 for i, t in enumerate(tickers)}

    uc = LazyPricesBacktestUseCase(
        similarity_fn=lambda tk, _d: sim_map[tk],
        forward_return_fn=lambda tk, _d: fwd_map[tk],
        universe_fn=_make_universe(tickers),
        min_names=10,
    )
    cohorts = [datetime(2015, 1, 1)]
    for q in range(1, 25):  # 25 cohorts so THIN_N does not fire
        cohorts.append(datetime(2015 + q // 4, (q % 4) * 3 + 1, 1))

    out = uc.execute(cohorts, horizon_label="63d")
    assert out["coverage"] == 1.0
    assert out["n_cohorts"] >= 20
    assert out["mean_ic"] > 0.5  # near-perfect monotone mapping
    # verdict is one of the locked decisions; with this synthetic signal it should pass.
    assert out["verdict"] in {"PASS", "CONDITIONAL_PASS_PRIMARY_ONLY"}


def test_execute_missing_signals_lower_coverage() -> None:
    tickers = [f"T{i}" for i in range(20)]
    # Half the universe returns None (MISSING) every cohort -> coverage ~0.5.
    uc = LazyPricesBacktestUseCase(
        similarity_fn=lambda tk, _d: None if int(tk[1:]) % 2 == 0 else 0.5,
        forward_return_fn=lambda tk, _d: 0.0,
        universe_fn=_make_universe(tickers),
        min_names=5,
    )
    out = uc.execute([datetime(2015, 1, 1), datetime(2015, 4, 1)], horizon_label="63d")
    assert out["coverage"] == 0.5
    assert out["verdict"] == "INCONCLUSIVE_THIN_COVERAGE"
