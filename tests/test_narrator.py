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


def test_fake_narrator_cannot_change_verdict():
    from application.narrator import FakeNarrator

    n = FakeNarrator(canned="explained")
    assert n.narrate({"ticker": "X", "verdict": "HOLD"}) == "explained"
