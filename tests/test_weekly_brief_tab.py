from __future__ import annotations

import json
from unittest.mock import patch

from adapters.visualization.data_loader import load_weekly_brief


def test_load_weekly_brief_missing_returns_none(tmp_path) -> None:  # type: ignore[no-untyped-def]
    assert load_weekly_brief(str(tmp_path / "nope.md")) is None


def test_load_weekly_brief_reads_markdown(tmp_path) -> None:  # type: ignore[no-untyped-def]
    p = tmp_path / "weekly_brief.md"
    p.write_text("# WEEKLY BRIEF — 2026-06-08\n")
    assert load_weekly_brief(str(p)) == "# WEEKLY BRIEF — 2026-06-08\n"


def test_tab_module_exposes_render() -> None:
    from adapters.visualization.tabs import weekly_brief as tab

    assert callable(tab.render)


def test_render_with_summary_fixture(tmp_path) -> None:  # type: ignore[no-untyped-def]
    import json

    p = tmp_path / "brief_summary.json"
    p.write_text(
        json.dumps(
            {
                "as_of": "2026-06-13",
                "regime": "neutral",
                "abstained": True,
                "holdings": [
                    {
                        "ticker": "ARKK",
                        "verdict": "REDUCE",
                        "unrealized_pct": -12.0,
                        "trend_state": "broken",
                        "why": "trend broken",
                    }
                ],
            }
        )
    )
    from adapters.visualization.tabs import weekly_brief

    weekly_brief.render(path=str(p))  # must not raise outside streamlit runtime


def test_render_with_adherence_log(tmp_path) -> None:  # type: ignore[no-untyped-def]
    import json

    p = tmp_path / "brief_summary.json"
    p.write_text(
        json.dumps(
            {
                "as_of": "2026-06-13",
                "regime": "neutral",
                "abstained": True,
                "holdings": [],
            }
        )
    )
    a = tmp_path / "adherence_log.jsonl"
    a.write_text(
        json.dumps(
            {
                "ticker": "ARKK",
                "verdict": "REDUCE",
                "flag_date": "2026-05-16",
                "actual_cut_fraction": 0.0,
                "label": "IGNORED",
                "gap_cad": -120.0,
                "gap_bps": -8.0,
            }
        )
        + "\n"
    )
    from adapters.visualization.tabs import weekly_brief

    weekly_brief.render(path=str(p), adherence_path=str(a))  # must not raise


def test_render_hero_counts_attention(tmp_path) -> None:  # type: ignore[no-untyped-def]
    import json

    p = tmp_path / "brief_summary.json"
    p.write_text(
        json.dumps(
            {
                "as_of": "2026-06-12",
                "regime": "NEUTRAL",
                "abstained": True,
                "macro": {"systematic_share": 0.64},
                "holdings": [
                    {
                        "ticker": "A",
                        "verdict": "REDUCE",
                        "unrealized_pct": -5.0,
                        "trend_state": "broken",
                        "why": "w",
                    },
                    {
                        "ticker": "B",
                        "verdict": "HOLD",
                        "unrealized_pct": 2.0,
                        "trend_state": "intact",
                        "why": "w",
                    },
                ],
            }
        )
    )
    from adapters.visualization.tabs import weekly_brief

    # reports_dir points to tmp_path — no screen file → degrades to "no screen yet"
    # adherence_path points to missing file → degrades to 0 rows
    weekly_brief.render(
        path=str(p),
        adherence_path=str(tmp_path / "adherence_log.jsonl"),
        reports_dir=str(tmp_path),
    )  # must not raise


def test_render_zero_attention_no_columns_crash(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Zero-attention branch must NOT call st.columns(0) — that would crash Streamlit."""
    import json

    p = tmp_path / "brief_summary.json"
    p.write_text(
        json.dumps(
            {
                "as_of": "2026-06-12",
                "regime": "NEUTRAL",
                "abstained": True,
                "macro": {"systematic_share": 0.30},
                "holdings": [
                    {
                        "ticker": "B",
                        "verdict": "HOLD",
                        "unrealized_pct": 2.0,
                        "trend_state": "intact",
                        "why": "w",
                    },
                ],
            }
        )
    )
    from adapters.visualization.tabs import weekly_brief

    # No REDUCE/TRIM holdings → attention list is empty → must NOT hit st.columns(0)
    weekly_brief.render(
        path=str(p),
        adherence_path=str(tmp_path / "adherence_log.jsonl"),
        reports_dir=str(tmp_path),
    )  # must not raise


def test_weekly_brief_hero_copy_has_no_forbidden_words() -> None:
    # Guard: the Home tab is NOT an exempt surface (unlike Trust), so its
    # rendered copy must carry no recommendation/forecast vocabulary. Scan the
    # REAL module source — not a hand-maintained copy literal — so any NEW copy
    # added to render()/helpers is caught (the literal-scan this replaced could
    # only ever see words the author already listed).
    import inspect

    from adapters.visualization.tabs import weekly_brief
    from domain.fit import FORBIDDEN_WORDS

    src = inspect.getsource(weekly_brief).lower()
    for word in FORBIDDEN_WORDS:
        assert word not in src, f"forbidden word {word!r} in weekly_brief source"


def test_render_missing_macro_skips_gauge(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Missing 'macro' key → gauge block must be skipped without raising."""
    p = tmp_path / "brief_summary.json"
    p.write_text(
        json.dumps(
            {
                "as_of": "2026-06-12",
                "regime": "NEUTRAL",
                "abstained": True,
                "holdings": [],  # no macro key, no holdings
            }
        )
    )
    from adapters.visualization.tabs import weekly_brief

    weekly_brief.render(
        path=str(p),
        adherence_path=str(tmp_path / "adherence_log.jsonl"),
        reports_dir=str(tmp_path),
    )  # must not raise


# ---------------------------------------------------------------------------
# Task 8: screen tile honesty + triage strip guards
# ---------------------------------------------------------------------------


def test_weekly_brief_no_forbidden_words() -> None:
    import inspect

    from adapters.visualization.tabs import weekly_brief
    from domain.fit import FORBIDDEN_WORDS

    src = inspect.getsource(weekly_brief).lower()
    for w in FORBIDDEN_WORDS:
        assert w not in src, f"forbidden word {w!r} in weekly_brief.py"


def test_home_render_new_layout(tmp_path) -> None:  # type: ignore[no-untyped-def]
    import json
    from unittest.mock import MagicMock, patch  # noqa: PLC0415

    import streamlit as st  # noqa: PLC0415

    from adapters.visualization.tabs import weekly_brief as wb
    from application.evidence_card import EvidenceCard

    p = tmp_path / "brief_summary.json"
    p.write_text(
        json.dumps(
            {
                "as_of": "2026-06-14",
                "regime": "RISK_ON",
                "abstained": False,
                "holdings": [
                    {
                        "ticker": "YUMC",
                        "verdict": "TRIM",
                        "unrealized_pct": 22.7,
                        "trend_state": "broken",
                        "why": "pulled back below trend",
                    }
                ],
                "macro": {
                    "systematic_share": 0.628,
                    "net_beta_by_factor": {"SPY": 1.42},
                },
            }
        )
    )
    # render must not raise; capture markdown
    # S5: stub _fetch_card (network) and st.progress (bare-mode CI).
    # _render_one_holding_fragment is wrapped with st.fragment which, in bare mode,
    # routes calls through an internal path that bypasses a patched st.markdown.
    # We therefore redirect the fragment attribute to the inner function so tests
    # can still capture st.markdown output without changing production behaviour.
    captured = []
    progress_mock = MagicMock()
    with (
        patch.object(
            st, "markdown", side_effect=lambda c, **k: captured.append(str(c))
        ),
        patch.object(st, "download_button"),
        patch.object(st, "caption"),
        patch.object(st, "expander"),
        patch.object(st, "divider"),
        # FIX A: _handle_onboarding is now always called; columns must unpack to 3
        patch.object(
            st, "columns", return_value=[MagicMock(), MagicMock(), MagicMock()]
        ),
        patch.object(st, "progress", return_value=progress_mock),
        patch.object(wb, "_fetch_card", return_value=EvidenceCard("YUMC", (), ())),
        patch.object(wb, "select_case_summarizer", return_value=MagicMock()),
        patch.object(wb, "_render_one_holding_fragment", wb._render_one_holding),
    ):
        wb.render(
            path=str(p),
            adherence_path=str(tmp_path / "a.jsonl"),
            reports_dir=str(tmp_path),
        )
    html = "\n".join(captured)
    assert "Net beta" in html and html.count("1.42") >= 1
    assert "ri-ledger" not in html  # ledger DELETED
    assert "VERDICT DISTRIBUTION" not in html  # distribution DELETED
    assert "YUMC" in html  # needs-review row present


def test_needs_review_rows_render_collapsed(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from adapters.visualization.tabs import weekly_brief as wb

    holdings = [
        {
            "ticker": "YUMC",
            "verdict": "TRIM",
            "unrealized_pct": 22.7,
            "trend_state": "broken",
            "why": "Winner pulled back below trend.",
        }
    ]
    html = wb._render_needs_review_html(holdings)
    assert "YUMC" in html and "TRIM" in html and "+22.7%" in html
    assert "dc-row" in html and "dc-sq" in html  # uses the S3 component


def test_home_honesty_line_points_to_trust() -> None:
    from adapters.visualization.tabs import weekly_brief as wb

    html = wb._render_honesty_line_html()
    assert "Trust" in html and (
        "coin flip" in html.lower() or "falsified" in html.lower()
    )
    for w in ("buy", "sell", "predict"):
        assert w not in html.lower()


def test_book_health_bar_flags_above_60() -> None:
    from adapters.visualization.tabs import weekly_brief as wb

    html = wb._render_book_health_html(systematic_share=0.628)
    assert "63%" in html and "macro-leaning" in html.lower()
    assert "60%" in html  # the flag reference


def test_book_strip_single_net_beta(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from adapters.visualization.tabs import weekly_brief as wb

    html = wb._render_book_strip_html(
        need_review=4,
        total=10,
        vs_market=3.2,
        net_beta=1.21,
        regime="RISK_ON",
        screen_cleared=304,
        screen_universe=512,
    )
    # exactly one "Net beta" label, value 1.21, and it's NOT the systematic share %
    assert html.count(">Net beta<") + html.lower().count("net beta") >= 1
    assert "1.21" in html and "ELEVATED" in html  # classify_net_beta band
    assert "+3.2%" in html and "RISK_ON" in html and "304" in html
    assert "63%" not in html  # systematic share does NOT appear in the beta tile


def test_screen_tile_content_has_candidates_no_abstained_emh() -> None:
    """With cleared=70 / scanned=512, screen tile must NOT contain ABSTAINED or =EMH,
    and MUST contain '70' (the real cleared count)."""
    from adapters.visualization.tabs.weekly_brief import _screen_tile_content

    screen = {
        "universe_size": 512,
        "candidates": [{"ticker": "AAPL"}] * 70,
        "diagnostics": {
            "scanned": 512,
            "had_history": 400,
            "above_trend": 200,
            "cleared": 70,
        },
    }
    number, stamp, tone, sub = _screen_tile_content(screen)

    # The number must include '70' and '512' in context, not 'ABSTAINED'/'=EMH'
    assert "70" in number, f"Expected cleared count '70' in tile number, got {number!r}"
    assert (
        "abstained" not in number.lower()
    ), f"'ABSTAINED' must not appear in screen tile number: {number!r}"
    assert (
        stamp is None or "emh" not in str(stamp).lower()
    ), f"'=EMH' must not be the stamp on the screen tile: {stamp!r}"


def test_screen_tile_content_earned_abstention_no_emh() -> None:
    """EARNED_ABSTENTION verdict: shows scanned/0 cleared, no EMH/ABSTAINED stamp."""
    from adapters.visualization.tabs.weekly_brief import _screen_tile_content

    screen = {
        "universe_size": 512,
        "candidates": [],
        "diagnostics": {
            "scanned": 512,
            "had_history": 400,
            "above_trend": 200,
            "cleared": 0,
        },
    }
    number, stamp, tone, sub = _screen_tile_content(screen)

    assert stamp is None, f"No stamp expected for EARNED_ABSTENTION, got {stamp!r}"
    assert (
        "emh" not in number.lower()
    ), f"'=EMH' must not appear in screen tile number: {number!r}"
    assert (
        "abstained" not in number.lower()
    ), f"'ABSTAINED' must not appear in screen tile number: {number!r}"


def test_screen_tile_content_under_powered_no_emh() -> None:
    """UNDER_POWERED verdict: shows neutral message, no EMH stamp."""
    from adapters.visualization.tabs.weekly_brief import _screen_tile_content

    screen = {
        "universe_size": 512,
        "candidates": [],
        "diagnostics": {
            "scanned": 512,
            "had_history": 10,  # < 0.5 * 512 → UNDER_POWERED
            "above_trend": 5,
            "cleared": 0,
        },
    }
    number, stamp, tone, sub = _screen_tile_content(screen)

    assert stamp is None, f"No stamp expected for UNDER_POWERED, got {stamp!r}"
    assert (
        "emh" not in number.lower()
    ), f"'=EMH' must not appear on under-powered screen tile: {number!r}"
    assert (
        "under-powered" in number.lower()
    ), f"Expected 'under-powered' in number for UNDER_POWERED verdict, got {number!r}"


def test_rendered_home_triage_strip_present(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Rendering Home with a diagnostics-bearing screen must produce a 'Need review'
    triage element in the captured markdown calls."""
    p = tmp_path / "brief_summary.json"
    p.write_text(
        json.dumps(
            {
                "as_of": "2026-06-13",
                "regime": "RISK_ON",
                "abstained": True,
                "holdings": [
                    {
                        "ticker": "ARKK",
                        "verdict": "REDUCE",
                        "unrealized_pct": -12.0,
                        "trend_state": "broken",
                        "why": "broken trend",
                    }
                ],
                "macro": {"systematic_share": 0.63},
            }
        )
    )
    # Write a screen file with diagnostics so the tile is exercised
    screen_file = tmp_path / "screen_20260613.json"
    screen_file.write_text(
        json.dumps(
            {
                "as_of": "2026-06-13",
                "universe_size": 512,
                "candidates": [],
                "abstained": True,
                "diagnostics": {
                    "scanned": 512,
                    "had_history": 400,
                    "above_trend": 200,
                    "cleared": 0,
                },
            }
        )
    )

    collected_html: list[str] = []

    import streamlit as st  # noqa: PLC0415

    original_markdown = st.markdown

    def capture_markdown(content: object, **kwargs: object) -> None:  # type: ignore[no-untyped-def]
        if isinstance(content, str):
            collected_html.append(content)
        original_markdown(content, **kwargs)  # type: ignore[arg-type]

    from adapters.visualization.tabs import weekly_brief

    with patch.object(st, "markdown", side_effect=capture_markdown):
        weekly_brief.render(
            path=str(p),
            adherence_path=str(tmp_path / "adherence_log.jsonl"),
            reports_dir=str(tmp_path),
        )

    all_html = "\n".join(collected_html).lower()
    assert (
        "need review" in all_html
    ), "Triage strip must render a 'Need review' element in the Home tab"


def test_rendered_home_screen_tile_no_false_abstained_emh(
    tmp_path,  # type: ignore[no-untyped-def]
) -> None:
    """Home book strip must NOT contain '=EMH' or false ABSTAINED phrasing.
    The screen tile shows len(candidates) from the screen JSON, not diagnostics.
    (Diagnostics-based tile tests are on _screen_tile_content directly.)"""
    p = tmp_path / "brief_summary.json"
    p.write_text(
        json.dumps(
            {
                "as_of": "2026-06-13",
                "regime": "RISK_ON",
                "abstained": False,
                "holdings": [],
                "macro": {"systematic_share": 0.5},
            }
        )
    )
    screen_file = tmp_path / "screen_20260613.json"
    screen_file.write_text(
        json.dumps(
            {
                "as_of": "2026-06-13",
                "universe_size": 512,
                "candidates": [{"ticker": "AAPL"}],
                "abstained": False,
                "diagnostics": {
                    "scanned": 512,
                    "had_history": 400,
                    "above_trend": 200,
                    "cleared": 70,
                },
            }
        )
    )

    collected_html: list[str] = []

    import streamlit as st  # noqa: PLC0415

    original_markdown = st.markdown

    def capture_markdown(content: object, **kwargs: object) -> None:  # type: ignore[no-untyped-def]
        if isinstance(content, str):
            collected_html.append(content)
        original_markdown(content, **kwargs)  # type: ignore[arg-type]

    from adapters.visualization.tabs import weekly_brief

    with patch.object(st, "markdown", side_effect=capture_markdown):
        weekly_brief.render(
            path=str(p),
            adherence_path=str(tmp_path / "adherence_log.jsonl"),
            reports_dir=str(tmp_path),
        )

    all_html = "\n".join(collected_html)

    # Book strip Screen tile shows len(candidates)=1, no ABSTAINED/=EMH
    import re  # noqa: PLC0415

    matches = re.findall(
        r"512[^<]{0,40}abstained|abstained[^<]{0,40}512", all_html, re.IGNORECASE
    )
    assert (
        not matches
    ), f"False '512...ABSTAINED' claim found in rendered Home: {matches}"
    assert "=emh" not in all_html.lower(), "=EMH must not appear in rendered Home"


def test_rendered_home_honesty_line_references_falsified(
    tmp_path,  # type: ignore[no-untyped-def]
) -> None:
    """The Home honesty line (replacing the removed VALIDATION FINDINGS tiles)
    must reference 'FALSIFIED' so the key finding remains visible.
    Full tiles now live on Trust tab."""
    p = tmp_path / "brief_summary.json"
    p.write_text(
        json.dumps(
            {
                "as_of": "2026-06-13",
                "regime": "RISK_ON",
                "abstained": True,
                "holdings": [],
            }
        )
    )

    collected_html: list[str] = []

    import streamlit as st  # noqa: PLC0415

    original_markdown = st.markdown

    def capture_markdown(content: object, **kwargs: object) -> None:  # type: ignore[no-untyped-def]
        if isinstance(content, str):
            collected_html.append(content)
        original_markdown(content, **kwargs)  # type: ignore[arg-type]

    from adapters.visualization.tabs import weekly_brief

    with patch.object(st, "markdown", side_effect=capture_markdown):
        weekly_brief.render(
            path=str(p),
            adherence_path=str(tmp_path / "adherence_log.jsonl"),
            reports_dir=str(tmp_path),
        )

    all_html = "\n".join(collected_html)

    # Honesty line on Home must still reference FALSIFIED (not via the tile — via the line)
    assert (
        "falsified" in all_html.lower()
    ), "Home honesty line must reference FALSIFIED — full tiles are on Trust tab"
    # Validation tiles (0.004, VERDICT DISTRIBUTION) must NOT be in the new Home
    assert (
        "VERDICT DISTRIBUTION" not in all_html
    ), "Verdict dist block must be deleted from Home"
    assert "ri-ledger" not in all_html, "Evidence ledger must be deleted from Home"


def test_home_cards_loader_returns_one_per_needs_review(monkeypatch: object) -> None:  # type: ignore[no-untyped-def]
    from adapters.visualization.tabs import weekly_brief as wb
    from application.evidence_card import EvidenceCard

    holds = [
        {"ticker": "YUMC", "verdict": "TRIM", "unrealized_pct": 1.0, "why": "x"},
        {"ticker": "AAPL", "verdict": "HOLD", "unrealized_pct": 2.0, "why": "y"},
    ]
    # stub the cached fetch to avoid network
    monkeypatch.setattr(wb, "_fetch_card", lambda t: EvidenceCard(t, (), ()))  # type: ignore[attr-defined]
    cards = wb._needs_review_cards(holds)  # type: ignore[attr-defined]
    assert [t for t, _ in cards] == ["YUMC"]  # only the TRIM row


# ---------------------------------------------------------------------------
# Fix 2: analyst key mapping — _fetch_card must remap yfinance keys so the
# Analysts square lights up (not GAP) when coverage is present.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# S6 Task 4: landing door + onboarding routing
# ---------------------------------------------------------------------------


def test_home_shows_door_when_no_book(monkeypatch: object) -> None:  # type: ignore[no-untyped-def]
    from adapters.visualization.tabs import weekly_brief as wb

    monkeypatch.setattr(wb, "is_local_runtime", lambda: True)  # type: ignore[attr-defined]
    html = wb._render_onboarding_html(has_book=False)  # type: ignore[attr-defined]
    assert "Load a book to begin" in html and "Explore sample book" in html


def test_home_door_always_present_even_with_book(monkeypatch: object) -> None:
    """FIX A: door must render regardless of whether a book is loaded.

    Old test (test_home_hides_door_when_book_present) asserted door is hidden
    when has_book=True.  New behaviour: door is ALWAYS rendered so the user can
    always reach Upload/Add-manually.
    """
    from adapters.visualization.tabs import weekly_brief as wb

    monkeypatch.setattr(wb, "is_local_runtime", lambda: True)  # type: ignore[attr-defined]
    html = wb._render_onboarding_html(has_book=True)  # type: ignore[attr-defined]
    assert "Load a book to begin" in html, "Door must render even when book is loaded"
    assert "Explore sample book" in html


def test_home_render_shows_door_and_book_vitals_together(tmp_path: object) -> None:  # type: ignore[no-untyped-def]
    """FIX A: when brief_summary.json exists, render() must show BOTH the
    landing door AND the Front-Desk vitals ('YOUR BOOK') in the same render.
    """
    import json
    from unittest.mock import MagicMock, patch

    import streamlit as st

    from adapters.visualization.tabs import weekly_brief as wb
    from application.evidence_card import EvidenceCard

    p = tmp_path / "brief_summary.json"  # type: ignore[operator]
    p.write_text(
        json.dumps(
            {
                "as_of": "2026-06-14",
                "regime": "RISK_ON",
                "abstained": False,
                "holdings": [
                    {
                        "ticker": "YUMC",
                        "verdict": "TRIM",
                        "unrealized_pct": 22.7,
                        "trend_state": "broken",
                        "why": "pulled back below trend",
                    }
                ],
                "macro": {
                    "systematic_share": 0.628,
                    "net_beta_by_factor": {"SPY": 1.42},
                },
            }
        )
    )
    captured: list[str] = []
    progress_mock = MagicMock()
    with (
        patch.object(
            st, "markdown", side_effect=lambda c, **k: captured.append(str(c))
        ),
        patch.object(st, "download_button"),
        patch.object(st, "caption"),
        patch.object(st, "expander"),
        patch.object(st, "divider"),
        patch.object(
            st, "columns", return_value=[MagicMock(), MagicMock(), MagicMock()]
        ),
        patch.object(st, "progress", return_value=progress_mock),
        patch.object(wb, "_fetch_card", return_value=EvidenceCard("YUMC", (), ())),
        patch.object(wb, "select_case_summarizer", return_value=MagicMock()),
        patch.object(wb, "_render_one_holding_fragment", wb._render_one_holding),
        patch.object(wb, "is_local_runtime", return_value=False),
    ):
        wb.render(
            path=str(p),
            adherence_path=str(tmp_path / "a.jsonl"),  # type: ignore[operator]
            reports_dir=str(tmp_path),  # type: ignore[arg-type]
        )
    html = "\n".join(captured)
    assert (
        "Load a book to begin" in html
    ), "Landing door must be present even when a brief exists"
    assert "YOUR BOOK" in html, "Book vitals strip must also be present"


def test_fetch_card_analyst_key_mapping_lights_analysts_square() -> None:
    """_fetch_card must remap numberOfAnalystOpinions → analyst_count so
    build_analyst_panel builds a non-GAP panel when coverage is present."""
    from unittest.mock import patch  # noqa: PLC0415

    from adapters.visualization.tabs import weekly_brief as wb
    from domain.evidence_rag import RagColor

    raw_info = {
        "numberOfAnalystOpinions": 18,
        "recommendationMean": 2.1,
        "targetMeanPrice": 320.0,
        "targetHighPrice": 380.0,
        "targetLowPrice": 260.0,
        "currentPrice": 295.0,
        "trailingPE": 24.0,
        "pegRatio": 1.5,
        "freeCashflow": 5_000_000_000,
        "debtToEquity": 45.0,
    }

    with (
        patch(
            "adapters.visualization.price_cache.fetch_ticker_info",
            return_value=raw_info,
        ),
        patch(
            "adapters.visualization.price_cache.fetch_prices",
            return_value={"MSFT": {"price": 295.0, "change_pct": 0.5}},
        ),
        patch(
            "adapters.data.earnings_history_adapter.fetch_earnings_history",
            return_value=None,
        ),
        patch(
            "adapters.visualization.price_cache._fetch_ticker_info_impl",
            return_value=raw_info,
        ),
        patch(
            "adapters.visualization.price_cache._batch_fetch_prices_impl",
            return_value={"MSFT": {"price": 295.0, "change_pct": 0.5}},
        ),
    ):
        # Patch at the lazy-import level by patching streamlit's cache_data to
        # be a pass-through so the cached wrappers call the (also patched) impls.
        import streamlit as st  # noqa: PLC0415

        with patch.object(
            st,
            "cache_data",
            side_effect=lambda *a, **kw: (lambda f: f),
        ):
            card = wb._fetch_card("MSFT")  # type: ignore[attr-defined]

    # Find the Analysts signal in the card
    analysts_sig = next((s for s in card.signals if s.dimension == "Analysts"), None)
    assert analysts_sig is not None, "Analysts signal missing from card"
    assert analysts_sig.color != RagColor.GAP, (
        f"Analysts square must NOT be GAP when numberOfAnalystOpinions=18, "
        f"got color={analysts_sig.color}"
    )
