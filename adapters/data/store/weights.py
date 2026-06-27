"""Weight adjustments and learned rules mixin for SQLiteStore."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from adapters.data.store._base import connect_and_init
from domain.pattern_memory import LearnedRule, WeightAdjustment


class WeightsMixin:
    _db_path: str

    def _conn(self) -> sqlite3.Connection:
        return connect_and_init(self._db_path)

    def save_weight_adjustment(self, adj: WeightAdjustment) -> None:
        conn = self._conn()
        conn.execute(
            """INSERT INTO weight_history
            (dimension, old_weight, new_weight, reason, adjusted_date)
            VALUES (?, ?, ?, ?, ?)""",
            (
                adj.dimension,
                adj.old_weight,
                adj.new_weight,
                adj.reason,
                adj.adjusted_date,
            ),
        )
        conn.commit()

    def get_weight_history(
        self, dimension: str | None = None
    ) -> list[WeightAdjustment]:
        query = "SELECT * FROM weight_history WHERE 1=1"
        params: list[Any] = []
        if dimension is not None:
            query += " AND dimension = ?"
            params.append(dimension)
        query += " ORDER BY adjusted_date DESC"
        conn = self._conn()
        rows = conn.execute(query, params).fetchall()
        return [
            WeightAdjustment(
                dimension=r["dimension"],
                old_weight=r["old_weight"],
                new_weight=r["new_weight"],
                reason=r["reason"] or "",
                adjusted_date=r["adjusted_date"],
            )
            for r in rows
        ]

    def save_learned_rule(self, rule: LearnedRule) -> None:
        conn = self._conn()
        conn.execute(
            """INSERT OR REPLACE INTO learned_rules
            (rule_id, description, signal_combination, sector, action,
             confidence, supporting_outcomes, learned_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                rule.rule_id,
                rule.description,
                json.dumps(list(rule.signal_combination)),
                rule.sector,
                rule.action,
                rule.confidence,
                rule.supporting_outcomes,
                rule.learned_date,
            ),
        )
        conn.commit()

    def get_learned_rules(self) -> list[LearnedRule]:
        conn = self._conn()
        rows = conn.execute("SELECT * FROM learned_rules").fetchall()
        return [
            LearnedRule(
                rule_id=r["rule_id"],
                description=r["description"],
                signal_combination=tuple(json.loads(r["signal_combination"])),
                sector=r["sector"],
                action=r["action"],
                confidence=r["confidence"],
                supporting_outcomes=r["supporting_outcomes"],
                learned_date=r["learned_date"],
            )
            for r in rows
        ]
