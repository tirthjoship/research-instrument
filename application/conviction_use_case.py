"""ConvictionScoringUseCase — orchestrates smart money signal gathering, scoring,
and OpportunityCard generation.
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable

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
        pinned: set[str] | None = None,
        top_n: int = 15,
    ) -> None:
        self._smart_money = smart_money
        self._tickers = tickers
        self._weights = weights
        self._pinned = pinned or set()
        self._top_n = top_n
        self._engineer = SmartMoneyFeatureEngineer()

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
        sub_scores = self._compute_sub_scores(features, ticker_signals, scan_time)

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
    ) -> dict[str, float]:
        """Compute the six sub-score dimensions."""
        # smart_money sub-score
        sm_raw = (
            features.get("sm_13d_count", 0.0) * 3
            + features.get("sm_insider_cluster", 0.0) * 7
            + features.get("sm_activist_count", 0.0) * 2
        )
        sm_score = min(sm_raw, 10.0)

        # signal_agreement: fraction of 4 key features that are non-zero
        agreement_features = [
            features.get("sm_13d_count", 0.0),
            features.get("sm_form4_buy_count", 0.0),
            features.get("sm_activist_count", 0.0),
            features.get("sm_insider_cluster", 0.0),
        ]
        non_zero = sum(1 for v in agreement_features if v != 0.0)
        signal_agreement = min(non_zero / 4.0 * 10.0, 10.0)

        # freshness: best score from filed_dates
        freshness = 2.0  # default (stale)
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
            "sentiment_momentum": 5.0,  # placeholder — wired in later phase
            "fundamental_basis": 5.0,  # placeholder
            "ml_direction": 5.0,  # placeholder
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
