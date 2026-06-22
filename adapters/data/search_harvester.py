"""Free search API -> real, citable candidate URLs (spec §4). Search is a fact
source; the LLM never invents URLs. Provider fallback handled by the injected client."""

from __future__ import annotations

import re
from datetime import date
from typing import Callable

_QUERIES = [
    "stocks to buy now analyst",
    "best stocks to invest in this week",
    "top stock picks",
]


class SearchHarvester:
    def __init__(
        self,
        search: Callable[[str], list[dict[str, object]]],
        known_tickers: set[str],
        cap: int = 25,
    ):
        self._search = search
        self._known = known_tickers
        self._cap = cap

    def search_candidates(self, as_of: date) -> list[dict[str, object]]:
        out: list[dict[str, object]] = []
        seen: set[tuple[str, str]] = set()
        for q in _QUERIES:
            try:
                results = self._search(q)
            except Exception:
                continue
            for r in results:
                text = f"{r.get('title', '')} {r.get('content', '')}"
                for tk in self._tickers_in(text):
                    url = str(r["url"])
                    key = (tk, url)
                    if key in seen:
                        continue
                    seen.add(key)
                    out.append({"ticker": tk, "url": url, "snippet": text[:400]})
                    if len(out) >= self._cap:
                        return out
        return out

    def _tickers_in(self, text: str) -> list[str]:
        toks = set(re.findall(r"\b[A-Z]{1,5}\b", text))
        return [t for t in toks if t in self._known]
