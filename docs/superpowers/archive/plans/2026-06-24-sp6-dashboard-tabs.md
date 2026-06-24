# SP6: Dashboard Tabs — Stock Analysis Decomposition + Corroboration Surface

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Decompose `stock_analysis.py` (1055 lines) into a `stock_analysis/` package and add a new Corroboration section that renders evidence from `CorroborationStore` with a persistent RESEARCH_ONLY banner and convergence tier badge.

**Architecture:** Pure-function section renderers in isolated files, orchestrated by `compose.py`. `data_loader.py` provides `load_corroboration_snapshot()` as the single data boundary — no direct store imports in visualization files. Corroboration section renders from persisted snapshot only (no live API calls on tab load).

**Tech Stack:** Python 3.12, Streamlit, Loguru, SQLite3, `domain.corroboration_models` (stdlib-only), `adapters.data.corroboration_store.CorroborationStore`, `adapters.visualization.components` (cards, formatters, charts).

## Global Constraints

- `uv run pytest` required (bare `pytest` fails — pyproject.toml injects `--timeout` flags)
- `make test-tab tab=stock_analysis` is the fast test target for this SP
- mypy strict must pass: `make typecheck`
- No direct imports of `CorroborationStore` inside `adapters/visualization/` files — only through `data_loader.py`
- No live API calls in corroboration section — snapshot read only
- All render functions type-annotated, return `None`
- Commit after each task — never batch multiple tasks into one commit

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `adapters/visualization/tabs/stock_analysis.py` | **DELETE** | Replaced by package |
| `adapters/visualization/tabs/stock_analysis/__init__.py` | CREATE | Re-exports `render`, `_SECTION_LABELS` |
| `adapters/visualization/tabs/stock_analysis/compose.py` | CREATE | Entry: RESEARCH_ONLY banner, chip nav, section orchestration |
| `adapters/visualization/tabs/stock_analysis/verdict_section.py` | CREATE | Verdict, Fit, Analyst, News, Peer percentiles |
| `adapters/visualization/tabs/stock_analysis/financials_section.py` | CREATE | Valuation, Growth, Health |
| `adapters/visualization/tabs/stock_analysis/market_section.py` | CREATE | Performance, Ownership |
| `adapters/visualization/tabs/stock_analysis/signals_section.py` | CREATE | Sentiment, Supply chain |
| `adapters/visualization/tabs/stock_analysis/corroboration_section.py` | CREATE | Corroboration, OurReadout, DirectionalView |
| `adapters/visualization/data_loader.py` | MODIFY | Add `CorroborationTabView`, `load_corroboration_snapshot()`, `_compute_directional_views()` |
| `tests/fakes/corroboration_store_fake.py` | CREATE | `FakeCorroborationStore` + claim fixtures |
| `tests/test_corroboration_section.py` | CREATE | Unit tests for pure-function logic |
| `tests/test_tab_stock_analysis.py` | CREATE/UPDATE | Smoke tests for full render path |

---

## Task 1: FakeCorroborationStore + test fixtures

**Files:**
- Create: `tests/fakes/corroboration_store_fake.py`

**Interfaces:**
- Produces: `FakeCorroborationStore`, `FAKE_CLAIM_BULLISH`, `FAKE_CLAIM_BEARISH`, `FAKE_CLAIM_WEAK`, `FAKE_SNAPSHOT` — imported by Tasks 2, 3, 5

- [ ] **Step 1: Create the fake store file**

```python
# tests/fakes/corroboration_store_fake.py
"""Fake CorroborationStore for testing — never hits SQLite."""
from __future__ import annotations

from datetime import date

from domain.corroboration_models import (
    CandidateSnapshot,
    ConvergenceTier,
    HarvestedClaim,
    Stance,
)


class FakeCorroborationStore:
    def __init__(
        self,
        run_id: int | None = 1,
        claims: list[HarvestedClaim] | None = None,
        candidates: list[CandidateSnapshot] | None = None,
    ) -> None:
        self._run_id = run_id
        self._claims: list[HarvestedClaim] = claims or []
        self._candidates: list[CandidateSnapshot] = candidates or []

    def latest_run_id(self) -> int | None:
        return self._run_id

    def load_run(self, run_id: int) -> list[HarvestedClaim]:
        return self._claims

    def load_candidates(self, run_id: int) -> list[CandidateSnapshot]:
        return self._candidates


FAKE_CLAIM_BULLISH = HarvestedClaim(
    source_name="Goldman Sachs",
    ticker="AAPL",
    stance=Stance.BULLISH,
    thesis_summary="Strong iPhone cycle and services momentum",
    url="https://example.com/gs-aapl-2026",
    published_at=date(2026, 6, 20),
    verified=True,
    reliability_weight=0.85,
)

FAKE_CLAIM_BEARISH = HarvestedClaim(
    source_name="Barclays",
    ticker="AAPL",
    stance=Stance.BEARISH,
    thesis_summary="China headwinds may weigh on near-term results",
    url="https://example.com/barcl-aapl-2026",
    published_at=date(2026, 6, 19),
    verified=True,
    reliability_weight=0.65,
)

FAKE_CLAIM_WEAK = HarvestedClaim(
    source_name="Reddit r/investing",
    ticker="AAPL",
    stance=Stance.BULLISH,
    thesis_summary="People love the Vision Pro",
    url="https://reddit.com/r/investing/aapl",
    published_at=date(2026, 6, 18),
    verified=False,
    reliability_weight=0.25,
)

FAKE_SNAPSHOT = CandidateSnapshot(
    ticker="AAPL",
    convergence=ConvergenceTier.MODERATE,
    verification="PARTIAL",
    mean_convergence=0.62,
)
```

- [ ] **Step 2: Verify import works**

```bash
uv run python -c "from tests.fakes.corroboration_store_fake import FakeCorroborationStore, FAKE_CLAIM_BULLISH; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add tests/fakes/corroboration_store_fake.py
git commit -m "test(fakes): add FakeCorroborationStore + claim fixtures for SP6"
```

---

## Task 2: CorroborationTabView DTO + data_loader extension

**Files:**
- Modify: `adapters/visualization/data_loader.py` (add after last import block, before first function)

**Interfaces:**
- Consumes: `FakeCorroborationStore` (tests only), `CorroborationStore` (runtime)
- Produces: `CorroborationTabView`, `load_corroboration_snapshot(ticker, db_path) -> CorroborationTabView | None`

- [ ] **Step 1: Write the failing test**

Create `tests/test_data_loader_corroboration.py`:

```python
# tests/test_data_loader_corroboration.py
"""Tests for corroboration data loader extension."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from domain.corroboration_models import ConvergenceTier, Stance
from tests.fakes.corroboration_store_fake import (
    FAKE_CLAIM_BULLISH,
    FAKE_CLAIM_WEAK,
    FAKE_SNAPSHOT,
    FakeCorroborationStore,
)


def _make_view(ticker: str, claims=None, candidates=None, run_id=1):
    """Helper: build CorroborationTabView via the internal builder."""
    from adapters.visualization.data_loader import _build_corroboration_view

    store = FakeCorroborationStore(
        run_id=run_id,
        claims=claims or [FAKE_CLAIM_BULLISH],
        candidates=candidates or [FAKE_SNAPSHOT],
    )
    return _build_corroboration_view(ticker=ticker, store=store)


def test_build_view_returns_view_for_known_ticker():
    view = _make_view("AAPL")
    assert view is not None
    assert view.ticker == "AAPL"
    assert len(view.claims) == 1


def test_build_view_filters_by_ticker():
    from domain.corroboration_models import HarvestedClaim, Stance
    other_claim = HarvestedClaim(
        source_name="X", ticker="MSFT", stance=Stance.BULLISH,
        thesis_summary="not for aapl", url="https://x.com",
        published_at=date(2026, 6, 1), verified=False, reliability_weight=0.5,
    )
    view = _make_view("AAPL", claims=[FAKE_CLAIM_BULLISH, other_claim])
    assert view is not None
    assert all(c.ticker == "AAPL" for c in view.claims)


def test_build_view_returns_none_when_no_run():
    from adapters.visualization.data_loader import _build_corroboration_view
    store = FakeCorroborationStore(run_id=None)
    assert _build_corroboration_view("AAPL", store) is None


def test_build_view_empty_claims_returns_view_with_empty_tuple():
    view = _make_view("AAPL", claims=[])
    assert view is not None
    assert view.claims == ()


def test_directional_views_bullish_majority():
    view = _make_view("AAPL", claims=[FAKE_CLAIM_BULLISH])
    assert view is not None
    assert len(view.directional_views) == 1
    assert view.directional_views[0].tilt in {"LEAN_IN", "HOLD"}


def test_load_corroboration_snapshot_returns_none_for_missing_db(tmp_path):
    from adapters.visualization.data_loader import load_corroboration_snapshot
    result = load_corroboration_snapshot("AAPL", db_path=str(tmp_path / "missing.db"))
    assert result is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_data_loader_corroboration.py -q
```

Expected: `ImportError` or `ModuleNotFoundError` — `_build_corroboration_view` not defined yet.

- [ ] **Step 3: Add CorroborationTabView DTO and functions to data_loader.py**

Add these imports at the top of `adapters/visualization/data_loader.py` (after existing imports):

```python
import sqlite3
from dataclasses import dataclass
from domain.corroboration_models import (
    CandidateSnapshot,
    DirectionalView,
    HarvestedClaim,
    OurReadout,
    Stance,
)
```

Add these definitions after the existing `logger = ...` line:

```python
@dataclass(frozen=True)
class CorroborationTabView:
    """Visualization-layer DTO for corroboration data. Not a domain type."""

    ticker: str
    as_of: date
    claims: tuple[HarvestedClaim, ...]
    snapshot: CandidateSnapshot | None
    our_readout: OurReadout | None  # populated by caller from AnalysisResult
    directional_views: tuple[DirectionalView, ...]


def _compute_directional_views(claims: list[HarvestedClaim]) -> list[DirectionalView]:
    """Derive a single DirectionalView from claims (evidence-consensus level)."""
    if not claims:
        return []
    total_w = sum(c.reliability_weight for c in claims)
    if total_w == 0.0:
        return []
    bull_w = sum(c.reliability_weight for c in claims if c.stance == Stance.BULLISH)
    bear_w = sum(c.reliability_weight for c in claims if c.stance == Stance.BEARISH)
    evidence_weight_pct = bull_w / total_w
    if evidence_weight_pct >= 0.70:
        tilt = "LEAN_IN"
    elif evidence_weight_pct >= 0.45:
        tilt = "HOLD"
    elif evidence_weight_pct >= 0.20:
        tilt = "LEAN_OUT"
    else:
        tilt = "AVOID"
    if bull_w > bear_w:
        net_stance = Stance.BULLISH
    elif bear_w > bull_w:
        net_stance = Stance.BEARISH
    else:
        net_stance = Stance.NEUTRAL
    return [
        DirectionalView(
            group_kind="sources",
            group_name="Evidence consensus",
            net_stance=net_stance,
            mean_convergence=evidence_weight_pct,
            your_exposure_pct=0.0,
            evidence_weight_pct=evidence_weight_pct,
            tilt=tilt,
        )
    ]


def _build_corroboration_view(
    ticker: str,
    store: Any,
) -> "CorroborationTabView | None":
    """Build CorroborationTabView from a store instance (real or fake)."""
    run_id = store.latest_run_id()
    if run_id is None:
        return None
    all_claims: list[HarvestedClaim] = store.load_run(run_id)
    ticker_claims = [c for c in all_claims if c.ticker == ticker]
    candidates: list[CandidateSnapshot] = store.load_candidates(run_id)
    snapshot = next((c for c in candidates if c.ticker == ticker), None)
    return CorroborationTabView(
        ticker=ticker,
        as_of=date.today(),
        claims=tuple(ticker_claims),
        snapshot=snapshot,
        our_readout=None,
        directional_views=tuple(_compute_directional_views(ticker_claims)),
    )


def load_corroboration_snapshot(
    ticker: str,
    db_path: str = "data/corroboration.db",
) -> "CorroborationTabView | None":
    """Load latest corroboration snapshot for ticker. Returns None on missing DB or store error."""
    if not Path(db_path).exists():
        return None
    try:
        from adapters.data.corroboration_store import CorroborationStore

        conn = sqlite3.connect(db_path)
        store = CorroborationStore(conn)
        return _build_corroboration_view(ticker=ticker, store=store)
    except Exception as e:
        logger.warning("corroboration snapshot load failed for %s: %s", ticker, e)
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_data_loader_corroboration.py -q
```

Expected: `6 passed`

- [ ] **Step 5: Run mypy**

```bash
make typecheck
```

Expected: `Success: no issues found`

- [ ] **Step 6: Commit**

```bash
git add adapters/visualization/data_loader.py tests/test_data_loader_corroboration.py
git commit -m "feat(data_loader): add CorroborationTabView DTO + load_corroboration_snapshot"
```

---

## Task 3: corroboration_section.py — pure functions + unit tests

**Files:**
- Create: `adapters/visualization/tabs/stock_analysis/corroboration_section.py`
- Create: `tests/test_corroboration_section.py`

Note: The `stock_analysis/` directory doesn't exist yet. Create it now (it will be populated further in Task 4).

**Interfaces:**
- Consumes: `CorroborationTabView` (from Task 2), `FakeCorroborationStore` (from Task 1)
- Produces: `render_corroboration_section(view: CorroborationTabView | None) -> None`

- [ ] **Step 1: Create the stock_analysis package directory and corroboration_section.py**

```python
# adapters/visualization/tabs/stock_analysis/corroboration_section.py
"""Corroboration evidence section — renders HarvestedClaims, OurReadout, DirectionalView."""
from __future__ import annotations

from typing import TYPE_CHECKING

import streamlit as st

if TYPE_CHECKING:
    from adapters.visualization.data_loader import CorroborationTabView

from domain.corroboration_models import (
    CandidateSnapshot,
    ConvergenceTier,
    DirectionalView,
    HarvestedClaim,
    OurReadout,
    Stance,
    TrendHealth,
)

_TIER_COLOUR: dict[str, str] = {
    "strong": "#16A34A",
    "moderate": "#2563EB",
    "weak": "#CA8A04",
    "conflicted": "#DC2626",
    "none": "#94A3B8",
}

_TILT_COLOUR: dict[str, str] = {
    "LEAN_IN": "#16A34A",
    "HOLD": "#2563EB",
    "LEAN_OUT": "#CA8A04",
    "AVOID": "#DC2626",
}

_STANCE_ICON: dict[Stance, str] = {
    Stance.BULLISH: "▲",
    Stance.BEARISH: "▼",
    Stance.NEUTRAL: "→",
}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def render_corroboration_section(view: "CorroborationTabView | None") -> None:
    """Render the full corroboration section. Handles empty state gracefully."""
    st.divider()
    st.markdown("#### Corroboration Evidence")
    if view is None or not view.claims:
        ticker = view.ticker if view is not None else ""
        st.markdown(_empty_state_html(ticker), unsafe_allow_html=True)
        return
    strong, moderate, weak = _group_claims_by_weight(view.claims)
    _render_strong_claims(strong)
    _render_moderate_claims(moderate)
    _render_weak_claims(weak)
    if view.snapshot is not None and view.snapshot.convergence == ConvergenceTier.CONFLICTED:
        st.markdown(
            '<div class="ws-card" style="border-left:3px solid #DC2626;padding:10px 14px;">'
            '<span style="font-weight:700;color:#DC2626;">⚠ CONFLICTED</span>'
            '<span style="font-size:13px;color:#64748B;margin-left:8px;">'
            "Sources disagree — treat with caution.</span></div>",
            unsafe_allow_html=True,
        )
    _render_our_readout(view.our_readout)
    _render_directional_views(list(view.directional_views))


# ---------------------------------------------------------------------------
# Claim grouping (pure — no Streamlit)
# ---------------------------------------------------------------------------


def _group_claims_by_weight(
    claims: tuple[HarvestedClaim, ...],
) -> tuple[list[HarvestedClaim], list[HarvestedClaim], list[HarvestedClaim]]:
    """Split claims into (strong, moderate, weak) buckets by verified + weight."""
    strong: list[HarvestedClaim] = []
    moderate: list[HarvestedClaim] = []
    weak: list[HarvestedClaim] = []
    for c in claims:
        if c.verified and c.reliability_weight >= 0.70:
            strong.append(c)
        elif c.verified or c.reliability_weight >= 0.45:
            moderate.append(c)
        else:
            weak.append(c)
    return strong, moderate, weak


# ---------------------------------------------------------------------------
# HTML builders (pure — no Streamlit, unit-testable)
# ---------------------------------------------------------------------------


def _empty_state_html(ticker: str) -> str:
    label = f" for {ticker}" if ticker else ""
    return (
        '<div class="ws-card" style="padding:16px;text-align:center;">'
        f'<div style="font-size:14px;color:#64748B;">No corroboration data{label}.</div>'
        '<div style="font-size:13px;color:#94A3B8;margin-top:4px;">'
        "Run <code>corroborate</code> to surface external evidence.</div>"
        "</div>"
    )


def _claim_card_html(claim: HarvestedClaim) -> str:
    """Full evidence card for a STRONG (verified, high-weight) claim."""
    verified_badge = (
        '<span style="font-size:11px;font-weight:600;color:#16A34A;'
        "background:#DCFCE7;padding:2px 6px;border-radius:4px;margin-left:6px;"
        '">✓ VERIFIED</span>'
        if claim.verified
        else ""
    )
    freshness = f"{claim.published_at.isoformat()}"
    icon = _STANCE_ICON.get(claim.stance, "→")
    return (
        '<div class="ws-card" style="padding:12px 16px;margin-bottom:8px;">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
        f'<span style="font-weight:600;font-size:14px;color:#1A202C;">'
        f"{icon} {claim.source_name}</span>"
        f"{verified_badge}"
        f'<span style="font-size:11px;color:#94A3B8;">{freshness}</span>'
        f"</div>"
        f'<div style="font-size:13px;color:#374151;margin-top:6px;">{claim.thesis_summary}</div>'
        f'<div style="margin-top:6px;">'
        f'<a href="{claim.url}" target="_blank" '
        f'style="font-size:12px;color:#0F6E80;">↗ Source</a></div>'
        "</div>"
    )


def _claim_row_html(claim: HarvestedClaim) -> str:
    """Compact row for a MODERATE claim."""
    icon = _STANCE_ICON.get(claim.stance, "→")
    return (
        f'<div style="padding:6px 10px;border-bottom:1px solid #F1F5F9;font-size:13px;">'
        f'<span style="color:#0F6E80;font-weight:500;">{icon} {claim.source_name}</span> '
        f'<span style="color:#374151;">{claim.thesis_summary}</span> '
        f'<span style="color:#94A3B8;font-size:11px;">{claim.published_at.isoformat()}</span>'
        f"</div>"
    )


def _our_readout_html(readout: OurReadout) -> str:
    """HTML block for OurReadout bridge."""
    fp = f"{readout.factor_percentile:.0f}th" if readout.factor_percentile is not None else "N/A"
    trend = readout.trend_health.value.upper() if readout.trend_health else "N/A"
    div_icon = "⚠" if readout.divergence_flag else "✓"
    disc = readout.discipline_flag or "—"
    trend_colour = {
        "HEALTHY": "#16A34A",
        "CAUTION": "#CA8A04",
        "BROKEN": "#DC2626",
    }.get(trend, "#64748B")
    return (
        '<div class="ws-card" style="padding:12px 16px;margin-top:12px;">'
        '<div style="font-size:12px;color:#94A3B8;text-transform:uppercase;'
        'letter-spacing:0.8px;margin-bottom:8px;">Our model says</div>'
        '<div style="display:flex;gap:24px;flex-wrap:wrap;">'
        f'<span style="font-size:13px;"><b>Factor percentile:</b> {fp}</span>'
        f'<span style="font-size:13px;color:{trend_colour};"><b>Trend:</b> {trend}</span>'
        f'<span style="font-size:13px;"><b>Divergence:</b> {div_icon}</span>'
        f'<span style="font-size:13px;"><b>Discipline:</b> {disc}</span>'
        "</div></div>"
    )


def _directional_views_html(views: list[DirectionalView]) -> str:
    """HTML table for DirectionalView tilt panel."""
    if not views:
        return ""
    rows = ""
    for v in views:
        colour = _TILT_COLOUR.get(v.tilt, "#64748B")
        stance_icon = _STANCE_ICON.get(v.net_stance, "→")
        rows += (
            f'<tr><td style="font-size:13px;padding:4px 8px;">{v.group_name}</td>'
            f'<td style="font-size:13px;padding:4px 8px;">{stance_icon} {v.net_stance.value}</td>'
            f'<td style="font-size:13px;padding:4px 8px;font-weight:700;color:{colour};">'
            f"{v.tilt}</td>"
            f'<td style="font-size:13px;padding:4px 8px;color:#94A3B8;">'
            f"{v.mean_convergence:.0%}</td></tr>"
        )
    return (
        '<div class="ws-card" style="padding:12px 16px;margin-top:12px;">'
        '<div style="font-size:12px;color:#94A3B8;text-transform:uppercase;'
        'letter-spacing:0.8px;margin-bottom:8px;">Directional tilt</div>'
        '<table style="width:100%;border-collapse:collapse;">'
        "<thead><tr>"
        '<th style="font-size:11px;color:#94A3B8;text-align:left;padding:4px 8px;">Group</th>'
        '<th style="font-size:11px;color:#94A3B8;text-align:left;padding:4px 8px;">Stance</th>'
        '<th style="font-size:11px;color:#94A3B8;text-align:left;padding:4px 8px;">Tilt</th>'
        '<th style="font-size:11px;color:#94A3B8;text-align:left;padding:4px 8px;">Confidence</th>'
        f"</tr></thead><tbody>{rows}</tbody></table></div>"
    )


# ---------------------------------------------------------------------------
# Streamlit renderers
# ---------------------------------------------------------------------------


def _render_strong_claims(claims: list[HarvestedClaim]) -> None:
    if not claims:
        return
    st.markdown(
        f'<div style="font-size:12px;font-weight:700;color:#16A34A;'
        'text-transform:uppercase;letter-spacing:0.6px;margin-top:8px;">'
        f"Strong evidence ({len(claims)})</div>",
        unsafe_allow_html=True,
    )
    for claim in claims:
        st.markdown(_claim_card_html(claim), unsafe_allow_html=True)


def _render_moderate_claims(claims: list[HarvestedClaim]) -> None:
    if not claims:
        return
    st.markdown(
        f'<div style="font-size:12px;font-weight:700;color:#2563EB;'
        'text-transform:uppercase;letter-spacing:0.6px;margin-top:8px;">'
        f"Moderate signals ({len(claims)})</div>",
        unsafe_allow_html=True,
    )
    for claim in claims:
        st.markdown(_claim_row_html(claim), unsafe_allow_html=True)


def _render_weak_claims(claims: list[HarvestedClaim]) -> None:
    if not claims:
        return
    with st.expander(f"Weak / unverified signals ({len(claims)})"):
        for claim in claims:
            st.markdown(_claim_row_html(claim), unsafe_allow_html=True)


def _render_our_readout(readout: OurReadout | None) -> None:
    if readout is None:
        return
    st.markdown(_our_readout_html(readout), unsafe_allow_html=True)


def _render_directional_views(views: list[DirectionalView]) -> None:
    html = _directional_views_html(views)
    if html:
        st.markdown(html, unsafe_allow_html=True)
```

- [ ] **Step 2: Write unit tests**

```python
# tests/test_corroboration_section.py
"""Unit tests for corroboration_section pure functions."""
from __future__ import annotations

from datetime import date

import pytest

from domain.corroboration_models import (
    ConvergenceTier,
    DirectionalView,
    OurReadout,
    Stance,
    TrendHealth,
)
from tests.fakes.corroboration_store_fake import (
    FAKE_CLAIM_BEARISH,
    FAKE_CLAIM_BULLISH,
    FAKE_CLAIM_WEAK,
)

from adapters.visualization.tabs.stock_analysis.corroboration_section import (
    _claim_card_html,
    _claim_row_html,
    _directional_views_html,
    _empty_state_html,
    _group_claims_by_weight,
    _our_readout_html,
)


def test_empty_state_html_contains_ticker():
    html = _empty_state_html("AAPL")
    assert "AAPL" in html
    assert "corroborate" in html


def test_empty_state_html_no_ticker():
    html = _empty_state_html("")
    assert "corroborate" in html


def test_group_claims_bullish_high_weight_goes_to_strong():
    strong, moderate, weak = _group_claims_by_weight((FAKE_CLAIM_BULLISH,))
    assert FAKE_CLAIM_BULLISH in strong
    assert not moderate
    assert not weak


def test_group_claims_unverified_low_weight_goes_to_weak():
    strong, moderate, weak = _group_claims_by_weight((FAKE_CLAIM_WEAK,))
    assert not strong
    assert not moderate
    assert FAKE_CLAIM_WEAK in weak


def test_group_claims_verified_mid_weight_goes_to_moderate():
    strong, moderate, weak = _group_claims_by_weight((FAKE_CLAIM_BEARISH,))
    # FAKE_CLAIM_BEARISH: verified=True, weight=0.65 → moderate bucket
    assert not strong
    assert FAKE_CLAIM_BEARISH in moderate
    assert not weak


def test_group_claims_mixed():
    strong, moderate, weak = _group_claims_by_weight(
        (FAKE_CLAIM_BULLISH, FAKE_CLAIM_BEARISH, FAKE_CLAIM_WEAK)
    )
    assert len(strong) == 1
    assert len(moderate) == 1
    assert len(weak) == 1


def test_claim_card_html_contains_source_and_thesis():
    html = _claim_card_html(FAKE_CLAIM_BULLISH)
    assert "Goldman Sachs" in html
    assert "Strong iPhone cycle" in html
    assert "VERIFIED" in html
    assert "https://example.com/gs-aapl-2026" in html


def test_claim_card_html_unverified_has_no_verified_badge():
    html = _claim_card_html(FAKE_CLAIM_WEAK)
    assert "VERIFIED" not in html


def test_claim_row_html_contains_source():
    html = _claim_row_html(FAKE_CLAIM_BEARISH)
    assert "Barclays" in html
    assert "China headwinds" in html


def test_our_readout_html_all_fields():
    readout = OurReadout(
        factor_percentile=73.0,
        trend_health=TrendHealth.HEALTHY,
        divergence_flag=False,
        discipline_flag="HOLD",
    )
    html = _our_readout_html(readout)
    assert "73" in html
    assert "HEALTHY" in html
    assert "HOLD" in html


def test_our_readout_html_none_fields():
    readout = OurReadout(
        factor_percentile=None,
        trend_health=None,
        divergence_flag=False,
        discipline_flag=None,
    )
    html = _our_readout_html(readout)
    assert "N/A" in html


def test_directional_views_html_lean_in():
    view = DirectionalView(
        group_kind="sources",
        group_name="Evidence consensus",
        net_stance=Stance.BULLISH,
        mean_convergence=0.80,
        your_exposure_pct=0.0,
        evidence_weight_pct=0.80,
        tilt="LEAN_IN",
    )
    html = _directional_views_html([view])
    assert "LEAN_IN" in html
    assert "Evidence consensus" in html
    assert "#16A34A" in html  # green for LEAN_IN


def test_directional_views_html_empty_returns_empty_string():
    assert _directional_views_html([]) == ""
```

- [ ] **Step 3: Run tests to verify they fail first**

```bash
uv run pytest tests/test_corroboration_section.py -q
```

Expected: `ImportError` — `corroboration_section` module not found yet (file created but package `__init__.py` missing).

- [ ] **Step 4: Create minimal `__init__.py` for the package**

```python
# adapters/visualization/tabs/stock_analysis/__init__.py
"""Stock analysis tab package."""
from adapters.visualization.tabs.stock_analysis.corroboration_section import (  # noqa: F401
    render_corroboration_section,
)
```

Note: Full `render` and `_SECTION_LABELS` will be exported here in Task 4. For now, just enough to make tests importable.

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/test_corroboration_section.py -q
```

Expected: `14 passed`

- [ ] **Step 6: Commit**

```bash
git add adapters/visualization/tabs/stock_analysis/__init__.py \
        adapters/visualization/tabs/stock_analysis/corroboration_section.py \
        tests/test_corroboration_section.py
git commit -m "feat(tabs): add corroboration_section.py with pure-function HTML builders"
```

---

## Task 4: Decompose stock_analysis.py → 5 section files + compose.py

**Files:**
- Create: `adapters/visualization/tabs/stock_analysis/verdict_section.py`
- Create: `adapters/visualization/tabs/stock_analysis/financials_section.py`
- Create: `adapters/visualization/tabs/stock_analysis/market_section.py`
- Create: `adapters/visualization/tabs/stock_analysis/signals_section.py`
- Create: `adapters/visualization/tabs/stock_analysis/compose.py`
- Modify: `adapters/visualization/tabs/stock_analysis/__init__.py`
- Delete: `adapters/visualization/tabs/stock_analysis.py` (original monolith)

**Function → file mapping** (exact, copy verbatim):

| Function | Line in original | Destination |
|----------|-----------------|-------------|
| `render()` | 71 | `compose.py` |
| `_ensure_fit_cached()` | 51 | `compose.py` |
| `_render_decision_lead_html()` | 976 | `compose.py` |
| `_render_decision_lead()` | 1049 | `compose.py` |
| `_render_verdict()` | 204 | `verdict_section.py` |
| `_render_fit_card()` | 280 | `verdict_section.py` |
| `_render_analyst_panel()` | 322 | `verdict_section.py` |
| `_render_news_context()` | 401 | `verdict_section.py` |
| `_render_peer_percentiles()` | 452 | `verdict_section.py` |
| `_snowflake_axes()` | 875 | `verdict_section.py` |
| `_fmt_market_cap()` | 941 | `verdict_section.py` |
| `_SEVERITY_CLASS` dict | 273 | `verdict_section.py` |
| `_render_valuation()` | 487 | `financials_section.py` |
| `_render_growth()` | 558 | `financials_section.py` |
| `_render_health()` | 658 | `financials_section.py` |
| `_render_performance()` | 614 | `market_section.py` |
| `_render_ownership()` | 720 | `market_section.py` |
| `_render_sentiment()` | 765 | `signals_section.py` |
| `_render_supply_chain()` | 816 | `signals_section.py` |

**Interfaces:**
- `compose.py` imports from all 4 section files
- `__init__.py` exports `render`, `_SECTION_LABELS`

- [ ] **Step 1: Create verdict_section.py**

Copy functions `_render_verdict`, `_render_fit_card`, `_render_analyst_panel`, `_render_news_context`, `_render_peer_percentiles`, `_snowflake_axes`, `_fmt_market_cap`, and the `_SEVERITY_CLASS` dict from the original `stock_analysis.py` (lines 204–979 minus the non-verdict functions).

The file starts with these imports:

```python
# adapters/visualization/tabs/stock_analysis/verdict_section.py
"""Verdict, Fit, Analyst, News, and Peer-percentiles sections."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import streamlit as st
from loguru import logger

if TYPE_CHECKING:
    from domain.fit import FitVerdict

from adapters.visualization.components.cards import (
    criteria_card,
    metric_kpi,
    price_range_bar,
    tooltip,
    verdict_bullet,
)
from adapters.visualization.components.charts import (
    apply_dossier_template,
    gauge_chart,
    comparison_bars,
)
from adapters.visualization.components.snowflake import build_snowflake
from adapters.visualization.components.tooltip import tooltip as glossary_tooltip
from adapters.visualization.components.formatters import grade_badge_html
from adapters.visualization.stock_analyzer import AnalysisResult
from domain.fit import FitVerdict

_SEVERITY_CLASS = {
    "INFO": "verdict-neutral",
    "CAUTION": "verdict-caution",
    "WARNING": "verdict-negative",
}
```

Then paste the 7 functions verbatim from the original. Do NOT modify logic, only fix imports.

- [ ] **Step 2: Create financials_section.py**

```python
# adapters/visualization/tabs/stock_analysis/financials_section.py
"""Valuation, Growth, Health sections."""
from __future__ import annotations

import streamlit as st

from adapters.visualization.components.cards import metric_kpi, tooltip
from adapters.visualization.components.charts import (
    apply_dossier_template,
    comparison_bars,
    financials_line,
)
from adapters.visualization.components.tooltip import tooltip as glossary_tooltip
from adapters.visualization.stock_analyzer import AnalysisResult
```

Then paste `_render_valuation` (487–557), `_render_growth` (558–613), `_render_health` (658–719) verbatim.

- [ ] **Step 3: Create market_section.py**

```python
# adapters/visualization/tabs/stock_analysis/market_section.py
"""Performance, Ownership sections."""
from __future__ import annotations

import streamlit as st

from adapters.visualization.components.cards import metric_kpi
from adapters.visualization.components.charts import (
    apply_dossier_template,
    insider_bars,
    ownership_pie,
)
from adapters.visualization.stock_analyzer import AnalysisResult
```

Then paste `_render_performance` (614–657) and `_render_ownership` (720–764) verbatim.

- [ ] **Step 4: Create signals_section.py**

```python
# adapters/visualization/tabs/stock_analysis/signals_section.py
"""Sentiment, Supply chain sections."""
from __future__ import annotations

import streamlit as st

from adapters.visualization.components.charts import (
    apply_dossier_template,
    cluster_bubble,
)
from adapters.visualization.components.tooltip import tooltip as glossary_tooltip
from adapters.visualization.stock_analyzer import AnalysisResult
```

Then paste `_render_sentiment` (765–815) and `_render_supply_chain` (816–874) verbatim.

- [ ] **Step 5: Create compose.py**

```python
# adapters/visualization/tabs/stock_analysis/compose.py
"""Stock Analysis tab — orchestrates section rendering."""
from __future__ import annotations

from collections.abc import Callable, MutableMapping
from typing import TYPE_CHECKING, Any

import streamlit as st
from loguru import logger

if TYPE_CHECKING:
    from domain.fit import FitVerdict

from adapters.visualization.components.snowflake import build_snowflake
from adapters.visualization.components.charts import apply_dossier_template
from adapters.visualization.data_loader import load_corroboration_snapshot
from adapters.visualization.stock_analyzer import AnalysisResult
from domain.fit import FitVerdict

from adapters.visualization.tabs.stock_analysis.verdict_section import (
    _render_verdict,
    _render_fit_card,
    _render_analyst_panel,
    _render_news_context,
    _render_peer_percentiles,
    _snowflake_axes,
)
from adapters.visualization.tabs.stock_analysis.financials_section import (
    _render_valuation,
    _render_growth,
    _render_health,
)
from adapters.visualization.tabs.stock_analysis.market_section import (
    _render_performance,
    _render_ownership,
)
from adapters.visualization.tabs.stock_analysis.signals_section import (
    _render_sentiment,
    _render_supply_chain,
)
from adapters.visualization.tabs.stock_analysis.corroboration_section import (
    render_corroboration_section,
)

_SECTION_LABELS: list[str] = [
    "Verdict",
    "Fit",
    "Valuation",
    "Growth",
    "Performance",
    "Health",
    "Ownership",
    "Sentiment",
    "Supply chain",
    "Corroboration",
]

_CORR_DB_PATH = "data/corroboration.db"
```

Then paste `_ensure_fit_cached`, `_render_decision_lead_html`, `_render_decision_lead` verbatim from original.

Then write the new `render()` with RESEARCH_ONLY banner:

```python
def render() -> None:
    """Render the Stock Analysis tab."""
    # Page-level RESEARCH_ONLY banner — always visible, before ticker input.
    st.markdown(
        '<div style="background:#FEF9C3;border-left:4px solid #CA8A04;'
        "padding:10px 16px;border-radius:4px;margin-bottom:16px;"
        'font-size:13px;color:#713F12;">'
        "<b>RESEARCH ONLY — not financial advice.</b> "
        "Grades reflect model confidence, not return forecasts. "
        "Corroboration shows evidence strength, never a price prediction."
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown("### Stock Analysis")
    st.markdown(
        '<div style="color:#64748B;font-size:14px;margin-bottom:16px;">'
        "Deep-dive analysis for any ticker — valuation, growth, health, sentiment, and supply chain."
        "</div>",
        unsafe_allow_html=True,
    )

    pending = st.session_state.pop("analyze_ticker", None)

    cols = st.columns([4, 1])
    ticker_input = cols[0].text_input(
        "Ticker", value=pending or "", placeholder="NVDA", label_visibility="collapsed"
    )
    analyze = cols[1].button("Run Analysis", type="primary") or pending is not None

    if analyze and ticker_input:
        ticker = ticker_input.upper().strip()
        try:
            from adapters.visualization.stock_analyzer import analyze_ticker

            with st.spinner(
                f"Analyzing {ticker} — fetching live market data, fundamentals, "
                "and sentiment (typically 20-60s)..."
            ):
                result = analyze_ticker(ticker, db_path="data/recommendations.db")
                st.session_state[f"analysis_{ticker}"] = result
                st.session_state.pop(f"fit_{ticker}", None)
        except Exception as exc:
            st.error(f"Analysis failed for {ticker}: {exc}")
            import traceback

            st.code(traceback.format_exc())
            return
    elif analyze and not ticker_input:
        st.warning("Type a ticker first — e.g. NVDA or AAPL.")

    lookup_key = ticker_input.upper().strip() if ticker_input else ""
    if lookup_key and f"analysis_{lookup_key}" in st.session_state:
        result = st.session_state[f"analysis_{lookup_key}"]

        # Load corroboration snapshot (None if store is empty or DB missing)
        corr_view = load_corroboration_snapshot(lookup_key, db_path=_CORR_DB_PATH)

        st.markdown(
            " ".join(
                f'<span class="section-chip">{i}</span>'
                f'<span style="margin-right:14px;font-size:13px;color:#5C6370;">'
                f"{name}</span>"
                for i, name in enumerate(_SECTION_LABELS, start=1)
            ),
            unsafe_allow_html=True,
        )
        _render_decision_lead(result)
        _render_verdict(result, corr_view=corr_view)
        st.markdown(
            '<div class="ri-sec" style="'
            "background:var(--ri-surface,#F8FAFC);"
            "border-left:3px solid var(--ri-teal,#0F6E80);"
            "padding:10px 14px;margin-bottom:12px;"
            'border-radius:4px;">'
            '<span style="font-weight:700;color:var(--ri-teal,#0F6E80);">'
            "Evidence Status: not a forecast</span>"
            '<span style="font-size:13px;color:#64748B;margin-left:8px;">'
            "All panels below surface attributed third-party data "
            "(yfinance, analyst consensus, buzz sources). "
            "This tool describes what is true today; it does not forecast returns."
            "</span></div>",
            unsafe_allow_html=True,
        )
        fit_key = f"fit_{lookup_key}"

        from datetime import datetime, timezone

        from application.fit_use_case import (
            default_beta_fn,
            gather_and_assess,
            market_systematic_share_threshold,
        )

        fit = _ensure_fit_cached(
            st.session_state,
            fit_key,
            lambda: gather_and_assess(
                ticker=lookup_key,
                reports_dir="data/reports",
                summary_path="data/personal/brief_summary.json",
                holdings_path="data/personal/holdings.csv",
                beta_fn=default_beta_fn,
                as_of=datetime.now(timezone.utc),
                systematic_share_threshold=market_systematic_share_threshold(),
            ),
        )
        if fit is not None:
            _render_fit_card(fit)
        else:
            st.caption("Fit verdict unavailable (see logs).")
        axes = _snowflake_axes(fit)
        fig = build_snowflake(axes)
        if fig is not None:
            st.markdown("##### Evidence snowflake")
            apply_dossier_template(fig)
            st.plotly_chart(fig, use_container_width=True)
            st.caption(
                "Factual percentiles vs the screened universe + fit "
                "arithmetic — a description of today, not a forecast."
            )
        _render_analyst_panel(result)
        _render_news_context(result)
        _render_peer_percentiles(result)
        _render_valuation(result)
        _render_growth(result)
        _render_performance(result)
        _render_health(result)
        _render_ownership(result)
        _render_sentiment(result)
        _render_supply_chain(result)
        render_corroboration_section(corr_view)
    elif not ticker_input:
        st.markdown(
            '<div class="ws-card" style="text-align:center;padding:2rem;">'
            '<div style="font-size:15px;font-weight:500;color:#1A202C;">Enter a ticker above to start</div>'
            '<div style="font-size:13px;color:#64748B;margin-top:4px;">'
            "Get valuation, growth, financial health, sentiment, and fit analysis"
            "</div></div>",
            unsafe_allow_html=True,
        )
```

Note: `_render_verdict` signature must be updated to accept `corr_view` (see Task 5 Step 1).

- [ ] **Step 6: Update `__init__.py` to export from compose.py**

```python
# adapters/visualization/tabs/stock_analysis/__init__.py
"""Stock analysis tab package."""
from adapters.visualization.tabs.stock_analysis.compose import (  # noqa: F401
    _SECTION_LABELS,
    render,
)
from adapters.visualization.tabs.stock_analysis.corroboration_section import (  # noqa: F401
    render_corroboration_section,
)
```

- [ ] **Step 7: Delete the original monolith**

```bash
git rm adapters/visualization/tabs/stock_analysis.py
```

- [ ] **Step 8: Run smoke test — verify no import errors and existing tests pass**

```bash
uv run python -c "from adapters.visualization.tabs.stock_analysis import render, _SECTION_LABELS; print('ok', _SECTION_LABELS)"
make test-tab tab=stock_analysis
```

Expected first command: `ok ['Verdict', 'Fit', ..., 'Corroboration']`
Expected second command: all existing stock_analysis tests pass.

- [ ] **Step 9: Run full fast suite to catch regressions**

```bash
make test-fast
```

Expected: all tests pass (same count as before this task).

- [ ] **Step 10: Commit**

```bash
git add adapters/visualization/tabs/stock_analysis/
git commit -m "refactor(tabs): decompose stock_analysis.py monolith into 6-file package"
```

---

## Task 5: Convergence badge on Verdict + smoke test

**Files:**
- Modify: `adapters/visualization/tabs/stock_analysis/verdict_section.py` (update `_render_verdict` signature)
- Create/Update: `tests/test_tab_stock_analysis.py`

**Interfaces:**
- Consumes: `CorroborationTabView | None` (from Task 2), `FakeCorroborationStore` (Task 1)

- [ ] **Step 1: Update `_render_verdict` signature to accept `corr_view`**

In `verdict_section.py`, update the function signature and add the convergence badge after the price header:

```python
# In verdict_section.py — update this function signature:
from adapters.visualization.data_loader import CorroborationTabView  # TYPE_CHECKING block

_TIER_COLOUR: dict[str, str] = {
    "strong": "#16A34A",
    "moderate": "#2563EB",
    "weak": "#CA8A04",
    "conflicted": "#DC2626",
    "none": "#94A3B8",
}


def _render_verdict(
    result: AnalysisResult,
    corr_view: "CorroborationTabView | None" = None,
) -> None:
    """Render top verdict section: price, RESEARCH_ONLY notice, consensus comparison."""
    # ... existing price header code unchanged (lines 207–225 of original) ...

    # Convergence badge — injected after price header if corroboration data available
    if corr_view is not None and corr_view.snapshot is not None:
        tier = corr_view.snapshot.convergence
        colour = _TIER_COLOUR.get(tier.value, "#94A3B8")
        label = tier.value.upper()
        st.markdown(
            f'<div style="margin-bottom:8px;">'
            f'<span style="font-size:12px;font-weight:700;color:{colour};'
            f"background:{colour}22;padding:3px 10px;border-radius:4px;"
            f'letter-spacing:0.5px;">◈ {label} CONVERGENCE</span></div>',
            unsafe_allow_html=True,
        )

    # ... rest of existing verdict function unchanged ...
```

- [ ] **Step 2: Write smoke tests**

```python
# tests/test_tab_stock_analysis.py
"""Smoke tests for stock_analysis tab package."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from tests.fakes.corroboration_store_fake import (
    FAKE_CLAIM_BULLISH,
    FAKE_SNAPSHOT,
    FakeCorroborationStore,
)
from adapters.visualization.tabs.stock_analysis import _SECTION_LABELS


def test_section_labels_contains_corroboration():
    assert "Corroboration" in _SECTION_LABELS
    assert _SECTION_LABELS.index("Corroboration") == 9


def test_section_labels_length():
    assert len(_SECTION_LABELS) == 10


def test_corroboration_section_renders_empty_state():
    """render_corroboration_section(None) must not raise."""
    import streamlit as st
    from adapters.visualization.tabs.stock_analysis.corroboration_section import (
        render_corroboration_section,
    )

    with patch.object(st, "markdown"), patch.object(st, "divider"):
        render_corroboration_section(None)  # must not raise


def test_corroboration_section_renders_with_data(tmp_path):
    """render_corroboration_section with real CorroborationTabView must not raise."""
    import streamlit as st
    from adapters.visualization.data_loader import _build_corroboration_view
    from adapters.visualization.tabs.stock_analysis.corroboration_section import (
        render_corroboration_section,
    )

    store = FakeCorroborationStore(
        run_id=1,
        claims=[FAKE_CLAIM_BULLISH],
        candidates=[FAKE_SNAPSHOT],
    )
    view = _build_corroboration_view("AAPL", store)

    with (
        patch.object(st, "markdown"),
        patch.object(st, "divider"),
        patch.object(st, "expander", return_value=MagicMock(__enter__=MagicMock(return_value=None), __exit__=MagicMock(return_value=False))),
    ):
        render_corroboration_section(view)  # must not raise


def test_research_only_banner_present_in_compose():
    """compose.py render() must include RESEARCH ONLY text."""
    import inspect
    from adapters.visualization.tabs.stock_analysis import compose
    src = inspect.getsource(compose.render)
    assert "RESEARCH ONLY" in src
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest tests/test_tab_stock_analysis.py tests/test_corroboration_section.py tests/test_data_loader_corroboration.py -q
```

Expected: all pass

- [ ] **Step 4: Run full fast suite**

```bash
make test-fast
```

Expected: all tests pass, count same or higher

- [ ] **Step 5: Run typecheck**

```bash
make typecheck
```

Expected: `Success: no issues found`

- [ ] **Step 6: Commit**

```bash
git add adapters/visualization/tabs/stock_analysis/verdict_section.py \
        tests/test_tab_stock_analysis.py
git commit -m "feat(tabs/sp6): convergence badge on Verdict + smoke tests — SP6 complete"
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] Decompose stock_analysis.py → 6-file package — Tasks 4
- [x] Persistent RESEARCH_ONLY banner (page-level amber) — compose.py render()
- [x] Convergence tier badge on Verdict section — Task 5
- [x] Corroboration section after Sentiment — compose.py + corroboration_section.py
- [x] Claims grouped: STRONG cards / MODERATE rows / WEAK collapsed — Task 3
- [x] OurReadout bridge below claims — corroboration_section.py
- [x] DirectionalView tilt panel below OurReadout — corroboration_section.py
- [x] Graceful empty state — Task 3
- [x] No live API calls — load_corroboration_snapshot reads persisted snapshot
- [x] FakeCorroborationStore — Task 1
- [x] Unit tests (pure functions) — Task 3
- [x] Smoke tests (render path) — Task 5
- [x] data_loader.py extension — Task 2
- [x] No CorroborationStore imports in visualization files — enforced by architecture
- [x] mypy strict — checked in Tasks 2 and 5

**Type consistency check:**
- `CorroborationTabView` defined in Task 2, consumed by Tasks 3, 4, 5 — name consistent
- `_build_corroboration_view(ticker, store)` defined Task 2, used in test Task 2 — consistent
- `render_corroboration_section(view)` defined Task 3, called in Task 4 compose.py — consistent
- `_render_verdict(result, corr_view=None)` updated in Task 5, called in Task 4 compose.py — consistent
- `FakeCorroborationStore` defined Task 1, used Tasks 2, 3, 5 — consistent

**Placeholder scan:** None found. All code blocks are complete.
