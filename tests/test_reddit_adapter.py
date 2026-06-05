from datetime import datetime, timezone
from unittest.mock import MagicMock, patch


def test_reddit_no_creds_is_noop():
    from adapters.data.reddit_adapter import RedditAdapter

    a = RedditAdapter(client_id=None, client_secret=None, user_agent=None)
    assert a.enabled is False
    assert (
        a.scan_sources(datetime(2026, 6, 2, tzinfo=timezone.utc), tickers=["ASTS"])
        == []
    )


def test_reddit_with_creds_emits_signal():
    from adapters.data.reddit_adapter import RedditAdapter

    submission = MagicMock(title="ASTS to the moon", score=50, num_comments=10)
    subreddit = MagicMock()
    subreddit.search.return_value = [submission, submission]
    reddit = MagicMock()
    reddit.subreddit.return_value = subreddit
    with patch("adapters.data.reddit_adapter.praw.Reddit", return_value=reddit):
        a = RedditAdapter(
            client_id="x",
            client_secret="y",
            user_agent="z",
            subreddit_map={"ASTS": ["spacestocks"]},
        )
        sigs = a.scan_sources(
            datetime(2026, 6, 2, tzinfo=timezone.utc), tickers=["ASTS"]
        )
    assert len(sigs) == 1
    assert sigs[0].source == "reddit"
    assert sigs[0].mention_count == 2
