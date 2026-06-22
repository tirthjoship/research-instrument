# domain/corroboration_service.py
"""Pure corroboration tier math. Stdlib-only. See spec §6/§7."""
from __future__ import annotations

from datetime import date

from domain.corroboration_models import (
    Agreement,
    ConvergenceTier,
    CorroboratedCandidate,
    DirectionalView,
    HarvestedClaim,
    OurReadout,
    Stance,
    TrendHealth,
    Uncertainty,
)

_SIGN = {Stance.BULLISH: 1, Stance.BEARISH: -1, Stance.NEUTRAL: 0}
_TIER_NUM = {
    ConvergenceTier.STRONG: 1.0,
    ConvergenceTier.MODERATE: 0.6,
    ConvergenceTier.WEAK: 0.3,
    ConvergenceTier.CONFLICTED: 0.1,
    ConvergenceTier.NONE: 0.0,
}


class CorroborationService:
    """Combine verified attributed claims + our own signals into a tier."""

    def corroborate(
        self,
        ticker: str,
        as_of: date,
        claims: list[HarvestedClaim],
        readout: OurReadout,
        held: bool,
    ) -> CorroboratedCandidate:
        verified = [c for c in claims if c.verified]
        agreement = self._agreement(verified, readout)
        uncertainty = self._uncertainty(verified, as_of)
        tier = self._tier(agreement, uncertainty)
        verification = (
            "NONE_DROPPED"
            if not verified
            else "ALL_VERIFIED" if len(verified) == len(claims) else "PARTIAL"
        )
        return CorroboratedCandidate(
            ticker=ticker,
            as_of=as_of,
            sources=tuple(verified),
            our_readout=readout,
            convergence=tier,
            agreement=agreement,
            uncertainty=uncertainty,
            held=held,
            verification=verification,
        )

    def _agreement(self, verified: list[HarvestedClaim], r: OurReadout) -> Agreement:
        wsum = sum(c.reliability_weight for c in verified)
        score = (
            sum(_SIGN[c.stance] * c.reliability_weight for c in verified) / wsum
            if wsum > 0
            else 0.0
        )
        n_bull = sum(1 for c in verified if c.stance is Stance.BULLISH)
        n_bear = sum(1 for c in verified if c.stance is Stance.BEARISH)
        align = self._alignment(score, r)
        return Agreement(n_bull, n_bear, score, align)

    def _alignment(self, score: float, r: OurReadout) -> str:
        # Our directional read: healthy+top-quartile = bullish lean; broken = bearish.
        our_sign = 0
        if r.trend_health is TrendHealth.HEALTHY and (r.factor_percentile or 100) <= 25:
            our_sign = 1
        elif r.trend_health is TrendHealth.BROKEN:
            our_sign = -1
        if our_sign == 0:
            return "NEUTRAL"
        if (score > 0 and our_sign > 0) or (score < 0 and our_sign < 0):
            return "AGREES"
        return "DIVERGES"

    def _uncertainty(self, verified: list[HarvestedClaim], as_of: date) -> Uncertainty:
        n = len(verified)
        has_bull = any(c.stance is Stance.BULLISH for c in verified)
        has_bear = any(c.stance is Stance.BEARISH for c in verified)
        freshness = (
            min((as_of - c.published_at).days for c in verified) if verified else 9999
        )
        return Uncertainty(
            coverage_n=n, conflict=(has_bull and has_bear), freshness_days=freshness
        )

    def _tier(self, a: Agreement, u: Uncertainty) -> ConvergenceTier:
        s = a.weighted_score
        if u.coverage_n == 0:
            return ConvergenceTier.NONE
        if u.conflict and abs(s) < 0.2:
            return ConvergenceTier.CONFLICTED
        if abs(s) >= 0.5 and u.coverage_n >= 3:
            if a.our_alignment == "DIVERGES":
                return ConvergenceTier.CONFLICTED
            if a.our_alignment == "AGREES":
                return ConvergenceTier.STRONG
            return ConvergenceTier.MODERATE
        if 0.2 <= abs(s) < 0.5 and u.coverage_n >= 2 and a.our_alignment != "DIVERGES":
            return ConvergenceTier.MODERATE
        return ConvergenceTier.WEAK

    def roll_up(
        self,
        candidates: list[CorroboratedCandidate],
        groups: dict[str, list[str]],
        exposure_pct: dict[str, float],
        group_kind: str = "theme",
    ) -> list[DirectionalView]:
        views: list[DirectionalView] = []
        by_ticker = {c.ticker: c for c in candidates}
        for name, tickers in groups.items():
            members = [by_ticker[t] for t in tickers if t in by_ticker]
            if not members:
                continue
            mean_conv = sum(_TIER_NUM[m.convergence] for m in members) / len(members)
            net = sum(m.agreement.weighted_score for m in members) / len(members)
            net_stance = (
                Stance.BULLISH
                if net > 0.1
                else Stance.BEARISH if net < -0.1 else Stance.NEUTRAL
            )
            yours = exposure_pct.get(name, 0.0)
            ev_weight = mean_conv * 100.0
            tilt = self._tilt(net_stance, mean_conv, yours, ev_weight)
            views.append(
                DirectionalView(
                    group_kind=group_kind,
                    group_name=name,
                    net_stance=net_stance,
                    mean_convergence=mean_conv,
                    your_exposure_pct=yours,
                    evidence_weight_pct=ev_weight,
                    tilt=tilt,
                )
            )
        return views

    def _tilt(
        self, net_stance: Stance, mean_conv: float, yours: float, ev_weight: float
    ) -> str:
        if net_stance is Stance.BEARISH and mean_conv >= 0.6:
            return "LEAN_OUT" if yours > 0 else "AVOID"
        if (
            net_stance is Stance.BULLISH
            and mean_conv >= 0.6
            and yours < ev_weight * 0.5
        ):
            return "LEAN_IN"
        return "HOLD"
