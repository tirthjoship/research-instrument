"""Cited-case cache — read/write JSON store for CaseResult objects.

Cache path convention: data/personal/cited_cases.json (gitignored).

Schema:
    {
        "as_of": "YYYY-MM-DD",
        "cases": {
            "<TICKER>": {
                "in_favor": [{"text": str, "source": str}, ...],
                "to_watch":  [{"text": str, "source": str}, ...],
                "data_gap":  bool
            }
        }
    }

No staleness logic beyond "key present or not" — callers decide freshness.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import cast

from domain.case_models import CasePoint, CaseResult

# Public cache path (gitignored via data/personal/).
CITED_CASES_PATH = "data/personal/cited_cases.json"


# ---------------------------------------------------------------------------
# Serialize / deserialize
# ---------------------------------------------------------------------------


def serialize_case(result: CaseResult) -> dict[str, object]:
    """Convert a CaseResult to a JSON-safe dict."""
    return {
        "in_favor": [{"text": p.text, "source": p.source_tag} for p in result.in_favor],
        "to_watch": [{"text": p.text, "source": p.source_tag} for p in result.to_watch],
        "data_gap": result.data_gap,
    }


def deserialize_case(d: dict[str, object]) -> CaseResult:
    """Reconstruct a CaseResult from a serialized dict."""
    raw_favor = cast(list[dict[str, object]], d.get("in_favor") or [])
    raw_watch = cast(list[dict[str, object]], d.get("to_watch") or [])
    in_favor = tuple(
        CasePoint(text=str(p["text"]), source_tag=str(p["source"])) for p in raw_favor
    )
    to_watch = tuple(
        CasePoint(text=str(p["text"]), source_tag=str(p["source"])) for p in raw_watch
    )
    return CaseResult(
        in_favor=in_favor,
        to_watch=to_watch,
        data_gap=bool(d.get("data_gap", False)),
    )


# ---------------------------------------------------------------------------
# Read / write
# ---------------------------------------------------------------------------


def write_case_cache(
    path: str,
    as_of: str,
    cases: dict[str, CaseResult],
) -> None:
    """Write (overwrite) the cache at *path* with the given ticker→result map.

    Creates parent directories if absent.
    """
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "as_of": as_of,
        "cases": {ticker: serialize_case(r) for ticker, r in cases.items()},
    }
    Path(path).write_text(json.dumps(payload, indent=2))


def load_cached_case(path: str, ticker: str) -> CaseResult | None:
    """Return the cached CaseResult for *ticker*, or None if absent/unreadable."""
    if not os.path.exists(path):
        return None
    try:
        payload = json.loads(Path(path).read_text())
        cases = payload.get("cases", {})
        if ticker not in cases:
            return None
        return deserialize_case(cases[ticker])
    except Exception:
        return None
