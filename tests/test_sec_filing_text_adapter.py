"""Tests for the SEC filing-TEXT adapter — HTML extraction + item-section splitting.

No live EDGAR calls (project rule #5): ``requests.get`` is patched and the HTML is a
hand-built fixture that reproduces the features that break naive extraction — a table of
contents that repeats every item heading, <script>/<style> bodies, inline-XBRL wrapper
tags, and HTML entities.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import requests

from adapters.data.sec_filing_text_adapter import (
    FilingRef,
    SECFilingTextAdapter,
    _split_sections,
    _strip_html,
)
from domain.filing_textchange_service import textchange_similarity

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# A 10-K whose item headings each appear TWICE: once in the table of contents (with a
# page number immediately followed by the next heading — a tiny span) and once at the
# real body (followed by paragraphs — a large span). Naive first-match extraction would
# return the TOC line; the hardened splitter must return the body.
_TEN_K_HTML = """
<html>
<head><style>.toc { color: red; } body { font: serif; }</style></head>
<body>
  <script>var trackingPixel = "DO_NOT_LEAK script contents";</script>
  <div class="toc">
    <p>Item 1A. Risk Factors .......... 23</p>
    <p>Item 1B. Unresolved Staff Comments .......... 30</p>
    <p>Item 3. Legal Proceedings .......... 31</p>
    <p>Item 7. Management&#8217;s Discussion and Analysis .......... 40</p>
    <p>Item 8. Financial Statements .......... 55</p>
  </div>

  <h2>Item 1A. Risk Factors</h2>
  <p>BODYRISK our supply chain depends on a concentrated set of foundry partners and
     research &amp; development&#160;spending may not yield returns.</p>
  <h2>Item 1B. Unresolved Staff Comments</h2>
  <p>None.</p>
  <h2>Item 3. Legal Proceedings</h2>
  <p>BODYLEGAL we are defendants in patent litigation in the Northern District.</p>
  <h2>Item 7. Management&#8217;s Discussion and Analysis</h2>
  <p>BODYMGMT operating margins held while
     <ix:nonNumeric name="dei:Item">XBRLCONTINGENCY reserve</ix:nonNumeric> was released.</p>
  <h2>Item 8. Financial Statements</h2>
  <p>See accompanying notes.</p>
</body>
</html>
"""

# A 10-Q uses DIFFERENT item numbers for the same sections (Part II Item 1 = Legal,
# Item 1A = Risk Factors; Part I Item 2 = MD&A). The number-agnostic anchors must still
# find them.
_TEN_Q_HTML = """
<html><body>
  <h2>Item 2. Management's Discussion and Analysis</h2>
  <p>BODYMGMTQ sequential revenue rose on stronger data-center demand.</p>
  <h2>Item 1. Legal Proceedings</h2>
  <p>BODYLEGALQ no material new proceedings this quarter.</p>
  <h2>Item 1A. Risk Factors</h2>
  <p>BODYRISKQ macro conditions remain uncertain.</p>
  <h2>Item 6. Exhibits</h2>
  <p>Index of exhibits.</p>
</body></html>
"""


def _mock_response(text: str = "", json_data: dict | None = None) -> MagicMock:
    mock = MagicMock()
    mock.status_code = 200
    mock.text = text
    mock.json.return_value = json_data or {}
    mock.raise_for_status.return_value = None
    return mock


def _ref(doc: str = "primary.htm") -> FilingRef:
    return FilingRef(
        ticker="NVDA",
        cik=1045810,
        form="10-K",
        filed_date=date(2023, 2, 24),
        fiscal_period="2023-01-29",
        accession_nodash="000104581023000017",
        primary_doc=doc,
    )


# ---------------------------------------------------------------------------
# _strip_html — HTML-aware text reduction
# ---------------------------------------------------------------------------


def test_strip_html_drops_script_and_style_bodies() -> None:
    text = _strip_html(_TEN_K_HTML)
    assert "DO_NOT_LEAK" not in text
    assert "color: red" not in text
    assert "font: serif" not in text


def test_strip_html_decodes_entities() -> None:
    text = _strip_html("research &amp; development &#160; costs")
    assert "research & development" in text
    assert "&amp;" not in text and "&#160;" not in text


def test_strip_html_unwraps_inline_xbrl_to_visible_text() -> None:
    text = _strip_html(_TEN_K_HTML)
    # The inline-XBRL wrapper tag is gone but its DISPLAYED value survives.
    assert "XBRLCONTINGENCY reserve" in text
    assert "ix:nonNumeric" not in text and "nonNumeric" not in text


# ---------------------------------------------------------------------------
# _split_sections — table-of-contents defeat + body extraction
# ---------------------------------------------------------------------------


def test_split_sections_returns_body_not_table_of_contents() -> None:
    sections = _split_sections(_strip_html(_TEN_K_HTML))
    assert set(sections) == {"risk_factors", "litigation", "management"}
    # Each section must contain its BODY marker, proving we took the body copy and not
    # the short table-of-contents line.
    assert "BODYRISK" in sections["risk_factors"]
    assert "BODYLEGAL" in sections["litigation"]
    assert "BODYMGMT" in sections["management"]
    # The page-number dotted leader from the TOC must NOT be the captured text.
    assert ".......... 23" not in sections["risk_factors"]


def test_split_sections_stops_at_next_item_boundary() -> None:
    sections = _split_sections(_strip_html(_TEN_K_HTML))
    # Risk Factors body must not bleed into the following Legal Proceedings body.
    assert "BODYLEGAL" not in sections["risk_factors"]
    # Management body must not bleed into the trailing Financial Statements item.
    assert "accompanying notes" not in sections["management"]


def test_split_sections_handles_10q_item_numbering() -> None:
    sections = _split_sections(_strip_html(_TEN_Q_HTML))
    assert "BODYMGMTQ" in sections["management"]
    assert "BODYLEGALQ" in sections["litigation"]
    assert "BODYRISKQ" in sections["risk_factors"]


def test_split_sections_omits_absent_section() -> None:
    # A document with only a risk-factors item yields ONLY that key (no empty imputation).
    html = "<body><h2>Item 1A. Risk Factors</h2><p>BODY only risks here.</p></body>"
    sections = _split_sections(_strip_html(html))
    assert set(sections) == {"risk_factors"}


# ---------------------------------------------------------------------------
# fetch_sections — wiring through requests
# ---------------------------------------------------------------------------


def test_fetch_sections_returns_three_sections() -> None:
    adapter = SECFilingTextAdapter(rate_limit_seconds=0.0)
    with patch("requests.get", return_value=_mock_response(text=_TEN_K_HTML)):
        sections = adapter.fetch_sections(_ref())
    assert set(sections) == {"risk_factors", "litigation", "management"}


def test_fetch_sections_returns_empty_on_fetch_failure() -> None:
    adapter = SECFilingTextAdapter(rate_limit_seconds=0.0)
    with patch("requests.get", side_effect=requests.ConnectionError("boom")):
        assert adapter.fetch_sections(_ref()) == {}


# ---------------------------------------------------------------------------
# list_filings — point-in-time discipline
# ---------------------------------------------------------------------------

_SUBMISSIONS = {
    "filings": {
        "recent": {
            "form": ["10-K", "8-K", "10-Q", "10-K"],
            "filingDate": ["2022-02-25", "2022-05-01", "2022-08-20", "2023-02-24"],
            "accessionNumber": [
                "0001-22-000001",
                "0001-22-000002",
                "0001-22-000003",
                "0001-23-000017",
            ],
            "primaryDocument": ["a.htm", "b.htm", "c.htm", "d.htm"],
            "reportDate": ["2022-01-30", "", "2022-07-31", "2023-01-29"],
        }
    }
}


def test_list_filings_filters_non_periodic_forms() -> None:
    adapter = SECFilingTextAdapter(rate_limit_seconds=0.0)
    with patch("requests.get", return_value=_mock_response(json_data=_SUBMISSIONS)):
        refs = adapter.list_filings("NVDA", 1045810, as_of=date(2024, 1, 1))
    # The 8-K is dropped; only the two 10-Ks and the 10-Q remain.
    assert [r.form for r in refs] == ["10-K", "10-Q", "10-K"]


def test_list_filings_enforces_point_in_time_cutoff() -> None:
    adapter = SECFilingTextAdapter(rate_limit_seconds=0.0)
    with patch("requests.get", return_value=_mock_response(json_data=_SUBMISSIONS)):
        refs = adapter.list_filings("NVDA", 1045810, as_of=date(2022, 6, 1))
    # Only filings filed on/before 2022-06-01 are visible — the future 10-Q/10-K are hidden.
    assert all(r.filed_date <= date(2022, 6, 1) for r in refs)
    assert [r.filed_date.isoformat() for r in refs] == ["2022-02-25"]


def test_list_filings_sorted_oldest_to_newest() -> None:
    adapter = SECFilingTextAdapter(rate_limit_seconds=0.0)
    with patch("requests.get", return_value=_mock_response(json_data=_SUBMISSIONS)):
        refs = adapter.list_filings("NVDA", 1045810, as_of=date(2024, 1, 1))
    filed = [r.filed_date for r in refs]
    assert filed == sorted(filed)


def test_list_filings_empty_on_fetch_failure() -> None:
    adapter = SECFilingTextAdapter(rate_limit_seconds=0.0)
    with patch("requests.get", side_effect=requests.ConnectionError("boom")):
        assert adapter.list_filings("NVDA", 1045810, as_of=date(2024, 1, 1)) == []


def test_document_url_is_well_formed() -> None:
    url = _ref(doc="nvda-20230129.htm").document_url
    assert url == (
        "https://www.sec.gov/Archives/edgar/data/1045810/"
        "000104581023000017/nvda-20230129.htm"
    )


# ---------------------------------------------------------------------------
# End-to-end: extraction feeds the domain similarity signal correctly
# ---------------------------------------------------------------------------


def test_extracted_sections_flow_into_textchange_signal() -> None:
    """A near-identical refiling scores as a NON-CHANGER (high similarity)."""
    adapter = SECFilingTextAdapter(rate_limit_seconds=0.0)
    with patch("requests.get", return_value=_mock_response(text=_TEN_K_HTML)):
        prior = adapter.fetch_sections(_ref())
        current = adapter.fetch_sections(_ref())  # same doc => identical sections
    score = textchange_similarity(current, prior)
    assert score is not None
    assert score > 0.99  # identical text => non-changer
