import json
from datetime import date, timedelta

from adapters.visualization.data_loader import (
    load_brief_summary,
    load_latest_screen,
    staleness_days,
)


def test_load_brief_summary_missing_returns_none(tmp_path):
    assert load_brief_summary(str(tmp_path / "nope.json")) is None


def test_load_brief_summary_roundtrip(tmp_path):
    p = tmp_path / "brief_summary.json"
    p.write_text(json.dumps({"as_of": "2026-06-13", "holdings": []}))
    assert load_brief_summary(str(p))["as_of"] == "2026-06-13"


def test_load_latest_screen_picks_newest_and_ignores_ic(tmp_path):
    (tmp_path / "screen_ic_2026-06-08.json").write_text("{}")
    (tmp_path / "screen_2026-06-01.json").write_text(
        json.dumps({"as_of": "2026-06-01"})
    )
    (tmp_path / "screen_2026-06-08.json").write_text(
        json.dumps({"as_of": "2026-06-08"})
    )
    got = load_latest_screen(str(tmp_path))
    assert got["as_of"] == "2026-06-08"


def test_load_latest_screen_ignores_cited_cases_sidecar(tmp_path):
    (tmp_path / "screen_2026-06-01.json").write_text(
        json.dumps({"as_of": "2026-06-01"})
    )
    (tmp_path / "screen_2026-06-08.json").write_text(
        json.dumps({"as_of": "2026-06-08", "universe_size": 512, "candidates": []})
    )
    # Sorts alphabetically after any screen_<date>.json — must not be picked as latest.
    (tmp_path / "screen_cited_cases.json").write_text(
        json.dumps({"as_of": "2026-06-08", "cases": {}})
    )
    got = load_latest_screen(str(tmp_path))
    assert got["as_of"] == "2026-06-08"
    assert got["universe_size"] == 512


def test_load_latest_screen_empty_dir(tmp_path):
    assert load_latest_screen(str(tmp_path)) is None


def test_staleness_days():
    nine_ago = (date.today() - timedelta(days=9)).isoformat()
    assert staleness_days(nine_ago) == 9
    assert staleness_days("not-a-date") is None


def test_load_adherence_log_missing_returns_empty(tmp_path):
    from adapters.visualization.data_loader import load_adherence_log

    assert load_adherence_log(str(tmp_path / "nope.jsonl")) == []


def test_load_adherence_log_parses_and_sorts(tmp_path):
    from adapters.visualization.data_loader import load_adherence_log

    p = tmp_path / "adherence_log.jsonl"
    p.write_text(
        '{"ticker": "ARKK", "verdict": "REDUCE", "flag_date": "2026-06-06", '
        '"actual_cut_fraction": 0.0, "label": "IGNORED", "gap_cad": -120.0, '
        '"gap_bps": -8.0}\n'
        "garbage line\n"
        '{"ticker": "XYZ", "verdict": "TRIM", "flag_date": "2026-05-30", '
        '"actual_cut_fraction": 0.5, "label": "FOLLOWED", "gap_cad": 40.0, '
        '"gap_bps": 3.0}\n'
    )
    rows = load_adherence_log(str(p))
    assert [r["ticker"] for r in rows] == ["XYZ", "ARKK"]  # sorted by flag_date


def test_load_screen_history_sorted_and_excludes_ic(tmp_path):
    import json

    from adapters.visualization.data_loader import load_screen_history

    (tmp_path / "screen_ic_2026-06-08.json").write_text("{}")
    (tmp_path / "screen_2026-06-01.json").write_text(
        json.dumps(
            {
                "as_of": "2026-06-01",
                "universe_size": 500,
                "candidates": [{"ticker": "A"}],
                "abstained": False,
            }
        )
    )
    (tmp_path / "screen_2026-06-08.json").write_text(
        json.dumps(
            {
                "as_of": "2026-06-08",
                "universe_size": 512,
                "candidates": [],
                "abstained": True,
            }
        )
    )
    hist = load_screen_history(str(tmp_path))
    assert [h["as_of"] for h in hist] == ["2026-06-08", "2026-06-01"]  # newest first
    assert hist[0]["n_candidates"] == 0 and hist[1]["n_candidates"] == 1


def test_load_screen_history_empty(tmp_path):
    from adapters.visualization.data_loader import load_screen_history

    assert load_screen_history(str(tmp_path)) == []


def test_load_screen_history_excludes_cited_cases_sidecar(tmp_path):
    from adapters.visualization.data_loader import load_screen_history

    (tmp_path / "screen_2026-06-08.json").write_text(
        json.dumps(
            {
                "as_of": "2026-06-08",
                "universe_size": 512,
                "candidates": [{"ticker": "A"}],
            }
        )
    )
    (tmp_path / "screen_cited_cases.json").write_text(
        json.dumps({"as_of": "2026-06-08", "cases": {}})
    )
    hist = load_screen_history(str(tmp_path))
    assert len(hist) == 1
    assert hist[0]["as_of"] == "2026-06-08"
