"""Tests for adapters.ml.gemini_models — no network calls (monkeypatched)."""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Helpers to build a fake google.generativeai module
# ---------------------------------------------------------------------------


def _make_fake_genai(responses: list[str | BaseException]) -> types.ModuleType:
    """Return a fake genai module whose GenerativeModel.generate_content
    plays back *responses* in order (str = success, exception = raise)."""
    call_index: list[int] = [0]

    class FakeModel:
        def __init__(self, name: str) -> None:
            self._name = name

        def generate_content(self, prompt: str) -> MagicMock:
            idx = call_index[0]
            call_index[0] += 1
            result = responses[idx]
            if isinstance(result, BaseException):
                raise result
            resp = MagicMock()
            resp.text = result
            return resp

    fake = types.ModuleType("google.generativeai")
    fake.configure = MagicMock()  # type: ignore[attr-defined]
    fake.GenerativeModel = FakeModel  # type: ignore[attr-defined]
    return fake


def _inject_genai(monkeypatch: pytest.MonkeyPatch, fake: types.ModuleType) -> None:
    """Inject fake genai into sys.modules so the lazy import in generate_with_fallback
    picks it up."""
    monkeypatch.setitem(sys.modules, "google.generativeai", fake)
    # Also ensure parent package exists
    if "google" not in sys.modules:
        google_pkg = types.ModuleType("google")
        monkeypatch.setitem(sys.modules, "google", google_pkg)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_chain_has_at_least_three_entries() -> None:
    from adapters.ml.gemini_models import GEMINI_MODEL_CHAIN

    assert len(GEMINI_MODEL_CHAIN) >= 3


def test_first_model_429_falls_through_to_second(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """First model raises a 429-like error; second model returns text."""
    quota_err = Exception("429 Resource has been exhausted (resourceExhausted)")
    fake = _make_fake_genai([quota_err, "success text from model 2"])
    _inject_genai(monkeypatch, fake)

    # Force module to re-do the lazy import with our fake
    monkeypatch.delitem(sys.modules, "adapters.ml.gemini_models", raising=False)

    from adapters.ml.gemini_models import GEMINI_MODEL_CHAIN, generate_with_fallback

    two_model_chain: tuple[str, ...] = (GEMINI_MODEL_CHAIN[0], GEMINI_MODEL_CHAIN[1])
    result = generate_with_fallback("fake-key", "test prompt", models=two_model_chain)
    assert result == "success text from model 2"


def test_all_models_quota_raises_last_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """All models raise quota errors → the last quota exception is re-raised."""
    errs = [
        Exception("429 quota exceeded"),
        Exception("quota exhausted"),
        Exception("ResourceExhausted: rate limit"),
    ]
    fake = _make_fake_genai(list(errs))  # type: ignore[arg-type]
    _inject_genai(monkeypatch, fake)
    monkeypatch.delitem(sys.modules, "adapters.ml.gemini_models", raising=False)

    from adapters.ml.gemini_models import generate_with_fallback

    three_chain = ("model-a", "model-b", "model-c")
    with pytest.raises(Exception, match="rate limit"):
        generate_with_fallback("fake-key", "prompt", models=three_chain)


def test_non_quota_error_reraised_immediately_no_second_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-quota error (e.g. ValueError) on the first model is re-raised
    immediately; the second model is never tried."""
    real_err = ValueError("bad request — invalid argument")
    # If a second call were made it would return "should not be reached"
    fake = _make_fake_genai([real_err, "should not be reached"])
    _inject_genai(monkeypatch, fake)
    monkeypatch.delitem(sys.modules, "adapters.ml.gemini_models", raising=False)

    from adapters.ml.gemini_models import generate_with_fallback

    two_chain = ("model-a", "model-b")
    with pytest.raises(ValueError, match="invalid argument"):
        generate_with_fallback("fake-key", "prompt", models=two_chain)


def test_first_success_returns_immediately(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the first model succeeds the helper returns without trying others."""
    fake = _make_fake_genai(["first model text"])
    _inject_genai(monkeypatch, fake)
    monkeypatch.delitem(sys.modules, "adapters.ml.gemini_models", raising=False)

    from adapters.ml.gemini_models import GEMINI_MODEL_CHAIN, generate_with_fallback

    result = generate_with_fallback(
        "fake-key", "prompt", models=(GEMINI_MODEL_CHAIN[0],)
    )
    assert result == "first model text"


# ---------------------------------------------------------------------------
# Multi-key fallback: a second (or third) GEMINI_API_KEY absorbs load once an
# earlier key's whole-account daily quota (not just one model) is exhausted.
# ---------------------------------------------------------------------------


def test_load_gemini_api_keys_collects_primary_and_numbered_fallbacks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from adapters.ml.gemini_models import load_gemini_api_keys

    monkeypatch.setenv("GEMINI_API_KEY", "key-1")
    monkeypatch.setenv("GEMINI_API_KEY_2", "key-2")
    monkeypatch.setenv("GEMINI_API_KEY_3", "key-3")
    assert load_gemini_api_keys() == ("key-1", "key-2", "key-3")


def test_load_gemini_api_keys_stops_at_first_gap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GEMINI_API_KEY_2 set but GEMINI_API_KEY_3 unset — must not silently
    skip the gap and pick up a later GEMINI_API_KEY_4."""
    monkeypatch.setenv("GEMINI_API_KEY", "key-1")
    monkeypatch.setenv("GEMINI_API_KEY_2", "key-2")
    monkeypatch.delenv("GEMINI_API_KEY_3", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY_4", "key-4")
    from adapters.ml.gemini_models import load_gemini_api_keys

    assert load_gemini_api_keys() == ("key-1", "key-2")


def test_load_gemini_api_keys_empty_when_none_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY_2", raising=False)
    from adapters.ml.gemini_models import load_gemini_api_keys

    assert load_gemini_api_keys() == ()


def test_load_gemini_api_keys_drops_duplicates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "same-key")
    monkeypatch.setenv("GEMINI_API_KEY_2", "same-key")
    from adapters.ml.gemini_models import load_gemini_api_keys

    assert load_gemini_api_keys() == ("same-key",)


def test_key_fallback_switches_key_when_whole_key_quota_exhausted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """First key's entire model chain is quota-exhausted (a whole-account
    daily cap fails fast on every model) — the second key must be tried and
    succeed, using its own fresh model chain."""
    quota_err = Exception("429 quota exceeded")
    # Key 1: both models in the chain quota-exhausted. Key 2: first model succeeds.
    fake = _make_fake_genai([quota_err, quota_err, "success from key 2"])
    _inject_genai(monkeypatch, fake)
    monkeypatch.delitem(sys.modules, "adapters.ml.gemini_models", raising=False)

    from adapters.ml.gemini_models import generate_with_key_fallback

    result = generate_with_key_fallback(
        ("key-1", "key-2"), "prompt", models=("model-a", "model-b")
    )
    assert result == "success from key 2"
    # configure() must have been called with each key in turn.
    configured_keys = [c.kwargs.get("api_key") for c in fake.configure.call_args_list]  # type: ignore[attr-defined]
    assert configured_keys == ["key-1", "key-2"]


def test_key_fallback_raises_last_exception_when_all_keys_exhausted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    errs = [Exception("429 key1 quota"), Exception("429 key2 quota")]
    fake = _make_fake_genai(list(errs))  # type: ignore[arg-type]
    _inject_genai(monkeypatch, fake)
    monkeypatch.delitem(sys.modules, "adapters.ml.gemini_models", raising=False)

    from adapters.ml.gemini_models import generate_with_key_fallback

    with pytest.raises(Exception, match="key2 quota"):
        generate_with_key_fallback(("key-1", "key-2"), "prompt", models=("model-a",))


def test_key_fallback_non_quota_error_reraised_no_second_key_tried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_err = ValueError("bad request — invalid argument")
    fake = _make_fake_genai([real_err, "should not be reached"])
    _inject_genai(monkeypatch, fake)
    monkeypatch.delitem(sys.modules, "adapters.ml.gemini_models", raising=False)

    from adapters.ml.gemini_models import generate_with_key_fallback

    with pytest.raises(ValueError, match="invalid argument"):
        generate_with_key_fallback(("key-1", "key-2"), "prompt", models=("model-a",))


def test_key_fallback_empty_keys_raises_value_error() -> None:
    from adapters.ml.gemini_models import generate_with_key_fallback

    with pytest.raises(ValueError):
        generate_with_key_fallback((), "prompt")
