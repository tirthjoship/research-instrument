"""Methodology tab — how this project keeps itself honest. Static content."""

from __future__ import annotations

import streamlit as st

_BODY = """
### Why this page exists
Six tabs make claims about your money. This page is the reason you can believe them. Everything this app shows survives four rules — and everything that broke those rules was deleted.

### How this project keeps itself honest

**Pre-registration.** Before running any test we write down the exact pass/fail
thresholds and lock them. If the result misses the bar, the idea dies — no
"just tweak it and re-run."

_Example: the insider-cluster test's pass/fail numbers were locked on June 9, 2026 — the verdict was read against them on June 10, unchanged._

**Point-in-time discipline.** Every prediction may only use data that existed at
that moment. Using tomorrow's data to "predict" today is the most common way
backtests lie; our code raises `LookAheadBiasError` if it ever happens.

_Example: our code raises `LookAheadBiasError` and halts rather than let tomorrow's price leak into today's signal._

**Costs included.** A signal that looks profitable before trading costs and
disappears after them is not an edge. We model the real cost of trading thin
stocks (slippage) and test net of it.

_Example: the insider-cluster edge looked real gross of costs — and died when 150 bps of real-world trading cost was applied._

**Abstention over bravado.** When the evidence doesn't clear the bar, the tool
says "no candidates" instead of guessing. Zero is an honest answer.

_Example: on June 11, 2026 the screen looked at 512 names and ranked zero. That empty list is the feature._

### Glossary (plain English)

| Term | Meaning | Where you'll see it |
|------|---------|---------------------|
| **Confidence interval (CI)** | The range the true average plausibly sits in. "CI low > 0" = even the pessimistic read is a profit. | Falsification Lab verdicts |
| **Slippage** | The hidden cost of actually buying a thinly-traded stock — you move the price against yourself. | Falsification Lab (cost-included tests) |
| **Tercile** | Split into thirds. "Bottom liquidity tercile" = the third of stocks that are hardest to trade. | Falsification Lab (insider-cluster test) |
| **Abnormal return** | A stock's return minus what a comparable index did over the same days — the part the stock did "on its own." | Falsification Lab event studies |
| **IC (information coefficient)** | Correlation between a signal's ranking and what actually happened next. Zero = the signal knows nothing. | Falsification Lab (sentiment + screen tests) |
| **Sharpe ratio** | Return earned per unit of risk taken. Higher is better — it rewards steady gains, not lucky volatile ones. | Falsification Lab (momentum-exit test) |
| **Bootstrap** | Re-running a test on thousands of resampled versions of the data to see how much of the result is just luck. A confidence interval that "spans zero" means the edge could easily be nothing. | Falsification Lab (momentum-exit test) |
| **Pre-registration** | Locking the test rules before seeing results, so you can't move the goalposts. | Everywhere — it is the house rule |
| **Look-ahead bias** | Accidentally letting future data leak into a prediction — makes backtests look great and live trading fail. | Enforced in code, invisible by design |
"""


def render() -> None:
    st.subheader("Methodology")
    st.markdown(
        '<div style="color:#64748B;font-size:14px;margin-bottom:16px;">'
        "The four rules that keep this app honest, and the words it uses."
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown(_BODY)
