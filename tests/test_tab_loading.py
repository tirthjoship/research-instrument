"""Tests for the cross-tab loading overlay builders (CSS + JS)."""

from adapters.visualization.components.tab_loading import (
    build_tab_loading_css,
    build_tab_loading_js,
)

TAB_LABELS = [
    "Loading your book",
    "Building this week's research shortlist",
    "Computing portfolio risk",
    "Loading your portfolio",
    "Loading stock analysis",
    "Loading the track record",
]


def test_css_has_overlay_classes_and_escalation_states():
    css = build_tab_loading_css()
    for cls in (
        ".scr-load-bar",
        ".scr-load-dot",
        ".scr-load-timer",
        ".scr-load-hint",
        ".scr-load-hint.warn",
        ".scr-load-hint.long",
        ".scr-skeleton",
        ".scr-sk-tile",
    ):
        assert cls in css


def test_css_uses_app_fonts_not_newsreader():
    css = build_tab_loading_css()
    assert "IBM Plex Mono" in css  # timer
    assert "DM Sans" in css  # label/hint
    assert "Newsreader" not in css  # mockup placeholder must be gone


def test_css_bar_moves_left_to_right_and_shimmers():
    css = build_tab_loading_css()
    assert "left:-40%" in css
    assert "left:102%" in css  # segment travels left -> right
    assert "shimmer" in css.lower()


def test_js_contains_all_six_labels():
    js = build_tab_loading_js(TAB_LABELS)
    for label in TAB_LABELS:
        assert label in js


def test_js_has_escalation_thresholds_and_exact_copy():
    js = build_tab_loading_js(TAB_LABELS)
    assert "10000" in js and "90000" in js
    assert "Still fetching live market data — this can take a moment." in js
    assert "Taking unusually long — try reloading the page." in js
    assert "Usually under a second; live look-ups take a few seconds." in js


def test_js_clears_on_populate_and_uses_real_timer():
    js = build_tab_loading_js(TAB_LABELS)
    assert "MutationObserver" in js
    assert "performance.now" in js
    assert "setInterval" in js
    assert "querySelectorAll" in js
    assert 'role="tabpanel"' in js or 'role=\\"tabpanel\\"' in js


def test_js_no_fake_eta_language():
    js = build_tab_loading_js(TAB_LABELS).lower()
    for banned in ("remaining", "estimated", "eta", "time left"):
        assert banned not in js


def test_js_requires_six_labels():
    import pytest

    with pytest.raises(ValueError):
        build_tab_loading_js(["only", "two"])
