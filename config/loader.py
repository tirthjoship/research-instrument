"""Load market configuration from YAML files."""

from pathlib import Path
from typing import Any

import yaml


def load_market_config(market: str = "us") -> dict[str, Any]:
    """Load market configuration from config/markets/{market}.yaml."""
    config_dir = Path(__file__).parent / "markets"
    config_path = config_dir / f"{market}.yaml"
    if not config_path.exists():
        msg = f"Market config not found: {config_path}"
        raise FileNotFoundError(msg)
    with open(config_path) as f:
        config: dict[str, Any] = yaml.safe_load(f)
    return config
