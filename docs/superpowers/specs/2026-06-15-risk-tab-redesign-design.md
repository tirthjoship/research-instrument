# Spec — Risk Tab Redesign ("Where your book stands")

**Date:** 2026-06-15 · **Status:** Locked (design approved from mockup v8) · **Author:** Tirth Joshi (+ Claude)
**Mockup of record:** `.superpowers/brainstorm/65055-1781542394/content/risk-v7.html` (eyebrow reads "v8 — full methodology")
**Reuse map:** `research/2026-06-15-risk-tab-existing-infra.md`
**Builds on:** ADR-052 (deterministic risk/CRO engine), ADR-057 (Home + decision-card redesign), the shipped macro-beta scrubber.

---

## 1. Goal & north-star

Rebuild the Streamlit **Risk tab** (`tab2`) into a single legible surface that answers three questions in one
progressive-disclosure stack — **"Am I safe? · What do I do? · Teach me"** — for a non-expert investor, while
hardening the underlying statistics to portfolio-credible standards.

North-star (from `feedback-dashboard-trust-legibility`): **non-expert legibility + projected trust via legible,
attributed evidence — never re-added prediction.**

### Honesty rails (non-negotiable, enforced by tests)
1. **Heuristic, not edge.** Dials are descriptive risk *character*, labeled "heuristic surfacing dial, not a validated
   edge · ADR-052". Nothing forecasts returns.
2. **Character ≠ quality.** Risk magnitude is never graded good/bad. Distance spectrums are symmetric.
3. **Attributed-not-predicted.** Sector "gaps" are *descriptive only* (name what's absent; never "buy X"). Google AI
   is an *attributed second opinion*, never the verdict, never a trade call.
4. **FORBIDDEN_WORDS** (`domain/fit.py`) scanned on every new rendered surface.
5. **Privacy fail-safe.** Any network/AI surface gated by `is_local_runtime()`; hidden when not local.

### Colour contract (the whole page, four colours)
- 🟢 **Green** = within your lines / no flag.
- ⬜ **Grey ramp** = neutral character / distance-from-market (no good/bad; symmetric).
- 🟠 **Amber** = a defined line crossed → "look here".
- 🔵 **Petrol** = your exposures (the only *data* hue). Direction shown by position + solid (long) vs hollow (short),
  not a second colour.

---

## 2. Page structure (top → bottom) — maps 1:1 to mockup v8

1. **Header** — eyebrow "Portfolio Risk", H1 "Where your book stands", ADR-052 heuristic line.
2. **Status banner** — traffic-light on *flags only*: "N of your risk lines are crossed" (amber) or "All clear"
   (green). Shows what it's measured against (the market β=1.0 · your risk lines · last week).
3. **Colour-contract legend** — "the whole page in three colours" + petrol.
4. **Lens jump-nav** — Am I safe? / What do I do? / Teach me (anchors).
5. **Vitals strip** — Effective bets (ENB) `3.2/66` · Net beta `1.18 ±0.09` · Downside beta `1.31×` ·
   Systematic share `71% ±5 (adj 66%)` · Diversification ratio `1.4×`. Each with `tooltip()`.
6. **Am I safe? — The Standing** — character pills (MARKET-LIKE · CONCENTRATED·FLAGGED) + one-sentence plain read +
   "translation" block.
7. **What do I do? — Dials** — three gauges (Market exposure=green/no-line · Diversification=grey/character ·
   Concentration=amber/flagged) + "positions on a spectrum, not scores" note.
8. **Grill-into-the-flag** — expandable drill-down on each flagged item (why it flagged · drivers · levers).
9. **The evidence — band strips** — net-beta grey distance ramp (symmetric) + systematic-share strip with the **60%
   flag line, amber over-zone, and a shaded 90% bootstrap band** around the needle.
10. **What's driving it — factor chart** — the configured factors as diverging petrol bars (solid long / hollow short),
    **confidence whiskers**, factors whose CI straddles 0 **greyed `≈0`**, **VIF caveat** ("collinear → one cluster").
    (Comes BEFORE the ENB section, matching the approved mockup.)
11. **How many real bets? — ENB section** — hero `3.2`, PCA principal-portfolio variance bars (PC-1 64% …), and an
    **expandable drill-down** naming the ~3 bets from PC loadings (e.g. big-tech market beta · duration/rates ·
    semis-vs-software) + "how to raise it" (add an axis you're empty on — reuses sector gaps; don't reshuffle within
    Bet 1; descriptive). If loadings are inconclusive, fall back to generic "Bet N" + DATA-GAP (no fabricated names).
12. **Sector concentration** — GICS sector weights + **HHI**, plus **descriptive diversification gaps** ("0% Health
    Care / Staples / Utilities …, historically less in step with a tech-growth bet") tagged `DESCRIPTIVE · NOT A BUY CALL`.
13. **Who owns the bet** — per-holding **risk contribution** (Euler, % of variance, sums to 100%), tagged `RISK ≠ $`,
    with the DATA-GAP coverage note.
14. **Has it moved? — drift** — 8-week systematic-share sparkline (grey→amber after crossing) + DRIFT flag context.
15. **Second opinion — Google AI** — attributed blind-spot panel (RESEARCH_ONLY, fail-safe, throttled+cached,
    hidden if not local / unreachable).
16. **Teach me — risk story** — collapsible 4-question plain-English walkthrough.
17. **Active flags** + honesty footer + coverage.

---

## 3. New statistics (domain math) — all descriptive

All live in **pure domain** (`domain/`, stdlib + numpy-in-adapter boundary respected: heavy linear algebra that needs
numpy/sklearn goes in an **adapter**; pure arithmetic stays in domain, mirroring the existing
`macro_beta.py` (pure) / `macro_beta_analyzer.py` (sklearn) split).

| # | Stat | Definition | Inputs | Output |
|---|------|-----------|--------|--------|
| 1 | **ENB** | PCA of holdings return covariance → variance fractions `pᵢ` along principal portfolios → `exp(−Σ pᵢ ln pᵢ)`; also top-3 PC variance shares + dominant loadings | holdings aligned return matrix | `enb: float`, `pc_variance: list[float]`, `pc_labels: list[str]` |
| 2 | **Systematic share band** | book R² (existing) + **adjusted R²** `1−(1−R²)(n−1)/(n−p−1)` + **bootstrap** (resample residual days, refit) → 5th/95th pct | book returns, factor returns, n, p | `sys_share`, `sys_share_adj`, `sys_share_ci=(lo,hi)` |
| 3 | **Beta CIs** | per-factor SE from OLS/ridge resampling; CI=β±1.645·SE (90%); `suppressed` if CI straddles 0 | book/holding fit | `beta_ci_by_factor: dict[str,(lo,hi)]`, `suppressed: set[str]` |
| 4 | **Downside beta** | net beta refit on **market-down days only** (SPY return < 0) | returns filtered on SPY<0 | `downside_beta: float` |
| 5 | **Risk contribution** | Euler: `RCᵢ = wᵢ·(Σw)ᵢ / (wᵀΣw)`, sums to 1 | weights, holdings covariance | `risk_contribution: dict[ticker,float]` |
| 6 | **VIF** | per factor `1/(1−R²ⱼ)` regressing factor j on the others | factor return matrix | `vif_by_factor: dict[str,float]` |
| 7 | **Diversification ratio** | `(Σ wᵢσᵢ)/σ_portfolio` | weights, vols, covariance | `diversification_ratio: float` |
| 8 | **Sector concentration** | GICS sector per holding (provider+cache) → dollar weights + **HHI**; descriptive `gaps` = standard sectors with ~0 weight | holdings, sector map | `sector_weights: dict`, `sector_hhi: float`, `sector_gaps: list[str]` |
| 9 | **Drift history** | last-8-weeks `systematic_share` series persisted weekly | weekly history store | `sys_share_history: list[(date,value)]` |

**Statistical notes baked into the UI copy:** in-sample R² is upward-biased → show *adjusted* + *bootstrap band*;
multicollinear factors (VIF>5) read as one cluster; betas with CI crossing 0 are not shown as real; risk contribution
≠ dollar weight; ENB is the rigorous restatement of the concentration thesis.

---

## 4. Data contract changes

Extend `BookMacroExposure` (`domain/models.py`) and the serializer (`application/brief_summary.py`) so the JSON
`macro` block carries the new fields. **Additive only** — existing fields and `tabs/risk.py` consumers unaffected
until the tab is rewritten. New `macro` keys:

```
enb, pc_variance[], pc_labels[],
systematic_share_adj, systematic_share_ci[lo,hi],
beta_ci_by_factor{f:[lo,hi]}, suppressed_factors[],
downside_beta,
risk_contribution{ticker:frac},            # per-holding (now serialized; today omitted)
holdings_meta[{ticker,name,sector,weight}],# names+sectors for who-owns + sector breakdown
sector_weights{sector:frac}, sector_hhi, sector_gaps[],
vif_by_factor{f:vif}, diversification_ratio,
sys_share_history[[date,value]]
```

`MacroBetaUseCase.execute()` extends to compute these (it already holds `holding_rets`/weights in memory for the
covariance-based stats). Sector lookup + weekly history are **new adapters/stores** (see §6 dependencies).

## 5. Reuse (do not rebuild)
`tooltip()`+`GLOSSARY` (add new terms) · `apply_dossier_template` · `render_verdict_card` · band-strip helper pattern ·
`is_local_runtime()` gate · the full Gemini stack (`select_case_summarizer`, `RateLimitedCaseSummarizer`,
`case_cache`, `TemplateCaseSummarizer`, `render_gemini_read`/`_case_html` pattern) · `FORBIDDEN_WORDS` · global
`styles.py` tokens (extend with status-first vars `--ok/--amber/--g0..g2`).

## 6. New build (what we don't have)
- Domain: `domain/risk_stats.py` (pure: adjusted R², ENB-from-eigenvalues entropy, diversification ratio, risk
  contribution from covariance, VIF arithmetic, downside-filter helper) + an adapter
  `adapters/ml/risk_stats_analyzer.py` (numpy PCA/eigendecomposition, bootstrap resampling, OLS SE).
- Sector source: `adapters/data/sector_provider.py` (yfinance `.info['sector']`, cached to
  `data/personal/sector_map.json`; offline-safe fallback → `sector="Unknown"`, surfaced as DATA-GAP). Verify yfinance
  field via context7 before coding.
- Weekly history store for `sys_share_history` (append-only JSONL `data/personal/macro_history.jsonl`, written by
  `weekly-brief`).
- Risk **Google-AI second-opinion**: a risk-specific summarizer call (reuse Gemini adapter + rate-limiter + cache key
  `risk_second_opinion`), prompt = "name blind spots in this risk read" with FORBIDDEN_WORDS forbidden; render via a
  new `components/risk_second_opinion.py` mirroring `render_gemini_read`; gated by `is_local_runtime()`.
- UI: rewrite `tabs/risk.py` render to the v8 layout + status-first CSS additions in `styles.py` + ~15 new `GLOSSARY`
  entries (ENB, adjusted R², bootstrap band, downside beta, risk contribution, VIF, diversification ratio, HHI, GICS,
  drift, risk line, coverage, systematic share, net beta, concentration).

## 7. Architecture (hexagonal)
`domain/risk_stats.py` (pure) ← `adapters/ml/risk_stats_analyzer.py` (numpy/sklearn) + `adapters/data/sector_provider.py`
→ orchestrated by extended `MacroBetaUseCase` → serialized by `brief_summary.py` → read by `data_loader` → rendered by
`tabs/risk.py`. Domain stays framework-free; all numpy/yfinance/network in adapters.

## 8. Testing
- Property tests: ENB ∈ [1, n]; ENB = n for equal-uncorrelated, = 1 for perfectly-correlated; risk contributions sum
  to 1.0; systematic_share_adj ≤ systematic_share; suppressed-factor set excludes any whose CI crosses 0.
- Honesty: FORBIDDEN_WORDS scan on the rewritten tab + risk second-opinion render; sector-gaps copy contains no
  imperative buy language (assert "NOT A BUY CALL" tag present, no "buy/consider buying").
- Privacy: risk second-opinion hidden when `is_local_runtime()` is False (extend the CI tripwire).
- Additivity/regression: `test_risk_tab.py` updated; renders with full macro, with thin macro (back-compat), and with
  `macro=None` (safe fallback). Sector/AI degrade to DATA-GAP, never crash.
- Determinism: bootstrap seeded for reproducible CIs in tests.

## 9. Non-goals (explicitly out of scope)
- No return prediction, VaR forecast, or trade recommendation of any kind.
- No live per-render Gemini calls (cache-first, weekly prefetch like the cited case).
- No portfolio optimizer / rebalancing engine — the tab *describes*, it does not *act*.
- No new factor universe beyond config (factor list stays `us.yaml`-driven; chart shows whatever factors are fit).

## 10. Integration / branch
Build in an isolated git **worktree** branch `feat/risk-tab-redesign`, branched off the committed
`feat/dashboard-legibility-redesign` HEAD (inherits v9 components + styles, avoids the parallel Home/Screener
sessions' uncommitted work). Standard gate: `make check` (ruff + mypy --strict + pytest ≥90%) green; FORBIDDEN_WORDS
and privacy tripwires pass; honesty footer present; before any main merge confirm no surface presents risk character
as a good/bad grade. `.superpowers/` added to `.gitignore`.

## 11. Open dependencies to resolve in planning
- **Sector source reliability** — yfinance `.info` is rate-limited/flaky; cache + offline fallback required; confirm
  field name via context7.
- **Bootstrap cost** — resampling the book fit must stay within the weekly-brief runtime budget; cap iterations
  (e.g. 500) and seed.
- **History bootstrap** — `sys_share_history` is empty until enough weekly runs accrue; UI must show "building
  history" until ≥3 points (don't fabricate a trend).
- **Factor count discrepancy (must not drift).** The mockup illustrates **9 factors**; `config/markets/us.yaml`
  currently fits **4** (SPY, TLT, UUP, XLE). The tab renders **whatever factors the config fits** — it must NOT
  hardcode 9. Expanding the factor universe (e.g. adding GROWTH/MOMENTUM/VALUE/CREDIT proxies) is an **optional,
  separate config decision** (its own grill/ADR if pursued); the redesign works at any factor count. Likewise the
  mockup's example numbers (1.18×, 71%, NVDA 14%, ENB 3.2) are illustrative placeholders, not committed values.
