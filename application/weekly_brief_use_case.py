"""Compose the unified weekly brief from the four validated sub-use-cases."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Callable

from domain.brief import ScorecardSnapshot, WeeklyBrief, assemble_brief
from domain.regime import Regime, classify_regime, screen_tilt
from domain.screen_models import ScreenLabel

VixProvider = Callable[[], float]
SpyTrendProvider = Callable[[], float]

# Callables injected so tests stay network-free.
ScreenLabelFn = Callable[[str], ScreenLabel]
ClusterPeersFn = Callable[[str], list[str]]
# screen scorecard -> (top_ret, spy_ret, n, significant)
ScreenScorecardFn = Callable[[], "tuple[float | None, float | None, int, bool]"]
# discipline scorecard -> (reduce_down_rate, n, gate_status)
DisciplineScorecardFn = Callable[[], "tuple[float | None, int, str]"]

_HISTORY_DAYS = 400  # lookback for holdings-risk price windows


class RegimeReadUseCase:
    """Thin: read live VIX + SPY trend-health, classify the regime."""

    def __init__(
        self, vix_provider: VixProvider, spy_trend_provider: SpyTrendProvider
    ) -> None:
        self._vix = vix_provider
        self._spy_trend = spy_trend_provider

    def read(self) -> Regime:
        return classify_regime(self._spy_trend(), self._vix())


class WeeklyBriefUseCase:
    """Compose a WeeklyBrief from screen, discipline, regime, and scorecard collaborators.

    All collaborators are injected so tests remain network-free. The use case
    drives four sub-operations point-in-time (screen.run, holdings_risk.execute,
    regime_reader.read, cluster_peers_fn per candidate) then calls the pure
    assemble_brief domain function.
    """

    def __init__(
        self,
        screen: Any,  # EvidenceScreenUseCase
        holdings_risk: Any,  # HoldingsRiskAssessmentUseCase
        regime_reader: RegimeReadUseCase,
        screen_label_fn: ScreenLabelFn,
        cluster_peers_fn: ClusterPeersFn,
        screen_scorecard_fn: ScreenScorecardFn,
        discipline_scorecard_fn: DisciplineScorecardFn,
    ) -> None:
        self._screen = screen
        self._holdings = holdings_risk
        self._regime = regime_reader
        self._label_fn = screen_label_fn
        self._cluster = cluster_peers_fn
        self._screen_card = screen_scorecard_fn
        self._disc_card = discipline_scorecard_fn

    def execute(
        self,
        universe: list[str],
        holdings: list[Any],  # list[Holding]
        as_of: datetime,
        report_dir: str,
        top_n: int = 10,
        concentration_threshold: float = 0.20,
    ) -> WeeklyBrief:
        as_of_iso = as_of.date().isoformat()

        screen_result = self._screen.run(universe, as_of_iso, top_n)
        label = self._label_fn(report_dir)
        regime = self._regime.read()

        start = as_of - timedelta(days=_HISTORY_DAYS)
        risk = self._holdings.execute(holdings, start, as_of)
        positions = risk["positions"]
        portfolio = risk["portfolio"]

        held_tickers = {h.ticker for h in holdings}

        # Cluster overlaps: for each candidate, which held tickers share its cluster.
        cluster_overlaps: dict[str, list[str]] = {}
        for c in screen_result.candidates[:top_n]:
            peers = set(self._cluster(c.ticker))
            overlaps = sorted(peers & held_tickers)
            cluster_overlaps[c.ticker] = overlaps

        top_ret, spy_ret, n, significant = self._screen_card()
        down_rate, disc_n, gate_status = self._disc_card()
        # The screen scorecard is FORWARD-tracked (the engine is forward-accountable):
        # the record accrues from when calls are first surfaced, so n=0 early is honest.
        scorecard = ScorecardSnapshot(
            screen_window=f"forward since {as_of_iso}",
            screen_top_ret=top_ret,
            screen_spy_ret=spy_ret,
            screen_n=n,
            screen_significant=significant,
            discipline_window="21d",
            discipline_reduce_down_rate=down_rate,
            discipline_n=disc_n,
            discipline_gate_status=gate_status,
        )

        return assemble_brief(
            as_of=as_of_iso,
            regime=regime,
            tilt=screen_tilt(regime),
            screen_result=screen_result,
            screen_label=label,
            top_n=top_n,
            positions=positions,
            portfolio=portfolio,
            held_tickers=held_tickers,
            cluster_overlaps=cluster_overlaps,
            scorecard=scorecard,
            concentration_threshold=concentration_threshold,
        )
