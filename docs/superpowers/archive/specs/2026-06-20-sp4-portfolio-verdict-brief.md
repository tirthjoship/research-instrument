# Spec Brief — SP4: Portfolio-Verdict Integration (Corroboration consumer)

**Status:** Design brief (needs its own brainstorm → full spec → plan before coding)
**Depends on:** SP1 Corroboration Engine; existing `weekly-brief` / `portfolio-verdict` / discipline engine
**Date:** 2026-06-20

## Purpose
Add "what credible sources now say about YOUR holdings" to the weekly verdict, so the engine improves the
direction it gives on the user's real book — beyond discipline flags alone. The user's ask: "engine sees
the portfolio and recommends which stream to go in / which we shouldn't."

## Scope (in)
- For each held ticker, attach its `CorroboratedCandidate` (held=True) to the weekly verdict.
- Use `DirectionalView` to flag exposure vs evidence: "evidence clustering in AI-infra; your book is
  light there → LEAN_IN" / "thinning in X; you're heavy → LEAN_OUT". Attributed, RESEARCH_ONLY.
- Combine with existing discipline flags (REDUCE/HOLD/ADD_OK) WITHOUT overriding them — show both.

## Scope (out)
- No automated trades, no buy/sell instruction — direction + evidence only (user decides).
- Does not replace the ADR-048 discipline gate (that stays the holdings risk authority).

## Proposed approach
Extend `weekly_brief_use_case` (after the holdings_risk crash is fixed — SP7) to call the corroboration
snapshot for held tickers and render a per-holding evidence block + the `DirectionalView` tilt section.
Reuse `GeminiNarratorAdapter` cited-case style for the attributed narrative (it already forbids buy/sell
words).

## Files likely touched
`application/weekly_brief_use_case.py` (modify), `application/cli/brief_commands.py` (modify),
`adapters/visualization/` portfolio/risk tabs later (SP6).

## Open questions
- Conflict display when discipline says REDUCE but sources say bullish (default: show the conflict
  explicitly as CONFLICTED — never silently pick a side).
- Theme/sector exposure source = Questrade holdings (`holdings_reader`, feat/questrade-holdings branch).
- Depends on SP7 fixing the `weekly-brief` `holdings_risk._vol` crash first.
