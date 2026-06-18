# Project Context Index

> This file is a navigation index only. All detail lives in the docs below.
> Full history trimmed 2026-06-17 — see `git log -- CONTEXT.md` for prior content.

## Current state
→ `docs/STATUS.md` — phase, branch, next action, open items (read this first, it is short)

## Architecture decisions
→ `docs/adr/` — ADR-036 through ADR-061+; each decision and its rationale

## Phase history
→ `docs/PHASE_LOG.md` — full session-by-session history (open on demand only)

## Skill routing
→ `docs/SKILL_ROUTING.md` — which skill/agent to invoke per phase

## Project brief (what we built and why)
→ `README.md` — feature overview, data sources, setup instructions

## Design specs
→ `docs/superpowers/specs/` — approved design documents per feature

## Domain context (key facts, not full detail)
- **Core hypothesis:** sentiment leads price 1–48h; cross-modal divergence predicts 5-day returns
- **Architecture:** hexagonal (ports & adapters); domain/ is stdlib-only; no framework imports in domain/
- **Phase:** maintenance / RESEARCH_ONLY — no new prediction signals without explicit ADR
- **Critical constraint:** look-ahead bias is non-negotiable; `LookAheadBiasError` halts pipeline on violation
- **Evaluation:** Sharpe ratio + precision/recall — never raw returns or accuracy alone
