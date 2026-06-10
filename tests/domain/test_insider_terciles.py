from domain.insider_terciles import slippage_bps_for_tercile, tercile_for_event


def test_slippage_schedule_locked():
    assert slippage_bps_for_tercile("bottom") == 150
    assert slippage_bps_for_tercile("mid") == 75
    assert slippage_bps_for_tercile("top") == 40


def test_first_event_is_bottom():
    # Singleton distribution: rank 0/1 -> bottom (conservative).
    assert tercile_for_event([], 5.0) == "bottom"


def test_expanding_distribution_bins_by_rank():
    prior = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert tercile_for_event(prior, 0.5) == "bottom"  # rank 0/6
    assert tercile_for_event(prior, 2.5) == "mid"  # rank 2/6
    assert tercile_for_event(prior, 6.0) == "top"  # rank 5/6
    assert tercile_for_event(prior, 3.5) == "mid"  # rank 3/6
    assert tercile_for_event(prior, 4.5) == "top"  # rank 4/6 = 2/3 boundary -> top


def test_ties_bin_low():
    # Equal ADVs take the first-occurrence rank -> lower bin (conservative
    # toward bottom, the primary-hypothesis tercile).
    assert tercile_for_event([2.0, 2.0], 2.0) == "bottom"  # rank 0/3


def test_same_adv_different_history_bins_differently():
    # The M2 point: the SAME adv must bin against ITS OWN point-in-time
    # distribution, not a pooled one.
    assert tercile_for_event([10.0, 20.0], 5.0) == "bottom"
    assert tercile_for_event([1.0, 2.0], 5.0) == "top"
