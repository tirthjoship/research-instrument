def test_template_narration_mentions_verdict_and_ticker():
    from application.narrator import template_narration

    ctx = {
        "ticker": "MU",
        "verdict": "REDUCE",
        "trend_health": -3.0,
        "unrealized_pct": -0.31,
        "account_type": "TFSA",
        "downside_to_stop": 0.1,
        "upside_to_recover": 0.3,
        "behavior_flags": ["disposition_risk"],
    }
    text = template_narration(ctx)
    assert "MU" in text and "REDUCE" in text
    assert "TFSA" in text


def test_template_narration_trim_is_not_framed_as_a_down_call():
    # ADR-048: TRIM is position-sizing / lock-gains, NOT a prediction of a drop.
    from application.narrator import template_narration

    text = template_narration(
        {"ticker": "WIN", "verdict": "TRIM", "behavior_flags": ["winner_past_stop"]}
    )
    assert "TRIM" in text
    assert "not a prediction" in text.lower()


def test_fake_narrator_cannot_change_verdict():
    from application.narrator import FakeNarrator

    n = FakeNarrator(canned="explained")
    assert n.narrate({"ticker": "X", "verdict": "HOLD"}) == "explained"


def test_ollama_falls_back_to_template_when_unreachable():
    from adapters.ml.ollama_narrator import OllamaNarratorAdapter

    n = OllamaNarratorAdapter(base_url="http://127.0.0.1:9", model="x", timeout=0.2)
    ctx = {
        "ticker": "MU",
        "verdict": "REDUCE",
        "trend_health": -3.0,
        "unrealized_pct": -0.31,
        "account_type": "TFSA",
        "behavior_flags": ["disposition_risk"],
    }
    text = n.narrate(ctx)
    assert "MU" in text and "REDUCE" in text


def test_ollama_uses_model_text_when_available(monkeypatch):
    import adapters.ml.ollama_narrator as mod

    def fake_call(self, prompt):
        return "LLM SAYS: trim it"

    monkeypatch.setattr(mod.OllamaNarratorAdapter, "_call", fake_call, raising=True)
    n = mod.OllamaNarratorAdapter()
    assert n.narrate({"ticker": "X", "verdict": "TRIM"}) == "LLM SAYS: trim it"
