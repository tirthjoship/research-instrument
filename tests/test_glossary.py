"""Task 1: Glossary entries for the screener redesign (S3)."""

from __future__ import annotations

import pytest


@pytest.mark.parametrize(
    "term",
    [
        "Evidence score",
        "Percentile",
        "Low-vol factor",
        "Analyst dispersion",
        "Trend gate",
        "Reason bucket",
    ],
)
def test_new_glossary_terms_present(term: str) -> None:
    from adapters.visualization.components import glossary as g

    assert term in g.GLOSSARY and len(g.GLOSSARY[term]) > 10
