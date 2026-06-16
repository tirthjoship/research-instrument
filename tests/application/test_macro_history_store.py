from application.macro_history_store import (
    append_systematic_share,
    load_systematic_share_history,
)


def test_append_and_load(tmp_path):
    p = tmp_path / "macro_history.jsonl"
    append_systematic_share(str(p), "2026-06-01", 0.64)
    append_systematic_share(str(p), "2026-06-08", 0.71)
    hist = load_systematic_share_history(str(p))
    assert hist == [("2026-06-01", 0.64), ("2026-06-08", 0.71)]


def test_load_missing_is_empty(tmp_path):
    assert load_systematic_share_history(str(tmp_path / "none.jsonl")) == []


def test_load_skips_malformed_lines(tmp_path):
    p = tmp_path / "h.jsonl"
    p.write_text(
        '{"as_of": "2026-06-01", "systematic_share": 0.5}\n'
        "not json at all\n"
        '{"as_of": "2026-06-08", "systematic_share": 0.6}\n'
        "\n"
    )
    hist = load_systematic_share_history(str(p))
    assert hist == [("2026-06-01", 0.5), ("2026-06-08", 0.6)]
