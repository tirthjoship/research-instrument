# tests/test_hybrid_universe.py
from pathlib import Path

import yaml


def test_themes_yaml_has_space_and_memory():
    data = yaml.safe_load(Path("config/universe/themes.yaml").read_text())
    themes = data["themes"]
    assert "ASTS" in themes["space"]
    assert "MU" in themes["memory_storage"]
