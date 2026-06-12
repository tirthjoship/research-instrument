"""FORBIDDEN_WORDS source scan across the whole cockpit package."""

import inspect

import pytest

from domain.fit import FORBIDDEN_WORDS

MODULES = [
    "adapters.visualization.cockpit.cockpit",
    "adapters.visualization.cockpit._danger",
    "adapters.visualization.cockpit._calls",
    "adapters.visualization.cockpit._retro",
    "adapters.visualization.cockpit._discover",
    "adapters.visualization.cockpit._lookup",
    "adapters.visualization.cockpit.stock_detail",
]


@pytest.mark.parametrize("mod_name", MODULES)
def test_cockpit_module_source_has_no_forbidden_words(mod_name):
    import importlib

    mod = importlib.import_module(mod_name)
    src = inspect.getsource(mod).lower()
    for word in FORBIDDEN_WORDS:
        assert word not in src, f"forbidden word {word!r} in {mod_name}"
