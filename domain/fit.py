"""Portfolio-fit verdict — evidence grade + fit arithmetic. NEVER a prediction.

Honest boundary (spec §2): seven falsified hypotheses killed prediction; they did
not kill evidence aggregation or portfolio arithmetic. Every output is descriptive.
The FORBIDDEN_WORDS guard is a domain invariant, enforced by tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

FORBIDDEN_WORDS: tuple[str, ...] = (
    "buy",
    "sell",
    "winner",
    "conviction",
    "predict",
    "alpha",
    "outperform",
)

_GRADE_STRONG = 0.80
_GRADE_MODERATE = 0.50

# How close to the systematic-share threshold counts as "already concentrated"
# enough that adding a same-direction name meaningfully deepens the bet.
_BETA_NEAR_THRESHOLD_BAND = 0.05


@dataclass(frozen=True)
class FitFlag:
    kind: str
    message: str
    severity: str


@dataclass(frozen=True)
class FitVerdict:
    ticker: str
    evidence_grade: str
    fit_flags: tuple[FitFlag, ...]
    summary: str
    label: str = "RESEARCH_ONLY"


def composite_rank(
    composite: float, universe_composites: Sequence[float]
) -> float | None:
    """Fraction of the universe this composite beats. None if universe empty."""
    if not universe_composites:
        return None
    n = len(universe_composites)
    beaten = sum(1 for c in universe_composites if c < composite)
    return beaten / max(n - 1, 1) if n > 1 else 1.0


def _grade(rank: float | None) -> str:
    if rank is None:
        return "UNKNOWN"
    if rank >= _GRADE_STRONG:
        return "STRONG"
    if rank >= _GRADE_MODERATE:
        return "MODERATE"
    return "WEAK"


def assess_fit(
    ticker: str,
    ticker_composite: float | None,
    universe_composites: Sequence[float],
    ticker_beta: float | None,
    book_net_spy_beta: float | None,
    book_systematic_share: float | None,
    systematic_share_threshold: float,
    position_values: Mapping[str, float],
    trend_state: str | None,
    hypothetical_weight: float = 0.02,
) -> FitVerdict:
    """Compute the fit verdict. Degrades to DATA_GAP flags, never raises."""
    flags: list[FitFlag] = []

    rank = (
        composite_rank(ticker_composite, universe_composites)
        if ticker_composite is not None
        else None
    )
    grade = _grade(rank)
    if grade == "UNKNOWN":
        flags.append(
            FitFlag(
                kind="DATA_GAP",
                message=(
                    f"{ticker} is not in the latest evidence screen — its "
                    "evidence grade is unknown until the next screen run."
                ),
                severity="INFO",
            )
        )

    if ticker_beta is None:
        flags.append(
            FitFlag(
                kind="DATA_GAP",
                message=(
                    f"No market beta could be estimated for {ticker} "
                    "(insufficient price history)."
                ),
                severity="INFO",
            )
        )
    elif (
        book_net_spy_beta is not None
        and book_systematic_share is not None
        and ticker_beta * book_net_spy_beta > 0
        and book_systematic_share
        >= systematic_share_threshold - _BETA_NEAR_THRESHOLD_BAND
    ):
        flags.append(
            FitFlag(
                kind="BETA_AMPLIFY",
                message=(
                    f"{ticker} moves with the market the same way your book "
                    f"already does (its beta is {ticker_beta:+.2f}, your book's "
                    f"is {book_net_spy_beta:+.2f}). Adding it deepens the one "
                    "market-wide bet that already drives "
                    f"{book_systematic_share:.0%} of your book's movement."
                ),
                severity="WARNING",
            )
        )

    if not position_values:
        flags.append(
            FitFlag(
                kind="DATA_GAP",
                message="No holdings loaded — fit vs your book is unavailable.",
                severity="INFO",
            )
        )
    else:
        book_total = sum(position_values.values())
        if book_total > 0:
            add_value = book_total * hypothetical_weight / (1 - hypothetical_weight)
            largest_ticker, largest_value = max(
                position_values.items(), key=lambda kv: kv[1]
            )
            new_total = book_total + add_value
            n_bigger = sum(1 for v in position_values.values() if v > add_value)
            if add_value > largest_value:
                flags.append(
                    FitFlag(
                        kind="CONCENTRATION",
                        message=(
                            f"At {hypothetical_weight:.0%} sizing this would "
                            "become your single largest position — larger than "
                            f"{largest_ticker} "
                            f"({largest_value / new_total:.1%} of the book)."
                        ),
                        severity="CAUTION",
                    )
                )
            else:
                flags.append(
                    FitFlag(
                        kind="CONCENTRATION",
                        message=(
                            f"At {hypothetical_weight:.0%} sizing this would be "
                            f"your #{n_bigger + 1} position by weight; your "
                            f"largest single name stays {largest_ticker} at "
                            f"{largest_value / new_total:.1%}."
                        ),
                        severity="INFO",
                    )
                )

    if trend_state:
        flags.append(
            FitFlag(
                kind="TREND_STATE",
                message=f"Price trend is currently {trend_state} (descriptive only).",
                severity="INFO",
            )
        )

    grade_text = {
        "STRONG": "sits in the top fifth of the screened universe on factual "
        "evidence (valuation, quality, health)",
        "MODERATE": "sits in the upper half of the screened universe on factual "
        "evidence",
        "WEAK": "ranks in the lower half of the screened universe on factual "
        "evidence",
        "UNKNOWN": "has no evidence grade yet (not in the latest screen)",
    }[grade]
    summary = (
        f"{ticker} {grade_text}. This is evidence + fit arithmetic, not a "
        "forecast — the project ran 18 years of backtests and the forecasting "
        "hypotheses failed (see Falsification Lab)."
    )

    return FitVerdict(
        ticker=ticker,
        evidence_grade=grade,
        fit_flags=tuple(flags),
        summary=summary,
    )
