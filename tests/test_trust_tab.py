import json


def test_unit_b_row_pending_when_missing(tmp_path):  # type: ignore[no-untyped-def]
    from adapters.visualization.tabs.trust import _unit_b_row

    assert _unit_b_row(str(tmp_path / "nope.json"))["verdict"] == "PENDING"


def test_unit_b_row_reads_verdict(tmp_path):  # type: ignore[no-untyped-def]
    p = tmp_path / "r.json"
    p.write_text(json.dumps({"verdict": "KILL"}))
    from adapters.visualization.tabs.trust import _unit_b_row

    assert _unit_b_row(str(p))["verdict"] == "KILL"


def test_unit_b_row_maps_real_thin_coverage_verdict(tmp_path):  # type: ignore[no-untyped-def]
    # The actual report verdict string -> practical-kill display label (ADR-053).
    p = tmp_path / "r.json"
    p.write_text(json.dumps({"verdict": "INCONCLUSIVE_THIN_COVERAGE"}))
    from adapters.visualization.tabs.trust import _unit_b_row

    assert _unit_b_row(str(p))["verdict"] == "INCONCLUSIVE → practical KILL"


def test_render_no_raise(tmp_path):  # type: ignore[no-untyped-def]
    from adapters.visualization.tabs import trust

    trust.render(
        report_path=str(tmp_path / "nope.json"),
        log_path=str(tmp_path / "nope.jsonl"),
    )


def test_render_no_raise_full(tmp_path):  # type: ignore[no-untyped-def]
    """Covers trophy grid (3-col), four-rules cards (2x2), and glossary expander."""
    import json as _json

    report = tmp_path / "r.json"
    report.write_text(_json.dumps({"verdict": "INCONCLUSIVE_THIN_COVERAGE"}))
    log = tmp_path / "discipline.jsonl"
    log.write_text(_json.dumps({"as_of": "2026-06-01", "action": "REDUCE"}) + "\n")
    from adapters.visualization.tabs import trust

    trust.render(
        report_path=str(report),
        log_path=str(log),
    )
