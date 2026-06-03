"""Tab 3: Signal Breakdown — Per-ticker multi-layer signal view."""

from __future__ import annotations

from typing import Any

import streamlit as st

from adapters.visualization.components.formatters import grade_badge_html, pct
from adapters.visualization.components.metrics import (
    render_inline_context,
    render_signal_layer_card,
)
from adapters.visualization.components.verdicts import signal_layer_verdict
from adapters.visualization.data_loader import load_recommendations

DB_PATH = "data/recommendations.db"


def render(db_path: str = DB_PATH) -> None:
    """Render the Signal Breakdown tab."""
    st.markdown("### Signal Breakdown")
    render_inline_context(
        st,
        "Select a ticker to see what each of the 5 signal layers is saying. "
        "When layers agree, conviction is higher.",
    )

    recs = load_recommendations(db_path)

    if not recs:
        st.markdown(
            '<div class="dashboard-card card-info">'
            "<strong>No signal data</strong><br>"
            '<span style="color: #6B7280;">Run a tournament to generate signal data.</span>'
            "</div>",
            unsafe_allow_html=True,
        )
        return

    symbols = sorted({r.symbol for r in recs})
    selected = st.selectbox("Select Ticker", symbols)

    if selected:
        ticker_recs = [r for r in recs if r.symbol == selected]
        if ticker_recs:
            rec = ticker_recs[-1]
            _render_convergence(rec)
            st.divider()
            _render_layers(rec)


def _render_convergence(rec: Any) -> None:
    """Show signal convergence summary."""
    signals = rec.horizon_signals or {}
    bullish = sum(1 for v in signals.values() if v == "bullish")
    bearish = sum(1 for v in signals.values() if v == "bearish")
    total = len(signals) if signals else 1

    grade_html = grade_badge_html(rec.grade.value)
    st.markdown(
        f'<div class="dashboard-card">'
        f'<div style="font-size: 20px; font-weight: 600;">{rec.symbol} {grade_html}</div>'
        f"</div>",
        unsafe_allow_html=True,
    )

    cols = st.columns(3)
    cols[0].metric("Composite Score", f"{rec.composite_score:.3f}")
    cols[1].metric("5d Prediction", pct(rec.prediction.predicted_return_5d))
    cols[2].metric(
        "Confidence",
        f"{rec.prediction.confidence_5d:.0%}" if rec.prediction.confidence_5d else "—",
    )

    if bullish > bearish:
        bg = "#DCFCE7"
        text = f"{bullish}/{total} horizons bullish"
    elif bearish > bullish:
        bg = "#FEE2E2"
        text = f"{bearish}/{total} horizons bearish"
    else:
        bg = "#FEF9C3"
        text = f"Mixed: {bullish} bullish, {bearish} bearish"

    st.markdown(
        f'<div style="background: {bg}; padding: 8px 16px; border-radius: 8px; '
        f'font-weight: 600; font-size: 14px; text-align: center;">{text}</div>',
        unsafe_allow_html=True,
    )


def _render_layers(rec: Any) -> None:
    """Render 5 signal layer cards with verdicts."""
    cols = st.columns(3)

    with cols[0]:
        tech_signal = rec.technical_signal or 0
        tech_dir = (
            "bullish"
            if tech_signal > 0.2
            else "bearish" if tech_signal < -0.2 else "neutral"
        )
        render_signal_layer_card(
            st,
            "Technical",
            "technical",
            tech_dir,
            signal_layer_verdict("technical", rec.technical_signal),
            {
                "RSI(14)": f"{rec.rsi_14:.1f}" if rec.rsi_14 else "N/A",
                "MACD": f"{rec.macd:.4f}" if rec.macd else "N/A",
                "Signal": (
                    f"{rec.technical_signal:.2f}" if rec.technical_signal else "N/A"
                ),
            },
        )

    with cols[1]:
        sent_signal = rec.sentiment_score or 0
        sent_dir = (
            "bullish"
            if sent_signal > 0.2
            else "bearish" if sent_signal < -0.2 else "neutral"
        )
        render_signal_layer_card(
            st,
            "Sentiment",
            "sentiment",
            sent_dir,
            signal_layer_verdict("sentiment", rec.sentiment_score),
            {
                "Score": f"{rec.sentiment_score:.2f}" if rec.sentiment_score else "N/A",
                "Divergence": (
                    f"{rec.divergence_score:.2f}" if rec.divergence_score else "N/A"
                ),
                "Type": rec.divergence_type or "aligned",
            },
        )

    with cols[2]:
        render_signal_layer_card(
            st,
            "Fundamental",
            "fundamental",
            "not_run",
            signal_layer_verdict("fundamental", None),
            {},
        )

    cols2 = st.columns(2)

    with cols2[0]:
        render_signal_layer_card(
            st,
            "Cross-Asset",
            "cross-asset",
            "not_run",
            signal_layer_verdict("cross-asset", None),
            {},
        )

    with cols2[1]:
        render_signal_layer_card(
            st,
            "Event-Causal",
            "event-causal",
            "not_run",
            signal_layer_verdict("event-causal", None),
            {},
        )
