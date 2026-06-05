from datetime import datetime
from unittest.mock import MagicMock, patch

from domain.models import AttentionPoint
from domain.ports import AttentionSeriesPort


def test_wikipedia_adapter_conforms_to_port():
    from adapters.data.wikipedia_pageviews_adapter import WikipediaPageviewsAdapter

    assert isinstance(WikipediaPageviewsAdapter(), AttentionSeriesPort)


def test_wikipedia_adapter_parses_pageviews():
    from adapters.data.wikipedia_pageviews_adapter import WikipediaPageviewsAdapter

    payload = {
        "items": [
            {"timestamp": "2026060100", "views": 1234},
            {"timestamp": "2026060200", "views": 5678},
        ]
    }
    with patch("adapters.data.wikipedia_pageviews_adapter.requests.get") as g:
        g.return_value = MagicMock(status_code=200, json=lambda: payload)
        g.return_value.raise_for_status = lambda: None
        pts = WikipediaPageviewsAdapter(
            article_map={"ASTS": "AST_SpaceMobile"}
        ).get_attention_series("ASTS", datetime(2026, 6, 1), datetime(2026, 6, 2))
    assert len(pts) == 2
    assert all(isinstance(p, AttentionPoint) for p in pts)
    assert pts[0].value == 1234.0
    assert pts[0].source == "wikipedia"


def test_wikipedia_adapter_returns_empty_on_error():
    from adapters.data.wikipedia_pageviews_adapter import WikipediaPageviewsAdapter

    with patch(
        "adapters.data.wikipedia_pageviews_adapter.requests.get",
        side_effect=Exception("boom"),
    ):
        pts = WikipediaPageviewsAdapter().get_attention_series(
            "ASTS", datetime(2026, 6, 1), datetime(2026, 6, 2)
        )
    assert pts == []
