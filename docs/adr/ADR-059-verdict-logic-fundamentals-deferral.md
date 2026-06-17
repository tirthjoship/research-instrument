# ADR-059: Fundamentals stay attributed evidence — verdict-logic extension deferred behind the forward gate

**Date:** 2026-06-16
**Status:** Accepted
**Deciders:** Tirth Joshi
**Builds on:** ADR-045 (pivot prediction → discipline), ADR-046 (KILL standard), ADR-048 (pre-registered
forward-calibration gate), ADR-051 (calibration readiness), ADR-057 (decision card v9, 5 RAG evidence squares)

## Context

The per-stock verdict (`REDUCE / TRIM / REVIEW / HOLD / ADD_OK`) is produced by
`domain/discipline.grade_position` — the **trend-break rule v1**. It is already multi-signal
(trend_health vs 200-day ATR, trailing-stop breach, disposition risk, volatility, relative strength,
market-wide context). The v9 redesign (ADR-057) surfaces this rubric and presents earnings / valuation /
financials as **attributed evidence** — the 5 RAG squares — *alongside* the trend-driven verdict.

**The question (raised 2026-06-14, deferred):** should the verdict logic be **extended** to fold
fundamentals **into** the `REDUCE/TRIM/BUY` decision itself, rather than presenting them only as evidence?

This was deliberately not done as a silent edit: it changes what the instrument *claims* (the verdict would
assert a fundamental view, not just a discipline/trend prompt), which risks the **attributed-not-predicted**
honesty stance. It deserves a grill + ADR + measured rule comparison — which this ADR records.

### What grounded the decision (verified, not assumed)

1. **v1 is unproven — it cannot have cleared its own gate.** `data/personal/discipline_log.jsonl` holds
   231 REDUCE flags dated **2026-06-08 → 2026-06-15**. The ADR-048 gate resolves REDUCE at a **21-trading-day**
   horizon and requires **n ≥ 30 resolved** flags (plus down_rate ≥ 55%, brier ≤ 0.45). As of 2026-06-16 the
   earliest flag is ~8 calendar days old → **0 flags are resolvable yet**. The first resolves ~July 2026;
   n ≥ 30 later still. The in-sample 58% down-rate is survivor-biased — "a report card, not proof" (ADR-048).

2. **Industry/academic norms (web-checked 2026-06-16) — our foundations are mainstream, not idiosyncratic:**
   - **Measurement-first is the field standard.** Real out-of-sample returns average ~26% below in-sample,
     dropping a further ~58% post-publication (Bailey & López de Prado, *Deflated Sharpe Ratio*; PBO;
     walk-forward as the validation gold standard). Our gate is appropriately cautious, not purist.
   - **Combining fundamentals into a signal is normal** (the "mix vs integrate" debate; standardized
     dollar-neutral composites, cross-sectional ranking). So the constraint is **how**, not **whether**:
     a measured composite — which *requires a resolved baseline first*.
   - **Disposition effect** is the most-documented bias (sell winners early, hold losers too long), and
     willpower / "but it's a good company" does **not** fix it — only mechanical rules do. Disciplined
     practice uses weakening fundamentals as an **additional exit trigger**, never as a reason to rescue a
     loser through a stop breach.

## Decision

**1. Fundamentals stay attributed evidence (the 5 RAG squares). The verdict remains trend-break rule v1.**
No fundamentals are folded into `grade_position` now. Rationale: the disciplined way to integrate is a
**measured composite**, and lift cannot be computed against a baseline with 0 resolved flags. This is not
"fundamentals don't belong" — it is "integrate them the disciplined way, which needs the baseline first."

**2. Revisit only after v1's forward gate resolves (PROCEED or KILL).** If v1 PROCEEDs, fundamentals become a
**candidate modifier**, treated as a new rule measured against v1 via the same forward-gate discipline
(ADR-048/051). The live rule is never swapped without beating v1 — the standard that killed ADR-039/043/044/046.

**3. Locked design principle for any future extension — the asymmetric (caution-only) veto:**
   - Fundamentals may **push toward caution**: downgrade an optimistic verdict (e.g. `ADD_OK → REVIEW/HOLD`)
     or reinforce an exit. This is industry-normal and anti-disposition-aligned.
   - Fundamentals may **never rescue** a name from a trend-driven `REDUCE`. Using "good fundamentals" to soften
     a stop-breach exit *is* the disposition effect the engine exists to counter.
   - Fundamentals may **never fabricate direction** out of nothing.
   - Corollary: any fundamentals-sourced *down*-call (weak fundamentals strengthening a REDUCE) is still a
     down-call → it feeds the gated signal and **owes the ADR-048 gate** like any other.

**4. The gate horizon is not retroactively shortened.** Shortening the pre-registered 21-day horizon on
existing flags to get a faster answer is p-hacking. If 21 days is genuinely wrong for the actual decision
cadence, a *shorter horizon must be re-registered prospectively* (for flags from that date forward), accepting
the restarted clock and noisier short-horizon signal. Open input needed: the real decision cadence on these
holdings (weekly vs monthly) — that, not impatience, would justify a re-registration.

## Consequences

- **Honesty stance held.** The verdict stays a discipline/trend prompt; fundamentals stay attributed,
  preserving the attributed-not-predicted line.
- **No code change in this ADR** — `grade_position` and the RAG evidence squares are unchanged. This is a
  recorded deferral + a pre-locked constraint, so a future mid-build session cannot drift toward a "full flip."
- **Re-entry trigger:** when the ADR-048 gate reaches a verdict (≈ when n ≥ 30 resolved REDUCE flags accrue),
  open the extension as a measured-composite experiment under the asymmetric-veto constraint above.
- **Unblocks the Risk-tab UI sprint** (R01–R08, separate work) without entangling it in a methodology change.

## Related

- ADR-048 (forward gate), ADR-051 (calibration readiness), ADR-057 (decision card v9 / 5 RAG squares)
- Memory: `project-verdict-logic-extension-question` (now resolved by this ADR)
