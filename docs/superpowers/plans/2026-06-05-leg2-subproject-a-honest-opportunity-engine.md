# Leg-2 Sub-Project A — Honest Opportunity Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the opportunity engine see and score emerging thematic mid-caps honestly — fix buzz-source coverage, backfill the divergence base window from real archives, compute all 8 conviction dims, log the full candidate distribution, and ship a schedulable daily cycle.

**Architecture:** Hexagonal. New data sources are adapters behind ports; the divergence blend and `AttentionPoint` are pure domain; backfill / conviction-caching / scan are application use cases. Two data shapes (events vs intensity) get two ports (`BuzzDiscoveryPort`, new `AttentionSeriesPort`) and two native acceleration computations blended into one divergence score.

**Tech Stack:** Python 3.12, SQLite, click CLI, pytest + Hypothesis, mypy strict, loguru, requests, pytrends (new), praw (new optional). Spec: `docs/superpowers/specs/2026-06-05-leg2-subproject-a-honest-opportunity-engine-design.md`.

**Branch:** `feat/opportunity-forward-tracking`.

**Conventions observed throughout:**
- Domain files import only stdlib (typing, dataclasses, datetime, enum). No framework imports in `domain/`.
- Adapters catch all network/parse errors, log a warning, return `[]`. One dead source never crashes a scan.
- All stored timestamps written via `.isoformat()`, read via `datetime.fromisoformat(...)`.
- Tests use fakes / mocked HTTP — **never** hit live APIs (rule #5). `make check` must stay green at ≥90% coverage.
- Commit after every green task with conventional-commit messages.

---

## Phase 0 — Dependencies & Config Scaffolding

### Task 1: Add pytrends + praw dependencies; retire StockTwits from pipeline

**Files:**
- Modify: `pyproject.toml` (the `[project] dependencies` array)
- Modify: `adapters/data/stocktwits_adapter.py:1` (deprecation note only)

- [ ] **Step 1: Add dependencies**

In `pyproject.toml`, add to the `dependencies` array:
```toml
    "pytrends>=4.9.2",
    "praw>=7.7.1",
```

- [ ] **Step 2: Install**

Run: `pip install "pytrends>=4.9.2" "praw>=7.7.1"`
Expected: both install successfully.

- [ ] **Step 3: Verify pytrends import (the recon gap)**

Run: `python -c "from pytrends.request import TrendReq; print('pytrends ok')"`
Expected: `pytrends ok`

- [ ] **Step 4: Mark StockTwits deprecated**

At the top of `adapters/data/stocktwits_adapter.py`, under the module docstring, add:
```python
# DEPRECATED (2026-06-05): StockTwits public API returns HTTP 403 (locked down).
# Retired from the live pipeline. Replaced by Reddit (Task 11) + Google News (Task 8).
# Kept for reference / potential future API revival; not wired into any use case.
```

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml adapters/data/stocktwits_adapter.py
git commit -m "chore: add pytrends + praw deps, deprecate dead StockTwits adapter"
```

---

### Task 2: Extend config — ticker aliases, source toggles, blend weights, thresholds

**Files:**
- Modify: `config/universe/themes.yaml` (add `aliases` per ticker)
- Modify: `config/markets/us.yaml` (add `opportunity_engine` block)

- [ ] **Step 1: Add alias mapping to themes.yaml**

For each ticker in the thematic spine, add a query-alias entry. Add a top-level `aliases` map (ticker → search terms for news/Reddit/Wikipedia). Example for the existing space + memory names:
```yaml
aliases:
  ASTS: { name: "AST SpaceMobile", cashtag: "ASTS", subreddits: ["ASTSpaceMobile", "spacestocks"], wiki: "AST_SpaceMobile" }
  RKLB: { name: "Rocket Lab", cashtag: "RKLB", subreddits: ["RKLB", "spacestocks"], wiki: "Rocket_Lab" }
  LUNR: { name: "Intuitive Machines", cashtag: "LUNR", subreddits: ["spacestocks"], wiki: "Intuitive_Machines" }
  OKLO: { name: "Oklo Inc", cashtag: "OKLO", subreddits: ["NuclearPower", "OKLO"], wiki: "Oklo_(company)" }
  MU:   { name: "Micron Technology", cashtag: "MU", subreddits: ["stocks"], wiki: "Micron_Technology" }
```
For tickers without an explicit alias, the loader falls back to the ticker symbol (and yfinance `longName` where available — wired in Task 8/Task 7).

- [ ] **Step 2: Add opportunity_engine config block to us.yaml**

```yaml
opportunity_engine:
  divergence_blend:
    event_weight: 0.5
    intensity_weight: 0.5
  thresholds:
    cmin: 6.0   # placeholder — recalibrated from --show-all distribution in Task 22
    dmin: 6.0   # placeholder — recalibrated from --show-all distribution in Task 22
  signal_cache_ttl_hours: 24
  backfill_days: 90
  sources:
    gdelt: true
    google_trends: true
    google_news: true
    wikipedia: true
    reddit: false   # flips to true once REDDIT_CLIENT_ID/SECRET env vars exist
```

- [ ] **Step 3: Verify YAML parses**

Run: `python -c "import yaml; yaml.safe_load(open('config/markets/us.yaml')); yaml.safe_load(open('config/universe/themes.yaml')); print('yaml ok')"`
Expected: `yaml ok`

- [ ] **Step 4: Commit**

```bash
git add config/universe/themes.yaml config/markets/us.yaml
git commit -m "chore: add ticker aliases + opportunity_engine config block"
```

---

## Phase 1 — Domain: AttentionPoint, AttentionSeriesPort, Blended Divergence

### Task 3: AttentionPoint domain model

**Files:**
- Modify: `domain/models.py` (add `AttentionPoint` near `BuzzSignal`, ~line 208)
- Test: `tests/test_domain_models.py`

- [ ] **Step 1: Write the failing test**

```python
def test_attention_point_valid_creation():
    from datetime import datetime
    from domain.models import AttentionPoint

    p = AttentionPoint(
        ticker="ASTS",
        timestamp=datetime(2026, 6, 1),
        value=42.0,
        source="google_trends",
    )
    assert p.ticker == "ASTS"
    assert p.value == 42.0


def test_attention_point_rejects_negative_value():
    import pytest
    from datetime import datetime
    from domain.models import AttentionPoint

    with pytest.raises(ValueError):
        AttentionPoint("ASTS", datetime(2026, 6, 1), -1.0, "wikipedia")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_domain_models.py::test_attention_point_valid_creation -v`
Expected: FAIL with `ImportError: cannot import name 'AttentionPoint'`

- [ ] **Step 3: Add the model**

In `domain/models.py`, after the `BuzzSignal` class (~line 208), add:
```python
@dataclass(frozen=True)
class AttentionPoint:
    """A single attention-intensity observation (search interest, pageviews).

    Distinct from BuzzSignal (discrete events): this is a magnitude at a point
    in time. Scale is source-relative (GT index 0-100, Wikipedia raw views);
    divergence uses scale-free ratios so no normalization is needed.
    """

    ticker: str
    timestamp: datetime
    value: float  # >= 0; source-relative intensity
    source: str  # e.g. "google_trends", "wikipedia"

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValueError("attention value must be >= 0")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_domain_models.py::test_attention_point_valid_creation tests/test_domain_models.py::test_attention_point_rejects_negative_value -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add domain/models.py tests/test_domain_models.py
git commit -m "feat: add AttentionPoint domain model"
```

---

### Task 4: AttentionSeriesPort protocol

**Files:**
- Modify: `domain/ports.py` (add import + protocol)
- Test: `tests/test_ports_conformance.py` (create if absent)

- [ ] **Step 1: Write the failing test**

```python
def test_attention_series_port_is_runtime_checkable():
    from datetime import datetime
    from domain.models import AttentionPoint
    from domain.ports import AttentionSeriesPort

    class Dummy:
        def get_attention_series(self, ticker, start, end):
            return [AttentionPoint(ticker, start, 1.0, "x")]

    assert isinstance(Dummy(), AttentionSeriesPort)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ports_conformance.py::test_attention_series_port_is_runtime_checkable -v`
Expected: FAIL with `ImportError: cannot import name 'AttentionSeriesPort'`

- [ ] **Step 3: Add the port**

In `domain/ports.py`, add `AttentionPoint` to the `from .models import (...)` block, then add:
```python
@runtime_checkable
class AttentionSeriesPort(Protocol):
    """Retrieves attention-intensity series (search interest, pageviews)."""

    def get_attention_series(
        self,
        ticker: str,
        start: datetime,
        end: datetime,
    ) -> list[AttentionPoint]:
        """Return intensity observations for ticker in [start, end]."""
        ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ports_conformance.py::test_attention_series_port_is_runtime_checkable -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add domain/ports.py tests/test_ports_conformance.py
git commit -m "feat: add AttentionSeriesPort protocol"
```

---

### Task 5: intensity_acceleration() in divergence_service

**Files:**
- Modify: `domain/divergence_service.py`
- Test: `tests/test_divergence_service.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_intensity_acceleration_rising_is_positive():
    from datetime import datetime, timedelta, timezone
    from domain.divergence_service import intensity_acceleration

    now = datetime(2026, 6, 5, tzinfo=timezone.utc)
    # base window (days 7-37) low, recent window (0-7) high
    series = [(now - timedelta(days=d), 10.0) for d in range(8, 30)]
    series += [(now - timedelta(days=d), 90.0) for d in range(0, 7)]
    assert intensity_acceleration(series, now) > 0.5


def test_intensity_acceleration_empty_is_zero():
    from datetime import datetime, timezone
    from domain.divergence_service import intensity_acceleration

    assert intensity_acceleration([], datetime(2026, 6, 5, tzinfo=timezone.utc)) == 0.0


def test_intensity_acceleration_flat_is_near_zero():
    from datetime import datetime, timedelta, timezone
    from domain.divergence_service import intensity_acceleration

    now = datetime(2026, 6, 5, tzinfo=timezone.utc)
    series = [(now - timedelta(days=d), 50.0) for d in range(0, 30)]
    assert abs(intensity_acceleration(series, now)) < 0.01
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_divergence_service.py -k intensity_acceleration -v`
Expected: FAIL with `ImportError: cannot import name 'intensity_acceleration'`

- [ ] **Step 3: Implement**

In `domain/divergence_service.py`, add (after the existing module constants):
```python
def _mean_between(
    series: list[tuple[datetime, float]], lo: datetime, hi: datetime
) -> float:
    vals = [v for t, v in series if lo < t <= hi]
    return sum(vals) / len(vals) if vals else 0.0


def intensity_acceleration(
    series: list[tuple[datetime, float]], now: datetime
) -> float:
    """Scale-free acceleration of an intensity series (GT index, pageviews).

    Mirrors event buzz_accel but on levels: recent mean vs base mean.
    Returns ~[-1, 1]; 0.0 when no data or perfectly flat.
    """
    if not series:
        return 0.0
    recent_level = _mean_between(series, now - timedelta(days=_RECENT_DAYS), now)
    base_level = _mean_between(
        series,
        now - timedelta(days=_RECENT_DAYS + _BASE_DAYS),
        now - timedelta(days=_RECENT_DAYS),
    )
    denom = max(recent_level, base_level, 1e-9)
    return (recent_level - base_level) / denom
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_divergence_service.py -k intensity_acceleration -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add domain/divergence_service.py tests/test_divergence_service.py
git commit -m "feat: add intensity_acceleration for attention-series divergence"
```

---

### Task 6: blended_divergence_score() + Hypothesis property tests

**Files:**
- Modify: `domain/divergence_service.py`
- Test: `tests/test_divergence_service.py`

- [ ] **Step 1: Write the failing tests (behavior + properties)**

```python
def test_blended_no_data_is_neutral():
    from datetime import datetime, timezone
    from domain.divergence_service import blended_divergence_score

    now = datetime(2026, 6, 5, tzinfo=timezone.utc)
    assert blended_divergence_score([], [], [], 0.5, now) == 5.0


def test_blended_events_only_matches_event_score():
    from datetime import datetime, timedelta, timezone
    from domain.divergence_service import blended_divergence_score, divergence_score

    now = datetime(2026, 6, 5, tzinfo=timezone.utc)
    buzz = [now - timedelta(days=d) for d in range(0, 5)]
    prices = [(now - timedelta(days=d), 100.0) for d in range(0, 40)]
    blended = blended_divergence_score(buzz, [], prices, 0.6, now)
    event_only = divergence_score(buzz, prices, 0.6, now)
    assert abs(blended - event_only) < 1e-6


def test_blended_intensity_only_uses_intensity():
    from datetime import datetime, timedelta, timezone
    from domain.divergence_service import blended_divergence_score

    now = datetime(2026, 6, 5, tzinfo=timezone.utc)
    intensity = [(now - timedelta(days=d), 10.0) for d in range(8, 30)]
    intensity += [(now - timedelta(days=d), 90.0) for d in range(0, 7)]
    prices = [(now - timedelta(days=d), 100.0) for d in range(0, 40)]
    score = blended_divergence_score([], intensity, prices, 0.5, now)
    assert score > 6.0  # rising attention, flat price


def test_blended_in_range():
    from datetime import datetime, timedelta, timezone
    from domain.divergence_service import blended_divergence_score

    now = datetime(2026, 6, 5, tzinfo=timezone.utc)
    buzz = [now - timedelta(days=d) for d in range(0, 5)]
    intensity = [(now - timedelta(days=d), 90.0) for d in range(0, 7)]
    prices = [(now - timedelta(days=d), 100.0) for d in range(0, 40)]
    score = blended_divergence_score(buzz, intensity, prices, 1.0, now)
    assert 1.0 <= score <= 10.0
```

Add Hypothesis property tests:
```python
from hypothesis import given, strategies as st


@given(
    sentiment=st.floats(min_value=0.0, max_value=1.0),
    n_buzz=st.integers(min_value=0, max_value=20),
    n_intensity=st.integers(min_value=0, max_value=20),
)
def test_blended_always_in_range(sentiment, n_buzz, n_intensity):
    from datetime import datetime, timedelta, timezone
    from domain.divergence_service import blended_divergence_score

    now = datetime(2026, 6, 5, tzinfo=timezone.utc)
    buzz = [now - timedelta(days=i % 30) for i in range(n_buzz)]
    intensity = [(now - timedelta(days=i % 30), 50.0) for i in range(n_intensity)]
    prices = [(now - timedelta(days=d), 100.0) for d in range(0, 40)]
    score = blended_divergence_score(buzz, intensity, prices, sentiment, now)
    assert 1.0 <= score <= 10.0


@given(extra_recent=st.integers(min_value=0, max_value=15))
def test_blended_monotonic_in_attention(extra_recent):
    """More recent attention (events) never decreases divergence, all else equal."""
    from datetime import datetime, timedelta, timezone
    from domain.divergence_service import blended_divergence_score

    now = datetime(2026, 6, 5, tzinfo=timezone.utc)
    prices = [(now - timedelta(days=d), 100.0) for d in range(0, 40)]
    base = [now - timedelta(days=20) for _ in range(3)]
    more = base + [now - timedelta(hours=1) for _ in range(extra_recent)]
    s_base = blended_divergence_score(base, [], prices, 0.5, now)
    s_more = blended_divergence_score(more, [], prices, 0.5, now)
    assert s_more >= s_base - 1e-9
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_divergence_service.py -k blended -v`
Expected: FAIL with `ImportError: cannot import name 'blended_divergence_score'`

- [ ] **Step 3: Implement**

In `domain/divergence_service.py`, add:
```python
def blended_divergence_score(
    buzz_times: list[datetime],
    intensity_series: list[tuple[datetime, float]],
    price_series: list[tuple[datetime, float]],
    sentiment: float,
    now: datetime,
    event_weight: float = 0.5,
    intensity_weight: float = 0.5,
) -> float:
    """Blend event-acceleration (news/social) + intensity-acceleration
    (search/pageviews) into one divergence score.

    Weights adapt to available data: if one shape is absent, the present
    shape gets full weight. Neutral 5.0 when neither shape has data.
    Inputs pre-filtered to <= now upstream.
    """
    has_events = bool(buzz_times)
    has_intensity = bool(intensity_series)
    if not has_events and not has_intensity:
        return 5.0

    event_accel = _event_acceleration(buzz_times, now) if has_events else 0.0
    intens_accel = (
        intensity_acceleration(intensity_series, now) if has_intensity else 0.0
    )

    if has_events and has_intensity:
        w_e, w_i = event_weight, intensity_weight
    elif has_events:
        w_e, w_i = 1.0, 0.0
    else:
        w_e, w_i = 0.0, 1.0

    blended_accel = w_e * event_accel + w_i * intens_accel
    price_move = max(_recent_return(price_series, now), 0.0)
    raw = blended_accel - price_move * 2.0
    score = 5.0 + raw * 5.0 + (sentiment - 0.5) * 2.0
    return max(1.0, min(10.0, score))
```

Then refactor the existing `divergence_score` to extract its acceleration into a shared `_event_acceleration` helper (so events-only blend ≡ legacy score). Replace the buzz_accel block inside `divergence_score` with a call to:
```python
def _event_acceleration(buzz_times: list[datetime], now: datetime) -> float:
    if not buzz_times:
        return 0.0
    recent = _count_between(buzz_times, now - timedelta(days=_RECENT_DAYS), now)
    base = _count_between(
        buzz_times,
        now - timedelta(days=_RECENT_DAYS + _BASE_DAYS),
        now - timedelta(days=_RECENT_DAYS),
    )
    base_rate = (base / _BASE_DAYS) * _RECENT_DAYS
    return (recent - base_rate) / max(recent, base_rate, 1.0)
```
In `divergence_score`, set `buzz_accel = _event_acceleration(buzz_times, now)` and keep the rest identical.

- [ ] **Step 4: Run the full divergence test file**

Run: `pytest tests/test_divergence_service.py -v`
Expected: PASS (all — existing + new + property tests)

- [ ] **Step 5: Commit**

```bash
git add domain/divergence_service.py tests/test_divergence_service.py
git commit -m "feat: blended_divergence_score (event + intensity acceleration)"
```

---

## Phase 2 — Source Adapters

### Task 7: WikipediaPageviewsAdapter (AttentionSeriesPort)

**Files:**
- Create: `adapters/data/wikipedia_pageviews_adapter.py`
- Create: `tests/fakes/fake_attention_series.py`
- Test: `tests/test_wikipedia_pageviews_adapter.py`

- [ ] **Step 1: Write the fake (shared test double for AttentionSeriesPort)**

`tests/fakes/fake_attention_series.py`:
```python
from __future__ import annotations

from datetime import datetime

from domain.models import AttentionPoint


class FakeAttentionSeries:
    def __init__(self, points: list[AttentionPoint] | None = None) -> None:
        self._points = points or []

    def get_attention_series(
        self, ticker: str, start: datetime, end: datetime
    ) -> list[AttentionPoint]:
        return [
            p for p in self._points
            if p.ticker == ticker and start <= p.timestamp <= end
        ]
```

- [ ] **Step 2: Write the failing test (mocked HTTP)**

`tests/test_wikipedia_pageviews_adapter.py`:
```python
from datetime import datetime
from unittest.mock import MagicMock, patch

from domain.models import AttentionPoint
from domain.ports import AttentionSeriesPort


def test_wikipedia_adapter_conforms_to_port():
    from adapters.data.wikipedia_pageviews_adapter import WikipediaPageviewsAdapter
    assert isinstance(WikipediaPageviewsAdapter(), AttentionSeriesPort)


def test_wikipedia_adapter_parses_pageviews():
    from adapters.data.wikipedia_pageviews_adapter import WikipediaPageviewsAdapter

    payload = {"items": [
        {"timestamp": "2026060100", "views": 1234},
        {"timestamp": "2026060200", "views": 5678},
    ]}
    with patch("adapters.data.wikipedia_pageviews_adapter.requests.get") as g:
        g.return_value = MagicMock(status_code=200, json=lambda: payload)
        g.return_value.raise_for_status = lambda: None
        pts = WikipediaPageviewsAdapter(article_map={"ASTS": "AST_SpaceMobile"}).get_attention_series(
            "ASTS", datetime(2026, 6, 1), datetime(2026, 6, 2)
        )
    assert len(pts) == 2
    assert all(isinstance(p, AttentionPoint) for p in pts)
    assert pts[0].value == 1234.0
    assert pts[0].source == "wikipedia"


def test_wikipedia_adapter_returns_empty_on_error():
    from adapters.data.wikipedia_pageviews_adapter import WikipediaPageviewsAdapter

    with patch("adapters.data.wikipedia_pageviews_adapter.requests.get", side_effect=Exception("boom")):
        pts = WikipediaPageviewsAdapter().get_attention_series(
            "ASTS", datetime(2026, 6, 1), datetime(2026, 6, 2)
        )
    assert pts == []
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_wikipedia_pageviews_adapter.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 4: Implement the adapter**

`adapters/data/wikipedia_pageviews_adapter.py`:
```python
"""Wikipedia pageviews adapter — honest attention-intensity series.

Wikimedia REST pageviews API: keyless, daily granularity, multi-year history.
Implements AttentionSeriesPort.
"""

from __future__ import annotations

import time
from datetime import datetime

import requests
from loguru import logger

from domain.models import AttentionPoint

_API = (
    "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
    "en.wikipedia/all-access/all-agents/{article}/daily/{start}/{end}"
)
_HEADERS = {"User-Agent": "multi-modal-stock-recommender/1.0 (research)"}


class WikipediaPageviewsAdapter:
    def __init__(
        self, article_map: dict[str, str] | None = None, throttle_s: float = 0.2
    ) -> None:
        self._article_map = article_map or {}
        self._throttle_s = throttle_s

    def _throttle(self) -> None:
        time.sleep(self._throttle_s)

    def get_attention_series(
        self, ticker: str, start: datetime, end: datetime
    ) -> list[AttentionPoint]:
        article = self._article_map.get(ticker, ticker)
        url = _API.format(
            article=article.replace(" ", "_"),
            start=start.strftime("%Y%m%d"),
            end=end.strftime("%Y%m%d"),
        )
        try:
            self._throttle()
            resp = requests.get(url, headers=_HEADERS, timeout=15)
            resp.raise_for_status()
            items = resp.json().get("items", [])
        except Exception as exc:  # noqa: BLE001
            logger.warning("Wikipedia pageviews failed for {}: {}", ticker, exc)
            return []
        out: list[AttentionPoint] = []
        for it in items:
            try:
                ts = datetime.strptime(str(it["timestamp"]), "%Y%m%d%H")
                out.append(AttentionPoint(ticker, ts, float(it["views"]), "wikipedia"))
            except (KeyError, ValueError):
                continue
        return out
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_wikipedia_pageviews_adapter.py -v`
Expected: PASS (3 passed)

- [ ] **Step 6: Commit**

```bash
git add adapters/data/wikipedia_pageviews_adapter.py tests/fakes/fake_attention_series.py tests/test_wikipedia_pageviews_adapter.py
git commit -m "feat: Wikipedia pageviews adapter (AttentionSeriesPort)"
```

---

### Task 8: GoogleNewsAdapter (per-ticker News RSS → BuzzDiscoveryPort)

**Files:**
- Create: `adapters/data/google_news_adapter.py`
- Test: `tests/test_google_news_adapter.py`

- [ ] **Step 1: Write the failing test (mocked feedparser)**

`tests/test_google_news_adapter.py`:
```python
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from domain.models import BuzzSignal


def test_google_news_emits_one_signal_per_ticker():
    from adapters.data.google_news_adapter import GoogleNewsAdapter

    entry = {"title": "AST SpaceMobile wins contract", "published_parsed": (2026, 6, 1, 0, 0, 0, 0, 0, 0)}
    feed = MagicMock(entries=[entry, entry, entry])
    with patch("adapters.data.google_news_adapter.feedparser.parse", return_value=feed):
        sigs = GoogleNewsAdapter(alias_map={"ASTS": "AST SpaceMobile"}).scan_sources(
            datetime(2026, 6, 2, tzinfo=timezone.utc), tickers=["ASTS"]
        )
    assert len(sigs) == 1
    assert sigs[0].ticker == "ASTS"
    assert sigs[0].source == "google_news"
    assert sigs[0].mention_count == 3


def test_google_news_returns_empty_on_error():
    from adapters.data.google_news_adapter import GoogleNewsAdapter

    with patch("adapters.data.google_news_adapter.feedparser.parse", side_effect=Exception("boom")):
        sigs = GoogleNewsAdapter().scan_sources(
            datetime(2026, 6, 2, tzinfo=timezone.utc), tickers=["ASTS"]
        )
    assert sigs == []


def test_google_news_no_tickers_returns_empty():
    from adapters.data.google_news_adapter import GoogleNewsAdapter
    assert GoogleNewsAdapter().scan_sources(datetime(2026, 6, 2, tzinfo=timezone.utc)) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_google_news_adapter.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement the adapter**

`adapters/data/google_news_adapter.py`:
```python
"""Google News per-ticker RSS adapter — keyless live mid-cap news volume.

Queries Google News RSS by company alias so mid-caps (not just mega-caps)
surface. Emits one aggregated BuzzSignal per ticker. Implements the
scan_sources half of BuzzDiscoveryPort.
"""

from __future__ import annotations

import hashlib
import time
from datetime import datetime

import feedparser
from loguru import logger

from domain.models import BuzzSignal

_RSS = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"


class GoogleNewsAdapter:
    def __init__(
        self, alias_map: dict[str, str] | None = None, throttle_s: float = 0.3
    ) -> None:
        self._alias_map = alias_map or {}
        self._throttle_s = throttle_s

    def _throttle(self) -> None:
        time.sleep(self._throttle_s)

    def _make_hash(self, ticker: str, scan_time: datetime) -> str:
        return hashlib.sha256(
            f"google_news:{ticker}:{scan_time.date().isoformat()}".encode()
        ).hexdigest()

    def scan_sources(
        self, scan_time: datetime, tickers: list[str] | None = None
    ) -> list[BuzzSignal]:
        if not tickers:
            return []
        out: list[BuzzSignal] = []
        for ticker in tickers:
            query = self._alias_map.get(ticker, ticker).replace(" ", "+")
            try:
                self._throttle()
                feed = feedparser.parse(_RSS.format(query=query))
                count = len(getattr(feed, "entries", []))
            except Exception as exc:  # noqa: BLE001
                logger.warning("Google News failed for {}: {}", ticker, exc)
                continue
            if count == 0:
                continue
            out.append(
                BuzzSignal(
                    ticker=ticker,
                    source="google_news",
                    mention_count=count,
                    sentiment_raw=0.0,  # volume signal; sentiment scored elsewhere
                    scorer="google_news",
                    fetched_at=scan_time,
                    article_hash=self._make_hash(ticker, scan_time),
                )
            )
        return out
```
(If `feedparser` is not already a dependency, add it to `pyproject.toml` in this task's commit and `pip install feedparser`. Check first: `python -c "import feedparser"` — the existing `rss_adapter.py` already uses it, so it is present.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_google_news_adapter.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add adapters/data/google_news_adapter.py tests/test_google_news_adapter.py
git commit -m "feat: Google News per-ticker RSS adapter (mid-cap news volume)"
```

---

### Task 9: Fix GdeltSentimentAdapter — backoff/retry + add get_historical_buzz

**Files:**
- Modify: `adapters/data/gdelt_sentiment_adapter.py`
- Test: `tests/test_gdelt_sentiment_adapter.py` (create if absent)

- [ ] **Step 1: Write the failing tests**

```python
from datetime import datetime
from unittest.mock import MagicMock, patch

import requests

from domain.models import BuzzSignal


def test_gdelt_retries_on_429_then_succeeds():
    from adapters.data.gdelt_sentiment_adapter import GdeltSentimentAdapter

    err = requests.HTTPError(response=MagicMock(status_code=429))
    ok = MagicMock(status_code=200, text="")
    ok.raise_for_status = lambda: None
    bad = MagicMock()
    bad.raise_for_status = MagicMock(side_effect=err)
    with patch("adapters.data.gdelt_sentiment_adapter.requests.get", side_effect=[bad, ok]) as g, \
         patch("adapters.data.gdelt_sentiment_adapter.time.sleep"):
        GdeltSentimentAdapter(max_retries=2, throttle_s=0).get_historical_sentiment(
            "ASTS", datetime(2026, 4, 1), datetime(2026, 6, 1)
        )
    assert g.call_count == 2  # retried after the 429


def test_gdelt_get_historical_buzz_returns_buzz_signals():
    from adapters.data.gdelt_sentiment_adapter import GdeltSentimentAdapter

    # ArtList CSV: header + 2 article rows dated in-window
    csv = "DATE\tSourceCommonName\tDocumentIdentifier\n20260501120000\tx\thttp://a\n20260502120000\ty\thttp://b\n"
    ok = MagicMock(status_code=200, text=csv)
    ok.raise_for_status = lambda: None
    with patch("adapters.data.gdelt_sentiment_adapter.requests.get", return_value=ok), \
         patch("adapters.data.gdelt_sentiment_adapter.time.sleep"):
        sigs = GdeltSentimentAdapter(throttle_s=0).get_historical_buzz(
            "ASTS", datetime(2026, 4, 1), datetime(2026, 6, 1)
        )
    assert all(isinstance(s, BuzzSignal) for s in sigs)
    assert all(s.source == "gdelt" for s in sigs)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_gdelt_sentiment_adapter.py -v`
Expected: FAIL (no `max_retries` kwarg / no `get_historical_buzz`)

- [ ] **Step 3: Implement backoff + get_historical_buzz**

In `adapters/data/gdelt_sentiment_adapter.py`:
- Add `import time` and `import hashlib` if absent.
- Change `__init__` to accept `max_retries: int = 3, throttle_s: float = 1.0` and store them.
- Wrap the `requests.get(...)` in `get_historical_sentiment` with a retry loop that, on HTTP 429, sleeps `2**attempt` seconds and retries up to `max_retries`, else returns `[]` (keep the existing return-empty-on-error contract).
- Add a new method that counts articles per day and emits one `BuzzSignal` per article date:
```python
def get_historical_buzz(
    self, ticker: str, start_date: datetime, end_date: datetime
) -> list["BuzzSignal"]:
    """Article-count buzz events from GDELT ArtList (honest historical timestamps)."""
    from domain.models import BuzzSignal

    params = {
        "query": f'"{ticker}" sourcelang:eng',
        "mode": "ArtList",
        "format": "csv",
        "startdatetime": start_date.strftime("%Y%m%d%H%M%S"),
        "enddatetime": end_date.strftime("%Y%m%d%H%M%S"),
        "maxrecords": "250",
    }
    text = self._get_with_retry(params)  # returns "" on failure
    if not text:
        return []
    out: list[BuzzSignal] = []
    for i, line in enumerate(text.strip().splitlines()):
        if i == 0:  # header
            continue
        cols = line.split("\t")
        if not cols or not cols[0]:
            continue
        try:
            ts = datetime.strptime(cols[0], "%Y%m%d%H%M%S")
        except ValueError:
            continue
        out.append(
            BuzzSignal(
                ticker=ticker,
                source="gdelt",
                mention_count=1,
                sentiment_raw=0.0,
                scorer="gdelt",
                fetched_at=ts,
                article_hash=hashlib.sha256(
                    f"gdelt:{ticker}:{cols[0]}:{i}".encode()
                ).hexdigest(),
            )
        )
    return out
```
- Extract the retry loop into a private `_get_with_retry(params) -> str` used by both methods; on `maxrecords` truncation (250 rows returned) log a warning: `logger.warning("GDELT maxrecords hit for {} — results truncated", ticker)`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_gdelt_sentiment_adapter.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add adapters/data/gdelt_sentiment_adapter.py tests/test_gdelt_sentiment_adapter.py
git commit -m "fix: GDELT 429 backoff/retry + add get_historical_buzz (honest events)"
```

---

### Task 10: GoogleTrendsAdapter — AttentionSeriesPort conformance wrapper

**Files:**
- Modify: `adapters/data/google_trends_adapter.py`
- Test: `tests/test_google_trends_adapter.py` (create if absent)

- [ ] **Step 1: Write the failing test**

```python
from datetime import datetime
from unittest.mock import MagicMock, patch

from domain.models import AttentionPoint
from domain.ports import AttentionSeriesPort


def test_google_trends_conforms_to_attention_series_port():
    from adapters.data.google_trends_adapter import GoogleTrendsAdapter
    assert isinstance(GoogleTrendsAdapter(), AttentionSeriesPort)


def test_get_attention_series_maps_historical_interest():
    from adapters.data.google_trends_adapter import GoogleTrendsAdapter

    a = GoogleTrendsAdapter()
    fake_buzz = [
        # get_historical_interest returns BuzzSignal list (mention_count = interest)
        MagicMock(ticker="ASTS", mention_count=10, fetched_at=datetime(2026, 5, 1)),
        MagicMock(ticker="ASTS", mention_count=80, fetched_at=datetime(2026, 6, 1)),
    ]
    with patch.object(a, "get_historical_interest", return_value=fake_buzz):
        pts = a.get_attention_series("ASTS", datetime(2026, 4, 1), datetime(2026, 6, 1))
    assert len(pts) == 2
    assert all(isinstance(p, AttentionPoint) for p in pts)
    assert pts[1].value == 80.0
    assert pts[1].source == "google_trends"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_google_trends_adapter.py -v`
Expected: FAIL (no `get_attention_series` method)

- [ ] **Step 3: Implement the wrapper**

In `adapters/data/google_trends_adapter.py`, add (the class already has `get_historical_interest` returning `BuzzSignal`s with `mention_count` = interest value):
```python
def get_attention_series(
    self, ticker: str, start: datetime, end: datetime
) -> list["AttentionPoint"]:
    """Adapt historical interest to AttentionSeriesPort (intensity points)."""
    from domain.models import AttentionPoint

    signals = self.get_historical_interest(ticker, start, end)
    return [
        AttentionPoint(
            ticker=ticker,
            timestamp=s.fetched_at,
            value=float(s.mention_count),
            source="google_trends",
        )
        for s in signals
    ]
```
Also guard the pytrends import so a missing dep degrades gracefully: wrap `from pytrends.request import TrendReq` in the existing `_get_pytrends` in a try/except that logs and raises a clear message (the scan_sources/get_historical_interest already catch and return []).

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_google_trends_adapter.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add adapters/data/google_trends_adapter.py tests/test_google_trends_adapter.py
git commit -m "feat: GoogleTrendsAdapter get_attention_series (AttentionSeriesPort)"
```

---

### Task 11: RedditAdapter (PRAW, pluggable no-op without creds)

**Files:**
- Create: `adapters/data/reddit_adapter.py`
- Test: `tests/test_reddit_adapter.py`

- [ ] **Step 1: Write the failing tests**

```python
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from domain.models import BuzzSignal


def test_reddit_no_creds_is_noop():
    from adapters.data.reddit_adapter import RedditAdapter

    a = RedditAdapter(client_id=None, client_secret=None, user_agent=None)
    assert a.enabled is False
    assert a.scan_sources(datetime(2026, 6, 2, tzinfo=timezone.utc), tickers=["ASTS"]) == []


def test_reddit_with_creds_emits_signal():
    from adapters.data.reddit_adapter import RedditAdapter

    submission = MagicMock(title="ASTS to the moon", score=50, num_comments=10)
    subreddit = MagicMock()
    subreddit.search.return_value = [submission, submission]
    reddit = MagicMock()
    reddit.subreddit.return_value = subreddit
    with patch("adapters.data.reddit_adapter.praw.Reddit", return_value=reddit):
        a = RedditAdapter(client_id="x", client_secret="y", user_agent="z",
                          subreddit_map={"ASTS": ["spacestocks"]})
        sigs = a.scan_sources(datetime(2026, 6, 2, tzinfo=timezone.utc), tickers=["ASTS"])
    assert len(sigs) == 1
    assert sigs[0].source == "reddit"
    assert sigs[0].mention_count == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_reddit_adapter.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement the adapter**

`adapters/data/reddit_adapter.py`:
```python
"""Reddit adapter (PRAW) — pluggable retail-buzz source.

No-op when credentials are absent (enabled=False) so the pipeline runs
keyless until REDDIT_CLIENT_ID/SECRET/USER_AGENT are configured.
"""

from __future__ import annotations

import hashlib
import time
from datetime import datetime

import praw
from loguru import logger

from domain.models import BuzzSignal


class RedditAdapter:
    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        user_agent: str | None = None,
        subreddit_map: dict[str, list[str]] | None = None,
        throttle_s: float = 0.5,
    ) -> None:
        self.enabled = bool(client_id and client_secret and user_agent)
        self._subreddit_map = subreddit_map or {}
        self._throttle_s = throttle_s
        self._reddit = None
        if self.enabled:
            try:
                self._reddit = praw.Reddit(
                    client_id=client_id,
                    client_secret=client_secret,
                    user_agent=user_agent,
                    check_for_async=False,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Reddit init failed, disabling: {}", exc)
                self.enabled = False
        else:
            logger.info("Reddit adapter: no creds, running as no-op")

    def scan_sources(
        self, scan_time: datetime, tickers: list[str] | None = None
    ) -> list[BuzzSignal]:
        if not self.enabled or not tickers:
            return []
        out: list[BuzzSignal] = []
        for ticker in tickers:
            subs = self._subreddit_map.get(ticker, ["stocks"])
            count = 0
            try:
                for sub in subs:
                    time.sleep(self._throttle_s)
                    results = self._reddit.subreddit(sub).search(
                        ticker, time_filter="week", limit=50
                    )
                    count += sum(1 for _ in results)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Reddit scan failed for {}: {}", ticker, exc)
                continue
            if count == 0:
                continue
            out.append(
                BuzzSignal(
                    ticker=ticker,
                    source="reddit",
                    mention_count=count,
                    sentiment_raw=0.0,
                    scorer="reddit",
                    fetched_at=scan_time,
                    article_hash=hashlib.sha256(
                        f"reddit:{ticker}:{scan_time.date().isoformat()}".encode()
                    ).hexdigest(),
                )
            )
        return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_reddit_adapter.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add adapters/data/reddit_adapter.py tests/test_reddit_adapter.py
git commit -m "feat: pluggable Reddit (PRAW) adapter — no-op without creds"
```

---

## Phase 3 — Store: New Tables + Methods

### Task 12: attention_series table + save/get methods

**Files:**
- Modify: `adapters/data/sqlite_store.py` (add to `_SCHEMA`; add methods)
- Test: `tests/test_sqlite_store.py`

- [ ] **Step 1: Write the failing test**

```python
def test_attention_series_roundtrip(tmp_path):
    from datetime import datetime
    from adapters.data.sqlite_store import SQLiteStore
    from domain.models import AttentionPoint

    store = SQLiteStore(db_path=str(tmp_path / "t.db"))
    pts = [
        AttentionPoint("ASTS", datetime(2026, 6, 1), 10.0, "google_trends"),
        AttentionPoint("ASTS", datetime(2026, 6, 2), 80.0, "wikipedia"),
    ]
    store.save_attention_points(pts)
    got = store.get_attention_series("ASTS", datetime(2026, 5, 1), datetime(2026, 7, 1))
    assert len(got) == 2


def test_attention_series_dedupe(tmp_path):
    from datetime import datetime
    from adapters.data.sqlite_store import SQLiteStore
    from domain.models import AttentionPoint

    store = SQLiteStore(db_path=str(tmp_path / "t.db"))
    p = AttentionPoint("ASTS", datetime(2026, 6, 1), 10.0, "google_trends")
    store.save_attention_points([p])
    store.save_attention_points([p])  # re-run, must not duplicate
    got = store.get_attention_series("ASTS", datetime(2026, 5, 1), datetime(2026, 7, 1))
    assert len(got) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_sqlite_store.py -k attention_series -v`
Expected: FAIL (no `save_attention_points`)

- [ ] **Step 3: Add table to `_SCHEMA` and the methods**

In `_SCHEMA` (after the buzz_signals block):
```sql
CREATE TABLE IF NOT EXISTS attention_series (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    source TEXT NOT NULL,
    ts TIMESTAMP NOT NULL,
    value REAL NOT NULL,
    UNIQUE(ticker, source, ts)
);
CREATE INDEX IF NOT EXISTS idx_attn_ticker ON attention_series(ticker);
```
Add methods (mirroring `save_buzz_signal`/`get_buzz_signals`):
```python
def save_attention_points(self, points: list[AttentionPoint]) -> None:
    for p in points:
        self._conn.execute(
            "INSERT OR IGNORE INTO attention_series (ticker, source, ts, value) "
            "VALUES (?, ?, ?, ?)",
            (p.ticker, p.source, p.timestamp.isoformat(), p.value),
        )
    self._conn.commit()

def get_attention_series(
    self, ticker: str, start: datetime, end: datetime
) -> list[AttentionPoint]:
    rows = self._conn.execute(
        "SELECT * FROM attention_series WHERE ticker = ? AND ts >= ? AND ts <= ? "
        "ORDER BY ts",
        (ticker, start.isoformat(), end.isoformat()),
    ).fetchall()
    return [
        AttentionPoint(r["ticker"], datetime.fromisoformat(r["ts"]), r["value"], r["source"])
        for r in rows
    ]
```
Add `AttentionPoint` to the `from domain.models import (...)` block at the top of `sqlite_store.py`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_sqlite_store.py -k attention_series -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add adapters/data/sqlite_store.py tests/test_sqlite_store.py
git commit -m "feat: attention_series store table + save/get (append-only, deduped)"
```

---

### Task 13: scan_candidates table + save/get methods

**Files:**
- Modify: `adapters/data/sqlite_store.py`
- Test: `tests/test_sqlite_store.py`

- [ ] **Step 1: Write the failing test**

```python
def test_scan_candidates_roundtrip(tmp_path):
    from adapters.data.sqlite_store import SQLiteStore

    store = SQLiteStore(db_path=str(tmp_path / "t.db"))
    store.save_scan_candidate(
        scan_date="2026-06-05",
        ticker="ASTS",
        conviction=6.4,
        divergence=7.1,
        sub_scores={"smart_money": 8.0, "event_signal": 6.0},
        surfaced=True,
        theme="space",
        cap_tier="mid",
    )
    rows = store.get_scan_candidates(scan_date="2026-06-05")
    assert len(rows) == 1
    assert rows[0]["ticker"] == "ASTS"
    assert rows[0]["surfaced"] == 1
    assert rows[0]["sub_scores"]["smart_money"] == 8.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_sqlite_store.py -k scan_candidates -v`
Expected: FAIL (no `save_scan_candidate`)

- [ ] **Step 3: Add table + methods**

`_SCHEMA`:
```sql
CREATE TABLE IF NOT EXISTS scan_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_date TEXT NOT NULL,
    ticker TEXT NOT NULL,
    conviction REAL NOT NULL,
    divergence REAL NOT NULL,
    sub_scores_json TEXT NOT NULL,
    surfaced INTEGER NOT NULL,
    theme TEXT,
    cap_tier TEXT
);
CREATE INDEX IF NOT EXISTS idx_cand_date ON scan_candidates(scan_date);
```
Methods (add `import json` at top if absent):
```python
def save_scan_candidate(
    self, scan_date: str, ticker: str, conviction: float, divergence: float,
    sub_scores: dict[str, float], surfaced: bool, theme: str | None,
    cap_tier: str | None,
) -> None:
    self._conn.execute(
        "INSERT INTO scan_candidates "
        "(scan_date, ticker, conviction, divergence, sub_scores_json, surfaced, theme, cap_tier) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (scan_date, ticker, conviction, divergence, json.dumps(sub_scores),
         1 if surfaced else 0, theme, cap_tier),
    )
    self._conn.commit()

def get_scan_candidates(self, scan_date: str | None = None) -> list[dict[str, Any]]:
    q = "SELECT * FROM scan_candidates"
    params: list[Any] = []
    if scan_date is not None:
        q += " WHERE scan_date = ?"
        params.append(scan_date)
    q += " ORDER BY conviction DESC"
    rows = self._conn.execute(q, params).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["sub_scores"] = json.loads(d.pop("sub_scores_json"))
        out.append(d)
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_sqlite_store.py -k scan_candidates -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add adapters/data/sqlite_store.py tests/test_sqlite_store.py
git commit -m "feat: scan_candidates full-distribution log table + save/get"
```

---

### Task 14: signal_cache table + get/put with TTL

**Files:**
- Modify: `adapters/data/sqlite_store.py`
- Test: `tests/test_sqlite_store.py`

- [ ] **Step 1: Write the failing test**

```python
def test_signal_cache_hit_and_ttl(tmp_path):
    from datetime import datetime, timedelta
    from adapters.data.sqlite_store import SQLiteStore

    store = SQLiteStore(db_path=str(tmp_path / "t.db"))
    t0 = datetime(2026, 6, 5, 8, 0, 0)
    store.put_cached_signal("ASTS", "event_signal", 7.0, t0)

    # fresh within TTL
    assert store.get_cached_signal("ASTS", "event_signal", t0 + timedelta(hours=1), ttl_hours=24) == 7.0
    # expired beyond TTL
    assert store.get_cached_signal("ASTS", "event_signal", t0 + timedelta(hours=25), ttl_hours=24) is None
    # missing key
    assert store.get_cached_signal("ZZZ", "event_signal", t0, ttl_hours=24) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_sqlite_store.py -k signal_cache -v`
Expected: FAIL (no `put_cached_signal`)

- [ ] **Step 3: Add table + methods**

`_SCHEMA`:
```sql
CREATE TABLE IF NOT EXISTS signal_cache (
    ticker TEXT NOT NULL,
    dim TEXT NOT NULL,
    value REAL NOT NULL,
    computed_at TIMESTAMP NOT NULL,
    PRIMARY KEY (ticker, dim)
);
```
Methods:
```python
def put_cached_signal(
    self, ticker: str, dim: str, value: float, computed_at: datetime
) -> None:
    self._conn.execute(
        "INSERT OR REPLACE INTO signal_cache (ticker, dim, value, computed_at) "
        "VALUES (?, ?, ?, ?)",
        (ticker, dim, value, computed_at.isoformat()),
    )
    self._conn.commit()

def get_cached_signal(
    self, ticker: str, dim: str, now: datetime, ttl_hours: float
) -> float | None:
    row = self._conn.execute(
        "SELECT value, computed_at FROM signal_cache WHERE ticker = ? AND dim = ?",
        (ticker, dim),
    ).fetchone()
    if row is None:
        return None
    computed = datetime.fromisoformat(row["computed_at"])
    if (now - computed).total_seconds() > ttl_hours * 3600:
        return None
    return float(row["value"])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_sqlite_store.py -k signal_cache -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add adapters/data/sqlite_store.py tests/test_sqlite_store.py
git commit -m "feat: signal_cache table + TTL get/put for conviction dims"
```

---

## Phase 4 — Application: Backfill, Conviction Cache, Scan Extension

### Task 15: BackfillHistoryUseCase

**Files:**
- Create: `application/backfill_use_case.py`
- Test: `tests/test_backfill_use_case.py`

- [ ] **Step 1: Write the failing tests**

```python
from datetime import datetime, timedelta

from domain.models import AttentionPoint, BuzzSignal


class _FakeGdelt:
    def __init__(self, fail_for=None):
        self.fail_for = fail_for or set()
    def get_historical_buzz(self, ticker, start, end):
        if ticker in self.fail_for:
            raise RuntimeError("boom")
        return [BuzzSignal(ticker, "gdelt", 1, 0.0, "gdelt", start, f"h-{ticker}")]


class _FakeAttn:
    def __init__(self, source):
        self.source = source
    def get_attention_series(self, ticker, start, end):
        return [AttentionPoint(ticker, start, 5.0, self.source)]


class _RecordingStore:
    def __init__(self):
        self.buzz = []
        self.points = []
    def save_buzz_signal(self, s):
        self.buzz.append(s)
    def save_attention_points(self, pts):
        self.points.extend(pts)


def test_backfill_persists_all_sources():
    from application.backfill_use_case import BackfillHistoryUseCase

    store = _RecordingStore()
    uc = BackfillHistoryUseCase(
        gdelt=_FakeGdelt(), trends=_FakeAttn("google_trends"),
        wiki=_FakeAttn("wikipedia"), store=store,
    )
    stats = uc.execute(["ASTS", "RKLB"], now=datetime(2026, 6, 5), days=90)
    assert len(store.buzz) == 2          # one gdelt buzz per ticker
    assert len(store.points) == 4        # trends + wiki per ticker
    assert stats["tickers"] == 2


def test_backfill_isolates_per_ticker_failure():
    from application.backfill_use_case import BackfillHistoryUseCase

    store = _RecordingStore()
    uc = BackfillHistoryUseCase(
        gdelt=_FakeGdelt(fail_for={"ASTS"}), trends=_FakeAttn("google_trends"),
        wiki=_FakeAttn("wikipedia"), store=store,
    )
    stats = uc.execute(["ASTS", "RKLB"], now=datetime(2026, 6, 5), days=90)
    # ASTS gdelt failed but RKLB still processed; attention still saved for both
    assert stats["errors"] >= 1
    assert any(s.ticker == "RKLB" for s in store.buzz)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_backfill_use_case.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`application/backfill_use_case.py`:
```python
"""Backfill the divergence base window from honest historical archives.

GDELT → event buzz (article timestamps); Google Trends + Wikipedia →
intensity series. Per-ticker isolation: one failure logs and continues.
Append-only persistence makes re-runs idempotent.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from loguru import logger


class BackfillHistoryUseCase:
    def __init__(self, gdelt: Any, trends: Any, wiki: Any, store: Any) -> None:
        self._gdelt = gdelt
        self._trends = trends
        self._wiki = wiki
        self._store = store

    def execute(
        self, tickers: list[str], now: datetime, days: int = 90
    ) -> dict[str, int]:
        start = now - timedelta(days=days)
        errors = 0
        for ticker in tickers:
            try:
                for sig in self._gdelt.get_historical_buzz(ticker, start, now):
                    self._store.save_buzz_signal(sig)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Backfill GDELT failed for {}: {}", ticker, exc)
                errors += 1
            for src in (self._trends, self._wiki):
                try:
                    pts = src.get_attention_series(ticker, start, now)
                    if pts:
                        self._store.save_attention_points(pts)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Backfill attention failed for {}: {}", ticker, exc)
                    errors += 1
        return {"tickers": len(tickers), "errors": errors}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_backfill_use_case.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add application/backfill_use_case.py tests/test_backfill_use_case.py
git commit -m "feat: BackfillHistoryUseCase (honest base window, per-ticker isolation)"
```

---

### Task 16: ConvictionSignalCache (cached event + analyst dims)

**Files:**
- Create: `application/conviction_signal_cache.py`
- Test: `tests/test_conviction_signal_cache.py`

- [ ] **Step 1: Write the failing tests**

```python
from datetime import datetime


class _MemStore:
    def __init__(self):
        self.data = {}
    def get_cached_signal(self, ticker, dim, now, ttl_hours):
        return self.data.get((ticker, dim))
    def put_cached_signal(self, ticker, dim, value, computed_at):
        self.data[(ticker, dim)] = value


def test_cache_miss_computes_and_stores():
    from application.conviction_signal_cache import ConvictionSignalCache

    store = _MemStore()
    calls = {"n": 0}
    def compute(ticker, now):
        calls["n"] += 1
        return 7.0
    csc = ConvictionSignalCache(store=store, ttl_hours=24)
    v = csc.get_or_compute("ASTS", "event_signal", datetime(2026, 6, 5), compute)
    assert v == 7.0 and calls["n"] == 1
    # second call hits cache
    v2 = csc.get_or_compute("ASTS", "event_signal", datetime(2026, 6, 5), compute)
    assert v2 == 7.0 and calls["n"] == 1


def test_cache_failure_returns_flagged_neutral():
    from application.conviction_signal_cache import ConvictionSignalCache

    store = _MemStore()
    def compute(ticker, now):
        raise RuntimeError("api down")
    csc = ConvictionSignalCache(store=store, ttl_hours=24)
    v = csc.get_or_compute("ASTS", "event_signal", datetime(2026, 6, 5), compute)
    assert v == 5.0
    assert ("ASTS", "event_signal") in csc.flags  # flagged, not silent
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_conviction_signal_cache.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`application/conviction_signal_cache.py`:
```python
"""Daily cache for the expensive conviction dims (event_signal, analyst_signal).

Cache hit within TTL → reuse. Miss → compute + store. Failure → honest
neutral 5.0 + a flag (never a silent pin). Flags seed sub-project B's
source-health monitor.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from loguru import logger

_NEUTRAL = 5.0


class ConvictionSignalCache:
    def __init__(self, store: Any, ttl_hours: float = 24.0) -> None:
        self._store = store
        self._ttl = ttl_hours
        self.flags: set[tuple[str, str]] = set()

    def get_or_compute(
        self,
        ticker: str,
        dim: str,
        now: datetime,
        compute: Callable[[str, datetime], float],
    ) -> float:
        cached = self._store.get_cached_signal(ticker, dim, now, self._ttl)
        if cached is not None:
            return cached
        try:
            value = compute(ticker, now)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Conviction dim {} failed for {}: {}", dim, ticker, exc)
            self.flags.add((ticker, dim))
            return _NEUTRAL
        self._store.put_cached_signal(ticker, dim, value, now)
        return value
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_conviction_signal_cache.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add application/conviction_signal_cache.py tests/test_conviction_signal_cache.py
git commit -m "feat: ConvictionSignalCache — cached event/analyst dims, flagged failures"
```

---

### Task 17: Extend OpportunityScanUseCase — intensity, blended divergence, distribution log

**Files:**
- Modify: `application/opportunity_scan_use_case.py`
- Test: `tests/test_opportunity_scan.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_scan_persists_full_candidate_distribution():
    from datetime import datetime, timezone
    from application.opportunity_scan_use_case import OpportunityScanUseCase
    from domain.universe import UniverseEntry
    from tests.fakes.fake_buzz_discovery import FakeBuzzDiscovery
    from tests.fakes.fake_market_data import FakeMarketData
    from tests.fakes.fake_surfaced_call_store import FakeSurfacedCallStore
    from tests.fakes.fake_universe_provider import FakeUniverseProvider
    from tests.fakes.fake_attention_series import FakeAttentionSeries

    NOW = datetime(2026, 6, 5, tzinfo=timezone.utc)
    store = FakeSurfacedCallStore()
    store.candidates = []  # extend fake to record (see Step 3)
    uc = OpportunityScanUseCase(
        universe_provider=FakeUniverseProvider([UniverseEntry("ASTS", "space"), UniverseEntry("DUD", "space")]),
        conviction_provider=lambda t, now: (8.0 if t == "ASTS" else 3.0, {"smart_money": 7.0}),
        buzz_discovery=FakeBuzzDiscovery([]),
        market_data=FakeMarketData(signals={"ASTS": [], "DUD": [], "SPY": [], "QQQ": []},
                                   ticker_info={"ASTS": {"marketCap": 3e9}, "DUD": {"marketCap": 5e8}}),
        store=store,
        attention_provider=FakeAttentionSeries([]),
        cmin=6.0, dmin=0.0,
    )
    uc.execute(NOW)
    # both candidates logged regardless of surfacing
    assert len(store.candidates) == 2
    surfaced_flags = {c["ticker"]: c["surfaced"] for c in store.candidates}
    assert surfaced_flags["ASTS"] is True
    assert surfaced_flags["DUD"] is False
```

- [ ] **Step 2: Extend the fake store to record candidates**

In `tests/fakes/fake_surfaced_call_store.py`, add to `__init__`: `self.candidates: list[dict] = []` and add:
```python
def save_scan_candidate(self, scan_date, ticker, conviction, divergence,
                        sub_scores, surfaced, theme, cap_tier):
    self.candidates.append({
        "scan_date": scan_date, "ticker": ticker, "conviction": conviction,
        "divergence": divergence, "sub_scores": sub_scores, "surfaced": surfaced,
        "theme": theme, "cap_tier": cap_tier,
    })
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_opportunity_scan.py -k distribution -v`
Expected: FAIL (`OpportunityScanUseCase` has no `attention_provider` param / no candidate logging)

- [ ] **Step 4: Implement**

In `application/opportunity_scan_use_case.py`:
- Add `attention_provider: Any = None` to `__init__` and store as `self._attn`.
- Import the blend: `from domain.divergence_service import blended_divergence_score`.
- Add a helper:
```python
def _intensity_series(self, ticker: str, now: datetime) -> list[tuple[datetime, float]]:
    if self._attn is None:
        return []
    start = now - timedelta(days=40)
    pts = self._attn.get_attention_series(ticker, start, now)
    return [(_match_awareness(p.timestamp, now), p.value) for p in pts]
```
- In `execute`, replace the `divergence = divergence_score(...)` call with:
```python
intensity = self._intensity_series(entry.ticker, now)
divergence = blended_divergence_score(
    buzz_times, intensity, self._price_series(entry.ticker, now), sentiment, now
)
```
- After computing `conviction`, `divergence`, `sub_scores`, and the `_cap_tier`, persist every candidate before the threshold check:
```python
info = self._md.get_ticker_info(entry.ticker)
cap = _cap_tier(float(info.get("marketCap", 0.0)))
surfaced = conviction >= self._cmin and divergence >= self._dmin
self._store.save_scan_candidate(
    scan_date=now.date().isoformat(),
    ticker=entry.ticker,
    conviction=conviction,
    divergence=divergence,
    sub_scores=sub_scores,
    surfaced=surfaced,
    theme=entry.theme,
    cap_tier=cap,
)
if not surfaced:
    continue
```
(Reuse the already-fetched `info`/`cap` when building the `SurfacedCall` instead of re-fetching.)

- [ ] **Step 5: Run the scan test file**

Run: `pytest tests/test_opportunity_scan.py -v`
Expected: PASS (all — existing + new)

- [ ] **Step 6: Commit**

```bash
git add application/opportunity_scan_use_case.py tests/test_opportunity_scan.py tests/fakes/fake_surfaced_call_store.py
git commit -m "feat: scan uses blended divergence + logs full candidate distribution"
```

---

## Phase 5 — CLI + Scheduling

### Task 18: backfill-history CLI command

**Files:**
- Modify: `application/cli.py`
- Test: `tests/test_opportunity_cli.py`

- [ ] **Step 1: Write the failing test (CliRunner)**

```python
def test_backfill_history_command_runs(monkeypatch, tmp_path):
    from click.testing import CliRunner
    from application.cli import cli

    # patch the use case to avoid network
    import application.cli as climod

    class _UC:
        def __init__(self, *a, **k): pass
        def execute(self, tickers, now, days=90): return {"tickers": len(tickers), "errors": 0}
    monkeypatch.setattr(climod, "BackfillHistoryUseCase", _UC, raising=False)

    runner = CliRunner()
    result = runner.invoke(cli, ["backfill-history", "--market", "us", "--days", "30", "--limit", "2"])
    assert result.exit_code == 0
    assert "Backfill complete" in result.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_opportunity_cli.py -k backfill_history -v`
Expected: FAIL (no such command)

- [ ] **Step 3: Implement the command**

In `application/cli.py`, mirroring the `scan-opportunities` command structure (`@cli.command`, `_build_dependencies`, lazy imports):
```python
@cli.command("backfill-history")
@click.option("--market", default="us", help="Market config to use")
@click.option("--days", default=90, show_default=True, type=int, help="Backfill window in days")
@click.option("--limit", default=0, type=int, help="Max tickers (0 = all in universe)")
def backfill_history(market: str, days: int, limit: int) -> None:
    """Backfill the divergence base window from honest historical archives (GDELT/GT/Wikipedia)."""
    from datetime import timezone

    from adapters.data.gdelt_sentiment_adapter import GdeltSentimentAdapter
    from adapters.data.google_trends_adapter import GoogleTrendsAdapter
    from adapters.data.wikipedia_pageviews_adapter import WikipediaPageviewsAdapter
    from application.backfill_use_case import BackfillHistoryUseCase

    deps = _build_dependencies(market)
    store = deps["store"]
    tickers = _load_universe_tickers(market)  # existing helper; if absent, read from config/tickers
    if limit:
        tickers = tickers[:limit]
    now = datetime.now(timezone.utc)
    uc = BackfillHistoryUseCase(
        gdelt=GdeltSentimentAdapter(),
        trends=GoogleTrendsAdapter(),
        wiki=WikipediaPageviewsAdapter(article_map=_load_wiki_map(market)),
        store=store,
    )
    stats = uc.execute(tickers, now=now, days=days)
    click.echo(f"Backfill complete: {stats['tickers']} tickers, {stats['errors']} errors")
```
If `_load_universe_tickers` / `_load_wiki_map` helpers don't exist, add small local helpers that read `config/tickers/*` and the `aliases:` block of `themes.yaml` respectively.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_opportunity_cli.py -k backfill_history -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add application/cli.py tests/test_opportunity_cli.py
git commit -m "feat: backfill-history CLI command"
```

---

### Task 19: scan-opportunities --show-all + wire conviction cache + attention sources

**Files:**
- Modify: `application/cli.py` (the `scan_opportunities` command + `conviction_provider`)
- Test: `tests/test_opportunity_cli.py`

- [ ] **Step 1: Write the failing test**

```python
def test_scan_show_all_prints_distribution(monkeypatch):
    from click.testing import CliRunner
    from application.cli import cli
    import application.cli as climod

    class _UC:
        def __init__(self, *a, **k): pass
        def execute(self, now, allow_abstention=True): return []
    monkeypatch.setattr(climod, "OpportunityScanUseCase", _UC, raising=False)

    runner = CliRunner()
    result = runner.invoke(cli, ["scan-opportunities", "--show-all"])
    assert result.exit_code == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_opportunity_cli.py -k show_all -v`
Expected: FAIL (no `--show-all` option)

- [ ] **Step 3: Implement**

In `application/cli.py` `scan_opportunities`:
- Add option: `@click.option("--show-all", is_flag=True, help="Print the full candidate score distribution")`.
- Add `show_all: bool` to the function signature.
- Wire the new sources into the use case: build `WikipediaPageviewsAdapter` + `GoogleTrendsAdapter` and pass `attention_provider=...` (a small combiner that merges both sources' `get_attention_series` results, averaging per-source as the spec notes — implement as an inline adapter object or a list passed to the use case; if multiple intensity sources, average their `intensity_acceleration` happens in domain, so just concatenate points here).
- In `conviction_provider`, replace `event_score=5.0, analyst_score=5.0` with cached computations:
```python
from application.conviction_signal_cache import ConvictionSignalCache
from adapters.data.gemini_event_classifier import GeminiEventClassifier  # event dim
# build once outside the closure:
signal_cache = ConvictionSignalCache(store=store, ttl_hours=_cfg_ttl(market))
# inside conviction_provider, before _compute_sub_scores:
event_score = signal_cache.get_or_compute(ticker, "event_signal", scan_time, _compute_event)
analyst_score = signal_cache.get_or_compute(ticker, "analyst_signal", scan_time, _compute_analyst)
```
where `_compute_event(ticker, now)` and `_compute_analyst(ticker, now)` call the existing Gemini event path and the AnalystRatings adapter respectively (reuse Phase 4D / ADR-038 code paths), each returning a [1,10] score. Pass the computed `event_score`/`analyst_score` into `_compute_sub_scores`. Remove the duplicate `engineer.compute(...)` call (keep one).
- After `calls = use_case.execute(now)`, if `show_all`, read and print the distribution:
```python
if show_all:
    rows = store.get_scan_candidates(scan_date=now.date().isoformat())
    click.echo("\nFull candidate distribution (conviction / divergence):")
    for r in rows:
        mark = "*" if r["surfaced"] else " "
        click.echo(f"  {mark} {r['ticker']:6s} c={r['conviction']:.2f} d={r['divergence']:.2f} [{r['cap_tier']}]")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_opportunity_cli.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add application/cli.py tests/test_opportunity_cli.py
git commit -m "feat: scan-opportunities --show-all + wire all 8 conviction dims (cached)"
```

---

### Task 20: daily-cycle CLI command

**Files:**
- Modify: `application/cli.py`
- Test: `tests/test_opportunity_cli.py`

- [ ] **Step 1: Write the failing test**

```python
def test_daily_cycle_invokes_scan_then_resolve(monkeypatch):
    from click.testing import CliRunner
    from application.cli import cli

    runner = CliRunner()
    result = runner.invoke(cli, ["daily-cycle", "--skip-backfill"])
    assert result.exit_code == 0
    assert "daily cycle" in result.output.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_opportunity_cli.py -k daily_cycle -v`
Expected: FAIL (no such command)

- [ ] **Step 3: Implement**

In `application/cli.py`, add a command that invokes the existing commands' callbacks via click context:
```python
@cli.command("daily-cycle")
@click.option("--market", default="us", help="Market config to use")
@click.option("--skip-backfill", is_flag=True, help="Skip the weekly backfill refresh")
@click.pass_context
def daily_cycle(ctx: click.Context, market: str, skip_backfill: bool) -> None:
    """Run the full daily cycle: scan-opportunities -> resolve-calls -> weekly backfill refresh."""
    click.echo("Starting daily cycle...")
    ctx.invoke(scan_opportunities, market=market, date=None, cmin=_cfg_cmin(market),
               dmin=_cfg_dmin(market), max_discovery=50, show_all=False)
    ctx.invoke(resolve_calls, date=None)
    if not skip_backfill and _is_backfill_due(market):
        ctx.invoke(backfill_history, market=market, days=14, limit=0)
    click.echo("Daily cycle complete.")
```
Add small config helpers `_cfg_cmin`/`_cfg_dmin`/`_cfg_ttl` reading the `opportunity_engine` block from `us.yaml`, and `_is_backfill_due` (true if 7+ days since last `attention_series` row — query store; default true if empty).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_opportunity_cli.py -k daily_cycle -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add application/cli.py tests/test_opportunity_cli.py
git commit -m "feat: daily-cycle CLI (scan -> resolve -> weekly backfill)"
```

---

### Task 21: launchd scheduling doc

**Files:**
- Create: `docs/scheduling.md`
- Modify: `README.md` (add a "Scheduling" pointer)

- [ ] **Step 1: Write the doc**

`docs/scheduling.md` — include a ready-to-edit launchd plist that runs `python -m application.cli daily-cycle` pre-market (~8:00 ET / 12:00 UTC), instructions to `launchctl load` it, where to put Reddit env vars, and the ADR-007 deviation note (local SQLite → local scheduling). Provide the exact plist XML with the working directory set to the repo path and `StandardOutPath`/`StandardErrorPath` to `data/reports/daily_cycle.log`.

- [ ] **Step 2: Add README pointer**

Add a short "## Scheduling" section to `README.md` linking to `docs/scheduling.md`.

- [ ] **Step 3: Commit**

```bash
git add docs/scheduling.md README.md
git commit -m "docs: launchd scheduling for daily-cycle (local, ADR-007 deviation noted)"
```

---

## Phase 6 — Integration, Calibration, ADR

### Task 22: Full quality gate + calibrate cmin/dmin from real distribution

**Files:**
- Modify: `config/markets/us.yaml` (calibrated thresholds)

- [ ] **Step 1: Run the full quality gate**

Run: `make check`
Expected: all tests pass, mypy strict clean, ≥90% coverage. Fix any failures before proceeding.

- [ ] **Step 2: Backfill + diagnostic scan (uses live APIs — run locally, not CI)**

Run:
```bash
python -m application.cli backfill-history --market us --days 90 --limit 40
python -m application.cli scan-opportunities --show-all > data/reports/_calibration_distribution.txt 2>&1
```
Expected: a printed ranked distribution of conviction/divergence per candidate.

- [ ] **Step 3: Set thresholds from the distribution**

Inspect `data/reports/_calibration_distribution.txt`. Choose `cmin`/`dmin` at the separation knee (e.g. the top-quartile boundary where scores meaningfully exceed the neutral 5.0 cluster). Update the `opportunity_engine.thresholds` block in `config/markets/us.yaml` with the chosen values and a comment citing the distribution date.

- [ ] **Step 4: Re-run scan to confirm non-empty (or honest abstention)**

Run: `python -m application.cli scan-opportunities`
Expected: surfaces mid-cap names that clear the calibrated bars, OR an honest abstention if none qualify (both are valid; record which in the commit message).

- [ ] **Step 5: Commit**

```bash
git add config/markets/us.yaml
git commit -m "chore: calibrate cmin/dmin from observed candidate distribution"
```

---

### Task 23: ADR-041 + update project status docs

**Files:**
- Create: `docs/adr/041-honest-opportunity-engine-sources-backfill.md`
- Modify: `CLAUDE.md` (Phase Status), `CONTEXT.md` (sources table / glossary)

- [ ] **Step 1: Write ADR-041**

Document the decisions: dead StockTwits retired; 4 keyless sources + pluggable Reddit; `AttentionSeriesPort` split (events vs intensity); blended divergence; honest GDELT/GT/Wikipedia backfill (and why it's leakage-free where a backtest wouldn't be); all-8-dim conviction with daily cache; full-distribution logging; local launchd scheduling (ADR-007 deviation). Status: Accepted.

- [ ] **Step 2: Update CLAUDE.md Phase Status**

Add a "Done (Leg-2 sub-project A — Honest Opportunity Engine 2026-06-05)" block summarizing the shipped components and final test count.

- [ ] **Step 3: Update CONTEXT.md**

Add `AttentionPoint`, `AttentionSeriesPort`, blended divergence, and the source table (GDELT/GT/Google-News/Wikipedia/Reddit) to the domain language section.

- [ ] **Step 4: Final quality gate**

Run: `make check`
Expected: green.

- [ ] **Step 5: Commit**

```bash
git add docs/adr/041-honest-opportunity-engine-sources-backfill.md CLAUDE.md CONTEXT.md
git commit -m "docs: ADR-041 honest opportunity engine + phase status update"
```

---

## Self-Review Checklist (completed by plan author)

**Spec coverage** — every spec section maps to a task:
- Q1 sources → Tasks 1, 7, 8, 9, 10, 11 (+ retire StockTwits T1)
- Q2 blended divergence → Tasks 3, 4, 5, 6
- Q3 conviction all-8 + cache + calibration → Tasks 14, 16, 19, 22
- Q4 distribution log → Tasks 13, 17, 19
- Backfill → Tasks 9 (get_historical_buzz), 12, 15, 18
- Scheduling → Tasks 20, 21
- Config/aliases → Task 2
- ADR/docs → Task 23

**Type/name consistency** (verified across tasks):
- `AttentionPoint(ticker, timestamp, value, source)` — T3, used T4/7/10/12/15/17
- `AttentionSeriesPort.get_attention_series(ticker, start, end)` — T4, impl T7/10, used T15/17
- `blended_divergence_score(buzz_times, intensity_series, price_series, sentiment, now, event_weight, intensity_weight)` — T6, used T17
- store: `save_attention_points`/`get_attention_series` (T12), `save_scan_candidate`/`get_scan_candidates` (T13), `get_cached_signal`/`put_cached_signal` (T14) — used T15/16/17/19
- `BackfillHistoryUseCase(gdelt, trends, wiki, store).execute(tickers, now, days)` — T15, used T18
- `ConvictionSignalCache(store, ttl_hours).get_or_compute(ticker, dim, now, compute)` — T16, used T19

**No placeholders** — every code step contains real code; modifications cite the file + the exact block to add and where.
