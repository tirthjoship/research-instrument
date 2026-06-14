import json
import re


def test_unit_b_row_pending_when_missing(tmp_path):  # type: ignore[no-untyped-def]
    from adapters.visualization.tabs.trust import _unit_b_row

    assert _unit_b_row(str(tmp_path / "nope.json"))["verdict"] == "PENDING"


def test_unit_b_row_reads_verdict(tmp_path):  # type: ignore[no-untyped-def]
    p = tmp_path / "r.json"
    p.write_text(json.dumps({"verdict": "KILL"}))
    from adapters.visualization.tabs.trust import _unit_b_row

    assert _unit_b_row(str(p))["verdict"] == "KILL"


def test_unit_b_row_maps_real_thin_coverage_verdict(tmp_path):  # type: ignore[no-untyped-def]
    # The actual report verdict string -> practical-kill display label (ADR-053).
    p = tmp_path / "r.json"
    p.write_text(json.dumps({"verdict": "INCONCLUSIVE_THIN_COVERAGE"}))
    from adapters.visualization.tabs.trust import _unit_b_row

    assert _unit_b_row(str(p))["verdict"] == "INCONCLUSIVE → practical KILL"


def test_render_no_raise(tmp_path):  # type: ignore[no-untyped-def]
    from adapters.visualization.tabs import trust

    trust.render(
        report_path=str(tmp_path / "nope.json"),
        log_path=str(tmp_path / "nope.jsonl"),
    )


def test_four_rules_count_and_scoreboard():  # type: ignore[no-untyped-def]
    from adapters.visualization.tabs import trust

    assert len(trust._FOUR_RULES) == 4
    assert all(set(r) >= {"title", "body", "example"} for r in trust._FOUR_RULES)
    assert len(trust._SCOREBOARD) >= 1


def test_render_no_raise_full(tmp_path):  # type: ignore[no-untyped-def]
    """Covers trophy grid (3-col), four-rules cards (2x2), and glossary expander."""
    import json as _json

    report = tmp_path / "r.json"
    report.write_text(_json.dumps({"verdict": "INCONCLUSIVE_THIN_COVERAGE"}))
    log = tmp_path / "discipline.jsonl"
    log.write_text(_json.dumps({"as_of": "2026-06-01", "action": "REDUCE"}) + "\n")
    from adapters.visualization.tabs import trust

    trust.render(
        report_path=str(report),
        log_path=str(log),
    )


# ---------------------------------------------------------------------------
# Regression lock: screener-512→0 must NOT appear as EMH/efficiency evidence
# ---------------------------------------------------------------------------


def _collect_trust_text() -> str:
    """Collect all string literals from the trust module that end up rendered."""
    from adapters.visualization.tabs import trust

    # Harvest static text sources: four rules bodies+examples, scoreboard rows,
    # intro card, anti-KPI tile labels/stamps/subs, verdict meanings.
    parts: list[str] = []
    for rule in trust._FOUR_RULES:
        parts.append(rule.get("body", ""))
        parts.append(rule.get("example", ""))
        parts.append(rule.get("title", ""))
    for row in trust._SCOREBOARD:
        parts.extend(row.values())
    for meaning in trust._VERDICT_MEANING.values():
        parts.append(meaning)
    return " ".join(parts)


def test_no_screener_512_as_evidence():  # type: ignore[no-untyped-def]
    """Regression: '512' must not appear adjacent to screener-abstention-as-evidence
    language (ABSTAINED / = EMH / efficient / ranked zero).

    The 512→0 empty screen was a bug, not genuine discipline or EMH evidence.
    Legitimate '512' occurrences (e.g. in ADR paths) are fine; this test checks
    the rendered text surfaces only return-prediction falsification as honesty proof.
    """
    text = _collect_trust_text()
    # Pattern: "512" within 120 chars of screener-abstention evidence words
    if "512" in text:
        window = 120
        idx = 0
        while True:
            pos = text.find("512", idx)
            if pos == -1:
                break
            surrounding = text[max(0, pos - window) : pos + window + len("512")]
            bad_words = re.compile(
                r"\b(ABSTAINED|abstained|ranked zero|=\s*EMH|efficient market|screener cleared)\b",
                re.IGNORECASE,
            )
            assert not bad_words.search(surrounding), (
                f"Found '512' adjacent to screener-abstention-as-evidence language "
                f"in Trust tab text. Surrounding context: {surrounding!r}"
            )
            idx = pos + 1


def test_genuine_falsification_content_survives():  # type: ignore[no-untyped-def]
    """Regression: genuine return-prediction falsification markers must remain.

    These come from real experiments (Rank-IC 0.004, 47.4% directional, 7 hypotheses
    retired) and must never be removed. They are the actual honesty evidence.
    """
    from adapters.visualization.tabs import trust

    # Check _load_rank_ic fallback value is the real measured number
    assert (
        trust._load_rank_ic("nonexistent_path_xyz") == "0.004"
    ), "Fallback Rank-IC must remain '0.004' (ADR-044 measured result)"

    # Check FALSIFIED stamp is still in hero tile logic (the "= EMH" stamp is on
    # directional accuracy tile — legitimate return-prediction falsification)
    text = _collect_trust_text()
    # At least one experiment card must reference return-prediction failure keywords
    assert any(
        kw in text for kw in ["KILL", "FALSIFIED", "INCONCLUSIVE", "predict returns"]
    ), "Genuine falsification verdict language must survive in Trust tab text"

    # The anti-KPI tile renders "FALSIFIED" stamp — verify it appears in render output
    # by checking the module-level constant used in _render_hero_tiles
    # (stamp="FALSIFIED" is hardcoded in the render_tile call)
    import inspect

    source = inspect.getsource(trust._render_hero_tiles)
    assert (
        "FALSIFIED" in source
    ), "Hero tile must still carry FALSIFIED stamp from return-prediction falsification"
    assert (
        "= EMH" in source
    ), "Hero tile must still carry '= EMH' stamp on directional accuracy (47.4% = coin flip)"
