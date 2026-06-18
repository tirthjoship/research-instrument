import tempfile
from datetime import datetime, timedelta

from adapters.ml.macro_beta_analyzer import RidgeMacroBetaEstimator
from adapters.ml.risk_stats_analyzer import RiskStatsAnalyzer
from application.macro_beta_use_case import MacroBetaUseCase


class _H:
    def __init__(self, ticker, shares):
        self.ticker = ticker
        self.shares = shares


def _trend(base, slope, n, start):
    return [(start + timedelta(days=i), base + slope * i) for i in range(n)]


def _provider_factory(series_by_ticker):
    def provider(ticker, start, end):
        return series_by_ticker.get(ticker, [])

    return provider


def _thresholds():
    return {
        "systematic_share_threshold": 0.60,
        "factor_dominance_threshold": 0.25,
        "drift_threshold": 0.50,
    }


def _make_uc(series):
    return MacroBetaUseCase(
        price_provider=_provider_factory(series),
        estimator=RidgeMacroBetaEstimator(alpha=0.2),
        factors=["SPY", "TLT", "UUP", "XLE"],
        alpha=0.2,
        headline_window=252,
        drift_window=63,
        thresholds=_thresholds(),
        history_days=400,
    )


def test_use_case_builds_book_exposure():
    start = datetime(2025, 1, 1)
    n = 320
    series = {
        "SPY": _trend(400, 0.5, n, start),
        "TLT": _trend(90, -0.05, n, start),
        "UUP": _trend(28, 0.0, n, start),
        "XLE": _trend(85, 0.1, n, start),
        "A": _trend(100, 0.4, n, start),
        "B": _trend(50, -0.02, n, start),
    }
    uc = _make_uc(series)
    book = uc.execute([_H("A", 10), _H("B", 20)], datetime(2026, 1, 1))
    assert book is not None
    assert book.total_holdings == 2
    assert book.coverage_holdings == 2
    assert set(book.net_beta_by_factor) == {"SPY", "TLT", "UUP", "XLE"}
    assert 0.0 <= book.systematic_share <= 1.0


def test_use_case_excludes_holding_without_history():
    start = datetime(2025, 1, 1)
    n = 320
    series = {
        "SPY": _trend(400, 0.5, n, start),
        "TLT": _trend(90, -0.05, n, start),
        "UUP": _trend(28, 0.0, n, start),
        "XLE": _trend(85, 0.1, n, start),
        "A": _trend(100, 0.4, n, start),
    }
    uc = _make_uc(series)
    book = uc.execute([_H("A", 10), _H("NEW", 5)], datetime(2026, 1, 1))
    assert book is not None
    assert book.total_holdings == 2
    assert book.coverage_holdings == 1


def test_use_case_all_factors_fail_returns_none():
    uc = _make_uc({})
    book = uc.execute([_H("A", 10)], datetime(2026, 1, 1))
    assert book is None


def test_coverage_value_frac_below_one_when_holding_unpriced():
    start = datetime(2025, 1, 1)
    n = 320
    series = {
        "SPY": _trend(400, 0.5, n, start),
        "TLT": _trend(90, -0.05, n, start),
        "UUP": _trend(28, 0.0, n, start),
        "XLE": _trend(85, 0.1, n, start),
        "A": _trend(100, 0.4, n, start),
        # "DEAD" has no series -> unpriced, must drag coverage below 100%
    }

    class _HC:
        def __init__(self, ticker, shares, cost_basis):
            self.ticker = ticker
            self.shares = shares
            self.cost_basis = cost_basis

    uc = _make_uc(series)
    book = uc.execute(
        [_HC("A", 10, 50.0), _HC("DEAD", 100, 30.0)], datetime(2026, 1, 1)
    )
    assert book is not None
    assert book.coverage_holdings == 1
    assert book.total_holdings == 2
    assert book.coverage_value_frac < 1.0  # DEAD's cost-basis value is in denominator


def test_weekly_brief_use_case_accepts_macro_fn():
    import inspect

    from application.weekly_brief_use_case import WeeklyBriefUseCase

    sig = inspect.signature(WeeklyBriefUseCase.__init__)
    assert "macro_fn" in sig.parameters


# ---- Task 8b: v8 risk stats wired through execute() ----


class _FakeSectorProvider:
    """All tickers map to 'Information Technology'."""

    @staticmethod
    def sector(ticker: str) -> str:
        return "Information Technology"


def _make_uc_v8(series, tmp_history_path):
    """Build a use-case with injected risk_analyzer + sector_provider + history_path."""
    return MacroBetaUseCase(
        price_provider=_provider_factory(series),
        estimator=RidgeMacroBetaEstimator(alpha=0.2),
        factors=["SPY", "TLT", "UUP", "XLE"],
        alpha=0.2,
        headline_window=252,
        drift_window=63,
        thresholds=_thresholds(),
        history_days=400,
        risk_analyzer=RiskStatsAnalyzer(seed=0, bootstrap_iters=50),
        sector_provider=_FakeSectorProvider(),
        history_path=tmp_history_path,
    )


def _synthetic_series_v8():
    """Return a series dict with two holdings that have real variance (non-linear trends)
    so the covariance matrix is non-degenerate and ENB >= 1."""
    import math

    start = datetime(2025, 1, 1)
    n = 320

    # SPY: uptrend with sine wave to create variance
    spy = [
        (start + timedelta(days=i), 400 + 0.5 * i + 10 * math.sin(i * 0.1))
        for i in range(n)
    ]
    tlt = [
        (start + timedelta(days=i), 90 - 0.05 * i + 5 * math.cos(i * 0.15))
        for i in range(n)
    ]
    uup = [(start + timedelta(days=i), 28 + 2 * math.sin(i * 0.07)) for i in range(n)]
    xle = [
        (start + timedelta(days=i), 85 + 0.1 * i + 8 * math.sin(i * 0.12))
        for i in range(n)
    ]
    # Two holdings with distinct variance profiles
    a = [
        (start + timedelta(days=i), 100 + 0.4 * i + 15 * math.sin(i * 0.09))
        for i in range(n)
    ]
    b = [
        (start + timedelta(days=i), 50 - 0.02 * i + 12 * math.cos(i * 0.13))
        for i in range(n)
    ]
    return {"SPY": spy, "TLT": tlt, "UUP": uup, "XLE": xle, "A": a, "B": b}


def test_v8_risk_stats_wired_through_execute():
    """Task 8b: ENB, sector_weights, risk_contribution, and sys_share_history
    are populated by execute() when risk_analyzer + sector_provider + history_path
    are injected. History written to disk is NOT the responsibility of execute()
    — it only prepends the loaded history and appends the current point in memory."""
    series = _synthetic_series_v8()

    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        tmp_path = f.name

    uc = _make_uc_v8(series, tmp_path)
    as_of = datetime(2026, 1, 1)
    result = uc.execute([_H("A", 10), _H("B", 20)], as_of)

    assert result is not None

    # ENB: with 2 holdings and real variance, must be >= 1
    assert result.enb >= 1.0, f"Expected enb >= 1.0, got {result.enb}"

    # sector_weights must be non-empty (both holdings have sector = "Information Technology")
    assert result.sector_weights, "sector_weights should be non-empty"
    assert "Information Technology" in result.sector_weights

    # risk_contribution fractions sum to ~1 (or dict is empty on degenerate data)
    if result.risk_contribution:
        total_rc = sum(result.risk_contribution.values())
        assert (
            abs(total_rc - 1.0) < 1e-6
        ), f"risk_contribution fractions should sum to 1.0, got {total_rc}"

    # sys_share_history: execute() appends current point IN MEMORY (no disk write)
    assert result.sys_share_history, "sys_share_history should be non-empty"
    last_date, last_val = result.sys_share_history[-1]
    assert (
        last_date == as_of.date().isoformat()
    ), f"Last history entry date should be {as_of.date().isoformat()}, got {last_date}"
    assert 0.0 <= last_val <= 1.0

    # suppressed_factors uses CI-straddles-zero logic (not VIF)
    # All suppressed factors must appear in beta_ci_by_factor with lo < 0 < hi
    for f in result.suppressed_factors:
        lo, hi = result.beta_ci_by_factor[f]
        assert (
            lo < 0.0 < hi
        ), f"Suppressed factor {f} must have CI straddling zero, got ({lo}, {hi})"

    # execute() must NOT write to the history file (read-only)
    import os

    file_size = os.path.getsize(tmp_path)
    assert (
        file_size == 0
    ), f"execute() must NOT write history to disk (file size should be 0, got {file_size})"


def test_pc_labels_fall_back_to_bet_n_when_no_sector_dominance():
    """PC labels must use 'Bet N' fallback + pc_labels_data_gap=True when
    no single sector covers >= 60% of the named top loaders."""
    from application.macro_beta_use_case import _label_principal_components

    # Simulate loadings where top tickers have mixed sectors
    # 2 PCs, each with 3 top tickers across different sectors
    loadings = [
        ["AAPL", "MSFT", "JPM"],  # PC1: 2 IT + 1 Financials → 67% IT → label IT
        ["XOM", "CVX", "AAPL"],  # PC2: 2 Energy + 1 IT → 67% Energy → label Energy
    ]

    def mixed_sector(ticker: str) -> str:
        # PC1: majority IT; PC2: majority Energy
        mapping = {
            "AAPL": "Information Technology",
            "MSFT": "Information Technology",
            "JPM": "Financials",
            "XOM": "Energy",
            "CVX": "Energy",
        }
        return mapping.get(ticker, "Unknown")

    labels, data_gap = _label_principal_components(loadings, mixed_sector)
    # With 67% dominance, both should get sector labels, data_gap=False
    assert labels[0] == "Information Technology"
    assert labels[1] == "Energy"
    assert not data_gap


def test_pc_labels_use_bet_n_when_no_60pct_dominance():
    """When no sector reaches 60% of named top loaders, label is 'Bet N'."""
    from application.macro_beta_use_case import _label_principal_components

    # Each PC has 3 tickers each with a different sector — no dominance
    loadings = [
        ["AAPL", "JPM", "XOM"],  # 1 IT, 1 Financials, 1 Energy → no 60% dominance
    ]

    def three_way_sector(ticker: str) -> str:
        mapping = {
            "AAPL": "Information Technology",
            "JPM": "Financials",
            "XOM": "Energy",
        }
        return mapping.get(ticker, "Unknown")

    labels, data_gap = _label_principal_components(loadings, three_way_sector)
    assert labels[0] == "Bet 1", f"Expected 'Bet 1', got '{labels[0]}'"
    assert data_gap is True


def test_suppressed_factors_uses_ci_straddles_zero_not_vif():
    """suppressed_factors must be exactly those factors whose beta CI lo < 0 < hi."""
    from application.macro_beta_use_case import _suppressed_from_ci

    beta_cis = {
        "SPY": (0.5, 1.2),  # both positive → NOT suppressed
        "TLT": (-0.3, 0.4),  # straddles zero → suppressed
        "UUP": (-1.0, -0.1),  # both negative → NOT suppressed
        "XLE": (-0.05, 0.05),  # straddles zero → suppressed
    }

    suppressed = _suppressed_from_ci(beta_cis)
    assert set(suppressed) == {"TLT", "XLE"}


def test_execute_does_not_write_history_to_disk():
    """execute() must be side-effect free: history file stays unchanged after call."""
    import os

    series = _synthetic_series_v8()

    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        tmp_path = f.name

    uc = _make_uc_v8(series, tmp_path)
    uc.execute([_H("A", 10), _H("B", 20)], datetime(2026, 1, 1))

    # File must still be empty (no write happened)
    assert os.path.getsize(tmp_path) == 0, "execute() must not write history to disk"


def test_pc_labels_all_unknown_falls_back_to_bet_n():
    from application.macro_beta_use_case import _label_principal_components

    labels, data_gap = _label_principal_components(
        [["AAA", "BBB"]], lambda t: "Unknown"
    )
    assert labels == ("Bet 1",)
    assert data_gap is True


def test_pc_labels_two_pcs_mixed_dominance():
    from application.macro_beta_use_case import _label_principal_components

    def sect(t):
        return {
            "A": "Energy",
            "B": "Energy",
            "C": "Energy",
            "D": "Energy",
            "E": "Health Care",
            "F": "Unknown",
        }[t]

    labels, data_gap = _label_principal_components(
        [["A", "B", "C"], ["D", "E", "F"]], sect
    )
    # PC1: 3/3 Energy → "Energy"; PC2: among named {D:Energy, E:Health Care} = 1/2 = 50% < 60% → Bet 2
    assert labels[0] == "Energy"
    assert labels[1] == "Bet 2"
    assert data_gap is True


def test_label_principal_components_dedups_same_sector() -> None:
    """Two PCs dominated by the same sector → second marked within-sector spread,
    so the ENB drill never shows the same bet name twice."""
    from application.macro_beta_use_case import _label_principal_components

    sectors = {
        "A": "Information Technology",
        "B": "Information Technology",
        "X": "Energy",
    }
    labels, gap = _label_principal_components(
        [["A", "B"], ["A", "B"], ["X"]], lambda t: sectors[t]
    )
    assert labels == (
        "Information Technology",
        "Information Technology (within-sector spread)",
        "Energy",
    )
    assert gap is False
