"""Pre-registered event-study gate + guards (pure). Thresholds LOCKED (spec sec.4-6).

Leg 1 (info, gross):     bootstrap CI lower bound of gross abnormal return > 0.
Leg 2 (tradeable, net):  bootstrap CI lower bound of net abnormal return > 0.
Verdict is 3-state because net = gross - slippage <= gross (slippage > 0):
  net.ci_low > 0                      -> PASS
  gross.ci_low > 0 and net.ci_low<=0  -> INCONCLUSIVE (info real, killed by costs)
  gross.ci_low <= 0                   -> KILL
Guards (override): coverage < 0.80 -> THIN_COVERAGE; n_events < 100 -> THIN_N.
"""

from __future__ import annotations

from application.precision_metrics import moving_block_bootstrap

MIN_COVERAGE = 0.80
MIN_CLUSTER_EVENTS = 100
N_RESAMPLES = 1000
SEED = 42


def _ci_low(series: list[float]) -> float | None:
    result = moving_block_bootstrap(series, n_resamples=N_RESAMPLES, seed=SEED)
    raw = result["ci_low"]
    if raw is None:
        return None
    assert isinstance(raw, (int, float))
    return float(raw)


def evaluate_gate(
    gross_abn: list[float],
    net_abn: list[float],
    n_events: int,
    coverage: float,
) -> dict[str, object]:
    if n_events < MIN_CLUSTER_EVENTS:
        return {"verdict": "INCONCLUSIVE_THIN_N", "n_events": n_events}
    if coverage < MIN_COVERAGE:
        return {"verdict": "INCONCLUSIVE_THIN_COVERAGE", "coverage": coverage}

    gross_ci = _ci_low(gross_abn)
    net_ci = _ci_low(net_abn)
    leg1 = (gross_ci or 0.0) > 0
    leg2 = (net_ci or 0.0) > 0

    if leg2:
        verdict = "PASS"
    elif leg1:
        verdict = "INCONCLUSIVE"
    else:
        verdict = "KILL"

    mean_gross = sum(gross_abn) / len(gross_abn) if gross_abn else 0.0
    mean_net = sum(net_abn) / len(net_abn) if net_abn else 0.0
    return {
        "verdict": verdict,
        "leg1_info_pass": leg1,
        "leg2_tradeable_pass": leg2,
        "mean_gross_abn": mean_gross,
        "mean_net_abn": mean_net,
        "gross_ci_low": gross_ci,
        "net_ci_low": net_ci,
        "n_events": n_events,
        "coverage": coverage,
    }
