# Home + Decision-Card Redesign — Design Spec (LOCKED 2026-06-14)

**Status:** Locked for planning. Source of truth for the implementation plans in
`docs/superpowers/plans/2026-06-14-*`. Every UI claim here is pinned to a canonical mockup; every data
claim is pinned to a real file from the codebase map. If code and this spec disagree, this spec wins for
*intent*, but verify the cited file still exists before building.

## 0. Goal & invariants

**Goal.** Turn the Home tab into a legible "Front Desk" triage page with a real onboarding front door, and
turn each holding into a collapsed→expanded **v9 decision card** (the redesigned Stock Analysis tab), so a
non-expert can tell at a glance what needs attention and drill into attributed evidence — never a prediction.

**North-star.** The user who didn't trade (0 trades) because he couldn't tell what to trust. One focal path;
attributed evidence; the app never issues buy/sell calls.

**Honesty invariants (non-negotiable, apply to every new surface):**
- No word from `FORBIDDEN_WORDS` (`domain/fit.py`: buy, sell, winner, conviction, predict, alpha, outperform)
  in module source — enforced by a source-scan test per new module (pattern: `tests/test_fit_card.py`).
- Third-party data is **attributed**, never adopted. The Google-AI case is labeled "informs you, not the verdict."
- Missing data renders **DATA-GAP**, never fabricated. `forward_pe_ratio` stays in `FUTURE_LEAKAGE_COLUMNS`
  (`domain/services.py`) and never enters a feature matrix; PEG/PE are display-only attributed values.
- The verdict is the deterministic trend-break rule (v1), shown with its measured reliability — never the AI case.

## 1. Canonical mockups (the visual contract — production must match these)

All under `.superpowers/brainstorm/97077-1781379305/content/`:
- **`home-FINAL.html`** — THE Home flow end-to-end: landing door → progressive load + progress bar → Front-Desk
  triage page → collapsed rows → v9 card → lazy AI-case. This is the acceptance reference for Home.
- **`per-stock-v9.html`** — THE decision card (5/5 cited case + 5-row RAG evidence table + learns box). Acceptance
  reference for the Stock Analysis tab / expanded card.
- `collapsed-expanded.html` — the row↔card disclosure + RAG-square hover + DATA-GAP square.
- `loading-states-AB.html` — loading model (Option 1 progressive + progress bar chosen).
- `home-redesign-AB.html` — Option A "Front Desk" chosen over Option B "Cockpit".
- `compare-v8-v9.html` — why v9 (full 5/5) over v8 (condensed).

## 2. Subsystem breakdown + build order (each plan ships independently)

Dependency-ordered. Each is a separate plan doc; earlier ones unblock later ones.

| # | Subsystem | Depends on | New vs reuse |
|---|---|---|---|
| **S1** | **Evidence signal layer** — 5 RAG dimensions + thresholds + per-holding assembler | — | mostly NEW domain + 1 new fetcher |
| **S2** | **Google-AI cited case** — `GeminiNarratorAdapter` + `NarratorPort` summarizer | S1 (feeds it facts) | NEW adapter |
| **S3** | **v9 decision card + Stock Analysis tab redesign** | S1, S2 | REDESIGN existing tab |
| **S4** | **Home "Front Desk" rewrite** (+ net-beta unify, vs-Market, section dispositions) | S1 (rows reuse card summary) | REWRITE existing tab |
| **S5** | **Loading / fetch infra** (fragments, progress, lazy-case, shimmer-vs-gap, cache) | S3, S4 | NEW (st.fragment first use) |
| **S6** | **Onboarding** — CSV upload, add-manually, sample book | S4, S5 | NEW |

Recommended ship sequence: **S1 → S3 → S4 → S2 → S5 → S6** (get the card + pages rendering on real data first;
layer the LLM case, then loading polish, then onboarding). S2 can slot earlier if desired (it's stubbable).

---

## 3. S1 — Evidence signal layer (the 5 RAG dimensions)

**Responsibility.** For a ticker, produce 5 R/A/G-coded evidence dimensions + their detail strings, honestly
(DATA-GAP where data missing). This is the data behind both the collapsed squares and the expanded table.

**New pure-domain module `domain/evidence_rag.py`:**
```python
class RagColor(Enum):
    RED = "R"; AMBER = "A"; GREEN = "G"; GAP = "GAP"

@dataclass(frozen=True)
class RagSignal:
    dimension: str       # one of the 5 fixed names, fixed order
    color: RagColor
    detail: str          # plain-English line shown in the expanded table
    # color==GAP → detail explains the gap, never a fabricated value

DIMENSIONS = ("Technicals", "Valuation", "Financials", "Earnings", "Analysts")  # FIXED ORDER (square 1..5)

def classify_technicals(atr_vs_200d: float | None, vs_spy_pct: float | None) -> RagSignal
def classify_valuation(peg: float | None, pe: float | None, sector_pctile: float | None) -> RagSignal
def classify_financials(fcf_positive: bool | None, debt_to_equity: float | None, margins_stable: bool | None) -> RagSignal
def classify_earnings(beats: int | None, total: int | None) -> RagSignal   # GAP if total is None
def classify_analysts(panel: AnalystPanel) -> RagSignal                    # GAP if panel.data_gap
```
Thresholds live here, unit-tested (Hypothesis for monotonic/boundary invariants per project standard). All stdlib.

**New application assembler `application/evidence_card.py`:**
```python
@dataclass(frozen=True)
class EvidenceCard:
    ticker: str
    signals: tuple[RagSignal, ...]    # always length 5, fixed DIMENSIONS order
    sparkline: tuple[float, ...]      # realized close prices, ~90d, NO projection
    # plus the scalar fields the card header needs (price, cost, unrealized, 7/30/90/180d)

def build_evidence_card(ticker: str, *, info: dict, prices: dict, panel: AnalystPanel,
                        earnings: EarningsHistory | None, peers: list[float | None]) -> EvidenceCard
```
Reuses: `domain/peer_relative.sector_percentile`, `application/analyst_panel.build_analyst_panel`,
`adapters/data/yfinance_adapter.get_ticker_info` field map (peg_ratio, free_cashflow, debt_to_equity,
gross/operating_margins, trailing_pe).

**NET-NEW fetcher `adapters/data/earnings_history_adapter.py`:**
```python
@dataclass(frozen=True)
class EarningsHistory:
    quarters: tuple[EpsQuarter, ...]   # last 4, each: label, eps_actual, eps_estimate, surprise_pct
    beats: int                          # count surprise_pct > 0
    total: int

def fetch_earnings_history(ticker: str) -> EarningsHistory | None   # None → Earnings square = DATA-GAP
```
Wraps `yfinance.Ticker(ticker).earnings_dates` / `.earnings_history`. **No adapter does this today.** Impl
function `_fetch_earnings_history_impl` (no Streamlit) + an `@st.cache_data` wrapper in `price_cache.py` style.
Revenue surprise stays DATA-GAP ("needs an estimates feed") per the mockup — do not fabricate.

**Color language (LOCKED):** RAG = good/bad is correct HERE (a beat is good). This is intentionally different
from the Risk tab's distance-ramp ("character not quality") for beta. Add a one-line legend on Home. See memory
`project-decision-card-v9-spec` + observation #5125.

**Tests:** boundary/monotonic property tests for each `classify_*`; assembler test with a faked yfinance info
dict + faked earnings → asserts 5 signals fixed order, DATA-GAP path renders GAP not a value; forbidden-word
source scan.

---

## 4. S2 — Google-AI cited case (`GeminiNarratorAdapter`)

**Responsibility.** Summarize ONLY the already-fetched cited articles (E3 `NewsContext`) + the S1 facts into
**5 in-favor / 5 to-watch**, each `[source]`-tagged. Never invents; both sides forced; "informs you, not the verdict."

**New port (in `domain/ports.py`, follow the `@runtime_checkable Protocol` pattern):**
```python
@runtime_checkable
class CaseSummarizerPort(Protocol):
    def summarize_case(self, ctx: CaseContext) -> CaseResult: ...
```
**New domain types `domain/case_models.py`:**
```python
@dataclass(frozen=True)
class CaseContext:
    ticker: str
    facts: tuple[RagSignal, ...]      # the 5 dimensions (grounding)
    news: tuple[NewsItem, ...]        # E3 cited items (the ONLY free-text source)
@dataclass(frozen=True)
class CaseResult:
    in_favor: tuple[CasePoint, ...]   # up to 5, each {text, source_tag}
    to_watch: tuple[CasePoint, ...]   # up to 5
    data_gap: bool                    # True → render "case unavailable", never blank-faked
```
**New adapter `adapters/ml/gemini_narrator.py` (`GeminiNarratorAdapter`):** follows `GeminiEventClassifier`
(google.generativeai, model `gemini-2.0-flash`, `GEMINI_API_KEY`, rate-limit) + `OllamaNarratorAdapter` fallback
shape. On any error / no key → returns `CaseResult(data_gap=True)`. Prompt constrains output to cited facts only,
forces both columns, forbids buy/sell verbs.

**Honesty test:** the adapter's *rendered* output must pass the forbidden-word scan; a fake summarizer is used in
card tests so no network in CI.

---

## 5. S3 — v9 decision card + Stock Analysis tab redesign

**Visual contract:** `per-stock-v9.html`. Top→bottom:
1. Verdict row: big verdict (TRIM/REDUCE/…) + "trend-break rule (v1) — review prompt, not a forecast" + "evidence: mixed".
2. "What this means" plain-English band.
3. Price row: Price · Your cost · Unrealized% · 7/30/90/180d.
4. **The case — Google AI, from cited sources** (S2) · badge "informs you, not the verdict" · ▲5/▼5 · footer
   "Summarised from real fetched articles (each cited). Doesn't pick for you."
5. **5-row RAG evidence table** (S1) — "the 5 squares, in full"; DATA-GAP rows say so.
6. "How this verdict learns" box + reliability ("0 of N scored · hit-rate ~mid-July").
7. Footer: "Research only · attributed evidence + your rule's measured history · not a buy/sell signal."

**Build:** REDESIGN `adapters/visualization/tabs/stock_analysis.py`. Add a new render path
`_render_decision_card(card: EvidenceCard, case: CaseResult | None, verdict: ...)` producing the v9 layout;
keep the existing `analyze_ticker` deep-dive available below or behind a toggle (don't delete working code —
the sections/snowflake become "full analysis", the v9 card becomes the lead). Reuse `_render_analyst_panel`,
`_render_news_context`. Pre-fill entry from Portfolio (`st.session_state["analyze_ticker"]`) preserved.

**Component reuse:** extract the collapsed row + v9 card into `adapters/visualization/components/decision_card.py`
so Home/Portfolio/Stock-Analysis render the SAME component (DRY). Functions: `render_collapsed_row(card, verdict)`,
`render_expanded_card(card, case, verdict)`.

**Tests:** tab test (Streamlit-stub pattern from `tests/test_positions_tab.py`) asserting v9 sections present,
DATA-GAP rendered, forbidden-word scan, lazy-case stub path.

---

## 6. S4 — Home "Front Desk" rewrite

**Visual contract:** `home-FINAL.html` (Option A). REWRITE `adapters/visualization/tabs/weekly_brief.py render()`.

**Layout top→bottom:** hero → landing door (S6) → "viewing: …" tag → [progress bar (S5)] → book strip (4 vitals)
→ book-health bar → "why doubt us → Trust" honesty line → Needs-review rows (collapsed v9 cards, S3) → Holding-steady
collapsed → footer (as-of · regime · adherence · "Download full brief (.md)").

**4 vitals:** Need review (count of REDUCE/TRIM/REVIEW) · vs-Market 1y (NEW, §below) · **Net beta** · Screen (cleared/universe).
Each hover-(i) via existing `tooltip()`.

**BUG FIX — net-beta unify (REQUIRED):** today `weekly_brief.py:~246` shows `macro.net_beta_by_factor["SPY"]`
labeled "Net beta" AND `:~318` shows `macro.systematic_share` % ALSO labeled "Net beta". Lock: **"Net beta" = the
SPY-beta number only**; the systematic-share % is **"Book health"** (the ring), a different name. One number per label.

**NEW — vs-Market (1y):** add `application/vs_market.py` `compute_vs_market_1y(book_returns, spy_returns) -> float`
(realized book trailing-12m return minus SPY's, from price series — backward-looking, no leakage). Surfaced in the
vs-Market tile; DATA-GAP if price history insufficient.

**Section dispositions (NOTHING deleted — forwarded; see table):**
| Current section (`weekly_brief.py`) | Disposition |
|---|---|
| Hero | keep (smaller) |
| TRIAGE strip | → the 4 vitals (relabeled, net-beta fixed) |
| Evidence ledger (`render_ledger`) | **DELETE** (dup + 2nd-net-beta bug); as-of/adherence → footer |
| VALIDATION FINDINGS (3 anti-KPI tiles) | **MOVE → Trust**; Home keeps the 1-line "why doubt us" band |
| BOOK HEALTH gauge | → compact book-health bar (ring); full gauge stays on Risk |
| DISCIPLINE FLAGS (top-5 cards) | → **Needs-review rows** (the v9 collapsed component) |
| RESEARCH SCREEN notice | → Screen vital tile + "Screener →" link |
| CONCENTRATION FLAGS | keep small (or Risk) |
| VERDICT DISTRIBUTION + all-attention table | **MOVE → My Portfolio** (full per-grade book) |
| Full markdown brief dump | → **"Download full brief (.md)"** button |

**Tests:** weekly_brief tab test (existing pattern) asserting: one "Net beta" value only, no `render_ledger`,
needs-review rows render, "Download full brief" present, no `=EMH`/`Rank-IC` full tiles (moved), forbidden-word scan.
Trust tab test gains the validation tiles.

---

## 7. S5 — Loading / fetch infra

**Visual contract:** `loading-states-AB.html` Option 1 + progress bar; `home-FINAL.html` integrated flow.

**Behavior (LOCKED):**
- Rows render instantly with ticker + verdict (trend-rule is cheap). Squares + sparkline **shimmer → fill** per
  holding as data lands (`st.fragment` per row so one slow holding doesn't freeze the page).
- **Global determinate progress bar** "Fetching N/total → ✓ ready" (extend the `st.progress` use already in
  `research_candidates.py:91`).
- **Lazy AI-case on card-expand ONLY** — never call S2 for the whole book; fetch on expand, with an in-card
  shimmer. (No LLM cost for unopened cards.)
- **Loading ≠ DATA-GAP visual:** animated petrol **shimmer** = loading; static **hatched grey square** = DATA-GAP.
- **Cache** per-ticker via the `price_cache.py` `@st.cache_data` pattern (+ new earnings/case caches with TTL).

**Streamlit verification (REQUIRED before building S5):** confirm current `st.fragment`, `st.status`, `st.progress`
APIs via **context7** (`resolve-library-id streamlit` → `query-docs`). `st.fragment` is NOT used anywhere today —
first use; verify version supports it (`streamlit>=1.33`). Fallback if unavailable: `st.status` stage-log (Option 2).

**Tests:** fragment functions are plain Python under the hood — test the data-readiness state machine (pending →
loaded → gap) without Streamlit; assert lazy-case is NOT invoked unless a card is expanded.

---

## 8. S6 — Onboarding (CSV upload · add-manually · sample book)

**Visual contract:** `home-FINAL.html` landing door + privacy copy.

- **Landing door** shown when no book loaded: "Explore sample book (10 stocks)" · "Upload holdings CSV" · "Add
  manually". Copy: "Your holdings stay on your machine — never uploaded, never shown to anyone."
- **Sample book:** ship a fixed `data/sample/sample_book.csv` (10 names) + a sample `brief_summary`-shaped fixture so
  the instrument demos with zero user data. "VIEWING: SAMPLE BOOK" tag.
- **CSV upload:** `st.file_uploader`; parse via `application/holdings_reader.read_holdings` shape (columns: symbol,
  quantity, book value, exchange, account type). Validation + error states (bad columns / 0 rows / wrong format).
- **Add manually:** reuse/extend `positions.py:_render_trade_form()` pattern (ticker, qty, price, date) → builds an
  in-session book; then runs S1/S5 to populate cards.

**PRIVACY HONESTY GATE (RESOLVED 2026-06-14 — local-only + babyproofing).** Decision: ship local-only now; make
it IMPOSSIBLE to accidentally expose the privacy promise on a hosted deploy. New pure-ish guard
`application/runtime_guard.py`:
```python
def is_local_runtime() -> bool:
    """Fail-safe: returns False unless ALL hold (default NOT local)."""
    # 1. explicit opt-in flag
    if os.environ.get("STOCKREC_LOCAL_ONLY") != "1": return False
    # 2. server bound to loopback (read streamlit server.address; reject 0.0.0.0 / public)
    if _server_address() not in {"localhost", "127.0.0.1", "::1"}: return False
    # 3. connecting client is loopback where exposed (st.context / ws headers); unknown → treat as remote
    if not _client_is_loopback(): return False
    return True
```
S6 behavior: the **CSV-upload widget + "stays on your machine" privacy copy render ONLY when `is_local_runtime()`
is True.** Otherwise render a notice: *"Holdings upload is disabled — this build isn't running local-only."* Sample
book + add-manually (no file leaves the machine) may still render. **CI tripwire test (REQUIRED):**
`test_runtime_guard_defaults_not_local` — with no env set, `is_local_runtime()` is False, so the privacy copy is
absent. This prevents a hosted deploy from ever printing a false promise even by accident. Verify exact Streamlit
API for server address / client host via context7 at build (`st.context`, `st.get_option("server.address")`).

**Tests:** CSV parse happy-path + 3 error states; sample-book loads + renders rows; privacy-copy wording test.

---

## 9. Acceptance criteria (production == mock)

A surface is done when, side-by-side with its canonical mockup:
1. **Home** matches `home-FINAL.html`: landing door → load (progress bar + progressive fill) → 4 vitals (ONE net-beta)
   + book-health ring + honesty line → needs-review collapsed rows → holding-steady → footer w/ brief download.
2. **Decision card** matches `per-stock-v9.html`: verdict + means + price + 5/5 cited case (badge) + 5-row RAG table
   + learns box + research-only footer.
3. **Squares** = fixed order Technicals/Valuation/Financials/Earnings/Analysts, hover tooltip each, DATA-GAP = hatched.
4. **Loading** = progressive fill + global progress bar; AI-case loads only on expand; shimmer ≠ hatched.
5. **Honesty:** forbidden-word source scan passes on every new module; no fabricated values; attributed case labeled.
6. `make check` green (mypy --strict, pre-commit, ≥90% cov). `git checkout data/reports/` before verify (2 JSONs
   strip trailing newlines).

## 10. Open decisions / risks (resolve during planning)

- **R1 Privacy copy** (S6) — RESOLVED: local-only + `is_local_runtime()` fail-safe guard + CI tripwire (see S6).
- **R2 LLM cost/latency** (S2) — Gemini free tier rate limit (14 rpm) vs book size; lazy-on-expand mitigates.
- **R3 vs-Market(1y)** (S4) — needs ≥1y price history per holding; partial book → DATA-GAP tile, don't fake.
- **R4 Two Holding models** — RESOLVED: CSV reader (`application/holdings_reader.Holding`) for the upload/in-session
  path into the card pipeline; SQLite (`domain/models.Holding`) for the persisted book. (Tirth confirmed rec.)
- **R5 st.fragment availability** (S5) — verify streamlit version via context7; fallback to st.status.
