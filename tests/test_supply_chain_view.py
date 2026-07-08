import inspect
from types import SimpleNamespace

from adapters.visualization.tabs.stock_analysis import supply_chain_view
from domain.fit import FORBIDDEN_WORDS


def _result(
    group: bool = True,
    co_movement: float | None = None,
    group_1w_pct: float | None = None,
    vs_group_1w_pct: float | None = None,
    provenance: str = "yaml+correlation",
) -> SimpleNamespace:
    g = (
        {
            "group": "ai_infrastructure",
            "group_display": "AI-semis",
            "leaders": ["NVDA"],
            "followers": ["AMD", "AVGO"],
            "typical_lag_days": 3,
            "notes": "leaders move first",
            "_is_leader": True,
            "provenance": provenance,
            "member_moves": {"NVDA": 2.0, "AMD": -1.0, "AVGO": 1.0},
            "member_market_caps": {"NVDA": 4.2e12, "AMD": 2.5e11, "AVGO": 8.0e11},
            **({"co_movement": co_movement} if co_movement is not None else {}),
            **({"group_1w_pct": group_1w_pct} if group_1w_pct is not None else {}),
            **(
                {"vs_group_1w_pct": vs_group_1w_pct}
                if vs_group_1w_pct is not None
                else {}
            ),
        }
        if group
        else None
    )
    return SimpleNamespace(supply_chain_group=g, ticker="NVDA", market_cap=4.2e12)


def test_group_role_members_present() -> None:
    v = supply_chain_view.build_supply_chain_view(_result())
    assert any("Group" in m.label for m in v["metrics"])
    assert any("ole" in m.label for m in v["metrics"])  # Role
    assert any("Members" in m.label for m in v["metrics"])


def test_group_tile_shows_display_name_and_provenance() -> None:
    v = supply_chain_view.build_supply_chain_view(_result())
    group_tile = next(m for m in v["metrics"] if m.label == "Group")
    assert group_tile.value == "AI-semis"
    assert group_tile.sub == "mapped"


def test_correlation_only_group_shows_corr_cluster_sub() -> None:
    v = supply_chain_view.build_supply_chain_view(
        _result(provenance="correlation_only")
    )
    group_tile = next(m for m in v["metrics"] if m.label == "Group")
    assert group_tile.sub == "corr-cluster"


def test_comovement_datagap_when_not_computed() -> None:
    v = supply_chain_view.build_supply_chain_view(_result())
    cm = next(m for m in v["metrics"] if m.label == "Co-move")
    assert cm.value == "—"


def test_comovement_real_value_when_computed() -> None:
    v = supply_chain_view.build_supply_chain_view(_result(co_movement=0.78))
    cm = next(m for m in v["metrics"] if m.label == "Co-move")
    assert cm.value == "0.78"
    assert cm.sub == "tight"


def test_comovement_high_value_flags_caution_verdict() -> None:
    v = supply_chain_view.build_supply_chain_view(_result(co_movement=0.78))
    assert any(vv.tone == "cau" and "0.78" in vv.text for vv in v["verdicts"])


def test_group_1w_and_vs_group_tiles() -> None:
    v = supply_chain_view.build_supply_chain_view(
        _result(group_1w_pct=5.4, vs_group_1w_pct=2.1)
    )
    group1w = next(m for m in v["metrics"] if m.label == "Group 1w")
    vsgrp = next(m for m in v["metrics"] if "vs grp" in m.label)
    assert group1w.value == "+5%"
    assert "NVDA vs grp" == vsgrp.label
    assert vsgrp.value == "+2pts"
    assert vsgrp.sub == "ahead"


def test_vs_group_tile_datagap_when_missing() -> None:
    v = supply_chain_view.build_supply_chain_view(_result())
    vsgrp = next(m for m in v["metrics"] if "vs grp" in m.label)
    assert vsgrp.value == "—"


def test_leader_and_high_comovement_headline() -> None:
    v = supply_chain_view.build_supply_chain_view(_result(co_movement=0.78))
    assert v["claim"] == "The anchor of its group — peers move around it"
    assert "NVDA" in v["reframe"]
    assert "AI-semis" in v["reframe"]


def test_chips_show_group_display_and_comovement() -> None:
    v = supply_chain_view.build_supply_chain_view(_result(co_movement=0.78))
    assert "AI-semis" in v["chips"]
    assert "co-move" in v["chips"]
    assert "0.78" in v["chips"]


def test_none_group_degrades() -> None:
    assert "Supply" in supply_chain_view.build_supply_chain_panel(_result(group=False))


def test_panel_renders() -> None:
    assert "Supply" in supply_chain_view.build_supply_chain_panel(_result())


def test_panel_renders_bubble_chart_when_market_caps_present() -> None:
    html = supply_chain_view.build_supply_chain_panel(_result())
    assert "<svg" in html
    assert "NVDA" in html


def test_no_streamlit_and_clean() -> None:
    src = inspect.getsource(supply_chain_view)
    assert "import streamlit" not in src
    low = src.lower()
    for w in FORBIDDEN_WORDS:
        assert w not in low, f"FORBIDDEN_WORD found: {w!r}"
