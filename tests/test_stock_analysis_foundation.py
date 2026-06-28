# tests/test_stock_analysis_foundation.py
from adapters.visualization.components import (
    metric_tile,
    mini_charts,
    status_chip,
    stock_metrics,
)


def test_compose_a_panel_header_fragment():
    chip = status_chip.render_status_chip(
        "RICH",
        "P/E 78th",
        tone="amber",
        rule="P/E >=75th pct of peers; price level only",
    )
    tile = metric_tile.render_metric_tile(
        "PEG",
        "0.75",
        sub="<1",
        tone="green",
        viz=mini_charts.percentile_bar(25.0),
        info_meaning="P/E / growth",
        info_basis="<1 cheap",
    )
    info = stock_metrics.metric_info("peg")
    fragment = f'<div class="sa-panel">{chip}{tile}{info}</div>'
    assert "sa-chip t-amber" in fragment
    assert "sa-tile t-green" in fragment
    assert (
        fragment.count("sa-tip") >= 3
    )  # chip + tile + metric_info all carry working tooltips
