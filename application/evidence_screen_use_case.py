"""Application-layer use case: evidence-based screening of a stock universe.

Partial analyst coverage is flagged-neutral (ticker stays), not dropped.
"""

from __future__ import annotations

import glob
import json
import os
from datetime import datetime
from typing import Protocol

from domain import trend_rules
from domain.factor_scores import FACTOR_KEYS, composite_score, revision_momentum, zscore
from domain.screen import abstain_if_thin, eligible, rank_universe
from domain.screen_models import FactorScore, ScreenCandidate, ScreenLabel, ScreenResult
from domain.surfaced_call import (
    EvidenceItem,
    OpportunityDirection,
    SurfacedCall,
    make_call_id,
)


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


class CallStorePort(Protocol):
    """Minimal protocol for persisting SurfacedCalls from the screen."""

    def save_call(self, call: SurfacedCall) -> None: ...


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

    def surface_calls(
        self,
        result: ScreenResult,
        as_of_dt: datetime,
        store: CallStorePort | None,
        spy_at_surface: float = 5.0,
        ndx_at_surface: float = 5.0,
    ) -> list[SurfacedCall]:
        """Persist each ranked ScreenCandidate as a SurfacedCall via *store*.

        Maps factor scores → EvidenceItem(dimension, score, note) and sets
        direction=BUY for all candidates (evidence-bounded screen, not a sell signal).

        Args:
            result:          The ScreenResult returned by run().
            as_of_dt:        Timezone-aware datetime anchor (POINT-IN-TIME).
            store:           SurfacedCallStorePort implementation, or None to skip.
            spy_at_surface:  SPY price at surface time (placeholder 5.0 when unknown).
            ndx_at_surface:  NDX price at surface time (placeholder 5.0 when unknown).

        Returns:
            List of SurfacedCall objects that were (attempted to be) persisted.
        """
        if store is None:
            return []

        calls: list[SurfacedCall] = []
        for cand in result.candidates:
            evidence: tuple[EvidenceItem, ...] = tuple(
                EvidenceItem(
                    dimension=fs.name,
                    score=max(0.0, min(10.0, (fs.value + 3.0) * (10.0 / 6.0))),
                    note=f"{fs.name} z-score {fs.value:+.2f}",
                )
                for fs in cand.factor_scores
            )
            call = SurfacedCall(
                call_id=make_call_id(cand.ticker, as_of_dt),
                ticker=cand.ticker,
                surfaced_at=as_of_dt,
                conviction=max(0.0, min(10.0, (cand.composite + 3.0) * (10.0 / 6.0))),
                divergence_score=5.0,  # screen has no divergence signal; use neutral
                direction=OpportunityDirection.BUY,
                evidence=evidence,
                theme=None,
                cap_tier="unknown",
                spy_at_surface=spy_at_surface,
                ndx_at_surface=ndx_at_surface,
            )
            store.save_call(call)
            calls.append(call)
        return calls

    @staticmethod
    def _z(vals: list[float | None]) -> list[float | None]:
        present = [v for v in vals if v is not None]
        if not present:
            return [None] * len(vals)
        zs = zscore(present)
        it = iter(zs)
        return [next(it) if v is not None else None for v in vals]


def label_from_verdict_file(report_dir: str) -> ScreenLabel:
    """Read the latest screen_ic_*.json in *report_dir* and return a ScreenLabel.

    Returns:
        VALIDATED  iff the latest verdict file has ``decision == "PASS"``.
        RESEARCH_ONLY  otherwise (INCONCLUSIVE, HALT, or no file found).
    """
    pattern = os.path.join(report_dir, "screen_ic_*.json")
    files = sorted(glob.glob(pattern))
    if not files:
        return ScreenLabel.RESEARCH_ONLY
    latest = files[-1]
    try:
        with open(latest) as fh:
            data = json.load(fh)
        return (
            ScreenLabel.VALIDATED
            if data.get("decision") == "PASS"
            else ScreenLabel.RESEARCH_ONLY
        )
    except Exception:
        return ScreenLabel.RESEARCH_ONLY
