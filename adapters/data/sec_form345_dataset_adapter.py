"""SEC DERA 'Insider Transactions' (Form 345) quarterly dataset ingest.

Downloads the quarterly zip, parses SUBMISSION / REPORTINGOWNER / NONDERIV_TRANS
TSVs, joins on ACCESSION_NUMBER, and yields domain InsiderTransaction records.
Verified live 2026-06-09: URL pattern, columns, coverage floor 2006q1 (see spec
sec.3.1). SEC fair-access requires a declared User-Agent or returns HTTP 403.
"""

from __future__ import annotations

import io
import zipfile
from datetime import date, datetime
from pathlib import Path

import requests
from loguru import logger

from domain.insider_cluster import InsiderTransaction

DERA_URL = (
    "https://www.sec.gov/files/structureddata/data/"
    "insider-transactions-data-sets/{q}_form345.zip"
)
SEC_USER_AGENT = "tirthjoshi95@gmail.com portfolio-research"


def _parse_dera_date(s: str) -> date:
    return datetime.strptime(s.strip(), "%d-%b-%Y").date()


def _read_tsv(zf: zipfile.ZipFile, name: str) -> list[dict[str, str]]:
    with zf.open(name) as fh:
        text = io.TextIOWrapper(fh, encoding="latin-1")
        header = text.readline().rstrip("\n").split("\t")
        rows: list[dict[str, str]] = []
        for line in text:
            parts = line.rstrip("\n").split("\t")
            if len(parts) != len(header):
                continue
            rows.append(dict(zip(header, parts)))
        return rows


class SECForm345DatasetAdapter:
    def __init__(self, cache_dir: Path, timeout: float = 60.0) -> None:
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._timeout = timeout

    def _download(self, year: int, quarter: int) -> bytes:
        q = f"{year}q{quarter}"
        cache = self._cache_dir / f"{q}_form345.zip"
        if cache.exists():
            return cache.read_bytes()
        url = DERA_URL.format(q=q)
        logger.info("SEC DERA download {}", url)
        resp = requests.get(
            url, headers={"User-Agent": SEC_USER_AGENT}, timeout=self._timeout
        )
        resp.raise_for_status()
        cache.write_bytes(resp.content)
        return resp.content

    def get_quarter(self, year: int, quarter: int) -> list[InsiderTransaction]:
        raw = self._download(year, quarter)
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            subs = {r["ACCESSION_NUMBER"]: r for r in _read_tsv(zf, "SUBMISSION.tsv")}
            owners = _read_tsv(zf, "REPORTINGOWNER.tsv")
            trans = _read_tsv(zf, "NONDERIV_TRANS.tsv")

        owner_by_acc: dict[str, list[str]] = {}
        for o in owners:
            owner_by_acc.setdefault(o["ACCESSION_NUMBER"], []).append(o["RPTOWNERCIK"])

        out: list[InsiderTransaction] = []
        for tr in trans:
            acc = tr["ACCESSION_NUMBER"]
            sub = subs.get(acc)
            if sub is None:
                continue
            ticker = (sub.get("ISSUERTRADINGSYMBOL") or "").strip().upper()
            if not ticker:
                continue
            try:
                filing_date = _parse_dera_date(sub["FILING_DATE"])
                trans_date = _parse_dera_date(
                    tr.get("TRANS_DATE") or sub["FILING_DATE"]
                )
                shares = float(tr.get("TRANS_SHARES") or 0.0)
                price = float(tr.get("TRANS_PRICEPERSHARE") or 0.0)
            except (KeyError, ValueError):
                continue
            aff = (sub.get("AFF10B5ONE") or "0").strip() in ("1", "Y", "true", "True")
            swap = (tr.get("EQUITY_SWAP_INVOLVED") or "0").strip() in (
                "1",
                "Y",
                "true",
                "True",
            )
            for cik in owner_by_acc.get(acc, []):
                out.append(
                    InsiderTransaction(
                        ticker=ticker,
                        insider_cik=cik,
                        accession=acc,
                        trans_code=(tr.get("TRANS_CODE") or "").strip(),
                        acquired_disp=(tr.get("TRANS_ACQUIRED_DISP_CD") or "").strip(),
                        shares=shares,
                        price_per_share=price,
                        filing_date=filing_date,
                        trans_date=trans_date,
                        equity_swap=swap,
                        aff10b51=aff,
                    )
                )
        logger.info("SEC DERA {}q{}: {} transactions", year, quarter, len(out))
        return out
