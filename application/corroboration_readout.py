"""Pure, testable logic for assembling an OurReadout from available signals.

All functions here are stdlib + domain only (hexagonal rule: no network, no
external libs).  The CLI injects live-fetched values; these functions only
do the mapping and assembly.
"""

from __future__ import annotations

from domain.corroboration_models import OurReadout, TrendHealth

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
# Mirrors domain/discipline.py _BROKEN_TREND_ATR: below -2.0 ATR units the
# trend is "clearly broken" and the discipline module would issue REDUCE.
# At >= 0.0 price is at/above the trend line (HEALTHY).
# Between -2.0 and 0.0 (exclusive) we call CAUTION — deteriorating but not yet
# broken.  Boundary: th == -2.0 is CAUTION (BROKEN is strictly th < -2.0).
_BROKEN_THRESHOLD: float = -2.0


def trend_health_band(th: float | None) -> TrendHealth | None:
    """Map a signed ATR-distance float to a TrendHealth enum band.

    Args:
        th: Signed distance of price from the 200-day SMA in ATR units, as
            returned by ``domain.trend_rules.trend_health()``.  None when
            inputs were unavailable.

    Returns:
        - None          when th is None (data unavailable)
        - HEALTHY       when th >= 0.0 (at or above the trend line)
        - CAUTION       when -2.0 <= th < 0.0 (below trend but not broken)
        - BROKEN        when th < -2.0 (discipline REDUCE threshold)
    """
    if th is None:
        return None
    if th >= 0.0:
        return TrendHealth.HEALTHY
    if th >= _BROKEN_THRESHOLD:  # -2.0 <= th < 0.0
        return TrendHealth.CAUTION
    # th < -2.0
    return TrendHealth.BROKEN


def factor_percentile_from_screen(ticker: str, screen: dict | None) -> float | None:  # type: ignore[type-arg]
    """Extract a ticker's composite factor percentile (0-100) from a screen JSON dict.

    The screen JSON written by ``screen-candidates`` has this shape::

        {
          "candidates": [
            {
              "ticker": "AAPL",
              "factor_scores": [
                {"name": "momentum", "value": 0.5, "percentile": 0.8, ...},
                ...
              ],
              ...
            }
          ]
        }

    Each ``factor_scores[i].percentile`` is a 0-1 fraction (rank fraction among
    candidates with present values for that factor).  We average these fractions
    across all factors present for the ticker and return the result × 100.

    Args:
        ticker: Stock ticker to look up.
        screen: Loaded screen JSON (dict) or None.

    Returns:
        Composite percentile on a 0-100 scale, or None when the ticker is
        absent, the screen is None/malformed, or no valid percentile values
        exist.
    """
    if screen is None:
        return None
    try:
        candidates = screen.get("candidates")
        if not isinstance(candidates, list):
            return None
        for cand in candidates:
            if not isinstance(cand, dict):
                continue
            if cand.get("ticker") != ticker:
                continue
            factor_scores = cand.get("factor_scores")
            if not isinstance(factor_scores, list) or not factor_scores:
                return None
            percentiles: list[float] = []
            for fs in factor_scores:
                if not isinstance(fs, dict):
                    continue
                p = fs.get("percentile")
                if isinstance(p, (int, float)):
                    percentiles.append(float(p))
            if not percentiles:
                return None
            return sum(percentiles) / len(percentiles) * 100.0
    except Exception:
        return None
    return None


def assemble_readout(
    ticker: str,
    *,
    trend_health_float: float | None,
    screen: dict | None,  # type: ignore[type-arg]
    divergence_flag: bool,
    discipline_flag: str | None,
) -> OurReadout:
    """Pure assembly: build an OurReadout from individual signal inputs.

    Args:
        ticker:             Stock ticker.
        trend_health_float: Raw ATR-distance float (from trend_rules.trend_health).
        screen:             Loaded screen_<date>.json dict or None.
        divergence_flag:    True when buzz is accelerating ahead of price.
        discipline_flag:    "REDUCE"/"HOLD"/"ADD_OK" if ticker is in held positions,
                            None otherwise.

    Returns:
        OurReadout with all fields populated (any unavailable field is None/False).
    """
    return OurReadout(
        factor_percentile=factor_percentile_from_screen(ticker, screen),
        trend_health=trend_health_band(trend_health_float),
        divergence_flag=divergence_flag,
        discipline_flag=discipline_flag,
    )
