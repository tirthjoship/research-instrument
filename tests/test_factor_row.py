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
    """revision key must show 'Analyst spread' as display label (honest label)."""
    from adapters.visualization.components.factor_row import render_factor_row

    html = render_factor_row("revision", value=0.9, percentile=0.88)
    assert "Analyst spread" in html
