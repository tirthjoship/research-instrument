from datetime import datetime, timedelta, timezone

from domain.divergence_service import divergence_score

NOW = datetime(2026, 6, 5, tzinfo=timezone.utc)


def _prices(flat=True):
    out = []
    for i in range(40):
        day = NOW - timedelta(days=39 - i)
        price = 100.0 if flat else (100.0 + i * 2.0)
        out.append((day, price))
    return out


def test_no_buzz_is_neutral():
    assert divergence_score([], _prices(), 0.5, NOW) == 5.0


def test_rising_buzz_flat_price_scores_high():
    buzz = [NOW - timedelta(days=d) for d in (1, 2, 2, 3, 4, 5, 6)]
    assert divergence_score(buzz, _prices(flat=True), 0.7, NOW) > 6.5


def test_rising_buzz_but_price_already_ran_scores_lower():
    buzz = [NOW - timedelta(days=d) for d in (1, 2, 2, 3, 4, 5, 6)]
    high = divergence_score(buzz, _prices(flat=True), 0.7, NOW)
    ran = divergence_score(buzz, _prices(flat=False), 0.7, NOW)
    assert ran < high


def test_score_clamped_to_range():
    buzz = [NOW - timedelta(days=1)] * 50
    s = divergence_score(buzz, _prices(flat=True), 1.0, NOW)
    assert 1.0 <= s <= 10.0


# --- intensity_acceleration tests ---


def test_intensity_acceleration_rising_is_positive():
    from datetime import datetime, timedelta, timezone

    from domain.divergence_service import intensity_acceleration

    now = datetime(2026, 6, 5, tzinfo=timezone.utc)
    series = [(now - timedelta(days=d), 10.0) for d in range(8, 30)]
    series += [(now - timedelta(days=d), 90.0) for d in range(0, 7)]
    assert intensity_acceleration(series, now) > 0.5


def test_intensity_acceleration_empty_is_zero():
    from datetime import datetime, timezone

    from domain.divergence_service import intensity_acceleration

    assert intensity_acceleration([], datetime(2026, 6, 5, tzinfo=timezone.utc)) == 0.0


def test_intensity_acceleration_flat_is_near_zero():
    from datetime import datetime, timedelta, timezone

    from domain.divergence_service import intensity_acceleration

    now = datetime(2026, 6, 5, tzinfo=timezone.utc)
    series = [(now - timedelta(days=d), 50.0) for d in range(0, 30)]
    assert abs(intensity_acceleration(series, now)) < 0.01
