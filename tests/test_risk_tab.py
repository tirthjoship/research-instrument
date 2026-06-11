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
