from __future__ import annotations

from datetime import date

from domain.corroboration_models import HarvestedClaim, Stance


class FakeHarvester:
    def __init__(self, seed_tickers):
        self._tickers = seed_tickers

    def harvest(self, as_of: date) -> list[HarvestedClaim]:
        return [
            HarvestedClaim(
                f"src-{t}",
                t,
                Stance.BULLISH,
                "seeded why",
                f"https://good/{t}",
                as_of,
                True,
                0.6,
            )
            for t in self._tickers
        ]


class FakeVerifier:
    def __init__(self, good_urls):
        self._good = set(good_urls)

    def verify(self, url: str, ticker: str) -> bool:
        return url in self._good


class FakeModelProvider:
    def __init__(self, models, stance="bullish", thesis="fake thesis"):
        self._models = models
        self._stance = stance
        self._thesis = thesis

    def list_free_models(self) -> list[str]:
        return list(self._models)

    def summarize(self, model: str, page_text: str, ticker: str) -> tuple[str, str]:
        return self._stance, self._thesis
