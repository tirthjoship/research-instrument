from datetime import datetime, timedelta, timezone

from hypothesis import given
from hypothesis import strategies as st

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


# --- blended_divergence_score tests ---


def test_blended_no_data_is_neutral():
    from datetime import datetime, timezone

    from domain.divergence_service import blended_divergence_score

    now = datetime(2026, 6, 5, tzinfo=timezone.utc)
    assert blended_divergence_score([], [], [], 0.5, now) == 5.0


def test_blended_events_only_matches_event_score():
    from datetime import datetime, timedelta, timezone

    from domain.divergence_service import blended_divergence_score, divergence_score

    now = datetime(2026, 6, 5, tzinfo=timezone.utc)
    buzz = [now - timedelta(days=d) for d in range(0, 5)]
    prices = [(now - timedelta(days=d), 100.0) for d in range(0, 40)]
    blended = blended_divergence_score(buzz, [], prices, 0.6, now)
    event_only = divergence_score(buzz, prices, 0.6, now)
    assert abs(blended - event_only) < 1e-6


def test_blended_intensity_only_uses_intensity():
    from datetime import datetime, timedelta, timezone

    from domain.divergence_service import blended_divergence_score

    now = datetime(2026, 6, 5, tzinfo=timezone.utc)
    intensity = [(now - timedelta(days=d), 10.0) for d in range(8, 30)]
    intensity += [(now - timedelta(days=d), 90.0) for d in range(0, 7)]
    prices = [(now - timedelta(days=d), 100.0) for d in range(0, 40)]
    score = blended_divergence_score([], intensity, prices, 0.5, now)
    assert score > 6.0


def test_blended_in_range():
    from datetime import datetime, timedelta, timezone

    from domain.divergence_service import blended_divergence_score

    now = datetime(2026, 6, 5, tzinfo=timezone.utc)
    buzz = [now - timedelta(days=d) for d in range(0, 5)]
    intensity = [(now - timedelta(days=d), 90.0) for d in range(0, 7)]
    prices = [(now - timedelta(days=d), 100.0) for d in range(0, 40)]
    score = blended_divergence_score(buzz, intensity, prices, 1.0, now)
    assert 1.0 <= score <= 10.0


@given(
    sentiment=st.floats(min_value=0.0, max_value=1.0),
    n_buzz=st.integers(min_value=0, max_value=20),
    n_intensity=st.integers(min_value=0, max_value=20),
)
def test_blended_always_in_range(sentiment, n_buzz, n_intensity):
    from datetime import datetime, timedelta, timezone

    from domain.divergence_service import blended_divergence_score

    now = datetime(2026, 6, 5, tzinfo=timezone.utc)
    buzz = [now - timedelta(days=i % 30) for i in range(n_buzz)]
    intensity = [(now - timedelta(days=i % 30), 50.0) for i in range(n_intensity)]
    prices = [(now - timedelta(days=d), 100.0) for d in range(0, 40)]
    score = blended_divergence_score(buzz, intensity, prices, sentiment, now)
    assert 1.0 <= score <= 10.0


@given(extra_recent=st.integers(min_value=0, max_value=15))
def test_blended_monotonic_in_attention(extra_recent):
    from datetime import datetime, timedelta, timezone

    from domain.divergence_service import blended_divergence_score

    now = datetime(2026, 6, 5, tzinfo=timezone.utc)
    prices = [(now - timedelta(days=d), 100.0) for d in range(0, 40)]
    base = [now - timedelta(days=20) for _ in range(3)]
    more = base + [now - timedelta(hours=1) for _ in range(extra_recent)]
    s_base = blended_divergence_score(base, [], prices, 0.5, now)
    s_more = blended_divergence_score(more, [], prices, 0.5, now)
    assert s_more >= s_base - 1e-9


# --- has_min_history tests ---


def test_has_min_history_true_when_span_sufficient():
    from datetime import datetime, timedelta, timezone

    from domain.divergence_service import has_min_history

    now = datetime(2026, 6, 5, tzinfo=timezone.utc)
    series = [(now - timedelta(days=d), 1.0) for d in range(0, 25)]
    assert has_min_history(series, now, min_days=21) is True


def test_has_min_history_false_when_too_thin():
    from datetime import datetime, timedelta, timezone

    from domain.divergence_service import has_min_history

    now = datetime(2026, 6, 5, tzinfo=timezone.utc)
    series = [(now - timedelta(days=d), 1.0) for d in range(0, 5)]
    assert has_min_history(series, now, min_days=21) is False


def test_has_min_history_false_when_empty():
    from datetime import datetime, timezone

    from domain.divergence_service import has_min_history

    now = datetime(2026, 6, 5, tzinfo=timezone.utc)
    assert has_min_history([], now, min_days=21) is False
