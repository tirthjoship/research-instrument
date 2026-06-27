from datetime import date

from adapters.data.search_harvester import SearchHarvester


def test_harvester_extracts_tickers_and_urls_from_results() -> None:
    def client(q: str) -> list[dict[str, object]]:
        return [
            {
                "url": "https://a/nvda",
                "title": "Why NVDA is a top buy",
                "content": "NVDA strong",
            }
        ]

    h = SearchHarvester(search=client, known_tickers={"NVDA"}, cap=25)
    raw = h.search_candidates(date(2026, 6, 20))
    assert any(r["ticker"] == "NVDA" and r["url"] == "https://a/nvda" for r in raw)
