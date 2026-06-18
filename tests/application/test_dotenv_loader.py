"""Shared .env loader contract."""

from __future__ import annotations

import os
from pathlib import Path

from application.dotenv_loader import load_dotenv


def _write(tmp_path: Path, body: str) -> Path:
    p = tmp_path / ".env"
    p.write_text(body, encoding="utf-8")
    return p


def test_loads_key_value(tmp_path: Path) -> None:
    env = _write(tmp_path, 'FOO_TEST_KEY=abc123\n# comment\nBAR_TEST="quoted"\n')
    os.environ.pop("FOO_TEST_KEY", None)
    os.environ.pop("BAR_TEST", None)
    load_dotenv(env)
    assert os.environ.get("FOO_TEST_KEY") == "abc123"
    assert os.environ.get("BAR_TEST") == "quoted"  # quotes stripped
    os.environ.pop("FOO_TEST_KEY", None)
    os.environ.pop("BAR_TEST", None)


def test_never_overrides_existing(tmp_path: Path) -> None:
    env = _write(tmp_path, "ALREADY_SET_KEY=from_file\n")
    os.environ["ALREADY_SET_KEY"] = "from_env"
    load_dotenv(env)
    assert os.environ["ALREADY_SET_KEY"] == "from_env"  # real env wins
    os.environ.pop("ALREADY_SET_KEY", None)


def test_missing_file_is_silent(tmp_path: Path) -> None:
    load_dotenv(tmp_path / "does_not_exist.env")  # must not raise
