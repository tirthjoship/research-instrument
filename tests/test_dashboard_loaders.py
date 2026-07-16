import json
from datetime import date, timedelta

from adapters.visualization.data_loader import (
    load_brief_summary,
    load_combined_screen,
    load_latest_screen,
    load_latest_screened,
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


def test_load_latest_screened_merges_universe_fields_from_underlying_screen(tmp_path):
    """screened_<date>.json (SP3 blended sidecar) only ever contains {as_of,
    corroboration_run_date, rows} -- see screen_commands.py::_write_screened_json.
    Without merging in universe_size/diagnostics from the underlying
    screen_<date>.json, build_header_html()'s Universe/Cleared/Shown tiles
    silently show 0/0/0 despite real candidates being listed below (caught
    running a real local screen-candidates for CA/India, which always
    writes both files)."""
    (tmp_path / "screen_2026-07-16.json").write_text(
        json.dumps(
            {
                "as_of": "2026-07-16",
                "universe_size": 52,
                "diagnostics": {"cleared": 29, "scanned": 52},
                "candidates": [{"ticker": "RY.TO"}],
            }
        )
    )
    (tmp_path / "screened_2026-07-16.json").write_text(
        json.dumps(
            {
                "as_of": "2026-07-16",
                "corroboration_run_date": None,
                "rows": [{"ticker": "RY.TO", "composite": 0.5}],
            }
        )
    )
    got = load_latest_screened(str(tmp_path))
    assert got["_source"] == "screened"
    assert got["rows"] == [{"ticker": "RY.TO", "composite": 0.5}]
    assert got["universe_size"] == 52
    assert got["diagnostics"] == {"cleared": 29, "scanned": 52}


def test_load_latest_screened_no_underlying_screen_stays_none(tmp_path):
    """If only the sidecar exists (no matching screen_<date>.json), the merge
    is a no-op -- universe_size/diagnostics stay absent rather than crashing,
    matching this project's DATA-GAP-not-fabricate discipline."""
    (tmp_path / "screened_2026-07-16.json").write_text(
        json.dumps({"as_of": "2026-07-16", "rows": []})
    )
    got = load_latest_screened(str(tmp_path))
    assert got.get("universe_size") is None
    assert got.get("diagnostics") is None


def test_load_combined_screen_merges_rows_format(tmp_path):
    us_dir = tmp_path / "us"
    ca_dir = tmp_path / "ca"
    us_dir.mkdir()
    ca_dir.mkdir()
    (us_dir / "screen_2026-07-16.json").write_text(
        json.dumps({"as_of": "2026-07-16", "universe_size": 500, "candidates": []})
    )
    (us_dir / "screened_2026-07-16.json").write_text(
        json.dumps(
            {
                "as_of": "2026-07-16",
                "rows": [{"ticker": "AAPL", "composite": 0.9}],
            }
        )
    )
    (ca_dir / "screen_2026-07-15.json").write_text(
        json.dumps({"as_of": "2026-07-15", "universe_size": 52, "candidates": []})
    )
    (ca_dir / "screened_2026-07-15.json").write_text(
        json.dumps(
            {
                "as_of": "2026-07-15",
                "rows": [{"ticker": "RY.TO", "composite": 0.95}],
            }
        )
    )
    got = load_combined_screen([str(us_dir), str(ca_dir)])
    assert got is not None
    assert [r["ticker"] for r in got["rows"]] == ["RY.TO", "AAPL"]
    assert got["as_of"] == "2026-07-16"


def test_load_combined_screen_merges_candidates_format(tmp_path):
    us_dir = tmp_path / "us"
    ca_dir = tmp_path / "ca"
    us_dir.mkdir()
    ca_dir.mkdir()
    (us_dir / "screen_2026-07-16.json").write_text(
        json.dumps(
            {
                "as_of": "2026-07-16",
                "universe_size": 500,
                "diagnostics": {"cleared": 300, "scanned": 500},
                "candidates": [{"ticker": "AAPL", "composite": 0.8}],
            }
        )
    )
    (ca_dir / "screen_2026-07-15.json").write_text(
        json.dumps(
            {
                "as_of": "2026-07-15",
                "universe_size": 52,
                "diagnostics": {"cleared": 30, "scanned": 52},
                "candidates": [{"ticker": "RY.TO", "composite": 0.85}],
            }
        )
    )
    got = load_combined_screen([str(us_dir), str(ca_dir)])
    assert got is not None
    assert [c["ticker"] for c in got["candidates"]] == ["RY.TO", "AAPL"]
    assert got["as_of"] == "2026-07-16"
    assert got["universe_size"] == 552
    assert got["diagnostics"] == {"cleared": 330, "scanned": 552}


def test_load_combined_screen_mixed_format_merges_via_candidates(tmp_path):
    us_dir = tmp_path / "us"
    ca_dir = tmp_path / "ca"
    us_dir.mkdir()
    ca_dir.mkdir()
    (us_dir / "screen_2026-07-16.json").write_text(
        json.dumps(
            {
                "as_of": "2026-07-16",
                "universe_size": 500,
                "candidates": [{"ticker": "AAPL", "composite": 0.8}],
            }
        )
    )
    (us_dir / "screened_2026-07-16.json").write_text(
        json.dumps(
            {
                "as_of": "2026-07-16",
                "rows": [{"ticker": "AAPL", "composite": 0.8}],
            }
        )
    )
    (ca_dir / "screen_2026-07-15.json").write_text(
        json.dumps(
            {
                "as_of": "2026-07-15",
                "universe_size": 52,
                "candidates": [{"ticker": "RY.TO", "composite": 0.95}],
            }
        )
    )
    got = load_combined_screen([str(us_dir), str(ca_dir)])
    assert got is not None
    assert got["_source"] != "screened" or "candidates" in got
    assert [c["ticker"] for c in got["candidates"]] == ["RY.TO", "AAPL"]
    assert got["as_of"] == "2026-07-16"
    assert got["universe_size"] == 552


def test_load_combined_screen_one_missing_degrades_to_other(tmp_path):
    us_dir = tmp_path / "us"
    ca_dir = tmp_path / "ca"
    us_dir.mkdir()
    ca_dir.mkdir()
    (us_dir / "screen_2026-07-16.json").write_text(
        json.dumps(
            {
                "as_of": "2026-07-16",
                "universe_size": 500,
                "candidates": [{"ticker": "AAPL", "composite": 0.8}],
            }
        )
    )
    got = load_combined_screen([str(us_dir), str(ca_dir)])
    assert got is not None
    assert [c["ticker"] for c in got["candidates"]] == ["AAPL"]
    assert got["universe_size"] == 500


def test_load_combined_screen_both_missing_returns_none(tmp_path):
    us_dir = tmp_path / "us"
    ca_dir = tmp_path / "ca"
    us_dir.mkdir()
    ca_dir.mkdir()
    assert load_combined_screen([str(us_dir), str(ca_dir)]) is None


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
