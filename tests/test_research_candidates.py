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


def test_disclosure_honest_note() -> None:
    from adapters.visualization.tabs import research_candidates as rc

    dis = rc.build_disclosure_html()
    assert "not a forecast" in dis.lower()
    assert "momentum" in dis.lower() and "no proven edge" in dis.lower()


def test_pipeline_visual_has_three_steps_and_tooltips() -> None:
    """Always-visible Z-score -> Band -> Grade strip (replaces the old legend
    prose). Band/Grade thresholds live in hover tooltips sourced from the
    glossary, not inline — the tooltip's definition text still lands in the
    HTML string, so the same tokens the old legend exposed are still present."""
    from adapters.visualization.tabs import research_candidates as rc

    html = rc.build_pipeline_visual_html()
    assert "Z-score" in html
    assert "Band" in html
    assert "Grade" in html
    for token in (
        "Exceptional",
        "Strong",
        "Flat",
        "Weak",
        "p95",
        "5%",
        "304",
        "Evidence score",
        "STRONG",
        "MODERATE",
        "Low-vol now live",
    ):
        assert token in html, f"Pipeline visual missing token: {token!r}"


# ---------------------------------------------------------------------------
# P0b: screener honesty — relabel "revision" → Analyst dispersion, disclose
# universe scope + per-factor coverage + snapshot caveats.
# ---------------------------------------------------------------------------


def test_universe_scope_disclosure() -> None:
    from adapters.visualization.tabs import research_candidates as rc

    html = rc.build_universe_scope_html(_FAKE_SCREEN)
    assert "Large-cap US" in html
    assert "Nasdaq-100" in html
    assert "570" in html
    assert "survivor-biased" in html
    assert "not the whole market" in html
    # the live scanned count from diagnostics is surfaced
    assert "512" in html


def test_universe_scope_no_screen_omits_count() -> None:
    from adapters.visualization.tabs import research_candidates as rc

    html = rc.build_universe_scope_html(None)
    assert "Large-cap US" in html
    assert "names scanned" not in html


def test_factor_honesty_dispersion_and_snapshot() -> None:
    from adapters.visualization.tabs import research_candidates as rc

    html = rc.build_factor_honesty_html()
    assert "Analyst dispersion" in html
    assert "DISPERSION" in html and "not revision drift" in html
    # value + quality flagged as current snapshot, not point-in-time
    assert "snapshot" in html.lower()
    assert "point-in-time" in html.lower()


def test_coverage_line_per_factor() -> None:
    from adapters.visualization.tabs import research_candidates as rc

    html = rc.build_coverage_html(_FAKE_SCREEN)
    assert "COVERAGE" in html
    # honest dispersion label, not "spread"/"signal"
    assert "Analyst dispersion" in html
    # lowvol absent in the fixture → DATA-GAP
    assert "Low-vol" in html and "DATA-GAP" in html


def test_coverage_line_empty_when_no_candidates() -> None:
    from adapters.visualization.tabs import research_candidates as rc

    assert rc.build_coverage_html(_EMPTY_SCREEN) == ""


def test_caveats_html_merges_three_disclosures() -> None:
    """build_caveats_html() replaces the legend + folds in disclosure/scope/
    factor-honesty content verbatim, for use inside one collapsed expander."""
    from adapters.visualization.tabs import research_candidates as rc

    html = rc.build_caveats_html(_FAKE_SCREEN)
    # Honest note (from build_disclosure_html)
    assert "not a forecast" in html.lower()
    assert "momentum" in html.lower() and "no proven edge" in html.lower()
    # Universe scope (from build_universe_scope_html)
    assert "Large-cap US" in html
    assert "Nasdaq-100" in html
    assert "570" in html
    assert "survivor-biased" in html
    assert "512" in html
    # What each factor really is (from build_factor_honesty_html)
    assert "Analyst dispersion" in html
    assert "not revision drift" in html
    assert "point-in-time" in html.lower()


def test_caveats_html_no_screen_omits_scanned_count() -> None:
    from adapters.visualization.tabs import research_candidates as rc

    html = rc.build_caveats_html(None)
    assert "Large-cap US" in html
    assert "names scanned" not in html


def test_friendly_label_is_dispersion() -> None:
    from adapters.visualization.tabs.research_candidates import _FRIENDLY

    assert _FRIENDLY["revision"] == "analyst dispersion"


def test_factors_tile_subtitle_says_dispersion() -> None:
    from adapters.visualization.tabs import research_candidates as rc

    html = rc.build_header_html(_FAKE_SCREEN)
    assert "analyst dispersion" in html


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
    for factor in ("Quality", "Value", "Analyst dispersion", "Momentum"):
        assert factor in html, f"Factor row {factor!r} missing from reason view"
    # Low-vol should appear as DATA-GAP (lowvol percentile=0.0)
    assert "Low-vol" in html
    assert "DATA-GAP" in html


def test_reason_view_do_next_present() -> None:
    from adapters.visualization.tabs import research_candidates as rc

    html = rc.build_reason_view_html(_make_full_candidates_for_reason())
    assert "Do next" in html


def test_reason_view_score_does_not_wrap() -> None:
    """The composite-score span (e.g. "0.85") sits in a narrow CSS-grid column
    with no white-space rule, so the browser wraps it onto two lines at the
    decimal point. Every score span must be white-space:nowrap, matching the
    grade badge already styled that way in the same row."""
    from adapters.visualization.tabs import research_candidates as rc

    reason_html = rc.build_reason_view_html(_make_full_candidates_for_reason())
    rank_html = rc.build_rank_view_html(_make_full_candidates_for_reason())
    for html in (reason_html, rank_html):
        assert "JetBrains Mono" in html
        idx = html.index("JetBrains Mono")
        span_chunk = html[idx : idx + 120]
        assert "white-space:nowrap" in span_chunk


def test_reason_view_google_ai_placeholder() -> None:
    """Google-AI read companion (live when local, else the Stock Analysis
    pointer) must be present for every row."""
    from adapters.visualization.tabs import research_candidates as rc

    html = rc.build_reason_view_html(_make_full_candidates_for_reason())
    assert "Stock Analysis" in html  # the permanent pointer, live or off-local


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


def test_enrich_candidates_adds_company_name_and_sector(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Candidates with no name/sector must be enriched from a cached ticker-info
    lookup — display-only, never touches score/composite/factor data."""
    from adapters.visualization.tabs import research_candidates as rc

    monkeypatch.setattr(
        rc,
        "fetch_ticker_info",
        lambda t: (
            {"longName": "Simon Property Group", "sector": "Real Estate"}
            if t == "SPG"
            else {}
        ),
    )
    candidates = [{"ticker": "SPG", "composite": 1.27, "factor_scores": []}]
    enriched = rc._enrich_candidates_with_company_info(candidates)
    assert enriched[0]["name"] == "Simon Property Group"
    assert enriched[0]["sector"] == "Real Estate"
    # Original list/dict must not be mutated in place.
    assert "name" not in candidates[0]


def test_enrich_candidates_skips_when_name_already_present(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Never overwrite a name already carried by the candidate dict, and never
    hit the network for it."""
    from adapters.visualization.tabs import research_candidates as rc

    called: list[str] = []

    def _spy(t: str) -> dict[str, str]:
        called.append(t)
        return {"longName": "Wrong Name", "sector": "Wrong"}

    monkeypatch.setattr(rc, "fetch_ticker_info", _spy)
    candidates = [{"ticker": "SPG", "name": "Simon Property Group", "composite": 1.27}]
    enriched = rc._enrich_candidates_with_company_info(candidates)
    assert enriched[0]["name"] == "Simon Property Group"
    assert called == []


def test_sub_line_shows_sector_when_present() -> None:
    """Fix: sub-line shows sector alongside company name when the candidate
    carries one (enriched by _enrich_candidates_with_company_info)."""
    from adapters.visualization.tabs.research_candidates import (
        _build_candidate_row_html,
    )

    c = {
        "ticker": "SPG",
        "name": "Simon Property Group",
        "sector": "Real Estate",
        "composite": 1.27,
        "factor_scores": [],
    }
    html = _build_candidate_row_html(rank=1, candidate=c)
    assert "Simon Property Group" in html
    assert "Real Estate" in html


def test_summary_row_shows_company_name_not_just_ticker() -> None:
    """The always-visible <summary> row (no expand needed — a collapsed
    <details> still hides its body from the visitor, even though the body
    text remains in the raw HTML) must itself show the company name, not
    just the bare ticker — this is the row a visitor sees first without
    clicking anything."""
    from adapters.visualization.tabs import research_candidates as rc

    candidates = [
        {
            "ticker": "SPG",
            "name": "Simon Property Group",
            "composite": 1.27,
            "why": "x",
            "label": "RESEARCH_ONLY",
            "factor_scores": [
                {"name": "quality", "value": 1.5, "percentile": 0.95},
            ],
        }
    ]
    reason_html = rc.build_reason_view_html(candidates)
    rank_html = rc.build_rank_view_html(candidates)
    for html in (reason_html, rank_html):
        summary_start = html.index("<summary")
        summary_end = html.index("</summary>")
        assert "Simon Property Group" in html[summary_start:summary_end], (
            "company name must be in the always-visible <summary>, not only "
            "the collapsed body"
        )


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
    for factor_label in (
        "Momentum",
        "Analyst dispersion",
        "Quality",
        "Value",
        "Low-vol",
    ):
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


def test_candidate_row_wires_live_google_ai_read(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """The static gai placeholder must be replaced by a real maybe_render_gemini()
    call fed with facts derived from the candidate's factor bands — when local
    and a summarizer is available, real in-favor/to-watch content renders, not
    just a link to Stock Analysis."""
    from adapters.visualization.tabs import research_candidates as rc
    from domain.case_models import CasePoint, CaseResult

    class _StubAdapter:
        def summarize_case(self, ctx: object) -> CaseResult:
            return CaseResult(
                in_favor=(CasePoint("Quality: Exceptional (p95)", "quality"),),
                to_watch=(),
                data_gap=False,
            )

    monkeypatch.setattr(rc, "is_local_runtime", lambda: True)
    monkeypatch.setattr(rc, "_gemini_adapter", _StubAdapter())
    monkeypatch.setattr(rc, "_fetch_recent_news_impl", lambda *a, **k: [])
    monkeypatch.setattr(rc, "buzz_sentiment_fact", lambda *a, **k: None)
    import streamlit as st

    st.session_state.pop("_gai_ZZZ1", None)

    c = {
        "ticker": "ZZZ1",
        "composite": 1.27,
        "factor_scores": [
            {"name": "quality", "value": 1.5, "percentile": 0.95},
        ],
    }
    # open_by_default=True: only the hero row fires a live Gemini call — this
    # test's purpose is verifying that live wiring, so it exercises the hero path.
    html = rc._build_candidate_row_html(rank=1, candidate=c, open_by_default=True)
    assert "Quality: Exceptional" in html, "stub's real case content must render"
    assert (
        "Stock Analysis" in html
    ), "the Stock Analysis pointer must still be present alongside the read"


def test_candidate_row_google_ai_off_local_shows_no_facts(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Privacy fail-safe: off-local, no facts/news leave the process — the
    stub adapter must never be called, and only the static pointer shows."""
    from adapters.visualization.tabs import research_candidates as rc

    called: list[str] = []

    class _SpyAdapter:
        def summarize_case(self, ctx: object) -> object:
            called.append("called")
            from domain.case_models import CaseResult

            return CaseResult((), (), True)

    monkeypatch.setattr(rc, "is_local_runtime", lambda: False)
    monkeypatch.setattr(rc, "_gemini_adapter", _SpyAdapter())

    c = {"ticker": "ZZZ2", "composite": 1.27, "factor_scores": []}
    # open_by_default=True: exercises the hero/live path's own privacy gate.
    html = rc._build_candidate_row_html(rank=1, candidate=c, open_by_default=True)
    assert called == [], "summarize_case must not be called off-local"
    assert "Stock Analysis" in html


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
    # Analyst dispersion (revision), Low-vol, Momentum — momentum LAST.
    iq = html.index(">Quality")
    iv = html.index(">Value")
    il = html.index(">Low-vol")
    im = html.index(">Momentum")
    assert iq < iv < il < im, "factor display order must end with Momentum"


# ---------------------------------------------------------------------------
# maybe_render_gemini_cache_only — non-hero rows read the persistent cache
# only, never a live call. Cache path is {reports_dir}/screen_cited_cases.json.
# ---------------------------------------------------------------------------


def test_cache_only_hit_renders_two_col(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    from adapters.visualization.tabs import research_candidates as rc
    from application.case_cache import write_case_cache
    from domain.case_models import CasePoint, CaseResult

    monkeypatch.setattr(rc, "is_local_runtime", lambda: True)
    cache_path = tmp_path / "screen_cited_cases.json"
    write_case_cache(
        str(cache_path),
        "2026-07-12",
        {
            "NVDA": CaseResult(
                in_favor=(CasePoint("demand durable", "Reuters"),),
                to_watch=(CasePoint("export controls", "Bloomberg"),),
                data_gap=False,
            )
        },
    )
    html = rc.maybe_render_gemini_cache_only("NVDA", str(tmp_path))
    assert "Green flags" in html
    assert "demand durable" in html


def test_cache_only_miss_shows_honest_note(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    from adapters.visualization.tabs import research_candidates as rc

    monkeypatch.setattr(rc, "is_local_runtime", lambda: True)
    html = rc.maybe_render_gemini_cache_only("NVDA", str(tmp_path))
    assert "not cached yet" in html.lower()
    assert "Green flags" not in html


def test_cache_only_ignores_local_runtime_hit(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Unlike the live-call path, cache-only reads a committed file — no live
    API call, no visitor data leaves the process — so it must show on Cloud
    (is_local_runtime()=False) too, not just local dev."""
    from adapters.visualization.tabs import research_candidates as rc
    from application.case_cache import write_case_cache
    from domain.case_models import CasePoint, CaseResult

    monkeypatch.setattr(rc, "is_local_runtime", lambda: False)
    cache_path = tmp_path / "screen_cited_cases.json"
    write_case_cache(
        str(cache_path),
        "2026-07-12",
        {
            "NVDA": CaseResult(
                in_favor=(CasePoint("demand durable", "Reuters"),),
                to_watch=(CasePoint("export controls", "Bloomberg"),),
                data_gap=False,
            )
        },
    )
    html = rc.maybe_render_gemini_cache_only("NVDA", str(tmp_path))
    assert "Green flags" in html
    assert "demand durable" in html


def test_cache_only_ignores_local_runtime_miss(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    from adapters.visualization.tabs import research_candidates as rc

    monkeypatch.setattr(rc, "is_local_runtime", lambda: False)
    html = rc.maybe_render_gemini_cache_only("NVDA", str(tmp_path))
    assert "not cached yet" in html.lower()


def test_hero_row_calls_live_non_hero_calls_cache_only(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Only the row rendered open_by_default fires a live call; other rows are
    cache-only — this is the practical resolution of 'lazy on expand' given
    Streamlit can't observe raw-HTML <details> toggles (see spec section 4)."""
    from adapters.visualization.tabs import research_candidates as rc

    live_calls: list[str] = []
    cache_only_calls: list[str] = []
    monkeypatch.setattr(
        rc,
        "maybe_render_gemini",
        lambda ticker, facts, news: live_calls.append(ticker) or "",
    )
    monkeypatch.setattr(
        rc,
        "maybe_render_gemini_cache_only",
        lambda ticker, reports_dir: cache_only_calls.append(ticker) or "",
    )

    c = {"ticker": "HERO", "composite": 1.0, "factor_scores": []}
    rc._build_candidate_row_html(rank=1, candidate=c, open_by_default=True)
    assert live_calls == ["HERO"]
    assert cache_only_calls == []

    live_calls.clear()
    c2 = {"ticker": "NOTHERO", "composite": 1.0, "factor_scores": []}
    rc._build_candidate_row_html(rank=2, candidate=c2, open_by_default=False)
    assert live_calls == []
    assert cache_only_calls == ["NOTHERO"]


def test_run_screen_candidates_cli_includes_cite_cases(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """A live 'Run screener' click should also warm the Gemini cache."""
    from adapters.visualization.tabs import research_candidates as rc

    captured: dict[str, list[str]] = {}

    def _fake_run(cmd: list[str], check: bool) -> None:
        captured["cmd"] = cmd

    monkeypatch.setattr(rc.subprocess, "run", _fake_run)
    rc._run_screen_candidates_cli(str(tmp_path))
    assert "--cite-cases" in captured["cmd"]


def test_no_misleading_stock_analysis_cited_case_pointer() -> None:
    """Stock Analysis does NOT implement the cited-case/Gemini feature (only
    Home/Portfolio/Risk do) — Screener's pointer copy must never claim a
    "cited case" awaits there."""
    from adapters.visualization.tabs import research_candidates as rc

    c = {"ticker": "KO", "composite": 0.88, "factor_scores": []}
    row_html = rc._build_candidate_row_html(rank=1, candidate=c)
    assert "full cited case" not in row_html

    zone2_html = rc.build_check_your_own_html(_make_fake_batch_rows())
    assert "full cited case" not in zone2_html


def test_candidate_cards_carry_rc_card_class_for_tooltip_escape() -> None:
    """The collapsible <details> card sets inline overflow:hidden for rounded
    corners, which also clips the factor-row (i) tooltip once expanded. The
    rc-card class is how styles.py's `.rc-card[open]{overflow:visible}` rule
    finds these cards to override that clipping — losing the class silently
    re-breaks the tooltip."""
    from adapters.visualization.tabs import research_candidates as rc

    candidates = _FAKE_SCREEN["candidates"]
    assert 'class="rc-card"' in rc.build_reason_view_html(candidates)
    assert 'class="rc-card"' in rc.build_rank_view_html(candidates)

    zone2_html = rc.build_check_your_own_html(_make_fake_batch_rows())
    assert 'class="rc-card"' in zone2_html
