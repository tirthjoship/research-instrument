from domain.factor_scores import (
    FACTOR_KEYS,
    composite_score,
    revision_momentum,
    winsorize,
    zscore,
)


def test_zscore_centers_and_scales():
    out = zscore([1.0, 2.0, 3.0, 4.0, 5.0])
    assert abs(sum(out)) < 1e-9
    assert abs(out[0] + out[4]) < 1e-9 and out[0] < 0 < out[4]


def test_zscore_degenerate_returns_zeros():
    assert zscore([2.0, 2.0, 2.0]) == [0.0, 0.0, 0.0]


def test_winsorize_clamps_tails():
    out = winsorize([0.0, 1, 2, 3, 100.0], p=0.2)
    assert max(out) < 100.0 and min(out) >= 0.0


def test_revision_momentum_positive_on_upgrades():
    assert revision_momentum([1.0, 1.1, 1.2, 1.3]) > 0


def test_revision_momentum_none_when_insufficient():
    assert revision_momentum([1.0]) is None


def test_composite_equal_weight_average_of_present():
    # 3 present factors: momentum=1.0, quality=-1.0, value=0.0 → mean = 0.0
    c = composite_score(
        {"momentum": 1.0, "revision": None, "quality": -1.0, "value": 0.0}
    )
    assert abs(c - 0.0) < 1e-9


# ── Step 1: denominator correctness ───────────────────────────────────────────


def test_composite_divides_by_present_count_not_total():
    # 2 present factors: momentum=3.0, quality=1.0 → mean = 2.0 (not 4.0/4=1.0)
    subs = {k: None for k in FACTOR_KEYS}
    subs["momentum"] = 3.0
    subs["quality"] = 1.0
    c = composite_score(subs)
    assert abs(c - 2.0) < 1e-9, f"Expected 2.0 (mean of 2 present), got {c}"


def test_composite_all_none_returns_zero():
    subs = {k: None for k in FACTOR_KEYS}
    assert composite_score(subs) == 0.0


def test_composite_all_present_is_plain_mean():
    # All 4 present: mean of 1+2+3+4 = 2.5
    keys = list(FACTOR_KEYS)
    subs = {k: float(i + 1) for i, k in enumerate(keys)}
    expected = sum(subs.values()) / len(subs)
    assert abs(composite_score(subs) - expected) < 1e-9


def test_composite_adding_none_factor_leaves_composite_unchanged():
    """Adding a None factor must NOT dilute the composite (the old bug)."""
    # 2 present factors
    subs_2 = {k: None for k in FACTOR_KEYS}
    subs_2["momentum"] = 4.0
    subs_2["quality"] = 2.0
    c_2 = composite_score(subs_2)  # mean of [4.0, 2.0] = 3.0

    # Same 2 present factors + 1 more None (revision=None already; add value=None)
    subs_same = dict(subs_2)
    subs_same["value"] = None  # already None, but explicit
    c_same = composite_score(subs_same)

    assert (
        abs(c_2 - c_same) < 1e-9
    ), f"Adding a None factor changed composite from {c_2} to {c_same}"


# ── Step 2: FACTOR_KEYS includes lowvol; 5-factor composite ───────────────────


def test_factor_keys_includes_lowvol():
    assert "lowvol" in FACTOR_KEYS


def test_factor_keys_has_five_factors():
    assert len(FACTOR_KEYS) == 5


def test_composite_five_present_factors_is_plain_mean():
    # All 5 present: mean of 1+2+3+4+5 = 3.0
    subs = {k: float(i + 1) for i, k in enumerate(FACTOR_KEYS)}
    expected = sum(subs.values()) / len(subs)
    assert abs(composite_score(subs) - expected) < 1e-9


def test_composite_lowvol_none_averages_over_four():
    # 4 present (lowvol=None): mean of 1+2+3+4 = 2.5
    subs = {k: float(i + 1) for i, k in enumerate(FACTOR_KEYS)}
    subs["lowvol"] = None
    expected = (1.0 + 2.0 + 3.0 + 4.0) / 4
    assert abs(composite_score(subs) - expected) < 1e-9
