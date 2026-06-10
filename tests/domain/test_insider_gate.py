from domain.insider_gate import evaluate_gate


def _pos(n=200):
    return [0.05 + (0.001 if i % 2 else -0.001) for i in range(n)]


def _neg(n=200):
    return [-x for x in _pos(n)]


def test_pass_when_net_ci_positive():
    v = evaluate_gate(gross_abn=_pos(), net_abn=_pos(), n_events=500, coverage=0.95)
    assert v["verdict"] == "PASS"


def test_kill_when_gross_ci_not_positive():
    v = evaluate_gate(gross_abn=_neg(), net_abn=_neg(), n_events=500, coverage=0.95)
    assert v["verdict"] == "KILL"


def test_inconclusive_gross_positive_net_not():
    v = evaluate_gate(gross_abn=_pos(), net_abn=_neg(), n_events=500, coverage=0.95)
    assert v["verdict"] == "INCONCLUSIVE"


def test_thin_coverage_overrides_everything():
    v = evaluate_gate(gross_abn=_pos(), net_abn=_pos(), n_events=500, coverage=0.50)
    assert v["verdict"] == "INCONCLUSIVE_THIN_COVERAGE"


def test_thin_n_overrides_legs():
    v = evaluate_gate(gross_abn=_pos(), net_abn=_pos(), n_events=42, coverage=0.95)
    assert v["verdict"] == "INCONCLUSIVE_THIN_N"
