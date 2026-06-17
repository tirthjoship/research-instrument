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
