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
        # records: events with a trailing ADV (tercile-assignable); no_price:
        # events with no bar at/after the fire date (delisted-before-fire / unmapped).
        records, no_price = resolve_events(events, self._prices)

        n_events = len(events)

        adv: dict[str, float] = {
            cast(str, r["ticker"]): cast(float, r["adv"]) for r in records
        }
        terciles = assign_terciles(adv)
        bottom = [
            r for r in records if terciles.get(cast(str, r["ticker"])) == "bottom"
        ]

        slip = slippage_bps_for_tercile("bottom") / 10000.0
        etf = BENCHMARK_ETF["bottom"]
        gross_abn: list[float] = []
        net_abn: list[float] = []
        for r in sorted(bottom, key=lambda x: cast(date, x["fire_date"])):
            # An ADV-only (delisted mid-window) record has no forward return; it
            # stays in the denominator (below) but contributes no abnormal return.
            if r["fwd_return"] is None:
                continue
            bench = benchmark_return(
                self._prices,
                etf,
                cast(date, r["entry_date"]),
                cast(date, r["exit_date"]),
            )
            if bench is None:
                continue
            g = cast(float, r["fwd_return"]) - bench
            gross_abn.append(g)
            net_abn.append(g - slip)

        n_benchmarked = len(gross_abn)

        # C1 fix (spec sec.5): the coverage denominator is ALL qualifying
        # bottom-tercile events, INCLUDING delisted/unpriceable ones — not just the
        # already-resolved set. ADV-only records are in `bottom`; no-price events
        # have no ADV/tercile, so they are conservatively binned into the bottom
        # (least-liquid) denominator. Residual survivorship therefore DRIVES
        # COVERAGE DOWN toward INCONCLUSIVE_THIN_COVERAGE instead of vanishing.
        bottom_population = len(bottom) + len(no_price)
        coverage = (n_benchmarked / bottom_population) if bottom_population else 0.0

        verdict = evaluate_gate(
            gross_abn=gross_abn,
            net_abn=net_abn,
            n_events=bottom_population,
            coverage=coverage,
        )

        # Report-only diagnostic: fraction of ALL cluster events with a usable
        # forward abnormal return (across all terciles). Complements the locked
        # bottom-tercile coverage guard above.
        n_with_fwd = sum(1 for r in records if r["fwd_return"] is not None)
        overall_resolution_rate = (n_with_fwd / n_events) if n_events else 0.0

        return {
            **verdict,
            "n_cluster_events": n_events,
            "n_records_with_adv": len(records),
            "n_no_price": len(no_price),
            "overall_resolution_rate": overall_resolution_rate,
            "n_bottom_population": bottom_population,
            "n_bottom_benchmarked": n_benchmarked,
            "coverage": coverage,
            "benchmark_etf": etf,
            "tercile_counts": {
                t: sum(1 for v in terciles.values() if v == t)
                for t in ("bottom", "mid", "top")
            },
        }
