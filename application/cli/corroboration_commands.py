"""Corroboration CLI command: corroborate. RESEARCH_ONLY — attributed evidence."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, cast

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

    as_of: date = date.fromisoformat(as_of_str) if as_of_str else datetime.now().date()

    # ---- adapters -------------------------------------------------------
    # Task B: use cached_preferred to avoid re-pinging list_models every run.
    # Cache stored at data/cache/model_registry.json with 7-day TTL.
    _cache_path = "data/cache/model_registry.json"

    def _read_text(path: str) -> str:
        return Path(path).read_text()

    def _write_text(path: str, text: str) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    registry = ModelRegistry(listers={"gemini": gemini_lister})
    preferred = registry.cached_preferred(
        "gemini",
        now=datetime.now(),
        read_text=_read_text,
        write_text=_write_text,
        cache_path=_cache_path,
    )
    provider = _GeminiProvider(preferred)
    summarizer = LLMSummarizer(provider=provider, preferred=preferred)

    def _search_fn(query: str) -> list[dict[str, object]]:
        """DuckDuckGo free search — lazy-import so module loads cleanly.

        Prefers the maintained ``ddgs`` package; falls back to the deprecated
        ``duckduckgo_search`` name for older environments.
        """
        try:
            try:
                from ddgs import DDGS
            except ImportError:
                from duckduckgo_search import DDGS  # type: ignore[assignment]

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

    # Build harvester with the summarizer for page text → stance/thesis.
    # Task C: _SummarizingSearchHarvester now exposes last_raw_count so we can
    # distinguish broken-pipeline from a genuinely-empty result.
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

    # Task A: Real OurReadout wiring via _build_readout_fn.
    held_tickers: set[str] = (
        set()
    )  # no holdings input yet — wired when holdings are passed
    readout_fn = _build_readout_fn(as_of, held_tickers)

    uc = CorroborationUseCase(
        harvester=harvester,
        verifier=verifier,
        readout_fn=readout_fn,
        held_tickers=held_tickers,
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

    # Task C: Distinguish broken-pipeline from genuinely-empty result.
    if len(result.candidates) == 0:
        raw_count = harvester.last_raw_count
        if raw_count == 0:
            click.echo(
                click.style(
                    "WARNING: search returned nothing — likely no API access / network "
                    "issue, not a clean empty result. Check DuckDuckGo connectivity.",
                    fg="yellow",
                )
            )
        else:
            click.echo(
                click.style(
                    f"WARNING: {raw_count} raw candidate(s) were harvested from search "
                    "but all were dropped (unverified or no credible stance extracted). "
                    "No corroborated recommendations found.",
                    fg="yellow",
                )
            )

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
# Task A: Real OurReadout builder
# ---------------------------------------------------------------------------

# Sentinel for lazy screen cache (distinguishes "not yet loaded" from "loaded as None")
_SENTINEL: object = object()


def _build_readout_fn(
    as_of: date,
    held_tickers: set[str],
) -> Callable[[str, date], Any]:
    """Return a closure that assembles a real OurReadout for each ticker.

    All live fetches are lazy (inside the closure) and exception-safe so the
    module still imports without network/API access.

    Divergence wiring is best-effort: requires SQLiteStore data to be present.
    If the DB is empty or the query fails, divergence_flag defaults to False
    with no fabrication.

    Held-position discipline is None in practice today (the CLI passes
    held_tickers=set()); wired when holdings are passed in.
    """
    import json as _json

    from application.corroboration_readout import assemble_readout

    # --- load the latest available screen JSON once, lazily ---
    _screen_cache: list[Any] = [_SENTINEL]

    def _load_screen() -> dict[str, Any] | None:
        if _screen_cache[0] is not _SENTINEL:
            return cast("dict[str, Any] | None", _screen_cache[0])
        screen: dict[str, Any] | None = None
        try:
            report_dir = Path("data/reports")
            if report_dir.exists():
                # Collect all screen_<date>.json files (not screen_ic_*)
                candidates = sorted(
                    (
                        p
                        for p in report_dir.glob("screen_*.json")
                        if not p.name.startswith("screen_ic_")
                    )
                )
                # Pick the most recent on/before as_of
                as_of_str = as_of.isoformat()
                eligible = [
                    p for p in candidates if p.stem.replace("screen_", "") <= as_of_str
                ]
                if eligible:
                    latest = eligible[-1]
                    screen = _json.loads(latest.read_text())
        except Exception:
            screen = None
        _screen_cache[0] = screen
        return screen

    def _readout_fn(ticker: str, _as_of: date) -> Any:
        # --- trend health (live yfinance fetch) ---
        trend_health_float: float | None = None
        try:
            from datetime import timezone as _tz

            from adapters.data.yfinance_adapter import YFinanceAdapter
            from domain.trend_rules import atr, sma
            from domain.trend_rules import trend_health as _th_fn

            adapter = YFinanceAdapter(cache_dir=Path("data/cache"))
            now = datetime.now(_tz.utc)
            two_years_ago = now.replace(year=now.year - 2)
            signals = adapter.get_signals(ticker, now, start_date=two_years_ago)
            if len(signals) >= 22:
                closes = [s.price for s in signals]
                highs = [s.high for s in signals]
                lows = [s.low for s in signals]
                sma_val = sma(closes, min(200, len(closes)))
                atr_val = atr(highs, lows, closes, 22)
                th = _th_fn(closes[-1], sma_val, atr_val)
                trend_health_float = th  # may be None if ATR unavailable
        except Exception:
            trend_health_float = None

        # --- divergence flag (deferred — honestly False) ---
        # Real cross-modal divergence (blended_divergence_score) needs BOTH a buzz/
        # attention series AND a price series so it can detect buzz accelerating
        # AHEAD of price. The store gives attention but not a point-in-time price
        # series here, and the thesis is explicit that buzz ALONE is not divergence
        # (buzz != returns). Rather than ship a misleading buzz-only proxy, leave
        # this honestly False until the price series is wired (SP2). No fabrication.
        divergence_flag: bool = False

        # --- discipline flag (held-position discipline: wired when holdings are passed) ---
        discipline_flag: str | None = None
        if ticker in held_tickers:
            # held-position discipline: wired when holdings are passed
            # Currently held_tickers=set() in the CLI, so this branch never fires.
            discipline_flag = None  # placeholder — extend when holdings port is wired

        return assemble_readout(
            ticker,
            trend_health_float=trend_health_float,
            screen=_load_screen(),
            divergence_flag=divergence_flag,
            discipline_flag=discipline_flag,
        )

    return _readout_fn


# ---------------------------------------------------------------------------
# Private helpers (lazy — only evaluated when command is invoked)
# ---------------------------------------------------------------------------


def _load_known_tickers() -> set[str]:
    """Load known tickers from config files; falls back to a small hardcoded set."""
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
            import os

            import google.generativeai as genai  # noqa: PLC0415

            api_key = os.environ.get("GEMINI_API_KEY")
            if not api_key:
                return "neutral", ""
            genai.configure(api_key=api_key)
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
    """Adapts SearchHarvester + LLMSummarizer to the RecommendationHarvestPort.

    Task C: exposes ``last_raw_count`` — the number of raw search candidates
    returned by SearchHarvester.search_candidates() on the most recent harvest
    call.  Zero means search itself returned nothing (likely a network/API issue);
    non-zero means candidates existed but were dropped during summarization.
    """

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
        self.last_raw_count: int = 0

    def harvest(self, as_of: date) -> list[HarvestedClaim]:
        from domain.corroboration_models import HarvestedClaim, Stance

        candidates = self._harvester.search_candidates(as_of)
        self.last_raw_count = len(
            candidates
        )  # Task C: track raw count before summarization
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
