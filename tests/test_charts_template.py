import plotly.graph_objects as go

from adapters.visualization.components.charts import apply_dossier_template


def test_template_sets_transparent_bg_and_font() -> None:
    fig = apply_dossier_template(go.Figure())
    assert fig.layout.paper_bgcolor in ("rgba(0,0,0,0)", "rgba(0, 0, 0, 0)")
    assert fig.layout.plot_bgcolor in ("rgba(0,0,0,0)", "rgba(0, 0, 0, 0)")
    assert "Plex" in (fig.layout.font.family or "")
