"""Ticker factor lookup / live-compute use case (S5 Task 2).

Given a ticker and a persisted screen, returns 5 factor score dicts
(name, value, percentile, source) suitable for rendering the Zone ② card.

- In-screen path: returns stored factor_scores directly (free, zero computation).
- Off-universe path: calls fetch_fn for raw z-scores, ranks them against the
  cohort z-distribution reconstructed from all candidates in the screen —
  mirroring evidence_screen_use_case.py:119-141 (no new scoring logic).
- DATA-GAP: if fetch_fn raises or returns None for a factor, the row is
  {"name": f, "value": None, "percentile": None, "source": "live"}.

Design: fetch_fn is an injected Callable[str, dict[str, float|None]] so tests
can supply a fake without touching any live adapter.
"""

from __future__ import annotations

from typing import Any, Callable

_ALL_FACTORS: tuple[str, ...] = ("momentum", "revision", "quality", "value", "lowvol")


def _rank_vs_cohort(z: float, cohort_zs: list[float]) -> float:
    """Rank *z* among *cohort_zs*; return 0-indexed fraction in [0, 1]."""
    n = len(cohort_zs)
    if n == 0:
        return 0.0
    beaten = sum(1 for cz in cohort_zs if cz < z)
    return beaten / max(n - 1, 1)


def ticker_factor_scores(
    ticker: str,
    screen: dict[str, Any],
    fetch_fn: Callable[[str], dict[str, float | None]],
) -> list[dict[str, Any]]:
    """Return 5 factor score dicts for *ticker*.

    Each dict has keys: name, value, percentile, source.

    Args:
        ticker: Stock ticker to look up or compute.
        screen: Persisted screen dict (with "candidates" list of dicts).
        fetch_fn: Callable that accepts a ticker and returns a dict of
            factor_name -> raw z-score (or None for DATA-GAP). Only called
            for off-universe tickers.

    Returns:
        List of 5 dicts, one per factor in _ALL_FACTORS order.
    """
    candidates: list[dict[str, Any]] = screen.get("candidates", [])

    # --- In-screen path: reuse stored scores ---
    for cand in candidates:
        if cand.get("ticker") == ticker:
            stored: list[dict[str, Any]] = list(cand.get("factor_scores", []))
            # Ensure all 5 factors are represented (backfill any missing as DATA-GAP)
            result: list[dict[str, Any]] = []
            for fname in _ALL_FACTORS:
                match = next((f for f in stored if f.get("name") == fname), None)
                if match is not None:
                    result.append(
                        {
                            "name": fname,
                            "value": match.get("value"),
                            "percentile": match.get("percentile"),
                            "source": "screen",
                        }
                    )
                else:
                    result.append(
                        {
                            "name": fname,
                            "value": None,
                            "percentile": None,
                            "source": "screen",
                        }
                    )
            return result

    # --- Off-universe path: fetch raw z-scores, rank vs cohort ---
    # Build cohort z-distribution from all stored candidates (per factor)
    cohort_zs: dict[str, list[float]] = {f: [] for f in _ALL_FACTORS}
    for cand in candidates:
        for fs in cand.get("factor_scores", []):
            fname = fs.get("name")
            val = fs.get("value")
            if fname in cohort_zs and val is not None:
                cohort_zs[fname].append(float(val))

    # Attempt live fetch
    try:
        raw = fetch_fn(ticker)
    except Exception:
        # DATA-GAP: fetch failed entirely
        return [
            {"name": f, "value": None, "percentile": None, "source": "live"}
            for f in _ALL_FACTORS
        ]

    # Rank each factor's raw z against the cohort
    live_result: list[dict[str, Any]] = []
    for fname in _ALL_FACTORS:
        z = raw.get(fname) if raw else None
        if z is None:
            live_result.append(
                {"name": fname, "value": None, "percentile": None, "source": "live"}
            )
        else:
            pct = _rank_vs_cohort(float(z), cohort_zs.get(fname, []))
            live_result.append(
                {
                    "name": fname,
                    "value": float(z),
                    "percentile": pct,
                    "source": "live",
                }
            )
    return live_result
