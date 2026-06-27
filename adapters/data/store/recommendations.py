"""Recommendations mixin for SQLiteStore."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from adapters.data.store._base import connect_and_init
from domain.models import (
    MultiHorizonPrediction,
    RecommendationGrade,
    StockRecommendation,
)


class RecommendationsMixin:
    _db_path: str

    def _conn(self) -> sqlite3.Connection:
        return connect_and_init(self._db_path)

    def save_recommendation(self, rec: StockRecommendation) -> None:
        conn = self._conn()
        conn.execute(
            """INSERT OR REPLACE INTO recommendations
            (symbol, week_start, grade, composite_score,
             predicted_return_2d, predicted_return_5d, predicted_return_10d,
             confidence_2d, confidence_5d, confidence_10d,
             horizon_signals, sentiment_score, divergence_score,
             divergence_type, technical_signal, rsi_14, macd,
             reasoning, sources)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                rec.symbol,
                rec.week_start,
                rec.grade.value,
                rec.composite_score,
                rec.prediction.predicted_return_2d,
                rec.prediction.predicted_return_5d,
                rec.prediction.predicted_return_10d,
                rec.prediction.confidence_2d,
                rec.prediction.confidence_5d,
                rec.prediction.confidence_10d,
                json.dumps(rec.horizon_signals),
                rec.sentiment_score,
                rec.divergence_score,
                rec.divergence_type,
                rec.technical_signal,
                rec.rsi_14,
                rec.macd,
                rec.reasoning,
                json.dumps(rec.sources),
            ),
        )
        conn.commit()

    def get_recommendations(
        self,
        week_start: str | None = None,
        symbol: str | None = None,
    ) -> list[StockRecommendation]:
        query = "SELECT * FROM recommendations WHERE 1=1"
        params: list[Any] = []
        if week_start is not None:
            query += " AND week_start = ?"
            params.append(week_start)
        if symbol is not None:
            query += " AND symbol = ?"
            params.append(symbol)

        conn = self._conn()
        rows = conn.execute(query, params).fetchall()
        return [self._row_to_recommendation(r) for r in rows]

    def _row_to_recommendation(self, r: sqlite3.Row) -> StockRecommendation:
        pred = MultiHorizonPrediction(
            predicted_return_2d=r["predicted_return_2d"],
            predicted_return_5d=r["predicted_return_5d"],
            predicted_return_10d=r["predicted_return_10d"],
            confidence_2d=r["confidence_2d"],
            confidence_5d=r["confidence_5d"],
            confidence_10d=r["confidence_10d"],
        )
        return StockRecommendation(
            symbol=r["symbol"],
            week_start=r["week_start"],
            grade=RecommendationGrade(r["grade"]),
            composite_score=r["composite_score"],
            prediction=pred,
            horizon_signals=json.loads(r["horizon_signals"]),
            reasoning=r["reasoning"],
            sources=json.loads(r["sources"]),
            sentiment_score=r["sentiment_score"],
            divergence_score=r["divergence_score"],
            divergence_type=r["divergence_type"],
            technical_signal=r["technical_signal"],
            rsi_14=r["rsi_14"],
            macd=r["macd"],
        )
