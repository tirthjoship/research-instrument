"""Application-layer use case: evidence-based screening of a stock universe.

Partial analyst coverage is flagged-neutral (ticker stays), not dropped.
"""

from __future__ import annotations

from typing import Protocol

from domain import trend_rules
from domain.factor_scores import FACTOR_KEYS, composite_score, revision_momentum, zscore
from domain.screen import abstain_if_thin, eligible, rank_universe
from domain.screen_models import FactorScore, ScreenCandidate, ScreenLabel, ScreenResult


class PricePort(Protocol):
    def monthly_closes(self, ticker: str) -> list[float]: ...
    def trend_health(self, ticker: str) -> float: ...
    def has_min_history(self, ticker: str) -> bool: ...


class AnalystPort(Protocol):
    def estimate_series(self, ticker: str) -> list[float] | None: ...


class FundamentalsPort(Protocol):
    def quality_value(self, ticker: str) -> dict[str, float]: ...


class NarratorPort(Protocol):
    def narrate(self, candidate: ScreenCandidate) -> str: ...


class EvidenceScreenUseCase:
    def __init__(
        self,
        price: PricePort,
        analyst: AnalystPort,
        fundamentals: FundamentalsPort,
        narrator: NarratorPort,
    ) -> None:
        self._price = price
        self._analyst = analyst
        self._fund = fundamentals
        self._narrator = narrator

    def run(
        self,
        universe: list[str],
        as_of: str,
        top_n: int = 10,
    ) -> ScreenResult:
        # --- gather raw signals (ineligible tickers are filtered) ---
        raw: list[tuple[str, float | None, float | None, dict[str, float], float]] = []
        for t in universe:
            th = self._price.trend_health(t)
            hist_ok = self._price.has_min_history(t)
            if not eligible(th, hist_ok):
                continue
            mom = trend_rules.momentum_12_1(self._price.monthly_closes(t))
            rev = revision_momentum(self._analyst.estimate_series(t))
            qv = self._fund.quality_value(t)
            raw.append((t, mom, rev, qv, th))

        if not raw:
            return ScreenResult(
                as_of=as_of,
                candidates=(),
                universe_size=len(universe),
                regime="NEUTRAL",
                scorecard_ref=None,
            )

        # --- cross-sectional z-scores (None-safe) ---
        zmom = self._z([r[1] for r in raw])
        zrev = self._z([r[2] for r in raw])
        zqual = self._z([r[3].get("quality") for r in raw])
        zval = self._z([r[3].get("value") for r in raw])

        cands: list[ScreenCandidate] = []
        present_fractions: list[float] = []

        for i, (t, _mom, _rev, _qv, th) in enumerate(raw):
            subs: dict[str, float | None] = {
                "momentum": zmom[i],
                "revision": zrev[i],
                "quality": zqual[i],
                "value": zval[i],
            }
            present = sum(1 for k in FACTOR_KEYS if subs[k] is not None)
            present_fractions.append(present / len(FACTOR_KEYS))

            comp = composite_score(subs)
            factor_scores = tuple(
                FactorScore(
                    name=k,
                    value=v if (v := subs[k]) is not None else 0.0,
                    percentile=0.0,
                    contribution=(v if (v := subs[k]) is not None else 0.0)
                    / len(FACTOR_KEYS),
                )
                for k in FACTOR_KEYS
            )

            # build a stub candidate so narrator can access ticker/composite
            stub = ScreenCandidate(
                t, comp, factor_scores, th, "", ScreenLabel.RESEARCH_ONLY
            )
            why = self._narrator.narrate(stub)
            cands.append(
                ScreenCandidate(
                    t, comp, factor_scores, th, why, ScreenLabel.RESEARCH_ONLY
                )
            )

        ranked = rank_universe(cands, top_n=top_n)

        # thin-coverage flag (informational — doesn't drop candidates)
        _thin = abstain_if_thin(min(present_fractions) if present_fractions else 0.0)

        return ScreenResult(
            as_of=as_of,
            candidates=tuple(ranked),
            universe_size=len(universe),
            regime="NEUTRAL",
            scorecard_ref=None,
        )

    @staticmethod
    def _z(vals: list[float | None]) -> list[float | None]:
        present = [v for v in vals if v is not None]
        if not present:
            return [None] * len(vals)
        zs = zscore(present)
        it = iter(zs)
        return [next(it) if v is not None else None for v in vals]
