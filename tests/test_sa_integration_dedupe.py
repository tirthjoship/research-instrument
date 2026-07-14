"""Phase-5 Task 1: dedupe TDD — verify render() post-top plan has no duplicate sections.

These tests assert that the pure helper `_post_top_render_plan()` returns ONLY
the section names that are NOT already rendered inside the group panels
(corroboration). The eight deep-dive sections (valuation, growth, performance,
health, ownership, sentiment, supply_chain, analyst_panel) now live inside the
sa-* group shells rendered by build_top_html, so they must NOT appear in the
post-top plan. Buzz headlines live in the Buzz panel — not a separate block.
"""

from __future__ import annotations

from adapters.visualization.tabs.stock_analysis import compose


def test_post_top_plan_has_no_duplicated_sections() -> None:
    """The post-top render plan must NOT contain any section that lives in a group panel."""
    plan = compose._post_top_render_plan()
    # the deep-dive sections now live inside the group panels (build_top_html); they must NOT be re-rendered flat
    for dup in (
        "valuation",
        "growth",
        "performance",
        "health",
        "ownership",
        "sentiment",
        "supply_chain",
        "analyst_panel",
    ):
        assert dup not in plan, f"{dup} is rendered twice (flat + in group)"


def test_post_top_plan_keeps_corroboration_only() -> None:
    """The post-top render plan must include corroboration (not in groups)."""
    plan = compose._post_top_render_plan()
    assert plan == ["corroboration"]
    assert "news_context" not in plan
