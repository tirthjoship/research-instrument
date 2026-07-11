from application.news_context import build_news_context


def test_news_context_groups_and_labels():
    signals = [
        {
            "source": "GDELT",
            "title": "X expands datacenter",
            "date": "2026-06-10",
            "url": "https://example.com/a",
        },
        {"source": "Google News", "title": "X earnings beat", "date": "2026-06-11"},
    ]
    ctx = build_news_context(signals, limit=10)
    assert ctx.label == "context, not signal"
    assert len(ctx.items) == 2
    assert ctx.items[0].source in {"GDELT", "Google News"}
    assert (
        ctx.items[0].url == "https://example.com/a"
        or ctx.items[1].url == "https://example.com/a"
    )


def test_news_context_empty_is_data_gap():
    ctx = build_news_context([], limit=10)
    assert ctx.data_gap is True
