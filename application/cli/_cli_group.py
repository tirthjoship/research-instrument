"""Click group definition — imported by all command submodules."""

from __future__ import annotations

import click


@click.group()
def cli() -> None:
    """Multi-modal stock recommender CLI."""
    from application.dotenv_loader import load_dotenv

    load_dotenv()
