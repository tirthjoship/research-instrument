"""Methodology tab — how this project keeps itself honest. Static content."""

from __future__ import annotations

import streamlit as st

_BODY = """
### How this project keeps itself honest

**Pre-registration.** Before running any test we write down the exact pass/fail
thresholds and lock them. If the result misses the bar, the idea dies — no
"just tweak it and re-run."

**Point-in-time discipline.** Every prediction may only use data that existed at
that moment. Using tomorrow's data to "predict" today is the most common way
backtests lie; our code raises `LookAheadBiasError` if it ever happens.

**Costs included.** A signal that looks profitable before trading costs and
disappears after them is not an edge. We model the real cost of trading thin
stocks (slippage) and test net of it.

**Abstention over bravado.** When the evidence doesn't clear the bar, the tool
says "no candidates" instead of guessing. Zero is an honest answer.

### Glossary (plain English)

| Term | Meaning |
|------|---------|
| **Confidence interval (CI)** | The range the true average plausibly sits in. "CI low > 0" = even the pessimistic read is a profit. |
| **Slippage** | The hidden cost of actually buying a thinly-traded stock — you move the price against yourself. |
| **Tercile** | Split into thirds. "Bottom liquidity tercile" = the third of stocks that are hardest to trade. |
| **Abnormal return** | A stock's return minus what a comparable index did over the same days — the part the stock did "on its own." |
| **IC (information coefficient)** | Correlation between a signal's ranking and what actually happened next. Zero = the signal knows nothing. |
| **Pre-registration** | Locking the test rules before seeing results, so you can't move the goalposts. |
| **Look-ahead bias** | Accidentally letting future data leak into a prediction — makes backtests look great and live trading fail. |
"""


def render() -> None:
    st.subheader("Methodology")
    st.markdown(_BODY)
