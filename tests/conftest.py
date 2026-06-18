"""Test-wide guards.

Some CLI tests invoke the click entrypoint, which loads the project-root .env
(application.dotenv_loader) into os.environ — that would leak a real
GEMINI_API_KEY into the in-process environment for subsequent tests and let them
make live API calls. CLAUDE.md rule #5: tests must never hit real APIs. This
autouse fixture strips live API keys before every test so summarizer selection
deterministically uses the offline template path unless a test sets its own key.
"""

from __future__ import annotations

import pytest

_LIVE_API_KEYS = ("GEMINI_API_KEY", "GOOGLE_API_KEY")


@pytest.fixture(autouse=True)
def _strip_live_api_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in _LIVE_API_KEYS:
        monkeypatch.delenv(key, raising=False)


_TAB_MARKERS: dict[str, str] = {
    "test_risk_tab.py": "tab_risk",
    "test_weekly_brief_tab.py": "tab_weekly_brief",
    "test_research_candidates_tab.py": "tab_research",
    "test_tab1_redesign.py": "tab_screener",
    "test_positions_tab.py": "tab_positions",
    "test_trust_tab.py": "tab_trust",
}

_SMOKE_FILES = frozenset(
    {
        "test_conviction_use_case.py",
        "test_domain_services.py",
        "test_phase5_tabs.py",
        "test_risk_tab.py",
        "test_weekly_brief_tab.py",
    }
)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Apply smoke + tab markers without editing every test module (ADR-061 / T9)."""
    for item in items:
        path = str(item.path)
        fname = item.path.name

        if "/tests/domain/" in path.replace("\\", "/"):
            item.add_marker(pytest.mark.smoke)

        tab = _TAB_MARKERS.get(fname)
        if tab is not None:
            item.add_marker(getattr(pytest.mark, tab))

        if fname in _SMOKE_FILES:
            item.add_marker(pytest.mark.smoke)
