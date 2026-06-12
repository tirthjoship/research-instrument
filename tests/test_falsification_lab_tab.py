import json


def test_unit_b_row_pending_when_missing(tmp_path):  # type: ignore[no-untyped-def]
    from adapters.visualization.tabs.falsification_lab import _unit_b_row

    assert _unit_b_row(str(tmp_path / "nope.json"))["verdict"] == "PENDING"


def test_unit_b_row_reads_verdict(tmp_path):  # type: ignore[no-untyped-def]
    p = tmp_path / "r.json"
    p.write_text(json.dumps({"verdict": "KILL"}))
    from adapters.visualization.tabs.falsification_lab import _unit_b_row

    assert _unit_b_row(str(p))["verdict"] == "KILL"


def test_unit_b_row_maps_real_thin_coverage_verdict(tmp_path):  # type: ignore[no-untyped-def]
    # The actual report verdict string -> practical-kill display label (ADR-053).
    p = tmp_path / "r.json"
    p.write_text(json.dumps({"verdict": "INCONCLUSIVE_THIN_COVERAGE"}))
    from adapters.visualization.tabs.falsification_lab import _unit_b_row

    assert _unit_b_row(str(p))["verdict"] == "INCONCLUSIVE → practical KILL"


def test_render_no_raise(tmp_path):  # type: ignore[no-untyped-def]
    from adapters.visualization.tabs import falsification_lab

    falsification_lab.render(
        report_path=str(tmp_path / "nope.json"),
        log_path=str(tmp_path / "nope.jsonl"),
    )
