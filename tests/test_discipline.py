def test_conditional_vol_signal_zero_when_trend_healthy():
    from domain.discipline import conditional_vol_signal

    assert (
        conditional_vol_signal(recent_vol=0.04, baseline_vol=0.02, trend_health=1.5)
        == 0.0
    )


def test_conditional_vol_signal_zero_when_vol_not_elevated():
    from domain.discipline import conditional_vol_signal

    assert (
        conditional_vol_signal(recent_vol=0.01, baseline_vol=0.02, trend_health=-1.0)
        == 0.0
    )


def test_conditional_vol_signal_positive_when_vol_up_and_trend_down():
    from domain.discipline import conditional_vol_signal

    sig = conditional_vol_signal(recent_vol=0.04, baseline_vol=0.02, trend_health=-1.0)
    assert 0.0 < sig <= 1.0


def test_risk_asymmetry_fields():
    from domain.discipline import risk_asymmetry

    out = risk_asymmetry(price=100.0, trailing_stop=90.0, recent_high=130.0)
    assert abs(out["downside_to_stop"] - 0.10) < 1e-9
    assert abs(out["upside_to_recover"] - 0.30) < 1e-9
