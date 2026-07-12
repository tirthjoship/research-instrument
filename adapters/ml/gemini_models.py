"""Shared Gemini multi-model + multi-key fallback helper.

Free-tier quota is **per model**, so rotating through models on quota/rate errors
recovers capacity without giving up on the request. Some quota errors are
**whole-account** (a daily free-tier request cap shared across every model on
one API key/project) — model rotation alone can't recover from those, so a
second key (a separate project, its own quota bucket) is tried next.

Chain order = preference (latency / capability); each entry has its own free quota.
``gemini-flash-latest`` is last as a catch-all alias that may overlap an earlier
entry but provides a final safety net.
"""

from __future__ import annotations

import os

from loguru import logger

# ---------------------------------------------------------------------------
# Public chain constant
# ---------------------------------------------------------------------------

GEMINI_MODEL_CHAIN: tuple[str, ...] = (
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash-lite",
    "gemini-flash-latest",
)

# Keywords that identify quota / rate-limit / transient availability errors.
# Matched case-insensitively against str(exception).
_QUOTA_MARKERS: tuple[str, ...] = (
    "429",
    "quota",
    "exhausted",
    "rate limit",
    "resourceexhausted",
    "unavailable",
    "deadline",
)


def _is_quota_error(exc: BaseException) -> bool:
    low = str(exc).lower()
    return any(marker in low for marker in _QUOTA_MARKERS)


def generate_with_fallback(
    api_key: str,
    prompt: str,
    *,
    models: tuple[str, ...] = GEMINI_MODEL_CHAIN,
    temperature: float | None = None,
) -> str:
    """Call Gemini with automatic model fallback on quota/rate errors.

    Iterates *models* in order. On a quota / rate-limit / transient error the
    current model is skipped and the next one is tried. Any other exception
    (e.g. ``ValueError``, ``AuthenticationError``) is re-raised immediately so
    bugs surface rather than burning the rest of the chain.

    *temperature* (when given) is passed through as the generation config —
    callers that need determinism (e.g. event classification, ADR-030) pass 0.0.

    Returns the response text from the first model that succeeds.
    Raises the last quota exception if every model in *models* is exhausted.
    """
    import google.generativeai as genai  # lazy — don't require package at import time

    genai.configure(api_key=api_key)

    gen_config = (
        genai.types.GenerationConfig(temperature=temperature)
        if temperature is not None
        else None
    )
    last_quota_exc: BaseException | None = None

    for model_name in models:
        try:
            model = genai.GenerativeModel(model_name)
            resp = (
                model.generate_content(prompt, generation_config=gen_config)
                if gen_config is not None
                else model.generate_content(prompt)
            )
            logger.info("gemini_fallback: succeeded with model={}", model_name)
            return resp.text  # type: ignore[no-any-return]
        except Exception as exc:  # noqa: BLE001
            if _is_quota_error(exc):
                logger.warning(
                    "gemini_fallback: quota/rate error on model={} reason={!r} — trying next",
                    model_name,
                    str(exc)[:120],
                )
                last_quota_exc = exc
                continue
            # Non-quota error → re-raise immediately
            raise

    # All models exhausted by quota errors
    assert last_quota_exc is not None  # always set if we reach here
    raise last_quota_exc


def load_gemini_api_keys(primary: str | None = None) -> tuple[str, ...]:
    """Collect available Gemini API keys for fallback.

    Order: *primary* if given, else ``GEMINI_API_KEY``; then numbered
    fallbacks ``GEMINI_API_KEY_2``, ``GEMINI_API_KEY_3``, ... — stops at the
    first missing suffix (a gap is not skipped over). Duplicate keys are
    dropped, order preserved. Returns ``()`` when no key is available.
    """
    keys: list[str] = []
    first = primary or os.environ.get("GEMINI_API_KEY")
    if first:
        keys.append(first)

    n = 2
    while True:
        nxt = os.environ.get(f"GEMINI_API_KEY_{n}")
        if not nxt:
            break
        keys.append(nxt)
        n += 1

    seen: set[str] = set()
    unique: list[str] = []
    for k in keys:
        if k not in seen:
            seen.add(k)
            unique.append(k)
    return tuple(unique)


def generate_with_key_fallback(
    api_keys: tuple[str, ...],
    prompt: str,
    *,
    models: tuple[str, ...] = GEMINI_MODEL_CHAIN,
    temperature: float | None = None,
) -> str:
    """Call ``generate_with_fallback`` per key, rotating keys on whole-account
    quota exhaustion (every model under one key failing is a strong signal
    the *account*, not just one model, is out of quota).

    Each key gets its own full *models* chain attempt via
    ``generate_with_fallback``. Non-quota errors are re-raised immediately —
    unchanged semantics, just propagated up one layer.

    Raises ``ValueError`` if *api_keys* is empty.
    Raises the last quota exception if every key (and every model under it)
    is exhausted.
    """
    if not api_keys:
        raise ValueError("no Gemini API keys available")

    last_quota_exc: BaseException | None = None
    for key in api_keys:
        try:
            return generate_with_fallback(
                key, prompt, models=models, temperature=temperature
            )
        except Exception as exc:  # noqa: BLE001
            if _is_quota_error(exc):
                logger.warning(
                    "gemini_fallback: all models quota-exhausted on key ...{} "
                    "— trying next key",
                    key[-4:],
                )
                last_quota_exc = exc
                continue
            raise

    assert last_quota_exc is not None
    raise last_quota_exc
