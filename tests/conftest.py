"""Test-wide guards.

Some CLI tests invoke the click entrypoint, which loads the project-root .env
(application.dotenv_loader) into os.environ — that would leak a real
GEMINI_API_KEY into the in-process environment for subsequent tests and let them
make live API calls. Project rule: tests must never hit real APIs. This
autouse fixture strips live API keys before every test so summarizer selection
deterministically uses the offline template path unless a test sets its own key.
"""

from __future__ import annotations

import logging

import pytest
from loguru import logger as loguru_logger

_LIVE_API_KEYS = ("GEMINI_API_KEY", "GOOGLE_API_KEY")
# Multi-key Gemini fallback (GEMINI_API_KEY_2, _3, ...) — strip a generous
# range too, so a numbered fallback key in a real .env can't leak into tests
# either. Individual tests that need one set it explicitly via monkeypatch.
_LIVE_API_KEY_FALLBACKS = tuple(f"GEMINI_API_KEY_{n}" for n in range(2, 6))


@pytest.fixture(autouse=True)
def _strip_live_api_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in _LIVE_API_KEYS + _LIVE_API_KEY_FALLBACKS:
        monkeypatch.delenv(key, raising=False)


_TAB_MARKERS: dict[str, str] = {
    "test_risk_tab.py": "tab_risk",
    "test_weekly_brief_tab.py": "tab_weekly_brief",
    "test_research_candidates_tab.py": "tab_research",
    "test_tab1_redesign.py": "tab_screener",
    "test_positions_tab.py": "tab_positions",
    "test_positions_render.py": "tab_positions",
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
    """Apply smoke + tab markers without editing every test module (T9)."""
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


@pytest.fixture(autouse=False)
def caplog_loguru(caplog: pytest.LogCaptureFixture) -> None:
    """Bridge loguru output into pytest caplog so caplog.records captures loguru logs."""

    class PropagateHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            logging.getLogger(record.name).handle(record)

    handler_id = loguru_logger.add(PropagateHandler(), format="{message}")
    yield  # type: ignore[misc]
    loguru_logger.remove(handler_id)
