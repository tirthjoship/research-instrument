# Strategic Wrap Plan — Real-Money Success Framework + Project Close by 2026-06-29

**Date:** 2026-06-10
**Status:** Approved (user, 2026-06-10)
**Builds on:** ADR-052 (CRO direction, alpha hunt closed), ADR-048/051 (forward gate),
ADR-053 draft (Unit B verdict, pending)

## Purpose

Pre-commit the strategic decision tree BEFORE the Unit B verdict exists, define what
"success with real money" measurably means, and close the project by 2026-06-29 into a
self-sustaining (deterministic, fail-loud, passive-accrual) state. All build work lands
by 2026-06-17; Jun 17–29 is refinement/sharpening only.

## §1 North star + success metrics

Success = measured risk-adjusted improvement of the user's actual 66-name book, through
three channels, each with its own metric and verdict date:

| Channel | Metric | Verdict point |
|---|---|---|
| Behavior-gap closure | Forward gate (ADR-048/051): REDUCE/TRIM flags vs inaction | ~mid-July 2026 |
| Risk control (Unit A) | Net-beta drift, systematic-variance share, flag adherence | Continuous; 6-mo review Dec 2026 |
| Predictive sleeve (Unit B) | Pre-committed decision tree (§2) | Full-window verdict (imminent) |

**Self-experiment:** an adherence column in the weekly discipline log — "tool said X,
user did Y, gap P&L." After 6 months this yields the user's own measured behavior gap
in bps (literature anchor: ~848 bps/yr disposition effect). This number is the
project's real-money ROI.

## §2 Unit B pre-committed decision tree (LOCKED 2026-06-10, before full-window verdict)

- **PASS** (net CI_low > 0): NO real money. 6-month forward paper validation — live
  cluster signals logged weekly by an automated job, paper fills at next-day open.
  (CONDITIONAL BUILD ITEM: this logger does not exist yet; a PASS verdict adds it to
  the build week — a small job reusing the SEC adapter + detect_clusters on the
  latest quarter, appending to a paper-trade log. No PASS → not built.)
  Single review ~Dec 2026/Jan 2027. Paper result consistent with backtest → live sleeve
  **≤ 5% of book, hard cap**, with pre-set kill switch: rolling-6-month sleeve net
  abnormal ≤ 0, OR sleeve drawdown > 30% → permanent kill. Paper inconsistent → KILL.
- **INCONCLUSIVE** (gross CI_low > 0, net ≤ 0): **final KILL by default.** The open
  question (realized execution cost vs the assumed 150 bps) would require a hands-on
  measurement experiment ("Unit D") that conflicts with project wrap. Unit D is PARKED
  as a documented option (see §6), not scheduled. No relitigation without it.
- **KILL** (gross CI_low ≤ 0): prediction permanently closed per ADR-052. Zero
  relitigation. The kill becomes the final chapter of the public write-up.
- **THIN_N / THIN_COVERAGE**: data insufficiency, not evidence. ONE remediation re-run
  is allowed — the M1/M2 amendment (§3) consumes that allowance. Still thin after →
  practical KILL: cannot validate ⇒ cannot ever trade.

**Sleeve cap rationale (pre-committed to defuse future overallocation):** at 5%, total
sleeve loss is recoverable; at smoke-run gross (~+1.6%/21d event) a surviving edge adds
roughly 0.5–1%/yr at book level. Cap chosen while holding no position — same logic as
pre-registered thresholds.

## §3 M1/M2 amendment — applied BEFORE the full run (documented deviation)

Both are validity bugs in event detection, fixed before the full-window run; recorded
in ADR-053 as an amendment made after the smoke run but before the full verdict, with
rationale (validity repair, not threshold tuning):

- **M1 — joint-filing dedup:** one Form 4 filed jointly by N reporting owners is ONE
  buy decision. Cluster requires ≥3 distinct insiders across ≥3 distinct accession
  numbers (or equivalent dedup of identical transaction rows fanned out per CIK).
- **M2 — point-in-time terciles:** per-EVENT ADV (no per-ticker dict collision where
  the last event's ADV bins all of a ticker's events), and tercile boundaries computed
  from an expanding point-in-time cross-section: an event is binned against the ADV
  distribution of all events with fire_date ≤ its own. Stability rule: until the
  expanding cross-section reaches a minimum population (implementation plan fixes the
  exact N, default 30), events are still binned against whatever cross-section exists —
  noisy early bins are accepted and disclosed rather than silently deferred (deferring
  would drop early events from the denominator, recreating the survivorship problem
  C1 fixed).

Honest expectation, accepted in advance: M1 removes fabricated clusters → event count
drops → THIN_N risk rises. That outcome is valid.

## §4 Capital deployment ladder

- **L0 (now):** tool is advisory-only.
- **L1 (mid-July, if forward gate PASS):** tool-gated trading — every real trade passes
  the discipline check first; adherence logged. Gate FAIL → stays L0; investigate
  before any gating.
- **L2 (Unit B PASS + paper pass only):** predictive sleeve ≤ 5%, reachable no earlier
  than ~Jan 2027.
- Real money flows through L1 regardless of Unit B; the behavior channel is the proven
  one.

## §5 Self-sustainability — honest definition (approved)

**Rejected:** "self-improving ML with no future fixes." Reasons recorded: (1) six
falsifications established no validated objective exists for unattended retraining to
improve toward — online learning here fits noise and drifts; (2) unattended ML fails
silently while external data rots (yfinance rate limits, delistings, symbol-format
changes — all hit within the last 48 hours); (3) the deterministic core is the only
part that can run unattended safely (ADR-052's design).

**Adopted:** deterministic core + passive evidence accrual + fail-loud:

- Evidence improves itself; code doesn't. The Saturday discipline job accrues forward
  gate + adherence data weekly with zero code changes.
- Health-check wrapper on the weekly job: any data-fetch failure is reported loudly
  (log line / notification); the job never silently emits garbage.
- Auto-prune delisted tickers (log + skip) instead of crashing.
- Retry/backoff on all external fetches.
- **Maintenance budget: ~1 hour/quarter** when a free-data API changes. Zero-touch
  weeks otherwise. Post-wrap interactions are reading verdicts (calendar reminders:
  mid-July gate, Dec self-experiment review), not coding.

## §6 Out of scope / parked

- **Unit D (realized-slippage measurement with tiny real orders):** parked, documented
  here only. Preconditions if ever revived: Unit B full-window INCONCLUSIVE with gross
  CI_low > 0; pre-registered budget and order plan; measured cost < gross edge required
  to amend the net leg.
- Any new signal/alpha hunting (ADR-052 closure stands).
- Any auto-retraining / online-learning loop.
- Tax-loss/wash-sale features (65/66 accounts registered — moot).

## §5.5 Plain-language documentation (hard deliverable, user requirement 2026-06-10)

All reader-facing documents — README, ADR-053 (and a pass over key earlier ADRs),
the verdict table, STATUS — must be understandable by a non-financial reader:

- Every finance/stats term defined on first use in plain English (e.g., "CI_low > 0 —
  the worst plausible average outcome is still a profit"; "slippage — the hidden cost
  of actually buying a thinly-traded stock"; "tercile — bottom/middle/top third").
- A short glossary section in the README.
- The verdict table phrased as plain questions: "Does X predict Y? — No (tested
  2006–2024, here's how)."
- Test of done: a reader with no finance background can answer "what did this project
  try, what did it find, why is the finding trustworthy" from the README alone.

## §7 Timeline

Dates are targets, not hard gates (user 2026-06-10: faster is better; quality and
self-sufficiency are the hard requirements).

- **Jun 10–16 (build week, everything lands):**
  1. M1/M2 fixes (TDD) → restart full 2006–2024 run → Unit B verdict → execute §2
     branch → finalize ADR-053 → merge `feat/insider-cluster-falsification`.
  2. Unit C: anti-overtrade throttle + cash-buffer policy (deterministic, folded into
     discipline engine).
  3. Adherence-logging column in the weekly discipline log.
  4. Hardening sprint: health checks, auto-prune, retry/backoff (§5).
- **Jun 17–29 (refine/sharpen, no new build):** verdict-table README rewrite,
  falsification write-up, plain-language documentation pass (§5.5), code polish,
  bug fixes, final STATUS/handoff doc. Project closed 2026-06-29 or earlier.
- **Post-wrap calendar:** mid-July forward-gate verdict (→ L1 decision, ~30 min);
  Dec 2026 self-experiment review (~30 min).

## Open items folded into build week

- C1 CLI echo KeyError: FIXED + committed (85f2eff) with end-to-end regression test.
- Shared-venv drift (mypy, feedparser, networkx, plotly missing) — fix during
  hardening so `make check` runs clean.
- Untracked `data/reports/divergence_ic_21d.json`, `momentum_discipline.json` —
  commit or gitignore during refinement.
