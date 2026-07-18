# ADR-042: Full IC Confidence Interval + Look-Ahead Caveat Printed on Every `backtest-screen` Run

**Status:** Accepted (backfilled 2026-07-17 — implemented earlier, never written up)
**Related:** ADR-011 (rigorous evaluation framework), ADR-044 (divergence IC verdict)

## Context

`application/cli/screen_commands.py`'s `backtest-screen` command writes a
full JSON report (IC, bootstrap CI, verdict, caveat) to disk — but a JSON
file sitting in a report directory is easy to skim past or never open.
Nothing stopped a terse, encouraging-looking stdout summary from omitting
the same honesty the JSON report carries, letting a user walk away with a
rosier impression than the data supports.

## Decision

Stdout must print, on every single run, unconditionally:

- The full bootstrap confidence interval on mean IC (`[low, high]`, or
  `"n/a (n<2)"` when there isn't enough data — never silently omitted).
- The verdict label in full sentence form (PASS / INCONCLUSIVE / HALT),
  not just the bare enum value.
- The exact look-ahead-bias caveat text (project rule #2): composite is
  tested on the momentum leg only, since revision/quality/value lack
  point-in-time history for 2018-2026 and were flagged-neutral to avoid
  look-ahead bias.

Enforced by `tests/test_cli_screen.py::test_backtest_screen_stdout_includes_caveat`
and `::test_backtest_screen_stdout_includes_ci` — both assert directly on
CLI stdout content, not just the JSON report file.

## Consequences

**Positive:** No code path can produce a "looks good" terminal summary
that hides the confidence bounds or the look-ahead-bias caveat behind a
JSON file most users won't open — the honest picture is unavoidable at
the point of use.

**Negative:** Verbose stdout for a command that might be run frequently
during iteration; accepted as the right trade-off given this project's
core discipline (never let a positive-looking result travel without its
uncertainty attached).
