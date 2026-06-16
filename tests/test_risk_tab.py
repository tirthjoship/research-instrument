import json

# ---------------------------------------------------------------------------
# Shared test macro fixtures
# ---------------------------------------------------------------------------

_MACRO_V8: dict = {
    # original keys
    "net_beta_by_factor": {"SPY": 1.18, "GROWTH": 0.41, "RATES": -0.22, "VALUE": -0.19},
    "factors": ["SPY", "GROWTH", "RATES", "VALUE"],
    "systematic_share": 0.71,
    "idiosyncratic_share": 0.29,
    "systematic_share_adj": 0.66,
    "dominant_factor": "SPY",
    "flags": ["SYSTEMATIC_DOMINANT"],
    "coverage_holdings": 58,
    "total_holdings": 66,
    # v8 risk-stats keys
    "enb": 3.2,
    "pc_variance": [0.64, 0.14, 0.09, 0.13],
    "pc_labels": [
        "Big-tech market beta",
        "Long-duration growth",
        "Semis vs software",
        "Residual",
    ],
    "pc_labels_data_gap": False,
    "systematic_share_ci": [0.66, 0.76],
    "beta_ci_by_factor": {
        "SPY": [1.09, 1.27],
        "GROWTH": [0.35, 0.47],
        "RATES": [-0.27, -0.17],
        "VALUE": [-0.25, -0.13],
    },
    "suppressed_factors": ["VALUE"],  # CI straddles 0 for VALUE in this mock
    "downside_beta": 1.31,
    "risk_contribution": {
        "NVDA": 0.14,
        "MSFT": 0.11,
        "AAPL": 0.09,
        "GOOGL": 0.08,
        "AMZN": 0.07,
    },
    "holdings_meta": [
        {"ticker": "NVDA", "name": "Nvidia", "weight": 0.09},
        {"ticker": "MSFT", "name": "Microsoft", "weight": 0.10},
        {"ticker": "AAPL", "name": "Apple", "weight": 0.10},
        {"ticker": "GOOGL", "name": "Alphabet", "weight": 0.08},
        {"ticker": "AMZN", "name": "Amazon", "weight": 0.07},
    ],
    "sector_weights": {
        "Info Technology": 0.52,
        "Comm. Services": 0.18,
        "Consumer Disc.": 0.16,
        "Financials": 0.07,
        "Energy": 0.02,
    },
    "sector_hhi": 0.34,
    "sector_gaps": ["Health Care", "Consumer Staples", "Utilities", "Real Estate"],
    "vif_by_factor": {"SPY": 8.2, "GROWTH": 6.1, "RATES": 2.1, "VALUE": None},
    "diversification_ratio": 1.4,
    "sys_share_history": [
        ["2026-04-20", 0.64],
        ["2026-04-27", 0.65],
        ["2026-05-04", 0.66],
        ["2026-05-11", 0.66],
        ["2026-05-18", 0.67],
        ["2026-05-25", 0.68],
        ["2026-06-01", 0.69],
        ["2026-06-08", 0.71],
    ],
}

_MACRO_NO_FLAGS = {**_MACRO_V8, "flags": []}

_MACRO_ENB_GAP = {
    **_MACRO_V8,
    "pc_labels_data_gap": True,
    "pc_labels": ["Bet 1", "Bet 2", "Bet 3", "Residual"],
}

# Thin macro: only original keys, none of the v8 ones
_THIN_MACRO: dict = {
    "net_beta_by_factor": {"SPY": 1.39},
    "systematic_share": 0.63,
    "idiosyncratic_share": 0.37,
    "dominant_factor": "SPY",
    "flags": ["SYSTEMATIC_DOMINANT"],
    "coverage_holdings": 60,
    "total_holdings": 66,
}


def _summary(tmp_path, macro):  # type: ignore[no-untyped-def]
    p = tmp_path / "brief_summary.json"
    p.write_text(json.dumps({"as_of": "2026-06-13", "macro": macro}))
    return str(p)


# ---------------------------------------------------------------------------
# Original tests (kept intact, still pass)
# ---------------------------------------------------------------------------


def test_render_with_macro(tmp_path):  # type: ignore[no-untyped-def]
    from adapters.visualization.tabs import risk

    risk.render(
        path=_summary(
            tmp_path,
            {
                "net_beta_by_factor": {"SPY": 1.39, "TLT": -0.2},
                "systematic_share": 0.63,
                "idiosyncratic_share": 0.37,
                "dominant_factor": "SPY",
                "flags": ["SYSTEMATIC_DOMINANT"],
                "coverage_holdings": 60,
                "total_holdings": 66,
            },
        )
    )


def test_render_without_macro_no_raise(tmp_path):  # type: ignore[no-untyped-def]
    from adapters.visualization.tabs import risk

    risk.render(path=_summary(tmp_path, None))


def test_band_strips_render_elevated_and_macro_leaning(tmp_path, capsys):  # type: ignore[no-untyped-def]
    """Band strips for net_beta=1.42 → Elevated, sys_share=0.628 → Macro-leaning.

    Also asserts a pre-existing element still renders (additive, not replacing).
    """
    from unittest.mock import patch

    import streamlit as st

    rendered_html: list[str] = []

    def capture_markdown(text: str, **kwargs: object) -> None:  # type: ignore[misc]
        rendered_html.append(str(text))

    from adapters.visualization.tabs import risk

    with (
        patch.object(st, "markdown", side_effect=capture_markdown),
        patch.object(st, "subheader"),
        patch.object(st, "caption"),
        patch.object(st, "divider"),
        patch.object(st, "columns", return_value=[_NullCtx(), _NullCtx()]),
        patch.object(st, "plotly_chart"),
        patch.object(st, "warning"),
    ):
        risk.render(
            path=_summary(
                tmp_path,
                {
                    "net_beta_by_factor": {"SPY": 1.42, "TLT": -0.1},
                    "systematic_share": 0.628,
                    "idiosyncratic_share": 0.372,
                    "dominant_factor": "SPY",
                    "flags": [],
                    "coverage_holdings": 55,
                    "total_holdings": 60,
                },
            )
        )

    all_html = "\n".join(rendered_html)

    # New band strips must be present
    assert (
        "Elevated" in all_html
    ), f"Expected 'Elevated' in rendered output; got:\n{all_html[:2000]}"
    assert (
        "Macro-leaning" in all_html
    ), f"Expected 'Macro-leaning' in rendered output; got:\n{all_html[:2000]}"

    # Pre-existing element: the hero metric row is still rendered (additivity check)
    assert (
        "ri-metric-row" in all_html
    ), "Expected pre-existing 'ri-metric-row' still present (additivity broken)"


class _NullCtx:
    """Minimal context-manager stub for st.columns() patching."""

    def __enter__(self) -> "_NullCtx":
        return self

    def __exit__(self, *args: object) -> None:
        pass


# ---------------------------------------------------------------------------
# NEW Task 12: _compose() pure-function tests  (TDD — write BEFORE implement)
# ---------------------------------------------------------------------------


def test_risk_tab_renders_full_macro_v8() -> None:
    """Fully populated v8 macro must hit every honesty needle."""
    from adapters.visualization.tabs import risk

    html = risk._compose(_MACRO_V8)
    for needle in [
        "Effective bets",
        "Systematic share",
        "Who owns the bet",
        "DESCRIPTIVE",
        "heuristic surfacing dial",
    ]:
        assert needle in html, f"Missing needle: {needle!r}"


def test_risk_tab_no_forbidden_words() -> None:
    """_compose must not emit any FORBIDDEN_WORDS as standalone words.

    Uses word-boundary check (\\bword\\b) to avoid false positives from compound
    words/names that contain a forbidden substring (e.g. 'Alphabet' ⊃ 'alpha',
    'outperforms' ⊃ 'outperform').  The intent is to prevent trade-recommendation
    language, not to ban every word that happens to share letters with a
    forbidden root.
    """
    import re

    from adapters.visualization.tabs import risk
    from domain.fit import FORBIDDEN_WORDS

    html = risk._compose(_MACRO_V8).lower()
    for w in FORBIDDEN_WORDS:
        pattern = rf"\b{re.escape(w)}\b"
        assert not re.search(
            pattern, html
        ), f"Forbidden word {w!r} found as a standalone word in rendered HTML"


def test_risk_tab_thin_macro_back_compat() -> None:
    """Thin macro (no v8 keys) must degrade gracefully — DATA-GAP or building history."""
    from adapters.visualization.tabs import risk

    html = risk._compose(_THIN_MACRO)
    assert (
        "DATA-GAP" in html or "building history" in html
    ), "Thin macro must produce DATA-GAP or building history fallback"


def test_risk_tab_none_macro_safe() -> None:
    """_compose(None) must return the safe-fallback warning (weekly-brief text)."""
    from adapters.visualization.tabs import risk

    html = risk._compose(None)
    assert "weekly-brief" in html, "None macro must contain the safe-fallback text"


def test_risk_tab_status_banner_green_when_no_flags() -> None:
    """Status banner must say 'All clear' when flags list is empty."""
    from adapters.visualization.tabs import risk

    html = risk._compose(_MACRO_NO_FLAGS)
    assert "All clear" in html, "Status banner must show 'All clear' when flags=[]"


def test_risk_tab_status_banner_amber_when_flags() -> None:
    """Status banner must show flag count when flags non-empty."""
    from adapters.visualization.tabs import risk

    html = risk._compose(_MACRO_V8)
    # '1 of your risk lines' (1 flag in _MACRO_V8)
    assert (
        "risk line" in html.lower()
    ), "Status banner must mention 'risk line' when flagged"


def test_risk_tab_enb_data_gap_fallback() -> None:
    """When pc_labels_data_gap=True, ENB section must show 'Bet 1' and DATA-GAP."""
    from adapters.visualization.tabs import risk

    html = risk._compose(_MACRO_ENB_GAP)
    assert "Bet 1" in html, "ENB gap fallback must show 'Bet 1'"
    assert "DATA-GAP" in html, "ENB gap fallback must show DATA-GAP note"


def test_risk_tab_sector_not_a_buy_call() -> None:
    """Sector gaps section must carry the trade-call disclaimer.

    NOTE: mockup uses "NOT A BUY CALL" but "buy" is a FORBIDDEN_WORD so the
    UI text was rephrased to "NOT A TRADE CALL" — same intent, no forbidden
    substring.  This test checks the actual rendered label.
    """
    from adapters.visualization.tabs import risk

    html = risk._compose(_MACRO_V8)
    assert "NOT A TRADE CALL" in html, (
        "Sector section must tag NOT A TRADE CALL "
        "(rephrased from mockup 'NOT A BUY CALL' to avoid FORBIDDEN_WORDS)"
    )


def test_risk_tab_who_owns_shows_risk_and_dollar() -> None:
    """Who-owns section must show both a risk % and a dollar % for contrast."""
    from adapters.visualization.tabs import risk

    html = risk._compose(_MACRO_V8)
    # risk contribution shown (14% for NVDA) and weight shown (9% for NVDA)
    assert "RISK" in html, "Who-owns section must show RISK"
    # NVDA weight is 9%
    assert "9%" in html or "9 %" in html, "Who-owns must show dollar weight (NVDA=9%)"
    # NVDA risk contrib is 14%
    assert "14%" in html or "14 %" in html, "Who-owns must show risk % (NVDA=14%)"


def test_risk_tab_compose_is_pure_no_streamlit() -> None:
    """_compose must not import or call streamlit — pure string composer."""
    # Ensure module is loaded
    from adapters.visualization.tabs import risk

    # _compose must be callable without st mock
    html = risk._compose(_MACRO_V8)
    assert isinstance(html, str) and len(html) > 100


def test_risk_tab_renders_config_factors_not_hardcoded() -> None:
    """Factor chart must iterate macro factors, not hardcode 9 specific names."""
    from adapters.visualization.tabs import risk

    # 4-factor macro — each factor ticker must appear in the output
    html = risk._compose(_MACRO_V8)
    for f in ["SPY", "GROWTH", "RATES"]:
        assert f in html, f"Factor {f!r} must appear in factor chart"


def test_risk_tab_drift_building_history_when_sparse() -> None:
    """Fewer than 3 history points must show 'building history', not a trend."""
    from adapters.visualization.tabs import risk

    sparse_macro = {**_MACRO_V8, "sys_share_history": [["2026-06-08", 0.71]]}
    html = risk._compose(sparse_macro)
    assert "building history" in html, "Sparse history must show 'building history'"


def test_risk_tab_suppressed_factors_greyed() -> None:
    """Factors in suppressed_factors must be labelled ≈0 in the factor chart."""
    from adapters.visualization.tabs import risk

    html = risk._compose(_MACRO_V8)
    # VALUE is suppressed in _MACRO_V8
    assert "≈0" in html, "Suppressed factor must show ≈0 label"


def test_risk_tab_vif_collinear_note() -> None:
    """Factors with high VIF (or None=inf) must trigger the collinear note."""
    from adapters.visualization.tabs import risk

    html = risk._compose(_MACRO_V8)
    # SPY and GROWTH have VIF > 5 in _MACRO_V8
    assert (
        "collinear" in html.lower() or "VIF" in html
    ), "High-VIF factors must surface the collinear/VIF caveat"


def test_risk_tab_systematic_share_ci_band() -> None:
    """Bootstrap CI band for systematic share must reference the ci values."""
    from adapters.visualization.tabs import risk

    html = risk._compose(_MACRO_V8)
    # systematic_share_ci=[0.66,0.76] → text about bootstrap or 90%
    assert (
        "bootstrap" in html.lower() or "90%" in html
    ), "Systematic share strip must reference the bootstrap CI band"


def test_risk_tab_measured_vs_subtext_always_present() -> None:
    """MEASURED VS sub-text must appear in every non-None state."""
    from adapters.visualization.tabs import risk

    for macro in [_MACRO_V8, _MACRO_NO_FLAGS, _THIN_MACRO]:
        html = risk._compose(macro)
        assert "MEASURED VS" in html, "MEASURED VS must always appear in status banner"
