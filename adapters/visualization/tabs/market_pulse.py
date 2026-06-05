"""Tab 6: Market Pulse — Data sources, supply chains, event decay."""

from __future__ import annotations

import streamlit as st

from adapters.visualization.components.charts import decay_curve
from adapters.visualization.components.metrics import render_inline_context
from adapters.visualization.data_loader import load_supply_chains

SUPPLY_CHAIN_PATH = "config/relationships/supply_chain.yaml"


def render(
    supply_chain_path: str = SUPPLY_CHAIN_PATH,
    db_path: str = "data/recommendations.db",
) -> None:
    """Render the Market Pulse tab."""
    st.markdown("### Market Context")
    render_inline_context(
        st,
        "Background intelligence — data sources, supply chain relationships, "
        "and event impact modeling.",
    )

    _render_data_sources(db_path)
    st.divider()
    _render_supply_chains(supply_chain_path)
    st.divider()
    _render_event_decay()


def _format_last_run(dt: object) -> str:
    """Format a datetime (or ISO string) as 'Last: Xmin/h/d ago', or '' if None."""
    if dt is None:
        return ""
    try:
        from datetime import datetime

        if isinstance(dt, str):
            dt = datetime.fromisoformat(dt)
        age = (datetime.now() - dt).total_seconds() / 3600  # type: ignore[operator]
        if age < 1:
            return f"Last: {int(age * 60)}min ago"
        elif age < 24:
            return f"Last: {int(age)}h ago"
        else:
            return f"Last: {int(age / 24)}d ago"
    except Exception:  # noqa: BLE001
        return ""


def _render_data_sources(db_path: str = "data/recommendations.db") -> None:
    """Show data pipeline status as a styled grid with real last-run timestamps."""
    st.markdown("#### Data Pipeline")
    render_inline_context(st, "What data sources are connected and when they last ran.")

    # Query last run times from buzz_signals per source
    last_runs: dict[str, object] = {}
    try:
        from collections import defaultdict

        from adapters.data.sqlite_store import SQLiteStore

        store = SQLiteStore(db_path)
        signals = store.get_buzz_signals()
        if signals:
            by_source: dict[str, list[object]] = defaultdict(list)
            for s in signals:
                by_source[getattr(s, "source", "unknown")].append(
                    getattr(s, "fetched_at", None)
                )
            for source, dates in by_source.items():
                valid = [d for d in dates if d is not None]
                if valid:
                    last_runs[source] = max(valid)  # type: ignore[type-var]
    except Exception:  # noqa: BLE001
        pass

    rss_detail = (
        _format_last_run(last_runs.get("yahoo_finance")) or "15 feeds configured"
    )
    trends_detail = (
        _format_last_run(last_runs.get("google_trends")) or "350 tickers tracked"
    )
    twits_detail = _format_last_run(last_runs.get("stocktwits")) or "Live sentiment"
    gdelt_detail = (
        _format_last_run(last_runs.get("gdelt")) or "Available in future phase"
    )

    sources = [
        ("RSS Feeds", True, rss_detail),
        ("Google Trends", True, trends_detail),
        ("StockTwits", True, twits_detail),
        ("GDELT", False, gdelt_detail),
        ("Fundamental", True, "Via yfinance (real-time)"),
        ("Cross-Asset", True, "Correlation matrix (daily)"),
        ("Event-Causal", True, "Gemini classifier (10 categories)"),
        ("SEC EDGAR", True, "13D activist filings + Form 4 insider trades"),
    ]

    cards_html = ""
    for name, active, detail in sources:
        dot_color = "#22C55E" if active else "#EF4444"
        dot_html = (
            f'<span style="display:inline-block; width:8px; height:8px; '
            f"border-radius:50%; background:{dot_color}; "
            f'margin-right:6px; flex-shrink:0; margin-top:3px;"></span>'
        )
        cards_html += (
            f'<div class="ws-card" style="padding:12px 14px;">'
            f'<div style="display:flex; align-items:flex-start; margin-bottom:4px;">'
            f"{dot_html}"
            f'<strong style="font-size:13px;">{name}</strong>'
            f"</div>"
            f'<span style="color:#6B7280; font-size:12px;">{detail}</span>'
            f"</div>"
        )

    grid_html = (
        f'<div style="display:grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); '
        f'gap:12px; margin-top:8px;">'
        f"{cards_html}"
        f"</div>"
    )
    st.markdown(grid_html, unsafe_allow_html=True)


def _ticker_tag(ticker: str, base_bg: str, prices: dict[str, dict[str, float]]) -> str:
    """Render a colored ticker tag with live price change border."""
    p = prices.get(ticker, {})
    change = p.get("change_pct", 0.0)
    border_color = "#16A34A" if change > 0 else "#DC2626" if change < 0 else "#D1D5DB"
    change_str = f" {change:+.1f}%" if p else ""
    return (
        f'<span style="background:{base_bg}; border:1.5px solid {border_color}; '
        f"padding:2px 8px; border-radius:4px; margin:2px; font-size:13px; "
        f'display:inline-block;">{ticker}{change_str}</span>'
    )


def _render_supply_chains(supply_chain_path: str) -> None:
    """Show supply chain cascades with live price-colored tags and cluster bubble."""
    st.markdown("#### Supply Chain Cascades")
    render_inline_context(
        st,
        "When leader stocks move >3%, follower stocks often follow within 1-3 days.",
    )

    chains = load_supply_chains(supply_chain_path)

    if not chains:
        st.caption("No supply chain config found.")
        return

    relationships = chains.get("relationships", [])

    # Batch-fetch prices for all tickers upfront
    all_tickers: set[str] = set()
    for rel in relationships:
        all_tickers.update(rel.get("leaders", []))
        all_tickers.update(rel.get("followers", []))

    prices: dict[str, dict[str, float]] = {}
    if all_tickers:
        try:
            from adapters.visualization.price_cache import batch_fetch_prices

            prices = batch_fetch_prices(tuple(sorted(all_tickers)))
        except Exception:  # noqa: BLE001
            pass

    for rel in relationships:
        group_name = rel.get("group", "unknown").replace("_", " ").title()
        lag = rel.get("typical_lag_days", "?")
        inverse = rel.get("inverse", False)
        corr_type = "Inverse" if inverse else "Positive"
        notes = rel.get("notes", "")

        st.markdown(
            f'<div class="ws-card">'
            f"<strong>{group_name}</strong> — {corr_type} · {lag}d lag",
            unsafe_allow_html=True,
        )

        leaders = rel.get("leaders", [])
        followers = rel.get("followers", [])

        lcols = st.columns(2)
        with lcols[0]:
            leader_tags = " ".join(_ticker_tag(t, "#DBEAFE", prices) for t in leaders)
            st.markdown(f"**Leaders** {leader_tags}", unsafe_allow_html=True)
        with lcols[1]:
            follower_tags = " ".join(
                _ticker_tag(t, "#FFEDD5", prices) for t in followers
            )
            st.markdown(f"**Followers** {follower_tags}", unsafe_allow_html=True)

        if notes:
            st.markdown(
                f'<span style="color: #9CA3AF; font-size: 12px;">{notes}</span>'
                f"</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown("</div>", unsafe_allow_html=True)

    # ── Cluster Bubble for first group ────────────────────────────────────────
    if relationships and prices:
        _render_cluster_bubble(relationships[0], prices)


def _render_cluster_bubble(
    rel: dict[str, object],
    prices: dict[str, dict[str, float]],
) -> None:
    """Render a cluster bubble chart for a supply chain group."""
    try:
        from adapters.visualization.components.charts import cluster_bubble
        from adapters.visualization.price_cache import fetch_ticker_info

        group_name = str(rel.get("group", "")).replace("_", " ").title()
        leaders_raw = rel.get("leaders", [])
        followers_raw = rel.get("followers", [])
        leaders = [str(x) for x in leaders_raw] if isinstance(leaders_raw, list) else []
        followers = (
            [str(x) for x in followers_raw] if isinstance(followers_raw, list) else []
        )
        all_group = leaders + followers

        ticker_data: list[dict[str, object]] = []
        for t in all_group[:10]:  # Limit to 10 for performance
            if t not in prices:
                continue
            info = fetch_ticker_info(t)
            mcap = float(info.get("marketCap", 0)) if info else 0.0
            change = prices[t].get("change_pct", 0.0)
            role = "leader" if t in leaders else "follower"
            if mcap > 0:
                ticker_data.append(
                    {
                        "ticker": t,
                        "market_cap": mcap,
                        "change_pct": change,
                        "role": role,
                    }
                )

        if ticker_data:
            st.markdown("#### Cluster Visualization")
            fig = cluster_bubble(ticker_data, group_name)
            st.plotly_chart(fig, use_container_width=True)
    except Exception:  # noqa: BLE001
        pass


def _render_event_decay() -> None:
    """Event impact decay interactive visualization."""
    st.markdown("#### Event Impact Decay")
    render_inline_context(
        st,
        "How quickly news events lose market impact. "
        "A 5% earnings surprise loses half its effect in ~5 days.",
    )

    col1, col2 = st.columns(2)
    magnitude = col1.slider("Impact Magnitude", 0.01, 0.10, 0.05, step=0.01)
    half_life = col2.slider("Half-Life (days)", 1.0, 14.0, 5.0, step=0.5)

    remaining = magnitude * (0.5 ** (5 / half_life))
    render_inline_context(
        st,
        f"After 5 days, a {magnitude:.0%} impact decays to {remaining:.2%} remaining.",
    )

    fig = decay_curve(magnitude, half_life)
    st.plotly_chart(fig, use_container_width=True)
