"""Pin the committed data/sample/ demo artifacts to the bundled sample book.

Cold-start visitors (local or hosted) see these files — they must never contain
tickers or figures outside the 10-name sample book (data/sample/sample_book.csv).
"""

from __future__ import annotations

import json
from pathlib import Path

from application.sample_book import load_sample_book

SAMPLE_DIR = Path("data/sample")


def _sample_tickers() -> set[str]:
    return {h.ticker for h in load_sample_book()}


def test_sample_brief_summary_exists_and_parses() -> None:
    path = SAMPLE_DIR / "brief_summary.json"
    assert path.exists(), "data/sample/brief_summary.json must be committed"
    data = json.loads(path.read_text())
    assert "holdings" in data
    assert "as_of" in data


def test_sample_brief_holdings_are_exactly_the_sample_book() -> None:
    data = json.loads((SAMPLE_DIR / "brief_summary.json").read_text())
    tickers = {h["ticker"] for h in data["holdings"]}
    assert tickers == _sample_tickers()


def test_sample_weekly_brief_markdown_exists() -> None:
    path = SAMPLE_DIR / "weekly_brief.md"
    assert path.exists(), "data/sample/weekly_brief.md must be committed"
    assert path.read_text().strip()


def test_sample_screen_report_exists_and_parses() -> None:
    screens = sorted(SAMPLE_DIR.glob("screen_*.json"))
    assert screens, "a committed data/sample/screen_<date>.json is required"
    data = json.loads(screens[-1].read_text())
    assert "candidates" in data
    assert "as_of" in data


def test_sample_book_csv_has_ten_holdings() -> None:
    assert len(_sample_tickers()) == 10
