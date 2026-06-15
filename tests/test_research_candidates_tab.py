"""Render-contract tests for the Research Candidates tab.

Guards:
- verdict-driven headline uses real diagnostics counts (no fabricated "discipline working")
- UNDER_POWERED path surfaces "under-powered" when history coverage is thin
- HAS_CANDIDATES path surfaces cleared count
- EARNED_ABSTENTION path surfaces "working as designed" and never the old false copy
- Graceful fallback when diagnostics key absent (old cached JSON)
"""

from __future__ import annotations

import json
from typing import Any

# ---------------------------------------------------------------------------
# Shared FakeSt — reused across verdict-contract tests
# ---------------------------------------------------------------------------


class _FakeCol:
    def __enter__(self) -> "_FakeCol":
        return self

    def __exit__(self, *a: object) -> bool:
        return False


class _FakeSt:
    session_state: dict[str, object] = {}

    def __init__(self) -> None:
        self._captured: list[str] = []

    def markdown(self, body: object, **k: object) -> None:
        self._captured.append(str(body))

    def dataframe(self, *a: object, **k: object) -> None:
        self._captured.append("DATAFRAME")

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

    def columns(self, n: object, **k: object) -> "list[_FakeCol]":
        count = n if isinstance(n, int) else len(n)  # type: ignore[arg-type]
        return [_FakeCol() for _ in range(count)]

    def expander(self, *a: object, **k: object) -> "_FakeCol":
        return _FakeCol()

    def radio(self, *a: object, **k: object) -> str:
        return "By reason"

    def segmented_control(self, *a: object, **k: object) -> str:
        return "By reason"

    def spinner(self, *a: object, **k: object) -> "_FakeCol":
        return _FakeCol()

    def progress(self, *a: object, **k: object) -> "_FakeSt":
        return self

    def plotly_chart(self, *a: object, **k: object) -> None:
        pass

    def metric(self, *a: object, **k: object) -> None:
        pass

    def empty(self) -> "_FakeSt":
        return self

    @property
    def joined(self) -> str:
        return " ".join(self._captured)


def _write_screen(tmp_path: Any, filename: str, payload: dict[str, Any]) -> None:
    (tmp_path / filename).write_text(json.dumps(payload))


# ---------------------------------------------------------------------------
# Verdict-contract: HAS_CANDIDATES — cleared count visible, no false copy
# ---------------------------------------------------------------------------


def test_has_candidates_verdict_shows_cleared_count(
    tmp_path: Any, monkeypatch: Any
) -> None:
    """diagnostics(512,490,300,70) → '70' visible; 'discipline working' absent."""
    from adapters.visualization.tabs import research_candidates as rc

    _write_screen(
        tmp_path,
        "screen_2026-06-13.json",
        {
            "as_of": "2026-06-13",
            "universe_size": 512,
            "abstained": False,
            "diagnostics": {
                "scanned": 512,
                "had_history": 490,
                "above_trend": 300,
                "cleared": 70,
            },
            "candidates": [
                {
                    "ticker": "AAPL",
                    "composite": 0.85,
                    "why": "cheap",
                    "label": "RESEARCH_ONLY",
                    "factor_scores": [
                        {"name": "value", "percentile": 0.9, "contribution": 0.3}
                    ],
                    "trend_health": 0.7,
                }
            ],
        },
    )

    fake = _FakeSt()
    monkeypatch.setattr(rc, "st", fake)
    rc.render(reports_dir=str(tmp_path))

    assert "70" in fake.joined, "'70' (cleared count) must appear in rendered output"
    assert (
        "discipline working" not in fake.joined.lower()
    ), "False 'discipline working' copy must not appear"
    # S3 redesign: cleared count now appears in the footer ledger (CLEARED 70)
    # and in the "of N that cleared" tile sub-caption
    assert (
        "cleared" in fake.joined.lower()
    ), "HAS_CANDIDATES must render 'cleared' count somewhere (ledger or tile)"


# ---------------------------------------------------------------------------
# Verdict-contract: UNDER_POWERED — under-powered copy when thin history
# ---------------------------------------------------------------------------


def test_under_powered_verdict_shows_under_powered(
    tmp_path: Any, monkeypatch: Any
) -> None:
    """diagnostics(512,20,0,0) → 'under-powered' visible; 'discipline working' absent."""
    from adapters.visualization.tabs import research_candidates as rc

    _write_screen(
        tmp_path,
        "screen_2026-06-13.json",
        {
            "as_of": "2026-06-13",
            "universe_size": 512,
            "abstained": False,
            "diagnostics": {
                "scanned": 512,
                "had_history": 20,
                "above_trend": 0,
                "cleared": 0,
            },
            "candidates": [],
        },
    )

    fake = _FakeSt()
    monkeypatch.setattr(rc, "st", fake)
    rc.render(reports_dir=str(tmp_path))

    assert (
        "under-powered" in fake.joined.lower()
    ), "'under-powered' must appear in rendered output for thin-history screen"
    assert (
        "discipline working" not in fake.joined.lower()
    ), "False 'discipline working' copy must not appear on UNDER_POWERED path"


# ---------------------------------------------------------------------------
# Verdict-contract: EARNED_ABSTENTION — correct copy, no false copy
# ---------------------------------------------------------------------------


def test_earned_abstention_verdict_shows_correct_copy(
    tmp_path: Any, monkeypatch: Any
) -> None:
    """diagnostics(512,490,300,0) → 'working as designed'; 'discipline working' absent."""
    from adapters.visualization.tabs import research_candidates as rc

    _write_screen(
        tmp_path,
        "screen_2026-06-13.json",
        {
            "as_of": "2026-06-13",
            "universe_size": 512,
            "abstained": True,
            "diagnostics": {
                "scanned": 512,
                "had_history": 490,
                "above_trend": 300,
                "cleared": 0,
            },
            "candidates": [],
        },
    )

    fake = _FakeSt()
    monkeypatch.setattr(rc, "st", fake)
    rc.render(reports_dir=str(tmp_path))

    assert (
        "working as designed" in fake.joined.lower()
    ), "'working as designed' must appear for EARNED_ABSTENTION verdict"
    assert (
        "discipline working" not in fake.joined.lower()
    ), "False 'discipline working' copy must not appear on EARNED_ABSTENTION path"


# ---------------------------------------------------------------------------
# Graceful fallback: no diagnostics key (old cached JSON) — no crash, no false copy
# ---------------------------------------------------------------------------


def test_no_diagnostics_fallback_no_crash_no_false_copy(
    tmp_path: Any, monkeypatch: Any
) -> None:
    """Old JSON without 'diagnostics' key must not crash and must not emit false copy."""
    from adapters.visualization.tabs import research_candidates as rc

    _write_screen(
        tmp_path,
        "screen_2026-06-10.json",
        {
            "as_of": "2026-06-10",
            "universe_size": 430,
            "abstained": False,
            "candidates": [],
            # no 'diagnostics' key — simulates pre-threading cached JSON
        },
    )

    fake = _FakeSt()
    monkeypatch.setattr(rc, "st", fake)
    rc.render(reports_dir=str(tmp_path))  # must not raise

    assert (
        "discipline working" not in fake.joined.lower()
    ), "False 'discipline working' copy must not appear even for old JSON without diagnostics"
    assert (
        "working as designed" not in fake.joined.lower()
    ), "Fallback must not claim 'working as designed' — we don't know if names were scored"
    assert (
        "discipline" not in fake.joined.lower()
    ), "Fallback must not emit 'discipline' copy — verdict is unknown for old cached JSON"
    assert (
        "diagnostics unavailable" in fake.joined.lower()
    ), "Fallback must render a neutral 'diagnostics unavailable' message for old cached JSON"


# ---------------------------------------------------------------------------
# Original tests below (unchanged)
# ---------------------------------------------------------------------------


def test_research_candidates_source_has_no_forbidden_words():
    import inspect

    from adapters.visualization.tabs import research_candidates
    from domain.fit import FORBIDDEN_WORDS

    src = inspect.getsource(research_candidates).lower()
    for word in FORBIDDEN_WORDS:
        assert word not in src, f"forbidden word {word!r} in research_candidates source"


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

        def radio(self, *a: object, **k: object) -> str:
            return "By reason"

        def segmented_control(self, *a: object, **k: object) -> str:
            return "By reason"

        def spinner(self, *a: object, **k: object) -> "_FakeCol":
            return _FakeCol()

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
    # (Header copy is now "Have your own names? Check them" in Home tokens.)
    assert (
        "Have your own names" in joined or "evidence card" in joined
    ), "Zone 2 'check your own names' section was not reached on abstention week"
    # S7: the screen-history table was MOVED to the Trust tab; the screener now
    # shows only a link, not the in-tab DATAFRAME/'Screen history' heading.
    assert (
        "Trust tab" in joined or "See past screens" in joined
    ), "Trust-tab history link not found — Zone ③ link should replace the in-screener history table"
    assert (
        "DATAFRAME" not in joined
    ), "Screen-history DATAFRAME still rendered in the screener — it should live on Trust now"


# ---------------------------------------------------------------------------
# Task 6: 4-factor rich candidate cards
# ---------------------------------------------------------------------------

_FOUR_FACTOR_SCREEN = {
    "as_of": "2026-06-13",
    "universe_size": 512,
    "abstained": False,
    "diagnostics": {
        "scanned": 512,
        "had_history": 490,
        "above_trend": 300,
        "cleared": 70,
    },
    "candidates": [
        {
            "ticker": "NVDA",
            "composite": 1.45,
            "trend_health": 0.82,
            "label": "RESEARCH_ONLY",
            "why": "strong momentum + cheap on value",
            # quality raised to p=0.80 so NVDA qualifies for Quality compounders
            "factor_scores": [
                {
                    "name": "momentum",
                    "value": 1.82,
                    "percentile": 0.91,
                    "contribution": 0.35,
                },
                {
                    "name": "revision",
                    "value": 0.64,
                    "percentile": 0.73,
                    "contribution": 0.18,
                },
                {
                    "name": "quality",
                    "value": 0.81,
                    "percentile": 0.80,
                    "contribution": 0.22,
                },
                {
                    "name": "value",
                    "value": -0.31,
                    "percentile": 0.38,
                    "contribution": 0.25,
                },
            ],
        }
    ],
}

_MISSING_REVISION_SCREEN = {
    "as_of": "2026-06-13",
    "universe_size": 512,
    "abstained": False,
    "diagnostics": {
        "scanned": 512,
        "had_history": 490,
        "above_trend": 300,
        "cleared": 70,
    },
    "candidates": [
        {
            "ticker": "KO",
            "composite": 0.92,
            "trend_health": 0.71,
            "label": "RESEARCH_ONLY",
            "why": "cheap on value",
            "factor_scores": [
                {
                    "name": "momentum",
                    "value": 0.55,
                    "percentile": 0.62,
                    "contribution": 0.30,
                },
                # revision intentionally absent — should render as DATA-GAP
                # quality raised to p=0.80 so KO qualifies for Quality compounders
                {
                    "name": "quality",
                    "value": 0.81,
                    "percentile": 0.80,
                    "contribution": 0.35,
                },
                {
                    "name": "value",
                    "value": 1.10,
                    "percentile": 0.88,
                    "contribution": 0.35,
                },
            ],
        }
    ],
}


def test_four_factor_card_shows_all_factor_names(
    tmp_path: Any, monkeypatch: Any
) -> None:
    """All 4 factor names must appear in rendered output for a full-data candidate."""
    from adapters.visualization.tabs import research_candidates as rc

    _write_screen(tmp_path, "screen_2026-06-13.json", _FOUR_FACTOR_SCREEN)

    fake = _FakeSt()
    monkeypatch.setattr(rc, "st", fake)
    rc.render(reports_dir=str(tmp_path))

    joined = fake.joined.lower()
    # revision is now displayed as "analyst spread" (honest label rename — spec §3)
    for factor in ("momentum", "analyst spread", "quality", "value"):
        assert (
            factor in joined
        ), f"Factor '{factor}' not found in rendered candidate card"


def test_four_factor_card_composite_labelled_not_a_forecast(
    tmp_path: Any, monkeypatch: Any
) -> None:
    """Composite must be labelled as 'not a forecast' (or equivalent phrase)."""
    from adapters.visualization.tabs import research_candidates as rc

    _write_screen(tmp_path, "screen_2026-06-13.json", _FOUR_FACTOR_SCREEN)

    fake = _FakeSt()
    monkeypatch.setattr(rc, "st", fake)
    rc.render(reports_dir=str(tmp_path))

    joined = fake.joined.lower()
    assert (
        "not a forecast" in joined
    ), "Composite must be labelled with 'not a forecast' to prevent misreading as a buy signal"


def test_missing_revision_renders_data_gap(tmp_path: Any, monkeypatch: Any) -> None:
    """A candidate missing 'revision' in factor_scores must show DATA-GAP, never a number."""
    from adapters.visualization.tabs import research_candidates as rc

    _write_screen(tmp_path, "screen_2026-06-13.json", _MISSING_REVISION_SCREEN)

    fake = _FakeSt()
    monkeypatch.setattr(rc, "st", fake)
    rc.render(reports_dir=str(tmp_path))

    joined = fake.joined.lower()
    # DATA-GAP or data-gap must appear
    assert (
        "data-gap" in joined or "data gap" in joined
    ), "Missing revision factor must render as DATA-GAP, not a fabricated number"
    # Revision is now displayed as "analyst spread" (honest rename — spec §3).
    # The row must appear even when data is missing.
    assert (
        "analyst spread" in joined
    ), "Analyst spread (revision) row must appear even when data is missing"


def test_candidate_card_has_no_buy_sell_words(tmp_path: Any, monkeypatch: Any) -> None:
    """No buy/sell language must appear anywhere in rendered candidate cards."""
    from adapters.visualization.tabs import research_candidates as rc

    _write_screen(tmp_path, "screen_2026-06-13.json", _FOUR_FACTOR_SCREEN)

    fake = _FakeSt()
    monkeypatch.setattr(rc, "st", fake)
    rc.render(reports_dir=str(tmp_path))

    joined = fake.joined.lower()
    for forbidden in ("buy", "sell"):
        assert (
            forbidden not in joined
        ), f"Forbidden word '{forbidden}' must not appear in candidate card output"


def test_candidate_card_shows_research_read_and_do_next(
    tmp_path: Any, monkeypatch: Any
) -> None:
    """Rich card must include a 'What this tells you' and a 'Do next' section."""
    from adapters.visualization.tabs import research_candidates as rc

    _write_screen(tmp_path, "screen_2026-06-13.json", _FOUR_FACTOR_SCREEN)

    fake = _FakeSt()
    monkeypatch.setattr(rc, "st", fake)
    rc.render(reports_dir=str(tmp_path))

    joined = fake.joined.lower()
    # S3 redesign: "What this tells you" → "plain read:" + "Do next"
    assert (
        "plain read" in joined or "do next" in joined
    ), "Card must include a plain-language read or 'Do next' step"
    assert "do next" in joined, "'Do next' research step must appear in candidate card"


# ---------------------------------------------------------------------------
# Task 6 BLOCKING FIX: value==0.0 & percentile==0.0 is a DATA-GAP (real shape)
# ---------------------------------------------------------------------------

# The REAL data shape: all 4 factor dicts are PRESENT in factor_scores but
# revision has value=0.0, percentile=0.0, contribution=0.0 — produced by
# evidence_screen_use_case.py when analyst revision coverage is absent.
# Pre-fix: renders "+0.00 · p0/100" (fabricated-looking zero).
# Post-fix: renders DATA-GAP (muted), never "+0.00" or "p0".

_ZERO_REVISION_SCREEN = {
    "as_of": "2026-06-13",
    "universe_size": 512,
    "abstained": False,
    "diagnostics": {
        "scanned": 512,
        "had_history": 490,
        "above_trend": 300,
        "cleared": 70,
    },
    "candidates": [
        {
            "ticker": "MCD",
            "composite": 0.88,
            "trend_health": 0.65,
            "label": "RESEARCH_ONLY",
            "why": "solid quality signal",
            # All 4 factor dicts PRESENT — revision is all-zeros (no analyst coverage)
            # quality raised to p=0.80 so MCD qualifies for Quality compounders bucket
            # and the factor rows render in the card
            "factor_scores": [
                {
                    "name": "momentum",
                    "value": 0.72,
                    "percentile": 0.68,
                    "contribution": 0.30,
                },
                {
                    "name": "revision",
                    "value": 0.0,
                    "percentile": 0.0,
                    "contribution": 0.0,
                },
                {
                    "name": "quality",
                    "value": 0.81,
                    "percentile": 0.80,
                    "contribution": 0.35,
                },
                {
                    "name": "value",
                    "value": 0.38,
                    "percentile": 0.55,
                    "contribution": 0.35,
                },
            ],
        }
    ],
}

# A separate fixture to confirm a REAL mid-pack factor (value=0.0 but percentile!=0.0)
# is NOT treated as a gap — only the AND of both being 0.0 is a gap.
_REAL_ZERO_VALUE_SCREEN = {
    "as_of": "2026-06-13",
    "universe_size": 512,
    "abstained": False,
    "diagnostics": {
        "scanned": 512,
        "had_history": 490,
        "above_trend": 300,
        "cleared": 70,
    },
    "candidates": [
        {
            "ticker": "IBM",
            "composite": 0.77,
            "trend_health": 0.50,
            "label": "RESEARCH_ONLY",
            "why": "mixed signals",
            # quality raised to p=0.80 so IBM qualifies for Quality compounders bucket
            "factor_scores": [
                {
                    "name": "momentum",
                    "value": 0.72,
                    "percentile": 0.68,
                    "contribution": 0.30,
                },
                # revision: value exactly 0.0 but percentile=0.5 — legitimately mid-pack
                {
                    "name": "revision",
                    "value": 0.0,
                    "percentile": 0.5,
                    "contribution": 0.10,
                },
                {
                    "name": "quality",
                    "value": 0.81,
                    "percentile": 0.80,
                    "contribution": 0.35,
                },
                {
                    "name": "value",
                    "value": 0.38,
                    "percentile": 0.55,
                    "contribution": 0.35,
                },
            ],
        }
    ],
}


def test_zero_value_and_zero_pct_revision_renders_data_gap(
    tmp_path: Any, monkeypatch: Any
) -> None:
    """A factor with value==0.0 AND percentile==0.0 must show DATA-GAP, never '+0.00' or 'p0'.

    This is the REAL missing-coverage shape from evidence_screen_use_case.py — it never
    emits None, it emits all-zeros. Pre-fix: renders '+0.00 · p0/100' (fabricated).
    Post-fix: renders DATA-GAP (muted).
    """
    from adapters.visualization.tabs import research_candidates as rc

    _write_screen(tmp_path, "screen_2026-06-13.json", _ZERO_REVISION_SCREEN)

    fake = _FakeSt()
    monkeypatch.setattr(rc, "st", fake)
    rc.render(reports_dir=str(tmp_path))

    joined = fake.joined
    joined_lower = joined.lower()

    # DATA-GAP must appear (case-insensitive match for data-gap or data gap)
    assert (
        "data-gap" in joined_lower
        or "data gap" in joined_lower
        or "n/a" in joined_lower
    ), (
        "Revision with value==0.0 and percentile==0.0 must render DATA-GAP (no analyst coverage), "
        f"but got: {joined!r}"
    )

    # Must NOT show the fabricated-looking "+0.00" for revision
    assert "+0.00" not in joined, (
        "Revision with value==0.0 and percentile==0.0 must NOT render '+0.00' — "
        f"that is a fabricated-looking zero. Got: {joined!r}"
    )

    # Must NOT show "p0/100" for revision
    assert "p0/100" not in joined, (
        "Revision with value==0.0 and percentile==0.0 must NOT render 'p0/100' — "
        f"that is fabricated. Got: {joined!r}"
    )


def test_zero_value_nonzero_pct_revision_is_not_a_gap(
    tmp_path: Any, monkeypatch: Any
) -> None:
    """A factor with value==0.0 but percentile==0.5 is a REAL mid-pack factor — NOT a gap.

    The AND condition (value==0.0 AND percentile==0.0) must not mis-detect a
    legitimate zero-z-score name with a real percentile rank.
    """
    from adapters.visualization.tabs import research_candidates as rc

    _write_screen(tmp_path, "screen_2026-06-13.json", _REAL_ZERO_VALUE_SCREEN)

    fake = _FakeSt()
    monkeypatch.setattr(rc, "st", fake)
    rc.render(reports_dir=str(tmp_path))

    joined = fake.joined

    # revision row must render a numeric value, NOT DATA-GAP
    # percentile 0.5 → p50/100 should appear
    assert "p50" in joined, (
        "Revision with value==0.0 but percentile==0.5 is a real mid-pack factor — "
        f"must render p50, not DATA-GAP. Got: {joined!r}"
    )


# ---------------------------------------------------------------------------
# Task 3: maybe_render_gemini — privacy guard and lazy call
# ---------------------------------------------------------------------------


def test_gemini_skipped_when_not_local(monkeypatch: Any) -> None:
    """When is_local_runtime() is False, maybe_render_gemini returns empty or local note."""
    from adapters.visualization.tabs import research_candidates as rc

    monkeypatch.setattr(rc, "is_local_runtime", lambda: False)
    html = rc.maybe_render_gemini("SPG", facts={}, news=[])
    assert html == "" or "local" in html.lower()


def test_gemini_skipped_when_not_local_no_gemini_call(monkeypatch: Any) -> None:
    """When is_local_runtime() is False, GeminiNarratorAdapter.summarize_case is NOT called."""
    from adapters.visualization.tabs import research_candidates as rc

    called: list[str] = []

    class _SpyAdapter:
        def summarize_case(self, ctx: object) -> object:
            called.append("called")
            from domain.case_models import CaseResult

            return CaseResult((), (), True)

    monkeypatch.setattr(rc, "is_local_runtime", lambda: False)
    monkeypatch.setattr(rc, "_gemini_adapter", _SpyAdapter())
    rc.maybe_render_gemini("SPG", facts={}, news=[])
    assert (
        called == []
    ), "summarize_case must NOT be called when not local (privacy guard)"


def test_gemini_returns_html_when_local(monkeypatch: Any) -> None:
    """When is_local_runtime() is True, maybe_render_gemini returns the .gai HTML block."""
    from adapters.visualization.tabs import research_candidates as rc
    from domain.case_models import CasePoint, CaseResult

    class _StubAdapter:
        def summarize_case(self, ctx: object) -> CaseResult:
            return CaseResult(
                in_favor=(CasePoint("occupancy recovering", "reported"),),
                to_watch=(),
                data_gap=False,
            )

    monkeypatch.setattr(rc, "is_local_runtime", lambda: True)
    monkeypatch.setattr(rc, "_gemini_adapter", _StubAdapter())
    # Clear session state cache
    import streamlit as st

    st.session_state.pop("_gai_SPG", None)
    html = rc.maybe_render_gemini("SPG", facts={"occupancy": "recovering"}, news=[])
    assert "Google-AI read" in html
    assert "never an input" in html.lower()


def test_gemini_cached_in_session_state(monkeypatch: Any) -> None:
    """Second call for the same ticker uses session_state cache — adapter not called again."""
    from adapters.visualization.tabs import research_candidates as rc
    from domain.case_models import CasePoint, CaseResult

    call_count: list[int] = [0]

    class _CountingAdapter:
        def summarize_case(self, ctx: object) -> CaseResult:
            call_count[0] += 1
            return CaseResult(
                in_favor=(CasePoint("strong margins", "reported"),),
                to_watch=(),
                data_gap=False,
            )

    monkeypatch.setattr(rc, "is_local_runtime", lambda: True)
    monkeypatch.setattr(rc, "_gemini_adapter", _CountingAdapter())
    import streamlit as st

    st.session_state.pop("_gai_MSFT", None)

    rc.maybe_render_gemini("MSFT", facts={"revenue": "up"}, news=[])
    rc.maybe_render_gemini("MSFT", facts={"revenue": "up"}, news=[])
    assert (
        call_count[0] == 1
    ), "summarize_case must only be called once (cached after first call)"
