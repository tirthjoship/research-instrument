def test_snowflake_builds_figure_with_axes():
    from adapters.visualization.components.snowflake import build_snowflake

    fig = build_snowflake({"Valuation": 80, "Quality": 60, "Trend": 40})
    assert fig is not None
    trace = fig.data[0]
    # closed polygon: first axis repeated at the end
    assert list(trace.theta) == ["Valuation", "Quality", "Trend", "Valuation"]
    assert list(trace.r) == [80, 60, 40, 80]


def test_snowflake_needs_three_axes():
    from adapters.visualization.components.snowflake import build_snowflake

    assert build_snowflake({"Valuation": 80, "Quality": 60}) is None


def test_snowflake_clamps_to_0_100():
    from adapters.visualization.components.snowflake import build_snowflake

    fig = build_snowflake({"A": 150, "B": -10, "C": 50})
    assert list(fig.data[0].r) == [100, 0, 50, 100]
