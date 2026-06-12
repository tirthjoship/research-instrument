# Skill Routing — Multi-Modal Stock Recommender

> **Purpose:** Which skill/agent to invoke at each phase of *this* repo, and what gate
> must pass before the next phase opens. Repo-specific projection onto the wrap plan
> (`docs/superpowers/specs/2026-06-10-strategic-wrap-plan-design.md`).
>
> **Read order:** `docs/STATUS.md` (Tier 0) → this file (routing) → the named spec/plan.

---

## Where this project sits

Portfolio flagship in WRAP mode (close by 2026-06-29, then maintenance). Direction is
LOCKED by ADR-052: deterministic risk/behavior CRO; the recommender ABSTAINS
(RESEARCH_ONLY), never predicts. Six falsifications + Unit B decide the predictive
question permanently.

## Phase → skill routing

| Phase | Gate to enter | Invoke | Model |
|-------|---------------|--------|-------|
| Unit B verdict | report JSON exists | execute the LOCKED §2 tree of the wrap spec — NO judgment calls; `verification-before-completion` on ADR-053 numbers | Opus |
| Unit C build | Unit B merged | `brainstorming` → `writing-plans` → `subagent-driven-development` | Opus plan / Sonnet build |
| Hardening sprint | Unit C merged | `writing-plans` → `subagent-driven-development`; `systematic-debugging` on any failure | Sonnet |
| Dashboard realign | hardening done (venv fixed) + Unit B verdict | spec + plan dated 2026-06-10 → `subagent-driven-development`; `frontend-design` for tab layout polish | Sonnet build / Opus review |
| Docs refinement | build complete | `humanizer` on the write-up; plain-language test (wrap spec §5.5) | Sonnet |
| Ship/wrap | review clean | `requesting-code-review` → `finishing-a-development-branch` → `caveman-commit` | Opus review |
| Maintenance (post-close) | project closed | read-only; `systematic-debugging` ONLY on breakage; ~1 hr/quarter budget | Sonnet |

## Always-on triggers (any phase)

| Situation | Invoke |
|-----------|--------|
| Need library/framework docs (yfinance, streamlit, click, plotly) | `context7` |
| Explore code structure without reading whole files | `smart-explore` |
| A test fails unexpectedly | `systematic-debugging` before any fix |
| About to claim "done / passing / fixed" | `verification-before-completion` — show command output |
| "Did we solve this before?" | `mem-search` |
| Methodology in doubt ("is our approach sound?") | `ds-methodology-review` |
| User wants understanding stress-tested | `grill-me` |

## Hard constraints these rules must never break

1. **No look-ahead bias** — all data timestamps ≤ prediction_time; `LookAheadBiasError` enforced.
2. **No framework imports in domain/** — stdlib only.
3. **Pre-registered gates stay LOCKED** — thresholds never tuned after seeing data; amendments are validity repairs only, recorded in the ADR.
4. **NO new signal hunting** (ADR-052) and **NO auto-retraining/online-learning loops** (wrap spec §5). Unit D stays parked (wrap spec §6).
5. Feature branches only — never commit to `main`/`develop`. Never `--no-verify`.
6. Tests use small fixtures — never hit real APIs in CI.
7. The recommender renders no "buy" language while RESEARCH_ONLY.
