"""Filing text-change signal ("Lazy Prices"). Pure, stdlib-only.

Hypothesis (Cohen, Malloy & Nguyen, J. Finance 2020): firms that materially CHANGE
the language of a periodic filing (10-K / 10-Q) vs the prior comparable filing
subsequently UNDER-perform; firms that leave the language largely unchanged
("non-changers") out-perform. The market is inattentive to these slow-moving
textual signals, so returns accrue over months — NOT days.

Signal convention here: ``textchange_similarity`` is HIGH for non-changers and LOW
for changers, so it is monotonically POSITIVE with expected forward return (a higher
signal predicts a higher forward return). This matches the cross-sectional rank-IC
harness, where a positive IC is the survival condition.

Pure domain code: stdlib only (no numpy, no sklearn). Tokenisation is deliberately
simple and deterministic so the same filing pair always yields the same similarity.
"""

from __future__ import annotations

import math
import re
from collections import Counter

# Sections the paper found most informative; an adapter may pass only these.
INFORMATIVE_SECTIONS = ("management", "litigation", "risk_factors")

_TOKEN_RE = re.compile(r"[a-z]{3,}")  # 3+ letter lowercase tokens; drops numbers/punct


def tokenize(text: str) -> list[str]:
    """Lowercase, keep 3+ letter alphabetic tokens. Deterministic, stdlib-only."""
    return _TOKEN_RE.findall(text.lower())


def _term_freq(tokens: list[str]) -> Counter[str]:
    return Counter(tokens)


def cosine_similarity(text_a: str, text_b: str) -> float:
    """Bag-of-words cosine similarity in [0, 1]. 1.0 = identical token distribution.

    Empty-vs-anything returns 0.0 (no information — treated as missing upstream,
    never imputed, to respect the no-look-ahead / no-fill discipline).
    """
    tf_a = _term_freq(tokenize(text_a))
    tf_b = _term_freq(tokenize(text_b))
    if not tf_a or not tf_b:
        return 0.0
    common = set(tf_a) & set(tf_b)
    dot = sum(tf_a[t] * tf_b[t] for t in common)
    norm_a = math.sqrt(sum(v * v for v in tf_a.values()))
    norm_b = math.sqrt(sum(v * v for v in tf_b.values()))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def jaccard_similarity(text_a: str, text_b: str) -> float:
    """Token-set Jaccard in [0, 1]. Robustness cross-check on cosine."""
    set_a = set(tokenize(text_a))
    set_b = set(tokenize(text_b))
    if not set_a or not set_b:
        return 0.0
    inter = len(set_a & set_b)
    union = len(set_a | set_b)
    return inter / union if union else 0.0


def textchange_similarity(
    current_sections: dict[str, str],
    prior_sections: dict[str, str],
    sections: tuple[str, ...] = INFORMATIVE_SECTIONS,
) -> float | None:
    """Mean cosine similarity across *sections* between a filing and its prior comparable.

    HIGH = non-changer (predicted out-performance); LOW = changer (under-performance).

    Returns ``None`` (MISSING, not 0.0) when no requested section has text in BOTH
    filings — the harness must drop the event, never impute. A real but tiny overlap
    still yields a number; absence yields None so coverage accounting stays honest.
    """
    sims: list[float] = []
    for name in sections:
        cur = current_sections.get(name, "")
        pri = prior_sections.get(name, "")
        if cur and pri:
            sims.append(cosine_similarity(cur, pri))
    if not sims:
        return None
    return sum(sims) / len(sims)
