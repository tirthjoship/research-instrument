from domain.fit import FitVerdict


def _fake_fit(ticker: str) -> FitVerdict:
    return FitVerdict(
        ticker=ticker, evidence_grade="MODERATE", fit_flags=(), summary=f"{ticker} ok."
    )


def test_parse_tickers_text_variants():
    from application.batch_fit_use_case import parse_tickers

    assert parse_tickers("nvda, aapl\nko msft,aapl") == ["NVDA", "AAPL", "KO", "MSFT"]


def test_parse_tickers_rejects_junk_and_caps():
    from application.batch_fit_use_case import MAX_TICKERS, parse_tickers

    out = parse_tickers(",".join(f"T{i}" for i in range(40)) + ", $$bad$$")
    assert len(out) == MAX_TICKERS
    assert all(t.isalnum() or "." in t or "-" in t for t in out)


def test_parse_csv_symbol_column():
    from application.batch_fit_use_case import parse_csv_tickers

    csv_text = "Name,Symbol,Qty\nApple,AAPL,5\nNvidia,NVDA,2\n"
    assert parse_csv_tickers(csv_text) == ["AAPL", "NVDA"]


def test_parse_csv_first_column_fallback():
    from application.batch_fit_use_case import parse_csv_tickers

    csv_text = "ko\nmsft\n"
    assert parse_csv_tickers(csv_text) == ["KO", "MSFT"]


def test_batch_fit_runs_per_ticker_and_survives_failure():
    from application.batch_fit_use_case import batch_fit

    def fit_fn(ticker):
        if ticker == "BAD":
            raise RuntimeError("boom")
        return _fake_fit(ticker)

    rows = batch_fit(["NVDA", "BAD"], fit_fn=fit_fn)
    assert len(rows) == 2
    assert rows[0].fetch_ok and rows[0].verdict.evidence_grade == "MODERATE"
    assert not rows[1].fetch_ok
    assert rows[1].verdict.evidence_grade == "UNKNOWN"
    assert rows[1].verdict.label == "RESEARCH_ONLY"


def test_parse_tickers_strips_bom():
    from application.batch_fit_use_case import parse_tickers

    assert parse_tickers("﻿KO MSFT") == ["KO", "MSFT"]


def test_parse_csv_strips_bom_header():
    from application.batch_fit_use_case import parse_csv_tickers

    csv_text = "﻿Name,Symbol,Qty\nApple,AAPL,5\n"
    assert parse_csv_tickers(csv_text) == ["AAPL"]


def test_parse_tickers_rejects_lone_punctuation():
    from application.batch_fit_use_case import parse_tickers

    assert parse_tickers(". - -- AAPL BRK.B") == ["AAPL", "BRK.B"]


def test_batch_fit_invokes_progress_per_ticker():
    from application.batch_fit_use_case import batch_fit
    from domain.fit import FitVerdict

    calls = []

    def fit_fn(t: str) -> FitVerdict:
        return FitVerdict(
            ticker=t, evidence_grade="MODERATE", fit_flags=(), summary=f"{t} ok."
        )

    batch_fit(
        ["NVDA", "AAPL"],
        fit_fn=fit_fn,
        progress=lambda frac, t: calls.append((round(frac, 3), t)),
    )
    assert calls == [(0.5, "NVDA"), (1.0, "AAPL")]
