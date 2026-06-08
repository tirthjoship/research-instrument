"""Tests for WikipediaArticleResolver — name→article + view-volume validation."""

from __future__ import annotations

import urllib.parse
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


def test_resolve_malformed_payload_returns_none() -> None:
    from adapters.data.wikipedia_article_resolver import WikipediaArticleResolver

    def http_get(url, headers=None, timeout=None):  # type: ignore[no-untyped-def]
        return _resp({"error": "unexpected"})  # dict, not the [q,[titles],...] list

    r = WikipediaArticleResolver(http_get=http_get, sleep=lambda s: None)
    assert r.resolve("Anything") is None


def test_mean_daily_views_skips_bad_items() -> None:
    from datetime import datetime

    from adapters.data.wikipedia_article_resolver import WikipediaArticleResolver

    def http_get(url, headers=None, timeout=None):  # type: ignore[no-untyped-def]
        return _resp({"items": [{"views": 100}, {"nope": 1}, {"views": 300}]})

    r = WikipediaArticleResolver(http_get=http_get, sleep=lambda s: None)
    assert r.mean_daily_views("X", datetime(2024, 1, 1), datetime(2024, 1, 3)) == 200.0


# ── 429 backoff tests ────────────────────────────────────────────────────────


import requests  # noqa: E402


def _err_resp(status: int):  # type: ignore[no-untyped-def]
    """Fake response whose raise_for_status() raises HTTPError with the status code in the message."""

    class _R:
        status_code = status

        def raise_for_status(self) -> None:
            raise requests.HTTPError(f"{status} Too Many Requests")

        def json(self):  # type: ignore[no-untyped-def]
            return {}

    return _R()


def test_resolve_429_then_200_retries() -> None:
    from adapters.data.wikipedia_article_resolver import WikipediaArticleResolver

    calls: dict[str, int] = {"n": 0}

    def http_get(url, headers=None, timeout=None):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        if calls["n"] == 1:
            return _err_resp(429)
        return _resp(["Apple Inc.", ["Apple Inc."], [""], ["u"]])

    r = WikipediaArticleResolver(
        http_get=http_get, sleep=lambda s: None, throttle_s=0.0, max_retries=3
    )
    assert r.resolve("Apple Inc.") == "Apple Inc."
    assert calls["n"] == 2


def test_resolve_persistent_429_raises_throttled() -> None:
    import pytest

    from adapters.data.wikipedia_article_resolver import WikipediaArticleResolver
    from domain.exceptions import SourceThrottledError

    def http_get(url, headers=None, timeout=None):  # type: ignore[no-untyped-def]
        return _err_resp(429)

    r = WikipediaArticleResolver(
        http_get=http_get, sleep=lambda s: None, throttle_s=0.0, max_retries=2
    )
    with pytest.raises(SourceThrottledError):
        r.resolve("Apple Inc.")


def test_mean_daily_views_persistent_429_raises_throttled() -> None:
    import pytest

    from adapters.data.wikipedia_article_resolver import WikipediaArticleResolver
    from domain.exceptions import SourceThrottledError

    def http_get(url, headers=None, timeout=None):  # type: ignore[no-untyped-def]
        return _err_resp(429)

    r = WikipediaArticleResolver(
        http_get=http_get, sleep=lambda s: None, throttle_s=0.0, max_retries=2
    )
    with pytest.raises(SourceThrottledError):
        r.mean_daily_views("Apple Inc.", datetime(2024, 1, 1), datetime(2024, 1, 3))


def _os(title: str):  # type: ignore[no-untyped-def]
    """opensearch response shape echoing the title."""
    return _resp([title, [title] if title else [], [""], ["u"]])


def test_normalize_company_name_strips_suffixes() -> None:
    from adapters.data.wikipedia_article_resolver import normalize_company_name

    assert normalize_company_name("AbbVie Inc.") == "AbbVie"
    assert normalize_company_name("Accenture plc") == "Accenture"
    assert normalize_company_name("Applied Materials, Inc.") == "Applied Materials"
    assert normalize_company_name("The Allstate Corporation") == "Allstate"
    assert (
        normalize_company_name("Archer-Daniels-Midland Company")
        == "Archer-Daniels-Midland"
    )
    # already clean stays clean
    assert normalize_company_name("Assurant") == "Assurant"


def test_resolve_validated_raw_first_keeps_apple() -> None:
    """raw 'Apple Inc.' passes the gate -> must NOT fall back to cleaned 'Apple'."""
    from adapters.data.wikipedia_article_resolver import WikipediaArticleResolver

    def http_get(url, headers=None, timeout=None):  # type: ignore[no-untyped-def]
        if "opensearch" in url:
            q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["search"][0]
            return _os(q)
        # pageviews: "Apple Inc." article is high-traffic
        if "Apple_Inc." in url:
            return _resp({"items": [{"views": 40000}]})
        return _resp({"items": [{"views": 9999}]})

    r = WikipediaArticleResolver(
        http_get=http_get, sleep=lambda s: None, throttle_s=0.0
    )
    assert (
        r.resolve_validated(
            "Apple Inc.", datetime(2024, 1, 1), datetime(2024, 1, 3), min_views=50.0
        )
        == "Apple Inc."
    )


def test_resolve_validated_falls_back_to_cleaned_for_abbvie() -> None:
    """raw 'AbbVie Inc.' -> stub (low views) -> fall back to cleaned 'AbbVie' -> passes."""
    from adapters.data.wikipedia_article_resolver import WikipediaArticleResolver

    def http_get(url, headers=None, timeout=None):  # type: ignore[no-untyped-def]
        if "opensearch" in url:
            q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["search"][0]
            return _os(q)
        if "AbbVie_Inc." in url:
            return _resp({"items": [{"views": 16}]})  # stub, below gate
        if "AbbVie" in url:
            return _resp({"items": [{"views": 896}]})  # real article
        return _resp({"items": []})

    r = WikipediaArticleResolver(
        http_get=http_get, sleep=lambda s: None, throttle_s=0.0
    )
    assert (
        r.resolve_validated(
            "AbbVie Inc.", datetime(2024, 1, 1), datetime(2024, 1, 3), min_views=50.0
        )
        == "AbbVie"
    )


def test_resolve_validated_no_fallback_when_name_already_clean() -> None:
    """if cleaned == raw, do not make duplicate calls; genuine low-views still -> None."""
    from adapters.data.wikipedia_article_resolver import WikipediaArticleResolver

    calls: dict[str, int] = {"n": 0}

    def http_get(url, headers=None, timeout=None):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        if "opensearch" in url:
            return _os("Tinycorp")
        return _resp({"items": [{"views": 3}]})  # below gate

    r = WikipediaArticleResolver(
        http_get=http_get, sleep=lambda s: None, throttle_s=0.0
    )
    assert (
        r.resolve_validated(
            "Tinycorp", datetime(2024, 1, 1), datetime(2024, 1, 3), min_views=50.0
        )
        is None
    )
    # exactly 2 calls: 1 opensearch + 1 pageviews (no second opensearch for fallback)
    assert calls["n"] == 2


def test_resolve_validated_propagates_throttle_not_reject() -> None:
    """A 429 on the pageviews validation must RAISE, not return None (no false rejection)."""
    import pytest

    from adapters.data.wikipedia_article_resolver import WikipediaArticleResolver
    from domain.exceptions import SourceThrottledError

    def http_get(url, headers=None, timeout=None):  # type: ignore[no-untyped-def]
        if "opensearch" in url:
            return _resp(["Apple Inc.", ["Apple Inc."], [""], ["u"]])
        return _err_resp(429)  # pageviews throttled

    r = WikipediaArticleResolver(
        http_get=http_get, sleep=lambda s: None, throttle_s=0.0, max_retries=2
    )
    with pytest.raises(SourceThrottledError):
        r.resolve_validated(
            "Apple Inc.", datetime(2024, 1, 1), datetime(2024, 1, 3), min_views=50.0
        )
