"""Read a published screen_<date>.json snapshot instead of running a live scan.

Item 5 of the Cloud deploy scaling design: the ~512-ticker full-universe scan
moves off live per-click execution onto a scheduled GitHub Actions job.
weekly-brief reads the latest committed snapshot for its "candidates"
section instead of re-scanning the universe inline on every visitor click —
only the visitor's own holdings are still evaluated live (bounded to their
ticker count, already paced/retried elsewhere in this codebase).
"""

from __future__ import annotations

from adapters.visualization.data_loader import load_latest_screen
from domain.screen_diagnostics import ScreenDiagnostics
from domain.screen_models import FactorScore, ScreenCandidate, ScreenLabel, ScreenResult


class SnapshotScreenReader:
    """Drop-in replacement for EvidenceScreenUseCase — same .run() interface
    (WeeklyBriefUseCase calls screen.run(universe, as_of, top_n)), backed by
    a committed snapshot instead of a live scan."""

    def __init__(self, reports_dir: str) -> None:
        self._reports_dir = reports_dir

    def run(
        self,
        universe: list[str],
        as_of: str,
        top_n: int = 10,
    ) -> ScreenResult:
        screen = load_latest_screen(self._reports_dir)
        if screen is None:
            return ScreenResult(
                as_of=as_of,
                candidates=(),
                universe_size=0,
                regime="NEUTRAL",
                scorecard_ref=None,
                abstained=True,
            )

        candidates = tuple(
            ScreenCandidate(
                ticker=c["ticker"],
                composite=c["composite"],
                factor_scores=tuple(
                    FactorScore(
                        name=f["name"],
                        value=f["value"],
                        percentile=f["percentile"],
                        contribution=f["contribution"],
                    )
                    for f in c.get("factor_scores", [])
                ),
                trend_health=c["trend_health"],
                why=c["why"],
                label=ScreenLabel(c["label"]),
            )
            for c in screen.get("candidates", [])
        )

        diagnostics_dict = screen.get("diagnostics")
        diagnostics = (
            ScreenDiagnostics(**diagnostics_dict) if diagnostics_dict else None
        )

        return ScreenResult(
            as_of=screen.get("as_of", as_of),
            candidates=candidates,
            universe_size=screen.get("universe_size", 0),
            regime=screen.get("regime", "NEUTRAL"),
            scorecard_ref=None,
            abstained=bool(screen.get("abstained", False)),
            diagnostics=diagnostics,
        )
