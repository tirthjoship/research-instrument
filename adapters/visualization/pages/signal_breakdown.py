"""Tab 3: Signal Breakdown — Per-ticker multi-layer signal view."""

from __future__ import annotations

from typing import Any

import streamlit as st

from adapters.visualization.components.formatters import pct
from adapters.visualization.components.metrics import render_signal_layer_card
from adapters.visualization.data_loader import load_recommendations

DB_PATH = "data/recommendations.db"


def render(db_path: str = DB_PATH) -> None:
    """Render the Signal Breakdown tab."""
    st.header("Signal Breakdown")

    recs = load_recommendations(db_path)

    if not recs:
        st.info(
            "No recommendation data. Run a tournament first:\n\n"
            "```\npython -m application.cli run-tournament --market us\n```"
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
    """Show signal convergence indicator."""
    signals = rec.horizon_signals or {}
    bullish = sum(1 for v in signals.values() if v == "bullish")
    bearish = sum(1 for v in signals.values() if v == "bearish")
    total = len(signals) if signals else 1

    st.subheader(f"{rec.symbol} — {rec.grade.value}")

    cols = st.columns(3)
    cols[0].metric("Grade", rec.grade.value)
    cols[1].metric("Composite Score", f"{rec.composite_score:.3f}")
    cols[2].metric("5d Prediction", pct(rec.prediction.predicted_return_5d))

    if bullish > bearish:
        st.success(f"{bullish}/{total} horizons BULLISH")
    elif bearish > bullish:
        st.error(f"{bearish}/{total} horizons BEARISH")
    else:
        st.warning(f"MIXED: {bullish} bull, {bearish} bear")


def _render_layers(rec: Any) -> None:
    """Render 5 signal layer cards."""
    cols = st.columns(3)

    with cols[0]:
        tech_signal = (
            "BULLISH"
            if (rec.technical_signal or 0) > 0.2
            else ("BEARISH" if (rec.technical_signal or 0) < -0.2 else "NEUTRAL")
        )
        render_signal_layer_card(
            st,
            "Technical",
            "📊",
            tech_signal,
            {
                "RSI(14)": f"{rec.rsi_14:.1f}" if rec.rsi_14 else "N/A",
                "MACD": f"{rec.macd:.4f}" if rec.macd else "N/A",
                "Signal": (
                    f"{rec.technical_signal:.2f}" if rec.technical_signal else "N/A"
                ),
            },
        )

    with cols[1]:
        sent_signal = (
            "BULLISH"
            if (rec.sentiment_score or 0) > 0.2
            else ("BEARISH" if (rec.sentiment_score or 0) < -0.2 else "NEUTRAL")
        )
        render_signal_layer_card(
            st,
            "Sentiment",
            "💬",
            sent_signal,
            {
                "Score": f"{rec.sentiment_score:.2f}" if rec.sentiment_score else "N/A",
                "Divergence": (
                    f"{rec.divergence_score:.2f}" if rec.divergence_score else "N/A"
                ),
                "Type": rec.divergence_type or "N/A",
            },
        )

    with cols[2]:
        render_signal_layer_card(
            st,
            "Fundamental",
            "💰",
            "—",
            {"Note": "Run tournament with --fundamental for details"},
        )

    cols2 = st.columns(2)

    with cols2[0]:
        render_signal_layer_card(
            st,
            "Cross-Asset",
            "🔗",
            "—",
            {"Note": "Run tournament with cross-asset features for details"},
        )

    with cols2[1]:
        render_signal_layer_card(
            st,
            "Event-Causal",
            "⚡",
            "—",
            {"Note": "Run event classification pipeline for details"},
        )
