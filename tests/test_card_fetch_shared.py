"""Tests for shared card-fetch helpers exposed from adapters.visualization.card_fetch."""

from adapters.visualization import card_fetch


def test_public_helpers_exist() -> None:
    assert hasattr(card_fetch, "fetch_card")
    assert hasattr(card_fetch, "implied_cost")
    assert hasattr(card_fetch, "window_returns")


def test_implied_cost_inverts_return() -> None:
    # price 110 after +10% implies cost 100
    assert round(card_fetch.implied_cost(110.0, 10.0), 2) == 100.0  # type: ignore[arg-type]


def test_implied_cost_zero_return() -> None:
    assert card_fetch.implied_cost(100.0, 0.0) == 100.0  # type: ignore[arg-type]


def test_implied_cost_none_inputs() -> None:
    assert card_fetch.implied_cost(None, 10.0) is None
    assert card_fetch.implied_cost(100.0, None) is None


def test_window_returns_shape() -> None:
    closes = [float(x) for x in range(1, 300)]
    rets = card_fetch.window_returns(closes)
    assert isinstance(rets, tuple)
    assert all(isinstance(x, float) for x in rets)


def test_window_returns_empty() -> None:
    assert card_fetch.window_returns([]) == ()
