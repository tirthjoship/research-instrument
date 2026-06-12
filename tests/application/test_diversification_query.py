import math


def _series(values):
    return [float(v) for v in values]


def test_ranks_lowest_abs_correlation_first():
    from application.diversification_query import rank_by_diversification

    factor = _series([100, 101, 99, 102, 103, 101, 104])
    mirror = _series([50, 50.5, 49.5, 51, 51.5, 50.5, 52])  # ~corr +1
    inverse = _series([50, 49.5, 50.5, 49, 48.5, 49.5, 48])  # ~corr -1
    flat = _series([50, 50.2, 49.9, 50.1, 50.0, 50.15, 49.95])  # ~corr 0

    ranked = rank_by_diversification(
        factor_series=factor,
        candidate_series={"MIRROR": mirror, "INVERSE": inverse, "FLAT": flat},
    )
    assert ranked[0][0] == "FLAT"
    assert {r[0] for r in ranked} == {"MIRROR", "INVERSE", "FLAT"}
    for _, corr in ranked:
        assert -1.0 <= corr <= 1.0 and not math.isnan(corr)


def test_skips_candidates_with_short_series():
    from application.diversification_query import rank_by_diversification

    factor = _series([100, 101, 99, 102, 103])
    ranked = rank_by_diversification(
        factor_series=factor,
        candidate_series={"SHORT": _series([1, 2]), "OK": _series([5, 6, 5, 7, 6])},
    )
    assert [r[0] for r in ranked] == ["OK"]


def test_empty_inputs_return_empty():
    from application.diversification_query import rank_by_diversification

    assert rank_by_diversification(factor_series=[], candidate_series={}) == []
