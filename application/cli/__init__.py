"""application.cli package — multi-modal stock recommender CLI.

The `cli` group is defined in `_cli_group`; each `*_commands` module registers
its commands against that group on import.  This __init__ re-exports everything
the test suite imports from `application.cli` so existing `import application.cli`
usage keeps working without changes.
"""

from __future__ import annotations

# 4. Re-export load_price_series at module level so tests can monkeypatch it
#    via `monkeypatch.setattr("application.cli.load_price_series", ...)`.
from application.price_returns import load_price_series  # noqa: F401

# 5. Import all command modules to register their @cli.command decorators.
#    Order does not matter for registration; alphabetical for readability.
from . import (  # noqa: F401
    backtest_commands,
    brief_commands,
    corroboration_commands,
    data_commands,
    ml_commands,
    portfolio_commands,
    scan_commands,
    screen_commands,
    validation_commands,
)

# 1. Re-export the cli group (the primary public API).
from ._cli_group import cli

# 2. Re-export shared helpers that tests import directly from application.cli
from ._deps import (
    MACRO_HISTORY_PATH,
    _build_dependencies,
    _build_evidence_screen,
    _cfg_cmin,
    _cfg_dmin,
    _CombinedAttention,
    _get_backtest_universe,
    _get_company_name,
    _get_ticker_universe,
    _is_backfill_due,
    _load_spine_tickers,
    _load_wiki_map,
    _load_wiki_map_merged,
    _print_report,
    _risk_macro_facts,
)

# 3. Re-export brief helpers that tests monkeypatch on the module
from .brief_commands import _build_weekly_brief, _prefetch_cited_cases, weekly_brief

__all__ = [
    "cli",
    "MACRO_HISTORY_PATH",
    "_build_dependencies",
    "_build_evidence_screen",
    "_build_weekly_brief",
    "_cfg_cmin",
    "_cfg_dmin",
    "_CombinedAttention",
    "_get_backtest_universe",
    "_get_company_name",
    "_get_ticker_universe",
    "_is_backfill_due",
    "_load_spine_tickers",
    "_load_wiki_map",
    "_load_wiki_map_merged",
    "_prefetch_cited_cases",
    "_print_report",
    "_risk_macro_facts",
    "load_price_series",
    "weekly_brief",
]
