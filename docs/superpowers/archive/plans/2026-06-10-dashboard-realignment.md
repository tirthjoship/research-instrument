# Dashboard Realignment + Skill-Routing Wiring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Realign the Streamlit dashboard to the project's honest capabilities (7 new tabs: Weekly Brief · Research Candidates · Risk · My Portfolio · Stock Analysis · Falsification Lab · Methodology), delete falsified prediction-era surfaces, and wire repo-level skill routing.

**Architecture:** Hexagonal — the dashboard is a visualization ADAPTER that renders artifacts written by CLI jobs; it never computes domain logic and (except user-initiated Stock Analysis) never touches the network. One new application-layer serializer (`brief_summary.py`) gives the dashboard structured data. Spec: `docs/superpowers/specs/2026-06-10-dashboard-realignment-design.md`.

**Tech Stack:** Python 3.12, Streamlit + Plotly (existing), pytest, click CLI, pre-commit (black/isort/mypy strict/ruff — NEVER `--no-verify`; if a hook reformats, re-add and commit again).

**UI treatment — anti-flat (user requirement 2026-06-11, applies to Tasks 4/5/6/9/10):**
The code blocks in this plan are FUNCTIONAL skeletons; do not ship them as bare
`st.table`/`st.markdown` walls. Each tab must use the existing SWST design system
(`components/styles.py` — global CSS already injected by `dashboard.py`):

- Wrap each logical section in a `ws-card` div (has hover elevation) instead of bare markdown.
- Headline numbers via `components/metrics.py` helpers — `render_hero_banner` (tab-top
  state), `render_verdict_card` (Weekly Brief banner, Risk dominant-factor), `render_inline_context`
  (plain-English asides) — and `st.metric` rows with `st.columns` for stat strips.
- Verdict/status chips via `components/formatters.py` `status_pill_html` / `grade_badge_html`
  (CSS pills, no emoji) rather than colored text spans where a pill reads better.
- Plotly: consistent template across tabs (font Inter, accent `#2563EB`, transparent paper
  background to sit on cards, `height=320`, no gridline clutter) — match the existing
  builders in `components/charts.py`.
- Falsification Lab scoreboard: render rows as cards with a colored left-border accent per
  verdict (the `ws-card` pattern), not a plain markdown list with dividers.
- Whitespace rhythm: `st.divider()` only between major sections; cards carry their own spacing.
- During Task 12, invoke the `frontend-design` skill for a polish pass over all 7 tabs
  (spec §6 step 3 already names it) — distinctive, production-grade, NOT generic-AI flat.

---

## PRECONDITIONS (verify before Task 2 — Task 1 is ungated)

1. **Unit B verdict landed (CONFIRMED 2026-06-11):** `data/reports/insider_cluster_falsification_2024.json` exists, verdict = `INCONCLUSIVE_THIN_COVERAGE` → practical KILL, ADR-053 final. Task 9's scoreboard maps this to an amber "INCONCLUSIVE → practical KILL" row; the PASS/paper-log branch is dead.
2. **Venv fixed:** `python -c "import streamlit, plotly"` succeeds (hardening-sprint dependency). If it fails, STOP — the dashboard test suite cannot run.
3. **Branch:** create `feat/dashboard-realignment` off up-to-date `develop`. Never commit to develop/main directly.
4. Run baseline: `python -m pytest tests/ -q 2>&1 | tail -3` and record the pass/fail count (pre-existing failures from venv drift should be GONE if precondition 2 holds; if any remain, record them — your changes must not add new failures).

---

### Task 1: Skill-routing wiring (UNGATED — can run today, before preconditions)

**Files:**
- Create: `docs/SKILL_ROUTING.md`
- Modify: `CLAUDE.md` (Phase Status section)
- Create: `.claude/settings.json`

- [ ] **Step 1: Create `docs/SKILL_ROUTING.md`** with exactly this content:

```markdown
# Skill Routing — Multi-Modal Stock Recommender

> **Purpose:** Which skill/agent to invoke at each phase of *this* repo, and what gate
> must pass before the next phase opens. Repo-specific projection onto the wrap plan
> (`docs/superpowers/specs/2026-06-10-strategic-wrap-plan-design.md`).
>
> **Read order:** `docs/STATUS.md` (Tier 0) → this file (routing) → the named spec/plan.

---

## Where this project sits

Portfolio flagship in WRAP mode (close by 2026-06-29, then maintenance). Direction is
LOCKED by ADR-052: deterministic risk/behavior CRO; the recommender ABSTAINS
(RESEARCH_ONLY), never predicts. Six falsifications + Unit B decide the predictive
question permanently.

## Phase → skill routing

| Phase | Gate to enter | Invoke | Model |
|-------|---------------|--------|-------|
| Unit B verdict | report JSON exists | execute the LOCKED §2 tree of the wrap spec — NO judgment calls; `verification-before-completion` on ADR-053 numbers | Opus |
| Unit C build | Unit B merged | `brainstorming` → `writing-plans` → `subagent-driven-development` | Opus plan / Sonnet build |
| Hardening sprint | Unit C merged | `writing-plans` → `subagent-driven-development`; `systematic-debugging` on any failure | Sonnet |
| Dashboard realign | hardening done (venv fixed) + Unit B verdict | spec + plan dated 2026-06-10 → `subagent-driven-development`; `frontend-design` for tab layout polish | Sonnet build / Opus review |
| Docs refinement | build complete | `humanizer` on the write-up; plain-language test (wrap spec §5.5) | Sonnet |
| Ship/wrap | review clean | `requesting-code-review` → `finishing-a-development-branch` → `caveman-commit` | Opus review |
| Maintenance (post-Jun 29) | — | read-only; `systematic-debugging` ONLY on breakage; ~1 hr/quarter budget | Sonnet |

## Always-on triggers (any phase)

| Situation | Invoke |
|-----------|--------|
| Need library/framework docs (yfinance, streamlit, click, plotly) | `context7` |
| Explore code structure without reading whole files | `smart-explore` |
| A test fails unexpectedly | `systematic-debugging` before any fix |
| About to claim "done / passing / fixed" | `verification-before-completion` — show command output |
| "Did we solve this before?" | `mem-search` |
| Methodology in doubt ("is our approach sound?") | `ds-methodology-review` |
| User wants understanding stress-tested | `grill-me` |

## Hard constraints these rules must never break

1. **No look-ahead bias** — all data timestamps ≤ prediction_time; `LookAheadBiasError` enforced.
2. **No framework imports in domain/** — stdlib only.
3. **Pre-registered gates stay LOCKED** — thresholds never tuned after seeing data; amendments are validity repairs only, recorded in the ADR.
4. **NO new signal hunting** (ADR-052) and **NO auto-retraining/online-learning loops** (wrap spec §5). Unit D stays parked (wrap spec §6).
5. Feature branches only — never commit to `main`/`develop`. Never `--no-verify`.
6. Tests use small fixtures — never hit real APIs in CI.
7. The recommender renders no "buy" language while RESEARCH_ONLY.
```

- [ ] **Step 2: Add pointer in `CLAUDE.md`.** In the "## Phase Status" section, after the line about `docs/STATUS.md`, add:

```markdown
Skill/agent routing per phase: `docs/SKILL_ROUTING.md` (which skill to invoke, which gate must pass).
```

- [ ] **Step 3: Guard hook — DO NOT OVERWRITE.** `.claude/settings.json` ALREADY EXISTS in this repo and wires `.claude/hooks/guardrails.sh`, which blocks `--no-verify`, force-push to main/dev, AND `rm` on `data/`/`reports/` — a SUPERSET of the product-experimentation hook. Overwriting it would strip the data-deletion guards (validated 2026-06-10). Action: read the existing file; if (and only if) the guardrails wiring is somehow absent, add the missing PreToolUse entry alongside what's there. Expected outcome for this step: NO change.

- [ ] **Step 4: Verify + commit**

Run: `python3 -c "import json; json.load(open('.claude/settings.json')); print('valid json')"`
Expected: `valid json`

```bash
git add docs/SKILL_ROUTING.md CLAUDE.md
git commit -m "docs: wire skill routing (dashboard spec §7)"
```

---

### Task 2: `brief_summary.json` serializer + CLI emission

**Files:**
- Create: `application/brief_summary.py`
- Modify: `application/cli.py` (the `weekly_brief` command; insert after `out_path.write_text(to_markdown(brief))`, cli.py:3074 as of 2026-06-11)
- Test: `tests/application/test_brief_summary.py` (create)

- [ ] **Step 1: Write the failing test** — create `tests/application/test_brief_summary.py`:

```python
from application.brief_summary import brief_to_summary_dict
from domain.brief import (
    BuyCandidateLine,
    ConcentrationFlag,
    HoldingVerdictLine,
    ScorecardSnapshot,
    WeeklyBrief,
)
from domain.discipline import Verdict  # validated: domain/discipline.py:38
from domain.regime import Regime  # validated: domain/regime.py:21, UPPERCASE members
from domain.screen_models import ScreenLabel


def _brief(macro=None):
    return WeeklyBrief(
        as_of="2026-06-13",
        regime=Regime.NEUTRAL,
        tilt={"equity": 1.0},
        candidates=(
            BuyCandidateLine(
                ticker="ABC", composite=0.71, factor_summary="value strong",
                why="cheap vs sector", already_held=False,
                label=ScreenLabel.RESEARCH_ONLY,
            ),
        ),
        holdings=(
            HoldingVerdictLine(
                ticker="ARKK", unrealized_pct=-12.0, trend_state="broken",
                verdict=Verdict.REDUCE, why="trend broken, momentum negative",
            ),
        ),
        research_links=(),
        concentration=(ConcentrationFlag(descriptor="Tech 40%", soft_warning=True),),
        scorecard=ScorecardSnapshot(
            screen_window="4w", screen_top_ret=None, screen_spy_ret=None,
            screen_n=0, screen_significant=False, discipline_window="8w",
            discipline_reduce_down_rate=None, discipline_n=42,
            discipline_gate_status="ACCRUING",
        ),
        screen_label=ScreenLabel.RESEARCH_ONLY,
        macro=macro,
    )


def test_summary_dict_has_flags_grouped_and_dates():
    d = brief_to_summary_dict(_brief())
    assert d["as_of"] == "2026-06-13"
    assert d["screen_label"] == "RESEARCH_ONLY"
    assert d["holdings"][0] == {
        "ticker": "ARKK", "verdict": "REDUCE", "unrealized_pct": -12.0,
        "trend_state": "broken", "why": "trend broken, momentum negative",
    }
    assert d["candidates"][0]["ticker"] == "ABC"
    assert d["macro"] is None
    assert d["scorecard"]["discipline_gate_status"] == "ACCRUING"
    assert d["abstained"] is False  # 1 candidate present


def test_summary_dict_abstention_flag():
    b = _brief()
    b = WeeklyBrief(**{**b.__dict__, "candidates": ()})
    d = brief_to_summary_dict(b)
    assert d["abstained"] is True
```

NOTE to implementer: imports validated against the real code 2026-06-10 (Verdict = `domain/discipline.py:38` str-Enum; Regime = `domain/regime.py:21`, UPPERCASE members). The dataclass-rebuild trick in the second test (`WeeklyBrief(**{**b.__dict__, ...})`) is validated: WeeklyBrief is frozen with no `__slots__`.

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/application/test_brief_summary.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'application.brief_summary'`

- [ ] **Step 3: Implement `application/brief_summary.py`:**

```python
"""Serialize a WeeklyBrief to the dashboard-facing structured summary.

The dashboard renders artifacts; it never computes domain logic. This module is
the single place the brief's shape is flattened to JSON-safe primitives.
Written next to the markdown brief (data/personal/ — gitignored, holdings detail).
"""

from __future__ import annotations

from typing import Any

from domain.brief import WeeklyBrief


def brief_to_summary_dict(brief: WeeklyBrief) -> dict[str, Any]:
    macro = brief.macro
    return {
        "as_of": brief.as_of,
        "regime": str(getattr(brief.regime, "value", brief.regime)),
        "screen_label": brief.screen_label.value,
        "abstained": len(brief.candidates) == 0,
        "candidates": [
            {
                "ticker": c.ticker,
                "composite": c.composite,
                "factor_summary": c.factor_summary,
                "why": c.why,
                "already_held": c.already_held,
                "label": c.label.value,
            }
            for c in brief.candidates
        ],
        "holdings": [
            {
                "ticker": h.ticker,
                "verdict": h.verdict.name,
                "unrealized_pct": h.unrealized_pct,
                "trend_state": h.trend_state,
                "why": h.why,
            }
            for h in brief.holdings
        ],
        "concentration": [
            {"descriptor": f.descriptor, "soft_warning": f.soft_warning}
            for f in brief.concentration
        ],
        "scorecard": {
            "screen_window": brief.scorecard.screen_window,
            "screen_n": brief.scorecard.screen_n,
            "screen_significant": brief.scorecard.screen_significant,
            "discipline_window": brief.scorecard.discipline_window,
            "discipline_n": brief.scorecard.discipline_n,
            "discipline_gate_status": brief.scorecard.discipline_gate_status,
        },
        "macro": None
        if macro is None
        else {
            "as_of": macro.as_of,
            "factors": list(macro.factors),
            "net_beta_by_factor": dict(macro.net_beta_by_factor),
            "systematic_share": macro.systematic_share,
            "idiosyncratic_share": macro.idiosyncratic_share,
            "dominant_factor": macro.dominant_factor,
            # MacroBetaFlag is a frozen DATACLASS (domain/models.py:470) with
            # fields kind/factor/message/value/threshold — NOT an Enum. The
            # Risk tab matches on the kind string (e.g. "SYSTEMATIC_DOMINANT").
            "flags": [f.kind for f in macro.flags],
            "coverage_holdings": macro.coverage_holdings,
            "total_holdings": macro.total_holdings,
        },
    }
```

(Validated 2026-06-10: `MacroBetaFlag` accessor is `f.kind` — already correct in the code above.)

- [ ] **Step 4: Wire into the CLI.** In `application/cli.py` `weekly_brief`, after `out_path.write_text(to_markdown(brief))` add:

```python
    import json

    from application.brief_summary import brief_to_summary_dict

    summary_path = out_path.with_name("brief_summary.json")
    summary_path.write_text(json.dumps(brief_to_summary_dict(brief), indent=2))
```

And extend the final echo:

```python
    click.echo(f"Structured summary written to: {summary_path}")
```

- [ ] **Step 5: Run tests green**

Run: `python -m pytest tests/application/test_brief_summary.py -v`
Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
git add application/brief_summary.py application/cli.py tests/application/test_brief_summary.py
git commit -m "feat: weekly-brief writes structured brief_summary.json for the dashboard"
```

---

### Task 3: data_loader additions (summary, latest screen, staleness)

**Files:**
- Modify: `adapters/visualization/data_loader.py`
- Test: `tests/test_dashboard_loaders.py` (create)

- [ ] **Step 1: Write the failing tests** — create `tests/test_dashboard_loaders.py`:

```python
import json
from datetime import date, timedelta

from adapters.visualization.data_loader import (
    load_brief_summary,
    load_latest_screen,
    staleness_days,
)


def test_load_brief_summary_missing_returns_none(tmp_path):
    assert load_brief_summary(str(tmp_path / "nope.json")) is None


def test_load_brief_summary_roundtrip(tmp_path):
    p = tmp_path / "brief_summary.json"
    p.write_text(json.dumps({"as_of": "2026-06-13", "holdings": []}))
    assert load_brief_summary(str(p))["as_of"] == "2026-06-13"


def test_load_latest_screen_picks_newest_and_ignores_ic(tmp_path):
    (tmp_path / "screen_ic_2026-06-08.json").write_text("{}")
    (tmp_path / "screen_2026-06-01.json").write_text(json.dumps({"as_of": "2026-06-01"}))
    (tmp_path / "screen_2026-06-08.json").write_text(json.dumps({"as_of": "2026-06-08"}))
    got = load_latest_screen(str(tmp_path))
    assert got["as_of"] == "2026-06-08"


def test_load_latest_screen_empty_dir(tmp_path):
    assert load_latest_screen(str(tmp_path)) is None


def test_staleness_days():
    nine_ago = (date.today() - timedelta(days=9)).isoformat()
    assert staleness_days(nine_ago) == 9
    assert staleness_days("not-a-date") is None


def test_load_adherence_log_missing_returns_empty(tmp_path):
    from adapters.visualization.data_loader import load_adherence_log

    assert load_adherence_log(str(tmp_path / "nope.jsonl")) == []


def test_load_adherence_log_parses_and_sorts(tmp_path):
    from adapters.visualization.data_loader import load_adherence_log

    p = tmp_path / "adherence_log.jsonl"
    p.write_text(
        '{"ticker": "ARKK", "verdict": "REDUCE", "flag_date": "2026-06-06", '
        '"actual_cut_fraction": 0.0, "label": "IGNORED", "gap_cad": -120.0, '
        '"gap_bps": -8.0}\n'
        "garbage line\n"
        '{"ticker": "XYZ", "verdict": "TRIM", "flag_date": "2026-05-30", '
        '"actual_cut_fraction": 0.5, "label": "FOLLOWED", "gap_cad": 40.0, '
        '"gap_bps": 3.0}\n'
    )
    rows = load_adherence_log(str(p))
    assert [r["ticker"] for r in rows] == ["XYZ", "ARKK"]  # sorted by flag_date
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_dashboard_loaders.py -v`
Expected: FAIL with ImportError (names don't exist)

- [ ] **Step 3: Implement** — append to `adapters/visualization/data_loader.py`:

```python
def load_brief_summary(
    path: str = "data/personal/brief_summary.json",
) -> dict[str, Any] | None:
    """Structured weekly-brief summary written by the weekly-brief CLI."""
    p = Path(path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def load_latest_screen(reports_dir: str = "data/reports") -> dict[str, Any] | None:
    """Newest screen_<date>.json (full ranked distribution). Excludes screen_ic_*."""
    candidates = sorted(
        f
        for f in Path(reports_dir).glob("screen_*.json")
        if not f.name.startswith("screen_ic_")
    )
    if not candidates:
        return None
    try:
        return json.loads(candidates[-1].read_text())
    except (json.JSONDecodeError, OSError):
        return None


def staleness_days(iso_date: str) -> int | None:
    """Days since iso_date (YYYY-MM-DD prefix tolerated). None if unparseable."""
    try:
        then = date.fromisoformat(iso_date[:10])
    except (ValueError, TypeError):
        return None
    return (date.today() - then).days


def load_adherence_log(
    path: str = "data/personal/adherence_log.jsonl",
) -> list[dict[str, Any]]:
    """Resolved Unit C adherence records (append-only JSONL written by the
    adherence-report CLI). Each line: ticker, verdict, flag_date,
    actual_cut_fraction, label, gap_cad, gap_bps. Defensive per-line parse;
    returns [] if the file is absent. Newest flag_date last."""
    p = Path(path)
    if not p.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    rows.sort(key=lambda r: str(r.get("flag_date", "")))
    return rows
```

(Validated 2026-06-11: the file imports `json`, `Path`, `Any` but NOT `date` — add `from datetime import date` to the top import block. Adherence record keys validated against `application/adherence.py` write block.)

- [ ] **Step 4: Run green, commit**

Run: `python -m pytest tests/test_dashboard_loaders.py -v` → 7 passed

```bash
git add adapters/visualization/data_loader.py tests/test_dashboard_loaders.py
git commit -m "feat: dashboard loaders — brief summary, latest screen, staleness"
```

---

### Task 4: Weekly Brief tab rewrite

**Files:**
- Modify: `adapters/visualization/tabs/weekly_brief.py` (full rewrite)
- Test: `tests/test_weekly_brief_tab.py` (extend)

- [ ] **Step 0: Prove ONE headless render test first (validated risk).** NO existing test in this repo calls a tab's `render()` — every current tab test is import-only (`assert callable(render)`). Whether `st.table`/`st.columns`/`st.expander`/`st.metric` work outside a Streamlit runtime in this streamlit version is UNVERIFIED. Before writing the full Task 4 test, write just `test_render_with_summary_fixture` below and run it. If Streamlit raises (`NoSessionContext` / `StreamlitAPIException`), FALL BACK for Tasks 4/5/6/9/10: extract each tab's data-shaping into pure helper functions (e.g. `_rows_for_grade(summary, grade) -> list[dict]`), unit-test THOSE, and keep render() tests import-only per repo convention. Apply whichever pattern Step 0 proves to all later tab tests.

- [ ] **Step 1: Rewrite `adapters/visualization/tabs/weekly_brief.py`:**

```python
"""Weekly Brief tab — the decision cockpit. Renders brief_summary.json."""

from __future__ import annotations

import streamlit as st

from adapters.visualization.data_loader import (
    load_adherence_log,
    load_brief_summary,
    load_weekly_brief,
    staleness_days,
)

_SUMMARY_PATH = "data/personal/brief_summary.json"
_BRIEF_MD_PATH = "data/personal/weekly_brief.md"
_ADHERENCE_PATH = "data/personal/adherence_log.jsonl"
_GRADE_ORDER = ["REDUCE", "TRIM", "REVIEW", "HOLD", "ADD_OK"]
_GRADE_COLOR = {
    "REDUCE": "#DC2626", "TRIM": "#EA580C", "REVIEW": "#CA8A04",
    "HOLD": "#64748B", "ADD_OK": "#16A34A",
}


def render(path: str = _SUMMARY_PATH, adherence_path: str = _ADHERENCE_PATH) -> None:
    st.subheader("Weekly Brief")
    summary = load_brief_summary(path)
    if summary is None:
        st.warning(
            "No structured brief found. Run "
            "`python -m application.cli weekly-brief` to generate it "
            "(stays on your machine)."
        )
        return

    days = staleness_days(summary.get("as_of", ""))
    if days is not None and days > 8:
        st.error(
            f"Brief is {days} days old — run "
            "`python -m application.cli weekly-brief` for a fresh one."
        )

    st.caption(f"As of {summary.get('as_of', '?')} · regime: {summary.get('regime', '?')}")

    # Buy side — abstention is the tool working, not failing.
    if summary.get("abstained", True):
        st.info(
            "Evidence screen: 0 buy candidates met the bar this week — "
            "the screen abstained (RESEARCH_ONLY, no buy language)."
        )

    # Discipline flags grouped most-urgent first.
    holdings = summary.get("holdings", [])
    for grade in _GRADE_ORDER:
        rows = [h for h in holdings if h.get("verdict") == grade]
        if not rows:
            continue
        st.markdown(
            f'<span style="color:{_GRADE_COLOR[grade]};font-weight:700;">'
            f"{grade}</span> · {len(rows)}",
            unsafe_allow_html=True,
        )
        st.table(
            [
                {
                    "Ticker": h["ticker"],
                    "Unrealized %": f"{h.get('unrealized_pct', 0):+.1f}%",
                    "Trend": h.get("trend_state", "?"),
                    "Why": h.get("why", ""),
                }
                for h in rows
            ]
        )

    # Adherence tracker (Unit C, shipped 2026-06-10): tool-said vs you-did,
    # resolved at the 21-day horizon. Advisory only (L0), descriptive — no
    # significance claims (Unit C Interpretation limits).
    st.markdown("**Adherence tracker** — tool-said vs you-did (resolved, 21d horizon)")
    adherence = load_adherence_log(adherence_path)
    if not adherence:
        st.caption(
            "No resolved adherence records yet. Run "
            "`python -m application.cli adherence-report` after flags age 21 days "
            "(records stay on your machine)."
        )
    else:
        st.table(
            [
                {
                    "Flagged": r.get("flag_date", "?"),
                    "Ticker": r.get("ticker", "?"),
                    "Verdict": r.get("verdict", "?"),
                    "You did": r.get("label", "?"),
                    "Cut": f"{r.get('actual_cut_fraction', 0) * 100:.0f}%",
                    "Gap (CAD)": f"{r.get('gap_cad', 0):+.0f}",
                    "Gap (bps)": f"{r.get('gap_bps', 0):+.1f}",
                }
                for r in adherence[-12:]
            ]
        )
        st.caption(
            "Gap = counterfactual CAD difference if you had cut per the verdict "
            "(f=0.5). Descriptive, underpowered by design."
        )

    with st.expander("Full markdown brief"):
        md = load_weekly_brief(_BRIEF_MD_PATH)
        st.markdown(md if md else "_No markdown brief found._")
```

- [ ] **Step 2: Extend `tests/test_weekly_brief_tab.py`** — keep the existing render-importable test; add:

```python
def test_render_with_summary_fixture(tmp_path, monkeypatch):
    import json

    p = tmp_path / "brief_summary.json"
    p.write_text(json.dumps({
        "as_of": "2026-06-13", "regime": "neutral", "abstained": True,
        "holdings": [{"ticker": "ARKK", "verdict": "REDUCE",
                      "unrealized_pct": -12.0, "trend_state": "broken",
                      "why": "trend broken"}],
    }))
    from adapters.visualization.tabs import weekly_brief

    weekly_brief.render(path=str(p))  # must not raise outside streamlit runtime


def test_render_with_adherence_log(tmp_path):
    import json

    p = tmp_path / "brief_summary.json"
    p.write_text(json.dumps({"as_of": "2026-06-13", "regime": "neutral",
                             "abstained": True, "holdings": []}))
    a = tmp_path / "adherence_log.jsonl"
    a.write_text(json.dumps({
        "ticker": "ARKK", "verdict": "REDUCE", "flag_date": "2026-05-16",
        "actual_cut_fraction": 0.0, "label": "IGNORED",
        "gap_cad": -120.0, "gap_bps": -8.0,
    }) + "\n")
    from adapters.visualization.tabs import weekly_brief

    weekly_brief.render(path=str(p), adherence_path=str(a))  # must not raise
```

(Streamlit calls run headless outside a server — they no-op or warn. If `st.table` raises outside runtime in this repo's streamlit version, wrap the call in the existing test pattern used by `tests/test_phase5_tabs.py` — follow that file's convention.)

- [ ] **Step 3: Run, commit**

Run: `python -m pytest tests/test_weekly_brief_tab.py tests/test_dashboard_loaders.py -q` → all pass

```bash
git add adapters/visualization/tabs/weekly_brief.py tests/test_weekly_brief_tab.py
git commit -m "feat: Weekly Brief tab — structured cockpit with flags, abstention, staleness"
```

---

### Task 5: Research Candidates tab (new)

**Files:**
- Create: `adapters/visualization/tabs/research_candidates.py`
- Test: `tests/test_research_candidates_tab.py` (create)

- [ ] **Step 1: Create the tab:**

```python
"""Research Candidates tab — factual evidence ranking. RESEARCH_ONLY, no buy language."""

from __future__ import annotations

import streamlit as st

from adapters.visualization.data_loader import load_latest_screen, staleness_days

_TOP_N = 15

_DISCLAIMER = (
    "Ranked by **current factual evidence** (valuation · quality · health) — "
    "**NOT predicted returns**. Prediction was tested 2006–2024 and falsified "
    "(see the Falsification Lab tab)."
)


def render(reports_dir: str = "data/reports") -> None:
    st.subheader("Research Candidates")
    st.markdown(_DISCLAIMER)

    screen = load_latest_screen(reports_dir)
    if screen is None:
        st.warning(
            "No screen report found. Run "
            "`python -m application.cli screen-candidates` to generate one."
        )
        return

    days = staleness_days(screen.get("as_of", ""))
    if days is not None and days > 8:
        st.error(f"Screen is {days} days old — re-run `screen-candidates`.")

    if screen.get("abstained"):
        st.info(
            "The evidence screen ABSTAINED — no name met the evidence bar. "
            "That is the tool working, not failing."
        )

    candidates = screen.get("candidates", [])[:_TOP_N]
    if not candidates:
        st.caption("No ranked candidates in the latest report.")
        return

    st.caption(
        f"Top {len(candidates)} of {screen.get('universe_size', '?')} by factual "
        f"composite · as of {screen.get('as_of', '?')} · label: "
        f"{screen.get('candidates', [{}])[0].get('label', 'RESEARCH_ONLY')}"
    )
    for i, c in enumerate(candidates, start=1):
        factors = c.get("factor_scores", [])
        # percentile is a 0-1 FRACTION in the screen JSON (domain/screen_models.py,
        # mirrored by domain/brief.py:112 which renders int(round(p*100))).
        chips = " · ".join(
            f"{f.get('name', '?')} p{f.get('percentile', 0) * 100:.0f}" for f in factors
        )
        st.markdown(
            f"**{i}. {c.get('ticker', '?')}** — composite {c.get('composite', 0):.2f}  \n"
            f"{chips}  \n"
            f"_{c.get('why', '')}_ — research it in the Stock Analysis tab."
        )
        st.divider()
```

(Validated 2026-06-10 against `application/cli.py:2521-2546`: serialized keys are `as_of`, `universe_size`, `abstained`, `candidates[].{ticker, composite, trend_health, label, why, factor_scores[].{name, value, percentile, contribution}}` — the accessors above match; percentile is the 0-1 fraction handled above.)

- [ ] **Step 2: Test** — create `tests/test_research_candidates_tab.py`:

```python
import json


def test_render_with_screen_fixture(tmp_path):
    (tmp_path / "screen_2026-06-13.json").write_text(json.dumps({
        "as_of": "2026-06-13", "universe_size": 430, "abstained": False,
        "candidates": [{
            "ticker": "ABC", "composite": 0.71, "why": "cheap vs sector",
            "label": "RESEARCH_ONLY",
            "factor_scores": [{"name": "value", "percentile": 88.0}],
        }],
    }))
    from adapters.visualization.tabs import research_candidates

    research_candidates.render(reports_dir=str(tmp_path))


def test_render_empty_dir_no_raise(tmp_path):
    from adapters.visualization.tabs import research_candidates

    research_candidates.render(reports_dir=str(tmp_path))
```

- [ ] **Step 3: Run, commit**

Run: `python -m pytest tests/test_research_candidates_tab.py -q` → 2 passed

```bash
git add adapters/visualization/tabs/research_candidates.py tests/test_research_candidates_tab.py
git commit -m "feat: Research Candidates tab — factual top-15, abstention-proud, RESEARCH_ONLY"
```

---

### Task 6: Risk tab (new)

**Files:**
- Create: `adapters/visualization/tabs/risk.py`
- Test: `tests/test_risk_tab.py` (create)

- [ ] **Step 1: Create the tab:**

```python
"""Risk tab — Unit A macro-beta scrubber, promoted from CLI markdown."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from adapters.visualization.data_loader import load_brief_summary

_FLAG_MEANING = {
    "SYSTEMATIC_DOMINANT": (
        "Most of the book's movement is one market-wide bet, not stock picking.",
        "Adding 'one more name' will not diversify this — only a different asset class or hedge changes it.",
    ),
    "FACTOR_DOMINANCE": (
        "One macro factor (e.g. the market or rates) explains an outsized share of risk.",
        "Check whether you MEANT to make that macro bet; trim names that all load on it if not.",
    ),
    "DRIFT": (
        "The book's factor mix moved materially since the last review.",
        "Re-read the latest weekly brief and confirm the new tilt is intentional.",
    ),
}


def render(path: str = "data/personal/brief_summary.json") -> None:
    st.subheader("Portfolio Risk — Macro-Beta Scrubber")
    st.caption("Heuristic surfacing dials, not validated edges (ADR-052).")

    summary = load_brief_summary(path)
    macro = (summary or {}).get("macro")
    if macro is None:
        st.warning(
            "No macro-beta data. Run `python -m application.cli weekly-brief` "
            "(the scrubber runs inside it)."
        )
        return

    betas: dict[str, float] = macro.get("net_beta_by_factor", {})
    dominant = macro.get("dominant_factor")

    cols = st.columns(3)
    spy_beta = betas.get("SPY")
    cols[0].metric("Net market beta (SPY)", f"{spy_beta:+.2f}" if spy_beta is not None else "n/a")
    cols[1].metric("Systematic share", f"{macro.get('systematic_share', 0):.0%}")
    cols[2].metric("Dominant factor", dominant or "none")

    if betas:
        fig = go.Figure(go.Bar(x=list(betas.keys()), y=list(betas.values())))
        fig.update_layout(title="Dollar-weighted net beta by factor", height=320)
        st.plotly_chart(fig, use_container_width=True)

    sys_share = float(macro.get("systematic_share", 0.0))
    donut = go.Figure(
        go.Pie(
            labels=["Systematic (macro)", "Idiosyncratic (stock-specific)"],
            values=[sys_share, max(0.0, 1.0 - sys_share)],
            hole=0.55,
        )
    )
    donut.update_layout(title="Where the book's risk comes from", height=320)
    st.plotly_chart(donut, use_container_width=True)

    for flag in macro.get("flags", []):
        meaning, action = _FLAG_MEANING.get(
            flag, ("Unrecognized flag.", "See the weekly brief markdown for detail.")
        )
        st.markdown(f"**{flag}** — {meaning}  \n_What you might do:_ {action}")

    st.caption(
        f"Coverage: {macro.get('coverage_holdings', '?')}/{macro.get('total_holdings', '?')} holdings."
    )
```

- [ ] **Step 2: Test** — create `tests/test_risk_tab.py`:

```python
import json


def _summary(tmp_path, macro):
    p = tmp_path / "brief_summary.json"
    p.write_text(json.dumps({"as_of": "2026-06-13", "macro": macro}))
    return str(p)


def test_render_with_macro(tmp_path):
    from adapters.visualization.tabs import risk

    risk.render(path=_summary(tmp_path, {
        "net_beta_by_factor": {"SPY": 1.39, "TLT": -0.2},
        "systematic_share": 0.63, "idiosyncratic_share": 0.37,
        "dominant_factor": "SPY", "flags": ["SYSTEMATIC_DOMINANT"],
        "coverage_holdings": 60, "total_holdings": 66,
    }))


def test_render_without_macro_no_raise(tmp_path):
    from adapters.visualization.tabs import risk

    risk.render(path=_summary(tmp_path, None))
```

- [ ] **Step 3: Run, commit**

Run: `python -m pytest tests/test_risk_tab.py -q` → 2 passed

```bash
git add adapters/visualization/tabs/risk.py tests/test_risk_tab.py
git commit -m "feat: Risk tab — macro-beta hero metrics, factor bars, variance donut, plain-English flags"
```

---

### Task 7: Stock Analysis reframe (RESEARCH_ONLY)

**Files:**
- Modify: `adapters/visualization/tabs/stock_analysis.py` (`_render_verdict` ~line 130–236, `_render_sentiment` ~line 512)
- Test: existing stock-analysis tests must stay green; add one assertion test

- [ ] **Step 1: Reframe `_render_verdict`.** Keep the company header block (name/price/market cap, lines ~132–151) UNCHANGED. Also KEEP the factual **Analyst Consensus card** (~lines 198–218) and the **+Watchlist / +Portfolio buttons** (~lines 220–229) — they are factual/functional, not falsified machinery (spec §2.5: keep factual content). Replace ONLY the radar + System-Verdict columns block (from the "Radar + verdict side by side" comment up to where the Analyst Consensus section begins) with:

```python
    # RESEARCH_ONLY reframe (dashboard spec §2.5): no grade, no conviction,
    # no radar — prediction was falsified (ADR-039..050, ADR-053).
    st.markdown(
        '<div class="ws-card" style="padding:12px 16px;margin-bottom:12px;">'
        '<span style="font-weight:700;color:#CA8A04;">RESEARCH ONLY</span> — '
        "descriptive data below; this tool makes no buy/sell call. "
        "Why: every predictive signal tested 2006–2024 was falsified "
        "(see the Falsification Lab tab)."
        "</div>",
        unsafe_allow_html=True,
    )
```

Then delete the now-unused helpers `_grade_color` and the radar import/usage IF nothing else references them (`grep -n "signal_radar\|_grade_color" adapters/visualization/ -r` first; `stock_analyzer.py` may still compute `signal_scores` — leave the analyzer alone, only the tab stops rendering it).

- [ ] **Step 2: Sentiment caption.** In `_render_sentiment`, directly under the `st.markdown("#### 6. Sentiment")` line, add:

```python
    st.caption(
        "Descriptive buzz only — predictive value was tested and falsified "
        "(ADR-044: no cross-sectional IC on a clean 430-ticker universe)."
    )
```

- [ ] **Step 3: Add a regression test** (append to the existing stock-analysis test file — find it with `grep -rln "stock_analysis" tests/`):

```python
def test_verdict_reframe_has_no_grade_language():
    import inspect

    from adapters.visualization.tabs import stock_analysis

    src = inspect.getsource(stock_analysis._render_verdict)
    assert "RESEARCH ONLY" in src
    assert "System Verdict" not in src
    assert "conviction" not in src.lower()
```

- [ ] **Step 4: Run, commit**

Run: `python -m pytest tests/ -q -k "stock_analysis or charts" 2>&1 | tail -3` — no new failures vs baseline

```bash
git add adapters/visualization/tabs/stock_analysis.py tests/
git commit -m "refactor: Stock Analysis verdict reframed RESEARCH_ONLY; sentiment honesty caption"
```

---

### Task 8: My Portfolio absorbs Watchlist

**Files:**
- Modify: `adapters/visualization/tabs/positions.py`
- Delete: `adapters/visualization/tabs/watchlist.py`
- Test: `tests/test_watchlist_portfolio.py` (update imports to positions)

- [ ] **Step 1:** Open `tabs/watchlist.py`, copy its body into a private `_render_watchlist_section()` in `positions.py`, called at the END of positions' `render()` inside `with st.expander("Watchlist"):`. Keep the data access (`load_watchlist`) identical.
- [ ] **Step 2:** Delete `adapters/visualization/tabs/watchlist.py`. Update `tests/test_watchlist_portfolio.py`: any import of `tabs.watchlist` now imports `tabs.positions` and asserts `_render_watchlist_section` exists/renders with a tmp DB fixture (follow the file's existing fixture pattern).
- [ ] **Step 3:** Run: `python -m pytest tests/test_watchlist_portfolio.py -q` → pass. Commit:

```bash
git add -A adapters/visualization/tabs/ tests/test_watchlist_portfolio.py
git commit -m "refactor: fold Watchlist into My Portfolio tab; delete watchlist tab"
```

---

### Task 9: Falsification Lab tab (new)

**Files:**
- Create: `adapters/visualization/tabs/falsification_lab.py`
- Test: `tests/test_falsification_lab_tab.py` (create)

- [ ] **Step 1: Create the tab:**

```python
"""Falsification Lab — the verdict scoreboard, exhibits, and the one live experiment."""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

_SCOREBOARD = [
    {
        "hypothesis": "Does community conviction predict returns out of sample?",
        "test": "Pre-registered OOS conviction backtest",
        "verdict": "KILL", "adr": "docs/adr/039-conviction-validation-findings.md",
    },
    {
        "hypothesis": "Do conviction sub-dimensions carry independent signal?",
        "test": "Dimension-by-dimension IC audit",
        "verdict": "KILL", "adr": "docs/adr/043-conviction-dims-dead-divergence-led-surfacing.md",
    },
    {
        "hypothesis": "Does sentiment-vs-price divergence predict returns?",
        "test": "Cross-sectional IC, clean 430-ticker universe",
        "verdict": "KILL", "adr": "docs/adr/044-divergence-ic-verdict.md",
    },
    {
        "hypothesis": "Do momentum exits beat buy-and-hold risk-adjusted?",
        "test": "Sharpe-difference bootstrap (CI spans 0)",
        "verdict": "KILL", "adr": "docs/adr/046-momentum-discipline-phase1-verdict.md",
    },
    {
        "hypothesis": "Does the evidence screen's top decile outperform?",
        "test": "Screen IC forward test",
        "verdict": "INCONCLUSIVE", "adr": "docs/adr/049-decision-support-engine-architecture.md",
    },
    {
        "hypothesis": "Does a trend-following sleeve clear the pre-registered bar?",
        "test": "TSMOM sleeve backtest vs locked gate",
        "verdict": "INCONCLUSIVE", "adr": "docs/adr/050-trend-following-sleeve-verdict.md",
    },
]

_VERDICT_COLOR = {"KILL": "#DC2626", "INCONCLUSIVE": "#CA8A04", "PASS": "#16A34A",
                  "PENDING": "#64748B"}

# Unit B's report verdict string is INCONCLUSIVE_THIN_COVERAGE (validated against
# data/reports/insider_cluster_falsification_2024.json, 2026-06-11). Per ADR-053
# this resolved to a PRACTICAL KILL via the survivorship-honest coverage guard.
# Map the raw verdict -> (display label, color key) so the scoreboard renders amber
# and states the practical-kill outcome, not a gray "unrecognized" fallback.
_VERDICT_DISPLAY = {
    "INCONCLUSIVE_THIN_COVERAGE": ("INCONCLUSIVE → practical KILL", "INCONCLUSIVE"),
}


def _unit_b_row(report_path: str) -> dict[str, str]:
    row = {
        "hypothesis": "Do insider buying clusters in sub-$1B names predict 21-day returns?",
        "test": "Event study vs liquidity-matched ETF, pre-registered coverage guard",
        "verdict": "PENDING", "adr": "docs/adr/053-insider-cluster-falsification-verdict.md",
    }
    p = Path(report_path)
    if p.exists():
        try:
            raw = str(json.loads(p.read_text()).get("verdict", "PENDING"))
            label, _ = _VERDICT_DISPLAY.get(raw, (raw, raw))
            row["verdict"] = label
        except (json.JSONDecodeError, OSError):
            pass
    return row


def _gate_strip(log_path: str) -> None:
    p = Path(log_path)
    if not p.exists():
        st.caption("Forward gate: no discipline log yet.")
        return
    dates = set()
    for line in p.read_text().splitlines():
        try:
            dates.add(json.loads(line).get("as_of", "")[:10])
        except json.JSONDecodeError:
            continue
    dates.discard("")
    st.markdown("**The one live experiment — discipline forward gate (ADR-048/051)**")
    # Targets validated against application/calibration_readiness.py (2026-06-11):
    # k_dates=3 distinct dates >=10 days apart, n_min=30 resolved flags. Rendered
    # as static text — the dashboard never recomputes readiness (domain logic
    # stays in the discipline-calibration-status CLI).
    st.caption(
        f"{len(dates)} weekly review dates accrued · gate needs ≥30 resolved "
        "REDUCE flags across ≥3 dates ≥10 days apart (ADR-051) · resolves "
        "~mid-July 2026 — evidence accrues weekly with zero code changes."
    )


def render(
    report_path: str = "data/reports/insider_cluster_falsification_2024.json",
    log_path: str = "data/personal/discipline_log.jsonl",
) -> None:
    st.subheader("Falsification Lab")
    st.markdown(
        "Most dashboards show what works. This one also shows what **doesn't** — "
        "every hypothesis below was tested with thresholds locked **before** "
        "seeing results (pre-registration), so a kill is a kill."
    )

    rows = _SCOREBOARD + [_unit_b_row(report_path)]
    for r in rows:
        # Color by the leading verdict token so display labels like
        # "INCONCLUSIVE → practical KILL" still resolve to the amber key.
        color = _VERDICT_COLOR.get(r["verdict"].split()[0], "#64748B")
        st.markdown(
            f'<span style="color:{color};font-weight:700;">{r["verdict"]}</span> — '
            f'**{r["hypothesis"]}**  \n'
            f'_{r["test"]}_ · `{r["adr"]}`',
            unsafe_allow_html=True,
        )
        st.divider()

    _gate_strip(log_path)
```

(All seven `adr` paths validated to exist 2026-06-10, including `039-conviction-validation-findings.md`. Unit B's verdict is FINAL = `INCONCLUSIVE_THIN_COVERAGE` → practical KILL (ADR-053, validated 2026-06-11); the old "if PASS, add paper-log expander" branch is DEAD — do not build it. EXHIBITS are REQUIRED by spec §2.6, not optional: transplant `_render_ablation` and `_render_shap` from `tabs/model_confidence.py` (lines ~370 and ~408, both use data_loader and transplant cleanly — validated) into this file, each preceded by `st.caption("FALSIFIED-era artifact — kept as exhibit")`, rendered between the scoreboard and the gate strip.)

- [ ] **Step 2: Test** — create `tests/test_falsification_lab_tab.py`:

```python
import json


def test_unit_b_row_pending_when_missing(tmp_path):
    from adapters.visualization.tabs.falsification_lab import _unit_b_row

    assert _unit_b_row(str(tmp_path / "nope.json"))["verdict"] == "PENDING"


def test_unit_b_row_reads_verdict(tmp_path):
    p = tmp_path / "r.json"
    p.write_text(json.dumps({"verdict": "KILL"}))
    from adapters.visualization.tabs.falsification_lab import _unit_b_row

    assert _unit_b_row(str(p))["verdict"] == "KILL"


def test_unit_b_row_maps_real_thin_coverage_verdict(tmp_path):
    # The actual report verdict string -> practical-kill display label (ADR-053).
    p = tmp_path / "r.json"
    p.write_text(json.dumps({"verdict": "INCONCLUSIVE_THIN_COVERAGE"}))
    from adapters.visualization.tabs.falsification_lab import _unit_b_row

    assert _unit_b_row(str(p))["verdict"] == "INCONCLUSIVE → practical KILL"


def test_render_no_raise(tmp_path):
    from adapters.visualization.tabs import falsification_lab

    falsification_lab.render(
        report_path=str(tmp_path / "nope.json"),
        log_path=str(tmp_path / "nope.jsonl"),
    )
```

- [ ] **Step 3: Run, commit**

Run: `python -m pytest tests/test_falsification_lab_tab.py -q` → 4 passed

```bash
git add adapters/visualization/tabs/falsification_lab.py tests/test_falsification_lab_tab.py
git commit -m "feat: Falsification Lab tab — verdict scoreboard, Unit B live row, gate strip"
```

---

### Task 10: Methodology tab (new, static)

**Files:**
- Create: `adapters/visualization/tabs/methodology.py`
- Test: add render-no-raise test to `tests/test_falsification_lab_tab.py`'s pattern in a new file `tests/test_methodology_tab.py`

- [ ] **Step 1: Create the tab** — static markdown, zero data deps:

```python
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
```

- [ ] **Step 2: Test + commit**

```python
# tests/test_methodology_tab.py
def test_render_no_raise():
    from adapters.visualization.tabs import methodology

    methodology.render()
```

Run: `python -m pytest tests/test_methodology_tab.py -q` → 1 passed

```bash
git add adapters/visualization/tabs/methodology.py tests/test_methodology_tab.py
git commit -m "feat: Methodology tab — plain-language honesty explainer + glossary"
```

---

### Task 11: Router rewrite + deletions

**Files:**
- Modify: `adapters/visualization/dashboard.py`
- Delete: `adapters/visualization/tabs/command_center.py`, `tabs/market_pulse.py`, `tabs/model_confidence.py`
- Modify/Delete tests: `tests/test_phase5_tabs.py`, any test importing deleted modules

- [ ] **Step 1: Salvage check before deleting.** The exhibit transplant (`_render_ablation`, `_render_shap` → `falsification_lab.py`) is REQUIRED and already done in Task 9. Here, verify nothing else still imports the doomed modules: `grep -rn "command_center\|market_pulse\|model_confidence" adapters/ application/ tests/ --include="*.py" | grep -v tabs/` — resolve any live imports first; do not leave dangling imports.

- [ ] **Step 2: Rewrite `dashboard.py` tab block:**

```python
tab0, tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
    [
        "Weekly Brief",
        "Research Candidates",
        "Risk",
        "My Portfolio",
        "Stock Analysis",
        "Falsification Lab",
        "Methodology",
    ]
)

with tab0:
    from adapters.visualization.tabs.weekly_brief import render as render_brief

    render_brief()
with tab1:
    from adapters.visualization.tabs.research_candidates import render as render_candidates

    render_candidates()
with tab2:
    from adapters.visualization.tabs.risk import render as render_risk

    render_risk()
with tab3:
    from adapters.visualization.tabs.positions import render as render_portfolio

    render_portfolio()
with tab4:
    from adapters.visualization.tabs.stock_analysis import render as render_analysis

    render_analysis()
with tab5:
    from adapters.visualization.tabs.falsification_lab import render as render_lab

    render_lab()
with tab6:
    from adapters.visualization.tabs.methodology import render as render_methodology

    render_methodology()
```

- [ ] **Step 3: Delete** `tabs/command_center.py`, `tabs/market_pulse.py`, `tabs/model_confidence.py`. Then `python -m pytest tests/ -q 2>&1 | tail -5`; delete or update every test module that imported the deleted tabs (`tests/test_phase5_tabs.py` parts, etc.) — keep tests of chart builders that survived in `components/charts.py`.

- [ ] **Step 4: Full suite + commit**

Run: `python -m pytest tests/ -q 2>&1 | tail -3` — no new failures vs the Task-preconditions baseline.

```bash
git add -A
git commit -m "feat: 7-tab honest cockpit router; delete falsified-era tabs (~1,400 lines)"
```

---

### Task 11.5: Wire artifact refresh into the Saturday job (closes the pipeline gap)

**Why (validated 2026-06-11):** `scripts/discipline_weekly_review.sh` runs holdings-risk /
resolve-flags / calibration-status / adherence-report but NOT `weekly-brief` or
`screen-candidates`. The spec assumed the hardening plan would add `screen-candidates`;
it did not. Without this task, `brief_summary.json` (Tabs 1+3) and `screen_<date>.json`
(Tab 2) never refresh — `data/reports/` currently has NO `screen_*.json` at all (only
`screen_ic_*`), so Research Candidates would warn forever.

**Files:**
- Modify: `scripts/discipline_weekly_review.sh`

- [ ] **Step 1:** Append two steps to the script block (after step 4, same `$PYTHON -m application.cli` pattern; both commands have working defaults — validated `weekly-brief` opts: `--market us --holdings <csv> --out data/personal/weekly_brief.md --report-dir data/reports/`; it writes `brief_summary.json` next to the markdown from Task 2 onward):

```bash
  echo "--- 5. weekly brief (markdown + brief_summary.json for the dashboard) ---"
  "$PYTHON" -m application.cli weekly-brief --holdings "$HOLDINGS"
  echo "--- 6. evidence screen (full ranked screen_<date>.json for the dashboard) ---"
  "$PYTHON" -m application.cli screen-candidates
```

Also update the header comment block (steps list) to mention 5 and 6.

- [ ] **Step 2:** Verify: `bash -n scripts/discipline_weekly_review.sh` → exit 0. Commit:

```bash
git add scripts/discipline_weekly_review.sh
git commit -m "feat: Saturday job refreshes brief_summary.json + screen_<date>.json for the dashboard"
```

---

### Task 12: Smoke the real app + finish

- [ ] **Step 1: UI polish pass.** Invoke the `frontend-design` skill and sweep all 7 tabs
  against the "UI treatment — anti-flat" requirements at the top of this plan: ws-cards,
  hero metrics, pills, consistent Plotly theme, left-border verdict accents. The dashboard
  must read as a designed product (SWST language), not stacked default-Streamlit widgets.
- [ ] **Step 2:** `streamlit run adapters/visualization/dashboard.py` locally; click all 7 tabs; verify fail-loud warnings appear where artifacts are missing and no tab crashes. (If running headless, `streamlit run --server.headless true` + curl the port for HTTP 200.)
- [ ] **Step 3:** `pre-commit run --all-files` → all pass.
- [ ] **Step 4:** Invoke `superpowers:finishing-a-development-branch` → PR `feat/dashboard-realignment` → `develop`.

---

## Validation status

Independently validated (Opus reviewer, 2026-06-10) against the real codebase; all
8 findings fixed in this revision:
1. `.claude/settings.json` already exists with a SUPERSET guard hook (guardrails.sh
   blocks rm on data//reports/) — T1 no longer overwrites it.
2. `MacroBetaFlag` is a dataclass — serializer uses `f.kind` (T2).
3. `FactorScore.percentile` is a 0–1 fraction — chips render `*100` (T5).
4. `Verdict` import = `domain.discipline`; `Regime` = `domain.regime`, UPPERCASE (T2).
5. `data_loader.py` lacks `date` import — instruction added (T3).
6. T7 preserves the factual Analyst Consensus card + action buttons.
7. No repo test calls `render()` — T4 Step 0 proves headless viability first, with a
   pure-helper fallback pattern for all tab tests.
8. ADR-039 path corrected; exhibits made REQUIRED per spec §2.6 (T9/T11).

Confirmed-correct by the same review: CLI insert anchor (cli.py:2947), screen JSON
key names (cli.py:2521–2546), brief_summary writer↔reader key contracts, loader
signatures T3↔T4/5/6, all scoreboard ADR paths, frozen-dataclass rebuild in T2's
test, `discipline_log.jsonl` line shape (`as_of` key).

### Post-merge amendments (2026-06-11, after Unit C + hardening landed on develop)

Re-validated every anchor against develop @ post-PR-#37/#38. All still hold; only
positions drifted (text anchors used, not line numbers). Two substantive fixes:

- **T9 Unit B verdict (was stale):** real report verdict string is
  `INCONCLUSIVE_THIN_COVERAGE`, NOT a generic "INCONCLUSIVE"/"PASS". `_unit_b_row`
  now maps it to display label "INCONCLUSIVE → practical KILL" (ADR-053) and the
  scoreboard colors by leading token so it renders amber, not gray. PASS/paper-log
  branch removed (dead). New test `test_unit_b_row_maps_real_thin_coverage_verdict`.
- **T4 adherence (was a placeholder caption):** Unit C shipped 2026-06-10, so the
  "arrives with Unit C" placeholder is replaced by a real `load_adherence_log`
  loader (T3) + adherence table in the Weekly Brief tab, reading
  `data/personal/adherence_log.jsonl` (keys validated against
  `application/adherence.py`). New loader tests (T3) + populated-render test (T4).

Net test-count deltas: T3 5→7, T4 +1, T9 3→4. CLI anchor now cli.py:3074
(`out_path.write_text(to_markdown(brief))`); screen serializer ~cli.py:2623–2653.

### Thoroughness review round 2 (2026-06-11, spec↔plan↔code cross-check)

- **Task 11.5 ADDED (pipeline gap):** Saturday job never ran `weekly-brief` /
  `screen-candidates`; no `screen_*.json` exists in data/reports. Spec §2.2 had
  assigned this to the hardening plan, which didn't do it. Without 11.5, Tabs 1/2/3
  show stale/missing warnings forever.
- **T9 gate strip:** now states the gate's real targets (≥30 resolved across ≥3 dates
  ≥10 days apart — `application/calibration_readiness.py` k_dates=3/d_days=10/n_min=30)
  as static text; dashboard still computes no domain logic.
- **UI treatment section ADDED (user requirement):** anti-flat — ws-cards, hero
  metrics/`render_verdict_card`, `status_pill_html` pills, consistent Plotly theme,
  verdict left-border accents, `frontend-design` polish pass in T12 (all component
  symbols validated to exist in `components/{metrics,formatters}.py` + styles.py).
- Spec updated with a matching Addendum section (plan supersedes §2.1/§2.2/§2.6/§7).
```
