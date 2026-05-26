"""Property-based tests for domain invariants using Hypothesis."""

from hypothesis import assume, given
from hypothesis import strategies as st

from domain.exceptions import InvalidMarketDataError, InvalidPredictionError
from domain.models import MultiHorizonPrediction, RecommendationGrade, Sentiment
from domain.services import classify_horizon, grade_from_horizons


@given(
    score=st.floats(min_value=-1.0, max_value=1.0),
    conf=st.floats(min_value=0.0, max_value=1.0),
)
def test_sentiment_score_bounded(score: float, conf: float) -> None:
    assume(not (score != score))
    assume(not (conf != conf))
    s = Sentiment(
        source="test",
        timestamp=__import__("datetime").datetime.now(),
        sentiment_score=score,
        confidence=conf,
    )
    assert -1.0 <= s.sentiment_score <= 1.0


@given(score=st.floats().filter(lambda x: x < -1.0 or x > 1.0))
def test_sentiment_rejects_out_of_bounds(score: float) -> None:
    assume(not (score != score))
    try:
        Sentiment(
            source="test",
            timestamp=__import__("datetime").datetime.now(),
            sentiment_score=score,
            confidence=0.5,
        )
        assert False, "Should have raised"
    except InvalidMarketDataError:
        pass


@given(
    r2=st.floats(min_value=-0.2, max_value=0.2),
    r5=st.floats(min_value=-0.2, max_value=0.2),
    r10=st.floats(min_value=-0.2, max_value=0.2),
)
def test_grading_always_returns_valid_grade(r2: float, r5: float, r10: float) -> None:
    assume(all(x == x for x in (r2, r5, r10)))
    pred = MultiHorizonPrediction(
        predicted_return_2d=r2,
        predicted_return_5d=r5,
        predicted_return_10d=r10,
        confidence_2d=0.5,
        confidence_5d=0.5,
        confidence_10d=0.5,
    )
    grade, signals = grade_from_horizons(pred)
    assert isinstance(grade, RecommendationGrade)
    assert set(signals.keys()) == {"2d", "5d", "10d"}
    assert all(s in ("bullish", "neutral", "bearish") for s in signals.values())


@given(
    r2=st.floats(min_value=-0.2, max_value=0.2),
    r5=st.floats(min_value=-0.2, max_value=0.2),
    r10=st.floats(min_value=-0.2, max_value=0.2),
)
def test_grading_symmetric_signals(r2: float, r5: float, r10: float) -> None:
    assume(all(x == x for x in (r2, r5, r10)))
    mirror = {"bullish": "bearish", "bearish": "bullish", "neutral": "neutral"}
    pred_pos = MultiHorizonPrediction(
        predicted_return_2d=r2,
        predicted_return_5d=r5,
        predicted_return_10d=r10,
        confidence_2d=0.5,
        confidence_5d=0.5,
        confidence_10d=0.5,
    )
    pred_neg = MultiHorizonPrediction(
        predicted_return_2d=-r2,
        predicted_return_5d=-r5,
        predicted_return_10d=-r10,
        confidence_2d=0.5,
        confidence_5d=0.5,
        confidence_10d=0.5,
    )
    _, signals_pos = grade_from_horizons(pred_pos)
    _, signals_neg = grade_from_horizons(pred_neg)
    for h in ("2d", "5d", "10d"):
        assert signals_neg[h] == mirror[signals_pos[h]]


@given(
    ret=st.floats(min_value=0.001, max_value=1.0),
    threshold=st.floats(min_value=0.001, max_value=0.5),
)
def test_classify_horizon_positive_above_threshold_is_bullish(
    ret: float, threshold: float
) -> None:
    assume(ret > threshold)
    assert classify_horizon(ret, threshold) == "bullish"


@given(
    ret=st.floats(min_value=-1.0, max_value=-0.001),
    threshold=st.floats(min_value=0.001, max_value=0.5),
)
def test_classify_horizon_negative_below_neg_threshold_is_bearish(
    ret: float, threshold: float
) -> None:
    assume(ret < -threshold)
    assert classify_horizon(ret, threshold) == "bearish"


@given(
    c2=st.floats(min_value=0.0, max_value=1.0),
    c5=st.floats(min_value=0.0, max_value=1.0),
    c10=st.floats(min_value=0.0, max_value=1.0),
)
def test_multi_horizon_confidence_always_valid(
    c2: float, c5: float, c10: float
) -> None:
    assume(all(x == x for x in (c2, c5, c10)))
    pred = MultiHorizonPrediction(
        predicted_return_2d=0.01,
        predicted_return_5d=0.02,
        predicted_return_10d=0.03,
        confidence_2d=c2,
        confidence_5d=c5,
        confidence_10d=c10,
    )
    assert 0.0 <= pred.confidence_2d <= 1.0


@given(bad_conf=st.floats().filter(lambda x: x == x and (x < 0.0 or x > 1.0)))
def test_multi_horizon_rejects_bad_confidence(bad_conf: float) -> None:
    try:
        MultiHorizonPrediction(
            predicted_return_2d=0.01,
            predicted_return_5d=0.02,
            predicted_return_10d=0.03,
            confidence_2d=bad_conf,
            confidence_5d=0.5,
            confidence_10d=0.5,
        )
        assert False, "Should have raised"
    except InvalidPredictionError:
        pass
