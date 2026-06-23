"""SP3 pure domain service — joins ScreenResult with corroboration snapshots."""

from __future__ import annotations

from datetime import date

from domain.screen_models import ScreenCandidate, ScreenResult
from domain.screened_row import CorroborationSnapshot, ScreenedRow, blend


class ScreenerCompositeService:
    def compose(
        self,
        result: ScreenResult,
        snapshots: list[CorroborationSnapshot],
        as_of: date,
        window_days: int = 7,
    ) -> tuple[ScreenedRow, ...]:
        """Join ScreenResult candidates with corroboration snapshots and re-rank.

        Candidates with no matching snapshot within window_days are marked
        factor_only=True and ranked by factor percentile alone.
        """
        if not result.candidates:
            return ()

        in_window = {
            s.ticker: s
            for s in snapshots
            if abs((as_of - s.surfaced_at).days) <= window_days
        }

        factor_pcts = _rank_percentiles(result.candidates)

        rows = []
        for cand in result.candidates:
            snap = in_window.get(cand.ticker)
            fp = factor_pcts[cand.ticker]
            rows.append(
                ScreenedRow(
                    candidate=cand,
                    corroboration=snap,
                    blended_percentile=blend(fp, snap),
                    factor_only=snap is None,
                )
            )

        rows.sort(key=lambda r: r.blended_percentile, reverse=True)
        return tuple(rows)


def _rank_percentiles(candidates: tuple[ScreenCandidate, ...]) -> dict[str, float]:
    """Convert composite z-scores to [0, 1] rank percentiles (0=worst, 1=best)."""
    n = len(candidates)
    if n == 1:
        return {candidates[0].ticker: 1.0}
    sorted_tickers = sorted(candidates, key=lambda c: c.composite)
    return {c.ticker: i / (n - 1) for i, c in enumerate(sorted_tickers)}
