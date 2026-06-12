"""Batch fit verdicts for a user-supplied ticker list (Screener upload)."""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from typing import Callable, Sequence

from loguru import logger

from domain.fit import FitFlag, FitVerdict


@dataclass(frozen=True)
class BatchFitRow:
    ticker: str
    verdict: FitVerdict
    fetch_ok: bool


MAX_TICKERS = 25

_TICKER_RE = re.compile(r"^(?=.*[A-Z0-9])[A-Z0-9.\-]{1,10}$")

_BOM = "﻿"


def parse_tickers(text: str) -> list[str]:
    """Comma/whitespace/newline-separated tickers → upper, dedup, capped."""
    out: list[str] = []
    for raw in re.split(r"[,\s]+", text.lstrip(_BOM).strip()):
        t = raw.strip().upper()
        if t and _TICKER_RE.match(t) and t not in out:
            out.append(t)
        if len(out) >= MAX_TICKERS:
            break
    return out


def parse_csv_tickers(csv_text: str) -> list[str]:
    """Tickers from a CSV: a Symbol/Ticker column if present, else column 0."""
    csv_text = csv_text.lstrip(_BOM)
    reader = csv.reader(io.StringIO(csv_text))
    rows = [r for r in reader if r]
    if not rows:
        return []
    header = [c.strip().lower() for c in rows[0]]
    col = 0
    has_header = False
    for name in ("symbol", "ticker"):
        if name in header:
            col = header.index(name)
            has_header = True
            break
    body = rows[1:] if has_header else rows
    return parse_tickers("\n".join(r[col] for r in body if len(r) > col))


def batch_fit(
    tickers: Sequence[str],
    fit_fn: Callable[[str], FitVerdict],
    progress: Callable[[float, str], None] | None = None,
) -> list[BatchFitRow]:
    """Run *fit_fn* per ticker; failures become UNKNOWN/DATA_GAP rows."""
    rows: list[BatchFitRow] = []
    n = len(tickers)
    for i, t in enumerate(tickers):
        if progress is not None:
            progress((i + 1) / max(n, 1), t)
        try:
            rows.append(BatchFitRow(ticker=t, verdict=fit_fn(t), fetch_ok=True))
        except Exception as exc:
            logger.warning(f"batch fit failed for {t}: {exc}")
            rows.append(
                BatchFitRow(
                    ticker=t,
                    verdict=FitVerdict(
                        ticker=t,
                        evidence_grade="UNKNOWN",
                        fit_flags=(
                            FitFlag(
                                kind="DATA_GAP",
                                message=f"Could not assess {t} (fetch failed).",
                                severity="INFO",
                            ),
                        ),
                        summary=f"{t} could not be assessed this run.",
                    ),
                    fetch_ok=False,
                )
            )
    return rows


def default_fit_fn(ticker: str) -> FitVerdict:
    """Production fit_fn: the ADR-054 gather path with live beta."""
    from datetime import datetime, timezone

    from application.fit_use_case import (
        default_beta_fn,
        gather_and_assess,
        market_systematic_share_threshold,
    )

    return gather_and_assess(
        ticker=ticker,
        reports_dir="data/reports",
        summary_path="data/personal/brief_summary.json",
        holdings_path="data/personal/holdings.csv",
        beta_fn=default_beta_fn,
        as_of=datetime.now(timezone.utc),
        systematic_share_threshold=market_systematic_share_threshold(),
    )
