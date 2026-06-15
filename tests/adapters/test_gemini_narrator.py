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
    adapter = GeminiNarratorAdapter()
    res = adapter.summarize_case(CaseContext("X", facts=("Valuation: cheap",), news=()))
    assert res.data_gap is True  # no key → honest gap, never fabricated


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
