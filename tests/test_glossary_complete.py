from adapters.visualization.components import glossary as g
from domain.fit import FORBIDDEN_WORDS

NEW_RISK_TERMS = [
    "Effective bets",
    "Adjusted R²",
    "Bootstrap band",
    "Downside beta",
    "Risk contribution",
    "VIF",
    "Diversification ratio",
    "HHI",
    "GICS sector",
    "Drift",
    "Risk line",
    "Coverage",
    "Systematic share",
    "Net beta",
    "Concentration",
]

REQUIRED = {
    "Net beta",
    "Universe",
    "Cleared the bar",
    "Abstention",
    "Directional accuracy",
    "Rank-IC",
    "Evidence screen",
    "Trend filter",
    "Concentrated risk",
    "Reduce flag",
    "Trim flag",
    "Hold flag",
    "Add-on flag",
    "Book health",
    "Momentum factor",
    "Revision factor",
    "Quality factor",
    "Value factor",
    "Industry percentile",
    "Analyst consensus",
    "Dispersion",
    "Portfolio fit",
}


def test_required_terms_present():
    missing = REQUIRED - set(g.GLOSSARY)
    assert not missing, f"glossary missing: {missing}"


def test_glossary_definitions_have_no_forbidden_words():
    for term, definition in g.GLOSSARY.items():
        low = definition.lower()
        for w in FORBIDDEN_WORDS:
            assert w not in low, f"'{w}' in glossary[{term}]"


def test_new_risk_terms_present() -> None:
    for term in NEW_RISK_TERMS:
        assert (
            term in g.GLOSSARY and g.GLOSSARY[term]
        ), f"glossary missing or empty: {term!r}"


def test_new_terms_have_no_forbidden_words() -> None:
    for term in NEW_RISK_TERMS:
        text = g.GLOSSARY[term].lower()
        for w in FORBIDDEN_WORDS:
            assert w not in text, f"'{w}' found in glossary[{term!r}]"


def test_band_and_grade_terms_present() -> None:
    """Screener pipeline-visual tooltips (Band/Grade boxes) need these entries."""
    assert "Band" in g.GLOSSARY
    band = g.GLOSSARY["Band"]
    for token in ("Exceptional", "Strong", "Flat", "Weak", "p95", "5%", "304"):
        assert token in band, f"glossary['Band'] missing token: {token!r}"

    assert "Grade" in g.GLOSSARY
    grade = g.GLOSSARY["Grade"]
    for token in ("Evidence score", "STRONG", "MODERATE", "Low-vol now live"):
        assert token in grade, f"glossary['Grade'] missing token: {token!r}"
