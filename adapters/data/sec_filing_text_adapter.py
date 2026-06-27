"""SEC filing-TEXT adapter — fetches 10-K / 10-Q document text for the Lazy Prices test.

Distinct from ``sec_edgar_adapter.py`` (which uses EFTS search for 13D/Form-4 smart-money
signals). This one pulls the actual periodic-report DOCUMENT text via the SEC submissions
API, so the domain ``filing_textchange_service`` can diff consecutive comparable filings.

Point-in-time discipline: ``list_filings(..., as_of)`` returns only filings whose
``filed_date <= as_of``. Section extraction (``fetch_sections``) parses the real
10-K/10-Q HTML with an HTML-aware text extractor (drops <script>/<style>/inline-XBRL
markup, decodes entities) and an item-heading splitter that is robust to the document's
table of contents — so the rig is runnable end-to-end against live EDGAR.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import date
from typing import Any

import requests
from bs4 import BeautifulSoup
from loguru import logger

_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
_ARCHIVE_DOC = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession_nodash}/{doc}"
_PERIODIC_FORMS = ("10-K", "10-Q")

# Section anchors keyed on the canonical ITEM heading, deliberately item-NUMBER-agnostic
# (``item\s+\d+[a-z]?``) so the SAME patterns find a section in both a 10-K (Risk Factors =
# Item 1A, Legal = Item 3, MD&A = Item 7) and a 10-Q (Risk Factors = Part II Item 1A, Legal
# = Part II Item 1, MD&A = Part I Item 2). The required "Item N" prefix is what keeps these
# from matching incidental body prose (e.g. "...the following risk factors..."), and the
# table-of-contents copy of each heading is defeated by max-span selection in _split_sections.
_ITEM_HEADING = r"item\s+\d{1,2}[a-z]?[.):\s]"
_SECTION_ANCHORS: dict[str, re.Pattern[str]] = {
    "risk_factors": re.compile(_ITEM_HEADING + r"\s{0,4}risk\s+factors", re.I),
    "litigation": re.compile(_ITEM_HEADING + r"\s{0,4}legal\s+proceedings", re.I),
    "management": re.compile(
        _ITEM_HEADING + r".{0,6}management['’\s]{0,4}s?\s*discussion", re.I
    ),
}
# Any item heading marks a section BOUNDARY (where the previous section ends).
_ITEM_BOUNDARY = re.compile(_ITEM_HEADING, re.I)


@dataclass(frozen=True)
class FilingRef:
    """A point-in-time reference to one periodic filing."""

    ticker: str
    cik: int
    form: str  # "10-K" | "10-Q"
    filed_date: date
    fiscal_period: str  # e.g. "FY2023" or "Q3-2023" — used to pair comparables
    accession_nodash: str
    primary_doc: str

    @property
    def document_url(self) -> str:
        return _ARCHIVE_DOC.format(
            cik=self.cik, accession_nodash=self.accession_nodash, doc=self.primary_doc
        )


class SECFilingTextAdapter:
    """Fetch periodic-report text from SEC EDGAR, point-in-time safe."""

    def __init__(
        self,
        rate_limit_seconds: float = 1.0,
        user_agent: str = "StockRecommender research@example.com",
    ) -> None:
        self._rate_limit_seconds = rate_limit_seconds
        self._last_request_time = 0.0
        self._user_agent = user_agent

    def _throttle(self) -> None:
        elapsed = time.time() - self._last_request_time
        if elapsed < self._rate_limit_seconds:
            time.sleep(self._rate_limit_seconds - elapsed)
        self._last_request_time = time.time()

    def _get(self, url: str) -> Any | None:
        headers = {"User-Agent": self._user_agent}
        try:
            self._throttle()
            resp = requests.get(url, headers=headers, timeout=20)
            resp.raise_for_status()
            return resp
        except Exception as exc:  # noqa: BLE001 — adapters fail soft, return None
            logger.warning("SEC filing fetch failed for {}: {}", url, exc)
            return None

    def list_filings(self, ticker: str, cik: int, as_of: date) -> list[FilingRef]:
        """Return 10-K/10-Q filings for *cik* filed on/before *as_of* (point-in-time).

        Sorted oldest→newest so the caller can pair each filing with its prior
        comparable (same form, one fiscal year earlier). Empty on any error.
        """
        resp = self._get(_SUBMISSIONS_URL.format(cik=cik))
        if resp is None:
            return []
        try:
            recent = resp.json()["filings"]["recent"]
        except (KeyError, ValueError) as exc:
            logger.warning("SEC submissions parse failed for CIK {}: {}", cik, exc)
            return []

        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])
        accns = recent.get("accessionNumber", [])
        docs = recent.get("primaryDocument", [])
        reports = recent.get("reportDate", [])

        out: list[FilingRef] = []
        for i, form in enumerate(forms):
            if form not in _PERIODIC_FORMS:
                continue
            try:
                filed = date.fromisoformat(dates[i])
            except (ValueError, IndexError):
                continue
            if filed > as_of:  # point-in-time guard — never see the future
                continue
            out.append(
                FilingRef(
                    ticker=ticker.upper(),
                    cik=cik,
                    form=form,
                    filed_date=filed,
                    fiscal_period=reports[i] if i < len(reports) else "",
                    accession_nodash=(
                        accns[i].replace("-", "") if i < len(accns) else ""
                    ),
                    primary_doc=docs[i] if i < len(docs) else "",
                )
            )
        out.sort(key=lambda f: f.filed_date)
        return out

    def fetch_sections(self, ref: FilingRef) -> dict[str, str]:
        """Return {section_name: text} for the informative sections of one filing.

        HTML is reduced to visible text with an HTML-aware extractor (``_strip_html``)
        that drops <script>/<style> and unwraps inline-XBRL markup, then the cleaned
        text is carved into item sections (``_split_sections``). A section whose item
        heading is absent is OMITTED — the domain service treats it as missing, never
        empty-imputed, so coverage accounting stays honest.
        """
        resp = self._get(ref.document_url)
        if resp is None:
            return {}
        raw = _strip_html(resp.text)
        return _split_sections(raw)


def _strip_html(html: str) -> str:
    """Reduce filing HTML to visible text, robust to inline-XBRL and entities.

    Uses an HTML parser (not tag-regex stripping): <script>/<style> bodies are removed
    rather than dumped into the text, inline-XBRL wrapper tags (``<ix:nonNumeric>`` …)
    are unwrapped to their displayed value, and HTML entities (``&#160;``, ``&amp;`` …)
    are decoded — none of which the old ``<[^>]+>`` regex handled correctly.
    """
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "head"]):
        tag.decompose()
    text = soup.get_text(separator=" ")
    return re.sub(r"\s+", " ", text).strip()


def _split_sections(text: str) -> dict[str, str]:
    """Carve out each informative section from the cleaned document text.

    A 10-K/10-Q prints each item heading TWICE — once in the table of contents (where
    the next heading follows almost immediately) and once at the real section body
    (followed by paragraphs of text). For each section we therefore take ALL anchor
    matches and keep the one with the largest span to the next item boundary — the body
    copy, never the TOC line. A section whose anchor never appears is omitted entirely.
    """
    boundaries = sorted(m.start() for m in _ITEM_BOUNDARY.finditer(text))
    boundaries.append(len(text))

    sections: dict[str, str] = {}
    for name, pat in _SECTION_ANCHORS.items():
        best: tuple[int, int] | None = None  # (span, start)
        for m in pat.finditer(text):
            start = m.start()
            end = next((b for b in boundaries if b > start), len(text))
            span = end - start
            if best is None or span > best[0]:
                best = (span, start)
        if best is not None:
            span, start = best
            sections[name] = text[start : start + span]
    return sections
