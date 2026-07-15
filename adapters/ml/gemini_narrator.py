"""Google-AI cited-case summarizer (CaseSummarizerPort). Summarises ONLY supplied cited facts/news.

Honesty: prompt forbids trade verbs; output is attributed; any failure -> data_gap=True (never faked).
"""

from __future__ import annotations

import json

from adapters.ml.gemini_models import generate_with_key_fallback, load_gemini_api_keys
from domain.case_models import CaseContext, CasePoint, CaseResult

_PROMPT = (
    "You summarise an investment research CASE from ONLY the facts and cited article titles given. "
    'Output STRICT JSON: {{"in_favor":[{{"text":..,"source":..}}],"to_watch":[{{"text":..,"source":..}}]}}. '
    "Up to 5 each side. Use ONLY the supplied facts/sources — invent nothing. "
    "Do NOT use the words buy, sell, predict, winner, conviction, alpha, or outperform. "
    "This informs the reader; it is NOT a recommendation.\n\nFACTS:\n{facts}\n\nARTICLES:\n{news}"
)

# Batched variant — one prompt, N tickers, one JSON response keyed by ticker.
# Cuts daily Gemini quota usage from N calls to ceil(N / chunk_size) — see
# application.case_batch.run_cases_in_batches for the chunking orchestration.
_BATCH_PROMPT = (
    "You summarise investment research CASES for MULTIPLE tickers, each from ONLY "
    "the facts and cited article titles given for that ticker. "
    'Output STRICT JSON keyed by ticker: {{"TICKER":{{"in_favor":[{{"text":..,"source":..}}],'
    '"to_watch":[{{"text":..,"source":..}}]}}, ...}}. One entry per ticker listed below, '
    "using ONLY that ticker's own facts/sources — never mix tickers, invent nothing. "
    "Up to 5 points each side per ticker. "
    "Do NOT use the words buy, sell, predict, winner, conviction, alpha, or outperform. "
    "This informs the reader; it is NOT a recommendation.\n\n{cases}"
)


def _case_result_from_dict(data: dict[str, object]) -> CaseResult:
    favor = tuple(
        CasePoint(p["text"], p.get("source", "")) for p in data.get("in_favor", [])
    )
    watch = tuple(
        CasePoint(p["text"], p.get("source", "")) for p in data.get("to_watch", [])
    )
    if not favor and not watch:
        return CaseResult((), (), True)
    return CaseResult(favor[:5], watch[:5], False)


def parse_case_json(raw: str) -> CaseResult:
    try:
        data = json.loads(raw[raw.index("{") : raw.rindex("}") + 1])
        return _case_result_from_dict(data)
    except Exception:  # noqa: BLE001 — any parse failure → honest gap
        return CaseResult((), (), True)


def parse_batch_case_json(
    raw: str, tickers: "tuple[str, ...]"
) -> dict[str, CaseResult]:
    """Parse a batched {"TICKER": {...}, ...} response.

    Any ticker missing from the response, or the whole response failing to
    parse, degrades that ticker to CaseResult((), (), True) — same honesty
    guarantee as the single-ticker parse_case_json, never fabricated.
    """
    gap = CaseResult((), (), True)
    try:
        data = json.loads(raw[raw.index("{") : raw.rindex("}") + 1])
        return {
            t: (_case_result_from_dict(data[t]) if t in data else gap) for t in tickers
        }
    except Exception:  # noqa: BLE001 — any parse failure → honest gap for all
        return dict.fromkeys(tickers, gap)


class GeminiNarratorAdapter:
    def __init__(self, api_key: str | None = None) -> None:
        # An explicit api_key is used as the sole key (caller's contract);
        # otherwise collect GEMINI_API_KEY + any numbered fallbacks
        # (GEMINI_API_KEY_2, _3, ...) so a second key can absorb load once an
        # earlier key's daily free-tier quota is exhausted.
        self._keys = (api_key,) if api_key else load_gemini_api_keys()

    def summarize_case(self, ctx: CaseContext) -> CaseResult:
        if not self._keys:
            return CaseResult((), (), True)
        try:
            prompt = _PROMPT.format(
                facts="\n".join(ctx.facts),
                news="\n".join(f"[{s}] {t}" for s, t in ctx.news) or "(none)",
            )
            text = generate_with_key_fallback(self._keys, prompt)
            return parse_case_json(text)
        except Exception:  # noqa: BLE001 — network/quota/parse → honest gap
            return CaseResult((), (), True)

    def summarize_cases(self, contexts: list[CaseContext]) -> dict[str, CaseResult]:
        """Batched variant of summarize_case: one API call for every ctx in
        *contexts*, not one call each. See _BATCH_PROMPT's module docstring."""
        if not contexts:
            return {}
        tickers = tuple(ctx.ticker for ctx in contexts)
        gap = {t: CaseResult((), (), True) for t in tickers}
        if not self._keys:
            return gap
        try:
            cases_block = "\n---\n".join(
                f"TICKER: {ctx.ticker}\nFACTS:\n{chr(10).join(ctx.facts)}\n"
                f"ARTICLES:\n{chr(10).join(f'[{s}] {t}' for s, t in ctx.news) or '(none)'}"
                for ctx in contexts
            )
            prompt = _BATCH_PROMPT.format(cases=cases_block)
            text = generate_with_key_fallback(self._keys, prompt)
            return parse_batch_case_json(text, tickers)
        except Exception:  # noqa: BLE001 — network/quota/parse → honest gap
            return gap
