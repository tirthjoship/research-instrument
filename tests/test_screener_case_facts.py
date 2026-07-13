"""TDD tests for application/screener_case_facts.py — pure fact-building logic
shared by the live Screener render path and the CLI --cite-cases prefetch, so a
cache-hit and a cache-miss-live-fallback never disagree on what a candidate's
bands say."""

from __future__ import annotations

from domain.factor_bands import Band


def test_candidate_bands_maps_present_factors() -> None:
    from application.screener_case_facts import candidate_bands

    candidate = {
        "ticker": "NVDA",
        "factor_scores": [
            {"name": "quality", "value": 1.5, "percentile": 0.95},
            {"name": "value", "value": 0.8, "percentile": 0.87},
            {"name": "momentum", "value": 0.22, "percentile": 0.59},
        ],
    }
    bands = candidate_bands(candidate)
    assert bands["quality"] == Band.EXCEPTIONAL
    assert bands["value"] == Band.STRONG
    assert bands["momentum"] == Band.FLAT


def test_candidate_bands_skips_data_gap_shape() -> None:
    from application.screener_case_facts import candidate_bands

    candidate = {
        "ticker": "XYZ",
        "factor_scores": [
            {"name": "lowvol", "value": 0.0, "percentile": 0.0},
            {"name": "quality", "value": 1.0, "percentile": 0.8},
        ],
    }
    bands = candidate_bands(candidate)
    assert "lowvol" not in bands
    assert bands["quality"] == Band.STRONG


def test_candidate_bands_skips_missing_value_or_percentile() -> None:
    from application.screener_case_facts import candidate_bands

    candidate = {
        "ticker": "ABC",
        "factor_scores": [
            {"name": "quality", "value": None, "percentile": None},
            {"name": "value", "value": 0.5},
        ],
    }
    assert candidate_bands(candidate) == {}


def test_facts_from_bands_formats_label_and_percentile() -> None:
    from application.screener_case_facts import facts_from_bands

    bands = {"quality": Band.EXCEPTIONAL}
    factor_by_name = {"quality": {"name": "quality", "percentile": 0.95}}
    facts = facts_from_bands(bands, factor_by_name)
    assert "Quality (ROE/margin)" in facts
    assert facts["Quality (ROE/margin)"] == "Exceptional (p95)"


def test_facts_from_bands_no_percentile_omits_p_notation() -> None:
    from application.screener_case_facts import facts_from_bands

    bands = {"momentum": Band.FLAT}
    facts = facts_from_bands(bands, {})
    assert facts["Momentum (12-1)"] == "Flat"
