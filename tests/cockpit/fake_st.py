"""Headless stand-in for streamlit, shared by cockpit renderer tests."""

from __future__ import annotations

from typing import Any


class FakeCol:
    def __init__(self, sink: list[str]) -> None:
        self._sink = sink

    def __enter__(self) -> "FakeCol":
        return self

    def __exit__(self, *a: object) -> None:
        pass

    def __getattr__(self, name: str) -> Any:
        return getattr(FakeSt(self._sink), name)


class FakeSt:
    """Captures markdown into `sink`; widgets return inert defaults."""

    def __init__(self, sink: list[str]) -> None:
        self.sink = sink
        self.session_state: dict[str, Any] = {}

    def markdown(self, body: object, **k: object) -> None:
        self.sink.append(str(body))

    def caption(self, body: object = "", **k: object) -> None:
        self.sink.append(str(body))

    def dataframe(self, *a: object, **k: object) -> None:
        self.sink.append("DATAFRAME")

    def plotly_chart(self, *a: object, **k: object) -> None:
        self.sink.append("PLOTLY")

    def metric(self, label: object = "", value: object = "", **k: object) -> None:
        self.sink.append(f"METRIC {label} {value}")

    def button(self, *a: object, **k: object) -> bool:
        return False

    def text_input(self, *a: object, **k: object) -> str:
        return ""

    def text_area(self, *a: object, **k: object) -> str:
        return ""

    def file_uploader(self, *a: object, **k: object) -> None:
        return None

    def columns(self, n: object, **k: object) -> list[FakeCol]:
        count = n if isinstance(n, int) else len(n)  # type: ignore[arg-type]
        return [FakeCol(self.sink) for _ in range(count)]

    def expander(self, label: object = "", **k: object) -> FakeCol:
        self.sink.append(f"EXPANDER {label}")
        return FakeCol(self.sink)

    def divider(self) -> None:
        pass

    def subheader(self, body: object = "", **k: object) -> None:
        self.sink.append(str(body))

    def info(self, body: object = "", **k: object) -> None:
        self.sink.append(str(body))

    def warning(self, body: object = "", **k: object) -> None:
        self.sink.append(str(body))

    def error(self, body: object = "", **k: object) -> None:
        self.sink.append(str(body))

    def success(self, body: object = "", **k: object) -> None:
        self.sink.append(str(body))

    def rerun(self) -> None:
        pass

    def dialog(self, title: str, **k: object):  # decorator passthrough
        def deco(fn: Any) -> Any:
            return fn

        return deco
