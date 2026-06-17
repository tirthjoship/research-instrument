"""Fama-French long-short factor returns adapter.

Supplies synthetic cumulative price-index series for FF5 + Momentum factors
(SMB, HML, MOM, RMW, CMA) so they satisfy the PriceProvider contract:

    PriceProvider = Callable[[str, datetime, datetime], list[tuple[datetime, float]]]

The macro-beta scrubber calls daily_returns(series) on the returned list, which
recovers the actual factor returns.

Data sources (both confirmed working):
- FF5 daily:  https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/
              F-F_Research_Data_5_Factors_2x3_daily_CSV.zip
- Momentum:   https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/
              F-F_Momentum_Factor_daily_CSV.zip

Values in the CSV are in percent (e.g. 0.79 = 0.79% = 0.0079 fraction).
Only rows matching the pattern ``^\\s*\\d{8},`` are treated as daily data;
trailing monthly/annual junk rows are silently skipped.
"""

from __future__ import annotations

import io
import json
import re
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from loguru import logger

# ── Public constant — other modules import this to route factor names ──────────

FF_FACTORS: frozenset[str] = frozenset({"SMB", "HML", "MOM", "RMW", "CMA"})

# ── Internal constants ─────────────────────────────────────────────────────────

_FF5_URL = (
    "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
    "F-F_Research_Data_5_Factors_2x3_daily_CSV.zip"
)
_MOM_URL = (
    "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
    "F-F_Momentum_Factor_daily_CSV.zip"
)
_DATE_ROW_RE = re.compile(r"^\s*\d{8},")
_DEFAULT_CACHE_PATH = Path("data/cache/fama_french_daily.json")
_REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0"}
_REQUEST_TIMEOUT = 30

# ── Type alias ─────────────────────────────────────────────────────────────────

# {YYYY-MM-DD: {factor_name: fraction}}
_RowsDict = dict[str, dict[str, float]]


# ── Parsing helpers ────────────────────────────────────────────────────────────


def _fetch_zip_text(url: str) -> str:
    """Download a zip from *url* and return the text of the first member."""
    logger.info("Fetching Fama-French zip: {}", url)
    resp = requests.get(url, headers=_REQUEST_HEADERS, timeout=_REQUEST_TIMEOUT)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        member = zf.namelist()[0]
        raw_bytes = zf.read(member)
    return raw_bytes.decode("latin-1")


def _parse_ff5(text: str) -> dict[str, dict[str, float]]:
    """Parse FF5 daily CSV text → {date_str: {SMB,HML,RMW,CMA: fraction}}.

    Column layout after splitting on ',' (0-indexed):
        0=date  1=Mkt-RF  2=SMB  3=HML  4=RMW  5=CMA  6=RF
    Source header: ,Mkt-RF,SMB,HML,RMW,CMA,RF
    """
    rows: dict[str, dict[str, float]] = {}
    for line in text.splitlines():
        if not _DATE_ROW_RE.match(line):
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 6:
            continue
        date_raw = parts[0].strip()
        try:
            dt = datetime.strptime(date_raw, "%Y%m%d")
        except ValueError:
            continue
        date_str = dt.strftime("%Y-%m-%d")
        try:
            rows[date_str] = {
                "SMB": float(parts[2]) / 100.0,
                "HML": float(parts[3]) / 100.0,
                "RMW": float(parts[4]) / 100.0,
                "CMA": float(parts[5]) / 100.0,
            }
        except (ValueError, IndexError):
            continue
    return rows


def _parse_mom(text: str) -> dict[str, float]:
    """Parse Momentum daily CSV text → {date_str: fraction}."""
    rows: dict[str, float] = {}
    for line in text.splitlines():
        if not _DATE_ROW_RE.match(line):
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 2:
            continue
        date_raw = parts[0].strip()
        try:
            dt = datetime.strptime(date_raw, "%Y%m%d")
        except ValueError:
            continue
        date_str = dt.strftime("%Y-%m-%d")
        try:
            rows[date_str] = float(parts[1]) / 100.0
        except ValueError:
            continue
    return rows


def _download_and_merge() -> _RowsDict:
    """Fetch both zips and return the merged rows dict (intersection of dates)."""
    ff5_text = _fetch_zip_text(_FF5_URL)
    mom_text = _fetch_zip_text(_MOM_URL)

    ff5_rows = _parse_ff5(ff5_text)
    mom_rows = _parse_mom(mom_text)

    common_dates = set(ff5_rows.keys()) & set(mom_rows.keys())
    logger.info(
        "FF5 dates: {}, MOM dates: {}, common: {}",
        len(ff5_rows),
        len(mom_rows),
        len(common_dates),
    )

    merged: _RowsDict = {}
    for d in common_dates:
        merged[d] = {**ff5_rows[d], "MOM": mom_rows[d]}
    return merged


# ── Main provider class ────────────────────────────────────────────────────────


class FamaFrenchProvider:
    """Provides synthetic cumulative-index series for FF long-short factors.

    On construction the provider either loads from disk cache or downloads
    the two FF zips and writes `data/cache/fama_french_daily.json`.

    Signature compatible with PriceProvider contract:
        provider.series(name, start, end) -> list[tuple[datetime, float]]
    """

    def __init__(
        self,
        cache_path: Path = _DEFAULT_CACHE_PATH,
        refresh: bool = False,
        _rows: _RowsDict | None = None,
    ) -> None:
        """Create provider.

        Args:
            cache_path: Path to the JSON cache file.
            refresh: If True, always re-download even when a cache exists.
            _rows: Internal injection for tests — skips all I/O when supplied.
        """
        self._cache_path = cache_path
        self._rows: _RowsDict = {}

        if _rows is not None:
            # Test injection path — no I/O at all.
            self._rows = _rows
            return

        if not refresh and self._cache_exists():
            loaded = self._load_cache()
            if loaded:
                logger.info("Loaded Fama-French cache from {}", cache_path)
                self._rows = loaded
                return
            logger.warning("Cache file empty/corrupt; re-downloading.")

        try:
            self._rows = _download_and_merge()
            self._write_cache(self._rows)
        except Exception as exc:
            # Fall back to whatever was on disk (may be partial).
            fallback = self._load_cache() if self._cache_exists() else {}
            if fallback:
                logger.warning(
                    "Download failed ({}); falling back to stale cache.", exc
                )
                self._rows = fallback
            else:
                raise RuntimeError(
                    f"Failed to fetch Fama-French data and no cache found: {exc}"
                ) from exc

    # ── Public API ─────────────────────────────────────────────────────────────

    def series(
        self,
        name: str,
        start: datetime,
        end: datetime,
    ) -> list[tuple[datetime, float]]:
        """Return a synthetic cumulative-index price series for *name*.

        The series is built from factor returns so that
        ``daily_returns(series)`` recovers the original factor returns.

        Point-in-time guarantee: no date after *end* is ever returned.

        Args:
            name:  Factor name, must be in FF_FACTORS.
            start: Inclusive lower bound.
            end:   Inclusive upper bound (PIT hard ceiling).

        Returns:
            Ascending list of (datetime, price_level) starting at 100.0.
            Empty list if *name* is unknown or no data falls in [start, end].
        """
        if name not in FF_FACTORS:
            return []

        # Collect in-window dates, strictly respecting PIT (end is hard ceiling).
        window_dates: list[datetime] = []
        for date_str in sorted(self._rows.keys()):
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                continue
            if dt < start:
                continue
            if dt > end:
                # PIT: never include dates beyond end.
                continue
            if name not in self._rows[date_str]:
                continue
            window_dates.append(dt)

        if not window_dates:
            return []

        # Build cumulative index.  Index starts at 100.0 on the first date.
        index_series: list[tuple[datetime, float]] = []
        level = 100.0
        index_series.append((window_dates[0], level))
        for dt in window_dates[1:]:
            r = self._rows[dt.strftime("%Y-%m-%d")][name]
            level = level * (1.0 + r)
            index_series.append((dt, level))

        return index_series

    def refresh(self) -> None:
        """Re-download both zips and overwrite the cache."""
        logger.info("Refreshing Fama-French data from remote.")
        self._rows = _download_and_merge()
        self._write_cache(self._rows)

    # ── Cache helpers ──────────────────────────────────────────────────────────

    def _cache_exists(self) -> bool:
        return self._cache_path.exists() and self._cache_path.stat().st_size > 0

    def _load_cache(self) -> _RowsDict:
        try:
            with self._cache_path.open("r", encoding="utf-8") as fh:
                data: dict[str, Any] = json.load(fh)
            rows: _RowsDict = data.get("rows", {})
            return rows
        except (json.JSONDecodeError, OSError, KeyError) as exc:
            logger.warning("Could not load cache {}: {}", self._cache_path, exc)
            return {}

    def _write_cache(self, rows: _RowsDict) -> None:
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        # Use the latest data date as the fetched stamp (no datetime.now()).
        fetched_stamp = max(rows.keys()) if rows else "unknown"
        payload: dict[str, Any] = {"fetched": fetched_stamp, "rows": rows}
        with self._cache_path.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        logger.info(
            "Wrote Fama-French cache to {} ({} dates)", self._cache_path, len(rows)
        )
