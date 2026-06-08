from application.evidence_screen_use_case import EvidenceScreenUseCase
from domain.screen_models import ScreenLabel


class FakePrice:
    def monthly_closes(self, t: str) -> list[float]:
        return [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 22, 24]

    def trend_health(self, t: str) -> float:
        return 0.4

    def has_min_history(self, t: str) -> bool:
        return True


class FakeAnalyst:
    def estimate_series(self, t: str) -> list[float] | None:
        return [1.0, 1.1, 1.2] if t == "MU" else None  # NVDA missing -> flagged-neutral


class FakeFund:
    def quality_value(self, t: str) -> dict[str, float]:
        return {"quality": 0.5, "value": 0.2}


class FakeNarrator:
    def narrate(self, cand: object) -> str:
        from domain.screen_models import ScreenCandidate

        assert isinstance(cand, ScreenCandidate)
        return f"why-{cand.ticker}"


def test_screen_ranks_and_flags_neutral_coverage() -> None:
    uc = EvidenceScreenUseCase(FakePrice(), FakeAnalyst(), FakeFund(), FakeNarrator())
    res = uc.run(universe=["MU", "NVDA"], as_of="2026-06-08", top_n=10)
    tickers = [c.ticker for c in res.candidates]
    assert set(tickers) == {"MU", "NVDA"}
    assert all(c.why.startswith("why-") for c in res.candidates)
    assert res.candidates[0].label in (ScreenLabel.VALIDATED, ScreenLabel.RESEARCH_ONLY)


def test_partial_analyst_coverage_both_tickers_returned() -> None:
    """Partial analyst coverage (NVDA=None) must NOT drop NVDA — it stays, flagged-neutral."""
    uc = EvidenceScreenUseCase(FakePrice(), FakeAnalyst(), FakeFund(), FakeNarrator())
    res = uc.run(universe=["MU", "NVDA"], as_of="2026-06-08", top_n=10)
    assert (
        len(res.candidates) == 2
    ), "NVDA must not be dropped despite missing analyst data"


def test_empty_universe() -> None:
    uc = EvidenceScreenUseCase(FakePrice(), FakeAnalyst(), FakeFund(), FakeNarrator())
    res = uc.run(universe=[], as_of="2026-06-08", top_n=10)
    assert res.candidates == ()
    assert res.universe_size == 0


def test_top_n_limits_results() -> None:
    uc = EvidenceScreenUseCase(FakePrice(), FakeAnalyst(), FakeFund(), FakeNarrator())
    res = uc.run(universe=["MU", "NVDA", "AAPL"], as_of="2026-06-08", top_n=2)
    assert len(res.candidates) <= 2


# ---------------------------------------------------------------------------
# Task 8a: surface_calls — persists SurfacedCall per ranked candidate
# ---------------------------------------------------------------------------


class FakeCallStore:
    def __init__(self) -> None:
        self.saved: list[object] = []

    def save_call(self, call: object) -> None:
        self.saved.append(call)

    def get_call(self, call_id: str) -> None:
        return None

    def get_all_calls(self) -> list[object]:
        return list(self.saved)

    def get_due_calls(self, now: object) -> list[object]:
        return []

    def save_outcome(self, outcome: object) -> None:
        pass

    def get_outcomes(self) -> list[object]:
        return []


def test_surface_calls_emits_one_per_candidate() -> None:
    """surface_calls() must persist exactly one SurfacedCall per ranked candidate."""
    from datetime import timezone

    from application.evidence_screen_use_case import EvidenceScreenUseCase
    from domain.surfaced_call import OpportunityDirection, SurfacedCall

    uc = EvidenceScreenUseCase(FakePrice(), FakeAnalyst(), FakeFund(), FakeNarrator())
    result = uc.run(universe=["MU", "NVDA"], as_of="2026-06-08", top_n=10)
    store = FakeCallStore()
    as_of_dt = __import__("datetime").datetime(2026, 6, 8, tzinfo=timezone.utc)
    uc.surface_calls(result, as_of_dt=as_of_dt, store=store)

    assert len(store.saved) == len(result.candidates)
    for call in store.saved:
        assert isinstance(call, SurfacedCall)
        assert call.direction == OpportunityDirection.BUY
        assert len(call.evidence) > 0
        assert call.ticker in ("MU", "NVDA")


def test_surface_calls_evidence_maps_factors() -> None:
    """Each SurfacedCall evidence tuple must include one EvidenceItem per factor."""
    from datetime import timezone

    from application.evidence_screen_use_case import EvidenceScreenUseCase
    from domain.surfaced_call import EvidenceItem

    uc = EvidenceScreenUseCase(FakePrice(), FakeAnalyst(), FakeFund(), FakeNarrator())
    result = uc.run(universe=["MU"], as_of="2026-06-08", top_n=10)
    store = FakeCallStore()
    as_of_dt = __import__("datetime").datetime(2026, 6, 8, tzinfo=timezone.utc)
    uc.surface_calls(result, as_of_dt=as_of_dt, store=store)

    assert store.saved
    call = store.saved[0]
    assert all(isinstance(e, EvidenceItem) for e in call.evidence)
    dimension_names = {e.dimension for e in call.evidence}
    # Must include the four factor dimensions
    for dim in ("momentum", "revision", "quality", "value"):
        assert dim in dimension_names, f"Missing evidence dimension: {dim}"


def test_surface_calls_skipped_when_store_is_none() -> None:
    """surface_calls(store=None) must not raise — existing run() tests stay green."""
    from datetime import timezone

    from application.evidence_screen_use_case import EvidenceScreenUseCase

    uc = EvidenceScreenUseCase(FakePrice(), FakeAnalyst(), FakeFund(), FakeNarrator())
    result = uc.run(universe=["MU", "NVDA"], as_of="2026-06-08", top_n=10)
    as_of_dt = __import__("datetime").datetime(2026, 6, 8, tzinfo=timezone.utc)
    # Must not raise
    uc.surface_calls(result, as_of_dt=as_of_dt, store=None)


# ---------------------------------------------------------------------------
# Task 8b: verdict-driven label — read screen_ic_*.json → ScreenLabel
# ---------------------------------------------------------------------------


def test_verdict_pass_yields_validated_label(tmp_path: object) -> None:
    """A PASS verdict file must produce VALIDATED label."""
    import json

    from application.evidence_screen_use_case import label_from_verdict_file

    verdict_file = tmp_path / "screen_ic_2026-06-08.json"  # type: ignore[operator]
    verdict_file.write_text(
        json.dumps({"decision": "PASS", "mean_ic": 0.035, "n_dates": 60})
    )

    label = label_from_verdict_file(str(tmp_path))
    assert label == ScreenLabel.VALIDATED


def test_verdict_inconclusive_yields_research_only(tmp_path: object) -> None:
    import json

    from application.evidence_screen_use_case import label_from_verdict_file

    verdict_file = tmp_path / "screen_ic_2026-06-08.json"  # type: ignore[operator]
    verdict_file.write_text(
        json.dumps({"decision": "INCONCLUSIVE", "mean_ic": 0.005, "n_dates": 30})
    )

    label = label_from_verdict_file(str(tmp_path))
    assert label == ScreenLabel.RESEARCH_ONLY


def test_verdict_missing_yields_research_only(tmp_path: object) -> None:
    """When no verdict file exists, default to RESEARCH_ONLY."""
    from application.evidence_screen_use_case import label_from_verdict_file

    label = label_from_verdict_file(str(tmp_path))
    assert label == ScreenLabel.RESEARCH_ONLY


def test_verdict_halt_yields_research_only(tmp_path: object) -> None:
    import json

    from application.evidence_screen_use_case import label_from_verdict_file

    verdict_file = tmp_path / "screen_ic_2026-06-08.json"  # type: ignore[operator]
    verdict_file.write_text(
        json.dumps({"decision": "HALT", "mean_ic": -0.01, "n_dates": 40})
    )

    label = label_from_verdict_file(str(tmp_path))
    assert label == ScreenLabel.RESEARCH_ONLY
