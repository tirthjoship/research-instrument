# Design Spec — Corroboration Engine (Sub-project 1 of 5)

**Date:** 2026-06-20
**Status:** Draft for user review
**Branch:** `feat/corroboration-engine`
**Author:** Tirth + Fable (brainstorm)
**Related research:** `research/2026-06-20-prediction-and-surfacing-state.md`

---

## 1. Problem statement

The two live "weekly job" paths do not serve the user:

- `run-tournament` is a **dead ML prediction path** (model never persisted/loaded → 0 picks). See research doc.
- `weekly-brief` works but is attributed-evidence on *existing holdings only* — it surfaces **no new
  candidates** and currently **crashes** in `holdings_risk._vol` (numpy float into `statistics.pstdev`,
  Python 3.12 — tracked separately).

Across **eight** pre-registered alpha hypotheses, **every one failed an honest out-of-sample bar** (1 NULL,
3 KILL, 3 INCONCLUSIVE, 1 RESEARCH_ONLY). Lesson: in-house return prediction has no demonstrated edge, and
in-sample results that looked good failed forward/OOS. The user's own north-star (memory
`feedback_attributed_not_predicted`, `dashboard_trust_legibility`): **attribute third-party views, never
adopt; build trust through legible evidence, not predictions.**

Meanwhile the investable universe is **frozen** to static files (S&P500 + NASDAQ-100 + a 28-ticker theme
spine + ~120 hardcoded names). No mechanism ingests what credible outlets actually recommend.

## 2. What we are building

A reusable **Corroboration Engine** that:

1. **Harvests** what credible, free sources are recommending (and *why*),
2. **Verifies + attributes** each claim (shown as theirs, with a fetched citation), and
3. **Stress-tests** each name against the project's *existing* signals (factor screen, trend health,
   divergence, discipline),

then emits a per-ticker **`CorroboratedCandidate`** and a theme/sector **`DirectionalView`** that power
three consumers — **new-candidate surfacing, screener revamp, portfolio-verdict** — plus a fourth,
**Hypothesis #9** (does corroboration forward-beat SPY?), gated and RESEARCH_ONLY until proven.

### Decomposition (this spec = Sub-project 1)

| # | Sub-project | Spec |
|---|-------------|------|
| **1** | **Harvesting + Corroboration core** | **THIS DOC** |
| 2 | Surfacing consumer (new candidates enter universe) | later |
| 3 | Screener revamp (convergence-backed ranking) | later |
| 4 | Portfolio-verdict integration | later |
| 5 | Hypothesis #9 pre-registered forward validation | later |

## 3. Goals / Non-goals

**Goals**
- Decision-support: every conclusion ships its full evidence chain so the *user* decides.
- Free-tier only; reuse the existing `gemini_models.py` fallback chain.
- Hard anti-hallucination: a claim with no resolvable, ticker-naming citation is dropped, never shown.
- Hexagonal: harvest/verify in adapters; corroboration logic is a pure domain service.
- Persist a weekly snapshot (mandatory for #9 forward accrual).
- Transparent "evolution": reuse the `source_reliability` SQLite table; reweight sources by *proven*
  forward hit-rate as outcomes resolve.

**Non-goals (this sub-project)**
- No return prediction claim. `convergence` is an evidence-strength label, never a forecast.
- No reviving the ML ensemble (only Hypothesis #9 could later justify it).
- No paid data, no scraping that violates ToS. Scraping is best-effort, free, and optional.
- No dashboard wiring (that is the consumer sub-projects).
- No backtest of LLM-harvested recommendations (impossible — no historical snapshot; see §8).

## 4. Architecture (hexagonal)

```
HARVEST (adapters, free, attributed)        CORROBORATE (domain, pure)              EMIT
GeminiGroundedHarvester (primary,+search)─┐  CorroborationService:                ┌─ CorroboratedCandidate
RSS / dated news adapters              ───┤   • drop unverified claims            ├─ DirectionalView
yfinance analyst events (dated)        ───┼─► • pull EXISTING signals             │   (theme/sector tilt)
GDELT / Finnhub / AlphaVantage (free)  ───┘   • weight by source_reliability      └─ weekly snapshot → SQLite
[CitationVerifier gate drops bad claims]      • compute convergence tier              → forward-resolve → #9 gate
```

- **New port** `RecommendationHarvestPort` (`domain/ports.py`): `harvest(as_of) -> list[HarvestedClaim]`.
- **Primary adapter** `GeminiGroundedHarvester` (`adapters/data/`): asks Gemini (with Google-Search
  grounding) "which stocks are credible sources recommending now, and why, with citation URLs"; reuses
  `gemini_models.py` fallback rotation. Returns claims with candidate URLs.
- **Corroborator adapters** (free): RSS/dated-news, `YFinanceAnalystAdapter` rating events, GDELT,
  Finnhub/AlphaVantage (free keys). Each contributes independent `HarvestedClaim`s.
- **`CitationVerifier`** (adapter): for each claim, fetch the URL (existing `WebFetch`-style/requests),
  confirm it resolves (HTTP 200) and the page text names the ticker/company. Unverified → dropped.
- **`CorroborationService`** (`domain/`, stdlib-only): consumes verified claims + existing outputs of
  `EvidenceScreenUseCase` (factor rank), trend-health, divergence, discipline; weights each source by
  its `source_reliability` row; emits `CorroboratedCandidate` + rolls up `DirectionalView`.
- **`CorroborationSnapshotStore`** (extends `adapters/data/sqlite_store.py`): writes `harvested_recs`
  and `corroboration_runs` weekly; later weeks resolve forward outcomes.

## 5. Data contract

### `HarvestedClaim` (domain dataclass)
`source_name: str`, `ticker: str`, `stance: Stance{BULLISH,BEARISH,NEUTRAL}`, `thesis_summary: str`
(*their* words, ≤280 chars), `url: str`, `published_at: date`, `verified: bool`,
`reliability_weight: float` (0–1, from `source_reliability`; default 0.5 for unseen source).

### `CorroboratedCandidate` (domain dataclass)
| Field | Type | Notes |
|-------|------|-------|
| `ticker`, `as_of` | str, date | point-in-time stamp |
| `sources` | list[HarvestedClaim] | verified only |
| `our_readout` | `OurReadout` | factor_percentile, trend_health{HEALTHY,CAUTION,BROKEN}, divergence_flag, discipline_flag(if held) |
| `convergence` | `ConvergenceTier{STRONG,MODERATE,WEAK,CONFLICTED,NONE}` | evidence strength, **not** a forecast |
| `agreement` | `Agreement` | n_bullish, n_bearish, weighted_score∈[-1,1], our_alignment{AGREES,DIVERGES,NEUTRAL} |
| `uncertainty` | `Uncertainty` | coverage_n, conflict: bool, freshness_days |
| `held` | bool + `PositionContext?` | from holdings |
| `verification` | `{ALL_VERIFIED,PARTIAL,NONE_DROPPED}` | |

### `DirectionalView` (domain dataclass)
Per **theme** (`themes.yaml`) and **sector**: `net_stance`, `mean_convergence`, `your_exposure_pct`,
`evidence_weight_pct`, `tilt: {LEAN_IN,HOLD,LEAN_OUT,AVOID}` (attributed, RESEARCH_ONLY).

## 6. Convergence tier math (transparent, auditable)

Pure function of two transparent inputs — **external agreement** and **our-signal alignment**:

1. `weighted_score = Σ(stance_sign · reliability_weight) / Σ(reliability_weight)` over verified sources,
   `stance_sign ∈ {+1 bull, −1 bear, 0 neutral}`; range [−1, +1].
2. `our_alignment` = AGREES if our_readout direction matches the sign of `weighted_score`; DIVERGES if
   opposite; NEUTRAL if our signal is flat.
3. Tier table (locked, no hidden weights):

| weighted_score | coverage_n | our_alignment | Tier |
|---|---|---|---|
| ≥ +0.5 | ≥ 3 | AGREES | **STRONG** |
| ≥ +0.5 | ≥ 3 | NEUTRAL | MODERATE |
| ≥ +0.5 | any | DIVERGES | **CONFLICTED** |
| +0.2 … +0.5 | ≥ 2 | AGREES/NEUTRAL | MODERATE |
| 0 … +0.2, or coverage_n<2 | any | any | WEAK |
| ~0 with both bull & bear present | any | any | CONFLICTED |
| no verified sources | 0 | — | NONE |

(Bearish mirror applies for negative scores.) Every card shows the numbers that produced its tier — no
black box. **Tiers carry no predictive weight until Hypothesis #9 (Sub-project 5) validates them.**

## 7. Source-reliability evolution (the honest "it learns")

- Reuse SQLite `source_reliability(source_name, n_calls, n_hits, hit_rate, updated_at)`.
- Each weekly resolution (Sub-project 5), a source's past BULLISH/BEARISH claims are scored against the
  realized forward return; `n_calls`/`n_hits` update; `reliability_weight = hit_rate` (Bayesian-smoothed,
  prior 0.5, so unseen sources start neutral and earn weight).
- Result: corroboration weights credible-by-track-record sources up and noise down, transparently and
  with no model. This is the only "self-improvement" mechanism; it is auditable per source.

## 8. Persistence + Hypothesis #9 hook

- Weekly run writes a `corroboration_runs` row + N `harvested_recs` rows (point-in-time `as_of`).
- **No historical backtest of harvested recs** — they don't exist before we start capturing them.
  Validation is **forward-only**, mirroring ADR-048: accrue weekly, resolve 21-day forward returns,
  gate at n≥30. (Sub-project 5 owns the pre-registered gate; this sub-project only guarantees the
  snapshot is captured point-in-time so #9 *can* run.)
- **Permitted historical sanity check (limited):** on the *dated-source slice only* (yfinance analyst
  rating events, dated news) we may run a 3–6 month retrospective as a **sanity signal, not a verdict**,
  and it must be labelled as such. The Gemini-grounded harvest is excluded (look-ahead/hallucination).

## 9. Look-ahead / leakage guards

- `as_of` stamped on every claim and candidate; `published_at <= as_of` enforced (claims dated after
  `as_of` are dropped) — reuse the project's PIT discipline.
- `our_readout` signals fetched with `prediction_time = as_of`, reusing `YFinanceAdapter`'s existing
  `validate_point_in_time`.
- The historical sanity check (§8) must use only sources with genuine publish timestamps.

## 10. Free-tier / reliability constraints

- Gemini: reuse `gemini_models.py` fallback chain; cache grounded harvest results per `as_of` to avoid
  re-pinging. Google-Search grounding free quota is limited → one harvest call per weekly run, cached.
- Corroborators: RSS/GDELT keyless; Finnhub/AlphaVantage free keys (already in repo, rate-limited).
- `CitationVerifier` fetches are throttled (reuse the throttle pattern from the yfinance fix:
  `fix/yfinance-throttle`).

## 11. Testing (mandatory, small fixtures, no live APIs)

- `CorroborationService` (pure): table-driven tests for every tier branch (§6) + Hypothesis property
  tests (e.g. all-bearish never yields STRONG-bull; dropping a source never raises a tier).
- `CitationVerifier`: fixtures for resolves/200+names-ticker → verified; 404 / no-mention → dropped.
- `GeminiGroundedHarvester`: fake Gemini client returning canned grounded JSON; assert claims parsed +
  URLs extracted; assert hallucinated (unverifiable) URLs are dropped downstream.
- Snapshot store: in-memory SQLite, round-trip `harvested_recs` / `corroboration_runs`.
- All adapters use fakes per `tests/fakes/`; conftest strips live keys.

## 12. Build order (for the implementation plan)

1. Domain types (`HarvestedClaim`, `CorroboratedCandidate`, `DirectionalView`, enums) + `CorroborationService` (TDD, pure).
2. `RecommendationHarvestPort` + `CitationVerifier` + `GeminiGroundedHarvester` (fakes first).
3. Free corroborator adapters (reuse existing RSS / analyst / GDELT).
4. `CorroborationSnapshotStore` (SQLite tables).
5. A `corroborate` CLI command that runs harvest→verify→corroborate→persist and prints the cards + DirectionalView (RESEARCH_ONLY banner).
6. Limited dated-source historical sanity check (labelled).

## 13. Open questions

- Q: Gemini Google-Search grounding on the *free* tier — confirm quota + that citation URLs are returned
  (verify via context7 / a probe before building the harvester). If grounding is not free, fall back to
  B-sources primary + Gemini summarization-only.
- Q: theme taxonomy — extend `themes.yaml` (6 themes) or add sectors from yfinance? (Default: both,
  sector from yfinance `info['sector']`, theme from `themes.yaml`.)
- Q: how many candidates per weekly harvest to cap (free-tier + verification cost)? Proposed default: 25.
