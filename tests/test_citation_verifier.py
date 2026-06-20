# tests/test_citation_verifier.py
from adapters.data.citation_verifier import CitationVerifier


def test_verified_when_page_resolves_and_names_ticker() -> None:
    def fetch(url: str) -> tuple[int, str]:
        return (200, "NVIDIA (NVDA) raised to 5 stars")

    v = CitationVerifier(fetcher=fetch, name_map={"NVDA": ["NVIDIA"]})
    assert v.verify("https://x", "NVDA") is True


def test_dropped_on_404() -> None:
    v = CitationVerifier(fetcher=lambda u: (404, ""), name_map={})
    assert v.verify("https://x", "NVDA") is False


def test_dropped_when_ticker_not_mentioned() -> None:
    def fetch(url: str) -> tuple[int, str]:
        return (200, "unrelated content")

    v = CitationVerifier(fetcher=fetch, name_map={"NVDA": ["NVIDIA"]})
    assert v.verify("https://x", "NVDA") is False


def test_short_ticker_does_not_false_verify_on_incidental_letter() -> None:
    # "F" (Ford) must not verify against a page that merely contains the letter f.
    def fetch(url: str) -> tuple[int, str]:
        return (200, "A fund manager profited from definitely unrelated assets")

    v = CitationVerifier(fetcher=fetch, name_map={})
    assert v.verify("https://x", "F") is False


def test_short_ticker_verifies_on_word_boundary_mention() -> None:
    def fetch(url: str) -> tuple[int, str]:
        return (200, "Ford Motor (F) upgraded by the analyst")

    v = CitationVerifier(fetcher=fetch, name_map={})
    assert v.verify("https://x", "F") is True
