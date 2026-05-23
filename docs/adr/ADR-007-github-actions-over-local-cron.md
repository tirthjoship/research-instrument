# ADR-007: GitHub Actions over local cron for weekly pipeline

**Date:** 2026-05-23
**Status:** Accepted
**Deciders:** Tirth Joshi

## Context
System needs to run autonomously every Sunday to generate weekly picks. Options: local cron/launchd, GitHub Actions scheduled workflow, cloud VM, Railway/Render.

## Decision
GitHub Actions with Sunday cron schedule + workflow_dispatch for manual testing.

## Alternatives Considered
- **Local Mac cron** — requires machine to be on/awake.
- **Cloud VM** — more setup, costs money.
- **Railway/Render** — adds infrastructure dependency.

## Consequences
**Positive:**
- Free (2000 min/month, pipeline needs ~5-10 min).
- Already have CI/CD set up.
- Logs visible in repo.
- Portfolio reviewers can see automation.
- No machine dependency.

**Negative:**
- Cron accuracy — GitHub Actions can delay up to 15-60 minutes (acceptable for Sunday night run).
- API keys in GitHub Secrets (secure but one more config step).
- Free tier budget is tight if pipeline grows.

## Superseded By
None
