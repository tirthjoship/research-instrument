# Evidence-First Opportunity Surfacing & Forward-Tracking — Design Spec

**Date:** 2026-06-05
**Status:** Approved (brainstorm complete; pending spec review → writing-plans)
**Branch:** `feat/opportunity-forward-tracking` (off `main`, PR → `develop`)
**Scope:** Leg-2, **sub-project 1 of 1** for this spec. Leg-2's portfolio/sizing/two-sided/real-money pieces are explicit non-goals here (separate spec later).
**Predecessor:** FIE v1 (ADR-038/039) + the conviction-validation-honesty work (in-sample edge did **not** survive out-of-sample — see "Why").

---

## Why this exists

The validated, backtestable slice of the conviction engine (smart-money 13D/insider + analyst, 2 of 8 dimensions) was tested honestly:

- **In-sample (2023-06→2026-05):** large-cap top-decile basket beat SPY by +3.58%/3wk, moving-block bootstrap p(mean≤0)=0.0005, CI floor +1.4%. Looked strong.
- **Out-of-sample (2018-01→2023-05, incl. 2020 crash + 2022 bear):** the edge **halved and lost significance** — mean +1.96%, bootstrap CI [−0.5%, +4.7%] (spans 0), t-test 0.052. Small/mid was **negative** OOS (−10pp). The in-sample strength was partly **bull-regime inflation**.

**Conclusion:** the late, backtestable institutional signals are a faint, regime-sensitive lean — not a tradeable foundation. The signals that catch emerging winners *early* (the thematic plays: space — ASTS/RKLB/LUNR/IRDM/HXL; memory/storage — MU/WDC/SNDK) live in the **6 conviction dimensions held neutral in the backtest** (event-causal, sentiment/buzz, cross-asset/thematic, fundamentals). Those **cannot be backtested** — reconstructing point-in-time buzz/theme state is look-ahead bias. The only honest way to validate them is to **forward-track live**: turn all 8 dimensions on, surface dated calls across an all-cap universe, and accumulate a real track record over weeks/months.

This sub-project builds that evidence engine. It is the "satellite-discovery + proof" foundation; the benchmark-beating portfolio (core+satellite) is built on top of it later, on signals that have earned trust.

**Owner constraint (carried from brainstorm):** all-cap, do **not** tunnel to large-cap / trillion-dollar names. Catch winners *early*, before the run. Avoid the hindsight/survivorship hype-chaser trap (for every ASTS that 5x'd, a dozen themed small-caps craters).

---

## Locked decisions (brainstorm outcomes)

1. **Evidence-first.** Sub-project 1 = surface + forward-track + accrue evidence. No portfolio construction yet.
2. **Hybrid all-cap universe.** Curated thematic spine (`config/universe/themes.yaml`) **+** dynamic-discovery overlay (`BuzzDiscoveryPort` + sentiment spikes). Spine guarantees watched themes; overlay auto-surfaces unknown waves.
3. **Multi-horizon forward-tracking.** Each call tracked at **1w / 1m / 3m** simultaneously, measured vs **both SPY and NDX**. The cross-horizon shape is signal (building 1m/3m = real wave; 1w pop that fades = lookalike). Reuses the `MultiHorizonPrediction` pattern.
4. **Layered surfacing trigger.** `conviction (8-dim quality) ≥ Cmin` **AND** `divergence (buzz-leads-price, "early") ≥ Dmin`. Quality *and* not-already-run. Honest **abstention** when nothing clears both bars.
5. **Approach 3 (thin tracking core + heavy signal reuse).** New, clean paper-call models + tracking loop (semantics differ from real-trade P&L); reuse conviction engine, all 8 dims, `BuzzDiscovery`, `MultiHorizon`, and Phase 8 `SignalPerformance`/learning as-is.

## Non-goals (deferred to Leg-2 sub-project 2)

Portfolio construction, position sizing (Kelly etc.), full two-sided buy/sell discipline beyond a direction tag, real-money execution, conformal/meta-label layers. None ship here.

---

## Success criteria (Definition of Done)

| # | Criterion | Verified by |
|---|-----------|-------------|
| 1 | `scan-opportunities` surfaces ranked all-cap opportunities (or abstains), each with per-dimension + divergence evidence | CLI output + `test_opportunity_scan` |
| 2 | All **8** conviction dimensions are active in the live scan (none forced neutral) | `test_opportunity_scan` asserts non-neutral dims present |
| 3 | Hybrid universe surfaces a **non-spine** ticker via the discovery overlay | `test_hybrid_universe` (fake `BuzzDiscoveryPort`) |
| 4 | A surfaced call logs a dated `SurfacedCall`; signals are point-in-time filtered to ≤ `surfaced_at` | `test_opportunity_scan` (future-dated signal ignored) |
| 5 | `resolve-calls` resolves matured calls at 1w/1m/3m and records return vs **SPY and NDX** | `test_forward_tracking` |
| 6 | Abstention: nothing clears both bars → no call surfaced, explicit "sitting out" | `test_abstention` |
| 7 | `opportunity-report` shows accruing per-signal & per-theme hit-rate across horizons vs SPY+NDX | `test_track_record` + CLI |
| 8 | Leakage-safe: outcome never feeds the same call's surfacing; resolution only at horizon maturity | `test_forward_tracking` timing tests |
| 9 | Quality gates: `make check` green (black, isort, mypy strict, ruff, pytest ≥90% cov), pre-commit clean | CI |
| 10 | Domain purity preserved: new domain models import only stdlib/typing/dataclasses/datetime/enum | `domain-check` skill |

---

## Architecture (hexagonal, Approach 3)

```
adapters/  →  domain/  ←  application/
```

### New — domain (pure)
| File | Responsibility |
|------|----------------|
| `domain/surfaced_call.py` | `SurfacedCall`, `CallOutcome` frozen dataclasses + `OpportunityDirection`, `Horizon` enums + invariants |
| `domain/divergence_service.py` | Pure `divergence_score(...)` — buzz/attention rising while price lags (sentiment-leads-price) |

### New — ports (`domain/ports.py` additions)
| Port | Contract |
|------|----------|
| `UniverseProviderPort` | `get_universe(now) -> list[UniverseEntry]` (ticker, theme, cap_tier) |
| `SurfacedCallStorePort` | `save_call`, `get_unresolved_calls(now)`, `save_outcome`, `get_track_record()` |

### New — adapters
| File | Responsibility |
|------|----------------|
| `adapters/data/hybrid_universe_provider.py` | Thematic spine (YAML) + `BuzzDiscoveryPort` overlay, merged/deduped; degrades to spine-only on discovery failure |
| `adapters/data/sqlite_store.py` (extend) | `surfaced_calls` + `call_outcomes` tables + CRUD implementing `SurfacedCallStorePort` |

### New — application
| File | Responsibility |
|------|----------------|
| `application/opportunity_scan_use_case.py` | `OpportunityScanUseCase`: universe → 8-dim conviction × divergence → layered trigger → surface/abstain → persist → ranked cards |
| `application/forward_tracking_use_case.py` | `ForwardTrackingUseCase`: resolve matured calls vs SPY+NDX at each horizon → `CallOutcome` → feed `SignalPerformance` |

### New — config / CLI
| File | Responsibility |
|------|----------------|
| `config/universe/themes.yaml` | Curated thematic baskets (space, memory_storage, ai_infra, nuclear_energy, defense, biotech, …) |
| `application/cli.py` (extend) | `scan-opportunities`, `resolve-calls`, `opportunity-report` |

### Reused as-is (no change)
Conviction engine (Phase 7 `ConvictionScoringUseCase` / `compute_conviction`), all 8 dimension feature engineers (3B sentiment/buzz, 4A fundamentals, 4C cross-asset, 4D event-causal, smart-money, analyst), `BuzzDiscoveryPort`, `MultiHorizonPrediction` pattern, Phase 8 `SignalPerformance`/learning, sentiment/market adapters, `validate_point_in_time_access`.

---

## Domain models (detail)

```python
class OpportunityDirection(Enum):
    BUY = "buy"                # a surfaced emerging opportunity
    SELL_WATCH = "sell_watch"  # a currently-held name surfacing with deteriorating signals
    # (full two-sided buy/sell discipline is deferred to sub-project 2)

class Horizon(Enum):
    W1 = 7      # calendar days
    M1 = 30
    M3 = 90

@dataclass(frozen=True)
class EvidenceItem:
    dimension: str          # e.g. "event_signal", "divergence", "smart_money"
    score: float            # 0-10 contribution
    note: str               # human-readable ("Intel ▲ government stake; Tech +")

@dataclass(frozen=True)
class SurfacedCall:
    call_id: str            # f"{ticker}_{surfaced_at:%Y%m%d}"
    ticker: str
    surfaced_at: datetime   # tz-aware; POINT-IN-TIME ANCHOR
    conviction: float       # 0-10 (all 8 dims)
    divergence_score: float # 0-10
    direction: OpportunityDirection
    evidence: tuple[EvidenceItem, ...]
    theme: str | None       # spine theme name, or "discovery"
    cap_tier: str           # "large" | "mid" | "small"
    spy_at_surface: float
    ndx_at_surface: float
    # invariants: 0<=conviction<=10, 0<=divergence<=10, surfaced_at tz-aware

@dataclass(frozen=True)
class CallOutcome:
    call_id: str
    horizon: Horizon
    resolved_at: datetime
    entry_price: float
    exit_price: float
    forward_return: float
    spy_return: float
    ndx_return: float
    beat_spy: bool
    beat_ndx: bool
    beat_both: bool
    # invariant: resolved_at >= call.surfaced_at + horizon.value days
```

## Divergence service (the new "early" signal)

```python
def divergence_score(
    buzz_series: list[tuple[datetime, float]],   # attention/volume over time
    price_series: list[tuple[datetime, float]],
    sentiment: float,                             # current sentiment 0-1
    now: datetime,
) -> float:                                       # 0-10, neutral 5.0 if no data
    """High when attention/buzz is ACCELERATING but price has NOT yet moved
    (sentiment-leads-price). Low when price already ran (buzz lagging price) or
    when buzz is flat. Pure: no I/O. All inputs pre-filtered to <= now upstream."""
```
Sketch: `buzz_accel = (recent_buzz_mean − trailing_baseline) / max(baseline, ε)`; `price_move = recent_return`; divergence rises with `buzz_accel` and falls with already-realized `price_move`; modulated by `sentiment`. Exact weights are tunable defaults, calibrated as the track record builds.

## Use cases (behaviour)

**`OpportunityScanUseCase.execute(now, *, allow_abstention=True) -> list[OpportunityCard]`**
1. `universe = universe_provider.get_universe(now)`.
2. For each entry: gather **point-in-time** signals (all ≤ `now`), compute `conviction` (8 dims) and `divergence_score`.
3. Layered trigger: keep iff `conviction ≥ Cmin AND divergence ≥ Dmin`.
4. If none qualify and `allow_abstention` → return `[]` (explicit sitting-out). No fabricated fill.
5. Assign `direction`: **BUY** for a surfaced opportunity; **SELL_WATCH** only when a currently-held ticker surfaces with deteriorating signals (full two-sided discipline deferred). Build `evidence` (per-dim + divergence), persist `SurfacedCall`, return ranked cards (rank by blend of conviction & divergence; flag high-divergence "early-and-rising").

**`ForwardTrackingUseCase.resolve_due_calls(now) -> list[CallOutcome]`**
1. `calls = store.get_unresolved_calls(now)` (any (call,horizon) with `now ≥ surfaced_at + horizon`).
2. For each: entry = first close ≥ `surfaced_at`; exit = first close ≥ `surfaced_at + horizon`; compute `forward_return`, `spy_return`, `ndx_return` over the same window; `beat_*` flags; persist `CallOutcome`; update Phase 8 `SignalPerformance` keyed by the dims/theme that drove the call.

**`ForwardTrackingUseCase.get_track_record() -> TrackRecord`** — per-signal & per-theme hit-rate vs SPY/NDX across the three horizons.

## Data flow / cadence

- **Daily `scan-opportunities`** → surface dated calls (or abstain) + ranked cards with evidence + horizons to watch.
- **Daily `resolve-calls`** → resolve any matured (call,horizon) → outcomes → update `SignalPerformance`.
- **On-demand `opportunity-report`** → the accruing live evidence (per-signal/theme/horizon hit-rate vs SPY+NDX) — the proof the backtest could not produce.

## Leakage safety (project rule #2, non-negotiable)

- `surfaced_at` is the point-in-time anchor; every signal feeding conviction/divergence is filtered to ≤ `surfaced_at` (reuse `validate_point_in_time_access`; raise `LookAheadBiasError` on violation).
- `CallOutcome` resolves only at true horizon maturity; forward/benchmark returns use **post-surface prices only**.
- Forward-only by construction: an outcome never influences the surfacing of its own (or any earlier) call.

## Error handling

- A failing dimension or adapter → that dimension scored **neutral**, logged (structured), scan continues (never crashes on one bad signal).
- Discovery overlay network failure → fall back to **spine-only** universe, log a warning.
- Missing price data at resolution → skip that (call,horizon), leave unresolved for a later run (don't fabricate a 0).

## Testing strategy

- **No network in CI** (rule #5): fakes for `UniverseProviderPort`, `BuzzDiscoveryPort`, market/sentiment ports, `SurfacedCallStorePort`.
- Pure domain (`divergence_service`, models) → Hypothesis property tests for invariants (scores in range, monotonicity of divergence in buzz_accel).
- Use-case tests on a small fake universe: surfacing, **abstention**, point-in-time filtering (future-dated signal ignored), multi-horizon resolution **timing** (not resolved before maturity), beat-SPY/NDX logic.
- Small fixtures only; never real APIs.

---

## File structure map

**New:** `domain/surfaced_call.py`, `domain/divergence_service.py`, `adapters/data/hybrid_universe_provider.py`, `application/opportunity_scan_use_case.py`, `application/forward_tracking_use_case.py`, `config/universe/themes.yaml`, tests (`tests/test_surfaced_call.py`, `test_divergence_service.py`, `test_hybrid_universe.py`, `test_opportunity_scan.py`, `test_forward_tracking.py`, `test_track_record.py`, `tests/fakes/fake_universe_provider.py`, `tests/fakes/fake_buzz_discovery.py`).

**Modified:** `domain/ports.py` (+2 ports), `adapters/data/sqlite_store.py` (+2 tables + CRUD), `application/cli.py` (+3 commands), `CLAUDE.md`/`CONTEXT.md` (status), ADR (write `docs/adr/040-opportunity-forward-tracking.md`).

**No deletions.**

## Cross-cutting rules (every task)

- TDD: failing test → run-fail → minimal impl → run-pass → commit.
- `domain/` imports only stdlib/typing/dataclasses/datetime/enum (rule #1).
- Point-in-time everywhere (rule #2). Evaluate vs SPY **and** NDX (rule #3 extended).
- Feature branch → PR to `develop` (rule #4). `make check` green; never `--no-verify`. Conventional commits.

## Open tunables (calibrated as evidence accrues — sensible defaults to start)

`Cmin`, `Dmin` thresholds; divergence formula weights; theme-basket membership; discovery-overlay size cap; horizon set (start 1w/1m/3m). All documented in `config/`, none hard-coded as magic numbers in domain.

## Self-review checklist

- [ ] Every success criterion (1–10) maps to a component + test.
- [ ] New domain models are pure (no framework imports).
- [ ] Abstention + point-in-time + multi-horizon timing all have explicit tests.
- [ ] Reuse is real (conviction engine, 8 dims, BuzzDiscovery, MultiHorizon, Phase 8 SignalPerformance) — no re-implementation.
- [ ] Scope holds: no portfolio construction / sizing / real-money here.
