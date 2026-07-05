import inspect
from types import SimpleNamespace

from adapters.visualization.tabs.stock_analysis import supply_chain_view
from domain.fit import FORBIDDEN_WORDS


def _result(group: bool = True, co_movement: float | None = None) -> SimpleNamespace:
    g = (
        {
            "group": "AI semis",
            "leaders": ["NVDA"],
            "followers": ["AMD", "AVGO"],
            "typical_lag_days": 3,
            "notes": "leaders move first",
            "_is_leader": True,
            "member_moves": {"NVDA": 2.0, "AMD": -1.0, "AVGO": 1.0},
            **({"co_movement": co_movement} if co_movement is not None else {}),
        }
        if group
        else None
    )
    return SimpleNamespace(supply_chain_group=g, ticker="NVDA", market_cap=4.2e12)


def test_group_role_members_lag() -> None:
    v = supply_chain_view.build_supply_chain_view(_result())
    assert any("Group" in m.label for m in v["metrics"])
    assert any("ole" in m.label for m in v["metrics"])  # Role


def test_comovement_datagap_when_not_computed() -> None:
    v = supply_chain_view.build_supply_chain_view(_result())
    cm = next(m for m in v["metrics"] if "o-move" in m.label or "ovement" in m.label)
    assert cm.value == "—"


def test_comovement_real_value_when_computed() -> None:
    v = supply_chain_view.build_supply_chain_view(_result(co_movement=0.78))
    cm = next(m for m in v["metrics"] if "o-move" in m.label or "ovement" in m.label)
    assert cm.value == "0.78"
    assert "not wired" not in cm.sub
    assert "Co-movement 0.78" in v["reframe"]


def test_comovement_high_value_flags_caution_verdict() -> None:
    v = supply_chain_view.build_supply_chain_view(_result(co_movement=0.78))
    assert any(vv.tone == "cau" and "0.78" in vv.text for vv in v["verdicts"])


def test_member_moves_caption_is_accurate() -> None:
    html = supply_chain_view.build_supply_chain_panel(_result())
    assert "1-day" in html
    assert "5-day" not in html


def test_none_group_degrades() -> None:
    assert "Supply" in supply_chain_view.build_supply_chain_panel(_result(group=False))


def test_panel_renders() -> None:
    assert "Supply" in supply_chain_view.build_supply_chain_panel(_result())


def test_no_streamlit_and_clean() -> None:
    src = inspect.getsource(supply_chain_view)
    assert "import streamlit" not in src
    low = src.lower()
    for w in FORBIDDEN_WORDS:
        assert w not in low, f"FORBIDDEN_WORD found: {w!r}"
