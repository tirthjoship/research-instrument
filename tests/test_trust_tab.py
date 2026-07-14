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


def test_header_html_uses_ri_classes():  # type: ignore[no-untyped-def]
    from adapters.visualization.tabs.trust import _header_html

    html = _header_html()
    assert 'class="ri-h1"' in html
    assert 'class="ri-sub"' in html
    assert "Trust" in html
    assert "receipts behind the app" in html


def test_lead_banner_html_uses_ri_card_not_ws_card():  # type: ignore[no-untyped-def]
    from adapters.visualization.tabs.trust import _lead_banner_html

    html = _lead_banner_html(n_total=7, n_dead=5, n_open=2)
    assert "ws-card" not in html
    assert "var(--ri-card)" in html
    assert "7" in html and "5" in html and "2" in html
    assert "Screener, Risk, and Stock Analysis" in html


def test_under_the_hood_is_stamp_tiles_not_expanders():  # type: ignore[no-untyped-def]
    from adapters.visualization.tabs import trust

    assert len(trust._UNDER_THE_HOOD) == 4
    for label, number, sub in trust._UNDER_THE_HOOD:
        assert label and number and sub
    numbers = {n for _, n, _ in trust._UNDER_THE_HOOD}
    assert numbers == {"22", "500", "52", "4"}

    import inspect

    source = inspect.getsource(trust._render_under_the_hood)
    assert "render_tile(" in source
    assert "st.expander" not in source


def test_dead_architecture_stats_has_two_tiles_not_three():  # type: ignore[no-untyped-def]
    """Hero tiles relocated + retired-count tile dropped (redundant with lead banner)."""
    import inspect

    from adapters.visualization.tabs import trust

    assert not hasattr(trust, "_render_hero_tiles"), (
        "_render_hero_tiles should be renamed to _render_dead_architecture_stats "
        "once relocated out of the top-of-page hero position"
    )
    source = inspect.getsource(trust._render_dead_architecture_stats)
    assert "st.columns(2)" in source
    assert source.count("render_tile(") == 2
    assert "label=retired_label" not in source
    assert "FALSIFIED" in source
    assert "= EMH" in source


def test_scoreboard_rows_carry_group_tag():  # type: ignore[no-untyped-def]
    from adapters.visualization.tabs import trust

    groups = [r["group"] for r in trust._SCOREBOARD]
    assert groups == [
        "external",
        "external",
        "external",
        "external",
        "methodology",
        "methodology",
    ]
    assert trust._unit_b_row("nonexistent.json")["group"] == "methodology"


def test_verdict_rule_color():  # type: ignore[no-untyped-def]
    from adapters.visualization.tabs.trust import _verdict_rule_color

    assert _verdict_rule_color("KILL") == "#DC2626"
    assert _verdict_rule_color("INCONCLUSIVE → practical KILL") == "#DC2626"
    assert _verdict_rule_color("INCONCLUSIVE") == "#CA8A04"
    assert _verdict_rule_color("PENDING") == "#64748B"


def test_scoreboard_strip_html_has_legend_and_seven_blocks():  # type: ignore[no-untyped-def]
    from adapters.visualization.tabs.trust import (
        _SCOREBOARD,
        _scoreboard_strip_html,
        _unit_b_row,
    )

    rows = _SCOREBOARD + [_unit_b_row("nonexistent.json")]
    html = _scoreboard_strip_html(rows)
    assert "KILL" in html and "dead, will never trade" in html
    assert "INCONCLUSIVE" in html and "unproven, resolving" in html
    assert "PENDING" in html and "still accruing evidence" in html
    assert html.count("#DC2626") >= 4  # legend swatch + 4 KILL blocks
    # No leftover placeholder glyphs inside the blocks themselves
    assert ">?</div>" not in html
    assert ">•</div>" not in html


def test_render_trophy_grid_groups_rows():  # type: ignore[no-untyped-def]
    import inspect

    from adapters.visualization.tabs import trust

    source = inspect.getsource(trust._render_trophy_grid)
    assert "External signals — all killed" in source
    assert "Our own methodology — resolving" in source
    assert "_scoreboard_strip_html(" in source


def test_decision_tree_html_names_each_experiment_on_its_branch():  # type: ignore[no-untyped-def]
    """Per-experiment branches, not just aggregate counts (2026-07-14 revision:
    the first version only repeated the scoreboard-strip counts in tree form —
    the ask was to show *which* experiment landed on each branch)."""
    from adapters.visualization.tabs.trust import (
        _SCOREBOARD,
        _decision_tree_html,
        _unit_b_row,
    )

    rows = _SCOREBOARD + [_unit_b_row("nonexistent.json")]
    html = _decision_tree_html(rows)
    assert "Pre-registration" in html
    assert "point-in-time" in html
    assert "net of" in html and "trading costs" in html

    # The 4 external-signal hypotheses must be named on the KILL branch.
    for name in [
        "Community conviction",
        "Conviction sub-dimensions",
        "Sentiment/price divergence",
        "Momentum-exit timing",
    ]:
        assert name in html
    # The 2 methodology hypotheses must be named on the INCONCLUSIVE branch.
    assert "Evidence-screen top decile" in html
    assert "Trend-following sleeve" in html
    # Insider clusters defaults to PENDING when no report file exists.
    assert "Insider clusters" in html

    assert "would advance to a live signal" in html
    # No two branches should show the bare, unlabelled digit pair "0/7" —
    # a currently-empty branch and the permanently-empty branch must read
    # differently, or a skimming viewer sees two "0/7"s and assumes a bug.
    assert html.count("0/7") <= 1


def test_decision_tree_html_wrapped_in_card():  # type: ignore[no-untyped-def]
    """The tree must sit inside a bordered card like the rest of the page,
    not float unstyled against the background (looked "abrupt" otherwise)."""
    from adapters.visualization.tabs.trust import (
        _SCOREBOARD,
        _decision_tree_html,
        _unit_b_row,
    )

    rows = _SCOREBOARD + [_unit_b_row("nonexistent.json")]
    html = _decision_tree_html(rows)
    assert "var(--ri-card)" in html
    assert "var(--ri-line)" in html


def test_render_trophy_grid_includes_decision_tree():  # type: ignore[no-untyped-def]
    import inspect

    from adapters.visualization.tabs import trust

    source = inspect.getsource(trust._render_trophy_grid)
    assert "_decision_tree_html(" in source


def test_pipeline_diagram_html_has_four_steps_in_order():  # type: ignore[no-untyped-def]
    from adapters.visualization.tabs.trust import _pipeline_diagram_html

    html = _pipeline_diagram_html()
    for step in ["Pre-registration", "Point-in-time gate", "Cost model", "Verdict"]:
        assert step in html
    assert html.index("Pre-registration") < html.index("Point-in-time gate")
    assert html.index("Point-in-time gate") < html.index("Cost model")
    assert html.index("Cost model") < html.index("Verdict")


def test_four_rules_cards_migrated_off_ws_card():  # type: ignore[no-untyped-def]
    import inspect

    from adapters.visualization.tabs import trust

    source = inspect.getsource(trust._render_four_rules)
    assert "ws-card" not in source
    assert "var(--ri-card)" in source
    assert "_pipeline_diagram_html(" in source


def test_four_rules_body_collapsed_to_trim_page_length():  # type: ignore[no-untyped-def]
    """2026-07-14: page was too long for a fast skim — collapse the pipeline
    diagram + rule cards behind one click, keep the section header visible."""
    import inspect

    from adapters.visualization.tabs import trust

    source = inspect.getsource(trust._render_four_rules)
    assert "st.expander(" in source
    # The #tr-honest anchor id must stay on something always visible (other
    # tabs' nav chips link here), not buried inside the collapsed body.
    assert 'id="tr-honest"' in source


def test_exhibits_render_side_by_side_not_nested():  # type: ignore[no-untyped-def]
    import inspect

    from adapters.visualization.tabs import trust

    source = inspect.getsource(trust._render_dead_architecture_details)
    assert "st.columns(2)" in source
    assert "_render_ablation_exhibit(" in source
    assert "_render_shap_exhibit(" in source
    # Exactly one expander at this level — no nested sub-expanders
    assert source.count("st.expander(") == 1


def test_dead_architecture_stats_folded_into_details_expander():  # type: ignore[no-untyped-def]
    """2026-07-14 trim: the 2 stat tiles used to sit always-visible before the
    exhibits expander; folded inside it so less is always-on-screen."""
    import inspect

    from adapters.visualization.tabs import trust

    source = inspect.getsource(trust._render_dead_architecture_details)
    assert "_render_dead_architecture_stats(" in source

    render_source = inspect.getsource(trust.render)
    assert "_render_dead_architecture_stats()" not in render_source


def test_nav_relabeled_dead_architecture_and_anchors_preserved():  # type: ignore[no-untyped-def]
    from adapters.visualization.tabs.trust import _trust_nav

    html = _trust_nav()
    assert "Dead architecture" in html
    assert "Deep data" not in html
    for anchor in ["#tr-hood", "#tr-tested", "#tr-honest", "#tr-live", "#tr-raw"]:
        assert anchor in html, f"nav must keep {anchor} — other tabs link to it"


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
    # by checking the module-level constant used in _render_dead_architecture_stats
    # (stamp="FALSIFIED" is hardcoded in the render_tile call; this function was
    # renamed from _render_hero_tiles when it was relocated into "Dead architecture")
    import inspect

    source = inspect.getsource(trust._render_dead_architecture_stats)
    assert (
        "FALSIFIED" in source
    ), "Hero tile must still carry FALSIFIED stamp from return-prediction falsification"
    assert (
        "= EMH" in source
    ), "Hero tile must still carry '= EMH' stamp on directional accuracy (47.4% = coin flip)"


# build_screen_history_html and build_zone3_html tests relocated to
# tests/test_research_candidates_tab.py on 2026-07-13 — the table now
# renders on the screener tab itself, not here (see trust-tab-redesign spec).


# ---------------------------------------------------------------------------
# 2026-07-14: info-tooltip icons on the exhibit charts, so a reader unfamiliar
# with SHAP/ablation/p-values can follow what the charts actually mean.
# ---------------------------------------------------------------------------


def test_exhibit_glossary_terms_defined():  # type: ignore[no-untyped-def]
    from adapters.visualization.components.glossary import GLOSSARY

    for term in ["Ablation study", "SHAP value", "Statistical significance (p-value)"]:
        assert term in GLOSSARY, f"{term!r} must be a defined glossary entry"
        assert GLOSSARY[term], f"{term!r} definition must not be empty"


def test_ablation_exhibit_has_info_tooltips():  # type: ignore[no-untyped-def]
    import inspect

    from adapters.visualization.tabs import trust

    heading_source = inspect.getsource(trust._render_dead_architecture_details)
    assert "tooltip('Ablation study'" in heading_source or (
        'tooltip("Ablation study"' in heading_source
    )

    body_source = inspect.getsource(trust._render_ablation_exhibit)
    assert "tooltip('Statistical significance (p-value)'" in body_source or (
        'tooltip("Statistical significance (p-value)"' in body_source
    )


def test_shap_exhibit_has_info_tooltip():  # type: ignore[no-untyped-def]
    import inspect

    from adapters.visualization.tabs import trust

    heading_source = inspect.getsource(trust._render_dead_architecture_details)
    assert "tooltip('SHAP value'" in heading_source or (
        'tooltip("SHAP value"' in heading_source
    )
