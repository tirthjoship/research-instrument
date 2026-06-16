# Risk Rubric — Design Spec

**Date:** 2026-06-13
**Status:** Locked (v3 mockup)
**Branch:** `feat/per-stock-decision-card`
**Mockups:** `.superpowers/brainstorm/risk-rubric/content/risk-v1..v3.html` (v3 = locked). v1 = A/B/C color comparison; v2 = hover clouds; v3 = numeric axis + endpoints.
**Sibling specs:** `2026-06-13-home-triage-design.md`, `2026-06-13-per-stock-decision-card-design.md`.
**Supersedes:** the inline RAG net-beta colors in the Home spec §2 ("green 0.8–1.2 · yellow 1.2–1.6 · red >1.6"). Home now uses the distance ramp defined here.

## 1. Problem

Net beta and systematic share render as raw numbers (e.g. `1.42`, `62.8%`) with no framing. A non-expert can't tell what's high, what's low, or where they stand — part of why the dashboard read as "gibberish" and produced 0 trades. We need a **legible risk rubric** on these metrics WITHOUT introducing a quality verdict (honesty rails: risk is *character*, not good/bad — high beta is a choice, not a mistake).

## 2. Core decision — character, not quality

The rubric describes **what the number means**, never whether it's good or bad. This is the load-bearing constraint and it drives every visual choice below.

- **Rejected:** RAG (green→red) coloring. Green→red reads as good→bad regardless of legend text; it re-creates the exact misread we're fixing. (Mockup A showed this; mockup C tried to keep RAG with a relabeled legend — still misread.)
- **Chosen (mockup B/v3):** a **mono-hue distance ramp anchored at market = 1.0**. Gray = market-like (the one reference a non-expert knows); deeper blue = farther from market in *either* direction. Defensive and Aggressive look equally "notable" — color encodes *distance from market*, never *worse*.

## 3. Scope

One rubric definition, reused on **both surfaces** (single source of truth, pure `domain/`):

| Surface | Metric(s) shown |
|---------|-----------------|
| Per-stock decision card (risk row) | that holding's beta to market |
| Home book panel | book net beta (SPY) **and** systematic share |

## 4. Bands

**Net beta** (character; full range incl. negative):

| Band | Range | Color |
|------|-------|-------|
| Hedged | < 0 | deep blue (`#1e3a8a`) |
| Defensive | 0 – 0.8 | light blue (`#60a5fa`) |
| Market-like | 0.8 – 1.2 | gray (`#cbd5e1`) — anchor |
| Elevated | 1.2 – 1.6 | light blue (`#60a5fa`) |
| Aggressive | > 1.6 | deep blue (`#1e3a8a`) |

**Systematic share** (monotonic — more macro-coupled = more notable; no "good" end, so a single-hue light→dark ramp, not a distance ramp):

| Band | Range | Color |
|------|-------|-------|
| Stock-specific | < 40% | `#ddd6fe` |
| Balanced | 40 – 60% | `#c4b5fd` |
| Macro-leaning | 60 – 75% | `#8b5cf6` |
| Macro-dominated | > 75% | `#5b21b6` |

The **60% boundary = existing `SYSTEMATIC_DOMINANT` flag line** (`config/markets/us.yaml: systematic_share_threshold: 0.60`). The rubric must read this threshold from config, not hardcode 60 — bands stay in sync with the flag.

## 5. Scale rendering (v3)

Every grid shows three things so a non-expert can place themselves instantly:

1. **▼ Needle** above the strip = where you stand (with the value label, e.g. "you 1.42").
2. **Axis ticks** below the strip at each band edge, with **bold anchors**:
   - Net beta: `0` and `1.0 (market)` are bold anchors; `0.8 / 1.2 / 1.6` are plain ticks.
   - Systematic share: `0% / 40 / 75 / 100%` plain; `60 (flag)` is the bold anchor.
3. **Endpoint captions** ◄ lowest / highest ► :
   - Net beta: ◄ *hedged (moves opposite)* … *aggressive (much swingier)* ►
   - Systematic share: ◄ *all your stock-picking* … *all the market* ►

Per-segment numeric labels are **removed** — numbers live on the axis only (user note: per-segment % was verbose).

**Axis math (linear position → %):**
- Net beta domain rendered `-0.5 → 2.0` (range 2.5): `pos% = (value + 0.5) / 2.5 × 100`. Values outside clamp to the end. (So 0→20%, 1.0→60%, 1.6→84%.)
- Systematic share domain `0 → 100%`: `pos% = value`.

Band segment widths are proportional to their numeric span within the rendered domain (not equal-flex), so a value's needle sits at its true position.

## 6. Copy (hover (i) clouds — hover-only, nothing printed on page)

Same pattern as Home/per-stock: each metric label carries a small `(i)`; on hover a dark cloud shows **term → your value → meaning → bands**. Cloud closes on mouse-out.

- **Beta / net beta:** "how much [this holding / your whole book] moves vs the market (market = 1.0). 1.42 → ~42% more, **up and down**. Not better or worse — livelier. Negative = hedged (moves opposite). Gray center = market; deeper blue = farther either way."
- **Systematic share:** "of all your book's wiggle, how much the **big market forces** (S&P, rates, dollar, energy) explain vs your own stock-picking. 62.8% → ~2/3 market, ~1/3 your picks. High = a **diversification illusion** — many names riding the market together. The 60% line is where we flag it."

## 7. Architecture

- **Pure `domain/`** — band thresholds + classification are stdlib-only domain logic (no framework imports). Add to `domain/macro_beta.py` (or a new `domain/risk_rubric.py` if `macro_beta.py` is growing too large — decide at build by file size).
  - `classify_net_beta(value: float) -> Band` → returns band enum/label.
  - `classify_systematic_share(value: float, threshold: float) -> Band` → threshold passed in from config, NOT hardcoded.
  - A small value object carrying `(label, color, needle_pos, band_edges)` so adapters render without re-deriving math. Position math (the `(v+0.5)/2.5` mapping) lives here too — pure, testable.
- **Adapter** (`adapters/visualization/`) consumes the value object and renders the strip + axis + needle + (i) cloud. No band logic in the adapter.
- Reuses existing `aggregate_macro_exposure` output (`net_beta_by_factor`, `systematic_share`).

## 8. Honesty rails (must hold)

- No good/bad verdict on risk; color = distance/intensity only. (Rail: risk is character.)
- No predictive content; this is descriptive of current exposure.
- Systematic-share flag line stays tied to the real config threshold — no fabricated bands.
- (i) copy defines the term for a non-expert first, then the value — never assumes prior knowledge.

## 9. Tests (pure domain, small fixtures)

- `classify_net_beta`: one per band + **boundary cases** (exactly 0, 0.8, 1.2, 1.6 — confirm which side each boundary falls; spec rule: lower bound inclusive, upper exclusive, i.e. `0.8 → Market-like`, `1.2 → Elevated`).
- Negative and extreme values (`-0.3 → Hedged`, `2.5 → Aggressive`).
- `classify_systematic_share`: bands + boundary at the **config threshold** (assert it reads 0.60 from config, and that 0.60 → Macro-leaning, i.e. the flag and the band edge coincide).
- Needle position math: `0→20%`, `1.0→60%`, `1.6→84%`, share `62.8→62.8%`; clamp test for out-of-domain values.
- Property test (Hypothesis): classification is monotonic in value (never jumps back a band as value rises).

## 10. Open items at build

- Confirm `domain/macro_beta.py` size → keep there vs new `domain/risk_rubric.py`.
- Per-holding beta source: confirm the per-stock card already has each holding's beta available, or whether it needs surfacing from `aggregate_macro_exposure`'s per-holding input.
