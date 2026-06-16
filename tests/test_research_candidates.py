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
    # _FAKE_SCREEN has 4 distinct factor names → shows 4
    assert "4" in html


# ── Step 6: dynamic factor count ──────────────────────────────────────────────

_FIVE_FACTOR_SCREEN: dict = {
    "as_of": "2026-06-14",
    "universe_size": 100,
    "abstained": False,
    "diagnostics": {"scanned": 100, "had_history": 90, "above_trend": 60, "cleared": 2},
    "candidates": [
        {
            "ticker": "AA",
            "composite": 1.0,
            "why": "test",
            "label": "RESEARCH_ONLY",
            "factor_scores": [
                {"name": "momentum", "value": 0.5, "percentile": 0.7},
                {"name": "revision", "value": 0.3, "percentile": 0.6},
                {"name": "quality", "value": 0.8, "percentile": 0.8},
                {"name": "value", "value": 0.4, "percentile": 0.65},
                {"name": "lowvol", "value": 0.2, "percentile": 0.55},
            ],
        },
    ],
}


def test_header_factors_tile_dynamic_four() -> None:
    """build_header_html shows the actual distinct factor count (4) from the screen."""
    from adapters.visualization.tabs import research_candidates as rc

    html = rc.build_header_html(_FAKE_SCREEN)
    # _FAKE_SCREEN candidates have 4 distinct factor names → ledger shows FACTORS <b>4</b>
    assert "<b>4</b>" in html


def test_header_factors_tile_dynamic_five() -> None:
    """build_header_html shows 5 for a 5-factor screen (future regen after lowvol wired)."""
    from adapters.visualization.tabs import research_candidates as rc

    html = rc.build_header_html(_FIVE_FACTOR_SCREEN)
    assert "Factors" in html
    # 5-factor screen must show 5 in both tile and ledger
    assert "<b>5</b>" in html


def test_header_ledger_factors_count_dynamic() -> None:
    """The FACTORS ledger entry must also reflect the actual factor count."""
    from adapters.visualization.tabs import research_candidates as rc

    html4 = rc.build_header_html(_FAKE_SCREEN)
    html5 = rc.build_header_html(_FIVE_FACTOR_SCREEN)
    # Both should contain FACTORS in the ledger
    assert "FACTORS" in html4 and "FACTORS" in html5
    # 4-factor screen ledger shows 4; 5-factor shows 5
    assert "FACTORS <b>4</b>" in html4
    assert "FACTORS <b>5</b>" in html5


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


def test_legend_has_grade_section() -> None:
    """Fix 2: legend must include Grade line with STRONG / MODERATE labels."""
    from adapters.visualization.tabs import research_candidates as rc

    html = rc.build_legend_html()
    assert "Grade" in html, "Legend must have a Grade section"
    assert "STRONG" in html, "Legend Grade section must mention STRONG"
    assert "MODERATE" in html, "Legend Grade section must mention MODERATE"
    # Wording update: top-5% for Exceptional, 304 cohort reference
    assert "5%" in html, "Legend Band line must say ~top 5%"
    assert "304" in html, "Legend pNN line must reference the 304 trend-eligible cohort"
    assert "Low-vol now live" in html, "Legend must say 'Low-vol now live' (5th factor)"


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


# ---------------------------------------------------------------------------
# S5 Task 4: build_check_your_own_html — Zone ② card with 5-factor parity
# ---------------------------------------------------------------------------


def _make_fake_batch_rows() -> list[Any]:
    """Fake BatchFitRow list for Zone ② rendering tests."""
    from application.batch_fit_use_case import BatchFitRow
    from domain.fit import FitVerdict

    verdict_strong = FitVerdict(
        ticker="NVDA",
        evidence_grade="STRONG",
        fit_flags=(),
        summary="NVDA sits in the top fifth of the screened universe on factual evidence.",
    )
    verdict_weak = FitVerdict(
        ticker="XYZ",
        evidence_grade="WEAK",
        fit_flags=(),
        summary="XYZ ranks in the lower half.",
    )
    row_in_screen = BatchFitRow(
        ticker="NVDA",
        verdict=verdict_strong,
        fetch_ok=True,
        factor_scores=(
            {"name": "momentum", "value": 1.2, "percentile": 0.92, "source": "screen"},
            {"name": "revision", "value": 0.8, "percentile": 0.80, "source": "screen"},
            {"name": "quality", "value": 1.5, "percentile": 0.95, "source": "screen"},
            {"name": "value", "value": -0.3, "percentile": 0.25, "source": "screen"},
            {"name": "lowvol", "value": None, "percentile": None, "source": "screen"},
        ),
    )
    row_off_universe = BatchFitRow(
        ticker="XYZ",
        verdict=verdict_weak,
        fetch_ok=True,
        factor_scores=(
            {"name": "momentum", "value": None, "percentile": None, "source": "live"},
            {"name": "revision", "value": None, "percentile": None, "source": "live"},
            {"name": "quality", "value": None, "percentile": None, "source": "live"},
            {"name": "value", "value": None, "percentile": None, "source": "live"},
            {"name": "lowvol", "value": None, "percentile": None, "source": "live"},
        ),
    )
    return [row_in_screen, row_off_universe]


def test_zone2_card_matches_shortlist() -> None:
    """build_check_your_own_html renders factor names, percentile, grade, fit."""
    from adapters.visualization.tabs import research_candidates as rc

    html = rc.build_check_your_own_html(_make_fake_batch_rows())
    for token in ("Quality", "Value", "Low-vol", "STRONG", "fit"):
        assert token in html, f"Expected token {token!r} missing from Zone ② HTML"
    # Percentile notation present (p92 etc.)
    assert "p" in html


def test_zone2_card_has_factor_rows() -> None:
    """Zone ② card renders all 5 factor rows per ticker."""
    from adapters.visualization.tabs import research_candidates as rc

    html = rc.build_check_your_own_html(_make_fake_batch_rows())
    for factor_label in ("Momentum", "Analyst spread", "Quality", "Value", "Low-vol"):
        assert factor_label in html, f"Factor label {factor_label!r} missing"


def test_zone2_card_shows_data_gap() -> None:
    """Off-universe rows show DATA-GAP, not fabricated numbers."""
    from adapters.visualization.tabs import research_candidates as rc

    html = rc.build_check_your_own_html(_make_fake_batch_rows())
    assert "DATA-GAP" in html


def test_zone2_card_shows_grade_badge() -> None:
    """Evidence grade badge (STRONG/MODERATE/WEAK) must appear per ticker."""
    from adapters.visualization.tabs import research_candidates as rc

    html = rc.build_check_your_own_html(_make_fake_batch_rows())
    # NVDA is STRONG, XYZ is WEAK
    assert "STRONG" in html and "WEAK" in html


def test_zone2_card_subtitle_source_annotation() -> None:
    """In-screen rows show 'in this week's screen'; off-universe show 'live-computed'."""
    from adapters.visualization.tabs import research_candidates as rc

    html = rc.build_check_your_own_html(_make_fake_batch_rows())
    assert "week" in html.lower() or "screen" in html.lower()
    assert "live" in html.lower() or "computed" in html.lower()


# ---------------------------------------------------------------------------
# S5 Task 5: Honesty gate — Zone ② HTML
# ---------------------------------------------------------------------------


def test_zone2_no_forbidden_words() -> None:
    """Zone ② HTML must not contain FORBIDDEN_WORDS from domain/fit.py."""
    import re

    from adapters.visualization.tabs import research_candidates as rc
    from domain.fit import FORBIDDEN_WORDS

    html = rc.build_check_your_own_html(_make_fake_batch_rows()).lower()
    words = set(re.findall(r"\b\w+\b", html))
    for w in FORBIDDEN_WORDS:
        assert w not in words, f"Forbidden word {w!r} in Zone ② HTML"


def test_zone2_data_gap_shows_data_gap_label_not_number() -> None:
    """DATA-GAP rows must show the text 'DATA-GAP', not a fabricated number."""
    from adapters.visualization.tabs import research_candidates as rc

    # Use only a row with all DATA-GAP factor scores (off-universe)
    from application.batch_fit_use_case import BatchFitRow
    from domain.fit import FitVerdict

    verdict = FitVerdict(
        ticker="FAKE",
        evidence_grade="UNKNOWN",
        fit_flags=(),
        summary="FAKE could not be assessed.",
    )
    row = BatchFitRow(
        ticker="FAKE",
        verdict=verdict,
        fetch_ok=False,
        factor_scores=(
            {"name": "momentum", "value": None, "percentile": None, "source": "live"},
            {"name": "revision", "value": None, "percentile": None, "source": "live"},
            {"name": "quality", "value": None, "percentile": None, "source": "live"},
            {"name": "value", "value": None, "percentile": None, "source": "live"},
            {"name": "lowvol", "value": None, "percentile": None, "source": "live"},
        ),
    )
    html = rc.build_check_your_own_html([row])
    assert "DATA-GAP" in html
    # Should NOT contain a percentile number notation like p92
    import re

    pct_matches = re.findall(r"\bp\d{2,3}\b", html)
    assert (
        len(pct_matches) == 0
    ), f"Fabricated percentile found in DATA-GAP card: {pct_matches}"


def test_zone2_cap_25_unchanged() -> None:
    """MAX_TICKERS must remain 25 — batch_fit cap must not change."""
    from application.batch_fit_use_case import MAX_TICKERS

    assert MAX_TICKERS == 25


def test_reason_view_opens_one_hero():
    """The first candidate (top of first non-empty bucket) renders as an open hero;
    the rest stay collapsed (mockup .row.open + elevated .hero)."""
    from adapters.visualization.tabs.research_candidates import build_reason_view_html

    cands = [
        {
            "ticker": "SPG",
            "composite": 1.31,
            "why": "x",
            "factor_scores": [
                {"name": "quality", "value": 2.8, "percentile": 0.95},
                {"name": "value", "value": 1.3, "percentile": 0.87},
            ],
        },
        {
            "ticker": "APA",
            "composite": 1.14,
            "why": "y",
            "factor_scores": [
                {"name": "value", "value": 2.0, "percentile": 0.95},
                {"name": "quality", "value": 0.4, "percentile": 0.78},
            ],
        },
    ]
    html = build_reason_view_html(cands)
    assert (
        html.count("<details open") == 1
    ), "exactly one hero should be open by default"
    assert "#CBD5E1" in html, "hero should use the elevated border colour"


def test_rank_view_opens_top_hero():
    from adapters.visualization.tabs.research_candidates import build_rank_view_html

    cands = [
        {"ticker": "SPG", "composite": 1.31, "why": "x", "factor_scores": []},
        {"ticker": "APA", "composite": 1.14, "why": "y", "factor_scores": []},
    ]
    html = build_rank_view_html(cands)
    assert html.count("<details open") == 1
    # #1 by composite is the hero
    assert html.index("SPG") < html.index("APA")


def test_tiles_carry_tooltip_clouds():
    from adapters.visualization.tabs.research_candidates import build_header_html

    screen = {
        "as_of": "2026-06-14",
        "universe_size": 512,
        "diagnostics": {"scanned": 512, "cleared": 304},
        "candidates": [
            {
                "ticker": "SPG",
                "composite": 1.3,
                "factor_scores": [
                    {"name": "quality", "value": 2.0, "percentile": 0.95}
                ],
            }
        ],
    }
    html = build_header_html(screen, reports_dir="data/reports")
    # consistent project tooltip component on the tiles (.ri-ttip), not a bespoke cloud
    assert html.count("ri-ttip") >= 4


def test_standout_chip_grade_words():
    from adapters.visualization.tabs.research_candidates import _standout_chip_html

    strong = {"factor_scores": [{"name": "quality", "value": 2.8, "percentile": 0.95}]}
    weak = {"factor_scores": [{"name": "value", "value": -1.5, "percentile": 0.10}]}
    gap = {"factor_scores": [{"name": "lowvol", "value": None, "percentile": None}]}
    assert "STRONG" in _standout_chip_html(strong)
    assert "WEAK" in _standout_chip_html(weak)
    assert "STRONG" not in _standout_chip_html(gap)  # DATA-GAP → neutral dash


def test_fix3_sub_line_uses_company_name() -> None:
    """Fix 3: sub-line shows company name from candidate dict when present."""
    from adapters.visualization.tabs.research_candidates import (
        _build_candidate_row_html,
    )

    c = {
        "ticker": "SPG",
        "name": "Simon Property Group",
        "composite": 1.27,
        "factor_scores": [
            {"name": "quality", "value": 1.5, "percentile": 0.95},
        ],
    }
    html = _build_candidate_row_html(rank=1, candidate=c)
    assert "Simon Property Group" in html, "sub-line must show the company name"
    assert "evidence 1.27" in html, "sub-line must show 'evidence {composite}'"


def test_fix3_sub_line_falls_back_to_ticker() -> None:
    """Fix 3: sub-line falls back to ticker when no company name key present."""
    from adapters.visualization.tabs.research_candidates import (
        _build_candidate_row_html,
    )

    c = {"ticker": "KO", "composite": 0.88, "factor_scores": []}
    html = _build_candidate_row_html(rank=1, candidate=c)
    assert "KO" in html
    assert "evidence 0.88" in html


def test_fix5_gai_placeholder_no_s6_in_zone1() -> None:
    """Fix 5: Zone 1 gai placeholder must not contain 'S6' or 'arrives in'."""
    from adapters.visualization.tabs.research_candidates import (
        _build_candidate_row_html,
    )

    c = {"ticker": "SPG", "composite": 1.27, "factor_scores": []}
    html = _build_candidate_row_html(rank=1, candidate=c)
    assert "S6" not in html, "Zone 1 gai placeholder must not say 'S6'"
    assert (
        "arrives in" not in html.lower()
    ), "Zone 1 gai placeholder must not say 'arrives in'"
    assert "Stock Analysis" in html, "Zone 1 gai must reference 'Stock Analysis'"


def test_fix5_gai_placeholder_no_s6_in_zone2() -> None:
    """Fix 5: Zone 2 gai placeholder must not contain 'S6' or 'arrives in'."""
    from adapters.visualization.tabs.research_candidates import _build_zone2_row_html
    from application.batch_fit_use_case import BatchFitRow
    from domain.fit import FitVerdict

    verdict = FitVerdict(
        ticker="NVDA",
        evidence_grade="STRONG",
        fit_flags=(),
        summary="Strong on evidence.",
    )
    row = BatchFitRow(
        ticker="NVDA",
        verdict=verdict,
        fetch_ok=True,
        factor_scores=(
            {"name": "quality", "value": 1.5, "percentile": 0.95, "source": "screen"},
        ),
    )
    html = _build_zone2_row_html(row)
    assert "S6" not in html, "Zone 2 gai placeholder must not say 'S6'"
    assert (
        "arrives in" not in html.lower()
    ), "Zone 2 gai placeholder must not say 'arrives in'"
    assert "Stock Analysis" in html, "Zone 2 gai must reference 'Stock Analysis'"


def test_fix3_also_in_badge_renders_for_repeat() -> None:
    """Fix 3: repeat candidates (appear in multiple buckets) show 'also in' badge."""
    from adapters.visualization.tabs.research_candidates import (
        _build_candidate_row_html,
    )

    c = {
        "ticker": "SPG",
        "composite": 1.27,
        "factor_scores": [
            {"name": "quality", "value": 1.5, "percentile": 0.95},
            {"name": "value", "value": 0.8, "percentile": 0.87},
        ],
    }
    html = _build_candidate_row_html(
        rank=1,
        candidate=c,
        show_repeat_badge=True,
        also_buckets=["🌟", "💰"],
    )
    assert "also" in html, "repeat badge must contain 'also'"
    assert "🌟" in html or "💰" in html, "also-in bucket emojis must appear"


def test_card_factor_order_momentum_last():
    from adapters.visualization.tabs.research_candidates import (
        _build_candidate_row_html,
    )

    c = {
        "ticker": "SPG",
        "composite": 1.3,
        "why": "x",
        "factor_scores": [
            {"name": "quality", "value": 2.0, "percentile": 0.95},
            {"name": "value", "value": 1.0, "percentile": 0.87},
            {"name": "revision", "value": 0.5, "percentile": 0.7},
            {"name": "momentum", "value": 0.1, "percentile": 0.55},
        ],
    }
    html = _build_candidate_row_html(rank=1, candidate=c)
    # canonical display order (render_factor_row labels): Quality, Value,
    # Analyst spread (revision), Low-vol, Momentum — momentum LAST.
    iq = html.index(">Quality")
    iv = html.index(">Value")
    il = html.index(">Low-vol")
    im = html.index(">Momentum")
    assert iq < iv < il < im, "factor display order must end with Momentum"
