from datetime import datetime

from domain.models import AttentionPoint, BuzzSignal


class _FakeGdelt:
    def __init__(self, fail_for=None):
        self.fail_for = fail_for or set()

    def get_historical_buzz(self, ticker, start, end):
        if ticker in self.fail_for:
            raise RuntimeError("boom")
        return [BuzzSignal(ticker, "gdelt", 1, 0.0, "gdelt", start, f"h-{ticker}")]


class _FakeAttn:
    def __init__(self, source):
        self.source = source

    def get_attention_series(self, ticker, start, end):
        return [AttentionPoint(ticker, start, 5.0, self.source)]


class _RecordingStore:
    def __init__(self):
        self.buzz = []
        self.points = []

    def save_buzz_signal(self, s):
        self.buzz.append(s)

    def save_attention_points(self, pts):
        self.points.extend(pts)


def test_backfill_persists_all_sources():
    from application.backfill_use_case import BackfillHistoryUseCase

    store = _RecordingStore()
    uc = BackfillHistoryUseCase(
        gdelt=_FakeGdelt(),
        trends=_FakeAttn("google_trends"),
        wiki=_FakeAttn("wikipedia"),
        store=store,
    )
    stats = uc.execute(["ASTS", "RKLB"], now=datetime(2026, 6, 5), days=90)
    assert len(store.buzz) == 2  # one gdelt buzz per ticker
    assert len(store.points) == 4  # trends + wiki per ticker
    assert stats["tickers"] == 2


def test_backfill_isolates_per_ticker_failure():
    from application.backfill_use_case import BackfillHistoryUseCase

    store = _RecordingStore()
    uc = BackfillHistoryUseCase(
        gdelt=_FakeGdelt(fail_for={"ASTS"}),
        trends=_FakeAttn("google_trends"),
        wiki=_FakeAttn("wikipedia"),
        store=store,
    )
    stats = uc.execute(["ASTS", "RKLB"], now=datetime(2026, 6, 5), days=90)
    assert stats["errors"] >= 1
    assert any(s.ticker == "RKLB" for s in store.buzz)
