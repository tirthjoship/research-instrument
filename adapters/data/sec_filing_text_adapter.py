"""SEC filing-TEXT adapter — fetches 10-K / 10-Q document text for the Lazy Prices test.

Distinct from ``sec_edgar_adapter.py`` (which uses EFTS search for 13D/Form-4 smart-money
signals). This one pulls the actual periodic-report DOCUMENT text via the SEC submissions
API, so the domain ``filing_textchange_service`` can diff consecutive comparable filings.

Point-in-time discipline: ``list_filings(..., as_of)`` returns only filings whose
``filed_date <= as_of``. Section extraction from raw 10-K/10-Q HTML is deliberately a
focused, hardening-pending step (see EXTRACTION TODO) — the URL/fetch plumbing and the
point-in-time contract are real so the rig is runnable end-to-end once extraction lands.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import date
from typing import Any

import requests
from loguru import logger

_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
_ARCHIVE_DOC = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession_nodash}/{doc}"
_PERIODIC_FORMS = ("10-K", "10-Q")

# Naive section anchors — production hardening should replace with item-tag parsing.
_SECTION_ANCHORS: dict[str, re.Pattern[str]] = {
    "risk_factors": re.compile(r"item\s+1a[\.\s].{0,40}risk\s+factors", re.I),
    "litigation": re.compile(r"item\s+3[\.\s].{0,40}legal\s+proceedings", re.I),
    "management": re.compile(r"item\s+7[\.\s].{0,60}management.{0,20}discussion", re.I),
}


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

        EXTRACTION TODO (hardening): the current splitter is anchor-regex based and
        will mis-handle some inline-XBRL 10-Ks. Replace with EDGAR financial-statement
        item parsing (e.g. sec-parsers / edgartools) before the verdict run. The
        point-in-time contract and pairing logic above do NOT depend on this and are
        already correct.
        """
        resp = self._get(ref.document_url)
        if resp is None:
            return {}
        raw = _strip_html(resp.text)
        return _split_sections(raw)


def _strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"&[a-z]+;", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _split_sections(text: str) -> dict[str, str]:
    """Carve out each informative section from the cleaned document text.

    Finds each section's anchor, then takes text up to the next anchor. Best-effort:
    a section whose anchor is absent is simply omitted (the domain service then treats
    it as missing rather than empty-imputed).
    """
    hits: list[tuple[int, str]] = []
    for name, pat in _SECTION_ANCHORS.items():
        m = pat.search(text)
        if m:
            hits.append((m.start(), name))
    hits.sort()
    sections: dict[str, str] = {}
    for idx, (start, name) in enumerate(hits):
        end = hits[idx + 1][0] if idx + 1 < len(hits) else len(text)
        sections[name] = text[start:end]
    return sections
