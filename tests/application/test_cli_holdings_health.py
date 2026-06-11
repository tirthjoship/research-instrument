"""tests/application/test_cli_holdings_health.py"""

from datetime import datetime, timedelta

from click.testing import CliRunner

from application import cli as cli_mod


def _series(px: float) -> list[tuple[datetime, float]]:
    start = datetime(2024, 1, 1)
    return [(start + timedelta(days=i), px) for i in range(260)]


def test_health_summary_printed_and_failure_exits_nonzero(
    tmp_path, monkeypatch
) -> None:
    # AC.TO fetches fine; BROKE.TO raises (real error) -> FAILED=1, exit nonzero,
    # but AC.TO is still assessed (collect-then-fail).
    from domain.exceptions import PriceFetchError

    def fake_load(ticker, start, end, *, strict=False):
        if ticker == "USDCAD=X":
            return _series(1.35)
        if ticker == "BROKE.TO":
            if strict:
                raise PriceFetchError("BROKE.TO", cause=ConnectionError("x"))
            return []
        return _series(20.0)

    monkeypatch.setattr("application.price_returns.load_price_series", fake_load)

    csv_path = tmp_path / "h.csv"
    csv_path.write_text(
        "Symbol,Exchange,Quantity,Book Value (CAD),Account Type\n"
        "AC,TSX,30,556.2,FHSA\n"
        "BROKE,TSX,10,100.0,FHSA\n"
    )
    res = CliRunner().invoke(
        cli_mod.cli,
        [
            "holdings-risk",
            "--holdings",
            str(csv_path),
            "--out",
            str(tmp_path / "o.txt"),
            "--log",
            str(tmp_path / "l.jsonl"),
            "--prune-list",
            str(tmp_path / "delisted.json"),
        ],
    )
    assert "fetched OK=" in res.output
    assert "FAILED=1" in res.output
    assert "BROKE.TO" in res.output
    assert res.exit_code != 0  # loud failure
    # AC.TO still assessed despite BROKE.TO failing
    assert "Assessed" in res.output


def test_delisted_name_pruned_and_job_exits_zero(tmp_path, monkeypatch) -> None:
    # Spec acceptance: a name already at the delist threshold shows under
    # `pruned`, is NOT fetched or FAILED, and the job still exits 0 (no real
    # errors). DEAD.TO is pre-seeded at 3 consecutive no-data weeks.
    import json

    def fake_load(ticker, start, end, *, strict=False):
        if ticker == "USDCAD=X":
            return _series(1.35)
        if ticker == "DEAD.TO":
            raise AssertionError("pruned ticker must not be fetched")
        return _series(20.0)

    monkeypatch.setattr("application.price_returns.load_price_series", fake_load)

    prune_path = tmp_path / "delisted.json"
    prune_path.write_text(json.dumps({"DEAD.TO": 3}))
    csv_path = tmp_path / "h.csv"
    csv_path.write_text(
        "Symbol,Exchange,Quantity,Book Value (CAD),Account Type\n"
        "AC,TSX,30,556.2,FHSA\n"
        "DEAD,TSX,10,100.0,FHSA\n"
    )
    res = CliRunner().invoke(
        cli_mod.cli,
        [
            "holdings-risk",
            "--holdings",
            str(csv_path),
            "--out",
            str(tmp_path / "o.txt"),
            "--log",
            str(tmp_path / "l.jsonl"),
            "--prune-list",
            str(prune_path),
        ],
    )
    assert res.exit_code == 0, res.output  # no real errors -> clean exit
    assert "pruned=1" in res.output
    assert "FAILED=0" in res.output
