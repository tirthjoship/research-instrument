"""Tests for GeminiNarratorAdapter.

NOTE: No source-scan test for gemini_narrator.py — that file's _PROMPT literally
negates the forbidden words ("Do NOT use buy, sell, ..."). A naive inspect.getsource
scan would flag them falsely. The honesty assertion is on rendered TEMPLATE OUTPUT
in test_template_case_output_has_no_forbidden_words (Task 5, below).
"""

from adapters.ml.gemini_narrator import GeminiNarratorAdapter, parse_case_json
from domain.case_models import CaseContext


def test_parse_case_json_maps_both_sides():
    raw = (
        '{"in_favor":[{"text":"Beat EPS 3 of 4","source":"reported"}],'
        '"to_watch":[{"text":"Below 200-day trend","source":"technical"}]}'
    )
    res = parse_case_json(raw)
    assert res.in_favor[0].source_tag == "reported"
    assert res.to_watch[0].text == "Below 200-day trend"
    assert res.data_gap is False


def test_parse_garbage_is_gap():
    assert parse_case_json("not json").data_gap is True


def test_adapter_without_key_falls_back_to_gap(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY_2", raising=False)
    adapter = GeminiNarratorAdapter()
    res = adapter.summarize_case(CaseContext("X", facts=("Valuation: cheap",), news=()))
    assert res.data_gap is True  # no key → honest gap, never fabricated


def test_adapter_uses_second_key_when_first_is_quota_exhausted(monkeypatch):
    """A second GEMINI_API_KEY_2 must absorb load once the first key's quota
    is exhausted — the adapter should not degrade to data_gap while a
    working fallback key is still available."""
    import adapters.ml.gemini_narrator as narrator_mod

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY_2", "key-2")

    calls: list[tuple[str, ...]] = []

    def fake_generate_with_key_fallback(api_keys, prompt, **kwargs):  # noqa: ANN001
        calls.append(tuple(api_keys))
        return '{"in_favor":[{"text":"Beat EPS","source":"reported"}],"to_watch":[]}'

    monkeypatch.setattr(
        narrator_mod, "generate_with_key_fallback", fake_generate_with_key_fallback
    )

    adapter = GeminiNarratorAdapter()
    res = adapter.summarize_case(CaseContext("X", facts=("Valuation: cheap",), news=()))
    assert res.data_gap is False
    assert res.in_favor[0].text == "Beat EPS"
    assert calls == [("key-2",)]


def test_adapter_explicit_key_still_used_as_sole_key(monkeypatch):
    """Passing an explicit api_key must not silently pull in env fallbacks —
    callers that construct the adapter with a specific key keep that
    contract."""
    import adapters.ml.gemini_narrator as narrator_mod

    monkeypatch.setenv("GEMINI_API_KEY_2", "env-key-2")

    calls: list[tuple[str, ...]] = []

    def fake_generate_with_key_fallback(api_keys, prompt, **kwargs):  # noqa: ANN001
        calls.append(tuple(api_keys))
        return '{"in_favor":[],"to_watch":[]}'

    monkeypatch.setattr(
        narrator_mod, "generate_with_key_fallback", fake_generate_with_key_fallback
    )

    adapter = GeminiNarratorAdapter(api_key="explicit-key")
    adapter.summarize_case(CaseContext("X", facts=("Valuation: cheap",), news=()))
    assert calls == [("explicit-key",)]


# EXEMPTION NOTE: We do NOT source-scan gemini_narrator.py for forbidden words.
# That file's _PROMPT literally negates them ("Do NOT use buy, sell, predict, …").
# A naive inspect.getsource scan would falsely flag those negations.
# Instead, we assert on the rendered OUTPUT of TemplateCaseSummarizer here.
def test_template_case_output_has_no_forbidden_words():
    from application.case_builder import TemplateCaseSummarizer, build_case_context
    from domain.evidence_rag import RagColor, RagSignal
    from domain.fit import FORBIDDEN_WORDS

    ctx = build_case_context(
        "YUMC",
        (RagSignal("Valuation", RagColor.GREEN, "PEG 0.9 cheap"),),
        [],
    )
    res = TemplateCaseSummarizer().summarize_case(ctx)
    rendered = " ".join(p.text for p in res.in_favor + res.to_watch).lower()
    for w in FORBIDDEN_WORDS:
        assert (
            w not in rendered
        ), f"Forbidden word '{w}' found in rendered case output: {rendered!r}"
