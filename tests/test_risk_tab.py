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
    # Realistic length-3 pc_variance (use case truncates to top-3 eigenvalue shares).
    # sum=0.87 → honest residual = 0.13 (13%) via 1 - sum(pc_variance).
    "enb": 3.2,
    "pc_variance": [0.64, 0.14, 0.09],
    "pc_labels": [
        "Big-tech market beta",
        "Long-duration growth",
        "Semis vs software",
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
    "pc_labels": ["Bet 1", "Bet 2", "Bet 3"],
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
# Render smoke tests
# ---------------------------------------------------------------------------


def test_render_with_macro(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """render() must not raise and must emit v8 surface markers with a full macro."""
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

    all_html = "\n".join(rendered_html)
    # v8 surface: status banner and vitals must be present
    assert "MEASURED VS" in all_html, "v8 status banner 'MEASURED VS' must be present"
    assert (
        "Systematic share" in all_html
    ), "v8 vitals 'Systematic share' must be present"
    assert (
        "book" in all_html.lower() and "stands" in all_html.lower()
    ), "v8 'Where your book stands' header must be present (may be wrapped in em tags)"


def test_render_without_macro_no_raise(tmp_path):  # type: ignore[no-untyped-def]
    from adapters.visualization.tabs import risk

    risk.render(path=_summary(tmp_path, None))


def test_render_no_legacy_block(tmp_path) -> None:
    """render() must NOT emit ri-metric-row (the removed legacy block)."""
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
    assert (
        "ri-metric-row" not in all_html
    ), "Legacy 'ri-metric-row' must NOT appear — the backward-compat block was removed"
    # v8 surface must still be present
    assert (
        "MEASURED VS" in all_html
    ), "v8 status banner must still be present after removing legacy block"


def test_render_ai_panel_surfaces_when_cache_and_local(tmp_path) -> None:
    """With a cached CaseResult and is_local_runtime True, AI panel HTML must appear."""
    from unittest.mock import patch

    import streamlit as st

    from domain.case_models import CasePoint, CaseResult

    _CACHED = CaseResult(
        in_favor=(
            CasePoint(text="portfolio beta is elevated", source_tag="risk-model"),
        ),
        to_watch=(),
        data_gap=False,
    )

    rendered_html: list[str] = []

    def capture_markdown(text: str, **kwargs: object) -> None:  # type: ignore[misc]
        rendered_html.append(str(text))

    import adapters.visualization.components.risk_second_opinion as rso_comp
    import application.risk_second_opinion as rso_app
    from adapters.visualization.tabs import risk

    with (
        patch.object(st, "markdown", side_effect=capture_markdown),
        patch.object(st, "subheader"),
        patch.object(st, "caption"),
        patch.object(st, "divider"),
        patch.object(st, "columns", return_value=[_NullCtx(), _NullCtx()]),
        patch.object(st, "plotly_chart"),
        patch.object(st, "warning"),
        patch.object(rso_comp, "is_local_runtime", return_value=True),
        patch.object(rso_app, "load_cached_case", return_value=_CACHED),
    ):
        risk.render(path=_summary(tmp_path, _MACRO_V8))

    all_html = "\n".join(rendered_html)
    assert (
        "Google AI" in all_html or "RESEARCH" in all_html
    ), "AI second-opinion panel HTML must appear when cache is populated and is_local_runtime=True"


def test_render_ai_panel_absent_when_off_local(tmp_path) -> None:
    """With is_local_runtime False (or cache empty), AI panel HTML must NOT appear."""
    from unittest.mock import patch

    import streamlit as st

    rendered_html: list[str] = []

    def capture_markdown(text: str, **kwargs: object) -> None:  # type: ignore[misc]
        rendered_html.append(str(text))

    import adapters.visualization.components.risk_second_opinion as rso_comp
    import application.risk_second_opinion as rso_app
    from adapters.visualization.tabs import risk

    with (
        patch.object(st, "markdown", side_effect=capture_markdown),
        patch.object(st, "subheader"),
        patch.object(st, "caption"),
        patch.object(st, "divider"),
        patch.object(st, "columns", return_value=[_NullCtx(), _NullCtx()]),
        patch.object(st, "plotly_chart"),
        patch.object(st, "warning"),
        patch.object(rso_comp, "is_local_runtime", return_value=False),
        patch.object(rso_app, "load_cached_case", return_value=None),
    ):
        risk.render(path=_summary(tmp_path, _MACRO_V8))

    all_html = "\n".join(rendered_html)
    assert (
        "risk-ai" not in all_html
    ), "AI panel CSS class 'risk-ai' must NOT appear when off-local or cache empty"


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


def test_risk_tab_enb_copy_concentrated_when_one_axis_dominates() -> None:
    """A dominant PC-1 (>=40% variance) → 'one thing, many ways' framing."""
    from adapters.visualization.tabs import risk

    html = risk._compose(_MACRO_V8)  # pc_variance[0] = 0.64
    assert "one thing, many ways" in html
    assert "genuinely spread" not in html


def test_risk_tab_enb_copy_diversified_when_no_axis_dominates() -> None:
    """A spread book (PC-1 < 40%, high ENB) must NOT claim concentration."""
    from adapters.visualization.tabs import risk

    diversified = {**_MACRO_V8, "enb": 23.0, "pc_variance": [0.21, 0.10, 0.08]}
    html = risk._compose(diversified)
    assert "genuinely spread" in html, "diversified book must read as spread"
    assert (
        "one thing, many ways" not in html
    ), "must NOT assert concentration when no axis dominates"


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


def test_risk_tab_escapes_holding_name() -> None:
    """HTML-special chars in holding name/ticker must be escaped, not injected raw."""
    from adapters.visualization.tabs import risk

    macro = {
        **_MACRO_V8,
        "holdings_meta": [
            {
                "ticker": "X&Y",
                "name": "A<script>alert(1)</script>",
                "sector": "Tech",
                "weight": 0.5,
            },
        ],
        "risk_contribution": {"X&Y": 1.0},
    }
    html = risk._compose(macro)
    # Raw tag must not survive
    assert "<script>" not in html, "Raw <script> tag must be escaped, not injected"
    # Escaped form must be present
    assert (
        "&lt;script&gt;" in html or "A&lt;" in html
    ), "Escaped form of the holding name (&lt;script&gt; or A&lt;) must appear in output"


def test_risk_tab_enb_present_but_empty_pc_variance_no_crash() -> None:
    """Degenerate covariance: enb=0.0, pc_variance=[] — _compose must NOT raise IndexError.

    Production scenario: use case returns enb=0.0 with pc_variance=() because the
    covariance matrix is degenerate (too few history points).  The old code passed the
    ``if enb is None`` guard and then crashed on ``pc_variance[0]``.  After the fix
    _compose must return a string that contains the DATA-GAP / 'building history'
    fallback text.
    """
    from adapters.visualization.tabs import risk

    # Build a macro shaped like _MACRO_V8 but with the degenerate ENB state
    degenerate_macro: dict = {
        **_MACRO_V8,
        "enb": 0.0,
        "pc_variance": [],
        "pc_labels": [],
        "pc_labels_data_gap": True,
    }
    html = risk._compose(degenerate_macro)  # must NOT raise IndexError
    assert isinstance(html, str) and len(html) > 100
    # The section must communicate the data-gap state, not silently succeed with
    # a broken numeric reference.
    assert "DATA-GAP" in html or "building history" in html, (
        "Degenerate ENB (enb=0.0, pc_variance=[]) must render DATA-GAP or 'building history', "
        f"got: {html[:300]}"
    )


def test_risk_tab_enb_residual_is_honest() -> None:
    """Residual variance bar must equal 1 - sum(pc_variance), not sum(pc_variance[3:]).

    With a realistic length-3 pc_variance=[0.64, 0.14, 0.09] (sum=0.87) the residual
    should be 0.13 (13%).  The old code used sum(pc_variance[3:]) which is always 0.0
    when the use case returns ≤3 components — meaning NO residual row was ever rendered
    in production.  After the fix, the residual row must appear and show 13%.
    """
    from adapters.visualization.tabs import risk

    realistic_macro: dict = {
        **_MACRO_V8,
        "pc_variance": [0.64, 0.14, 0.09],  # length-3, sum=0.87 → residual=0.13
        "pc_labels": [
            "Big-tech market beta",
            "Long-duration growth",
            "Semis vs software",
        ],
        "pc_labels_data_gap": False,
    }
    html = risk._compose(realistic_macro)
    # The residual row label contains "PC 4" — check it appears WITH "13%"
    # (the PC bar row, not a sector bar which also has arbitrary percentages)
    assert "PC 4" in html, (
        "Residual bar row (PC 4–N) must be rendered when 1-sum(pc_variance)=0.13 > 0.005. "
        "Old code used sum(pc_variance[3:]) which is always 0.0 for ≤3 components."
    )
    # Find the PC 4 row and verify it carries the honest 13% residual value
    pc4_idx = html.find("PC 4")
    pc4_segment = html[pc4_idx : pc4_idx + 200]
    assert "13%" in pc4_segment, (
        "Residual PC-4 row must display 13% (= 1 - 0.87). "
        f"Got PC4 segment: {pc4_segment}"
    )


# ---------------------------------------------------------------------------
# R07 — _compose ai_html injection ordering
# ---------------------------------------------------------------------------


def test_compose_ai_html_placed_after_drift_before_teach() -> None:
    """When ai_html is provided, _compose must inject it AFTER drift and BEFORE teach.

    Mockup order: _drift → [Second opinion · Google AI] → _teach → _flags_footer
    """
    from adapters.visualization.tabs import risk

    sentinel = '<div class="test-ai-sentinel">AI_PANEL_HERE</div>'
    html = risk._compose(_MACRO_V8, ai_html=sentinel)

    assert sentinel in html, "_compose must include ai_html when provided"

    # Verify ordering: drift section marker < ai_html < teach section marker.
    # _drift emits "risk-drift" class; _teach emits id="teach" on its section div.
    drift_idx = html.find("risk-drift")
    ai_idx = html.find("AI_PANEL_HERE")
    teach_idx = html.find('id="teach"')

    assert drift_idx != -1, "drift section must be present (risk-drift class)"
    assert ai_idx != -1, "AI sentinel must appear in composed HTML"
    assert teach_idx != -1, 'teach section must be present (id="teach")'

    assert (
        drift_idx < ai_idx
    ), f"AI panel (pos {ai_idx}) must appear AFTER drift (pos {drift_idx})"
    assert (
        ai_idx < teach_idx
    ), f"AI panel (pos {ai_idx}) must appear BEFORE teach section (pos {teach_idx})"


def test_compose_empty_ai_html_not_inserted() -> None:
    """When ai_html is empty string (default), _compose must not add a blank entry."""
    from adapters.visualization.tabs import risk

    html_default = risk._compose(_MACRO_V8)
    html_empty = risk._compose(_MACRO_V8, ai_html="")

    assert (
        html_default == html_empty
    ), "_compose with ai_html='' must produce the same output as calling without ai_html"


def test_compose_ai_html_not_present_without_arg() -> None:
    """_compose without ai_html must not contain any AI-panel markers (pure test)."""
    from adapters.visualization.tabs import risk

    html = risk._compose(_MACRO_V8)
    # No Google-AI specific CSS class should appear from _compose alone
    assert (
        "risk-ai" not in html
    ), "_compose alone must not inject risk-ai CSS class — AI HTML comes from render()"


# ---------------------------------------------------------------------------
# P2-Risk — evidence chips, benchmark card, impact-ranked decision levers
# ---------------------------------------------------------------------------


def test_vitals_carry_registry_evidence_chips() -> None:
    """Key metrics must render the registry-backed evidence chip (ri-chip + verdict)."""
    from adapters.visualization.tabs import risk

    html = risk._compose(_MACRO_V8)
    assert "ri-chip" in html, "vitals must render the evidence-chip component"
    assert "ri-vbadge" in html, "evidence chip must carry a verdict badge"
    # Registry labels for the chipped metrics (distinct from the short vital tooltips)
    assert "Effective number of bets" in html, "ENB chip label must appear"
    assert (
        "Diversification ratio" in html
    ), "diversification-ratio chip label must appear"
    # Sector-HHI chip lives in the sector section
    assert "Sector concentration (HHI)" in html, "sector-HHI chip label must appear"
    # A registry healthy-band string must reach the page (chip tooltip + benchmark)
    assert "broadly diversified book is 40+" in html, "ENB healthy band must surface"


def test_benchmark_card_is_descriptive_with_reference_points() -> None:
    """_benchmark must place book values next to reference points, tagged not-advice."""
    from adapters.visualization.tabs.risk.evidence import _benchmark

    html = _benchmark(_MACRO_V8)
    assert "reference points" in html.lower(), "benchmark must frame reference points"
    assert "NOT A TRADE CALL" in html, "benchmark must carry the descriptive disclaimer"
    assert "71%" in html, "book systematic share (71%) must appear"
    assert "0.34" in html, "book sector HHI (0.34) must appear"
    assert "SPY" in html, "a reference point (SPY) must appear"
    assert "Healthy band" in html, "registry healthy band must be shown"


def test_benchmark_card_empty_when_no_metrics() -> None:
    """_benchmark must return '' (skip) when none of its metrics are present."""
    from adapters.visualization.tabs.risk.evidence import _benchmark

    assert _benchmark({}) == "", "benchmark must skip cleanly with no metrics"


def test_decision_levers_impact_ranked_and_descriptive() -> None:
    """_decision_levers must rank by risk contribution and frame leverage, not advice."""
    from adapters.visualization.tabs.risk.sections import _decision_levers

    html = _decision_levers(_MACRO_V8)
    assert "NOT A TRADE CALL" in html, "levers must carry the descriptive disclaimer"
    assert "risk-per-dollar" in html, "leverage annotation must appear"
    assert "leverage" in html.lower(), "card must be framed as leverage on the metric"
    # NVDA (rc=0.14) is the top contributor → must be ranked first, before MSFT (0.11)
    assert html.find("NVDA") < html.find("MSFT"), "must be impact-ranked by risk share"
    # Systematic share 71% is 11 points past the 60% line — directional gap framing
    assert "60% line" in html, "gap framing vs the 60% line must appear"


def test_decision_levers_empty_without_risk_contribution() -> None:
    """_decision_levers must return '' when the Euler decomposition is unavailable."""
    from adapters.visualization.tabs.risk.sections import _decision_levers

    no_rc = {**_MACRO_V8, "risk_contribution": {}}
    assert _decision_levers(no_rc) == "", "levers must skip without risk_contribution"


def test_decision_levers_no_forbidden_words() -> None:
    """The new levers/benchmark copy must not introduce trade-recommendation words."""
    import re

    from adapters.visualization.tabs.risk.evidence import _benchmark
    from adapters.visualization.tabs.risk.sections import _decision_levers
    from domain.fit import FORBIDDEN_WORDS

    blob = (_benchmark(_MACRO_V8) + _decision_levers(_MACRO_V8)).lower()
    for w in FORBIDDEN_WORDS:
        assert not re.search(
            rf"\b{re.escape(w)}\b", blob
        ), f"Forbidden word {w!r} found in new P2-Risk copy"


def test_render_default_path_resolves_via_book_context(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """render() called with no explicit path (the real dashboard.py call) must
    resolve through the book-context resolver — the sample brief on cold
    start, never data/personal/brief_summary.json."""
    from adapters.visualization.tabs import risk

    captured: dict[str, str] = {}

    def fake_load_brief_summary(path: str) -> None:
        captured["path"] = path
        return None

    monkeypatch.setattr(risk.compose, "load_brief_summary", fake_load_brief_summary)

    risk.render()

    assert captured["path"] == "data/sample/brief_summary.json"


def test_render_never_shows_personal_upload_history_table(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """The Risk tab must never render the operator's personal holdings
    upload-history table — not for a hosted/public visitor (leaks the
    operator's own upload filenames/cost basis), and not locally either
    (unused dogfood table with no place in the Risk tab)."""
    import pathlib

    import streamlit as st

    from adapters.visualization.tabs import risk

    monkeypatch.setattr(pathlib.Path, "exists", lambda self: True)
    captured: list[object] = []
    monkeypatch.setattr(
        st, "subheader", lambda *a, **k: captured.append(a)
    )  # noqa: ARG005

    for local in (True, False):
        monkeypatch.setattr(
            risk.compose,
            "holdings_upload_enabled",
            lambda local=local: local,
            raising=False,
        )
        risk.render(path=str(tmp_path / "brief.json"))

    assert (
        captured == []
    ), "personal upload history table must never render on the Risk tab"
