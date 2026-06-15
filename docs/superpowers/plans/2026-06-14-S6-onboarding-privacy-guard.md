# S6 — Onboarding (CSV / Manual / Sample) + Privacy Guard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the Home landing door (Explore sample book / Upload holdings CSV / Add manually) matching `home-FINAL.html`, so a new user can demo the instrument or load a book — with a fail-safe runtime guard that makes it IMPOSSIBLE to expose the "stays on your machine" privacy promise on a hosted deploy.

**Architecture:** A pure-ish `application/runtime_guard.py` (`is_local_runtime()`, fail-safe → False by default). A sample book fixture (`data/sample/sample_book.csv`) + loader. The landing door renders at the top of Home when no book is in `st.session_state`; the CSV-upload widget + privacy copy render ONLY when `is_local_runtime()` is True. CSV parsing reuses `application/holdings_reader.read_holdings`. Add-manually reuses the `positions.py:_render_trade_form` idiom into an in-session book.

**Tech Stack:** Python 3.12, Streamlit (`st.file_uploader`, `st.session_state`, `st.button`), pytest. Depends on **S4** (Home render) + **S5** (the loaded book flows into needs-review rows). Reuses `application/holdings_reader` (R4: CSV path).

**Spec:** §8 + the RESOLVED privacy gate. **Anchors:** component-map §2 (`components/onboarding.py` exists — reuse), §4-Portfolio (`_render_trade_form`), `application/holdings_reader.read_holdings` (CSV columns: `symbol`, `quantity`, `book value (cad)`, `exchange`, `account type`).

---

## File Structure

- Create `application/runtime_guard.py` — `is_local_runtime()` + `_server_address()` + `_client_is_loopback()`.
- Create `data/sample/sample_book.csv` — 10 fixed holdings (demo).
- Create `application/sample_book.py` — `load_sample_book() -> list[Holding]`.
- Modify `adapters/visualization/components/onboarding.py` — `render_landing_door(local: bool) -> None` (door HTML + buttons).
- Modify `adapters/visualization/tabs/weekly_brief.py` — show door when no book in session; route sample/CSV/manual into the book + S5 rows.
- Create `tests/application/test_runtime_guard.py`, `tests/application/test_sample_book.py`, `tests/components/test_onboarding.py`.

---

### Task 1: Runtime guard (fail-safe) + CI tripwire

**Files:** Create `application/runtime_guard.py`; Test `tests/application/test_runtime_guard.py`.

`is_local_runtime()` returns True ONLY if all hold: env `STOCKREC_LOCAL_ONLY=1`, server bound to loopback, client is loopback. Default (nothing set) → False. **This is the babyproofing.**

- [ ] **Step 1: Failing test (the tripwire is the most important test)**

```python
# tests/application/test_runtime_guard.py
from application.runtime_guard import is_local_runtime


def test_defaults_not_local(monkeypatch):
    """CI TRIPWIRE: with nothing set, runtime is NOT local → privacy copy must stay hidden."""
    monkeypatch.delenv("STOCKREC_LOCAL_ONLY", raising=False)
    assert is_local_runtime() is False


def test_flag_alone_not_enough(monkeypatch):
    monkeypatch.setenv("STOCKREC_LOCAL_ONLY", "1")
    monkeypatch.setattr("application.runtime_guard._server_address", lambda: "0.0.0.0")
    assert is_local_runtime() is False  # bound to 0.0.0.0 → treat as remote


def test_all_conditions_true_is_local(monkeypatch):
    monkeypatch.setenv("STOCKREC_LOCAL_ONLY", "1")
    monkeypatch.setattr("application.runtime_guard._server_address", lambda: "localhost")
    monkeypatch.setattr("application.runtime_guard._client_is_loopback", lambda: True)
    assert is_local_runtime() is True
```

- [ ] **Step 2: Run fail** → `pytest tests/application/test_runtime_guard.py -v` FAIL

- [ ] **Step 3: Implement**

```python
# application/runtime_guard.py
"""Fail-safe local-only guard. Default = NOT local, so a hosted deploy can never expose
the 'stays on your machine' privacy promise by accident."""
from __future__ import annotations

import os

_LOOPBACK = {"localhost", "127.0.0.1", "::1"}


def _server_address() -> str:
    try:
        import streamlit as st  # verify API via context7 (st.get_option)

        return str(st.get_option("server.address") or "")
    except Exception:  # noqa: BLE001
        return ""


def _client_is_loopback() -> bool:
    try:
        import streamlit as st

        host = getattr(getattr(st, "context", None), "headers", {}) or {}
        # best-effort: if Streamlit doesn't expose the client host, treat as NOT loopback (fail-safe)
        forwarded = host.get("Host", "") if hasattr(host, "get") else ""
        return any(lb in forwarded for lb in _LOOPBACK)
    except Exception:  # noqa: BLE001
        return False


def is_local_runtime() -> bool:
    if os.environ.get("STOCKREC_LOCAL_ONLY") != "1":
        return False
    if _server_address() not in _LOOPBACK:
        return False
    if not _client_is_loopback():
        return False
    return True
```

> **context7 verify:** `st.get_option("server.address")` and `st.context.headers` exact APIs. If `_client_is_loopback` can't read the host on the installed Streamlit, it returns False (fail-safe) — acceptable: worst case is the upload is hidden on a true-local run with an unusual setup, never the reverse.

- [ ] **Step 4: Run pass** → PASS (3, incl. the tripwire)

- [ ] **Step 5: Commit**

```bash
git checkout data/reports/ 2>/dev/null || true
git add application/runtime_guard.py tests/application/test_runtime_guard.py
git commit -m "feat(onboarding): fail-safe is_local_runtime() guard + CI tripwire"
```

---

### Task 2: Sample book fixture + loader

**Files:** Create `data/sample/sample_book.csv`, `application/sample_book.py`; Test `tests/application/test_sample_book.py`.

- [ ] **Step 1: Create the sample CSV** (columns match `holdings_reader.read_holdings`):

```bash
mkdir -p data/sample
cat > data/sample/sample_book.csv <<'CSV'
symbol,quantity,book value (cad),exchange,account type
YUMC,100,3638,NYSE,TFSA
AAPL,15,2850,NASDAQ,TFSA
BABA,40,3600,NYSE,Margin
MSFT,10,4300,NASDAQ,TFSA
KO,50,3100,NYSE,RRSP
TD.TO,30,2400,TSX,TFSA
ENB.TO,60,2900,TSX,RRSP
NVDA,8,9500,NASDAQ,Margin
COST,5,4200,NASDAQ,TFSA
PEP,20,3400,NASDAQ,RRSP
CSV
```

- [ ] **Step 2: Failing test**

```python
# tests/application/test_sample_book.py
from application.sample_book import load_sample_book


def test_sample_book_has_ten_holdings():
    book = load_sample_book()
    assert len(book) == 10
    tickers = {h.ticker for h in book}
    assert "YUMC" in tickers and "AAPL" in tickers
```

- [ ] **Step 3: Run fail** → FAIL

- [ ] **Step 4: Implement**

```python
# application/sample_book.py
"""Load the bundled demo book (no user data needed)."""
from __future__ import annotations

from application.holdings_reader import Holding, read_holdings

_SAMPLE_PATH = "data/sample/sample_book.csv"


def load_sample_book(path: str = _SAMPLE_PATH) -> list[Holding]:
    return read_holdings(path)
```

- [ ] **Step 5: Run pass + commit**

```bash
pytest tests/application/test_sample_book.py -v   # PASS
git add data/sample/sample_book.csv application/sample_book.py tests/application/test_sample_book.py
git commit -m "feat(onboarding): bundled 10-name sample book + loader"
```

---

### Task 3: Landing door component (privacy-gated)

**Files:** Modify `adapters/visualization/components/onboarding.py`; Test `tests/components/test_onboarding.py`.

`render_landing_door_html(local: bool) -> str` — the petrol door + 3 buttons. The CSV button + "stays on your machine" copy appear ONLY when `local` is True; otherwise the door shows sample + manual + a "upload disabled — not running local-only" notice.

- [ ] **Step 1: Failing test**

```python
# tests/components/test_onboarding.py
from adapters.visualization.components.onboarding import render_landing_door_html


def test_door_local_shows_privacy_and_upload():
    html = render_landing_door_html(local=True)
    assert "stays on your machine" in html.lower()
    assert "Upload holdings CSV" in html
    assert "Explore sample book" in html


def test_door_hosted_hides_privacy_and_upload():
    html = render_landing_door_html(local=False)
    assert "stays on your machine" not in html.lower()      # no false promise
    assert "Upload holdings CSV" not in html                # upload hidden
    assert "isn't running local-only" in html               # honest notice
    assert "Explore sample book" in html                    # sample still ok
```

- [ ] **Step 2: Run fail** → FAIL

- [ ] **Step 3: Implement** — add to `onboarding.py`:

```python
def render_landing_door_html(local: bool) -> str:
    privacy = ('<p style="margin:0 0 16px;font-size:12.5px;color:rgba(255,255,255,.82)">'
               'See the instrument on a sample book, or load your own. '
               '<b style="color:#fff">Your holdings stay on your machine</b> — never uploaded.</p>'
               if local else
               '<p style="margin:0 0 16px;font-size:12.5px;color:rgba(255,255,255,.82)">'
               'See the instrument on a sample book. Holdings upload is disabled — '
               'this build isn\'t running local-only.</p>')
    csv_btn = ('<button class="db ghost">↓ Upload holdings CSV</button>' if local else '')
    return (
        '<div class="door"><h2 style="font-family:Fraunces,serif;font-weight:700;font-size:19px;margin:0 0 3px">'
        'Load a book to begin</h2>'
        f'{privacy}'
        '<div style="display:flex;gap:10px;flex-wrap:wrap">'
        '<button class="db primary">▸ Explore sample book (10 stocks)</button>'
        f'{csv_btn}'
        '<button class="db ghost">+ Add manually</button></div></div>'
    )
```

> The `.door`/`.db` CSS goes into `GLOBAL_CSS` (styles.py) alongside the S3 card CSS — add a small block mirroring `home-FINAL.html`'s `.door`/`.db` rules. (Add as Task 3 Step 3b if not already present.)

- [ ] **Step 4: Run pass** → PASS (both — note the hosted test asserts NO false promise)

- [ ] **Step 5: Commit**

```bash
git add adapters/visualization/components/onboarding.py adapters/visualization/components/styles.py tests/components/test_onboarding.py
git commit -m "feat(onboarding): privacy-gated landing door (upload+copy hidden when not local)"
```

---

### Task 4: Wire door + book routing into Home

**Files:** Modify `adapters/visualization/tabs/weekly_brief.py`; Test `tests/test_weekly_brief_tab.py`.

At the top of `render()`: if no book in `st.session_state["book"]`, render the door (via `is_local_runtime()`), wire the 3 Streamlit buttons (`st.button`) to set the session book (sample → `load_sample_book()`; CSV → `st.file_uploader` gated on local → `read_holdings`; manual → trade-form), then `st.rerun()`. Once a book exists, proceed to the Front-Desk render (S4) over that book.

- [ ] **Step 1: Failing test (door shows when no book; gated upload)**

```python
def test_home_shows_door_when_no_book(monkeypatch):
    from adapters.visualization.tabs import weekly_brief as wb
    monkeypatch.setattr(wb, "is_local_runtime", lambda: True)
    html = wb._render_onboarding_html(has_book=False)
    assert "Load a book to begin" in html and "Explore sample book" in html


def test_home_hides_door_when_book_present():
    from adapters.visualization.tabs import weekly_brief as wb
    assert wb._render_onboarding_html(has_book=True) == ""
```

- [ ] **Step 2: Run fail** → FAIL

- [ ] **Step 3: Implement** — add to `weekly_brief.py`:

```python
from application.runtime_guard import is_local_runtime
from adapters.visualization.components.onboarding import render_landing_door_html


def _render_onboarding_html(has_book: bool) -> str:
    if has_book:
        return ""
    return render_landing_door_html(local=is_local_runtime())
```

Then in `render()`: compute `has_book = "book" in st.session_state`, `st.markdown(_render_onboarding_html(has_book), unsafe_allow_html=True)`. Add the button handlers (sample/CSV/manual) below the door; CSV uploader wrapped in `if is_local_runtime():`. On any selection set `st.session_state["book"] = <holdings>` and `st.rerun()`. When `has_book`, run the existing S4 Front-Desk render over the session book's brief.

- [ ] **Step 4: Run pass** → PASS

- [ ] **Step 5: Commit**

```bash
git add adapters/visualization/tabs/weekly_brief.py tests/test_weekly_brief_tab.py
git commit -m "feat(onboarding): landing door + sample/CSV/manual routing on Home"
```

---

### Task 5: Honesty + privacy + full S6 verify

- [ ] **Step 1: Privacy-promise guard test (belt-and-suspenders)**

```python
def test_privacy_copy_never_shown_when_not_local():
    from adapters.visualization.components.onboarding import render_landing_door_html
    assert "stays on your machine" not in render_landing_door_html(local=False).lower()
```

- [ ] **Step 2: Forbidden-word scans**

```python
def test_onboarding_no_forbidden_words():
    import inspect
    from adapters.visualization.components import onboarding
    from application import runtime_guard, sample_book
    from domain.fit import FORBIDDEN_WORDS
    for mod in (onboarding, runtime_guard, sample_book):
        src = inspect.getsource(mod).lower()
        for w in FORBIDDEN_WORDS:
            assert w not in src, f"forbidden word {w!r} in {mod.__name__}"
```

- [ ] **Step 3: Full S6 verify**

```bash
mypy application/runtime_guard.py application/sample_book.py adapters/visualization/components/onboarding.py
pytest tests/application/test_runtime_guard.py tests/application/test_sample_book.py tests/components/test_onboarding.py tests/test_weekly_brief_tab.py -v
```
Expected: mypy Success; tests PASS (esp. the tripwire + privacy tests).

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "test(onboarding): privacy tripwire + forbidden-word scans for S6"
```

---

## Self-Review (S6)

1. **Spec §8 coverage:** landing door (Task 3) ✓; sample book (Task 2) ✓; CSV upload via `read_holdings`, gated (Tasks 3–4) ✓; add-manually (Task 4) ✓; **privacy gate** = `is_local_runtime()` fail-safe + CI tripwire + door hides copy/upload when not local (Tasks 1, 3, 5) ✓.
2. **Placeholders:** none. (CSV error-state handling: `read_holdings` raises on bad columns; wrap the uploader call in try/except → `st.error` — add as a concrete sub-step in Task 4 implementation.)
3. **Type consistency:** `Holding` = `application/holdings_reader.Holding` (R4 CSV path); `is_local_runtime()->bool` used in door + Home; door HTML helper signatures match across onboarding + weekly_brief.
4. **Honesty/privacy:** the false promise CANNOT ship to a hosted env — default-not-local + door hides copy+upload when not local + a dedicated test asserts it. Forbidden-word scans on all new modules.

**Plan set complete: S1 → S6.** Cross-plan contracts: S1 `EvidenceCard` → S3 card + S4 rows + S5 fetch; S2 `CaseResult` → S3 card + S5 lazy; S5 wires real fetch into S4 rows; S6 feeds the book into S4/S5.
