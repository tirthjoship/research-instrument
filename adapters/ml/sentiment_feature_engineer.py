"""Sentiment feature engineer — computes 24 sentiment/buzz/divergence features.

Zero external framework imports. Only math + stdlib.
"""

from __future__ import annotations

import math

from domain.models import BuzzSignal, Sentiment, SourceReliability

_NAN = float("nan")

SENTIMENT_FEATURE_NAMES: list[str] = [
    "buzz_volume",
    "buzz_acceleration",
    "sentiment_keyword",
    "sentiment_flan_t5",
    "sentiment_agreement",
    "sentiment_momentum_3d",
    "sentiment_momentum_7d",
    "source_weighted_sentiment",
    "top_source_reliability",
    "rss_reddit_divergence",
    "sentiment_price_divergence_flag",
    "sentiment_price_divergence_magnitude",
    "buzz_price_divergence",
    "sector_buzz_ratio",
    # Phase 3.5 features
    "google_trends_current",
    "google_trends_change_1w",
    "google_trends_spike",
    "stocktwits_volume_24h",
    "stocktwits_bullish_ratio",
    "stocktwits_volume_change",
    "news_sentiment_avg_7d",
    "news_volume_7d",
    "news_sentiment_momentum",
    "news_negative_spike",
]


def _safe_avg(values: list[float]) -> float:
    """Return average of values, or NaN if empty."""
    if not values:
        return _NAN
    return sum(values) / len(values)


def _is_valid(v: float) -> bool:
    return not math.isnan(v)


def _sign(v: float) -> int:
    if v > 0:
        return 1
    if v < 0:
        return -1
    return 0


class SentimentFeatureEngineer:
    """Computes 24 sentiment/buzz/divergence features from raw signal inputs."""

    def compute(
        self,
        keyword_sentiment: float,
        flan_t5_sentiment: float,
        sentiments: list[Sentiment],
        buzz_signals_current: list[BuzzSignal],
        buzz_signals_prior: list[BuzzSignal],
        sector_buzz_total: int,
        reliability: SourceReliability,
        price_return_5d: float,
        # Phase 3.5 — optional new source inputs
        google_trends_signals: list[BuzzSignal] | None = None,
        google_trends_prior: list[BuzzSignal] | None = None,
        google_trends_52w_mean: float | None = None,
        google_trends_52w_std: float | None = None,
        stocktwits_signals: list[BuzzSignal] | None = None,
        stocktwits_prior: list[BuzzSignal] | None = None,
        news_sentiments_7d: list[Sentiment] | None = None,
        news_sentiments_prior_7d: list[Sentiment] | None = None,
        news_negative_baseline_mean: float | None = None,
        news_negative_baseline_std: float | None = None,
    ) -> dict[str, float]:
        """Compute all 24 sentiment features.

        Args:
            keyword_sentiment: Keyword-scorer sentiment in [-1, 1] or NaN.
            flan_t5_sentiment: Flan-T5 scorer sentiment in [-1, 1] or NaN.
            sentiments: Ordered list of Sentiment objects (most-recent first).
            buzz_signals_current: Buzz signals for the current window.
            buzz_signals_prior: Buzz signals for the prior window.
            sector_buzz_total: Total buzz count across the sector.
            reliability: SourceReliability for the top source.
            price_return_5d: 5-day price return, or NaN.

        Returns:
            Dict mapping each feature name to its computed float value.
        """
        current_count = len(buzz_signals_current)
        prior_count = len(buzz_signals_prior)

        # 1. buzz_volume
        buzz_volume = float(current_count)

        # 2. buzz_acceleration
        if prior_count > 0:
            buzz_acceleration = (current_count - prior_count) / prior_count
        elif current_count > 0:
            buzz_acceleration = float(current_count)
        else:
            buzz_acceleration = 0.0

        # 3 & 4. pass-through
        sentiment_keyword = keyword_sentiment
        sentiment_flan_t5 = flan_t5_sentiment

        # 5. sentiment_agreement
        kw_valid = _is_valid(keyword_sentiment)
        ft_valid = _is_valid(flan_t5_sentiment)
        if not kw_valid or not ft_valid:
            sentiment_agreement = _NAN
        else:
            kw_sign = _sign(keyword_sentiment)
            ft_sign = _sign(flan_t5_sentiment)
            if kw_sign == 0 or ft_sign == 0:
                # zero treated as neither agreement nor disagreement
                sentiment_agreement = _NAN
            elif kw_sign == ft_sign:
                sentiment_agreement = 1.0
            else:
                sentiment_agreement = 0.0

        # 6. sentiment_momentum_3d
        scores = [s.sentiment_score for s in sentiments]
        if len(scores) < 2:
            sentiment_momentum_3d = _NAN
        else:
            # split at 3-item boundary; fall back to even split for short lists
            recent_part = scores[: min(3, len(scores) // 2 + len(scores) % 2)]
            older_part = scores[len(recent_part) : len(recent_part) + 3]
            if older_part:
                sentiment_momentum_3d = _safe_avg(recent_part) - _safe_avg(older_part)
            else:
                sentiment_momentum_3d = _NAN

        # 7. sentiment_momentum_7d — same logic with 7-item windows
        if len(scores) < 2:
            sentiment_momentum_7d = _NAN
        else:
            recent7 = scores[:7]
            older7 = scores[7:14]
            if older7:
                sentiment_momentum_7d = _safe_avg(recent7) - _safe_avg(older7)
            else:
                # fall back to splitting evenly
                mid = len(scores) // 2
                recent_h = scores[: mid + len(scores) % 2]
                older_h = scores[mid + len(scores) % 2 :]
                if older_h:
                    sentiment_momentum_7d = _safe_avg(recent_h) - _safe_avg(older_h)
                else:
                    sentiment_momentum_7d = _NAN

        # 8. source_weighted_sentiment
        valid_scores = [s.sentiment_score for s in sentiments]
        if not valid_scores:
            source_weighted_sentiment = _NAN
        else:
            avg_sent = _safe_avg(valid_scores)
            source_weighted_sentiment = avg_sent * reliability.accuracy

        # 9. top_source_reliability
        top_source_reliability = reliability.accuracy

        # 10. rss_reddit_divergence
        rss_scores = [
            b.sentiment_raw for b in buzz_signals_current if "rss" in b.source
        ]
        reddit_scores = [
            b.sentiment_raw for b in buzz_signals_current if "reddit" in b.source
        ]
        if not rss_scores or not reddit_scores:
            rss_reddit_divergence = _NAN
        else:
            rss_avg = _safe_avg(rss_scores)
            reddit_avg = _safe_avg(reddit_scores)
            rss_reddit_divergence = 1.0 if _sign(rss_avg) != _sign(reddit_avg) else 0.0

        # 11 & 12. sentiment_price_divergence_flag / magnitude
        avg_sentiment = _safe_avg(valid_scores) if valid_scores else _NAN
        if not _is_valid(avg_sentiment) or not _is_valid(price_return_5d):
            sentiment_price_divergence_flag = _NAN
            sentiment_price_divergence_magnitude = _NAN
        else:
            diverging = _sign(avg_sentiment) != _sign(price_return_5d) and (
                _sign(avg_sentiment) != 0 and _sign(price_return_5d) != 0
            )
            if diverging:
                sentiment_price_divergence_flag = 1.0
                sentiment_price_divergence_magnitude = abs(avg_sentiment) * abs(
                    price_return_5d
                )
            else:
                sentiment_price_divergence_flag = 0.0
                sentiment_price_divergence_magnitude = 0.0

        # 13. buzz_price_divergence
        if current_count == 0:
            buzz_price_divergence = _NAN
        else:
            buzz_price_divergence = (
                1.0
                if current_count > 5
                and _is_valid(price_return_5d)
                and abs(price_return_5d) < 0.01
                else 0.0
            )

        # 14. sector_buzz_ratio
        if sector_buzz_total == 0:
            sector_buzz_ratio = _NAN
        else:
            sector_buzz_ratio = current_count / sector_buzz_total

        # --- Phase 3.5: Google Trends features ---
        gt_signals = google_trends_signals or []
        gt_prior = google_trends_prior or []

        if gt_signals:
            gt_current_interest = float(gt_signals[0].mention_count)
        else:
            gt_current_interest = _NAN

        if gt_signals and gt_prior:
            prior_interest = float(gt_prior[0].mention_count)
            if prior_interest > 0:
                gt_change_1w = (gt_current_interest - prior_interest) / prior_interest
            else:
                gt_change_1w = _NAN
        else:
            gt_change_1w = _NAN

        if (
            gt_signals
            and google_trends_52w_mean is not None
            and google_trends_52w_std is not None
            and google_trends_52w_std > 0
        ):
            threshold = google_trends_52w_mean + 2.0 * google_trends_52w_std
            gt_spike = 1.0 if gt_current_interest > threshold else 0.0
        else:
            gt_spike = _NAN

        # --- Phase 3.5: StockTwits features ---
        st_signals = stocktwits_signals or []
        st_prior = stocktwits_prior or []

        if st_signals:
            st_volume_24h = float(st_signals[0].mention_count)
            # sentiment_raw is (bull-bear)/total in [-1,1]; normalize to [0,1]
            st_bullish_ratio = (st_signals[0].sentiment_raw + 1.0) / 2.0
        else:
            st_volume_24h = _NAN
            st_bullish_ratio = _NAN

        if st_signals and st_prior:
            prior_vol = float(st_prior[0].mention_count)
            if prior_vol > 0:
                st_volume_change = (st_volume_24h - prior_vol) / prior_vol
            else:
                st_volume_change = _NAN
        else:
            st_volume_change = _NAN

        # --- Phase 3.5: News headline sentiment features ---
        news_7d = news_sentiments_7d or []
        news_prior = news_sentiments_prior_7d or []

        if news_7d:
            news_scores = [s.sentiment_score for s in news_7d]
            news_sentiment_avg = _safe_avg(news_scores)
            news_volume = float(len(news_7d))
        else:
            news_sentiment_avg = _NAN
            news_volume = _NAN

        if news_7d and news_prior:
            current_avg = _safe_avg([s.sentiment_score for s in news_7d])
            prior_avg = _safe_avg([s.sentiment_score for s in news_prior])
            news_sentiment_momentum = current_avg - prior_avg
        else:
            news_sentiment_momentum = _NAN

        if news_7d:
            negative_count = sum(1 for s in news_7d if s.sentiment_score < -0.3)
            n_baseline_mean = (
                news_negative_baseline_mean
                if news_negative_baseline_mean is not None
                else 2.0
            )
            n_baseline_std = (
                news_negative_baseline_std
                if news_negative_baseline_std is not None
                else 1.0
            )
            if n_baseline_std > 0:
                news_neg_spike = (
                    1.0
                    if negative_count > n_baseline_mean + 2.0 * n_baseline_std
                    else 0.0
                )
            else:
                news_neg_spike = _NAN
        else:
            news_neg_spike = _NAN

        return {
            "buzz_volume": buzz_volume,
            "buzz_acceleration": buzz_acceleration,
            "sentiment_keyword": sentiment_keyword,
            "sentiment_flan_t5": sentiment_flan_t5,
            "sentiment_agreement": sentiment_agreement,
            "sentiment_momentum_3d": sentiment_momentum_3d,
            "sentiment_momentum_7d": sentiment_momentum_7d,
            "source_weighted_sentiment": source_weighted_sentiment,
            "top_source_reliability": top_source_reliability,
            "rss_reddit_divergence": rss_reddit_divergence,
            "sentiment_price_divergence_flag": sentiment_price_divergence_flag,
            "sentiment_price_divergence_magnitude": sentiment_price_divergence_magnitude,
            "buzz_price_divergence": buzz_price_divergence,
            "sector_buzz_ratio": sector_buzz_ratio,
            # Phase 3.5 features
            "google_trends_current": gt_current_interest,
            "google_trends_change_1w": gt_change_1w,
            "google_trends_spike": gt_spike,
            "stocktwits_volume_24h": st_volume_24h,
            "stocktwits_bullish_ratio": st_bullish_ratio,
            "stocktwits_volume_change": st_volume_change,
            "news_sentiment_avg_7d": news_sentiment_avg,
            "news_volume_7d": news_volume,
            "news_sentiment_momentum": news_sentiment_momentum,
            "news_negative_spike": news_neg_spike,
        }
