"""Delisted-ticker prune list. A name returning no data for `threshold`
consecutive weekly runs is treated as delisted: logged loudly, skipped from
assessment, and persisted to a gitignored JSON so it is not re-fetched (yfinance
is throttled). Reversible: delete the ticker's key (or the file) to retry.

PRIVACY: the file lives under data/personal/ and is never committed."""

from __future__ import annotations

import json
import os
from typing import Any


def record_fetch_outcome(
    state: dict[str, int], ticker: str, had_data: bool
) -> dict[str, int]:
    """Return a new state with ticker's consecutive-no-data counter updated:
    incremented on no-data, reset to 0 on data. Pure (copies input)."""
    out = dict(state)
    out[ticker] = 0 if had_data else out.get(ticker, 0) + 1
    return out


def is_delisted(state: dict[str, int], ticker: str, threshold: int = 3) -> bool:
    """True once a ticker has `threshold` consecutive no-data weeks. The
    threshold guards against a one-off yfinance hiccup pruning a live name."""
    return state.get(ticker, 0) >= threshold


def load_prune_list(path: str) -> dict[str, int]:
    if not os.path.exists(path):
        return {}
    with open(path) as fh:
        data: dict[str, Any] = json.load(fh)
    return {str(k): int(v) for k, v in data.items()}


def save_prune_list(path: str, state: dict[str, int]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as fh:
        json.dump(state, fh, indent=2, sort_keys=True)
