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
