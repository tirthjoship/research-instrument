from adapters.visualization.components.treemap import LENSES, lens_color


def test_lenses_exact():
    assert LENSES == ("pnl", "today", "verdict")


def test_pnl_bins_capped():
    # deep green for big winner (capped at +25 band)
    assert (
        lens_color({"pnl": 75.0, "today": 1.0, "verdict": "HOLD"}, "pnl")[0]
        == "#15803D"
    )
    # deep red for big loser
    assert (
        lens_color({"pnl": -40.0, "today": -1.0, "verdict": "REDUCE"}, "pnl")[0]
        == "#DC2626"
    )
    # pale green just above zero
    assert (
        lens_color({"pnl": 2.0, "today": 0.0, "verdict": "HOLD"}, "pnl")[0] == "#BBF7D0"
    )


def test_verdict_lens_colors():
    assert (
        lens_color({"pnl": 0, "today": 0, "verdict": "REDUCE"}, "verdict")[0]
        == "#DC2626"
    )
    assert (
        lens_color({"pnl": 0, "today": 0, "verdict": "REVIEW"}, "verdict")[0]
        == "#FBBF24"
    )
    assert (
        lens_color({"pnl": 0, "today": 0, "verdict": "HOLD"}, "verdict")[0] == "#22C55E"
    )


def test_returns_bg_and_fg():
    bg, fg = lens_color({"pnl": 75.0, "today": 0, "verdict": "HOLD"}, "pnl")
    assert bg == "#15803D" and fg == "#FFFFFF"
