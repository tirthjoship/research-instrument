# HANDOFF — Risk tab fix sprint (Claude Code)

**For:** a fresh Claude Code session implementing Risk-tab UI fixes from Tirth's review.
**From:** Cursor planning session 2026-06-16.
**Status:** ✅ Brief complete — **start here.**

---

## Your job

Implement items **R01–R08** in `docs/fix-targets/RISK_TAB_FIX_BRIEF.md`. Each item has current/desired screenshots, root-cause notes, and acceptance criteria. **R09 is already done** — skip unless regression.

```bash
cd "/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/multi-modal-stock-recommender"
```

**Primary doc (read fully):** `docs/fix-targets/RISK_TAB_FIX_BRIEF.md`
**Mockup of record:** `docs/superpowers/mockups/risk-v8.html`
**Honesty rails:** `docs/superpowers/specs/2026-06-15-risk-tab-redesign-design.md` (ADR-052)

---

## Already shipped (do not redo)

| ID | What | Where |
|----|------|--------|
| **R09** | Removed per-tab `↻ refresh` on all tabs | `adapters/visualization/dashboard.py` — verify no `_refresh_button` |

---

## Recommended execution order

Work **P0 first**, then P1. Batch shared CSS once.

| Order | ID | Why this order |
|-------|-----|----------------|
| 1 | **R01** | Top of tab — typography/copy; quick wins |
| 2 | **R02** | Lens nav anchors — may need JS for Streamlit scroll |
| 3 | **R07** | Google AI panel — **fix placement** (`_drift` → AI → `_teach`); cache prefetch |
| 4 | **R03** | Factor chart — config expansion (4→9 factors) + UI labels + READ line |
| 5 | **CSS batch** | Port `.teach`, `.tbody`, `.chap`, `.donut`, `.levers`, `.act` from mockup → `styles.py` |
| 6 | **R04** | ENB drill-down bin (uses `.teach`) |
| 7 | **R08** | Plain-English walkthrough bin + donut (uses `.teach`) |
| 8 | **R05** | Who owns — section header + tooltip |
| 9 | **R06** | Who owns — holdings row `%` column |

**Shared root cause (R04 + R08):** `class="teach"` HTML exists but CSS only lives in `risk-v8.html`, not `styles.py`. Port once.

**Shared root cause (R07):** `render()` appends AI panel *after* full `_compose()` (which includes `_teach`). Must inject between `_drift` and `_teach`.

**Shared root cause (R03):** `config/markets/us.yaml` → `macro_beta.factors: [SPY, TLT, UUP, XLE]` — only 4 factors. Expanding to 9 is a **config + weekly-brief** sub-task, not UI-only.

---

## Key files

| Area | Path |
|------|------|
| Risk tab render | `adapters/visualization/tabs/risk.py` |
| Global styles | `adapters/visualization/components/styles.py` |
| Tooltips / glossary | `adapters/visualization/components/tooltip.py`, `glossary.py` |
| Google AI panel | `adapters/visualization/components/risk_second_opinion.py` |
| AI cache/build | `application/risk_second_opinion.py` |
| Macro data | `data/personal/brief_summary.json` |
| Factor config | `config/markets/us.yaml` |
| Dashboard (R09 done) | `adapters/visualization/dashboard.py` |

---

## Verify before declaring done

```bash
make check   # ruff + mypy --strict + pytest ≥90%
```

**Live eyeball:**

```bash
STOCKREC_LOCAL_ONLY=1 streamlit run adapters/visualization/dashboard.py
```

Open **Risk** tab; compare section-by-section against screenshots in `docs/fix-targets/screenshots/risk-tab/`.

**Google AI panel (R07):** needs local runtime + cache. Run weekly-brief with `GEMINI_API_KEY` in `.env` to populate `cited_cases.json` → `risk_second_opinion` entry.

---

## Non-negotiable rails

- Dials = heuristic surfacing, not validated edge (ADR-052)
- No `FORBIDDEN_WORDS` in rendered strings (`buy/sell/winner/conviction/predict/alpha/outperform`)
- Sector gaps = descriptive only (`NOT A BUY CALL`)
- Google AI = attributed second opinion, `RESEARCH ONLY`, `is_local_runtime()` gated
- Do **not** hardcode mockup numbers (1.18×, 71%, ENB 3.2) — use live `macro` data
- Render factor count from **config**, not hardcoded 9 (but user wants 9-factor expansion per R03)

---

## Screenshot index

20 PNGs in `docs/fix-targets/screenshots/risk-tab/` — all embedded in `RISK_TAB_FIX_BRIEF.md`. Use as visual truth when text is ambiguous.

---

## Suggested Claude Code prompt

Paste this to start the session:

```
Read docs/fix-targets/HANDOFF-risk-tab-fixes.md and docs/fix-targets/RISK_TAB_FIX_BRIEF.md.

Implement R01–R08 in the recommended order. R09 (refresh button) is already done.

After each item: run affected tests, then make check before moving on.
Eyeball the Risk tab against the screenshots when all items are complete.
```
