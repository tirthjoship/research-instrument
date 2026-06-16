# tests/application/test_evidence_card.py
from adapters.data.earnings_history_adapter import EarningsHistory, EpsQuarter
from application.analyst_panel import AnalystPanel
from application.evidence_card import EvidenceCard, build_evidence_card
from domain.evidence_rag import DIMENSIONS, RagColor


def _panel() -> AnalystPanel:
    return AnalystPanel(
        count=43,
        mean_rating=1.9,
        target_mean=47.8,
        target_high=52.0,
        target_low=44.0,
        as_of="2026-06-14",
        attribution="yfinance",
        data_gap=False,
    )


def _earnings() -> EarningsHistory:
    qs = tuple(
        EpsQuarter(m, a, e, s)
        for m, a, e, s in [
            ("Aug", 0.18, 0.20, -10.0),
            ("Nov", 0.41, 0.40, 2.5),
            ("Feb", 0.33, 0.30, 9.2),
            ("Apr", 0.55, 0.50, 10.0),
        ]
    )
    return EarningsHistory(quarters=qs, beats=3, total=4)


def test_build_card_has_five_signals_fixed_order() -> None:
    info = {
        "peg_ratio": 0.9,
        "trailing_pe": 19.0,
        "free_cashflow": 1.2e9,
        "debt_to_equity": 45.0,
        "current_price": 44.63,
    }
    prices = {
        "closes": [40.0] * 150 + [44.63],
        "atr": 2.0,
        "ma200": 50.0,
        "spy_1y": 0.0,
        "book_1y": -9.0,
    }
    card = build_evidence_card(
        "YUMC",
        info=info,
        prices=prices,
        panel=_panel(),
        earnings=_earnings(),
        peers=[20.0, 25.0, 18.0, 30.0],
    )
    assert isinstance(card, EvidenceCard)
    assert tuple(s.dimension for s in card.signals) == DIMENSIONS
    assert card.signals[3].color is RagColor.GREEN  # Earnings beat 3/4
    assert len(card.sparkline) > 0


def test_build_card_data_gap_paths() -> None:
    info = {"current_price": 10.0}  # nothing else
    prices = {
        "closes": [10.0],
        "atr": None,
        "ma200": None,
        "spy_1y": None,
        "book_1y": None,
    }
    card = build_evidence_card(
        "X",
        info=info,
        prices=prices,
        panel=AnalystPanel(0, None, None, None, None, "2026-06-14", "yfinance", True),
        earnings=None,
        peers=[],
    )
    colors = {s.dimension: s.color for s in card.signals}
    assert colors["Earnings"] is RagColor.GAP
    assert colors["Analysts"] is RagColor.GAP
    assert colors["Technicals"] is RagColor.GAP
