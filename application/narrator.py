"""Default templated narrator + a fake for tests. The real local-LLM adapter lives
in adapters/ml/ollama_narrator.py and falls back to template_narration on any error."""

from __future__ import annotations


def template_narration(context: dict[str, object]) -> str:
    """Deterministic plain-English explanation built from the computed context.
    Used as the graceful default when no LLM is available."""
    t = context.get("ticker", "?")
    v = context.get("verdict", "REVIEW")
    th = context.get("trend_health")
    unreal = context.get("unrealized_pct")
    acct = context.get("account_type", "")
    raw_flags = context.get("behavior_flags") or []
    flags: list[object] = list(raw_flags) if isinstance(raw_flags, list) else []
    parts: list[str] = [f"{t}: {v}."]
    if isinstance(th, (int, float)):
        where = "above" if th >= 0 else "below"
        parts.append(f"Price is {abs(float(th)):.1f} ATRs {where} its 200-day trend.")
    if isinstance(unreal, (int, float)):
        parts.append(f"Position is {float(unreal) * 100:+.0f}% vs cost.")
    if "disposition_risk" in flags:
        parts.append("This is the hold-a-loser pattern — broken trend held at a loss.")
    if "winner_past_stop" in flags:
        parts.append("Winner that breached its trailing stop — consider trimming.")
    if str(v).upper() == "TRIM":
        parts.append(
            "TRIM manages position size / locks gains — not a prediction the name will fall."
        )
    if acct and str(acct).upper() in {"TFSA", "RRSP", "FHSA"}:
        parts.append(f"In a {acct}, there is no capital-gains tax friction on selling.")
    return " ".join(parts)


class FakeNarrator:
    """Test double implementing NarratorPort."""

    def __init__(self, canned: str = "narration") -> None:
        self._canned = canned

    def narrate(self, context: dict[str, object]) -> str:
        return self._canned
