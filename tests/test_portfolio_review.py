# tests/test_portfolio_review.py
from adapters.visualization.components.portfolio_review import (
    build_calm_html,
    build_review_card_html,
)
from adapters.visualization.portfolio_view import PortfolioRow


def _row(tk, v, pnl):
    return PortfolioRow(
        tk, "Tech", 5.0, 100, 100, pnl, -0.5, v, "trend broke", None, 1.1, 10
    )


def test_flagged_holdings_use_toggle_row_not_separate_expander(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """My Portfolio's Needs Review cards must use the same merged
    row+chevron component as Home — no separate 'TICKER — VERDICT (expand for
    full evidence)' st.expander label."""
    import streamlit as st

    from adapters.visualization.tabs import positions as pos_tab
    from application.holdings_reader import Holding

    st.session_state.clear()
    monkeypatch.setattr(
        pos_tab.st,
        "session_state",
        {
            "book": [Holding("PLTR", 10.0, 100.0, "TFSA")],
            "is_sample_book": False,
        },
        raising=False,
    )
    monkeypatch.setattr(
        "adapters.visualization.data_loader.load_brief_summary",
        lambda *a, **k: {
            "holdings": [{"ticker": "PLTR", "verdict": "REVIEW", "why": "test flag"}]
        },
    )
    # Never hit real yfinance in tests — fake the price/info fetches.
    monkeypatch.setattr(
        "adapters.visualization.price_cache.batch_fetch_prices", lambda *a, **k: {}
    )
    monkeypatch.setattr(
        "adapters.visualization.price_cache.fetch_ticker_info", lambda *a, **k: {}
    )

    seen: list[str] = []
    orig_markdown = st.markdown
    monkeypatch.setattr(
        st,
        "markdown",
        lambda body, *a, **k: (seen.append(body) if isinstance(body, str) else None)
        or orig_markdown(body, *a, **k),
    )

    # The old implementation put the offending label on a *separate*
    # st.expander (not st.markdown) — capture expander labels too, or this
    # test would pass even against the un-migrated code.
    expander_labels: list[str] = []

    class _FakeExpander:
        def __enter__(self) -> "_FakeExpander":
            return self

        def __exit__(self, *exc: object) -> None:
            return None

    def _fake_expander(label: str = "", *a: object, **k: object) -> _FakeExpander:
        expander_labels.append(str(label))
        return _FakeExpander()

    monkeypatch.setattr(st, "expander", _fake_expander)
    monkeypatch.setattr(pos_tab.st, "expander", _fake_expander)

    pos_tab.render()
    assert not any("expand for full evidence" in s for s in seen)
    assert not any("expand for full evidence" in lbl for lbl in expander_labels)


def test_flagged_rows_each_get_own_toggle_row(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Regression test for the classic loop-closure late-binding bug: each
    flagged row's detail callback must be bound to its own row, not the last
    row in the loop. Verified by capturing the session_key passed to
    render_toggle_row for each of several flagged rows."""
    import streamlit as st

    from adapters.visualization.tabs import positions as pos_tab
    from application.holdings_reader import Holding

    st.session_state.clear()
    monkeypatch.setattr(
        pos_tab.st,
        "session_state",
        {
            "book": [
                Holding("PLTR", 10.0, 500.0, "TFSA"),
                Holding("TSLA", 5.0, 500.0, "TFSA"),
            ],
            "is_sample_book": False,
        },
        raising=False,
    )
    monkeypatch.setattr(
        "adapters.visualization.data_loader.load_brief_summary",
        lambda *a, **k: {
            "holdings": [
                {"ticker": "PLTR", "verdict": "REVIEW", "why": "test flag"},
                {"ticker": "TSLA", "verdict": "TRIM", "why": "test flag"},
            ]
        },
    )
    # Never hit real yfinance in tests — fake the price/info fetches.
    monkeypatch.setattr(
        "adapters.visualization.price_cache.batch_fetch_prices", lambda *a, **k: {}
    )
    monkeypatch.setattr(
        "adapters.visualization.price_cache.fetch_ticker_info", lambda *a, **k: {}
    )

    seen_keys: list[str] = []
    captured_details: dict[str, object] = {}

    def _fake_render_toggle_row(*, row_html, session_key, detail):  # type: ignore[no-untyped-def]
        seen_keys.append(session_key)
        captured_details[session_key] = detail

    import adapters.visualization.tabs.positions as pos_tab_module

    # Patch render_toggle_row at the source module so the local import inside
    # render() picks up the fake.
    monkeypatch.setattr(
        "adapters.visualization.components.expandable_row.render_toggle_row",
        _fake_render_toggle_row,
    )

    # Capture which ticker each row's detail() callback actually renders —
    # this is what catches the late-binding closure bug: a broken
    # implementation (capturing `r` by reference instead of default-arg)
    # would have every callback render the *last* loop ticker.
    rendered_tickers: list[str] = []
    monkeypatch.setattr(
        "adapters.visualization.components.portfolio_detail.render_inspect_body",
        lambda row, reports_dir=None: rendered_tickers.append(row.ticker),
    )

    pos_tab_module.render()

    # Both flagged holdings (REVIEW/PLTR, TRIM/TSLA) must produce distinct
    # per-ticker session keys.
    assert len(seen_keys) == 2
    assert len(seen_keys) == len(set(seen_keys))
    assert {"pf_nr_open_PLTR", "pf_nr_open_TSLA"} == set(seen_keys)

    # Invoking each captured detail() callback must render its OWN ticker,
    # not whichever ticker was last in the loop.
    captured_details["pf_nr_open_PLTR"]()
    captured_details["pf_nr_open_TSLA"]()
    assert rendered_tickers == ["PLTR", "TSLA"]


def test_review_card_has_ticker_and_pill():
    html = build_review_card_html(_row("PLTR", "REDUCE", -18.4))
    assert "PLTR" in html
    assert "REDUCE" in html
    assert "-18.4%" in html
    assert "trend broke" in html


def test_card_border_class_by_verdict():
    assert "reduce" in build_review_card_html(_row("A", "REDUCE", -5))
    assert "trim" in build_review_card_html(_row("B", "TRIM", -2))
    assert "review" in build_review_card_html(_row("C", "REVIEW", 1))


def test_calm_state():
    html = build_calm_html()
    assert "Nothing needs review" in html


def test_review_card_outer_tag_is_div_no_anchor():
    """The card must open with a <div> wrapper (CommonMark HTML-block rule 6
    only recognizes block-level tags for raw-HTML passthrough; <a> isn't one).
    It must also contain zero anchors — the card used to be wrapped in an
    <a href="?inspect=..."> for click-to-inspect, but a real browser
    navigation from that link wiped session state on Streamlit Cloud (see
    portfolio_detail.py). positions.py now renders a real st.button next to
    the card instead."""
    html = build_review_card_html(_row("PLTR", "REDUCE", -18.4))
    assert html.startswith('<div class="pf-review reduce">')
    assert "<a " not in html
    assert "href=" not in html
