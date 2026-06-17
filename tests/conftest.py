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
