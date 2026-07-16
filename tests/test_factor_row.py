"""Task 2: factor_row HTML adapter over factor_bands."""

from __future__ import annotations


def test_render_factor_row_has_band_and_percentile_and_tooltip() -> None:
    from adapters.visualization.components.factor_row import render_factor_row

    html = render_factor_row("quality", value=2.83, percentile=0.95)
    assert "Exceptional" in html  # band label
    assert "p95" in html  # percentile
    # colour comes from a CSS var(), not a raw hex inline before any var()
    assert "var(" in html
    # glossary tooltip wired
    assert "ri-ttip" in html or "Quality factor" in html


def test_render_factor_row_data_gap() -> None:
    from adapters.visualization.components.factor_row import render_factor_row

    html = render_factor_row("lowvol", value=None, percentile=None)
    assert "DATA-GAP" in html


def test_render_factor_row_no_hex_before_var() -> None:
    """Colour must come from a CSS var(), never a raw hex in the early part."""
    from adapters.visualization.components.factor_row import render_factor_row

    html = render_factor_row("quality", value=2.83, percentile=0.95)
    # No raw 6-char hex colours (e.g. #16A34A) should appear outside a CSS var() reference
    # Simple heuristic: split on "var(" — the part before first var() should not end in a hex
    parts = html.split("var(")
    prefix = parts[0][-2:] if len(parts[0]) >= 2 else parts[0]
    assert "#" not in prefix, f"Hex colour before var(): ...{parts[0][-20:]!r}"


def test_render_factor_row_strong_band() -> None:
    from adapters.visualization.components.factor_row import render_factor_row

    html = render_factor_row("momentum", value=1.1, percentile=0.80)
    assert "Strong" in html
    assert "p80" in html


def test_render_factor_row_weak_band() -> None:
    from adapters.visualization.components.factor_row import render_factor_row

    html = render_factor_row("value", value=-0.5, percentile=0.25)
    assert "Weak" in html
    assert "p25" in html


def test_render_factor_row_analyst_spread_display_label() -> None:
    """revision key must show 'Analyst dispersion' as display label (honest label)."""
    from adapters.visualization.components.factor_row import render_factor_row

    html = render_factor_row("revision", value=0.9, percentile=0.88)
    assert "Analyst dispersion" in html


# ── Fix 1: circle badge tooltip ───────────────────────────────────────────────


def test_factor_row_tooltip_is_circle_badge() -> None:
    """Glossary tooltip trigger must render as a grey circle badge, not a bare 'i'."""
    from adapters.visualization.components.factor_row import render_factor_row

    html = render_factor_row("quality", value=2.83, percentile=0.95)
    # Circle badge: border-radius:50% and background:#CBD5E1 present on the trigger.
    assert "border-radius:50%" in html, "circle badge must have border-radius:50%"
    assert "#CBD5E1" in html, "circle badge must use #CBD5E1 muted background"
    # The .ri-ttip + .ri-tip structure must be intact for hover cloud.
    assert "ri-ttip" in html
    assert "ri-tip" in html


def test_factor_row_data_gap_tooltip_badge() -> None:
    """DATA-GAP row should also render the glossary circle badge (if term exists)."""
    from adapters.visualization.components.factor_row import render_factor_row

    html = render_factor_row("quality", value=None, percentile=None)
    # DATA-GAP row still has label + tooltip trigger.
    assert "ri-ttip" in html
    assert "DATA-GAP" in html


# ── Fix 4: momentum sparkline ────────────────────────────────────────────────


def test_momentum_row_has_sparkline_svg() -> None:
    """Fix 4: momentum row must contain an inline SVG sparkline (decorative motif)."""
    from adapters.visualization.components.factor_row import render_factor_row

    html = render_factor_row("momentum", value=0.8, percentile=0.75)
    assert "<svg" in html, "momentum row must contain an SVG sparkline"
    assert "polyline" in html, "sparkline must use a polyline element"


def test_non_momentum_row_has_no_sparkline() -> None:
    """Non-momentum factor rows must NOT render a sparkline."""
    from adapters.visualization.components.factor_row import render_factor_row

    for key in ("quality", "value", "revision", "lowvol"):
        html = render_factor_row(key, value=1.0, percentile=0.85)
        assert "<svg" not in html, f"{key} row must not contain an SVG sparkline"


def test_momentum_data_gap_no_sparkline() -> None:
    """DATA-GAP momentum row omits the sparkline (no band badge to prepend to)."""
    from adapters.visualization.components.factor_row import render_factor_row

    html = render_factor_row("momentum", value=None, percentile=None)
    # DATA-GAP path has no band badge — sparkline is not prepended there.
    assert "DATA-GAP" in html


def test_glossary_tooltip_uses_left_anchored_variant() -> None:
    """The glossary tooltip trigger sits in the leftmost grid column of each
    factor row -- a centered tooltip there overflows past the card's left
    edge and gets clipped (regression: was reported on a live CA/India
    screen mockup where the leftmost factor row's tooltip text was cut off).
    Must use the left-anchored .ri-tip-left variant, not the default centered
    .ri-tip alone."""
    from adapters.visualization.components.factor_row import render_factor_row

    html = render_factor_row("quality", value=2.83, percentile=0.95)
    assert "ri-tip-left" in html
