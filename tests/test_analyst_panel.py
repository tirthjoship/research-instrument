from application.analyst_panel import build_analyst_panel


def test_panel_attributes_and_shows_dispersion():
    raw = {
        "analyst_recommendation_mean": 2.1,
        "analyst_count": 28,
        "targetMeanPrice": 480.0,
        "targetHighPrice": 600.0,
        "targetLowPrice": 350.0,
    }
    p = build_analyst_panel(raw, as_of="2026-06-12")
    assert p.count == 28 and p.target_high == 600.0 and p.target_low == 350.0
    assert p.as_of == "2026-06-12"
    assert p.attribution.lower().startswith("the street")  # attributed, not adopted


def test_panel_handles_missing_data_gap():
    p = build_analyst_panel({}, as_of="2026-06-12")
    assert p.count == 0 and p.data_gap is True
