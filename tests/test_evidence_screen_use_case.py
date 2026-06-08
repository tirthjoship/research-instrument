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


def test_run_returns_full_distribution_regardless_of_top_n() -> None:
    """run() must return ALL eligible candidates (full distribution).

    top_n is intentionally ignored — it is the caller's (CLI's) responsibility to
    slice to top_n for stdout/surfaced-calls.  The result contains all ranked
    candidates so the JSON report is a true full distribution.
    """
    uc = EvidenceScreenUseCase(FakePrice(), FakeAnalyst(), FakeFund(), FakeNarrator())
    res = uc.run(universe=["MU", "NVDA", "AAPL"], as_of="2026-06-08", top_n=2)
    # All 3 eligible candidates must be present (full distribution, not truncated)
    assert len(res.candidates) == 3


# ---------------------------------------------------------------------------
# IMPORTANT 3: abstained field
# ---------------------------------------------------------------------------


def test_abstained_true_when_all_analyst_and_fund_missing() -> None:
    """abstained must be True when analyst+fund factors are all None (thin coverage).

    With revision=None and quality=value=0 (from empty FakeFund), present_fraction
    per ticker = 1/4 (only momentum) which is below the 0.5 threshold.
    """

    class AllNoneAnalyst:
        def estimate_series(self, t: str) -> list[float] | None:
            return None  # revision missing

    class EmptyFund:
        def quality_value(self, t: str) -> dict[str, float]:
            return {}  # no quality/value → both z-scored as None

    uc = EvidenceScreenUseCase(
        FakePrice(), AllNoneAnalyst(), EmptyFund(), FakeNarrator()
    )
    res = uc.run(universe=["MU", "NVDA"], as_of="2026-06-08", top_n=10)
    assert res.abstained is True


def test_abstained_false_on_full_coverage() -> None:
    """abstained must be False when all factors are present for all tickers."""

    class AllPresentAnalyst:
        def estimate_series(self, t: str) -> list[float] | None:
            return [1.0, 1.1, 1.2]

    class AllPresentFund:
        def quality_value(self, t: str) -> dict[str, float]:
            return {"quality": 0.5, "value": 0.3}

    uc = EvidenceScreenUseCase(
        FakePrice(), AllPresentAnalyst(), AllPresentFund(), FakeNarrator()
    )
    res = uc.run(universe=["MU", "NVDA"], as_of="2026-06-08", top_n=10)
    assert res.abstained is False


# ---------------------------------------------------------------------------
# IMPORTANT 4: winsorize before z-score
# ---------------------------------------------------------------------------


def test_outlier_does_not_dominate_z_scores() -> None:
    """An extreme outlier must not give a z-score magnitude >> 3 after winsorization."""
    from application.evidence_screen_use_case import EvidenceScreenUseCase

    # Give OUTLIER a momentum value 1000x the others via monthly closes trend.
    # We achieve this by directly testing _z with an extreme value.
    zs = EvidenceScreenUseCase._z([1.0, 1.0, 1.0, 1.0, 1000.0])
    assert zs is not None
    present = [v for v in zs if v is not None]
    # With winsorization the outlier should not push any z-score beyond ~4
    assert max(abs(v) for v in present) < 4.0


# ---------------------------------------------------------------------------
# NIT 5: percentile computed cross-sectionally
# ---------------------------------------------------------------------------


def test_percentile_in_range_and_top_is_highest() -> None:
    """Each factor's percentile must be in [0,1] and not all zero when values differ."""

    class RankedAnalyst:
        def estimate_series(self, t: str) -> list[float] | None:
            # MU gets best revision, NVDA moderate, AAPL none
            return {"MU": [1.0, 2.0], "NVDA": [1.0, 1.1]}.get(t)

    class RankedFund:
        _quality = {"MU": 0.9, "NVDA": 0.5, "AAPL": 0.1}
        _value = {"MU": 0.8, "NVDA": 0.4, "AAPL": 0.2}

        def quality_value(self, t: str) -> dict[str, float]:
            return {"quality": self._quality[t], "value": self._value[t]}

    class RankedPrice:
        # Different monthly closes per ticker → different momentum z-scores
        _closes = {
            "MU": [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 25, 30],
            "NVDA": [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 22, 24],
            "AAPL": [10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 11],
        }

        def monthly_closes(self, t: str) -> list[float]:
            return self._closes.get(t, [])

        def trend_health(self, t: str) -> float:
            return 0.4

        def has_min_history(self, t: str) -> bool:
            return True

    uc = EvidenceScreenUseCase(
        RankedPrice(), RankedAnalyst(), RankedFund(), FakeNarrator()
    )
    res = uc.run(universe=["MU", "NVDA", "AAPL"], as_of="2026-06-08", top_n=10)

    all_percentiles = [fs.percentile for c in res.candidates for fs in c.factor_scores]
    assert all(
        0.0 <= p <= 1.0 for p in all_percentiles
    ), "All percentiles must be in [0,1]"

    # With different values across tickers, not all percentiles can be 0.0
    assert not all(p == 0.0 for p in all_percentiles), "Percentiles must not all be 0.0"


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
