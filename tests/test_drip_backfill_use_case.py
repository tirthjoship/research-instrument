from datetime import datetime

from domain.exceptions import SourceThrottledError
from domain.models import AttentionPoint, SourceHealth


class _Trends:
    def __init__(self, throttle_for=None):
        self.throttle_for = throttle_for or set()
        self.calls = []

    def get_attention_series(self, ticker, start, end):
        self.calls.append(ticker)
        if ticker in self.throttle_for:
            raise SourceThrottledError("429")
        return [AttentionPoint(ticker, start, 5.0, "google_trends")]


class _Store:
    def __init__(self, already_fresh=None):
        self.points = []
        self._fresh = already_fresh or set()

    def save_attention_points(self, pts):
        self.points.extend(pts)

    def get_attention_series(self, ticker, start, end):
        # used by resumability check: return a row dated `end` if "fresh today"
        if ticker in self._fresh:
            return [AttentionPoint(ticker, end, 1.0, "google_trends")]
        return []


def test_drip_persists_and_reports_health():
    from application.drip_backfill_use_case import DripBackfillUseCase

    store = _Store()
    trends = _Trends()
    uc = DripBackfillUseCase(
        sources={"google_trends": trends}, store=store, sleep=lambda s: None
    )
    report = uc.execute(["ASTS", "RKLB"], now=datetime(2026, 6, 5), days=90)
    assert len(store.points) == 2
    h = report["google_trends"]
    assert isinstance(h, SourceHealth)
    assert h.ok == 2 and h.throttled == 0


def test_drip_throttle_writes_nothing_and_is_counted():
    from application.drip_backfill_use_case import DripBackfillUseCase

    store = _Store()
    trends = _Trends(throttle_for={"ASTS"})
    uc = DripBackfillUseCase(
        sources={"google_trends": trends}, store=store, sleep=lambda s: None
    )
    report = uc.execute(["ASTS", "RKLB"], now=datetime(2026, 6, 5), days=90)
    assert [p.ticker for p in store.points] == ["RKLB"]  # ASTS throttle wrote nothing
    assert report["google_trends"].throttled == 1
    assert report["google_trends"].ok == 1


def test_drip_resumable_skips_fresh_tickers():
    from application.drip_backfill_use_case import DripBackfillUseCase

    store = _Store(already_fresh={"ASTS"})
    trends = _Trends()
    uc = DripBackfillUseCase(
        sources={"google_trends": trends}, store=store, sleep=lambda s: None
    )
    uc.execute(["ASTS", "RKLB"], now=datetime(2026, 6, 5), days=90)
    assert trends.calls == ["RKLB"]  # ASTS already fresh today -> skipped
