import json


def test_render_with_screen_fixture(tmp_path):  # type: ignore[no-untyped-def]
    (tmp_path / "screen_2026-06-13.json").write_text(
        json.dumps(
            {
                "as_of": "2026-06-13",
                "universe_size": 430,
                "abstained": False,
                "candidates": [
                    {
                        "ticker": "ABC",
                        "composite": 0.71,
                        "why": "cheap vs sector",
                        "label": "RESEARCH_ONLY",
                        "factor_scores": [{"name": "value", "percentile": 0.88}],
                    }
                ],
            }
        )
    )
    from adapters.visualization.tabs import research_candidates

    research_candidates.render(reports_dir=str(tmp_path))


def test_render_empty_dir_no_raise(tmp_path):  # type: ignore[no-untyped-def]
    from adapters.visualization.tabs import research_candidates

    research_candidates.render(reports_dir=str(tmp_path))


def test_render_abstained_false_no_candidates_no_raise(tmp_path):  # type: ignore[no-untyped-def]
    """abstained=false but candidates=[] (eligibility filtered all out) must render abstention card."""
    (tmp_path / "screen_2026-06-11.json").write_text(
        json.dumps(
            {
                "as_of": "2026-06-11",
                "universe_size": 512,
                "abstained": False,
                "candidates": [],
            }
        )
    )
    from adapters.visualization.tabs import research_candidates

    research_candidates.render(reports_dir=str(tmp_path))


def test_render_with_history_no_raise(tmp_path):  # type: ignore[no-untyped-def]
    import json

    (tmp_path / "screen_2026-06-08.json").write_text(
        json.dumps(
            {
                "as_of": "2026-06-08",
                "universe_size": 512,
                "candidates": [],
                "abstained": True,
            }
        )
    )
    from adapters.visualization.tabs import research_candidates

    research_candidates.render(reports_dir=str(tmp_path))


def test_upload_section_renders_on_abstention_week(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    """Prove that history strip + upload section render even on abstention weeks.

    Before the fix, an early `return` on the no-candidates path meant lines after
    it (the history strip and 'Check your own list' block) were never reached.
    This test would have FAILED pre-fix because 'Check your own list' would never
    appear in captured_md.
    """
    import json

    from adapters.visualization.tabs import research_candidates as rc

    # Abstention screen (0 candidates) — the current production reality.
    (tmp_path / "screen_2026-06-12.json").write_text(
        json.dumps(
            {
                "as_of": "2026-06-12",
                "universe_size": 512,
                "candidates": [],
                "abstained": True,
            }
        )
    )

    captured_md: list[str] = []

    class FakeCol:
        def __enter__(self) -> "FakeCol":
            return self

        def __exit__(self, *a: object) -> bool:
            return False

    class FakeSt:
        session_state: dict[str, object] = {}

        def markdown(self, body: object, **k: object) -> None:
            captured_md.append(str(body))

        def dataframe(self, *a: object, **k: object) -> None:
            captured_md.append("DATAFRAME")

        def divider(self) -> None:
            pass

        def caption(self, *a: object, **k: object) -> None:
            pass

        def subheader(self, *a: object, **k: object) -> None:
            pass

        def title(self, *a: object, **k: object) -> None:
            pass

        def info(self, *a: object, **k: object) -> None:
            pass

        def warning(self, *a: object, **k: object) -> None:
            pass

        def error(self, *a: object, **k: object) -> None:
            pass

        def text_area(self, *a: object, **k: object) -> str:
            return ""

        def file_uploader(self, *a: object, **k: object) -> None:
            return None

        def button(self, *a: object, **k: object) -> bool:
            return False

        def columns(self, n: object, **k: object) -> list[FakeCol]:
            count = n if isinstance(n, int) else len(n)  # type: ignore[arg-type]
            return [FakeCol() for _ in range(count)]

        def expander(self, *a: object, **k: object) -> FakeCol:
            return FakeCol()

        def progress(self, *a: object, **k: object) -> "FakeSt":
            return self

        def plotly_chart(self, *a: object, **k: object) -> None:
            pass

        def metric(self, *a: object, **k: object) -> None:
            pass

        def empty(self) -> "FakeSt":
            return self

    monkeypatch.setattr(rc, "st", FakeSt())
    rc.render(reports_dir=str(tmp_path))

    joined = " ".join(captured_md)
    # Upload section must be reachable past the former early-return on abstention.
    assert (
        "Check your own list" in joined
    ), "'Check your own list' header not found — upload section was not reached on abstention week"
    # History strip: with one abstention screen, load_screen_history returns it as history.
    # Either a DATAFRAME was rendered or the 'Screen history' heading appeared.
    assert (
        "DATAFRAME" in joined or "Screen history" in joined
    ), "Neither DATAFRAME nor 'Screen history' found — history strip was not reached on abstention week"
