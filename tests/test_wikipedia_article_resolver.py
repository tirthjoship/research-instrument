"""Tests for WikipediaArticleResolver — name→article + view-volume validation."""

from __future__ import annotations

from datetime import datetime


def _resp(json_body):  # type: ignore[no-untyped-def]
    class _R:
        status_code = 200

        def __init__(self) -> None:
            self._j = json_body

        def json(self):  # type: ignore[no-untyped-def]
            return self._j

        def raise_for_status(self) -> None:
            pass

    return _R()


def test_resolve_returns_first_title() -> None:
    from adapters.data.wikipedia_article_resolver import WikipediaArticleResolver

    def http_get(url, headers=None, timeout=None):  # type: ignore[no-untyped-def]
        return _resp(["Assurant", ["Assurant"], [""], ["http://..."]])

    r = WikipediaArticleResolver(http_get=http_get, sleep=lambda s: None)
    assert r.resolve("Assurant") == "Assurant"


def test_resolve_no_hit_returns_none() -> None:
    from adapters.data.wikipedia_article_resolver import WikipediaArticleResolver

    def http_get(url, headers=None, timeout=None):  # type: ignore[no-untyped-def]
        return _resp(["Zzxq", [], [], []])

    r = WikipediaArticleResolver(http_get=http_get, sleep=lambda s: None)
    assert r.resolve("Zzxq Nonexistent Corp") is None


def test_mean_daily_views_computes_average() -> None:
    from adapters.data.wikipedia_article_resolver import WikipediaArticleResolver

    def http_get(url, headers=None, timeout=None):  # type: ignore[no-untyped-def]
        return _resp({"items": [{"views": 100}, {"views": 200}, {"views": 300}]})

    r = WikipediaArticleResolver(http_get=http_get, sleep=lambda s: None)
    assert (
        r.mean_daily_views("Assurant", datetime(2024, 1, 1), datetime(2024, 1, 3))
        == 200.0
    )


def test_mean_daily_views_empty_is_zero() -> None:
    from adapters.data.wikipedia_article_resolver import WikipediaArticleResolver

    def http_get(url, headers=None, timeout=None):  # type: ignore[no-untyped-def]
        return _resp({"items": []})

    r = WikipediaArticleResolver(http_get=http_get, sleep=lambda s: None)
    assert r.mean_daily_views("X", datetime(2024, 1, 1), datetime(2024, 1, 3)) == 0.0


def test_resolve_validated_rejects_low_views() -> None:
    from adapters.data.wikipedia_article_resolver import WikipediaArticleResolver

    calls: list[str] = []

    def http_get(url, headers=None, timeout=None):  # type: ignore[no-untyped-def]
        calls.append(url)
        if "opensearch" in url:
            return _resp(["AIZ", ["AIZ"], [""], ["http://..."]])
        return _resp({"items": [{"views": 3}, {"views": 5}]})  # mean 4 < 50

    r = WikipediaArticleResolver(http_get=http_get, sleep=lambda s: None)
    assert (
        r.resolve_validated(
            "AIZ", datetime(2024, 1, 1), datetime(2024, 1, 3), min_views=50.0
        )
        is None
    )


def test_resolve_validated_accepts_high_views() -> None:
    from adapters.data.wikipedia_article_resolver import WikipediaArticleResolver

    def http_get(url, headers=None, timeout=None):  # type: ignore[no-untyped-def]
        if "opensearch" in url:
            return _resp(["Apple Inc.", ["Apple Inc."], [""], ["http://..."]])
        return _resp({"items": [{"views": 40000}, {"views": 44000}]})

    r = WikipediaArticleResolver(http_get=http_get, sleep=lambda s: None)
    assert (
        r.resolve_validated(
            "Apple Inc.", datetime(2024, 1, 1), datetime(2024, 1, 3), min_views=50.0
        )
        == "Apple Inc."
    )


def test_resolve_validated_no_article_returns_none() -> None:
    from adapters.data.wikipedia_article_resolver import WikipediaArticleResolver

    def http_get(url, headers=None, timeout=None):  # type: ignore[no-untyped-def]
        return _resp(["Zzz", [], [], []])  # opensearch miss

    r = WikipediaArticleResolver(http_get=http_get, sleep=lambda s: None)
    assert (
        r.resolve_validated("Zzz", datetime(2024, 1, 1), datetime(2024, 1, 3)) is None
    )


def test_url_encoding_handles_special_chars() -> None:
    from adapters.data.wikipedia_article_resolver import WikipediaArticleResolver

    seen: dict[str, str] = {}

    def http_get(url, headers=None, timeout=None):  # type: ignore[no-untyped-def]
        seen["url"] = url
        return _resp(["x", ["Arthur J. Gallagher & Co."], [""], ["u"]])

    r = WikipediaArticleResolver(http_get=http_get, sleep=lambda s: None)
    r.resolve("Arthur J. Gallagher & Co.")
    # name must be URL-encoded — no raw spaces or ampersand breaking the URL
    assert " " not in seen["url"]
