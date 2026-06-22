from datetime import date

from application.corroboration_sanity import dated_source_hit_rate


def test_hit_rate_on_dated_events_fixture() -> None:
    events = [
        ("AAA", date(2026, 3, 1), "bullish", 0.04),
        ("BBB", date(2026, 3, 1), "bullish", -0.02),
    ]
    res = dated_source_hit_rate(events)
    assert res["n"] == 2
    assert res["hit_rate"] == 0.5
    assert res["label"] == "SANITY-NOT-VERDICT"
