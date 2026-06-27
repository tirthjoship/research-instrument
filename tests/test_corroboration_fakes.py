# tests/test_corroboration_fakes.py
from datetime import date

from tests.fakes.corroboration_fakes import FakeHarvester, FakeVerifier


def test_fake_harvester_returns_seeded_claims():
    h = FakeHarvester(seed_tickers=["NVDA"])
    claims = h.harvest(date(2026, 6, 20))
    assert claims and claims[0].ticker == "NVDA"


def test_fake_verifier_marks_known_url_verified():
    v = FakeVerifier(good_urls={"https://good"})
    assert v.verify("https://good", "NVDA") is True
    assert v.verify("https://bad", "NVDA") is False
