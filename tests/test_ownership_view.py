"""Contract tests for ownership_view — 5 tests, all must pass pristine."""

import inspect
from types import SimpleNamespace

from adapters.visualization.tabs.stock_analysis import ownership_view
from domain.fit import FORBIDDEN_WORDS


def _result(ticker="NVDA", **info_over):
    info = {"heldPercentInstitutions": 0.66, "heldPercentInsiders": 0.04}
    info.update(info_over)
    return SimpleNamespace(
        info=info, insider_transactions=[{"value": -48_000_000}], ticker=ticker
    )


def test_six_metrics_inst_and_netq():
    v = ownership_view.build_ownership_view(_result())
    assert len(v["metrics"]) == 6
    inst = next(m for m in v["metrics"] if "nstitution" in m.label)
    assert "66" in inst.value


def test_short_interest_datagap_when_no_short_shares():
    # no shortPercentOfFloat AND no sharesShort -> genuine gap
    v = ownership_view.build_ownership_view(_result())
    si = next(m for m in v["metrics"] if "Short" in m.label)
    assert si.value == "—"


def test_short_interest_computed_from_primitives():
    # yfinance often omits shortPercentOfFloat but carries sharesShort + floatShares
    v = ownership_view.build_ownership_view(
        _result(sharesShort=250e6, floatShares=23.5e9)
    )
    si = next(m for m in v["metrics"] if "Short" in m.label)
    assert si.value == "1.1%"  # 250M / 23.5B


def test_days_to_cover_computed_from_primitives():
    v = ownership_view.build_ownership_view(
        _result(sharesShort=250e6, averageDailyVolume10Day=250e6)
    )
    dtc = next(m for m in v["metrics"] if "cover" in m.label.lower())
    assert dtc.value == "1.0d"  # 250M / 250M


def test_institutional_tile_green_when_majority_held():
    v = ownership_view.build_ownership_view(_result())  # 66% institutional
    inst = next(m for m in v["metrics"] if "nstitution" in m.label)
    assert inst.tone == "green"


def test_public_float_amber_when_thin():
    v = ownership_view.build_ownership_view(
        _result(heldPercentInstitutions=0.88, heldPercentInsiders=0.05)
    )  # public float ~7% -> thin
    flt = next(m for m in v["metrics"] if "float" in m.label.lower())
    assert flt.tone == "amber"


def test_short_interest_amber_when_elevated():
    v = ownership_view.build_ownership_view(_result(shortPercentOfFloat=0.08))
    si = next(m for m in v["metrics"] if "Short" in m.label)
    assert si.tone == "amber"


def test_insider_net_tile_stays_grey_adr053():
    v = ownership_view.build_ownership_view(_result())
    net = next(m for m in v["metrics"] if "net" in m.label.lower())
    assert net.tone == "grey"  # falsified signal — never coloured good/bad


def test_insiders_chip_grey_and_falsified():
    v = ownership_view.build_ownership_view(_result())
    assert "INSIDERS" in v["chips"] and "falsified" in v["chips"].lower()
    assert "t-grey" in v["chips"] or "grey" in v["chips"].lower()


def test_panel_renders():
    assert "Ownership" in ownership_view.build_ownership_panel(_result())


def test_insider_net_q_tile_uses_latest_quarter_not_alltime_sum():
    # Three quarters of activity: the strip tile is labelled "Insider net Q"
    # and its tooltip says "reported for the latest quarter" — it must match
    # the same latest-quarter bucket the trend chart plots (-$186M, Q2 2026),
    # not the sum across all three quarters (-$396M).
    result = SimpleNamespace(
        info={"heldPercentInstitutions": 0.66, "heldPercentInsiders": 0.04},
        insider_transactions=[
            {"value": -186e6, "Start Date": "2026-06-18"},
            {"value": -120e6, "Start Date": "2026-03-15"},
            {"value": -90e6, "Start Date": "2025-12-10"},
        ],
        ticker="NVDA",
    )
    v = ownership_view.build_ownership_view(result)
    net = next(m for m in v["metrics"] if "net" in m.label.lower())
    assert net.value == "-$186M"


def test_insider_quarterly_net_aggregates_by_quarter():
    qn = ownership_view._insider_quarterly_net(
        [
            {"value": -186e6, "Start Date": "2026-06-18"},
            {"value": -120e6, "Start Date": "2026-03-15"},
            {"value": -90e6, "Start Date": "2025-12-10"},
        ]
    )
    assert len(qn) == 3
    assert qn[0][0] == "Q4 2025" and qn[-1][0] == "Q2 2026"  # chronological
    assert qn[-1][1] == -186e6  # latest quarter net is signed (reducing)


def test_indian_ticker_insider_net_shows_rupee_symbol():
    """An NSE-suffixed ticker's Insider net Q tile must show the rupee symbol,
    not bare $ — bare $ would misrepresent INR amounts as USD."""
    v = ownership_view.build_ownership_view(_result(ticker="RELIANCE.NS"))
    net = next(m for m in v["metrics"] if "net" in m.label.lower())
    assert "₹" in net.value
    assert "$" not in net.value


def test_no_streamlit_and_clean():
    src = inspect.getsource(ownership_view)
    assert "import streamlit" not in src
    low = src.lower()
    for w in FORBIDDEN_WORDS:
        assert w not in low
