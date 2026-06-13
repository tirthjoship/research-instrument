import inspect

from adapters.visualization.components import ledger
from domain.fit import FORBIDDEN_WORDS


def test_ledger_renders_segments() -> None:
    html = ledger.render_ledger(
        [("UNIVERSE", "512"), ("CLEARED", "0"), ("NET β", "+1.37")]
    )
    assert "512" in html and "CLEARED" in html and "ri-ledger" in html


def test_ledger_source_has_no_forbidden_words() -> None:
    src = inspect.getsource(ledger).lower()
    for w in FORBIDDEN_WORDS:
        assert w not in src
