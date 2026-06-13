import inspect

from adapters.visualization.components import proof_tile
from domain.fit import FORBIDDEN_WORDS


def test_tile_renders_number_and_stamp() -> None:
    html = proof_tile.render_tile("Rank-IC", "0.004", stamp="FALSIFIED", tone="crimson")
    assert "0.004" in html and "FALSIFIED" in html and "ri-stamp" in html


def test_proof_tile_source_clean() -> None:
    src = inspect.getsource(proof_tile).lower()
    for w in FORBIDDEN_WORDS:
        assert w not in src
