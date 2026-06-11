"""tests/application/test_delisted.py"""

from hypothesis import given
from hypothesis import strategies as st

from application.delisted import (
    is_delisted,
    load_prune_list,
    record_fetch_outcome,
    save_prune_list,
)


def test_no_data_increments_counter() -> None:
    state = record_fetch_outcome({}, "DEAD.TO", had_data=False)
    assert state["DEAD.TO"] == 1
    state = record_fetch_outcome(state, "DEAD.TO", had_data=False)
    assert state["DEAD.TO"] == 2


def test_data_resets_counter() -> None:
    state = {"FLAKY.TO": 2}
    state = record_fetch_outcome(state, "FLAKY.TO", had_data=True)
    assert state["FLAKY.TO"] == 0


def test_is_delisted_at_threshold() -> None:
    assert not is_delisted({"X.TO": 2}, "X.TO", threshold=3)
    assert is_delisted({"X.TO": 3}, "X.TO", threshold=3)
    assert not is_delisted({}, "UNKNOWN.TO", threshold=3)


def test_round_trip_persistence(tmp_path) -> None:
    path = str(tmp_path / "delisted.json")
    save_prune_list(path, {"A.TO": 3, "B.TO": 1})
    assert load_prune_list(path) == {"A.TO": 3, "B.TO": 1}


def test_load_missing_file_is_empty(tmp_path) -> None:
    assert load_prune_list(str(tmp_path / "nope.json")) == {}


@given(st.integers(min_value=0, max_value=10))
def test_property_data_always_resets(prior: int) -> None:
    state = record_fetch_outcome({"T.TO": prior}, "T.TO", had_data=True)
    assert state["T.TO"] == 0
