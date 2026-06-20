"""Corroboration CLI command: corroborate. RESEARCH_ONLY — attributed evidence."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Callable

import click

from ._cli_group import cli

if TYPE_CHECKING:
    from adapters.ml.llm_summarizer import LLMSummarizer
    from domain.corroboration_models import HarvestedClaim


@cli.command("corroborate")
@click.option(
    "--date",
    "as_of_str",
    default=None,
    help="Reference date (YYYY-MM-DD). Defaults to today.",
)
def corroborate(as_of_str: str | None) -> None:
    """Run the corroboration engine. RESEARCH_ONLY — attributed evidence, not a forecast."""
    import sqlite3

    from adapters.data.citation_verifier import CitationVerifier, requests_fetcher
    from adapters.data.corroboration_store import CorroborationStore
    from adapters.ml.llm_summarizer import LLMSummarizer
    from adapters.ml.model_registry import ModelRegistry, gemini_lister
    from application.corroboration_use_case import CorroborationUseCase
    from domain.corroboration_models import OurReadout

    as_of: date = date.fromisoformat(as_of_str) if as_of_str else datetime.now().date()

    # ---- adapters -------------------------------------------------------
    registry = ModelRegistry(listers={"gemini": gemini_lister})
    preferred = registry.preferred("gemini")
    provider = _GeminiProvider(preferred)
    summarizer = LLMSummarizer(provider=provider, preferred=preferred)

    def _search_fn(query: str) -> list[dict[str, object]]:
        """DuckDuckGo free search — lazy-import so module loads cleanly."""
        try:
            from duckduckgo_search import DDGS  # type: ignore[import-not-found]

            with DDGS() as ddgs:
                return [
                    {
                        "title": r.get("title", ""),
                        "url": r.get("href", ""),
                        "content": r.get("body", ""),
                    }
                    for r in ddgs.text(query, max_results=5)
                ]
        except Exception:
            return []

    # Build harvester with the summarizer for page text → stance/thesis
    harvester = _SummarizingSearchHarvester(
        search=_search_fn,
        summarizer=summarizer,
        known_tickers=_load_known_tickers(),
        cap=25,
    )

    # CitationVerifier — empty name_map (ticker alone is the needle)
    verifier = CitationVerifier(fetcher=requests_fetcher, name_map={})

    # CorroborationStore on the standard recommendations DB
    conn = sqlite3.connect("data/recommendations.db")
    store = CorroborationStore(conn)
    store.init_schema()

    # readout_fn — pragmatic stub; wiring EvidenceScreen would require live
    # yfinance and is deferred (see TODO below).
    # TODO(sp2): wire EvidenceScreen readout via _build_evidence_screen
    def _readout_fn(ticker: str, _as_of: date) -> OurReadout:
        return OurReadout(None, None, False, None)

    uc = CorroborationUseCase(
        harvester=harvester,
        verifier=verifier,
        readout_fn=_readout_fn,
        held_tickers=set(),
        store=store,
    )

    # ---- run -----------------------------------------------------------
    click.echo(
        click.style(
            "\n** RESEARCH_ONLY — attributed evidence, not a forecast **\n",
            bold=True,
        )
    )
    click.echo(f"Running corroboration for {as_of.isoformat()} …")

    result = uc.execute(as_of)
    click.echo(f"Run ID: {result.run_id}  |  candidates: {len(result.candidates)}\n")

    for cand in result.candidates:
        click.echo(
            click.style(f"[{cand.ticker}]", bold=True)
            + f"  convergence={cand.convergence.value}  verified={cand.verification}"
        )
        for src in cand.sources:
            click.echo(f"  • {src.source_name}  stance={src.stance.value}  {src.url}")
        r = cand.our_readout
        fp = f"{r.factor_percentile:.0f}" if r.factor_percentile is not None else "n/a"
        th = r.trend_health.value if r.trend_health is not None else "n/a"
        click.echo(
            f"  our_readout: factor_pct={fp}  trend={th}  div={r.divergence_flag}"
        )
        click.echo("")

    click.echo(
        click.style(
            "** RESEARCH_ONLY — attributed evidence, not a forecast **\n",
            bold=True,
        )
    )


# ---------------------------------------------------------------------------
# Private helpers (lazy — only evaluated when command is invoked)
# ---------------------------------------------------------------------------


def _load_known_tickers() -> set[str]:
    """Load known tickers from config files; falls back to a small hardcoded set."""
    from pathlib import Path

    config_dir = Path(__file__).parent.parent.parent / "config" / "tickers"
    tickers: set[str] = set()
    for fname in ("sp500.txt", "nasdaq100.txt"):
        fpath = config_dir / fname
        if fpath.exists():
            for line in fpath.read_text().splitlines():
                s = line.strip()
                if s and not s.startswith("#"):
                    tickers.add(s)
    if not tickers:
        tickers = {"AAPL", "MSFT", "GOOG", "AMZN", "META", "TSLA", "NVDA", "JPM"}
    return tickers


class _GeminiProvider:
    """Thin wrapper around google.generativeai to satisfy ModelProviderPort."""

    def __init__(self, models: list[str]) -> None:
        self._models = models

    def list_free_models(self) -> list[str]:
        return list(self._models)

    def summarize(self, model: str, page_text: str, ticker: str) -> tuple[str, str]:
        try:
            import google.generativeai as genai  # noqa: PLC0415

            m = genai.GenerativeModel(model)
            prompt = (
                f"Analyse this text about {ticker}. "
                "Reply with exactly two lines:\n"
                "STANCE: bullish|bearish|neutral\n"
                "THESIS: one sentence attributing the source's view.\n\n"
                f"{page_text[:3000]}"
            )
            resp = m.generate_content(prompt)
            text: str = resp.text or ""
            stance = "neutral"
            thesis = ""
            for line in text.splitlines():
                if line.upper().startswith("STANCE:"):
                    s = line.split(":", 1)[1].strip().lower()
                    if s in {"bullish", "bearish", "neutral"}:
                        stance = s
                elif line.upper().startswith("THESIS:"):
                    thesis = line.split(":", 1)[1].strip()
            return stance, thesis
        except Exception:
            return "neutral", ""


class _SummarizingSearchHarvester:
    """Adapts SearchHarvester + LLMSummarizer to the RecommendationHarvestPort."""

    def __init__(
        self,
        search: Callable[[str], list[dict[str, object]]],
        summarizer: LLMSummarizer,
        known_tickers: set[str],
        cap: int = 25,
    ) -> None:
        from adapters.data.search_harvester import SearchHarvester

        self._harvester = SearchHarvester(
            search=search,
            known_tickers=known_tickers,
            cap=cap,
        )
        self._summarizer = summarizer

    def harvest(self, as_of: date) -> list[HarvestedClaim]:
        from domain.corroboration_models import HarvestedClaim, Stance

        candidates = self._harvester.search_candidates(as_of)
        claims: list[HarvestedClaim] = []
        for c in candidates:
            ticker = str(c["ticker"])
            url = str(c["url"])
            snippet = str(c.get("snippet", ""))
            stance_str, thesis = self._summarizer.summarize(snippet, ticker)
            try:
                stance = Stance(stance_str)
            except ValueError:
                stance = Stance.NEUTRAL
            claims.append(
                HarvestedClaim(
                    source_name=url.split("/")[2] if "/" in url else url,
                    ticker=ticker,
                    stance=stance,
                    thesis_summary=thesis or snippet[:120],
                    url=url,
                    published_at=as_of,
                    verified=False,
                    reliability_weight=0.5,
                )
            )
        return claims
