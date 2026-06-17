# tests/test_portfolio_glossary.py
from adapters.visualization.components.glossary import GLOSSARY


def test_portfolio_terms_present():
    for term in (
        "Concentration (top 5)",
        "Needs review",
        "Treemap colour",
        "Beta",
        "Dividend yield",
        "Alpha vs SPY",
    ):
        assert term in GLOSSARY, f"missing glossary term: {term}"
        assert len(GLOSSARY[term]) > 20
