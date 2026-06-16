# Screener Redesign — Plans Index

**Spec:** `docs/superpowers/specs/2026-06-14-screener-redesign-spec.md`
**Canonical mockup (drift reference):** `.superpowers/brainstorm/screener-FINAL-v2.html`
(served live during implementation — refresh the companion URL to compare any rendered surface).

One combined build (no Track-1/Track-2 split in product). Seven per-subsystem plans, in build order.
Each plan produces working, tested software on its own. Later plans depend on earlier ones landing.

| # | Plan | Subsystem | Depends on | Risk |
|---|------|-----------|-----------|------|
| 1 | `…-S4-factor-bands.md` | Pure z/percentile → plain-language band + plain-read template | — | low (pure) |
| 2 | `…-S1-factor-model.md` | Add Low-vol factor, resolve Revision (spike), asset-growth, IC re-run | — (spike first) | **high** (scoring/methodology) |
| 3 | `…-S2-bucket-engine.md` | Deterministic 6-bucket assignment, repeats, empty states | S4 | medium |
| 4 | `…-S3-screener-ui.md` | Tab rewrite to Home tokens: tiles, legend, toggle, collapsible 5-factor cards | S1,S2,S4 | medium |
| 5 | `…-S5-zone2-parity.md` | "Check your own list" full-matrix parity (lookup / live-compute / DATA-GAP) | S1,S3,S4 | medium |
| 6 | `…-S6-gemini-read.md` | Attributed Google-AI read on row expand (never an input to score) | S3 | medium |
| 7 | `…-S7-history-to-trust.md` | Move screen-history table to Trust tab | S3 | low |

## Drift guard (per user request)
Every UI plan (S3/S5/S6/S7) carries a **mockup pin** block listing the exact element + tokens from
`screener-FINAL-v2.html` it must match (fonts, color vars, layout). After each UI task, the reviewer
opens the live companion mockup and the rendered tab side by side and confirms no structural drift.

## Methodology gate
S1 must pass a `ds-methodology-review` before its factor math is locked (Low-vol definition, Revision
resolution, asset-growth, leakage). The IC gate (`backtest-screen`) is the arbiter of "predictive"
vs "descriptive"; default is descriptive + disclosed. No factor is presented as predictive unless the
gate PASSes.

## Honesty invariants (all plans)
FORBIDDEN_WORDS clean (`domain/fit.py:13-21`); no forecast wording; DATA-GAP never faked; attributed-
never-adopted (Gemini never feeds the score); no look-ahead; `git checkout data/reports/` before verify.
