"""Unit B orchestration — pre-registered insider-cluster falsification (event study).

Wires the domain pieces + reuses the bootstrap harness. Produces a verdict dict
(the report). Build is deliberately thin; integrity lives in the locked gate
(domain/insider_gate.py) and the guards. See spec sec.4 (event-study amendment) + ADR-052.
"""

from __future__ import annotations

from datetime import date
from typing import cast

from application.insider_forward_returns import (
    PriceFn,
    benchmark_return,
    resolve_events,
)
from domain.insider_cluster import detect_clusters
from domain.insider_gate import evaluate_gate
from domain.insider_terciles import assign_terciles, slippage_bps_for_tercile
from domain.ports import InsiderTransactionsPort

BENCHMARK_ETF = {"bottom": "IWC", "mid": "IWM", "top": "IWM"}


class InsiderClusterFalsificationUseCase:
    def __init__(
        self,
        port: InsiderTransactionsPort,
        prices: PriceFn,
        quarters: list[tuple[int, int]],
    ) -> None:
        self._port = port
        self._prices = prices
        self._quarters = quarters

    def run(self) -> dict[str, object]:
        txns = []
        for y, q in self._quarters:
            txns.extend(self._port.get_quarter(y, q))
        events = detect_clusters(txns)
        resolved, unresolved = resolve_events(events, self._prices)

        n_events = len(events)

        adv: dict[str, float] = {
            cast(str, r["ticker"]): cast(float, r["adv"]) for r in resolved
        }
        terciles = assign_terciles(adv)
        bottom = [
            r for r in resolved if terciles.get(cast(str, r["ticker"])) == "bottom"
        ]

        slip = slippage_bps_for_tercile("bottom") / 10000.0
        etf = BENCHMARK_ETF["bottom"]
        gross_abn: list[float] = []
        net_abn: list[float] = []
        n_benchmarked = 0
        for r in sorted(bottom, key=lambda x: cast(date, x["fire_date"])):
            bench = benchmark_return(
                self._prices,
                etf,
                cast(date, r["entry_date"]),
                cast(date, r["exit_date"]),
            )
            if bench is None:
                continue
            n_benchmarked += 1
            g = cast(float, r["fwd_return"]) - bench
            gross_abn.append(g)
            net_abn.append(g - slip)

        # Coverage = bottom-tercile events with a usable abnormal return / all
        # bottom-tercile cluster events. (Price-unresolved events have no ADV so
        # cannot be tercile-assigned; they are tracked separately as n_unresolved.)
        coverage = (n_benchmarked / len(bottom)) if bottom else 0.0

        verdict = evaluate_gate(
            gross_abn=gross_abn,
            net_abn=net_abn,
            n_events=len(bottom),
            coverage=coverage,
        )

        return {
            **verdict,
            "n_cluster_events": n_events,
            "n_resolved": len(resolved),
            "n_unresolved": len(unresolved),
            "n_bottom_tercile": len(bottom),
            "n_benchmarked": n_benchmarked,
            "coverage": coverage,
            "benchmark_etf": etf,
            "tercile_counts": {
                t: sum(1 for v in terciles.values() if v == t)
                for t in ("bottom", "mid", "top")
            },
        }
