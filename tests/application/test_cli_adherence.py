"""tests/application/test_cli_adherence.py — end-to-end CLI pattern, mirrors
tests/application/test_cli_insider.py (CliRunner + monkeypatch + tmp_path)."""

import json
from datetime import datetime, timedelta

from click.testing import CliRunner

from application import cli as cli_mod


def _provider(ticker: str) -> list[tuple[datetime, float]]:
    start = datetime(2026, 6, 13)
    return [(start + timedelta(days=i), 100.0 - i * 0.3) for i in range(40)]


def test_adherence_report_end_to_end(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "application.cli.validation_commands.load_price_series",
        lambda t, s, e: _provider(t),
    )
    log = tmp_path / "discipline_log.jsonl"
    rows = [
        {
            "ticker": "XYZ.TO",
            "verdict": "REDUCE",
            "price": 100.0,
            "trend_health": -2.5,
            "as_of": "2026-06-13T09:00:00+00:00",
            "quantity": 50.0,
            "market_value_cad": 5000.0,
        },
        {
            "ticker": "XYZ.TO",
            "verdict": "REDUCE",
            "price": 95.0,
            "trend_health": -2.5,
            "as_of": "2026-06-20T09:00:00+00:00",
            "quantity": 50.0,
            "market_value_cad": 4750.0,
        },
    ]
    log.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    cash = tmp_path / "cash.json"
    cash.write_text(json.dumps({"cash_cad": 1000.0, "as_of": "2026-07-08"}))
    adh = tmp_path / "adherence_log.jsonl"

    result = CliRunner().invoke(
        cli_mod.cli,
        [
            "adherence-report",
            "--log",
            str(log),
            "--cash-config",
            str(cash),
            "--adherence-log",
            str(adh),
            "--today",
            "2026-07-10",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "IGNORED" in result.output  # XYZ never sold
    assert "gap" in result.output.lower()
    assert "skipped_unresolved" in result.output or "skipped" in result.output.lower()
    assert adh.exists()  # record appended
