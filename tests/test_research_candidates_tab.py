import json


def test_render_with_screen_fixture(tmp_path):  # type: ignore[no-untyped-def]
    (tmp_path / "screen_2026-06-13.json").write_text(
        json.dumps(
            {
                "as_of": "2026-06-13",
                "universe_size": 430,
                "abstained": False,
                "candidates": [
                    {
                        "ticker": "ABC",
                        "composite": 0.71,
                        "why": "cheap vs sector",
                        "label": "RESEARCH_ONLY",
                        "factor_scores": [{"name": "value", "percentile": 0.88}],
                    }
                ],
            }
        )
    )
    from adapters.visualization.tabs import research_candidates

    research_candidates.render(reports_dir=str(tmp_path))


def test_render_empty_dir_no_raise(tmp_path):  # type: ignore[no-untyped-def]
    from adapters.visualization.tabs import research_candidates

    research_candidates.render(reports_dir=str(tmp_path))
