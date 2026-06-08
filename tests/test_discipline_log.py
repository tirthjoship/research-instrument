from datetime import datetime, timezone


def test_append_and_read_roundtrip(tmp_path):
    from application.discipline_log import append_assessments, read_assessments

    log = tmp_path / "log.jsonl"
    rows = [
        {
            "ticker": "MU",
            "verdict": "REDUCE",
            "price": 100.0,
            "as_of": "2026-06-08T00:00:00+00:00",
        }
    ]
    append_assessments(str(log), rows)
    back = read_assessments(str(log))
    assert back[0]["ticker"] == "MU" and back[0]["verdict"] == "REDUCE"


def test_resolve_flags_scores_reduce_followed_by_drop(tmp_path):
    from application.discipline_log import resolve_flags

    logged = [
        {
            "ticker": "MU",
            "verdict": "REDUCE",
            "price": 100.0,
            "as_of": datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat(),
        }
    ]
    series = {
        "MU": [
            (datetime(2026, 1, 1, tzinfo=timezone.utc), 100.0),
            (datetime(2026, 2, 5, tzinfo=timezone.utc), 80.0),
        ]
    }
    out = resolve_flags(logged, lambda t: series.get(t, []), horizon_days=21)
    assert out["resolved"] == 1
    assert 0.0 <= out["brier"] <= 1.0
    assert out["down_rate_on_reduce"] == 1.0


def test_resolve_flags_excludes_trim_from_directional_gate():
    # ADR-048: TRIM is a position-sizing action (trim a winner past its trailing
    # stop), NOT a down-call. It must NOT feed the directional Brier/gate; it is
    # tracked separately for transparency. Here the TRIM name RISES after the flag.
    from application.discipline_log import resolve_flags

    logged = [
        {
            "ticker": "WIN",
            "verdict": "TRIM",
            "price": 100.0,
            "as_of": datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat(),
        }
    ]
    series = {
        "WIN": [
            (datetime(2026, 1, 1, tzinfo=timezone.utc), 100.0),
            (datetime(2026, 2, 5, tzinfo=timezone.utc), 120.0),
        ]
    }
    out = resolve_flags(logged, lambda t: series.get(t, []), horizon_days=21)
    # directional gate is REDUCE-only — a TRIM contributes nothing to it
    assert out["resolved"] == 0
    assert out["brier"] == 0.0
    assert out["down_rate_on_reduce"] == 0.0
    # TRIM tracked separately; it went up, so its down-rate is 0
    assert out["trim_resolved"] == 1
    assert out["down_rate_on_trim"] == 0.0
