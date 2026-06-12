# Phase 6 — Portfolio-Fit Verdict + Weekend Wrap

**Date:** 2026-06-11
**Status:** Approved (user, 2026-06-11)
**Builds on:** ADR-051 (gate design), ADR-052 (alpha hunt closed), wrap plan
(`2026-06-10-strategic-wrap-plan-design.md`), dashboard realignment (PR #39, merged)
**Supersedes:** wrap plan §7 timeline only — project closes ~2026-06-14/15
(user 2026-06-11: weekend close preferred; wrap spec already says faster is better).

## Purpose

Close the project into its final form: a **family financial-intelligence hub** that is
honest about what it knows. One last build item (the portfolio-fit verdict), then a
documentation sprint that makes the whole project navigable by a non-financial reader,
then close. The mid-July forward-gate verdict and the December self-experiment review
remain calendar events, not work.

**Reframed primary audience (user, 2026-06-11):** the user and their family making
real investment decisions — portfolio-showcase value is retained but secondary. This
strengthens, not changes, the §5.5 plain-language requirement.

## §1 Scope

IN:
1. **Portfolio-fit verdict** in the Stock Analysis tab (the one sanctioned live tab).
2. **`docs/HYPOTHESIS_BACKLOG.md`** — alpha-hunt keepalive with a pre-registration
   entry bar (docs only, no code).
3. **Docs sprint** — README rewrite around the verdict table, glossary, falsification
   write-up, plain-language pass, final project information architecture (§6).
4. Final STATUS/handoff overwrite; project close.

OUT (unchanged locks):
- Any return prediction, buy/sell language, or new signal hunting (ADR-052).
- Auto-retraining / online learning (wrap plan §5).
- Unit D (parked, wrap plan §6).
- Gate tooling — `discipline-calibration-status` CLI + dashboard gate strip already
  cover readiness; verdict resolves mid-July post-close.

## §2 The honest boundary (why this verdict is allowed)

Seven falsified hypotheses killed **prediction**. They did not kill **evidence
aggregation** or **portfolio arithmetic**. The fit verdict answers two questions the
project can answer with sheer precision:

1. **Evidence quality** — where does this stock sit on the screen's factual composite
   (valuation · quality · health), today? (Reuses the existing evidence screen — the
   same machinery behind Research Candidates.)
2. **Fit** — what would adding it do to *your* book's risk shape? (Reuses Unit A
   macro-beta + concentration arithmetic — deterministic, no prediction.)

It never answers "will it go up." The verdict card says so explicitly, every render.

## §3 Domain — `domain/fit.py` (new, pure, stdlib only)

```python
@dataclass(frozen=True)
class FitFlag:
    kind: str          # BETA_AMPLIFY | CONCENTRATION | TREND_STATE | DATA_GAP
    message: str       # plain English, family-readable
    severity: str      # INFO | CAUTION | WARNING

@dataclass(frozen=True)
class FitVerdict:
    ticker: str
    evidence_grade: str        # STRONG | MODERATE | WEAK | UNKNOWN
    fit_flags: tuple[FitFlag, ...]
    summary: str               # 1–3 plain-English sentences
    label: str = "RESEARCH_ONLY"

def assess_fit(
    ticker: str,
    candidate: ScreenCandidate | None,             # the analyzed ticker's screen row
    universe_composites: Sequence[float],          # ALL composites from the same
                                                   # ScreenResult — rank is computed
                                                   # HERE, it is not pre-stored
    ticker_beta: float | None,                     # SPY beta_headline for this ticker
    book: BookMacroExposure | None,                # current Unit A output
    position_values_cad: Mapping[str, float],      # ticker -> market_value_cad
    systematic_share_threshold: float,             # INJECTED from market config
                                                   # (config/markets/us.yaml:
                                                   # macro_beta.systematic_share_threshold,
                                                   # currently 0.60) — never hardcoded
    hypothetical_weight: float = 0.02,             # default 2% position sizing
) -> FitVerdict: ...
```

Rules (locked at design time, not tuned later):
- `evidence_grade`: percentile RANK of `candidate.composite` within
  `universe_composites` — computed inside `assess_fit` (validated 2026-06-11: the
  screen stores per-FACTOR percentiles on `FactorScore`, but composite rank is NOT
  pre-computed anywhere; `ScreenCandidate.composite` is a raw z-blend). rank ≥ 0.80 →
  STRONG; ≥ 0.50 → MODERATE; else WEAK; `candidate is None` → UNKNOWN.
- `BETA_AMPLIFY`: fires when `ticker_beta` and book's net SPY beta have the same sign
  AND the hypothetical add (at `hypothetical_weight`) moves systematic share toward or
  past `systematic_share_threshold`. The threshold is config, NOT a module constant
  (validated 2026-06-11: `domain/macro_beta.py` has no such constant — it is threaded
  from `config/markets/us.yaml` as a `build_flags` parameter; mirror that injection).
- `CONCENTRATION`: **single-name weight, NOT sector** (validated 2026-06-11: holdings
  carry no sector field anywhere in the pipeline — sector-based book weights have zero
  data source, and adding per-holding sector fetch would violate §4's no-new-IO lock).
  Computed from `position_values_cad` (market value, CAD): message phrased "at 2%
  sizing this would be your 12th-largest position; largest single name stays NVDA at
  8.4%" or fires CAUTION when the hypothetical add itself exceeds the largest existing
  single-name weight. **Do NOT reuse `PortfolioRisk.top_concentration`** — it is
  per-share-PRICE based (`application/holdings_risk.py:195`), semantically wrong for
  weight (known bug; the plan may include a separate one-line fix + test for it, but
  the fit path computes weights from `market_value_cad` directly either way).
- `TREND_STATE`: descriptive only ("trend intact/broken as of <date>"); wording must
  never imply an exit/entry signal (ADR-046 KILL).
- `DATA_GAP`: any missing input (no holdings, no beta, no factors) produces an explicit
  flag naming what is missing — degraded output is labeled, never silent.

Invariants (Hypothesis property tests):
1. No output string ever contains: buy, sell, winner, conviction, predict, alpha,
   outperform (case-insensitive vocabulary guard — single shared constant).
2. Hypothetical add never *decreases* reported concentration for the added sector/name.
3. `assess_fit` never raises on None/empty inputs — it degrades to UNKNOWN + DATA_GAP.
4. `label` is always RESEARCH_ONLY.

## §4 Application — `application/fit_use_case.py` (new)

Orchestrates existing machinery; no new ports, no new adapters (all callables
validated 2026-06-11):
- screen scores: `EvidenceScreenUseCase.run(universe, as_of, top_n)`
  (`application/evidence_screen_use_case.py:69`) — universe-only scoring; NO
  single-ticker path exists. Fit scores the universe and looks up the ticker
  (§8 fallback confirmed as the only option); pass all candidate composites to
  `assess_fit` for ranking.
- ticker beta: per-holding SPY beta = `MacroFactorBeta.beta_headline` for
  `factor="SPY"`, obtained via `MacroBetaUseCase.execute` machinery (1-element
  holdings list) or the lower-level path `load_price_series` →
  `domain/macro_beta.daily_returns`/`align_returns` → estimator fit. NOT `net_beta`
  (that is the book-aggregate dollar-weighted sum — wrong quantity).
- book exposure: existing `MacroBetaUseCase.execute(holdings, as_of)` output.
- holdings: `read_holdings(path)` from `application/holdings_reader.py` — pin THIS
  `Holding` type (ticker/shares/cost_basis/account_type); `domain/models.py:261`
  defines a DIFFERENT legacy `Holding` (symbol/quantity/…) used by the
  action_runner — do not mix them. Position market values from the holdings-risk
  path's `market_value_cad`.
- price history fetch: `load_price_series` (`application/price_returns.py:57`) —
  retry/backoff confirmed built-in; returns empty on failure (non-strict).
- Returns `FitVerdict`. All fetch failures → `DATA_GAP` flags, never exceptions to UI.

## §5 UI — Stock Analysis tab (modify only)

Verdict card directly under the existing RESEARCH ONLY banner (insertion point
validated: `tabs/stock_analysis.py` after the banner block in `_render_verdict`;
`AnalysisResult.sector` exists for display):
- Evidence grade as `grade_badge_html` pill (`components/formatters.py:101`) + the
  per-factor percentiles inline (note: those are per-FACTOR ranks, distinct from the
  composite rank driving the grade — caption the difference).
- Fit flags via `render_verdict_card` (`components/metrics.py:42`) — ONE card per
  flag. Severity→tone mapping (explicit; validated tone set is
  positive/negative/neutral only): `INFO → neutral`, `WARNING → negative`,
  `CAUTION → new `verdict-caution` CSS class` (one amber left-border class added to
  `components/styles.py`, mirroring the existing verdict tone classes — the only CSS
  addition in this phase).
- Summary sentence(s) + permanent caption: "Evidence + fit only — this tool does not
  predict returns (see Falsification Lab)."
- No holdings file → card renders evidence grade + "fit unavailable — no holdings
  loaded" (fail-loud, not blank).

Tests follow the realignment pattern: pure-helper extraction + render-no-raise with
tmp fixtures; vocabulary-guard regression test on rendered strings.

## §6 Final information architecture (docs sprint, ~1 day)

The repo must read top-down for a non-financial reader:

```
README.md                      ← the front door (rewritten)
  1. What this is (3 sentences, family-readable)
  2. The verdict table — "Does X predict Y? — No (tested 2006–2024, here's how)"
     one row per hypothesis, 7 rows + forward gate row, links to ADRs
  3. What the tool DOES do (CRO: weekly brief, risk scrubber, fit verdict, discipline)
  4. How to run it (dashboard + Saturday job, 5 lines)
  5. Glossary (CI, slippage, tercile, IC, pre-registration, look-ahead bias…)
  6. Architecture (hexagonal, one diagram, link to AGENTS.md)
  7. The story — falsification write-up (or link to docs/WRITEUP.md if >2 pages)
docs/STATUS.md                 ← final state + the two calendar dates
docs/HYPOTHESIS_BACKLOG.md     ← parked ideas; entry bar: hypothesis, pre-registered
                                 thresholds, kill condition, data cost — BEFORE any code
docs/SKILL_ROUTING.md          ← already exists; add maintenance-mode row
docs/adr/                      ← untouched history (plain-language pass on 052/053 only)
```

Definition of done (§5.5 test, unchanged): a reader with no finance background can
answer "what did this project try, what did it find, why is the finding trustworthy"
from the README alone.

## §7 Sequence + branches

| When | What | Branch |
|---|---|---|
| Thu–Fri Jun 11–12 | fit verdict, TDD, domain→application→UI | `feat/portfolio-fit-verdict` → PR → develop |
| Sat Jun 13 | docs sprint + HYPOTHESIS_BACKLOG + plain-language pass | `docs/final-wrap` → PR → develop |
| Sun Jun 14 | final review, STATUS overwrite, develop → main, close | release PR |
| Mid-July | forward-gate verdict (read-only, ~30 min) | — |
| Dec 2026 | self-experiment review (~30 min) | — |

## §8 Risks

- **Screen scoring path may not expose single-ticker scoring** (it ranks a universe).
  Plan must verify; fallback = score the universe, look up the ticker, accept the cost
  (user-initiated tab, latency tolerable) — never fork a duplicate scorer.
- **Per-ticker beta needs return history** — reuse the macro-beta fetch path with its
  existing retry/backoff; failure → DATA_GAP, not crash.
- **Scope creep risk:** correlation-vs-book deferred to HYPOTHESIS_BACKLOG (explicitly
  out; medium cost, weekend deadline).
- **Language drift risk:** vocabulary guard is a *domain invariant test*, not a UI
  convention — drift fails CI.

## §9 Validation status

Independently validated against the codebase (Opus reviewer, 2026-06-11). All findings
amended in place:
1. Systematic-share threshold is CONFIG (`config/markets/us.yaml`, 0.60) threaded as a
   parameter — `assess_fit` takes it injected; no module constant exists to import.
2. Sector concentration DROPPED — holdings carry no sector field anywhere; replaced
   with single-name market-value weight from `market_value_cad`. Known bug noted:
   `top_concentration` is per-share-price based; do not reuse.
3. No single-ticker screen scoring exists — universe-scoring fallback confirmed and
   wired into the design (`EvidenceScreenUseCase.run`).
4. Per-ticker beta = `MacroFactorBeta.beta_headline` (SPY), not `net_beta`
   (book-aggregate). `load_price_series` retry/backoff confirmed.
5. Two distinct `Holding` types — pinned to `application/holdings_reader.Holding`.
6. `render_verdict_card` tones are positive/negative/neutral — explicit severity→tone
   map added; one new `verdict-caution` CSS class is the only CSS addition.
7. Composite percentile-rank is computed in `assess_fit` from universe composites —
   it is not pre-stored anywhere (signature fixed to receive them).

Confirmed-correct by the same review: verdict-card insertion point in
`_render_verdict`, `AnalysisResult.sector`, `grade_badge_html`, `FactorScore`
per-factor percentiles, retry/backoff in price fetch.
