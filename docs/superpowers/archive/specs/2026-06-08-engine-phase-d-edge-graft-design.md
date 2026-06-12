# Engine Phase D — Conditional Edge Graft — Design Spec

**Date:** 2026-06-08
**Status:** Draft for review (CONDITIONAL — may never execute, by design)
**Author:** Tirth Joshi (with Claude)
**Follows:** ADR-049 (engine architecture), Phase-A/B/C specs
**Phase:** D of 4 (graft a *validated* edge into sizing/weighting — gated on a passed test)

---

## 1. What this is — and what it is not

A **conditional** phase that grafts **only an already-validated edge** into the engine's decision layer — turning a proven signal from a *label on a report* into an *input that tilts screen weights or position sizing*. It is the single point where the engine is permitted to move from "evidence + abstention" toward "act on a measured edge."

**It is explicitly NOT:**
- guaranteed to run. **If no prior phase produced a validated edge, Phase D does not execute** — and that is a pre-agreed, honest success state (research + discipline + abstaining-screen is a complete product).
- a place to graft a hopeful or marginal signal. Only a gate-passing edge, sized for its *measured* (modest, decayed) magnitude.
- a re-opening of the alpha hunt. Grafting requires a *passed pre-registered test*, never a new untested hypothesis.

## 2. Entry condition (hard gate — checked before any work)

Phase D runs **iff at least one** of the following has PASSED its pre-registered gate:
- **Phase A** evidence screen — IC ≥ 0.02 (CI > 0) or top-decile Sharpe-diff CI > 0 net of costs.
- **Phase C** economic-link drift — positive obscure-tail excess, CI > 0 net of costs.
- **Discipline July gate (ADR-048)** — REDUCE down-rate ≥ 55% AND Brier ≤ 0.45 AND n ≥ 30, forward.

If **none** passed → **stop. Do not build Phase D.** Update ADR-049 to record the engine's final form as research + discipline + abstaining-screen. Tell the user plainly; this is the four-falsifications discipline holding the line, not a shortfall.

## 3. What gets grafted (per source that passed)

| Passed source | Graft | Sizing rule |
|---|---|---|
| Phase A screen | composite rank tilts buy-candidate ordering + a *small* sizing weight | weight ∝ measured IC, capped (decay-aware); abstains in regimes where the OOS test was weak |
| Phase C drift | a supplier-after-customer-event candidate enters the screen as a *time-boxed* tag | only obscure-tail links; decays over the measured half-life |
| Discipline gate | REDUCE/TRIM verdicts gain a *sizing* recommendation (not just a flag) | sized to the measured drawdown-reduction, never a leverage call |

**Common rule:** the graft magnitude equals the **measured** effect size from the passing test — never a hoped-for one. Every graft is wrapped so it can be disabled by config without touching the core (hexagonal — a weighting adapter, not domain surgery).

## 4. Architecture (minimal, reversible)

```
domain/ (pure)                         application/
 sizing (new): edge_weight(...),  ◄──   GraftedScreenUseCase (extends EvidenceScreenUseCase)
 abstain_by_regime(...)                 (reuse) all Phase-A/B/C use cases unchanged
config/
 graft.yaml (which edges live, weights, caps — all measured, all toggleable)
```

The graft is **config-gated and reversible**: `graft.yaml` lists each validated edge, its measured weight, its cap, and an on/off toggle. Default off; an edge turns on only after its gate passes and a re-validation (Section 5) confirms the graft itself didn't break calibration.

## 5. Validation (re-validate AFTER grafting — anti-overfitting)

Grafting can itself introduce bias (interaction effects, regime leakage). So:
- **Re-run the relevant pre-registered gate on the grafted engine**, point-in-time, net of costs — the graft must **preserve** the edge, not just inherit the claim.
- **Forward-track the grafted output** vs SPY/NDX via the existing `CallOutcome` scorecard; if forward calibration degrades below the gate, **auto-disable the graft** (config toggle) and revert to the abstaining-screen.
- **No compounding claims:** grafts do not "learn up" over time (ADR-045 Tier-3 is out). Each is a static, measured tilt, re-validated periodically.

## 6. Honest non-claims
- Even a passed graft yields a **modest** tilt (decayed factors, small drift) — the engine still does not "beat SPY by 20–30%."
- The grafted engine still **abstains** when regime/coverage is thin and still prints its scorecard. The graft sharpens ordering/sizing; it does not turn the tool into an oracle.

## 7. Testing
- `domain/sizing.py`: unit + Hypothesis (edge_weight ∈ [0, cap], monotone in measured effect, 0 when effect ≤ 0; abstain_by_regime returns neutral in flagged regimes).
- `GraftedScreenUseCase`: with-graft vs without-graft fixtures; assert reversibility (toggle off ≡ Phase-A output exactly) and that a degraded forward score auto-disables.
- Re-validation harness: grafted engine must still pass the source's planted-edge fixture and not false-PASS on zero-edge.
- `make check` green (mypy strict, 90% cov).

## 8. Open questions for reviewer (deferred until entry condition is met)
1. If two sources pass, combine grafts additively or keep them as separate toggleable tilts? (Lean: separate + capped sum.)
2. Re-validation cadence: monthly forward check, or on every N new resolved calls? (Lean: monthly + on-threshold.)
3. Sizing output: advisory percentages only, or integrate with the discipline engine's position-risk sizing? (Lean: advisory v1; never auto-trade — ADR-047.)

---

## 9. Phase Exit Gate → engine "done for now" (validate-as-we-go)

**On completing Phase D (if it ran):**
- [ ] Each grafted edge re-validated post-graft; `graft.yaml` records measured weight + cap + toggle.
- [ ] Grafted engine forward-tracked; auto-disable path tested.
- [ ] Toggle-off reproduces the pre-graft (Phase-A/B) output exactly.
- [ ] `make check` green; ADR-049 updated with the engine's final composition.

**If Phase D did NOT run** (no edge passed): record in ADR-049 that the engine ships as **research + discipline + abstaining-screen**, with the four-falsification lineage intact. This is the honest terminal state — the project's value is the disciplined process, the forward-accountable scorecard, and a senior-grade portfolio artifact, not a money-printer.

**Standing intercept:** any future "let's add signal X" requires a *new* pre-registered hypothesis with its own locked gate and ADR (ADR-047 rule) — never a tweak to a dead one. The gates are the product's spine; Phase D is the only door through them, and it stays locked until a test opens it.
