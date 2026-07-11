import inspect

from adapters.visualization.components import stock_metrics
from domain.fit import FORBIDDEN_WORDS

REQUIRED_KEYS = [
    "pe_ttm",
    "peg",
    "ev_ebitda",
    "ps",
    "p_fcf",
    "roic",
    "net_debt_ebitda",
    "interest_coverage",
    "relative_strength",
    "co_movement",
]


def test_registry_has_required_keys():
    for k in REQUIRED_KEYS:
        assert k in stock_metrics.STOCK_METRICS, f"missing metric {k}"
        meaning, basis = stock_metrics.STOCK_METRICS[k]
        assert meaning and basis


def test_metric_info_renders_tooltip():
    html = stock_metrics.metric_info("peg")
    assert "sa-tip" in html and "PEG" in html


def test_unknown_key_raises():
    import pytest

    with pytest.raises(KeyError):
        stock_metrics.metric_info("does_not_exist")


def test_clean():
    src = inspect.getsource(stock_metrics).lower()
    for w in FORBIDDEN_WORDS:
        assert w not in src
