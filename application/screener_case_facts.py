"""Pure fact-building logic for a screener candidate — shared by the live
Screener render path (adapters/visualization/tabs/research_candidates.py) and
the CLI --cite-cases prefetch (application/cli/screen_commands.py), so a cache
hit and a cache-miss live fallback never disagree on what a candidate's bands
say.
"""

from __future__ import annotations

from typing import Any

from domain.factor_bands import Band, band_for_percentile
from domain.factor_scores import factor_display_label


def candidate_bands(candidate: dict[str, Any]) -> dict[str, Band]:
    """Map each present factor (non-None, not all-zero) to its plain-language band."""
    bands: dict[str, Band] = {}
    for fd in candidate.get("factor_scores", []):
        if not isinstance(fd, dict):
            continue
        rv, rp = fd.get("value"), fd.get("percentile")
        if rv is None or rp is None:
            continue
        fv, fp = float(rv), float(rp)
        if fv == 0.0 and fp == 0.0:  # DATA-GAP / no coverage
            continue
        bands[str(fd.get("name", ""))] = band_for_percentile(fp)
    return bands


def facts_from_bands(
    bands: dict[str, Band], factor_by_name: dict[str, dict[str, Any]]
) -> dict[str, str]:
    """Build plain-English facts from live factor bands for the Google-AI
    case context.

    HONESTY INVARIANT: only band + percentile text, never the composite score
    or grade — Gemini must never see (or be influenced by) the ranking.
    """
    facts: dict[str, str] = {}
    for fname, band in bands.items():
        label = factor_display_label(fname)
        pct = factor_by_name.get(fname, {}).get("percentile")
        pct_txt = f" (p{round(float(pct) * 100)})" if pct is not None else ""
        facts[label] = f"{band.value}{pct_txt}"
    return facts
