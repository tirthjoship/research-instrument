"""Evidence registry — the single source of truth tying every product metric to its research.

The project's credibility lives in docs/adr/ (8 pre-registered hypotheses, 7 killed/inconclusive,
1 forward-pending) and in the Trust tab. But the operational tabs historically showed numbers
WITHOUT that backing. This registry closes that gap: every metric the UI renders maps to an
``EvidenceEntry`` carrying its plain-English meaning, a healthy interpretation band, the ADR that
validated or killed related work, and an honest verdict/caveat.

Pure domain (stdlib only). UI layers look up an entry by key and render it inline (the
``evidence_chip`` component) so a number is never shown without its backing. Descriptive only —
nothing here is a forecast.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Verdict(str, Enum):
    """How much trust a metric has earned, from the project's falsification record."""

    VALIDATED = "VALIDATED"  # cleared a pre-registered gate
    DESCRIPTIVE = (
        "DESCRIPTIVE"  # a fact about today; no predictive claim made or needed
    )
    RESEARCH_ONLY = "RESEARCH_ONLY"  # surfaced for research; not a forward signal
    INCONCLUSIVE = "INCONCLUSIVE"  # tested; CI spanned 0 / underpowered
    FALSIFIED = "FALSIFIED"  # tested and killed; do not treat as predictive
    FORWARD_PENDING = "FORWARD_PENDING"  # live pre-registered gate, verdict not yet in


@dataclass(frozen=True)
class EvidenceEntry:
    """The backing for one product metric. Rendered inline next to the number."""

    key: str
    label: str
    meaning: str  # plain-English: what this number IS
    healthy_band: str | None  # interpretation context / healthy range, if any
    verdict: Verdict
    adr: str | None  # the ADR that validated/killed related work, e.g. "ADR-044"
    caveat: str  # the honest "what this is NOT" — guards against over-reading


# Single source of truth. Keys are stable identifiers the UI references.
_REGISTRY: dict[str, EvidenceEntry] = {
    # --- Home / book-health tiles ------------------------------------------------
    "need_review": EvidenceEntry(
        key="need_review",
        label="Need review",
        meaning="Count of holdings a discipline rule fired on this week.",
        healthy_band="0 is calm; rising counts mean more positions drifted from your rules.",
        verdict=Verdict.DESCRIPTIVE,
        adr="ADR-045",
        caveat="A flag is a prompt to look, not a sell call.",
    ),
    "vs_market_1y": EvidenceEntry(
        key="vs_market_1y",
        label="vs Market (1y)",
        meaning="Realized 1-year return of the book minus SPY.",
        healthy_band="A passive outcome, not a skill measure — compare risk-adjusted, not raw.",
        verdict=Verdict.DESCRIPTIVE,
        adr="ADR-046",
        caveat="Not evidence of edge: momentum exits failed the Sharpe test (ADR-046).",
    ),
    "net_beta": EvidenceEntry(
        key="net_beta",
        label="Net beta (SPY)",
        meaning="How much the whole book moves when the market moves (+1.00 = with the market).",
        healthy_band="An all-stock book sits near 1.0; <1 is defensive, >1 is amplified.",
        verdict=Verdict.DESCRIPTIVE,
        adr="ADR-052",
        caveat="Inherited exposure, not a strategic lever — momentum as active edge was killed (ADR-046).",
    ),
    "systematic_share": EvidenceEntry(
        key="systematic_share",
        label="Systematic share",
        meaning="Share of the book's variance explained by macro factors (market/rates/USD).",
        healthy_band="The 60% line is a heuristic surfacing dial, not a validated edge (ADR-052).",
        verdict=Verdict.RESEARCH_ONLY,
        adr="ADR-052",
        caveat="High share isn't good or bad — it's your choice; the dial just makes it visible.",
    ),
    # --- Screener / evidence-screen factors --------------------------------------
    "screen_cleared": EvidenceEntry(
        key="screen_cleared",
        label="Screen",
        meaning="How many names cleared every pre-registered gate this week, out of the universe.",
        healthy_band="Large-cap US universe only (survivor-biased) — not the whole market.",
        verdict=Verdict.RESEARCH_ONLY,
        adr="ADR-049",
        caveat="The ranking signal is unproven: forward-IC=0.0107, CI spans 0 (ADR-049). Description, not a forecast.",
    ),
    "factor_momentum": EvidenceEntry(
        key="factor_momentum",
        label="Momentum (12-1)",
        meaning="12-month return excluding the most recent month; the one point-in-time-safe factor.",
        healthy_band="Cross-sectional rank within the universe.",
        verdict=Verdict.INCONCLUSIVE,
        adr="ADR-049",
        caveat="Tested OOS: IC=0.0107, CI spans 0 — no proven edge. Jegadeesh-Titman factor, post-publication decayed.",
    ),
    "factor_value": EvidenceEntry(
        key="factor_value",
        label="Value (1/PE)",
        meaning="Inverse trailing P/E from the current snapshot.",
        healthy_band="Cross-sectional rank within the universe.",
        verdict=Verdict.RESEARCH_ONLY,
        adr="ADR-049",
        caveat="Current snapshot, NOT point-in-time — never validated in backtest. Descriptive of today only.",
    ),
    "factor_quality": EvidenceEntry(
        key="factor_quality",
        label="Quality (ROE/margin)",
        meaning="Return-on-equity or profit margin from the current snapshot.",
        healthy_band="Cross-sectional rank within the universe.",
        verdict=Verdict.RESEARCH_ONLY,
        adr="ADR-049",
        caveat="Current snapshot, NOT point-in-time — never validated. Descriptive of today only.",
    ),
    "factor_analyst_dispersion": EvidenceEntry(
        key="factor_analyst_dispersion",
        label="Analyst dispersion",
        meaning="Spread of analyst price targets (high-low) — how much analysts DISAGREE.",
        healthy_band="Wide spread = high uncertainty about the name.",
        verdict=Verdict.RESEARCH_ONLY,
        adr="ADR-049",
        caveat="This is target DISPERSION, not revision drift — no published evidence it predicts returns. Do not read as a revision signal.",
    ),
    # --- Risk tab ----------------------------------------------------------------
    "enb": EvidenceEntry(
        key="enb",
        label="Effective number of bets",
        meaning="How many truly independent bets the book holds (Meucci ENB on the covariance).",
        healthy_band="5-8 is normal for a concentrated thesis; a broadly diversified book is 40+.",
        verdict=Verdict.DESCRIPTIVE,
        adr="ADR-052",
        caveat="Low ENB isn't wrong if concentration is intentional — it just quantifies it.",
    ),
    "downside_beta": EvidenceEntry(
        key="downside_beta",
        label="Downside beta",
        meaning="How hard the book falls on down-market days (beta fit on SPY<0 days only).",
        healthy_band="1.0 = falls with the market; >1 = falls harder than it rises.",
        verdict=Verdict.DESCRIPTIVE,
        adr="ADR-052",
        caveat="Describes asymmetry, not a prediction of the next drawdown.",
    ),
    "diversification_ratio": EvidenceEntry(
        key="diversification_ratio",
        label="Diversification ratio",
        meaning="Weighted-average single-name volatility divided by portfolio volatility.",
        healthy_band="~1.2-1.8 typical for US equities; near 1.0 means names move together.",
        verdict=Verdict.DESCRIPTIVE,
        adr="ADR-052",
        caveat="A structural fact about co-movement, not a risk forecast.",
    ),
    "sector_hhi": EvidenceEntry(
        key="sector_hhi",
        label="Sector concentration (HHI)",
        meaning="Herfindahl index of sector weights — how concentrated the book is by sector.",
        healthy_band="SPY ~0.10; active managers 0.10-0.25; higher = more concentrated.",
        verdict=Verdict.DESCRIPTIVE,
        adr="ADR-052",
        caveat="Concentration is a choice; the number makes the tilt visible, not a call to diversify.",
    ),
    # --- Cross-cutting: signals the project tested and KILLED (so tabs can cite honestly) ---
    "sentiment_signal": EvidenceEntry(
        key="sentiment_signal",
        label="Sentiment",
        meaning="Aggregated news/social sentiment for the name.",
        healthy_band=None,
        verdict=Verdict.FALSIFIED,
        adr="ADR-044",
        caveat="Predictive value was tested and falsified (ADR-044: cross-sectional IC ~0 on a clean 430-ticker universe). Descriptive buzz only.",
    ),
    "evidence_grade": EvidenceEntry(
        key="evidence_grade",
        label="Evidence grade",
        meaning="Where a name ranks on present-day facts (valuation/quality/health) vs the universe.",
        healthy_band="A description of today's standing, not a ranking with proven forward edge.",
        verdict=Verdict.RESEARCH_ONLY,
        adr="ADR-049",
        caveat="Relies on factual metrics only; conviction had no OOS edge (ADR-039). Not a forecast.",
    ),
    "discipline_gate": EvidenceEntry(
        key="discipline_gate",
        label="Discipline gate",
        meaning="The live, pre-registered test of whether the discipline tool improves adherence.",
        healthy_band="Thresholds locked before any live data; resolves ~mid-July 2026.",
        verdict=Verdict.FORWARD_PENDING,
        adr="ADR-048",
        caveat="No verdict yet — the result will be reported honestly whatever it is (ADR-048/051).",
    ),
}


def get_evidence(key: str) -> EvidenceEntry | None:
    """Return the EvidenceEntry for a metric key, or None if unregistered."""
    return _REGISTRY.get(key)


def all_keys() -> tuple[str, ...]:
    """All registered metric keys (stable order for tests/iteration)."""
    return tuple(_REGISTRY.keys())


def entries_by_verdict(verdict: Verdict) -> tuple[EvidenceEntry, ...]:
    """All entries with a given verdict — powers the Home 'what we know/don't know' card."""
    return tuple(e for e in _REGISTRY.values() if e.verdict is verdict)
