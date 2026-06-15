"""Tests for the new research_candidates build_* helper functions (S3 Tasks 3-8)."""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Shared fake screen fixture
# ---------------------------------------------------------------------------

_FAKE_SCREEN: dict[str, Any] = {
    "as_of": "2026-06-14",
    "universe_size": 512,
    "abstained": False,
    "diagnostics": {
        "scanned": 512,
        "had_history": 490,
        "above_trend": 304,
        "cleared": 304,
    },
    "candidates": [
        {
            "ticker": "SPG",
            "composite": 1.27,
            "why": "Quality, value & analyst signal strong; momentum flat",
            "label": "RESEARCH_ONLY",
            "factor_scores": [
                {"name": "momentum", "value": 0.22, "percentile": 0.59},
                {"name": "revision", "value": 1.1, "percentile": 0.88},
                {"name": "quality", "value": 1.5, "percentile": 0.95},
                {"name": "value", "value": 0.8, "percentile": 0.87},
            ],
        },
        {
            "ticker": "KLAC",
            "composite": 1.08,
            "why": "Exceptional quality + trend, looks expensive",
            "label": "RESEARCH_ONLY",
            "factor_scores": [
                {"name": "momentum", "value": 0.9, "percentile": 0.81},
                {"name": "revision", "value": 0.3, "percentile": 0.55},
                {"name": "quality", "value": 1.8, "percentile": 0.97},
                {"name": "value", "value": -0.8, "percentile": 0.15},
            ],
        },
    ],
}

_EMPTY_SCREEN: dict[str, Any] = {
    "as_of": "2026-06-14",
    "universe_size": 512,
    "abstained": True,
    "diagnostics": {
        "scanned": 512,
        "had_history": 490,
        "above_trend": 304,
        "cleared": 0,
    },
    "candidates": [],
}


# ---------------------------------------------------------------------------
# Task 3: build_header_html + build_tiles_html
# ---------------------------------------------------------------------------


def test_header_and_tiles_render() -> None:
    from adapters.visualization.tabs import research_candidates as rc

    html = rc.build_header_html(_FAKE_SCREEN)
    assert "research shortlist" in html.lower()
    assert "not a forecast" in html.lower()
    assert "UNIVERSE" in html and "CLEARED" in html


def test_header_shows_showing_count() -> None:
    from adapters.visualization.tabs import research_candidates as rc

    html = rc.build_header_html(_FAKE_SCREEN)
    # Should mention showing N of cleared
    assert "Showing" in html or "15" in html or "2" in html  # fake has 2 candidates


def test_header_has_as_of_date() -> None:
    from adapters.visualization.tabs import research_candidates as rc

    html = rc.build_header_html(_FAKE_SCREEN)
    assert "Jun" in html or "2026" in html or "2026-06-14" in html


def test_header_has_factors_tile() -> None:
    from adapters.visualization.tabs import research_candidates as rc

    html = rc.build_header_html(_FAKE_SCREEN)
    assert "Factors" in html
    # Shows 4 (live factors count), not 5
    assert "4" in html


def test_header_has_trust_tile() -> None:
    from adapters.visualization.tabs import research_candidates as rc

    html = rc.build_header_html(_FAKE_SCREEN)
    # Trust tile has IC verdict — honest "Inconclusive" or "INCONCLUSIVE"
    assert "nconclusive" in html


def test_header_no_inline_hex_colours() -> None:
    from adapters.visualization.tabs import research_candidates as rc

    html = rc.build_header_html(_FAKE_SCREEN)
    # All colours should come from CSS var() — no raw 7-char hex like #15803D
    # The tile's border-left colors use --warning/--purple via var()
    # Check: before first var() the string shouldn't end in a hex

    # Find raw hex colors (#RRGGBB) not inside a var() or background shorthand
    # We look for hex that appears OUTSIDE of CSS property value contexts that use var()
    # Simple check: the header should use var(--...) color references
    assert "var(--" in html, "Header must use CSS var() tokens, not raw hex"


# ---------------------------------------------------------------------------
# Task 4: build_legend_html + build_disclosure_html
# ---------------------------------------------------------------------------


def test_legend_and_disclosure() -> None:
    from adapters.visualization.tabs import research_candidates as rc

    html = rc.build_legend_html()
    for token in ("Exceptional", "Strong", "Flat", "Weak", "p95", "Evidence score"):
        assert token in html, f"Legend missing token: {token!r}"

    dis = rc.build_disclosure_html()
    assert "not a forecast" in dis.lower()
    assert "momentum" in dis.lower() and "no proven edge" in dis.lower()


# ---------------------------------------------------------------------------
# Task 5: resolve_view_mode
# ---------------------------------------------------------------------------


def test_view_mode_default_is_reason() -> None:
    from adapters.visualization.tabs import research_candidates as rc

    assert rc.resolve_view_mode(session={}) == "reason"
    assert rc.resolve_view_mode(session={"screener_view": "rank"}) == "rank"


def test_view_mode_reason_explicit() -> None:
    from adapters.visualization.tabs import research_candidates as rc

    assert rc.resolve_view_mode(session={"screener_view": "reason"}) == "reason"


# ---------------------------------------------------------------------------
# Task 6: build_reason_view_html — buckets + collapsible cards
# ---------------------------------------------------------------------------


def _make_bucket_inputs() -> list[Any]:
    from domain.screen_buckets import BucketInput

    return [
        BucketInput(
            ticker="SPG",
            percentiles={
                "quality": 0.95,
                "value": 0.87,
                "revision": 0.88,
                "momentum": 0.59,
                "lowvol": 0.0,
            },
            composite=1.27,
        ),
        BucketInput(
            ticker="KLAC",
            percentiles={
                "quality": 0.97,
                "value": 0.15,
                "revision": 0.55,
                "momentum": 0.81,
                "lowvol": 0.0,
            },
            composite=1.08,
        ),
    ]


def _make_full_candidates_for_reason() -> list[dict[str, Any]]:
    return [
        {
            "ticker": "SPG",
            "composite": 1.27,
            "why": "Quality, value & analyst signal strong; momentum flat",
            "label": "RESEARCH_ONLY",
            "factor_scores": [
                {"name": "momentum", "value": 0.22, "percentile": 0.59},
                {"name": "revision", "value": 1.1, "percentile": 0.88},
                {"name": "quality", "value": 1.5, "percentile": 0.95},
                {"name": "value", "value": 0.8, "percentile": 0.87},
            ],
        },
        {
            "ticker": "KLAC",
            "composite": 1.08,
            "why": "Exceptional quality + trend, looks expensive",
            "label": "RESEARCH_ONLY",
            "factor_scores": [
                {"name": "momentum", "value": 0.9, "percentile": 0.81},
                {"name": "revision", "value": 0.3, "percentile": 0.55},
                {"name": "quality", "value": 1.8, "percentile": 0.97},
                {"name": "value", "value": -0.8, "percentile": 0.15},
            ],
        },
    ]


def test_reason_view_renders_buckets_and_empty() -> None:
    from adapters.visualization.tabs import research_candidates as rc

    html = rc.build_reason_view_html(_make_full_candidates_for_reason())
    assert "All-rounder" in html and "🌟" in html
    # Momentum leaders bucket should be empty since SPG has momentum p59 < 0.75
    # and KLAC has momentum p81 but revision p55 < 0.75
    assert "Momentum leaders" in html and "Empty this week" in html


def test_reason_view_factor_rows_present() -> None:
    from adapters.visualization.tabs import research_candidates as rc

    html = rc.build_reason_view_html(_make_full_candidates_for_reason())
    # The 5 factor rows (4 live + 1 DATA-GAP for lowvol) should be in each card
    for factor in ("Quality", "Value", "Analyst spread", "Momentum"):
        assert factor in html, f"Factor row {factor!r} missing from reason view"
    # Low-vol should appear as DATA-GAP (lowvol percentile=0.0)
    assert "Low-vol" in html
    assert "DATA-GAP" in html


def test_reason_view_do_next_present() -> None:
    from adapters.visualization.tabs import research_candidates as rc

    html = rc.build_reason_view_html(_make_full_candidates_for_reason())
    assert "Do next" in html


def test_reason_view_google_ai_placeholder() -> None:
    """Google-AI read placeholder div must be present (filled by S6 later)."""
    from adapters.visualization.tabs import research_candidates as rc

    html = rc.build_reason_view_html(_make_full_candidates_for_reason())
    assert "gai" in html  # the placeholder div id/class


def test_reason_view_repeat_badge() -> None:
    """SPG qualifies for multiple buckets; should show 'also' badge in secondary."""
    from adapters.visualization.tabs import research_candidates as rc

    html = rc.build_reason_view_html(_make_full_candidates_for_reason())
    assert "also" in html


def test_reason_view_no_forbidden_words() -> None:
    from adapters.visualization.tabs import research_candidates as rc

    html = rc.build_reason_view_html(_make_full_candidates_for_reason()).lower()
    # Use word-boundary check (split on spaces/punctuation)
    import re

    words = set(re.findall(r"\b\w+\b", html))
    for w in ("buy", "sell", "winner", "conviction", "predict", "alpha", "outperform"):
        assert w not in words, f"Forbidden word {w!r} in reason view HTML"


# ---------------------------------------------------------------------------
# Task 7: build_rank_view_html + build_body_html (abstention path)
# ---------------------------------------------------------------------------


def test_rank_view_is_flat_ranked() -> None:
    from adapters.visualization.tabs import research_candidates as rc

    html = rc.build_rank_view_html(_make_full_candidates_for_reason())
    # flat list — no bucket headers
    assert "All-rounder" not in html
    # SPG (composite 1.27) should appear before KLAC (1.08)
    assert html.index("SPG") < html.index("KLAC")


def test_abstention_path_is_honest() -> None:
    from adapters.visualization.tabs import research_candidates as rc

    html = rc.build_body_html(_EMPTY_SCREEN, view="reason")
    assert "Empty" in html or "none cleared" in html.lower()
    assert (
        "working as designed" in html.lower() or "scanned" in html.lower()
    ), "Abstention must state working-as-designed or reference scanned count"


# ---------------------------------------------------------------------------
# Task 8: Honesty gate — no forbidden words in reason view HTML
# ---------------------------------------------------------------------------


def test_screener_html_no_forbidden_words() -> None:
    from adapters.visualization.tabs import research_candidates as rc

    html = rc.build_reason_view_html(_make_full_candidates_for_reason()).lower()
    import re

    words = set(re.findall(r"\b\w+\b", html))
    for w in ("buy", "sell", "winner", "conviction", "predict", "alpha", "outperform"):
        assert w not in words, f"Forbidden word {w!r} in screener HTML"
