"""Smoke tests for the surviving cockpit-era tabs (risk + trust)."""

from __future__ import annotations


def test_risk_importable() -> None:
    from adapters.visualization.tabs.risk import render

    assert callable(render)


def test_trust_importable() -> None:
    from adapters.visualization.tabs.trust import render

    assert callable(render)


def test_deleted_tabs_absent() -> None:
    """Falsified-era tabs must not be importable — they were deleted (ADR-044)."""
    import importlib

    for module in (
        "adapters.visualization.tabs.command_center",
        "adapters.visualization.tabs.market_pulse",
        "adapters.visualization.tabs.model_confidence",
    ):
        try:
            importlib.import_module(module)
            raise AssertionError(f"{module} should not exist")
        except ModuleNotFoundError:
            pass
