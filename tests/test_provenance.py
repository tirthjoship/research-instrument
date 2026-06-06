"""Provenance tests — stored timestamp is the SOURCE observation date, not fetch date.

The project's #1 rule (no look-ahead) extends to data storage: every
AttentionPoint.timestamp must equal the date the observation was *recorded by
the source* (i.e. the Wikipedia daily bucket or the Google Trends week-start),
never the wall-clock time we fetched it.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch


def test_wikipedia_ts_is_observation_date() -> None:
    """Wikipedia adapter must parse the API timestamp field as the observation date."""
    from adapters.data.wikipedia_pageviews_adapter import WikipediaPageviewsAdapter

    # API returns timestamp in "YYYYMMDDHH" format representing the observation day.
    payload = {"items": [{"timestamp": "2026060100", "views": 10}]}
    with patch("adapters.data.wikipedia_pageviews_adapter.requests.get") as g:
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = payload
        mock_resp.raise_for_status = lambda: None
        g.return_value = mock_resp
        pts = WikipediaPageviewsAdapter(
            article_map={"ASTS": "AST_SpaceMobile"}
        ).get_attention_series("ASTS", datetime(2026, 6, 1), datetime(2026, 6, 2))
    assert len(pts) == 1
    # timestamp must be the observation date (2026-06-01), NOT today's fetch date
    assert pts[0].timestamp == datetime(2026, 6, 1)


def test_google_trends_ts_is_observation_date() -> None:
    """Google Trends adapter must use the data point's week-start as the timestamp."""
    from adapters.data.google_trends_adapter import GoogleTrendsAdapter

    a = GoogleTrendsAdapter()
    # BuzzSignal.fetched_at holds the *observation* week date (set from the
    # pandas Timestamp index, not from time.time()).
    fake_signal = MagicMock()
    fake_signal.fetched_at = datetime(2026, 5, 1)
    fake_signal.mention_count = 50
    with patch.object(a, "get_historical_interest", return_value=[fake_signal]):
        pts = a.get_attention_series("ASTS", datetime(2026, 4, 1), datetime(2026, 6, 1))
    assert len(pts) == 1
    # timestamp must equal the observation week date, NOT today
    assert pts[0].timestamp == datetime(2026, 5, 1)
