"""Batch fit verdicts for a user-supplied ticker list (Screener upload)."""

from __future__ import annotations

from dataclasses import dataclass

from domain.fit import FitVerdict


@dataclass(frozen=True)
class BatchFitRow:
    ticker: str
    verdict: FitVerdict
    fetch_ok: bool
