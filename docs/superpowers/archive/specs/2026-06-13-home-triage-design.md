# Home Triage — Design Spec

**Date:** 2026-06-13
**Status:** Locked (v6 format) — refinements below to apply at build
**Branch:** `feat/per-stock-decision-card`
**Mockups:** `.superpowers/brainstorm/*/content/home-v1..v6.html` (v6 = locked); standalone `/tmp/home_v6_standalone.html`.
**Sibling spec:** `2026-06-13-per-stock-decision-card-design.md` (the drill-down target).

## 1. Problem

The shipped Home repeats REDUCE/TRIM holdings 3×, scatters counts, shows no per-stock evidence, and is illegible to a non-expert. Goal: a **3-second triage** that de-duplicates, leads with what needs attention, and drills into the per-stock decision card. Recruiter-safe (the dashboard is a portfolio piece).

## 2. Design (v6 locked)

Two states:

**A. Landing / empty state** (shown when no book is loaded; vanishes once loaded):
- "See the instrument on a sample book, or load your own."
- Three paths: **Explore sample book (10 stocks)** · **Upload holdings CSV** · **Add manually**.
- Privacy line: *holdings stay on your machine — never uploaded, never shown.*

**B. Populated** (sample or user's book):
- **Metrics strip** (≤5 tiles), each with a hover **(i)** glossary cloud:
  - **Need review** — ratio `4 / 10` (most actionable → visually dominant).
  - **vs Market (1y)** — book return − SPY, with Sharpe in the tooltip (risk-adjusted, per the project's "never claim beats-market without risk-adjustment" rule). Can be negative.
  - **Net beta** — color rubric: green 0.8–1.2 market-like · yellow 1.2–1.6 elevated · red >1.6 aggressive (descriptive of risk *character*, not quality).
  - **Regime** — RISK_ON/OFF with a "why" tooltip (breadth %, index trend).
  - (**Screener count moved OUT** of the strip → Screener nav; too tool-internal for prime real estate — research-backed.)
- **De-duplicated holdings list**, **"Needs review" first**, then "Holding steady" (collapsed). Each holding appears **once** as a mini-card: ticker · verdict pill · 5 RAG dots · sparkline · one-line meaning · unrealized % · `›` → opens the full per-stock card.
- Screener section (if kept on Home) states **why** 0 cleared (legible abstention), not just a number.

## 3. Refinements to apply at build (research-backed + user note)

Sources: eleken, userguiding, wildnetedge, fdcapital, UXPin, smashingmagazine, Google Design (Robinhood), pragmaticcoders.

- **Need review = dominant headline** (larger / badged), not one of five equals.
- **Plain-language line** under the strip: e.g. *"4 of your 10 holdings have signals worth reviewing."*
- **Directional arrows** on tiles, not color alone.
- **(i) icon smaller** (user note: too big next to labels).
- **Onboarding card conditional** — present at 0 holdings, gone once loaded.
- **No animated/blinking price numbers** (Robinhood dark pattern — anxiety, not insight).
- **No buy/sell CTAs** (matches honesty rails).

## 4. Tooltips (site-wide standard)

- Extend the existing glossary system (`adapters/visualization/components/tooltip.py`, `glossary.py`, the shipped 39-term glossary) to **every** metric on **every** tab.
- Hover-only: appear on hover, **close on mouse-out**. **Never printed on the page.**
- Copy **defines the term first** for a non-expert, then the value, then the implication. (e.g. "Net beta — how much your book moves vs the market, market = 1.0. You're 1.21 → ~21% more, up and down…")

## 5. Privacy

- Real holdings live only in `data/personal/` (gitignored); never uploaded anywhere.
- A bundled **sample book (10 representative tickers)** is the default demo for visitors/recruiters.
- Upload = local CSV parse (`ticker, shares[, cost_basis]`) into `data/personal/`.

## 6. Architecture (reuse-first)

- Reuse `data/personal/brief_summary.json` (holdings + verdicts, macro/net-beta/regime, screen), `domain/discipline.py` verdicts, `domain/macro_beta.py`.
- New: sample-book fixture + loader; CSV upload adapter; **vs-Market** calc (book vs SPY return + Sharpe) in `application`/`domain`; **net-beta color rubric** (pure `domain` thresholds); per-holding **mini-card** component; glossary extension to all metrics; `Screen` relocation to nav.
- Domain stays stdlib-only; yfinance/CSV live in adapters behind ports.

## 7. Testing

- FORBIDDEN_WORDS guard on every Home string + tooltip.
- Each metric has a glossary tooltip (presence test).
- Net-beta rubric + RAG threshold unit tests (pure domain); vs-Market sign + Sharpe test with fakes.
- De-dup: each holding rendered once (no 3× repeat).
- Privacy: sample/demo path never reads real `data/personal/` holdings; upload writes only locally.
- Onboarding card conditional on holdings count.

## 8. Open Questions

- Which 10 tickers seed the sample book?
- Exact net-beta rubric bands (0.8–1.2 / 1.2–1.6 / >1.6 — confirm).
- vs-Market default period (1y) and whether to expose a selector.

## 9. Out of Scope

- Buy/sell CTAs, predictive scores, animated prices. Drill-down detail lives in the per-stock card spec.
