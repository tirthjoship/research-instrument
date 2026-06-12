"""Cockpit assembler renders all five sections in priority order."""

from tests.cockpit.fake_st import FakeSt


def test_cockpit_renders_sections_in_priority_order(monkeypatch, tmp_path):
    from adapters.visualization.cockpit import cockpit

    sink: list[str] = []
    fake = FakeSt(sink)
    # each section module gets the same fake st
    for mod_name in ("_danger", "_calls", "_retro", "_discover", "_lookup"):
        mod = getattr(cockpit, mod_name)
        monkeypatch.setattr(mod, "st", fake, raising=False)
    monkeypatch.setattr(cockpit, "st", fake, raising=False)

    cockpit.render(
        summary_path=str(tmp_path / "missing.json"),
        reports_dir=str(tmp_path),
        holdings_path=str(tmp_path / "missing.csv"),
        discipline_log_path=str(tmp_path / "log.jsonl"),
        adherence_log_path=str(tmp_path / "adh.jsonl"),
        history_dir=str(tmp_path / "hist"),
    )

    joined = " ".join(sink)
    # all five anchors present even with NO data (graceful empty states)
    anchors = ["cp-danger", "cp-calls", "cp-retro", "cp-discover", "cp-lookup"]
    positions = [joined.find(a) for a in anchors]
    assert all(p >= 0 for p in positions), f"missing section anchors: {positions}"
    assert positions == sorted(positions), "sections out of priority order"
