"""Task 12 — positions.render() TDD bootstrap tests."""

import adapters.visualization.tabs.positions as positions


def test_render_is_callable():
    assert callable(positions.render)


def test_threshold_constant():
    # small-book flat-treemap threshold is defined and sane
    assert positions.SMALL_BOOK_MAX == 5
