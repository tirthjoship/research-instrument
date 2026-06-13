from domain.peer_relative import sector_percentile


def test_percentile_basic():
    peers = [10.0, 20.0, 30.0, 40.0]
    assert sector_percentile(25.0, peers) == 50.0  # beats 2 of 4
    assert sector_percentile(45.0, peers) == 100.0
    assert sector_percentile(5.0, peers) == 0.0


def test_percentile_ignores_none_and_empty():
    assert sector_percentile(10.0, []) is None
    assert sector_percentile(10.0, [None, None]) is None
