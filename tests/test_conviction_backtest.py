from application.conviction_backtest import run_conviction_backtest


def test_perfectly_predictive_conviction():
    dates = ["2026-01-01", "2026-02-01"]
    tickers = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]
    convictions = {
        t: 10 - i for i, t in enumerate(tickers)
    }  # A highest (10), J lowest (1)

    def score_fn(d: str) -> dict[str, float]:
        return dict(convictions)

    def fwd(t: str, d: str) -> float:
        return 0.10 if convictions[t] >= 6 else -0.05  # top names win

    def bench(d: str) -> float:
        return 0.0

    r = run_conviction_backtest(dates, tickers, score_fn, fwd, bench, decile=0.1)
    assert r["top_decile_hit_rate"] == 1.0
    assert r["excess_sharpe"] > 0
    assert r["expected_profit_per_signal"] > 0
    assert r["n_dates"] == 2
    assert "precision_curve" in r and "p_value" in r and "f_beta_0_5" in r


def test_uninformative_conviction_near_base_rate():
    dates = ["2026-01-01"]
    tickers = [f"T{i}" for i in range(20)]
    conv = {t: i for i, t in enumerate(tickers)}

    def score_fn(d: str) -> dict[str, float]:
        return dict(conv)

    def fwd(t: str, d: str) -> float:
        return 0.05 if int(t[1:]) % 2 == 0 else -0.05  # uncorrelated with conviction

    def bench(d: str) -> float:
        return 0.0

    r = run_conviction_backtest(dates, tickers, score_fn, fwd, bench, decile=0.5)
    assert 0.2 <= r["top_decile_hit_rate"] <= 0.8


def test_empty_dates_safe():
    r = run_conviction_backtest([], [], lambda d: {}, lambda t, d: 0.0, lambda d: 0.0)
    assert r["n_dates"] == 0
    assert r["top_decile_hit_rate"] == 0.0


def test_result_contains_new_keys():
    """Output dict must contain base_rate, edge_over_base, p_value_vs_50, date_level."""
    dates = ["2026-01-01", "2026-02-01"]
    tickers = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]
    convictions = {t: 10 - i for i, t in enumerate(tickers)}

    def score_fn(d: str) -> dict[str, float]:
        return dict(convictions)

    def fwd(t: str, d: str) -> float:
        return 0.10 if convictions[t] >= 6 else -0.05

    def bench(d: str) -> float:
        return 0.0

    r = run_conviction_backtest(dates, tickers, score_fn, fwd, bench, decile=0.1)
    assert "base_rate" in r
    assert "edge_over_base" in r
    assert "p_value_vs_50" in r
    assert "date_level" in r


def test_perfectly_correlated_scenario_extended():
    """Existing scenario still hits top_decile_hit_rate==1.0; new fields are coherent."""
    dates = ["2026-01-01", "2026-02-01"]
    tickers = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]
    convictions = {t: 10 - i for i, t in enumerate(tickers)}

    def score_fn(d: str) -> dict[str, float]:
        return dict(convictions)

    def fwd(t: str, d: str) -> float:
        return 0.10 if convictions[t] >= 6 else -0.05

    def bench(d: str) -> float:
        return 0.0

    r = run_conviction_backtest(dates, tickers, score_fn, fwd, bench, decile=0.1)
    assert r["top_decile_hit_rate"] == 1.0
    assert r["edge_over_base"] >= 0
    dl = r["date_level"]
    assert isinstance(dl, dict)
    assert dl["t_pvalue"] is not None
    assert dl["t_pvalue"] < 0.5
