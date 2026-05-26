# ADR-006: SQLite over PostgreSQL for initial storage

**Date:** 2026-05-23
**Status:** Accepted
**Deciders:** Tirth Joshi

## Context
Need persistent storage for weekly recommendations, accuracy records, and watchlist. Options: SQLite, PostgreSQL, DuckDB, flat files.

## Decision
SQLite for Phase 3. Single file, zero setup, handles years of weekly data.

## Alternatives Considered
- **PostgreSQL** — needs server, overkill for solo project.
- **DuckDB** — analytics-oriented but less standard for app storage.
- **Flat files (JSON/CSV)** — no query capability, poor for accuracy lookups.

## Consequences
**Positive:**
- Zero infrastructure.
- Portable (file lives in repo).
- Handles concurrent reads fine for single-user.
- Port interface means swap to PostgreSQL by changing one adapter.

**Negative:**
- No concurrent writes (irrelevant for weekly batch pipeline).
- No remote access for dashboard (Phase 5 will address).
- Mitigated by RecommendationStorePort abstraction.

## Superseded By
None
