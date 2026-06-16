import json


def _summary(tmp_path, macro):  # type: ignore[no-untyped-def]
    p = tmp_path / "brief_summary.json"
    p.write_text(json.dumps({"as_of": "2026-06-13", "macro": macro}))
    return str(p)


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
