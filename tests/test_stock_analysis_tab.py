"""Tests for stock_analysis tab decision-card lead (S3 + S5)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any


def _fake_result() -> Any:
    """Minimal AnalysisResult-like object for testing _render_decision_lead_html."""
    return SimpleNamespace(
        ticker="YUMC",
        company_name="Yum China Holdings",
        current_price=44.63,
        info={},
        analyst_panel=None,
        peer_data=[],
        # fields that may be absent on real AnalysisResult (use getattr in impl)
        # price_series, atr, ma200, vs_spy_pct intentionally absent
    )


def test_decision_lead_renders_v9_sections(monkeypatch: Any) -> None:
    from adapters.data import earnings_history_adapter
    from adapters.visualization.tabs import stock_analysis as sa

    # Patch earnings fetch to return None (DATA-GAP path) — avoids network
    monkeypatch.setattr(
        earnings_history_adapter, "fetch_earnings_history", lambda _: None
    )

    html = sa._render_decision_lead_html(_fake_result(), verdict_value="TRIM")
    assert "Evidence detail" in html and "informs you, not the verdict" in html
    assert "not a trade signal" in html


def test_stock_analysis_case_uses_summarizer(monkeypatch: Any) -> None:
    from adapters.data import earnings_history_adapter
    from adapters.visualization.tabs import stock_analysis as sa
    from domain.case_models import CasePoint, CaseResult

    monkeypatch.setattr(
        earnings_history_adapter, "fetch_earnings_history", lambda _: None
    )
    monkeypatch.setattr(
        sa,
        "select_case_summarizer",
        lambda: type(
            "S",
            (),
            {
                "summarize_case": lambda self, ctx: CaseResult(
                    (CasePoint("Cheap", "valuation"),), (), False
                )
            },
        )(),
    )
    html = sa._render_decision_lead_html(
        _fake_result(), verdict_value="TRIM", with_case=True
    )
    assert "Cheap" in html
