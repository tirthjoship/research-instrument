import json
from datetime import datetime, timezone

from application.fit_use_case import gather_and_assess


def _write_screen(tmp_path, tickers_composites):
    p = tmp_path / "screen_2026-06-13.json"
    p.write_text(
        json.dumps(
            {
                "as_of": "2026-06-13",
                "candidates": [
                    {"ticker": t, "composite": c, "trend_health": 0.8}
                    for t, c in tickers_composites
                ],
            }
        )
    )
    return str(tmp_path)


def _write_summary(tmp_path, macro):
    p = tmp_path / "brief_summary.json"
    p.write_text(json.dumps({"as_of": "2026-06-13", "macro": macro}))
    return str(p)


def _write_holdings(tmp_path):
    # Headers match the real read_holdings parser:
    # _get(row, "symbol"), _get(row, "quantity"), _get(row, "book value (cad)"),
    # _get(row, "account type") — all case-insensitive strip matches.
    p = tmp_path / "holdings.csv"
    p.write_text(
        "Symbol,Quantity,Book Value (CAD),Account Type\n"
        "AAPL,10,5000,TFSA\nMSFT,5,3000,TFSA\n"
    )
    return str(p)


def test_gather_full_inputs(tmp_path):
    reports = _write_screen(tmp_path, [("NVDA", 2.0), ("AAPL", 0.5), ("XYZ", -1.0)])
    summary = _write_summary(
        tmp_path,
        {
            "net_beta_by_factor": {"SPY": 1.2},
            "systematic_share": 0.63,
        },
    )
    holdings = _write_holdings(tmp_path)
    v = gather_and_assess(
        ticker="NVDA",
        reports_dir=reports,
        summary_path=summary,
        holdings_path=holdings,
        beta_fn=lambda ticker, as_of: 1.4,
        as_of=datetime(2026, 6, 13, tzinfo=timezone.utc),
        systematic_share_threshold=0.60,
    )
    assert v.ticker == "NVDA"
    assert v.evidence_grade == "STRONG"
    assert any(f.kind == "BETA_AMPLIFY" for f in v.fit_flags)


def test_gather_all_artifacts_missing_degrades(tmp_path):
    v = gather_and_assess(
        ticker="NVDA",
        reports_dir=str(tmp_path),
        summary_path=str(tmp_path / "nope.json"),
        holdings_path=str(tmp_path / "nope.csv"),
        beta_fn=lambda ticker, as_of: None,
        as_of=datetime(2026, 6, 13, tzinfo=timezone.utc),
        systematic_share_threshold=0.60,
    )
    assert v.evidence_grade == "UNKNOWN"
    assert v.label == "RESEARCH_ONLY"
    gaps = [f for f in v.fit_flags if f.kind == "DATA_GAP"]
    assert len(gaps) >= 2


def test_beta_fn_exception_becomes_data_gap(tmp_path):
    def boom(ticker, as_of):
        raise RuntimeError("yfinance down")

    v = gather_and_assess(
        ticker="NVDA",
        reports_dir=str(tmp_path),
        summary_path=str(tmp_path / "nope.json"),
        holdings_path=str(tmp_path / "nope.csv"),
        beta_fn=boom,
        as_of=datetime(2026, 6, 13, tzinfo=timezone.utc),
        systematic_share_threshold=0.60,
    )
    assert v.label == "RESEARCH_ONLY"
