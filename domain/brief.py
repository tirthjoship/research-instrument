"""Pure assembly + formatting for the unified weekly brief (no IO).

Phase B adds NO predictive claim — it composes the Phase-A screen and the
discipline engine honestly. RESEARCH_ONLY screens never render 'buy' language.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

__all__ = [
    "BuyCandidateLine",
    "HoldingVerdictLine",
    "ConcentrationFlag",
    "ResearchLink",
    "ScorecardSnapshot",
    "WeeklyBrief",
    "assemble_brief",
    "to_markdown",
    "to_stdout_masked",
]

from domain.discipline import Verdict
from domain.models import PortfolioRisk, PositionRisk
from domain.regime import Regime
from domain.screen_models import ScreenCandidate, ScreenLabel, ScreenResult


@dataclass(frozen=True)
class BuyCandidateLine:
    ticker: str
    composite: float
    factor_summary: str
    why: str
    already_held: bool
    label: ScreenLabel


@dataclass(frozen=True)
class HoldingVerdictLine:
    ticker: str
    unrealized_pct: float
    trend_state: str  # "uptrend" | "broken" | "unknown"
    verdict: Verdict
    why: str


@dataclass(frozen=True)
class ConcentrationFlag:
    descriptor: str
    soft_warning: bool


@dataclass(frozen=True)
class ResearchLink:
    source: str
    linked: str
    relationship: str


@dataclass(frozen=True)
class ScorecardSnapshot:
    screen_window: str
    screen_top_ret: float | None
    screen_spy_ret: float | None
    screen_n: int
    screen_significant: bool
    discipline_window: str
    discipline_reduce_down_rate: float | None
    discipline_n: int
    discipline_gate_status: str


@dataclass(frozen=True)
class WeeklyBrief:
    as_of: str
    regime: Regime
    tilt: dict[str, float]
    candidates: tuple[BuyCandidateLine, ...]
    holdings: tuple[HoldingVerdictLine, ...]
    research_links: tuple[ResearchLink, ...]
    concentration: tuple[ConcentrationFlag, ...]
    scorecard: ScorecardSnapshot
    screen_label: ScreenLabel


# ---------------------------------------------------------------------------
# Verdict urgency for ordering holdings (most urgent first).
# ---------------------------------------------------------------------------

_VERDICT_ORDER: dict[Verdict, int] = {
    Verdict.REDUCE: 0,
    Verdict.TRIM: 1,
    Verdict.REVIEW: 2,
    Verdict.HOLD: 3,
    Verdict.ADD_OK: 4,
}


def _factor_summary(cand: ScreenCandidate) -> str:
    parts: list[str] = []
    for fs in cand.factor_scores:
        # A flagged-neutral factor has value==0 and percentile==0 (no coverage).
        if fs.value == 0.0 and fs.percentile == 0.0:
            parts.append(f"{fs.name[:3]} n/a")
        else:
            parts.append(f"{fs.name[:3]} p{int(round(fs.percentile * 100))}")
    trend = "trend ok" if cand.trend_health >= 0 else "trend weak"
    return " · ".join(parts) + " · " + trend


def _trend_state(th: float | None) -> str:
    if th is None:
        return "unknown"
    return "uptrend" if th >= 0 else "broken"


def assemble_brief(
    *,
    as_of: str,
    regime: Regime,
    tilt: dict[str, float],
    screen_result: ScreenResult,
    screen_label: ScreenLabel,
    top_n: int,
    positions: list[PositionRisk],
    portfolio: PortfolioRisk,
    held_tickers: set[str],
    cluster_overlaps: dict[str, list[str]],
    scorecard: ScorecardSnapshot,
    concentration_threshold: float = 0.20,
) -> WeeklyBrief:
    """Compose a WeeklyBrief from already-fetched pieces (pure, IO-free).

    held_tickers: set of tickers the user holds (for already-held marking).
    cluster_overlaps: candidate ticker -> held tickers in its correlation cluster.
    """
    candidates = tuple(
        BuyCandidateLine(
            ticker=c.ticker,
            composite=c.composite,
            factor_summary=_factor_summary(c),
            why=c.why,
            already_held=c.ticker in held_tickers,
            label=screen_label,
        )
        for c in screen_result.candidates[:top_n]
    )

    holdings = tuple(
        sorted(
            (
                HoldingVerdictLine(
                    ticker=p.ticker,
                    unrealized_pct=p.unrealized_pct,
                    trend_state=_trend_state(p.trend_health),
                    verdict=p.verdict,
                    why=p.why,
                )
                for p in positions
            ),
            key=lambda h: _VERDICT_ORDER.get(h.verdict, 99),
        )
    )

    flags: list[ConcentrationFlag] = []
    if portfolio.top_concentration > concentration_threshold:
        flags.append(
            ConcentrationFlag(
                descriptor=(
                    f"Top concentration {portfolio.top_concentration:.0%} of book "
                    f"(> {concentration_threshold:.0%}) — correlated leverage on one bet, "
                    f"not diversification"
                ),
                soft_warning=True,
            )
        )
    for cand_ticker, overlaps in cluster_overlaps.items():
        if overlaps:
            flags.append(
                ConcentrationFlag(
                    descriptor=(
                        f"{cand_ticker} is in the same correlation cluster as "
                        f"{', '.join(overlaps)} you already hold — adds to an existing bet"
                    ),
                    soft_warning=True,
                )
            )

    return WeeklyBrief(
        as_of=as_of,
        regime=regime,
        tilt=dict(tilt),
        candidates=candidates,
        holdings=holdings,
        research_links=(),  # Phase C stub — populated only when Phase C ships.
        concentration=tuple(flags),
        scorecard=scorecard,
        screen_label=screen_label,
    )


# ---------------------------------------------------------------------------
# Markdown formatter
# ---------------------------------------------------------------------------


def _candidates_header(label: ScreenLabel) -> str:
    if label == ScreenLabel.VALIDATED:
        return "BUY CANDIDATES (validated)"
    return "EVIDENCE-RANKED CANDIDATES (research-only, not validated)"


def to_markdown(brief: WeeklyBrief) -> str:
    """Full brief as markdown — written to a gitignored file / rendered in the
    dashboard. Includes holding tickers + P&L (the file lives under data/personal/).

    RESEARCH_ONLY label suppresses all 'buy' language — header reads
    'EVIDENCE-RANKED CANDIDATES' instead.
    """
    tilt = brief.tilt
    tilt_str = " · ".join(
        f"{k} {tilt[k]:.0%}" for k in ("momentum", "revision", "quality", "value")
    )
    lines: list[str] = []
    lines.append(f"# WEEKLY BRIEF — {brief.as_of}")
    lines.append("")
    lines.append(f"**REGIME:** {brief.regime.value}  →  screen tilt: {tilt_str}")
    lines.append("")
    lines.append(f"## {_candidates_header(brief.screen_label)}")
    if not brief.candidates:
        lines.append("_(screen abstained — no eligible candidates)_")
    for c in brief.candidates:
        held = "  ⚠ already held" if c.already_held else ""
        lines.append(f"- **{c.ticker}**  {c.factor_summary}  — {c.why}{held}")
    lines.append("")
    lines.append("## HOLDINGS VERDICTS")
    for h in brief.holdings:
        lines.append(
            f"- **{h.ticker}**  {h.unrealized_pct:+.0%}  {h.trend_state}  "
            f"**{h.verdict.value}** — {h.why}"
        )
    lines.append("")
    lines.append("## RESEARCH LINKS (research-only, Phase C pending)")
    if not brief.research_links:
        lines.append("_(economic-link research ships in Phase C — not a signal)_")
    for link in brief.research_links:
        lines.append(
            f"- {link.source} → {link.linked} ({link.relationship}) → go research"
        )
    lines.append("")
    lines.append("## CONCENTRATION")
    if not brief.concentration:
        lines.append("_(no concentration flags)_")
    for f in brief.concentration:
        lines.append(f"- {f.descriptor}")
    lines.append("")
    lines.append("## SCORECARD")
    sc = brief.scorecard
    if sc.screen_n == 0:
        lines.append(
            f"- screen ({sc.screen_window}): n=0 — abstaining, no track record yet"
        )
    else:
        sig = "significant" if sc.screen_significant else "not significant"
        lines.append(
            f"- screen ({sc.screen_window}): top-10 {sc.screen_top_ret:+.2%} vs "
            f"SPY {sc.screen_spy_ret:+.2%} (n={sc.screen_n}, {sig})"
        )
    dr = (
        "n/a"
        if sc.discipline_reduce_down_rate is None
        else f"{sc.discipline_reduce_down_rate:.0%}"
    )
    lines.append(
        f"- discipline ({sc.discipline_window}): REDUCE down-rate {dr} "
        f"(n={sc.discipline_n}) — forward gate {sc.discipline_gate_status}"
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Masked stdout formatter
# ---------------------------------------------------------------------------


def to_stdout_masked(brief: WeeklyBrief) -> str:
    """Terminal summary — masks all holding-level detail (ADR-047).

    Shows: regime, public buy/evidence candidates (universe is public), aggregate
    holding verdict counts (NOT tickers or P&L), concentration as aggregate text,
    and the scorecard. Full detail goes only to the gitignored markdown file.

    Holdings tickers and per-position P&L are NEVER written to stdout.
    """
    lines: list[str] = []
    lines.append(f"WEEKLY BRIEF — {brief.as_of}   REGIME: {brief.regime.value}")
    lines.append(_candidates_header(brief.screen_label))
    for c in brief.candidates:
        held = "  [already held]" if c.already_held else ""
        lines.append(f"  {c.ticker}  {c.factor_summary}{held}")
    counts = Counter(h.verdict.value for h in brief.holdings)
    lines.append(
        "HOLDINGS (masked): " + ", ".join(f"{v} {counts[v]}" for v in sorted(counts))
    )
    if brief.concentration:
        lines.append(
            f"CONCENTRATION: {len(brief.concentration)} flag(s) — see full brief"
        )
    sc = brief.scorecard
    dr = (
        "n/a"
        if sc.discipline_reduce_down_rate is None
        else f"{sc.discipline_reduce_down_rate:.0%}"
    )
    screen_line = "n=0 (abstaining)" if sc.screen_n == 0 else f"n={sc.screen_n}"
    lines.append(
        f"SCORECARD: screen {screen_line}; discipline REDUCE down-rate {dr} "
        f"(n={sc.discipline_n}, gate {sc.discipline_gate_status})"
    )
    return "\n".join(lines)
