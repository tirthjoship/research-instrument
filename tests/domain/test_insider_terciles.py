from domain.insider_terciles import assign_terciles, slippage_bps_for_tercile


def test_assign_terciles_splits_by_adv():
    adv = {"A": 1.0, "B": 2.0, "C": 3.0, "D": 4.0, "E": 5.0, "F": 6.0}
    t = assign_terciles(adv)
    assert t["A"] == "bottom" and t["B"] == "bottom"
    assert t["C"] == "mid" and t["D"] == "mid"
    assert t["E"] == "top" and t["F"] == "top"


def test_slippage_schedule_locked():
    assert slippage_bps_for_tercile("bottom") == 150
    assert slippage_bps_for_tercile("mid") == 75
    assert slippage_bps_for_tercile("top") == 40


def test_empty_adv_returns_empty():
    assert assign_terciles({}) == {}
