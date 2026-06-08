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


def test_disposition_risk_broken_trend_at_loss():
    from domain.discipline import is_disposition_risk

    assert is_disposition_risk(trend_health=-2.0, unrealized_pct=-0.30) is True
    assert is_disposition_risk(trend_health=1.0, unrealized_pct=-0.30) is False
    assert is_disposition_risk(trend_health=-2.0, unrealized_pct=0.50) is False


def test_winner_past_stop():
    from domain.discipline import is_winner_past_stop

    assert is_winner_past_stop(trend_health=1.5, price=95.0, trailing_stop=96.0) is True
    assert (
        is_winner_past_stop(trend_health=1.5, price=100.0, trailing_stop=96.0) is False
    )
    assert (
        is_winner_past_stop(trend_health=-1.0, price=95.0, trailing_stop=96.0) is False
    )


def test_grade_reduce_when_broken_trend_loss_and_market_ok():
    from domain.discipline import Verdict, grade_position

    v, conf, abstained = grade_position(
        trend_health=-3.0,
        vol_signal=0.5,
        relative_strength=-0.2,
        disposition=True,
        winner_past_stop=False,
        market_trend_health=1.0,
    )
    assert v == Verdict.REDUCE
    assert abstained is False
    assert 0.0 < conf <= 1.0


def test_grade_abstains_to_review_when_market_also_broken():
    from domain.discipline import Verdict, grade_position

    v, conf, abstained = grade_position(
        trend_health=-3.0,
        vol_signal=0.5,
        relative_strength=0.1,
        disposition=True,
        winner_past_stop=False,
        market_trend_health=-2.5,
    )
    assert v == Verdict.REVIEW
    assert abstained is True


def test_grade_trim_for_winner_past_stop():
    from domain.discipline import Verdict, grade_position

    v, conf, abstained = grade_position(
        trend_health=1.2,
        vol_signal=0.0,
        relative_strength=0.1,
        disposition=False,
        winner_past_stop=True,
        market_trend_health=1.0,
    )
    assert v == Verdict.TRIM


def test_grade_hold_when_in_trend():
    from domain.discipline import Verdict, grade_position

    v, conf, abstained = grade_position(
        trend_health=2.5,
        vol_signal=0.0,
        relative_strength=0.3,
        disposition=False,
        winner_past_stop=False,
        market_trend_health=1.0,
    )
    assert v in (Verdict.HOLD, Verdict.ADD_OK)


def test_grade_review_when_trend_health_none():
    from domain.discipline import Verdict, grade_position

    v, conf, abstained = grade_position(
        trend_health=None,
        vol_signal=0.0,
        relative_strength=None,
        disposition=False,
        winner_past_stop=False,
        market_trend_health=None,
    )
    assert v == Verdict.REVIEW
    assert abstained is True
