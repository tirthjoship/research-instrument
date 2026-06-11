"""tests/application/test_fetch_health.py"""

from application.fetch_health import FetchHealth


def test_counts_and_summary() -> None:
    h = FetchHealth()
    h.record_ok("AC.TO")
    h.record_ok("BMO.TO")
    h.record_no_data("NEW.TO")
    h.record_failed("BROKE.TO")
    h.record_pruned("DEAD.TO")
    assert h.summary_line() == ("fetched OK=2 no-data=1 FAILED=1 pruned=1")
    assert h.any_failed() is True
    assert h.failed_tickers == ["BROKE.TO"]


def test_clean_run_not_failed() -> None:
    h = FetchHealth()
    h.record_ok("AC.TO")
    h.record_no_data("NEW.TO")
    h.record_pruned("DEAD.TO")
    assert h.any_failed() is False
    assert h.summary_line() == "fetched OK=1 no-data=1 FAILED=0 pruned=1"
