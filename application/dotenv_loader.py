"""Minimal project-root .env loader (no python-dotenv dependency).

Both the Streamlit dashboard and the CLI use this so keys like GEMINI_API_KEY in
the project-root .env reach every entry point — not just the app. Without it, a
CLI run (e.g. ``weekly-brief --cite-cases``) never sees the key and silently
falls back to the offline template summarizer.

Never overrides a variable already set in the real environment; fails silent on
any error (env loading must never crash an entry point).
"""

from __future__ import annotations

import os
from pathlib import Path

# application/dotenv_loader.py → parents[1] is the repo root.
_ENV_PATH = Path(__file__).resolve().parents[1] / ".env"


def load_dotenv(env_path: Path = _ENV_PATH) -> None:
    """Load KEY=VALUE lines from the project-root .env into os.environ.

    Existing environment variables win (never overridden). Blank lines, comments
    (#…), and lines without '=' are skipped. Surrounding quotes are stripped.
    """
    try:
        if not env_path.exists():
            return
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val
    except Exception:  # noqa: BLE001 — env loading must never crash an entry point
        pass
