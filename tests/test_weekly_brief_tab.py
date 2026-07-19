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


def test_render_with_summary_fixture(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
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

    # REDUCE verdict is in _NEEDS_REVIEW — an unmocked render() spawns a real
    # background daemon thread hitting live yfinance for "ARKK". This test
    # only cares that render() doesn't raise.
    monkeypatch.setattr(weekly_brief, "_launch_case_fetcher", lambda *a, **k: None)

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


def test_render_hero_counts_attention(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
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

    # ticker "A" has verdict REDUCE (in _NEEDS_REVIEW) — an unmocked render()
    # spawns a real background daemon thread hitting live yfinance.
    monkeypatch.setattr(weekly_brief, "_launch_case_fetcher", lambda *a, **k: None)

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
        # _handle_onboarding now uses 2-column layout (_render_book_actions)
        patch.object(
            st,
            "container",
            return_value=MagicMock(
                __enter__=MagicMock(return_value=MagicMock()),
                __exit__=MagicMock(return_value=False),
            ),
        ),
        patch.object(
            st,
            "popover",
            return_value=MagicMock(
                __enter__=MagicMock(return_value=MagicMock()),
                __exit__=MagicMock(return_value=False),
            ),
        ),
        patch.object(st, "caption"),
        patch.object(st, "progress", return_value=progress_mock),
        patch.object(wb, "fetch_card", return_value=EvidenceCard("YUMC", (), ())),
        patch.object(wb, "select_case_summarizer", return_value=MagicMock()),
        patch.object(wb, "_render_one_holding_fragment", wb._render_one_holding),
        # _launch_case_fetcher's background worker also calls personal_case_news,
        # which hits live yfinance if unmocked (fetch_card alone isn't enough).
        patch.object(wb, "personal_case_news", return_value=[]),
        # FIX B: stub network fetches so _render_one_holding doesn't hit yfinance
        patch(
            "adapters.visualization.price_cache.fetch_prices",
            return_value={"YUMC": {"price": 44.63, "change_pct": 0.5}},
        ),
        patch(
            "adapters.visualization.price_cache.fetch_price_history",
            return_value={
                "closes": [float(100 + i) for i in range(200)],
                "atr": None,
                "ma200": None,
            },
        ),
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


def test_book_health_label_not_duplicated() -> None:
    """Regression: 'Systematic share' used to print twice back-to-back
    ('...systematic shareSystematic share')."""
    from adapters.visualization.tabs import weekly_brief as wb

    html = wb._render_book_health_html(systematic_share=0.628)
    assert html.lower().count("systematic share") == 1


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


def test_book_strip_tile_labels_are_not_duplicated(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Regression: each tile used to combine tooltip(term) with an evidence
    chip that renders the same term again, printing e.g. 'Need review Need
    review' / 'vs Market (1y) vs Market (1y)'."""
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
    assert html.lower().count("need review") == 1
    assert html.lower().count("vs market (1y)") == 1
    assert html.lower().count("net beta") == 1


def test_book_strip_chips_have_no_inline_adr_or_badge() -> None:
    """Home's book-strip tiles must not print raw ADR-0XX / verdict badges
    inline — that jargon moves into the chip's hover tooltip only."""
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
    assert "ri-vbadge" not in html
    assert "ri-chip-adr" not in html
    assert "ADR-" not in html.split('class="ri-chip-tip"')[0]


def test_book_health_chip_has_no_inline_adr_or_badge() -> None:
    from adapters.visualization.tabs import weekly_brief as wb

    html = wb._render_book_health_html(systematic_share=0.628)
    assert "ri-vbadge" not in html
    assert "ri-chip-adr" not in html


def test_evidence_record_row_chips_have_no_inline_adr_or_badge() -> None:
    from adapters.visualization.tabs import weekly_brief as wb
    from domain.evidence_registry import get_evidence

    entry = get_evidence("net_beta")
    assert entry is not None
    html = wb._evidence_record_row_html("What we know", "blurb", [entry])
    assert "ri-vbadge" not in html
    assert "ri-chip-adr" not in html


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


def test_rendered_home_triage_strip_present(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
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

    # This fixture's holding has verdict REDUCE (in _NEEDS_REVIEW), so an
    # unmocked render() spawns a real background daemon thread hitting live
    # yfinance for "ARKK" — this test only cares about the triage strip HTML.
    monkeypatch.setattr(weekly_brief, "_launch_case_fetcher", lambda *a, **k: None)

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
    monkeypatch.setattr(wb, "fetch_card", lambda t: EvidenceCard(t, (), ()))  # type: ignore[attr-defined]
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

    html = wb._render_onboarding_html()  # type: ignore[attr-defined]
    assert "Sample book" in html


def test_home_door_always_present_even_with_book() -> None:
    """Banner renders the same regardless of book state — always visible."""
    from adapters.visualization.tabs import weekly_brief as wb

    html = wb._render_onboarding_html()  # type: ignore[attr-defined]
    assert "Sample book" in html, "Banner must always be present"


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
        # _handle_onboarding now uses 2-column layout (_render_book_actions)
        patch.object(
            st,
            "container",
            return_value=MagicMock(
                __enter__=MagicMock(return_value=MagicMock()),
                __exit__=MagicMock(return_value=False),
            ),
        ),
        patch.object(
            st,
            "popover",
            return_value=MagicMock(
                __enter__=MagicMock(return_value=MagicMock()),
                __exit__=MagicMock(return_value=False),
            ),
        ),
        patch.object(st, "caption"),
        patch.object(st, "progress", return_value=progress_mock),
        patch.object(wb, "fetch_card", return_value=EvidenceCard("YUMC", (), ())),
        patch.object(wb, "select_case_summarizer", return_value=MagicMock()),
        patch.object(wb, "_render_one_holding_fragment", wb._render_one_holding),
        # _launch_case_fetcher's background worker also calls personal_case_news,
        # which hits live yfinance if unmocked (fetch_card alone isn't enough).
        patch.object(wb, "personal_case_news", return_value=[]),
        patch(
            "adapters.visualization.price_cache.fetch_price_history",
            return_value=None,
        ),
    ):
        wb.render(
            path=str(p),
            adherence_path=str(tmp_path / "a.jsonl"),  # type: ignore[operator]
            reports_dir=str(tmp_path),  # type: ignore[arg-type]
        )
    html = "\n".join(captured)
    assert (
        "Sample book" in html
    ), "Sample-book banner must be present even when a brief exists"
    assert "YOUR BOOK" in html, "Book vitals strip must also be present"


# ---------------------------------------------------------------------------
# FIX B: pure helper unit tests (RED — must fail before helpers are added)
# ---------------------------------------------------------------------------


def test_implied_cost_known_values() -> None:
    """implied_cost(price=44.63, unrealized_pct=22.7) → ~36.37 (±0.01)."""
    from adapters.visualization.tabs.weekly_brief import (
        implied_cost,  # type: ignore[attr-defined]
    )

    result = implied_cost(44.63, 22.7)
    assert result is not None
    assert abs(result - 36.37) < 0.01, f"Expected ~36.37, got {result}"


def test_implied_cost_zero_unrealized() -> None:
    """When unrealized_pct == 0, cost == price."""
    from adapters.visualization.tabs.weekly_brief import (
        implied_cost,  # type: ignore[attr-defined]
    )

    result = implied_cost(100.0, 0.0)
    assert result is not None
    assert abs(result - 100.0) < 1e-9


def test_implied_cost_none_when_price_none() -> None:
    """When price is None, implied_cost returns None (honest gap)."""
    from adapters.visualization.tabs.weekly_brief import (
        implied_cost,  # type: ignore[attr-defined]
    )

    assert implied_cost(None, 22.7) is None  # type: ignore[arg-type]


def test_implied_cost_none_when_unrealized_none() -> None:
    """When unrealized_pct is None, implied_cost returns None (honest gap)."""
    from adapters.visualization.tabs.weekly_brief import (
        implied_cost,  # type: ignore[attr-defined]
    )

    assert implied_cost(100.0, None) is None  # type: ignore[arg-type]


def test_window_returns_basic() -> None:
    """window_returns with 200 closes returns a 4-tuple for (7,30,90,180)."""
    from adapters.visualization.tabs.weekly_brief import (
        window_returns,  # type: ignore[attr-defined]
    )

    closes = [float(100 + i * 0.1) for i in range(200)]
    result = window_returns(closes)
    assert len(result) == 4  # one per window


def test_window_returns_values_correct() -> None:
    """7d return from 200 closes of known values is calculable."""
    from adapters.visualization.tabs.weekly_brief import (
        window_returns,  # type: ignore[attr-defined]
    )

    # All closes are 100 except last 8 which rise by 1 each
    closes = [100.0] * 192 + [101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0, 108.0]
    result = window_returns(closes)
    # 7d: closes[-1]=108, closes[-8]=101 → (108/101 - 1)*100 ≈ 6.93
    assert abs(result[0] - (108.0 / 101.0 - 1) * 100) < 0.01, f"7d: {result[0]}"


def test_window_returns_short_history_skips_unavailable() -> None:
    """With only 10 closes, windows >10 must be absent (not fabricated)."""
    from adapters.visualization.tabs.weekly_brief import (
        window_returns,  # type: ignore[attr-defined]
    )

    closes = [float(100 + i) for i in range(10)]  # only 10 days
    result = window_returns(closes)
    # 7d is available (needs 8 closes), 30/90/180 are not available (< 31 closes)
    assert len(result) <= 4
    # The 7d return should be present since we have 10 closes (index -8 exists)
    assert len(result) >= 1


def test_window_returns_empty_closes() -> None:
    """Empty closes → empty tuple."""
    from adapters.visualization.tabs.weekly_brief import (
        window_returns,  # type: ignore[attr-defined]
    )

    result = window_returns([])
    assert result == ()


def test_home_expanded_card_has_real_price(tmp_path: object) -> None:  # type: ignore[no-untyped-def]
    """FIX B: when fetch_prices returns a real price, the expanded card HTML
    must contain that price value (e.g. '295.0'), not '—'.
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
                "macro": {"systematic_share": 0.50, "net_beta_by_factor": {"SPY": 1.0}},
            }
        )
    )
    captured: list[str] = []
    progress_mock = MagicMock()

    # 200 fake closes so all 4 windows are available
    fake_closes = [float(100 + i * 0.1) for i in range(200)]
    fake_history = {"closes": fake_closes, "atr": 1.5, "ma200": 110.0, "vs_spy": None}
    fake_prices = {"YUMC": {"price": 44.63, "change_pct": 0.5}}

    # Pre-populate book so _handle_onboarding skips auto-load (which would clear the cache).
    st.session_state["book"] = []
    # Pre-populate case cache so _render_one_holding renders the full expanded card
    # (case=None → data_gap placeholder, but price/returns still wired from fetched data)
    st.session_state[wb._HOME_CASES_KEY] = {"YUMC": None}
    st.session_state[wb._HOME_FETCH_STARTED_KEY] = True
    # The row is now a merged row + chevron toggle (render_toggle_row) instead
    # of a separate st.expander — open it via its session_state key so the
    # detail callback (which contains the price/returns HTML) actually runs.
    st.session_state["nr_open_YUMC"] = True

    with (
        patch.object(
            st, "markdown", side_effect=lambda c, **k: captured.append(str(c))
        ),
        patch.object(st, "download_button"),
        patch.object(st, "caption"),
        patch.object(st, "divider"),
        # _handle_onboarding now uses 2-column layout (_render_book_actions)
        patch.object(
            st,
            "container",
            return_value=MagicMock(
                __enter__=MagicMock(return_value=MagicMock()),
                __exit__=MagicMock(return_value=False),
            ),
        ),
        patch.object(
            st,
            "popover",
            return_value=MagicMock(
                __enter__=MagicMock(return_value=MagicMock()),
                __exit__=MagicMock(return_value=False),
            ),
        ),
        patch.object(st, "caption"),
        patch.object(st, "progress", return_value=progress_mock),
        patch.object(wb, "fetch_card", return_value=EvidenceCard("YUMC", (), ())),
        patch.object(wb, "select_case_summarizer", return_value=MagicMock()),
        patch.object(wb, "_render_one_holding_fragment", wb._render_one_holding),
        patch(
            "adapters.visualization.price_cache.fetch_prices", return_value=fake_prices
        ),
        patch(
            "adapters.visualization.price_cache.fetch_price_history",
            return_value=fake_history,
        ),
    ):
        wb.render(
            path=str(p),
            adherence_path=str(tmp_path / "a.jsonl"),  # type: ignore[operator]
            reports_dir=str(tmp_path),  # type: ignore[arg-type]
        )

    html = "\n".join(captured)
    # The expanded card must contain the real price "44.63" (not just "—")
    assert (
        "44.63" in html
    ), f"Expected real price 44.63 in expanded card HTML, got: {html[:500]}"


def test_one_holding_data_gap_case_shows_honest_no_evidence_not_pending() -> None:
    """A completed fetch that found no evidence (data_gap=True) must render the
    same honest 'no evidence found' message as a failed fetch (case=None) —
    never the misleading 'loads when you open this card' pending copy, since
    by the time this branch runs the fetch has already been attempted."""
    from unittest.mock import MagicMock, patch

    import streamlit as st

    from adapters.visualization.tabs import weekly_brief as wb
    from application.evidence_card import EvidenceCard
    from domain.case_models import CaseResult

    holding = {
        "ticker": "YUMC",
        "verdict": "TRIM",
        "unrealized_pct": 22.7,
        "why": "pulled back below trend",
    }

    # The row is now a merged row + chevron toggle (render_toggle_row) instead
    # of a separate st.expander — open it via its session_state key so the
    # detail callback (which contains the "no evidence" HTML) actually runs.
    st.session_state.clear()
    st.session_state["nr_open_YUMC"] = True

    captured: list[str] = []
    with (
        patch.object(
            st, "markdown", side_effect=lambda c, **k: captured.append(str(c))
        ),
        patch.object(st, "caption"),
        patch.object(wb, "fetch_card", return_value=EvidenceCard("YUMC", (), ())),
        patch(
            "adapters.visualization.price_cache.fetch_prices",
            return_value={"YUMC": {"price": 44.63, "change_pct": 0.5}},
        ),
        patch(
            "adapters.visualization.price_cache.fetch_price_history",
            return_value={"closes": [], "atr": None, "ma200": None},
        ),
    ):
        wb._render_one_holding("YUMC", holding, MagicMock(), CaseResult((), (), True))

    html = "\n".join(captured)
    assert "loads when you open this card" not in html.lower()
    assert "No cited evidence found" in html


def test_fetch_card_analyst_key_mapping_lights_analysts_square() -> None:
    """fetch_card must remap numberOfAnalystOpinions → analyst_count so
    build_analyst_panel builds a non-GAP panel when coverage is present."""
    from unittest.mock import patch  # noqa: PLC0415

    import adapters.visualization.card_fetch as card_fetch_mod
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
            card = card_fetch_mod.fetch_card("MSFT")

    # Find the Analysts signal in the card
    analysts_sig = next((s for s in card.signals if s.dimension == "Analysts"), None)
    assert analysts_sig is not None, "Analysts signal missing from card"
    assert analysts_sig.color != RagColor.GAP, (
        f"Analysts square must NOT be GAP when numberOfAnalystOpinions=18, "
        f"got color={analysts_sig.color}"
    )


# ── FIX 2: 1-year return window (252 trading days) ───────────────────────────


def test_window_returns_five_values_for_long_series() -> None:
    """window_returns with windows=(7,30,90,180,252) and 300 closes returns 5 values."""
    from adapters.visualization.tabs.weekly_brief import window_returns

    closes = [float(i) for i in range(1, 302)]  # 301 elements, all windows available
    result = window_returns(closes, windows=(7, 30, 90, 180, 252))
    assert len(result) == 5, f"expected 5 values, got {len(result)}"
    # 252-window value: (closes[-1] / closes[-1-252] - 1) * 100 = (301/49 - 1)*100
    expected_1y = (closes[-1] / closes[-1 - 252] - 1.0) * 100.0
    assert abs(result[4] - expected_1y) < 1e-6


def test_window_returns_skips_1y_for_short_series() -> None:
    """window_returns with a 100-close series skips the 252 window (returns 4 values)."""
    from adapters.visualization.tabs.weekly_brief import window_returns

    closes = [
        float(i) for i in range(1, 102)
    ]  # 101 elements: covers 7/30/90, not 180 or 252
    result = window_returns(closes, windows=(7, 30, 90, 180, 252))
    # 101 closes: 7+1=8 ✓, 30+1=31 ✓, 90+1=91 ✓, 180+1=181 ✗, 252+1=253 ✗ → 3 values
    assert (
        len(result) == 3
    ), f"expected 3 values for 101-close series, got {len(result)}"


def test_window_returns_default_includes_252() -> None:
    """After FIX 2, window_returns() default windows tuple includes 252."""
    import inspect

    from adapters.visualization.tabs.weekly_brief import window_returns

    sig = inspect.signature(window_returns)
    default_windows = sig.parameters["windows"].default
    assert 252 in default_windows, f"252 not in default windows: {default_windows}"


def test_expanded_card_shows_1y_label() -> None:
    """render_expanded_card must include '1y' in the returns label after FIX 2."""
    from adapters.visualization.components.decision_card import render_expanded_card
    from application.evidence_card import EvidenceCard
    from domain.discipline import Verdict
    from domain.evidence_rag import RagColor, RagSignal

    sigs = (RagSignal("Technicals", RagColor.GREEN, "above trend"),)
    card = EvidenceCard(ticker="AAPL", signals=sigs, sparkline=())
    html = render_expanded_card(
        card,
        case=None,
        verdict=Verdict.HOLD,
        name="Apple",
        unrealized_pct=10.0,
        means="Trending well.",
        price=150.0,
        cost=120.0,
        returns=(2.0, 5.0, 12.0, 18.0, 35.0),
        reliability="n/a",
    )
    assert "1y" in html, "expanded card must contain '1y' label after FIX 2"


# ---------------------------------------------------------------------------
# P2-Home: inline evidence chips on the 5 book tiles + the credibility panel
# ("What we know / don't know / still testing") driven by the evidence registry.
# ---------------------------------------------------------------------------


def _fake_entry(key: str, label: str, verdict):  # type: ignore[no-untyped-def]
    """Build a tiny EvidenceEntry fixture (no registry / API dependency)."""
    from domain.evidence_registry import EvidenceEntry

    return EvidenceEntry(
        key=key,
        label=label,
        meaning=f"meaning of {label}",
        healthy_band=f"band for {label}",
        verdict=verdict,
        adr="ADR-099",
        caveat=f"caveat for {label}",
    )


def test_book_strip_tiles_carry_evidence_chips() -> None:
    """Each of the 4 book-strip tiles must render an inline evidence chip; the
    verdict + ADR from the registry surface inside the hover tooltip only
    (Home chips are compact — see test_book_strip_chips_have_no_inline_adr_or_badge)."""
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
    # The shared chip component is present on the strip...
    assert "ri-chip" in html
    # ...and the strip carries one chip per tile (need_review / vs_market /
    # net_beta / screen_cleared) — at least 4 chip spans.
    assert html.count('class="ri-chip"') >= 4
    # Verdict words from the registry ride along inside the hover tooltip
    # (e.g. descriptive + research-only) — not as an always-visible badge.
    assert "DESCRIPTIVE" in html and "RESEARCH_ONLY" in html
    assert "ri-vbadge" not in html
    # Registry meaning text rides along for the screen tile.
    assert "pre-registered gate" in html.lower() or "ADR-049" in html


def test_book_health_tile_carries_systematic_share_chip() -> None:
    """The systematic-share book-health tile must carry its registry chip."""
    from adapters.visualization.tabs import weekly_brief as wb

    html = wb._render_book_health_html(systematic_share=0.628)
    assert "ri-chip" in html
    # systematic_share is RESEARCH_ONLY in the registry — verdict word rides
    # along inside the hover tooltip only, no always-visible badge on Home.
    assert "RESEARCH_ONLY" in html
    assert "ri-vbadge" not in html
    # Existing behaviour preserved.
    assert "63%" in html and "60%" in html


def test_evidence_record_row_renders_entry_chips() -> None:
    from adapters.visualization.tabs import weekly_brief as wb
    from domain.evidence_registry import Verdict

    entries = [
        _fake_entry("a", "Alpha Fact", Verdict.DESCRIPTIVE),
        _fake_entry("b", "Beta Fact", Verdict.VALIDATED),
    ]
    html = wb._evidence_record_row_html("What we know", "blurb here", entries)
    assert "What we know" in html and "blurb here" in html
    assert html.count('class="ri-chip"') == 2
    assert "Alpha Fact" in html and "Beta Fact" in html
    assert "— none —" not in html


def test_evidence_record_row_empty_shows_none() -> None:
    from adapters.visualization.tabs import weekly_brief as wb

    html = wb._evidence_record_row_html("Killed in testing", "blurb", [])
    assert "Killed in testing" in html
    assert "— none —" in html
    assert "ri-chip" not in html


def test_render_evidence_record_html_has_four_buckets() -> None:
    from adapters.visualization.tabs import weekly_brief as wb
    from domain.evidence_registry import Verdict

    html = wb._render_evidence_record_html(
        known=[_fake_entry("k", "Known One", Verdict.DESCRIPTIVE)],
        unproven=[_fake_entry("u", "Unproven One", Verdict.RESEARCH_ONLY)],
        killed=[_fake_entry("x", "Killed One", Verdict.FALSIFIED)],
        testing=[_fake_entry("t", "Testing One", Verdict.FORWARD_PENDING)],
    )
    assert "ws-card" in html  # reuses the existing card class
    assert "What we know" in html
    assert "still researching" in html.lower()
    assert "Killed in testing" in html
    assert "Still testing" in html
    # All four fixture entries render as chips.
    for label in ("Known One", "Unproven One", "Killed One", "Testing One"):
        assert label in html
    assert html.count('class="ri-chip"') == 4


def test_home_evidence_record_html_uses_live_registry() -> None:
    """The assembled panel must pull the real registry: the forward-pending
    discipline gate (ADR-048) and a falsified signal must both surface."""
    from adapters.visualization.tabs import weekly_brief as wb

    html = wb._home_evidence_record_html()
    assert "ws-card" in html
    # FORWARD_PENDING entry — the live discipline gate.
    assert "ADR-048" in html and "Discipline gate" in html
    # FALSIFIED entry — the killed sentiment signal.
    assert "Sentiment" in html
    # The four bucket headings are all present.
    assert "What we know" in html
    assert "Killed in testing" in html
    assert "Still testing" in html


def test_rendered_home_shows_evidence_record_panel(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """render() must emit the credibility panel into the page markup."""
    p = tmp_path / "brief_summary.json"
    p.write_text(
        json.dumps(
            {
                "as_of": "2026-06-13",
                "regime": "RISK_ON",
                "abstained": True,
                "holdings": [],
                "macro": {"systematic_share": 0.5},
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
    assert "What we know" in all_html
    assert "Still testing" in all_html
    # The panel pulls the live registry — the forward-pending gate is shown.
    assert "ADR-048" in all_html


# ---------------------------------------------------------------------------
# Public sample book: cold start must never auto-load data/personal/
# ---------------------------------------------------------------------------


def test_handle_onboarding_never_autoloads_personal_even_if_present(  # type: ignore[no-untyped-def]
    monkeypatch,
) -> None:
    """Regression for the live bug: cold start must always resolve to the
    sample book, never ``data/personal/holdings.csv``, even when that file and
    ``upload_history.json`` exist on the machine running the dashboard (the
    normal state on the operator's own laptop)."""
    import pathlib
    from unittest.mock import MagicMock

    import streamlit as st

    from adapters.visualization.tabs import weekly_brief as wb
    from application.holdings_reader import Holding

    monkeypatch.setattr(st, "session_state", {}, raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

    real_exists = pathlib.Path.exists

    def fake_exists(self: pathlib.Path) -> bool:
        if str(self) in {
            "data/personal/holdings.csv",
            "data/personal/upload_history.json",
        }:
            return True
        return real_exists(self)

    monkeypatch.setattr(pathlib.Path, "exists", fake_exists)
    monkeypatch.setattr(
        wb,
        "read_holdings",
        lambda path: (
            [Holding("COST", 1.0, 100.0, "TFSA")] if "personal" in str(path) else []
        ),
    )
    monkeypatch.setattr(wb, "holdings_upload_enabled", lambda: False)
    monkeypatch.setattr(
        st,
        "container",
        lambda *a, **k: MagicMock(  # noqa: ARG005
            __enter__=MagicMock(return_value=MagicMock()),
            __exit__=MagicMock(return_value=False),
        ),
    )
    monkeypatch.setattr(st, "markdown", lambda *a, **k: None)  # noqa: ARG005

    wb._handle_onboarding()

    assert st.session_state["is_sample_book"] is True
    tickers = {h.ticker for h in st.session_state["book"]}
    assert "COST" not in tickers
    assert tickers == {
        "AAPL",
        "MSFT",
        "NVDA",
        "GOOGL",
        "AMZN",
        "TSLA",
        "META",
        "JPM",
        "V",
        "BRK-B",
    }


def test_render_default_args_resolve_to_sample_paths_on_cold_start(  # type: ignore[no-untyped-def]
    monkeypatch,
) -> None:
    """render() called with no explicit path/reports_dir (the real call from
    dashboard.py) must resolve through the book-context resolver on cold
    start — the committed sample artifacts, never data/personal/."""
    from unittest.mock import MagicMock

    import streamlit as st

    from adapters.visualization.tabs import weekly_brief as wb

    monkeypatch.setattr(st, "session_state", {}, raising=False)
    monkeypatch.setattr(wb, "holdings_upload_enabled", lambda: False)
    monkeypatch.setattr(
        st,
        "container",
        lambda *a, **k: MagicMock(  # noqa: ARG005
            __enter__=MagicMock(return_value=MagicMock()),
            __exit__=MagicMock(return_value=False),
        ),
    )
    monkeypatch.setattr(st, "markdown", lambda *a, **k: None)  # noqa: ARG005
    monkeypatch.setattr(st, "info", lambda *a, **k: None)  # noqa: ARG005
    monkeypatch.setattr(st, "warning", lambda *a, **k: None)  # noqa: ARG005

    captured: dict[str, str] = {}

    def fake_load_brief_summary(path: str) -> None:
        captured["path"] = path
        return None

    monkeypatch.setattr(wb, "load_brief_summary", fake_load_brief_summary)

    wb.render()

    assert captured["path"] == "data/sample/brief_summary.json"


def test_stage_csv_upload_is_session_only(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Upload must never write to data/personal/ (save_and_sync_holdings) —
    the parsed book goes straight into session_state, and the background
    rebuild target must be a session/temp path."""
    import streamlit as st

    from adapters.visualization.tabs import weekly_brief as wb

    monkeypatch.setattr(st, "session_state", {}, raising=False)
    monkeypatch.setattr(st, "toast", lambda *a, **k: None)  # noqa: ARG005
    monkeypatch.setattr(st, "rerun", lambda: None)

    assert not hasattr(wb, "save_and_sync_holdings"), (
        "the public-facing tab module must not even import the "
        "data/personal/-writing sync function"
    )

    rebuild_calls: list[tuple[object, object]] = []
    monkeypatch.setattr(
        wb,
        "_start_dashboard_rebuild_background",
        lambda *a, **k: rebuild_calls.append((a, k)),
    )

    class FakeUpload:
        name = "portfolio.csv"

        def getvalue(self) -> bytes:
            return (
                b"symbol,quantity,book value (cad),exchange,account type\n"
                b"COST,5,900,NASDAQ,TFSA\n"
            )

    wb._stage_csv_upload(FakeUpload())

    assert st.session_state["is_sample_book"] is False
    tickers = {h.ticker for h in st.session_state["book"]}
    assert tickers == {"COST"}
    assert rebuild_calls, "must still kick off a background rebuild"
    call_args, call_kwargs = rebuild_calls[0]
    blob = str(call_args) + str(call_kwargs)
    assert "data/personal" not in blob
    assert wb.SESSION_BRIEF_PATH_KEY in st.session_state
    assert "data/personal" not in st.session_state[wb.SESSION_BRIEF_PATH_KEY]


def test_stage_csv_upload_deletes_previous_upload_tmp_dir(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """A second CSV upload must delete the FIRST upload's tmp dir (holdings
    CSV + its rebuild artifacts) — it's immediately superseded, since
    session_state pointers only ever reference the newest upload. Otherwise
    every upload on a long-lived Cloud container leaks another visitor's
    holdings CSV on disk forever (tempfile.mkdtemp has no built-in cleanup)."""
    from pathlib import Path

    import streamlit as st

    from adapters.visualization.tabs import weekly_brief as wb

    monkeypatch.setattr(st, "session_state", {}, raising=False)
    monkeypatch.setattr(st, "toast", lambda *a, **k: None)  # noqa: ARG005
    monkeypatch.setattr(st, "rerun", lambda: None)
    monkeypatch.setattr(
        wb, "_start_dashboard_rebuild_background", lambda *a, **k: None
    )  # noqa: ARG005

    old_dir = tmp_path / "old_upload_dir"
    old_dir.mkdir()
    (old_dir / "holdings.csv").write_text("stale holder data")
    st.session_state[wb._HOME_UPLOAD_TMP_DIR_KEY] = str(old_dir)

    class FakeUpload:
        name = "portfolio.csv"

        def getvalue(self) -> bytes:
            return (
                b"symbol,quantity,book value (cad),exchange,account type\n"
                b"COST,5,900,NASDAQ,TFSA\n"
            )

    wb._stage_csv_upload(FakeUpload())

    assert not old_dir.exists(), "previous upload's tmp dir must be deleted"
    new_dir = st.session_state[wb._HOME_UPLOAD_TMP_DIR_KEY]
    assert new_dir != str(old_dir)
    assert Path(new_dir).exists(), "the new upload's own tmp dir must still exist"


def test_run_brief_button_sample_context_refreshes_to_session_temp(  # type: ignore[no-untyped-def]
    monkeypatch,
) -> None:
    """Clicking Run brief while viewing the sample book must read the
    committed sample CSV but write to a fresh session-scoped temp path —
    never overwrite data/sample/brief_summary.json itself."""
    from unittest.mock import MagicMock

    import streamlit as st

    from adapters.visualization.book_context import UIBookContext
    from adapters.visualization.tabs import weekly_brief as wb

    monkeypatch.setattr(st, "session_state", {}, raising=False)
    monkeypatch.setattr(
        st,
        "container",
        lambda *a, **k: MagicMock(  # noqa: ARG005
            __enter__=MagicMock(return_value=MagicMock()),
            __exit__=MagicMock(return_value=False),
        ),
    )
    monkeypatch.setattr(st, "caption", lambda *a, **k: None)  # noqa: ARG005
    monkeypatch.setattr(st, "button", lambda *a, **k: True)  # noqa: ARG005

    rebuild_calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        wb,
        "_start_dashboard_rebuild_background",
        lambda **kw: rebuild_calls.append(kw),
    )

    ctx = UIBookContext(
        book=[],
        is_sample=True,
        brief_path="data/sample/brief_summary.json",
        reports_dir="data/sample",
    )
    wb._render_run_brief_gate(ctx, 3)

    assert rebuild_calls, "must trigger a background rebuild"
    kw = rebuild_calls[0]
    assert kw["holdings_csv"] == "data/sample/sample_book.csv"
    assert kw["out_path"] != "data/sample/weekly_brief.md"
    refreshed = st.session_state[wb.SESSION_SAMPLE_REFRESH_BRIEF_KEY]
    assert refreshed != "data/sample/brief_summary.json"


def test_trigger_brief_run_deletes_previous_click_tmp_dir(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Each Run brief click creates a fresh output tmp dir (per its own
    docstring: 'each Run click never collides with an earlier one') — the
    PREVIOUS click's dir must be deleted since it's immediately superseded
    (SESSION_SAMPLE_REFRESH_BRIEF_KEY/SESSION_BRIEF_PATH_KEY always point at
    only the newest). Otherwise repeated clicks leak a tmp dir forever."""
    from pathlib import Path

    import streamlit as st

    from adapters.visualization.book_context import UIBookContext
    from adapters.visualization.tabs import weekly_brief as wb

    old_dir = tmp_path / "old_run_dir"
    old_dir.mkdir()
    (old_dir / "brief_summary.json").write_text("{}")

    monkeypatch.setattr(
        st,
        "session_state",
        {wb._HOME_BRIEF_RUN_TMP_DIR_KEY: str(old_dir)},
        raising=False,
    )
    monkeypatch.setattr(
        wb, "_start_dashboard_rebuild_background", lambda *a, **k: None
    )  # noqa: ARG005

    ctx = UIBookContext(
        book=[],
        is_sample=True,
        brief_path="data/sample/brief_summary.json",
        reports_dir="data/sample",
    )
    wb._trigger_brief_run(ctx)

    assert not old_dir.exists(), "previous Run brief click's tmp dir must be deleted"
    new_dir = st.session_state[wb._HOME_BRIEF_RUN_TMP_DIR_KEY]
    assert new_dir != str(old_dir)
    assert Path(new_dir).exists()


def test_run_brief_button_disabled_when_fresh_never_triggers_rebuild(  # type: ignore[no-untyped-def]
    monkeypatch,
) -> None:
    """A fresh (<1 day old) brief must not offer a working Run button —
    st.button(disabled=True) never returns True, but assert the gate wiring
    passes disabled=True through so Streamlit actually blocks the click."""
    from unittest.mock import MagicMock

    import streamlit as st

    from adapters.visualization.book_context import UIBookContext
    from adapters.visualization.tabs import weekly_brief as wb

    monkeypatch.setattr(st, "session_state", {}, raising=False)
    monkeypatch.setattr(
        st,
        "container",
        lambda *a, **k: MagicMock(  # noqa: ARG005
            __enter__=MagicMock(return_value=MagicMock()),
            __exit__=MagicMock(return_value=False),
        ),
    )
    monkeypatch.setattr(st, "caption", lambda *a, **k: None)  # noqa: ARG005

    captured_kwargs: dict[str, object] = {}

    def fake_button(*args: object, **kwargs: object) -> bool:
        captured_kwargs.update(kwargs)
        return False

    monkeypatch.setattr(st, "button", fake_button)

    ctx = UIBookContext(
        book=[],
        is_sample=True,
        brief_path="data/sample/brief_summary.json",
        reports_dir="data/sample",
    )
    wb._render_run_brief_gate(ctx, 0)

    assert captured_kwargs.get("disabled") is True


# ---------------------------------------------------------------------------
# Background rebuild elapsed-time status — so a visitor uploading holdings
# (or clicking Run brief) sees real evidence the background job is alive,
# not a static banner that looks frozen for up to ~90s (correlation-graph
# pacing + holdings-risk + macro-beta).
# ---------------------------------------------------------------------------


def test_start_rebuild_records_start_timestamp(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import streamlit as st

    from adapters.visualization.tabs import weekly_brief as wb

    monkeypatch.setattr(st, "session_state", {}, raising=False)
    monkeypatch.setattr(
        wb.threading,
        "Thread",
        lambda **k: type("T", (), {"start": lambda self: None})(),
    )  # noqa: ARG005
    monkeypatch.setattr(wb, "_time_time", lambda: 1000.0)

    wb._start_dashboard_rebuild_background()

    assert st.session_state[wb._HOME_BRIEF_STARTED_AT_KEY] == 1000.0


def test_start_rebuild_passes_and_records_progress_path(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import streamlit as st

    from adapters.visualization.tabs import weekly_brief as wb

    monkeypatch.setattr(st, "session_state", {}, raising=False)

    class _SyncThread:
        def __init__(self, target, daemon=True) -> None:  # type: ignore[no-untyped-def]
            self._target = target

        def start(self) -> None:
            self._target()

    monkeypatch.setattr(wb.threading, "Thread", _SyncThread)

    rebuild_calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        wb, "rebuild_weekly_brief_cached", lambda **k: rebuild_calls.append(k)
    )

    wb._start_dashboard_rebuild_background(progress_path="/tmp/fake_progress.json")

    assert (
        st.session_state[wb._HOME_BRIEF_PROGRESS_PATH_KEY] == "/tmp/fake_progress.json"
    )
    assert rebuild_calls
    assert rebuild_calls[0]["progress_path"] == "/tmp/fake_progress.json"


def test_processing_status_shows_elapsed_seconds(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import streamlit as st

    from adapters.visualization.tabs import weekly_brief as wb

    monkeypatch.setattr(
        st,
        "session_state",
        {
            wb._HOME_BRIEF_PROCESSING_KEY: True,
            wb._HOME_BRIEF_STARTED_AT_KEY: 1000.0,
        },
        raising=False,
    )
    monkeypatch.setattr(wb, "_time_time", lambda: 1017.0)
    captured: list[str] = []
    monkeypatch.setattr(
        st, "info", lambda msg, **k: captured.append(msg)
    )  # noqa: ARG005

    wb._render_brief_processing_status()

    assert captured
    assert "17" in captured[0]


def test_processing_status_shows_real_ticker_progress_when_file_present(  # type: ignore[no-untyped-def]
    monkeypatch, tmp_path
) -> None:
    """When the CLI subprocess's progress file exists, show real
    succeeded/failed ticker counts — not just elapsed seconds."""
    import json

    import streamlit as st

    from adapters.visualization.tabs import weekly_brief as wb

    progress_file = tmp_path / "progress.json"
    progress_file.write_text(
        json.dumps(
            {
                "completed": 12,
                "total": 45,
                "succeeded": 10,
                "failed": 2,
                "failed_tickers": ["XYZ", "ABC"],
                "last_ticker": "MSFT",
            }
        )
    )
    monkeypatch.setattr(
        st,
        "session_state",
        {
            wb._HOME_BRIEF_PROCESSING_KEY: True,
            wb._HOME_BRIEF_STARTED_AT_KEY: 1000.0,
            wb._HOME_BRIEF_PROGRESS_PATH_KEY: str(progress_file),
        },
        raising=False,
    )
    monkeypatch.setattr(wb, "_time_time", lambda: 1017.0)
    captured: list[str] = []
    monkeypatch.setattr(
        st, "info", lambda msg, **k: captured.append(msg)
    )  # noqa: ARG005

    wb._render_brief_processing_status()

    assert captured
    msg = captured[0]
    assert "12/45" in msg
    assert "2 failed" in msg


def test_processing_status_falls_back_to_elapsed_when_progress_file_missing(  # type: ignore[no-untyped-def]
    monkeypatch, tmp_path
) -> None:
    """A configured progress_path that doesn't exist yet (early in the
    rebuild, before the first ticker completes) must degrade gracefully to
    the elapsed-only message — never crash on a missing/malformed file."""
    import streamlit as st

    from adapters.visualization.tabs import weekly_brief as wb

    monkeypatch.setattr(
        st,
        "session_state",
        {
            wb._HOME_BRIEF_PROCESSING_KEY: True,
            wb._HOME_BRIEF_STARTED_AT_KEY: 1000.0,
            wb._HOME_BRIEF_PROGRESS_PATH_KEY: str(tmp_path / "nonexistent.json"),
        },
        raising=False,
    )
    monkeypatch.setattr(wb, "_time_time", lambda: 1005.0)
    captured: list[str] = []
    monkeypatch.setattr(
        st, "info", lambda msg, **k: captured.append(msg)
    )  # noqa: ARG005

    wb._render_brief_processing_status()

    assert captured
    assert "5s elapsed" in captured[0]


def test_processing_status_no_op_when_not_processing(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import streamlit as st

    from adapters.visualization.tabs import weekly_brief as wb

    monkeypatch.setattr(st, "session_state", {}, raising=False)
    called: list[str] = []
    monkeypatch.setattr(st, "info", lambda msg, **k: called.append(msg))  # noqa: ARG005

    wb._render_brief_processing_status()

    assert called == []


def test_run_brief_gate_blocks_a_second_independent_session_while_first_runs(  # type: ignore[no-untyped-def]
    monkeypatch,
) -> None:
    """The Cloud incident this fixes: st.session_state is per-visitor, so two
    different visitors (simulated here by two fresh session_state dicts) must
    NOT both be able to start a background rebuild concurrently — the gate
    must be enforced process-globally, not per-session."""
    from unittest.mock import MagicMock

    import streamlit as st

    from adapters.visualization import run_gate
    from adapters.visualization.book_context import UIBookContext
    from adapters.visualization.tabs import weekly_brief as wb

    monkeypatch.setattr(
        st,
        "container",
        lambda *a, **k: MagicMock(  # noqa: ARG005
            __enter__=MagicMock(return_value=MagicMock()),
            __exit__=MagicMock(return_value=False),
        ),
    )
    monkeypatch.setattr(st, "caption", lambda *a, **k: None)  # noqa: ARG005
    monkeypatch.setattr(st, "rerun", lambda: None)
    monkeypatch.setattr(
        wb, "rebuild_weekly_brief_cached", lambda **k: None
    )  # noqa: ARG005

    class _SyncThread:
        def __init__(self, target, daemon=True) -> None:  # type: ignore[no-untyped-def]
            self._target = target

        def start(self) -> None:
            self._target()

    monkeypatch.setattr(wb.threading, "Thread", _SyncThread)

    # Reset global gate state so this test is isolated from others.
    run_gate.set_processing("home_brief", False)
    run_gate.set_last_run_ts("home_brief", None)  # type: ignore[arg-type]

    ctx = UIBookContext(
        book=[],
        is_sample=True,
        brief_path="data/sample/brief_summary.json",
        reports_dir="data/sample",
    )

    # Visitor 1: fresh session, gate must be ready (no prior global run).
    monkeypatch.setattr(st, "session_state", {}, raising=False)
    gate1 = run_gate.evaluate_run_gate(
        staleness_days=3,
        is_running=run_gate.is_processing("home_brief"),
        last_run_ts=run_gate.get_last_run_ts("home_brief"),
    )
    assert gate1.can_run is True, "visitor 1 should be able to run"

    # Visitor 1 clicks — this sets the GLOBAL processing flag while running,
    # and (since the fake thread runs synchronously) clears it once done, but
    # the last-run timestamp is now set globally.
    monkeypatch.setattr(st, "button", lambda *a, **k: True)  # noqa: ARG005
    wb._render_run_brief_gate(ctx, 3)

    # Visitor 2: a totally independent session (fresh session_state dict) —
    # must now be blocked by the global cooldown, not "ready" again.
    monkeypatch.setattr(st, "session_state", {}, raising=False)
    gate2 = run_gate.evaluate_run_gate(
        staleness_days=3,
        is_running=run_gate.is_processing("home_brief"),
        last_run_ts=run_gate.get_last_run_ts("home_brief"),
    )
    assert gate2.can_run is False
    assert gate2.reason == "cooldown", (
        "a second, independent visitor session must see the global cooldown "
        "from visitor 1's run, not a fresh 'ready' gate"
    )


# ---------------------------------------------------------------------------
# Needs-review auto-fetch: fully automatic, single progress bar, auto-land.
# ---------------------------------------------------------------------------


def _needs_review_holdings() -> list[dict[str, object]]:
    return [
        {"ticker": "AAA", "verdict": "TRIM", "unrealized_pct": 1.0, "why": "x"},
        {"ticker": "BBB", "verdict": "REDUCE", "unrealized_pct": -2.0, "why": "y"},
    ]


def test_launch_case_fetcher_threads_real_news_and_extra_facts(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """The background worker must fetch real news + verdict/why/buzz facts,
    not the old news=[] gap — mirrors the fix already landed for Screener and
    Stock Analysis this session."""
    from adapters.visualization.tabs import weekly_brief as wb

    monkeypatch.setattr(wb, "fetch_card", lambda ticker: object())

    calls: list[dict[str, object]] = []

    def _fake_get_case_on_expand(ticker, card, news, *, expanded, summarizer, extra_facts=(), cache_path=None):  # type: ignore[no-untyped-def]
        calls.append(
            {
                "ticker": ticker,
                "news": news,
                "extra_facts": extra_facts,
            }
        )
        return object()

    monkeypatch.setattr(wb, "get_case_on_expand", _fake_get_case_on_expand)
    monkeypatch.setattr(wb, "personal_case_news", lambda ticker: [f"news-for-{ticker}"])
    monkeypatch.setattr(
        wb,
        "personal_case_extra_facts",
        lambda ticker, *, verdict, why: (f"Verdict: {verdict}. {why}",),
    )

    class _SyncThread:
        def __init__(self, target, daemon=True) -> None:  # type: ignore[no-untyped-def]
            self._target = target

        def start(self) -> None:
            self._target()

    monkeypatch.setattr(wb.threading, "Thread", _SyncThread)

    cards = [(h["ticker"], h) for h in _needs_review_holdings()]
    cases: dict[str, object] = {}
    wb._launch_case_fetcher(
        cards, summarizer=object(), cases=cases, reports_dir="data/reports/sample"
    )

    assert {c["ticker"] for c in calls} == {"AAA", "BBB"}
    aaa = next(c for c in calls if c["ticker"] == "AAA")
    assert aaa["news"] == ["news-for-AAA"]
    assert aaa["extra_facts"] == ("Verdict: TRIM. x",)
    assert set(cases) == {"AAA", "BBB"}


def test_launch_case_fetcher_threads_reports_dir_into_cache_path(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """The background worker must pass a {reports_dir}-scoped cache_path to
    get_case_on_expand, not the hardcoded data/personal/cited_cases.json —
    that path is gitignored and never exists on a fresh Cloud clone, so every
    visitor was silently firing live, uncached Gemini calls on Home tab load."""
    from adapters.visualization.tabs import weekly_brief as wb

    monkeypatch.setattr(wb, "fetch_card", lambda ticker: object())
    monkeypatch.setattr(wb, "personal_case_news", lambda ticker: [])
    monkeypatch.setattr(
        wb, "personal_case_extra_facts", lambda ticker, *, verdict, why: ()
    )

    calls: list[dict[str, object]] = []

    def _fake_get_case_on_expand(
        ticker, card, news, *, expanded, summarizer, extra_facts=(), cache_path=None
    ):  # type: ignore[no-untyped-def]
        calls.append({"ticker": ticker, "cache_path": cache_path})
        return object()

    monkeypatch.setattr(wb, "get_case_on_expand", _fake_get_case_on_expand)

    class _SyncThread:
        def __init__(self, target, daemon=True) -> None:  # type: ignore[no-untyped-def]
            self._target = target

        def start(self) -> None:
            self._target()

    monkeypatch.setattr(wb.threading, "Thread", _SyncThread)

    cards = [(h["ticker"], h) for h in _needs_review_holdings()]
    wb._launch_case_fetcher(
        cards, summarizer=object(), cases={}, reports_dir="data/reports/sample"
    )

    assert calls
    assert all(
        c["cache_path"] == "data/reports/sample/home_cited_cases.json" for c in calls
    )


def test_launch_case_fetcher_paces_yfinance_calls(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """The background worker fires ~4 yfinance calls per ticker (info, prices,
    price history, earnings) via fetch_card. Firing all needs-review tickers
    back-to-back with zero pacing is what tripped Yahoo's burst rate-limit on
    the Cloud deploy (DATA-GAP on Valuation/Financials/Earnings/Analysts for
    tickers that plainly have the data). The worker must sleep between tickers."""
    from adapters.visualization.tabs import weekly_brief as wb

    monkeypatch.setattr(wb, "fetch_card", lambda ticker: object())
    monkeypatch.setattr(
        wb, "get_case_on_expand", lambda *a, **k: object()
    )  # noqa: ARG005
    monkeypatch.setattr(wb, "personal_case_news", lambda ticker: [])
    monkeypatch.setattr(
        wb, "personal_case_extra_facts", lambda ticker, *, verdict, why: ()
    )

    class _SyncThread:
        def __init__(self, target, daemon=True) -> None:  # type: ignore[no-untyped-def]
            self._target = target

        def start(self) -> None:
            self._target()

    monkeypatch.setattr(wb.threading, "Thread", _SyncThread)

    sleep_calls: list[float] = []
    monkeypatch.setattr(wb, "_SLEEP", sleep_calls.append)

    cards = [(h["ticker"], h) for h in _needs_review_holdings()]
    wb._launch_case_fetcher(
        cards, summarizer=object(), cases={}, reports_dir="data/reports/sample"
    )

    assert len(sleep_calls) == len(cards)
    assert all(s > 0 for s in sleep_calls)


def test_needs_review_fetch_starts_without_button_click(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Fetch must start as soon as needs-review holdings render — zero clicks."""
    import streamlit as st

    from adapters.visualization.tabs import weekly_brief as wb

    monkeypatch.setattr(st, "session_state", {}, raising=False)
    monkeypatch.setattr(wb, "select_case_summarizer", lambda: object())
    monkeypatch.setattr(st, "progress", lambda *a, **k: None)  # noqa: ARG005
    monkeypatch.setattr(st, "markdown", lambda *a, **k: None)  # noqa: ARG005
    monkeypatch.setattr(
        wb, "_render_one_holding_fragment", lambda *a, **k: None
    )  # noqa: ARG005

    launch_calls: list[object] = []
    monkeypatch.setattr(
        wb,
        "_launch_case_fetcher",
        lambda cards, summarizer, cases, reports_dir: launch_calls.append(cards),
    )

    button_calls: list[object] = []
    monkeypatch.setattr(
        st,
        "button",
        lambda *a, **k: (button_calls.append((a, k)), False)[1],  # noqa: ARG005
    )

    wb._render_needs_review(_needs_review_holdings(), "data/reports/sample")

    assert len(launch_calls) == 1
    assert [t for t, _h in launch_calls[0]] == ["AAA", "BBB"]
    assert button_calls == []  # no Fetch/Refresh button rendered


def test_needs_review_progress_bar_reflects_done_total(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Progress bar must show done/total while the fetch is in flight."""
    import streamlit as st

    from adapters.visualization.tabs import weekly_brief as wb

    monkeypatch.setattr(st, "session_state", {}, raising=False)
    st.session_state[wb._HOME_CASES_KEY] = {"AAA": object()}  # 1 of 2 done
    st.session_state[wb._HOME_FETCH_STARTED_KEY] = True
    st.session_state[wb._HOME_FETCH_LANDED_KEY] = False

    cards = [(h["ticker"], h) for h in _needs_review_holdings()]

    progress_calls: list[tuple[object, object]] = []
    monkeypatch.setattr(
        st, "progress", lambda frac, **k: progress_calls.append((frac, k))
    )

    wb._render_needs_review_status(cards)

    assert len(progress_calls) == 1
    frac, kwargs = progress_calls[0]
    assert frac == 0.5
    assert "1 / 2" in kwargs.get("text", "")


def test_needs_review_completion_reruns_exactly_once_then_shows_success(  # type: ignore[no-untyped-def]
    monkeypatch,
) -> None:
    """On completion, exactly one full rerun fires (guarded by a one-shot
    flag) before the success state renders — it must not re-fire every tick."""
    import streamlit as st

    from adapters.visualization.tabs import weekly_brief as wb

    monkeypatch.setattr(st, "session_state", {}, raising=False)
    cards = [(h["ticker"], h) for h in _needs_review_holdings()]
    st.session_state[wb._HOME_CASES_KEY] = {"AAA": object(), "BBB": object()}
    st.session_state[wb._HOME_FETCH_STARTED_KEY] = True
    st.session_state[wb._HOME_FETCH_LANDED_KEY] = False

    rerun_calls: list[None] = []
    monkeypatch.setattr(st, "rerun", lambda: rerun_calls.append(None))
    success_calls: list[str] = []
    monkeypatch.setattr(
        st, "success", lambda msg, **k: success_calls.append(msg)  # noqa: ARG005
    )
    monkeypatch.setattr(st, "progress", lambda *a, **k: None)  # noqa: ARG005

    # First call after completion: fires the one-shot rerun, no success yet.
    wb._render_needs_review_status(cards)
    assert len(rerun_calls) == 1
    assert success_calls == []

    # Second call (post-rerun): already landed — shows success, no second rerun.
    wb._render_needs_review_status(cards)
    assert len(rerun_calls) == 1
    assert success_calls == ["Evidence ready for 2 holdings."]


def test_needs_review_never_renders_fetch_or_refresh_button(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """No Fetch/Refresh button in any state — before, during, or after fetch."""
    import streamlit as st

    from adapters.visualization.tabs import weekly_brief as wb

    monkeypatch.setattr(st, "session_state", {}, raising=False)
    monkeypatch.setattr(wb, "select_case_summarizer", lambda: object())
    monkeypatch.setattr(
        wb, "_launch_case_fetcher", lambda *a, **k: None
    )  # noqa: ARG005
    monkeypatch.setattr(st, "progress", lambda *a, **k: None)  # noqa: ARG005
    monkeypatch.setattr(st, "success", lambda *a, **k: None)  # noqa: ARG005
    monkeypatch.setattr(st, "rerun", lambda: None)
    monkeypatch.setattr(st, "markdown", lambda *a, **k: None)  # noqa: ARG005
    monkeypatch.setattr(
        wb, "_render_one_holding_fragment", lambda *a, **k: None
    )  # noqa: ARG005

    button_calls: list[object] = []
    monkeypatch.setattr(
        st,
        "button",
        lambda *a, **k: (button_calls.append((a, k)), False)[1],  # noqa: ARG005
    )

    holdings = _needs_review_holdings()
    wb._render_needs_review(holdings, "data/reports/sample")  # not started
    st.session_state[wb._HOME_CASES_KEY] = {"AAA": object()}  # in flight
    wb._render_needs_review(holdings, "data/reports/sample")
    st.session_state[wb._HOME_CASES_KEY] = {"AAA": object(), "BBB": object()}  # done
    wb._render_needs_review(holdings, "data/reports/sample")

    assert button_calls == []


def _fake_evidence_card(ticker: str):  # type: ignore[no-untyped-def]
    from application.evidence_card import EvidenceCard
    from domain.evidence_rag import RagColor, RagSignal

    return EvidenceCard(
        ticker=ticker,
        signals=(RagSignal("Technicals", RagColor.GREEN, "ok"),),
        sparkline=(),
    )


def test_needs_review_row_has_no_separate_expander_label(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """The old 'TICKER — VERDICT (expand for full evidence)' st.expander label
    must be gone — the row itself is now the only click target, so
    st.expander must never be called for the Needs Review row."""
    from unittest.mock import patch

    import streamlit as st

    from adapters.visualization.tabs import weekly_brief as wb

    st.session_state.clear()
    monkeypatch.setattr(wb, "fetch_card", lambda ticker: _fake_evidence_card(ticker))
    monkeypatch.setattr(
        wb, "fetch_price_history", lambda ticker: {"closes": []}, raising=False
    )

    h = {"ticker": "AAPL", "verdict": "TRIM", "unrealized_pct": 18.4, "why": "test"}
    with patch.object(st, "expander") as mock_expander:
        wb._render_one_holding("AAPL", h, summarizer=object(), cached_case=None)

    mock_expander.assert_not_called()


def test_needs_review_row_expands_in_place_when_toggled(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Setting the row's session_state toggle True must render its evidence
    detail on the same pass, without a second click."""
    import streamlit as st

    from adapters.visualization.tabs import weekly_brief as wb

    st.session_state.clear()
    st.session_state["nr_open_AAPL"] = True
    monkeypatch.setattr(wb, "fetch_card", lambda ticker: _fake_evidence_card(ticker))
    monkeypatch.setattr(
        wb, "fetch_price_history", lambda ticker: {"closes": []}, raising=False
    )

    seen: list[str] = []
    orig_markdown = st.markdown

    def _capture(body, *a, **k):  # type: ignore[no-untyped-def]
        if isinstance(body, str):
            seen.append(body)
        return orig_markdown(body, *a, **k)

    monkeypatch.setattr(st, "markdown", _capture)
    h = {"ticker": "AAPL", "verdict": "TRIM", "unrealized_pct": 18.4, "why": "test"}
    wb._render_one_holding("AAPL", h, summarizer=object(), cached_case=None)

    assert any("dc-case" in s or "Evidence detail" in s for s in seen)


def test_needs_review_row_closed_by_default_hides_detail(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """With no nr_open_<TICKER> toggle set in session_state, the row must
    render collapsed — the expanded evidence detail must NOT appear on the
    first render. Negative-case counterpart to
    test_needs_review_row_expands_in_place_when_toggled."""
    import streamlit as st

    from adapters.visualization.tabs import weekly_brief as wb

    st.session_state.clear()
    monkeypatch.setattr(wb, "fetch_card", lambda ticker: _fake_evidence_card(ticker))
    monkeypatch.setattr(
        wb, "fetch_price_history", lambda ticker: {"closes": []}, raising=False
    )

    seen: list[str] = []
    orig_markdown = st.markdown

    def _capture(body, *a, **k):  # type: ignore[no-untyped-def]
        if isinstance(body, str):
            seen.append(body)
        return orig_markdown(body, *a, **k)

    monkeypatch.setattr(st, "markdown", _capture)
    h = {"ticker": "AAPL", "verdict": "TRIM", "unrealized_pct": 18.4, "why": "test"}
    wb._render_one_holding("AAPL", h, summarizer=object(), cached_case=None)

    assert not any("dc-case" in s or "Evidence detail" in s for s in seen)
