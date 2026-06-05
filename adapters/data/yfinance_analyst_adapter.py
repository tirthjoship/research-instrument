"""yfinance analyst-history adapter — AnalystRatingsPort implementation.

Uses ``yfinance.Ticker.upgrades_downgrades`` which retains multi-year history,
unlike the Finnhub free tier (~4 months). The pure helper ``parse_yf_upgrades``
is pandas-free and fully unit-testable without network access.
"""

from __future__ import annotations

from datetime import datetime

from loguru import logger

from domain.analyst import AnalystAction, AnalystRating

_ACTION_MAP: dict[str, AnalystAction] = {
    "up": AnalystAction.UPGRADE,
    "down": AnalystAction.DOWNGRADE,
    "init": AnalystAction.INIT,
    "reinit": AnalystAction.INIT,
    "main": AnalystAction.MAINTAIN,
}


def parse_yf_upgrades(
    records: list[dict],  # type: ignore[type-arg]
    ticker: str,
    since: datetime,
    until: datetime | None,
    source: str = "yfinance",
) -> list[AnalystRating]:
    """Pure helper: convert yfinance upgrades_downgrades records to AnalystRating list.

    Applies point-in-time filtering: drops items published before ``since`` or
    after ``until``. Skips entries with missing ``GradeDate``.

    The caller is responsible for converting the DataFrame to records via::

        df.reset_index().to_dict("records")

    so that this function remains pandas-free and unit-testable.

    Args:
        records: List of dicts with keys GradeDate, Firm, ToGrade, FromGrade, Action.
        ticker: Stock ticker symbol (e.g. ``"NVDA"``).
        since: Inclusive lower bound for publish datetime.
        until: Inclusive upper bound (point-in-time safe). None means no upper bound.
        source: Source label attached to each AnalystRating.

    Returns:
        List of AnalystRating objects, ordered as received.
    """
    out: list[AnalystRating] = []
    for rec in records:
        gd = rec.get("GradeDate")
        if gd is None:
            continue
        # pandas Timestamp is a subclass of datetime — isinstance check handles both;
        # string dates are parsed via fromisoformat (truncated to 19 chars to drop tz).
        published: datetime = (
            gd if isinstance(gd, datetime) else datetime.fromisoformat(str(gd)[:19])
        )
        if published < since or (until is not None and published > until):
            continue
        fg = rec.get("FromGrade")
        prior: str | None = str(fg) if fg else None
        action = _ACTION_MAP.get(
            str(rec.get("Action", "")).lower(), AnalystAction.MAINTAIN
        )
        out.append(
            AnalystRating(
                ticker=ticker,
                firm=str(rec.get("Firm", "")),
                rating=str(rec.get("ToGrade", "")),
                prior_rating=prior,
                action=action,
                price_target=None,
                published_at=published,
                source=source,
            )
        )
    return out


class YFinanceAnalystAdapter:
    """AnalystRatingsPort implementation using yfinance upgrades_downgrades.

    Fetches multi-year analyst rating history (Finnhub free tier only retains
    ~4 months; yfinance returns years of history). On any network, parse, or
    data error the adapter logs a warning and returns an empty list — it never
    raises.
    """

    def get_rating_events(
        self,
        ticker: str,
        since: datetime,
        until: datetime | None = None,
    ) -> list[AnalystRating]:
        """Return analyst rating events for *ticker* published in [since, until].

        Fetches ``yfinance.Ticker(ticker).upgrades_downgrades`` and applies
        point-in-time filtering via ``parse_yf_upgrades``.

        Args:
            ticker: Stock ticker symbol (e.g. ``"AAPL"``).
            since: Inclusive start datetime.
            until: Inclusive end datetime (point-in-time bound). None = no upper bound.

        Returns:
            List of AnalystRating objects. Empty list on any error.
        """
        try:
            import yfinance as yf

            df = yf.Ticker(ticker).upgrades_downgrades
            if df is None or df.empty:
                return []
            records = df.reset_index().to_dict("records")
            return parse_yf_upgrades(records, ticker, since, until)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "YFinanceAnalystAdapter: failed to fetch ratings for {}: {}",
                ticker,
                exc,
            )
            return []
