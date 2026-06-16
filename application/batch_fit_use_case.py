"""Batch fit verdicts for a user-supplied ticker list (Screener upload)."""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from typing import Any, Callable, Sequence

from loguru import logger

from domain.fit import FitFlag, FitVerdict


@dataclass(frozen=True)
class BatchFitRow:
    ticker: str
    verdict: FitVerdict
    fetch_ok: bool
    factor_scores: tuple[dict[str, object], ...] = ()


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
    screen: dict[str, Any] | None = None,
    live_fetch: bool = False,
    fetch_fn: Callable[[str], dict[str, float | None]] | None = None,
) -> list[BatchFitRow]:
    """Run *fit_fn* per ticker; failures become UNKNOWN/DATA_GAP rows.

    Args:
        tickers: Ticker symbols to assess.
        fit_fn: Callable returning a FitVerdict for a single ticker.
        progress: Optional progress callback (fraction, ticker).
        screen: Optional persisted screen dict. When provided, factor_scores
            are looked up (in-screen) or computed live (off-universe when
            live_fetch=True) via ticker_factor_scores. When None, factor_scores
            stays empty.
        live_fetch: When True and screen is provided, off-universe tickers get
            their factor_scores computed via live data (or the injected fetch_fn
            if supplied). Default False preserves legacy DATA-GAP behaviour.
        fetch_fn: Optional injectable fetch callable (ticker -> factor dict).
            When live_fetch=True and fetch_fn is provided, this is used instead
            of constructing the default live adapter. Intended for testing with
            fake adapters. Ignored when live_fetch=False.
    """
    from application.ticker_factors_use_case import (
        live_factor_fetch_fn,
        ticker_factor_scores,
    )

    # Resolve which fetch callable to pass to ticker_factor_scores
    def _no_fetch(_ticker: str) -> dict[str, float | None]:
        raise RuntimeError("No live fetch wired in batch_fit")

    resolved_fetch_fn: Callable[[str], dict[str, float | None]]
    if live_fetch:
        resolved_fetch_fn = fetch_fn if fetch_fn is not None else live_factor_fetch_fn()
    else:
        resolved_fetch_fn = _no_fetch

    rows: list[BatchFitRow] = []
    n = len(tickers)
    for i, t in enumerate(tickers):
        if progress is not None:
            progress((i + 1) / max(n, 1), t)
        try:
            verdict = fit_fn(t)
            fs: tuple[dict[str, Any], ...] = ()
            if screen is not None:
                fs = tuple(
                    ticker_factor_scores(t, screen=screen, fetch_fn=resolved_fetch_fn)
                )
            rows.append(
                BatchFitRow(ticker=t, verdict=verdict, fetch_ok=True, factor_scores=fs)
            )
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
