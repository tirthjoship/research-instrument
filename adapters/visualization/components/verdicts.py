"""Plain-English verdict generators for dashboard tabs.

Each function takes structured data and returns a human-readable sentence
that answers "what should I know?" before showing numbers.
"""

from __future__ import annotations


def command_center_verdict(
    n_holdings: int,
    n_recommendations: int,
    n_sell_signals: int,
    freshness_hours: float | None,
) -> str:
    """Generate hero banner verdict for Command Center."""
    if n_holdings == 0 and n_recommendations == 0:
        return "No data yet — run a full cycle to get started."

    parts: list[str] = []

    if n_sell_signals > 0:
        parts.append(
            f"{n_sell_signals} sell signal{'s' if n_sell_signals != 1 else ''} need attention"
        )

    buy_count = n_recommendations
    if buy_count > 0:
        parts.append(f"{buy_count} ranked picks available")

    if not parts:
        parts.append("Portfolio is up to date")

    verdict = " · ".join(parts) + "."

    if freshness_hours is not None:
        if freshness_hours > 24:
            verdict += " Data is stale — consider running a scan."
        elif freshness_hours > 6:
            verdict += f" Last scan was {freshness_hours:.0f}h ago."

    return verdict


def model_confidence_verdict(
    accuracy: float,
    p_value: float,
    n_folds: int,
) -> str:
    """Generate verdict for Model Confidence tab."""
    beats_random = p_value < 0.05

    if beats_random:
        return (
            f"The model has a proven statistical edge. "
            f"{accuracy:.1%} accuracy across {n_folds} folds (p={p_value:.4f}). "
            f"Sentiment features are the primary driver of this lift."
        )
    return (
        f"The model doesn't have a proven edge yet. "
        f"{accuracy:.1%} accuracy across {n_folds} folds (p={p_value:.4f}). "
        f"Technical features alone perform at random on mega-caps. "
        f"Adding sentiment lifted accuracy to ~70% in-sample — promising but unproven out-of-sample."
    )


def signal_layer_verdict(layer_name: str, signal_value: float | None) -> str:
    """Generate verdict for a single signal layer card."""
    if signal_value is None:
        return f"Not yet run — run a tournament with {layer_name} features enabled to populate."

    if abs(signal_value) < 0.2:
        return "No strong directional pressure detected."
    elif signal_value > 0.2:
        return "Showing positive momentum — bullish signal from this layer."
    else:
        return "Showing negative pressure — bearish signal from this layer."


def pick_verdict(
    grade: str,
    n_bullish: int,
    n_total: int,
    reasoning: str,
) -> str:
    """Generate verdict for a single pick card."""
    from adapters.visualization.components.formatters import grade_display_name

    grade_display_name(grade)  # validate it works

    if "buy" in grade.lower() or "strong" in grade.lower():
        agreement = f"{n_bullish}/{n_total} layers bullish" if n_total > 0 else ""
        prefix = (
            "Highest conviction"
            if n_bullish == n_total and n_total > 1
            else "Strong momentum"
        )
        return (
            f"{prefix} — {agreement}. {reasoning}"
            if agreement
            else f"{prefix}. {reasoning}"
        )
    elif "hold" in grade.lower():
        return f"Mixed signals — waiting for clearer direction. {reasoning}"
    elif "sell" in grade.lower():
        return f"Caution — negative signals detected. {reasoning}"
    return f"{reasoning}"


def ablation_verdict(
    tech_accuracy: float | None,
    combined_accuracy: float | None,
) -> str:
    """Generate verdict for ablation section."""
    if tech_accuracy is None or combined_accuracy is None:
        return "Run Phase 3B validation to compare technical-only vs combined accuracy."

    lift = combined_accuracy - tech_accuracy
    if lift > 0.05:
        return (
            f"Yes — sentiment helps significantly. "
            f"Technical-only: {tech_accuracy:.1%} → Combined: {combined_accuracy:.1%} "
            f"(+{lift:.1%} lift)."
        )
    elif lift > 0:
        return (
            f"Marginal improvement. "
            f"Technical-only: {tech_accuracy:.1%} → Combined: {combined_accuracy:.1%}."
        )
    return (
        f"No improvement detected. "
        f"Technical-only: {tech_accuracy:.1%}, Combined: {combined_accuracy:.1%}."
    )


def outcome_tracker_verdict(
    n_trades: int,
    n_outcomes: int,
    total_return: float,
    win_rate: float,
) -> str:
    """Generate verdict for the Outcome Tracker section."""
    if n_trades == 0:
        return "No trades recorded yet — use the Positions tab to log your first trade."
    if n_outcomes == 0:
        return f"{n_trades} trade{'s' if n_trades != 1 else ''} recorded, none closed yet — outcomes will appear once you log a sell."
    sign = "+" if total_return >= 0 else ""
    return (
        f"{n_outcomes} completed trade{'s' if n_outcomes != 1 else ''} — "
        f"{sign}${total_return:,.2f} total return, {win_rate:.0f}% win rate."
    )


def system_intelligence_verdict(
    n_outcomes: int,
    best_signal: str | None,
    worst_signal: str | None,
) -> str:
    """Generate verdict for the System Intelligence section."""
    if n_outcomes == 0:
        return "No outcome data yet — close your first trade to start building signal intelligence."
    if n_outcomes < 10:
        return f"{n_outcomes} outcome{'s' if n_outcomes != 1 else ''} tracked. Need 10+ for reliable signal data."
    return (
        f"Based on {n_outcomes} completed trades: "
        f"best signal is {best_signal}, weakest is {worst_signal}."
    )
