def test_audit_reports_per_dim_variance_and_neutral_share():
    from application.discrimination_audit_use_case import DiscriminationAuditUseCase

    # candidates: list of dicts with sub_scores per dim
    candidates = [
        {"ticker": "A", "sub_scores": {"smart_money": 8.0, "event_signal": 5.0}},
        {"ticker": "B", "sub_scores": {"smart_money": 3.0, "event_signal": 5.0}},
        {"ticker": "C", "sub_scores": {"smart_money": 6.0, "event_signal": 5.0}},
    ]
    report = DiscriminationAuditUseCase().execute(candidates, neutral=5.0)
    sm = report["smart_money"]
    ev = report["event_signal"]
    assert sm["variance"] > 0  # smart_money discriminates
    assert ev["variance"] == 0.0  # event_signal is dead (all neutral)
    assert ev["neutral_share"] == 1.0  # 100% neutral -> prune candidate
    assert sm["neutral_share"] == 0.0


def test_audit_empty_candidates_returns_empty():
    from application.discrimination_audit_use_case import DiscriminationAuditUseCase

    assert DiscriminationAuditUseCase().execute([], neutral=5.0) == {}
