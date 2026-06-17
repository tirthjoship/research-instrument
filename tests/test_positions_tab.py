"""Tests for My Portfolio tab — decision-card row rendering (Task 9).

The Holding domain model carries: symbol, quantity, purchase_price, purchase_date, notes.
Unrealized % is COMPUTED from live price vs purchase_price.
Verdict and why text are SOURCED from brief_summary.json.
There are NO 5-signal RAG arrays on the Holding model — that is an honest DATA-GAP.

Test harness pattern mirrors test_weekly_brief_tab.py / test_risk_tab.py:
  - patch st.markdown to capture rendered HTML
  - assert structural invariants without starting Streamlit
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Glossary — new terms used in decision-card rows must be registered
# ---------------------------------------------------------------------------


def test_glossary_has_position_verdict_terms() -> None:
    """Verdict-framing terms used in position cards must be in the glossary."""
    from adapters.visualization.components.glossary import GLOSSARY

    assert "Trim flag" in GLOSSARY, "'Trim flag' must be registered in glossary"
    assert "Reduce flag" in GLOSSARY, "'Reduce flag' must be registered in glossary"
    assert "Hold flag" in GLOSSARY, "'Hold flag' must be registered in glossary"
