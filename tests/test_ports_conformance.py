"""Runtime-checkable Protocol conformance tests for domain ports."""


def test_attention_series_port_is_runtime_checkable():
    from datetime import datetime

    from domain.models import AttentionPoint
    from domain.ports import AttentionSeriesPort

    class Dummy:
        def get_attention_series(
            self, ticker: str, start: datetime, end: datetime
        ) -> list[AttentionPoint]:
            return [AttentionPoint(ticker, start, 1.0, "x")]

    assert isinstance(Dummy(), AttentionSeriesPort)
