"""Lens-nav scroll shim — JS shape contract."""

from __future__ import annotations

from adapters.visualization.components.lens_scroll import build_lens_scroll_js


def test_js_intercepts_click_and_scrolls() -> None:
    js = build_lens_scroll_js()
    # Targets the lens beans, prevents the disruptive native hash nav, scrolls.
    assert "a.ri-lens" in js
    assert "preventDefault" in js
    assert "scrollIntoView" in js
    assert "behavior: 'smooth'" in js


def test_js_uses_parent_document_and_rewire_guard() -> None:
    js = build_lens_scroll_js()
    # v2 component → main document via ownerDocument; guard against double-wiring.
    assert "parentElement.ownerDocument" in js
    assert "lensWired" in js
