import json
from datetime import datetime, timedelta
from pathlib import Path

from click.testing import CliRunner

from application import cli as cli_mod


def test_backtest_trend_sleeve_writes_report_and_prints_verdict(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    base = datetime(2006, 1, 2)
    flat = [(base + timedelta(days=i), 50.0) for i in range(1200)]

    # Avoid network: every ticker returns the same synthetic flat series.
    monkeypatch.setattr(
        "application.trend_sleeve_backtest.load_price_series",
        lambda ticker, start, end: flat,
        raising=False,
    )

    runner = CliRunner()
    result = runner.invoke(
        cli_mod.cli,
        [
            "backtest-trend-sleeve",
            "--start",
            "2007-01-01",
            "--end",
            "2008-12-01",
            "--report-dir",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "VERDICT" in result.output
    assert "drawdown" in result.output.lower()
    reports = list(Path(tmp_path).glob("trend_sleeve_*.json"))
    assert len(reports) == 1
    data = json.loads(reports[0].read_text())
    assert data["decision"] in ("PASS", "INCONCLUSIVE", "KILL")
    assert "sharpe_diff_ci_low" in data and "dd_reduction" in data
