from adapters.visualization.components import glossary as g
from domain.fit import FORBIDDEN_WORDS

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
