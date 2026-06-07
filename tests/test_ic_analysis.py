def test_ic_perfect_rank_agreement_is_one():
    from application.ic_analysis import spearman_ic

    signal = [1.0, 2.0, 3.0, 4.0, 5.0]
    fwd = [0.1, 0.2, 0.3, 0.4, 0.5]
    assert abs(spearman_ic(signal, fwd) - 1.0) < 1e-9


def test_ic_perfect_disagreement_is_minus_one():
    from application.ic_analysis import spearman_ic

    signal = [1.0, 2.0, 3.0, 4.0, 5.0]
    fwd = [0.5, 0.4, 0.3, 0.2, 0.1]
    assert abs(spearman_ic(signal, fwd) + 1.0) < 1e-9


def test_ic_too_few_points_is_nan_skipped():
    import math

    from application.ic_analysis import spearman_ic

    assert math.isnan(spearman_ic([1.0], [0.1]))


def test_aggregate_ic_summarizes_per_date_series():
    from application.ic_analysis import aggregate_ic

    per_date = [
        ([1.0, 2.0, 3.0], [0.1, 0.2, 0.3]),  # IC = +1
        ([1.0, 2.0, 3.0], [0.3, 0.2, 0.1]),  # IC = -1
        ([1.0, 2.0, 3.0], [0.1, 0.2, 0.3]),  # IC = +1
    ]
    out = aggregate_ic(per_date, min_names=3)
    assert out["n_dates"] == 3
    assert abs(out["mean_ic"] - (1.0 - 1.0 + 1.0) / 3.0) < 1e-9
    assert out["pct_positive_dates"] == 2 / 3
    assert out["ic_series"] == [1.0, -1.0, 1.0]


def test_aggregate_ic_skips_thin_dates():
    from application.ic_analysis import aggregate_ic

    per_date = [([1.0, 2.0], [0.1, 0.2]), ([1.0, 2.0, 3.0], [0.1, 0.2, 0.3])]
    out = aggregate_ic(per_date, min_names=3)
    assert out["n_dates"] == 1  # the 2-name date is skipped


def test_rank_tie_handling_produces_average_ranks():
    from application.ic_analysis import _rank

    # sorted asc: [1.0(rank1), 5.0, 5.0(ranks 2,3 → avg 2.5)]
    # input [5, 5, 1] → [2.5, 2.5, 1.0]
    result = _rank([5.0, 5.0, 1.0])
    assert result == [2.5, 2.5, 1.0]


def test_ic_degenerate_all_equal_signal_returns_nan():
    import math

    from application.ic_analysis import spearman_ic

    assert math.isnan(spearman_ic([2.0, 2.0, 2.0], [0.1, 0.2, 0.3]))


def test_ic_nan_input_propagates_nan():
    import math

    from application.ic_analysis import spearman_ic

    assert math.isnan(spearman_ic([float("nan"), 2.0, 3.0], [0.1, 0.2, 0.3]))
