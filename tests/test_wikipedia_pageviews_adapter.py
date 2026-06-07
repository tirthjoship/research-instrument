from datetime import datetime
from unittest.mock import MagicMock, patch

import requests as _requests

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


# ---------------------------------------------------------------------------
# Helpers for injectable-callable tests (no network)
# ---------------------------------------------------------------------------


def _fake_resp(status: int, json_body: dict | None = None) -> object:
    class _R:
        status_code = status

        def __init__(self) -> None:
            self._j = json_body or {}

        def json(self) -> dict:
            return self._j

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                err = _requests.HTTPError(f"{self.status_code} Error")
                err.response = self  # type: ignore[attr-defined]
                raise err

    return _R()


def test_wiki_429_then_200_succeeds_after_retry() -> None:
    from adapters.data.wikipedia_pageviews_adapter import WikipediaPageviewsAdapter

    calls: dict[str, int] = {"n": 0}
    body = {"items": [{"timestamp": "2024010100", "views": 42}]}

    def http_get(
        url: str, headers: dict | None = None, timeout: int | None = None
    ) -> object:
        calls["n"] += 1
        return _fake_resp(429) if calls["n"] == 1 else _fake_resp(200, body)

    adapter = WikipediaPageviewsAdapter(
        http_get=http_get, sleep=lambda s: None, throttle_s=0.0, max_retries=3
    )
    pts = adapter.get_attention_series(
        "AAPL", datetime(2024, 1, 1), datetime(2024, 1, 2)
    )
    assert len(pts) == 1 and pts[0].value == 42.0
    assert calls["n"] == 2  # one retry


def test_wiki_persistent_429_raises_throttled() -> None:
    import pytest

    from adapters.data.wikipedia_pageviews_adapter import WikipediaPageviewsAdapter
    from domain.exceptions import SourceThrottledError

    def http_get(
        url: str, headers: dict | None = None, timeout: int | None = None
    ) -> object:
        return _fake_resp(429)

    adapter = WikipediaPageviewsAdapter(
        http_get=http_get, sleep=lambda s: None, throttle_s=0.0, max_retries=2
    )
    with pytest.raises(SourceThrottledError):
        adapter.get_attention_series("AAPL", datetime(2024, 1, 1), datetime(2024, 1, 2))


def test_wiki_genuine_empty_returns_empty_no_raise() -> None:
    from adapters.data.wikipedia_pageviews_adapter import WikipediaPageviewsAdapter

    def http_get(
        url: str, headers: dict | None = None, timeout: int | None = None
    ) -> object:
        return _fake_resp(200, {"items": []})

    adapter = WikipediaPageviewsAdapter(
        http_get=http_get, sleep=lambda s: None, throttle_s=0.0
    )
    assert (
        adapter.get_attention_series("AAPL", datetime(2024, 1, 1), datetime(2024, 1, 2))
        == []
    )


def test_wiki_non_429_error_returns_empty() -> None:
    from adapters.data.wikipedia_pageviews_adapter import WikipediaPageviewsAdapter

    def http_get(
        url: str, headers: dict | None = None, timeout: int | None = None
    ) -> object:
        return _fake_resp(404)

    adapter = WikipediaPageviewsAdapter(
        http_get=http_get, sleep=lambda s: None, throttle_s=0.0
    )
    assert (
        adapter.get_attention_series("AAPL", datetime(2024, 1, 1), datetime(2024, 1, 2))
        == []
    )
