# Screener Legibility — Design Spec

**Date:** 2026-06-13
**Status:** Locked (v3 mockup)
**Branch:** `feat/per-stock-decision-card`
**Mockups:** `.superpowers/brainstorm/screener/content/screener-v1..v3.html` (v3 = locked). v1 = funnel/abstention; v2 = honest momentum-only composite + hover; v3 = diagnostic gate + research-action read.
**Sibling specs:** home-triage, per-stock-decision-card, risk-rubric (all 2026-06-13). This is the 4th and final redesign spec.
**Relevant ADRs:** 045 (pivot prediction→discipline), 047 (alpha-hunt complete), 052 (CRO direction / alpha-hunt closed → screen is RESEARCH_ONLY, not validated).

## 1. Problem

The Screener shows **"0 cleared"** and reads as broken/empty to a non-expert. The redesign goal is legibility — but an investigation (below) found that **the 0 is NOT safe to frame as disciplined abstention**: it is most likely a *thin price-feed*, not the market offering nothing. So this spec has two coupled work-streams: **(A) fix/diagnose the logic**, then **(B) make it legible on truth**.

## 2. Investigation findings (evidence, 2026-06-13 — ROOT CAUSE CONFIRMED LIVE)

- `data/reports/screen_2026-06-11.json`: **universe_size 512, candidates 0, abstained False**. 0 candidates with `abstained=False` ⇒ `raw` was empty ⇒ **nothing passed `eligible()`** (`has_min_history` AND `trend_health > 0`) — filtered before scoring.
- **Live gate diagnostic (80-ticker sample):** `has_min_history` TRUE for **96%** (feed is healthy, NOT thin) — but **`trend_health` returned exactly `0.000` for all 80** (min=med=max=0.000). So `eligible()` (`trend_health > 0`) passes nobody, every week.
- **ROOT CAUSE — a silent field-name bug, not discipline and not a thin feed.** The screen price adapter (`application/cli.py`) reads **`s.close`**, but `domain.models.Signal` exposes **`s.price`** (with `open_`/`high`/`low`). Affects two methods, both behind **bare `except: return <empty>`**:
  - `trend_health` (cli.py:2496) → `[s.close for s in signals]` raises `AttributeError` → swallowed → returns `0.0` for every ticker.
  - `monthly_closes` (cli.py:2481) → same `AttributeError` → returns `[]` → momentum dead too.
- **Verified fix:** swapping `s.close → s.price` recovers real values — `trend_health` for AAPL/MSFT/JPM/NVDA/KO/XOM/JNJ/WMT = `3.52 / -5.02 / 2.33 / 1.89 / 6.15 / 3.23 / 5.93 / 1.59` → **7/8 above trend**, consistent with RISK_ON. The screen produces candidates once fixed.
- **Lesson:** the bare excepts turned a hard crash into a permanent silent zero. The fix MUST narrow them so this class of failure surfaces (raise or log, never swallow to a neutral value).
- **Composite is momentum-only by construction:** `composite_score` (domain/factor_scores.py) is an equal-weight mean over `FACTOR_KEYS = (momentum, revision, quality, value)` where `None → 0.0`; revision/quality/value are permanent **DATA-GAP** (need point-in-time fundamentals, see `application/screen_ic_panels.py`). So composite ≈ **momentum ÷ 4**, range ≈ −0.7…+0.7.
- **Two contradictory `abstained` definitions:**
  - `application/evidence_screen_use_case.py:167` → `abstained = abstain_if_thin(min(present_fractions))` → momentum-only = 0.25 < 0.5 → **always True**.
  - `application/brief_summary.py:21` → `abstained = (len(candidates) == 0)`.
  - The dashboard reads the brief, conflating "empty" with "abstained." **Bug: pick one definition.**

## 3. Work-stream A — fix + diagnostic (pure domain first)

**A0. FIX THE SCREEN (confirmed bug, do first, own concern).** In the `application/cli.py` price adapter: `s.close → s.price` in **both** `trend_health` and `monthly_closes`. **Narrow the bare `except`** in each so a future attribute/shape error raises or logs instead of silently returning `0.0`/`[]`. TDD: add a test feeding `Signal` fixtures (with `.price/.high/.low`) and asserting `trend_health` is non-zero for a known uptrend and `monthly_closes` returns the prices — these tests are what was missing. Suggested branch: `fix/screen-trend-health-price-attr`. This unblocks everything below.

**A1. Single source of truth for `abstained`.** Decide one meaning and apply everywhere. Recommended: `abstained` means **"declined to rank because factor coverage was too thin"** (the `abstain_if_thin` sense). "No candidates cleared the gates" is a *separate* state (`len(candidates) == 0`), NOT abstention. Update `brief_summary.py` to stop redefining it; carry the real flag through.

**A2. Per-gate diagnostic counts.** Add a pure-domain value object emitted by the screen use-case:
```
ScreenDiagnostics(scanned, had_history, above_trend, scored, cleared)
```
Populate it in `evidence_screen_use_case.run()` (count drops at each `eligible()` sub-gate). Stdlib-only; no framework imports. This is the data that makes the UI honest.

**A3. Verdict logic (pure domain).** A function that maps diagnostics → one of:
- `UNDER_POWERED` — `had_history / scanned` below a config'd coverage floor (e.g. `<0.5`, reuse the 0.5 thin threshold). "Feed thin — can't claim the market offered nothing."
- `EARNED_ABSTENTION` — coverage healthy AND `cleared == 0`. "Working as designed."
- `ABSTAINED_THIN` — `ScreenResult.abstained` true on the single definition. "Held back — not enough data to score safely."
- `HAS_CANDIDATES` — `cleared > 0`.
Thresholds in `config/markets/us.yaml`, not hardcoded.

**A4. Build-time live diagnostic (methodology, run once).** Run the screen live (yfinance) and read `ScreenDiagnostics`. This answers the open question: is `had_history` ~0 because the feed is sparse, or because `has_min_history` is mis-gating? Fix the root cause if it's the gate. Record the finding in an ADR or PHASE_LOG. **Do not ship the "working as designed" hero until this confirms the bar is correctly strict.**

## 4. Work-stream B — legibility UI

**Four states, chosen by §3 verdict (never by guesswork):**

| Verdict | Headline | Body |
|---------|----------|------|
| `UNDER_POWERED` | ⚠ "Screen under-powered, not disciplined" (red) | per-gate funnel; "only X of 512 had usable history — feed thin" |
| `EARNED_ABSTENTION` | ✓ "Working as designed" (green) | funnel; "scanned & scored N, none cleared the strict bar; shows nothing rather than force a pick" |
| `ABSTAINED_THIN` | ⏸ "Held back — not enough data to score safely" | distinct from the above; factor coverage < threshold |
| `HAS_CANDIDATES` | "N ideas cleared, of 512 scanned" | candidate cards (below) |

**Per-gate funnel** (all states): `scanned → had_history → above_trend → cleared`, showing the drop at each step. This *shows the work* and is what makes 0 legible.

**Candidate card** (HAS_CANDIDATES):
- **Composite** — labelled a *research-priority score, not a forecast*; hover explains momentum ÷ 4 today.
- **Momentum** — z-score bar centered at 0 (green right for positive), + **percentile (0–100)** as the bounded "how strong"; value colored by sign.
- **Revision / Quality / Value** — rendered as **DATA-GAP** (hatched, "gap") from `FactorScore` whose underlying sub-score is `None`. **Never** a fabricated number.
- **"What this is telling you"** — plain read: e.g. *"risen faster than ~88% of names scanned — a reason to look, momentum only; not a buy signal, says nothing about price paid."*
- **Verify-before-position checklist** — earnings date proximity · steady-vs-one-day-spike · valuation (DATA-GAP, check yourself).
- **"Do next" research step** — directive but bounded to investigation: *"open the 1-yr chart + next earnings date…"* tagged *"a research step, not a trade instruction."*

**RESEARCH_ONLY** badge loud on every state (ADR-052). Hover (i) on every number/term, hover-only (consistent with Home/per-stock/risk tabs).

## 5. Honesty rails (must hold)

- **No buy/sell/trade verdict; no return forecast.** "Action" language is permitted **only** for *research/verification* steps; the object is always investigation, never a position. (Catches the documented pull toward decisive UI — `feedback_attributed_not_predicted`, `feedback_dashboard_trust_legibility`.)
- **Never dress a data failure as discipline.** The "working as designed" verdict is gated behind the live diagnostic confirming healthy coverage.
- **No fabricated factor values.** DATA-GAP renders from `None`, explicitly labelled.
- Composite is described as momentum-only while 3/4 factors are gaps.
- RESEARCH_ONLY everywhere until the screen is validated.

## 6. Architecture

- **Pure `domain/`:** `ScreenDiagnostics` value object + the verdict-mapping function (stdlib only). Likely a new `domain/screen_diagnostics.py` (keep `screen.py` small).
- **`application/evidence_screen_use_case.py`:** populate `ScreenDiagnostics` during the eligibility loop; carry the single `abstained` definition; stop the `brief_summary.py` redefinition.
- **Adapter (`adapters/visualization/`):** renders funnel + verdict + candidate cards from the value objects; no gate/verdict logic in the adapter.
- Reuses existing `FactorScore`, `ScreenResult`, `composite_score`, `eligible`, `abstain_if_thin`.

## 7. Tests (pure domain, small fixtures)

- `ScreenDiagnostics` counts: a fixture universe with mixed history/trend → assert each gate count + drops.
- Verdict mapping: one test per verdict incl. boundary at the coverage floor (e.g. exactly 0.5).
- Single `abstained` definition: assert `brief_summary` no longer flips it; one source.
- Composite momentum-only: `composite_score({momentum: z, revision: None, quality: None, value: None})` == z/4.
- DATA-GAP rendering contract: a `FactorScore` with `None` sub-score never surfaces a numeric value.
- Property (Hypothesis): verdict is deterministic and total over all `(coverage, cleared, abstained)` combinations (no unhandled state).

## 8. Open items at build

- **Run A4 live first** — the result decides whether work-stream A also includes a `has_min_history`/feed fix, and whether `EARNED_ABSTENTION` is ever reachable today.
- Confirm the coverage-floor threshold value with Tirth once the live numbers are in.
- Decide ADR vs PHASE_LOG for recording the diagnostic finding.
