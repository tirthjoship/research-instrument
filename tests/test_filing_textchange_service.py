"""Tests for the pure Lazy-Prices text-change signal service."""

from __future__ import annotations

from domain.filing_textchange_service import (
    cosine_similarity,
    jaccard_similarity,
    textchange_similarity,
    tokenize,
)


def test_tokenize_keeps_alpha_words_drops_numbers_and_short_tokens() -> None:
    assert tokenize("The Company's 2023 revenue grew!") == [
        "the",
        "company",
        "revenue",
        "grew",
    ]


def test_cosine_identical_text_is_one() -> None:
    text = "risk factors include supply chain disruption and litigation exposure"
    assert cosine_similarity(text, text) == 1.0


def test_cosine_disjoint_text_is_zero() -> None:
    assert cosine_similarity("alpha beta gamma", "delta epsilon zeta") == 0.0


def test_cosine_partial_overlap_between_zero_and_one() -> None:
    sim = cosine_similarity(
        "supply chain risk litigation exposure",
        "supply chain risk and new currency exposure",
    )
    assert 0.0 < sim < 1.0


def test_cosine_empty_returns_zero_not_error() -> None:
    assert cosine_similarity("", "anything here") == 0.0


def test_jaccard_identical_is_one_disjoint_is_zero() -> None:
    assert jaccard_similarity("a bb ccc", "a bb ccc") == 1.0
    assert jaccard_similarity("aaa bbb", "ccc ddd") == 0.0


def test_textchange_non_changer_scores_high() -> None:
    """A filing nearly identical to its prior comparable = high similarity (non-changer)."""
    prior = {
        "management": "operations were stable and margins held across all segments",
        "risk_factors": "we face competition and regulatory risk in key markets",
    }
    current = {
        "management": "operations were stable and margins held across all segments",
        "risk_factors": "we face competition and regulatory risk in key markets today",
    }
    score = textchange_similarity(current, prior)
    assert score is not None
    assert score > 0.8


def test_textchange_changer_scores_low() -> None:
    """A materially rewritten filing = low similarity (changer)."""
    prior = {
        "management": "operations were stable and margins held across all segments",
        "risk_factors": "we face competition and regulatory risk in key markets",
    }
    current = {
        "management": "we initiated restructuring litigation and impaired goodwill heavily",
        "risk_factors": "going concern doubt liquidity covenant breach bankruptcy possible",
    }
    score = textchange_similarity(current, prior)
    assert score is not None
    assert score < 0.3


def test_textchange_missing_section_pair_returns_none_not_zero() -> None:
    """No section present in BOTH filings -> MISSING (None), never imputed to 0.0."""
    assert (
        textchange_similarity({"management": "text here"}, {"risk_factors": "other"})
        is None
    )
    assert textchange_similarity({}, {}) is None
