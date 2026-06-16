"""Google-AI cited-case summarizer (CaseSummarizerPort). Summarises ONLY supplied cited facts/news.

Honesty: prompt forbids trade verbs; output is attributed; any failure -> data_gap=True (never faked).
"""

from __future__ import annotations

import json
import os

from domain.case_models import CaseContext, CasePoint, CaseResult

_MODEL = "gemini-flash-latest"
_PROMPT = (
    "You summarise an investment research CASE from ONLY the facts and cited article titles given. "
    'Output STRICT JSON: {{"in_favor":[{{"text":..,"source":..}}],"to_watch":[{{"text":..,"source":..}}]}}. '
    "Up to 5 each side. Use ONLY the supplied facts/sources — invent nothing. "
    "Do NOT use the words buy, sell, predict, winner, conviction, alpha, or outperform. "
    "This informs the reader; it is NOT a recommendation.\n\nFACTS:\n{facts}\n\nARTICLES:\n{news}"
)


def parse_case_json(raw: str) -> CaseResult:
    try:
        data = json.loads(raw[raw.index("{") : raw.rindex("}") + 1])
        favor = tuple(
            CasePoint(p["text"], p.get("source", "")) for p in data.get("in_favor", [])
        )
        watch = tuple(
            CasePoint(p["text"], p.get("source", "")) for p in data.get("to_watch", [])
        )
        if not favor and not watch:
            return CaseResult((), (), True)
        return CaseResult(favor[:5], watch[:5], False)
    except Exception:  # noqa: BLE001 — any parse failure → honest gap
        return CaseResult((), (), True)


class GeminiNarratorAdapter:
    def __init__(self, api_key: str | None = None) -> None:
        self._key = api_key or os.environ.get("GEMINI_API_KEY")

    def summarize_case(self, ctx: CaseContext) -> CaseResult:
        if not self._key:
            return CaseResult((), (), True)
        try:
            import google.generativeai as genai  # lazy import (matches GeminiEventClassifier)

            genai.configure(api_key=self._key)
            model = genai.GenerativeModel(_MODEL)
            prompt = _PROMPT.format(
                facts="\n".join(ctx.facts),
                news="\n".join(f"[{s}] {t}" for s, t in ctx.news) or "(none)",
            )
            resp = model.generate_content(prompt)
            return parse_case_json(resp.text)
        except Exception:  # noqa: BLE001 — network/quota/parse → honest gap
            return CaseResult((), (), True)
