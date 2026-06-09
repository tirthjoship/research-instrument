import json
from datetime import datetime, timezone

from click.testing import CliRunner

from application import cli as cli_mod


def _log(tmp_path, dates):  # type: ignore[no-untyped-def]
    p = tmp_path / "disc.jsonl"
    with open(p, "w") as fh:
        for d in dates:
            fh.write(
                json.dumps(
                    {"ticker": "AAA", "verdict": "REDUCE", "price": 100.0, "as_of": d}
                )
                + "\n"
            )
    return str(p)


def test_resolve_flags_cli_thin_dates_label(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    # one as_of date, the name drops -> would naively PROCEED, but guard says THIN
    log = _log(tmp_path, [datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat()] * 40)

    def fake_prices(ticker, start, end):  # type: ignore[no-untyped-def]
        return [
            (datetime(2026, 1, 1, tzinfo=timezone.utc), 100.0),
            (datetime(2026, 3, 1, tzinfo=timezone.utc), 80.0),
        ]

    monkeypatch.setattr("application.cli.load_price_series", fake_prices, raising=False)
    result = CliRunner().invoke(cli_mod.cli, ["resolve-discipline-flags", "--log", log])
    assert result.exit_code == 0, result.output
    assert "INCONCLUSIVE_THIN_DATES" in result.output


def test_calibration_status_reports_thin_single_date(tmp_path):  # type: ignore[no-untyped-def]
    log = _log(tmp_path, [datetime(2026, 6, 8, tzinfo=timezone.utc).isoformat()] * 46)
    result = CliRunner().invoke(
        cli_mod.cli,
        [
            "discipline-calibration-status",
            "--log",
            log,
            "--today",
            "2026-06-09",
            "--gate-date",
            "2026-07-15",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "VERDICT: THIN" in result.output
    assert "distinct" in result.output.lower()
    assert "AAA" not in result.output  # masked: no tickers on stdout
