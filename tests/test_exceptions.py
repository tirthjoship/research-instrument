"""Tests for domain exceptions."""


def test_source_throttled_error_is_raisable():
    import pytest

    from domain.exceptions import SourceThrottledError

    with pytest.raises(SourceThrottledError):
        raise SourceThrottledError("google_trends rate-limited")
