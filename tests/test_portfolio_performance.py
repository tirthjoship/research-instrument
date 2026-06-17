from adapters.visualization.components.portfolio_performance import (
    alpha_vs_spy,
    build_perf_figure,
)


def test_alpha_simple():
    assert round(alpha_vs_spy(11.1, 7.1), 1) == 4.0


def test_alpha_none_when_spy_gap():
    assert alpha_vs_spy(11.1, None) is None


def test_build_perf_figure_two_traces():
    fig = build_perf_figure(
        port_pct=[0.0, 4.0, 11.1],
        spy_pct=[0.0, 3.0, 7.1],
        labels=["Mar", "Apr", "Jun"],
    )
    # two line traces (portfolio + spy)
    names = [t.name for t in fig.data]
    assert "Portfolio" in names and "SPY" in names
