"""ConvictionScoringUseCase — orchestrates smart money signal gathering, scoring,
and OpportunityCard generation.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Callable

from loguru import logger

from adapters.ml.smart_money_engineer import SmartMoneyFeatureEngineer
from domain.conviction import (
    ActionType,
    ConvictionScore,
    ConvictionWeights,
    OpportunityCard,
    SmartMoneySignal,
    SmartMoneyType,
)
from domain.conviction_service import (
    compute_conviction,
    compute_freshness_score,
    determine_action,
    rank_opportunities,
)
from domain.event_service import event_conviction_score


class ConvictionScoringUseCase:
    """Orchestrates the full conviction scoring pipeline.

    Steps per ``run()``:
        1. Gather all smart-money signals via the port.
        2. Validate temporal boundary (filter future signals).
        3. For each ticker: compute features → sub-scores → conviction score.
        4. Rank with ``rank_opportunities``.
        5. Build an ``OpportunityCard`` per ranked ticker.
        6. Return cards sorted by conviction descending.
    """

    def __init__(
        self,
        smart_money: object,  # duck-typed SmartMoneyPort
        tickers: list[str],
        weights: ConvictionWeights,
        store: object | None = None,
        pinned: set[str] | None = None,
        top_n: int = 15,
        news_source: object | None = None,
        event_classifier: object | None = None,
        event_impacts: dict[Any, Any] | None = None,
    ) -> None:
        self._smart_money = smart_money
        self._tickers = tickers
        self._weights = weights
        self._store = store
        self._pinned = pinned or set()
        self._top_n = top_n
        self._engineer = SmartMoneyFeatureEngineer()
        self._news_source = news_source
        self._event_classifier = event_classifier
        self._event_impacts: dict[Any, Any] = event_impacts or {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        scan_time: datetime,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[OpportunityCard]:
        """Execute the conviction scoring pipeline and return ranked cards."""
        if not self._tickers:
            return []

        # 1. Gather all signals
        all_signals: list[SmartMoneySignal] = self._smart_money.get_all_signals()  # type: ignore[attr-defined]

        # 2. Validate and filter temporal boundary (drop future signals silently)
        valid_signals = self._filter_future_signals(scan_time, all_signals)

        # 3. Score each ticker
        conviction_scores: list[ConvictionScore] = []
        total = len(self._tickers)
        for idx, ticker in enumerate(self._tickers, start=1):
            try:
                score = self._score_ticker(ticker, valid_signals, scan_time)
                conviction_scores.append(score)
            except Exception as exc:
                logger.debug(f"Skipping {ticker} during conviction scoring: {exc}")
            if progress_callback is not None:
                progress_callback(idx, total)

        # 4. Rank
        ranked = rank_opportunities(
            conviction_scores,
            top_n=self._top_n,
            pinned=self._pinned,
        )

        # 5. Build cards
        cards = [self._build_card(cs, valid_signals, scan_time) for cs in ranked]

        # 6. Sort by conviction descending (rank_opportunities already does this
        #    for non-pinned; re-sort to guarantee full order including pinned)
        cards.sort(key=lambda c: c.conviction, reverse=True)

        logger.info(
            f"ConvictionScoringUseCase: {len(cards)} cards from "
            f"{len(self._tickers)} tickers at {scan_time.isoformat()}"
        )
        return cards

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _filter_future_signals(
        scan_time: datetime, signals: list[SmartMoneySignal]
    ) -> list[SmartMoneySignal]:
        """Return only signals whose filed_date <= scan_time (silently drop rest)."""
        valid: list[SmartMoneySignal] = []
        for sig in signals:
            try:
                filed_dt = datetime.strptime(sig.filed_date, "%Y-%m-%d")
                if filed_dt <= scan_time:
                    valid.append(sig)
                else:
                    logger.debug(
                        f"Filtered future signal: {sig.ticker} filed {sig.filed_date}"
                    )
            except ValueError:
                logger.warning(f"Unparseable filed_date '{sig.filed_date}' — skipped")
        return valid

    def _score_ticker(
        self,
        ticker: str,
        signals: list[SmartMoneySignal],
        scan_time: datetime,
    ) -> ConvictionScore:
        """Compute a ConvictionScore for a single ticker."""
        features = self._engineer.compute(
            ticker=ticker, signals=signals, prediction_time=scan_time
        )

        ticker_signals = [s for s in signals if s.ticker == ticker]

        buzz_signals = None
        recommendation = None
        ticker_info = None

        if self._store is not None:
            try:
                buzz_signals = self._store.get_buzz_signals(ticker=ticker)  # type: ignore[attr-defined]
            except Exception:
                pass
            try:
                recs = self._store.get_recommendations()  # type: ignore[attr-defined]
                ticker_recs = [r for r in recs if r.symbol == ticker]
                recommendation = ticker_recs[0] if ticker_recs else None
            except Exception:
                pass

        try:
            from adapters.visualization.price_cache import _fetch_ticker_info_impl

            ticker_info = _fetch_ticker_info_impl(ticker)
        except Exception:
            pass

        # Event intelligence sub-score (point-in-time: until=scan_time)
        event_score = 5.0
        if self._news_source is not None and self._event_classifier is not None:
            sector = str(ticker_info.get("sector", "")) if ticker_info else ""
            since = scan_time - timedelta(days=30)
            headlines = self._news_source.get_recent_headlines(  # type: ignore[attr-defined]
                ticker, since, scan_time
            )
            events = self._event_classifier.classify_batch(headlines)  # type: ignore[attr-defined]
            event_score = event_conviction_score(
                events, sector, self._event_impacts, scan_time
            )

        sub_scores = self._compute_sub_scores(
            features=features,
            ticker_signals=ticker_signals,
            scan_time=scan_time,
            buzz_signals=buzz_signals,
            ticker_info=ticker_info,
            recommendation=recommendation,
            event_score=event_score,
        )

        conviction = compute_conviction(sub_scores, self._weights)

        # Freshest signal timestamp (fall back to scan_time if none)
        filed_dates = [
            datetime.strptime(s.filed_date, "%Y-%m-%d") for s in ticker_signals
        ]
        freshest = max(filed_dates) if filed_dates else scan_time

        explanation = self._build_explanation(ticker, sub_scores, conviction)

        return ConvictionScore(
            ticker=ticker,
            score=conviction,
            sub_scores=sub_scores,
            signals_firing=sum(1 for v in sub_scores.values() if v > 0),
            freshest_signal=freshest,
            explanation=explanation,
        )

    @staticmethod
    def _compute_sub_scores(
        features: dict[str, float],
        ticker_signals: list[SmartMoneySignal],
        scan_time: datetime,
        buzz_signals: list[Any] | None = None,
        ticker_info: dict[str, Any] | None = None,
        recommendation: object | None = None,
        event_score: float = 5.0,
    ) -> dict[str, float]:
        """Compute the six sub-score dimensions using real data when available."""
        # smart_money (existing logic)
        sm_raw = (
            features.get("sm_13d_count", 0.0) * 3
            + features.get("sm_insider_cluster", 0.0) * 7
            + features.get("sm_activist_count", 0.0) * 2
        )
        sm_score = min(sm_raw, 10.0)

        # signal_agreement: cross-layer check
        layers_firing = 0
        if sm_score > 2:
            layers_firing += 1
        if buzz_signals and any(
            getattr(b, "sentiment_raw", 0) > 0 for b in buzz_signals
        ):
            layers_firing += 1
        if ticker_info and float(ticker_info.get("pegRatio") or 99) < 2:
            layers_firing += 1
        if recommendation and getattr(recommendation, "grade", "") in (
            "strong_buy",
            "buy",
        ):
            layers_firing += 1
        signal_agreement = min(layers_firing / 4.0 * 10.0, 10.0)

        # sentiment_momentum from buzz_signals
        sentiment_momentum = 5.0
        if buzz_signals:
            recent_sentiments: list[float] = []
            for b in buzz_signals:
                fetched = getattr(b, "fetched_at", None)
                raw = float(getattr(b, "sentiment_raw", 0.0))
                if fetched is not None:
                    try:
                        age_days = (scan_time - fetched).total_seconds() / 86400
                        if age_days < 7:
                            recent_sentiments.append(raw)
                    except (TypeError, AttributeError):
                        recent_sentiments.append(raw)
                else:
                    recent_sentiments.append(raw)
            if recent_sentiments:
                avg = sum(recent_sentiments) / len(recent_sentiments)
                sentiment_momentum = max(1.0, min(10.0, 5.0 + avg * 5.0))

        # fundamental_basis from yfinance ticker_info
        fundamental_basis = 5.0
        if ticker_info:
            peg = float(ticker_info.get("pegRatio") or 99)
            mcap = float(ticker_info.get("marketCap") or 1)
            fcf = float(ticker_info.get("freeCashflow") or 0)
            fcf_yield = fcf / max(mcap, 1.0)
            roe = float(ticker_info.get("returnOnEquity") or 0)
            peg_s = 3 if peg < 1 else (2 if peg < 2 else (1 if peg < 3 else 0))
            fcf_s = (
                3
                if fcf_yield > 0.05
                else (2 if fcf_yield > 0.02 else (1 if fcf_yield > 0 else 0))
            )
            roe_s = 4 if roe > 0.2 else (3 if roe > 0.15 else (2 if roe > 0.1 else 1))
            fundamental_basis = max(1.0, min(10.0, float(peg_s + fcf_s + roe_s)))

        # ml_direction from stored recommendation
        ml_direction = 5.0
        if recommendation:
            grade = getattr(recommendation, "grade", "hold")
            grade_map = {
                "strong_buy": 9,
                "buy": 7,
                "hold": 5,
                "may_sell": 3,
                "immediate_sell": 1,
            }
            ml_direction = float(grade_map.get(grade, 5))

        # temporal_freshness (existing logic)
        freshness = 2.0
        for sig in ticker_signals:
            try:
                filed_dt = datetime.strptime(sig.filed_date, "%Y-%m-%d")
                fs = compute_freshness_score(filed_dt, scan_time)
                freshness = max(freshness, fs)
            except ValueError:
                pass

        return {
            "smart_money": sm_score,
            "signal_agreement": signal_agreement,
            "temporal_freshness": freshness,
            "sentiment_momentum": sentiment_momentum,
            "fundamental_basis": fundamental_basis,
            "ml_direction": ml_direction,
            "event_signal": event_score,
        }

    @staticmethod
    def _build_explanation(
        ticker: str, sub_scores: dict[str, float], conviction: float
    ) -> str:
        dominant = max(sub_scores, key=lambda k: sub_scores[k])
        return (
            f"{ticker}: conviction={conviction:.1f}, "
            f"dominant={dominant}({sub_scores[dominant]:.1f})"
        )

    def _build_card(
        self,
        cs: ConvictionScore,
        signals: list[SmartMoneySignal],
        scan_time: datetime,
    ) -> OpportunityCard:
        """Convert a ConvictionScore into a display-ready OpportunityCard."""
        ticker_signals = [s for s in signals if s.ticker == cs.ticker]

        evidence = self._build_evidence(ticker_signals)
        action = determine_action(cs.score, is_bullish=True)
        suggestion = self._build_suggestion(action, cs)
        risks = self._build_risks(ticker_signals)

        alert_summary = f"{cs.ticker}: conviction {cs.score:.1f}/10 — {action.value}"

        return OpportunityCard(
            ticker=cs.ticker,
            conviction=cs.score,
            action=action,
            alert_summary=alert_summary,
            evidence=evidence,
            suggestion=suggestion,
            risks=risks,
            generated_at=scan_time,
            conviction_score=cs,
        )

    @staticmethod
    def _build_evidence(ticker_signals: list[SmartMoneySignal]) -> list[str]:
        """Build evidence bullet points from smart money signals."""
        if not ticker_signals:
            return ["No specific smart money signals detected."]

        lines: list[str] = []
        for sig in ticker_signals:
            if sig.signal_type == SmartMoneyType.FORM_13D:
                article = "an" if sig.filer_name[0].lower() in "aeiou" else "a"
                lines.append(
                    f"{sig.filer_name} filed a 13D as {article}n investor. "
                    f"Filed {sig.filed_date}."
                )
            elif sig.signal_type == SmartMoneyType.FORM_4:
                tt_lower = sig.transaction_type.lower()
                direction = (
                    "sell"
                    if any(word in tt_lower for word in ("sale", "sell", "disposition"))
                    else "buy"
                )
                value_str = f"${sig.transaction_value:,.0f}"
                lines.append(
                    f"{sig.filer_name} ({sig.insider_role}) {direction} "
                    f"({value_str}). Filed {sig.filed_date}."
                )

        return lines if lines else ["No specific smart money signals detected."]

    @staticmethod
    def _build_suggestion(action: ActionType, cs: ConvictionScore) -> str:
        """Map ActionType to plain-English suggestion."""
        mapping: dict[ActionType, str] = {
            ActionType.BUY: (
                f"Consider initiating or adding to a position in {cs.ticker}. "
                f"Smart money signals are strong (conviction {cs.score:.1f}/10)."
            ),
            ActionType.WATCH: (
                f"Monitor {cs.ticker} closely. Signals are developing but not yet "
                f"strong enough for a committed entry (conviction {cs.score:.1f}/10)."
            ),
            ActionType.HOLD: (
                f"Maintain existing position in {cs.ticker}. "
                f"No new catalysts detected (conviction {cs.score:.1f}/10)."
            ),
            ActionType.SELL: (
                f"Review your position in {cs.ticker}. "
                f"Smart money activity may signal downside risk (conviction {cs.score:.1f}/10)."
            ),
        }
        return mapping.get(action, f"Review {cs.ticker} manually.")

    @staticmethod
    def _build_risks(ticker_signals: list[SmartMoneySignal]) -> list[str]:
        """Build risk bullets. Market risk is always present."""
        risks: list[str] = ["General market risk may affect this opportunity."]

        has_13d = any(s.signal_type == SmartMoneyType.FORM_13D for s in ticker_signals)
        has_form4 = any(s.signal_type == SmartMoneyType.FORM_4 for s in ticker_signals)

        if has_13d:
            risks.append(
                "13D filings may trigger regulatory scrutiny or activist event risk."
            )
        if has_form4:
            risks.append(
                "Insider transaction timing may not align with public market moves."
            )

        return risks
