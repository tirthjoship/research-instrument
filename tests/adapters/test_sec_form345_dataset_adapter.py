import io
import zipfile
from datetime import date

from adapters.data.sec_form345_dataset_adapter import SECForm345DatasetAdapter
from domain.ports import InsiderTransactionsPort


def _make_zip() -> bytes:
    sub = (
        "ACCESSION_NUMBER\tFILING_DATE\tISSUERTRADINGSYMBOL\tAFF10B5ONE\n"
        "0001\t10-JAN-2020\tABC\t0\n"
        "0002\t12-JAN-2020\tABC\t1\n"
    )
    own = "ACCESSION_NUMBER\tRPTOWNERCIK\n" "0001\t111\n" "0002\t222\n"
    trans = (
        "ACCESSION_NUMBER\tTRANS_CODE\tTRANS_ACQUIRED_DISP_CD\tTRANS_SHARES"
        "\tTRANS_PRICEPERSHARE\tEQUITY_SWAP_INVOLVED\tTRANS_DATE\n"
        "0001\tP\tA\t100\t5.0\t0\t08-JAN-2020\n"
        "0002\tP\tA\t200\t6.0\t0\t10-JAN-2020\n"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("SUBMISSION.tsv", sub)
        z.writestr("REPORTINGOWNER.tsv", own)
        z.writestr("NONDERIV_TRANS.tsv", trans)
    return buf.getvalue()


def test_parse_join_yields_transactions(tmp_path, monkeypatch):
    adapter = SECForm345DatasetAdapter(cache_dir=tmp_path)
    monkeypatch.setattr(adapter, "_download", lambda y, q: _make_zip())
    txns = adapter.get_quarter(2020, 1)
    assert len(txns) == 2
    abc = next(t for t in txns if t.insider_cik == "111")
    assert abc.ticker == "ABC"
    assert abc.trans_code == "P" and abc.acquired_disp == "A"
    assert abc.shares == 100.0 and abc.price_per_share == 5.0
    assert abc.filing_date == date(2020, 1, 10)
    assert abc.aff10b51 is False
    assert abc.accession == "0001"
    other = next(t for t in txns if t.insider_cik == "222")
    assert other.aff10b51 is True
    assert other.accession == "0002"


def test_missing_prices_smoke(tmp_path, monkeypatch):
    adapter = SECForm345DatasetAdapter(cache_dir=tmp_path)
    monkeypatch.setattr(adapter, "_download", lambda y, q: _make_zip())
    assert adapter.get_quarter(2020, 1)


def test_satisfies_port(tmp_path):
    adapter = SECForm345DatasetAdapter(cache_dir=tmp_path)
    assert isinstance(adapter, InsiderTransactionsPort)
