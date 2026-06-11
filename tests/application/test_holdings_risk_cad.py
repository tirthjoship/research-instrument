"""tests/application/test_holdings_risk_cad.py"""

from datetime import datetime, timedelta, timezone

from application.holdings_reader import Holding
from application.holdings_risk import HoldingsRiskAssessmentUseCase


class _FakeNarrator:
    def narrate(self, context: dict[str, object]) -> str:
        return "test"


def _series(px: float) -> list[tuple[datetime, float]]:
    start = datetime(2024, 1, 1)
    return [(start + timedelta(days=i), px) for i in range(260)]


def _provider(ticker: str) -> list[tuple[datetime, float]]:
    if ticker == "USDCAD=X":
        return _series(1.35)
    if ticker == "AC.TO":
        return _series(20.0)
    return _series(75.0)  # SPY benchmark + US names (e.g. ARKK)


def test_cad_name_market_value_is_price_times_shares() -> None:
    uc = HoldingsRiskAssessmentUseCase(_provider, _FakeNarrator())
    report = uc.execute(
        [Holding("AC.TO", 30.0, 556.2, "FHSA")],
        datetime(2024, 1, 1, tzinfo=timezone.utc),
        datetime(2024, 9, 16, tzinfo=timezone.utc),
    )
    p = report["positions"][0]
    assert p.quantity == 30.0
    assert p.market_value_cad == 30.0 * 20.0  # fx 1.0 for .TO


def test_usd_name_market_value_converted_via_usdcad() -> None:
    uc = HoldingsRiskAssessmentUseCase(_provider, _FakeNarrator())
    report = uc.execute(
        [Holding("ARKK", 12.0, 1355.87, "FHSA")],
        datetime(2024, 1, 1, tzinfo=timezone.utc),
        datetime(2024, 9, 16, tzinfo=timezone.utc),
    )
    p = report["positions"][0]
    assert p.market_value_cad == 12.0 * 75.0 * 1.35


def test_fx_unavailable_yields_none_not_silent_native() -> None:
    def no_fx(ticker: str) -> list[tuple[datetime, float]]:
        if ticker == "USDCAD=X":
            return []
        return _series(75.0)

    uc = HoldingsRiskAssessmentUseCase(no_fx, _FakeNarrator())
    report = uc.execute(
        [Holding("ARKK", 12.0, 1355.87, "FHSA")],
        datetime(2024, 1, 1, tzinfo=timezone.utc),
        datetime(2024, 9, 16, tzinfo=timezone.utc),
    )
    assert report["positions"][0].market_value_cad is None  # fail loud downstream


def test_logged_rows_carry_quantity_and_cad_value(tmp_path, monkeypatch) -> None:
    import json

    from click.testing import CliRunner

    from application import cli as cli_mod

    monkeypatch.setattr(
        "application.price_returns.load_price_series",
        lambda t, s, e, *, strict=False: _provider(t),
    )

    csv_path = tmp_path / "holdings.csv"
    csv_path.write_text(
        "Symbol,Exchange,Quantity,Book Value (CAD),Account Type\n"
        "AC,TSX,30,556.2,FHSA\n"
    )
    log_path = tmp_path / "log.jsonl"
    out_path = tmp_path / "detail.txt"

    result = CliRunner().invoke(
        cli_mod.cli,
        [
            "holdings-risk",
            "--holdings",
            str(csv_path),
            "--out",
            str(out_path),
            "--log",
            str(log_path),
        ],
    )
    assert result.exit_code == 0, result.output
    row = json.loads(log_path.read_text().splitlines()[0])
    assert row["quantity"] == 30.0
    assert row["market_value_cad"] == 600.0  # 30 * 20.0, .TO so fx 1.0
