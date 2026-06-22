# Spec Brief — SP6: Stock-Analysis Tabs (dashboard surface)

**Status:** Design brief (needs its own brainstorm → full spec → plan before coding)
**Depends on:** SP1 (engine), ideally SP2/SP3/SP4 (consumers) for full data
**Date:** 2026-06-20
**Note:** This is the user's originally-stated "next phase = tabs for stock analysis" goal.

## Purpose
Surface the corroboration ecosystem in the Streamlit dashboard so the user reads, trusts, and acts on it.
North-star: trust via legibility (memory `dashboard_trust_legibility`) — non-expert can tell what to
trust; show the evidence chain, not a number.

## Scope (in)
- A per-stock **analysis tab/card** rendering a `CorroboratedCandidate`: convergence tier (status-first
  colour), each verified source with its clickable citation + attributed thesis, our_readout (factor
  percentile, trend, divergence, discipline if held), uncertainty (coverage, freshness, conflict).
- A **DirectionalView** panel: theme/sector tilt map (LEAN_IN/HOLD/LEAN_OUT/AVOID) vs portfolio exposure.
- Prominent **RESEARCH_ONLY** framing; convergence shown as evidence strength, never a price forecast.

## Scope (out)
- No new prediction widgets, no return projections (the documented failure mode — memory
  `feedback_attributed_not_predicted`, `ux_redesign_must_show_before_ship`).

## Proposed approach
New tab module under `adapters/visualization/tabs/` (follow the decomposed risk/ package pattern). Reuse
shared components (`components/styles.py`, `cards.py`, `charts.py`). Render from the persisted snapshot
(`CorroborationStore`) so the tab is instant and offline-safe (no live pings on load — respect lazy-tab +
cross-tab-loading work, ADR-058 and memory `cross_tab_loading_plan`).

## Files likely touched
`adapters/visualization/tabs/stock_analysis/` (new package), `tabs/__init__.py`, dashboard nav,
shared `components/`.

## Open questions
- Tab vs per-stock card vs both — design in brainstorm with a mockup (MUST screenshot live header vs
  approved mockup before claiming done — memory `verify_render_against_mockup`).
- How it coexists with existing tabs (risk, weekly_brief, research, screener, positions, trust).
- Non-default Streamlit tabs screenshot blank (memory `streamlit_screenshot_lazy_tabs`) — verify via
  solo harness.
