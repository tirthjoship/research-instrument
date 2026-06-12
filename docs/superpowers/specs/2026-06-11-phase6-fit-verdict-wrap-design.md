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
    factor_scores: Sequence[FactorScore] | None,   # from screen scoring
    ticker_beta: float | None,                     # vs SPY, from macro-beta machinery
    book: BookMacroExposure | None,                # current Unit A output
    holdings: Sequence[Holding],
    sector: str | None,
    hypothetical_weight: float = 0.02,             # default 2% position sizing
) -> FitVerdict: ...
```

Rules (locked at design time, not tuned later):
- `evidence_grade`: percentile RANK of the ticker's composite within the latest
  screened universe (not the raw composite value): rank ≥ 0.80 → STRONG;
  ≥ 0.50 → MODERATE; else WEAK; `factor_scores is None` → UNKNOWN.
- `BETA_AMPLIFY`: fires when `ticker_beta` and book's net SPY beta have the same sign
  AND the hypothetical add (at `hypothetical_weight`) moves systematic share toward or
  past the existing SYSTEMATIC_DOMINANT threshold (reuse the threshold constant from
  `domain/macro_beta.py` — never re-declare it).
- `CONCENTRATION`: hypothetical add recomputes sector/name weight; message phrased
  "Tech 40% → 44%". Reuses `ConcentrationFlag` thresholds (`domain/brief.py`).
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

Orchestrates existing machinery; no new ports, no new adapters:
- factor scores: the screen's per-ticker scoring path (same code Research Candidates
  ranking uses — plan must identify the exact callable and reuse, not duplicate).
- ticker beta + book exposure: `MacroBetaUseCase` machinery / `domain/macro_beta.py`
  (`net_beta`, `aggregate_macro_exposure`).
- holdings: existing holdings reader (`application/holdings_reader.py`).
- Returns `FitVerdict`. All fetch failures → `DATA_GAP` flags, never exceptions to UI.

## §5 UI — Stock Analysis tab (modify only)

Verdict card directly under the existing RESEARCH ONLY banner:
- Evidence grade as `grade_badge_html`/pill + the three factor percentiles inline.
- Fit flags as `render_verdict_card` rows, severity-colored left border (SWST pattern,
  consistent with dashboard realignment).
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
