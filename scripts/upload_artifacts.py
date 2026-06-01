"""Upload backtest and SHAP report artifacts to AWS S3.

Usage:
    python scripts/upload_artifacts.py --bucket my-ml-portfolio --prefix stock-recommender/
    python scripts/upload_artifacts.py --dry-run  # list files, don't upload
"""

from __future__ import annotations

from pathlib import Path

import click
from loguru import logger

REPORT_DIR = Path("data/reports")
ARTIFACT_PATTERNS = ["backtest_report_*.json", "shap_importance.json"]


def find_artifacts(report_dir: Path = REPORT_DIR) -> list[Path]:
    """Find all uploadable report artifacts."""
    artifacts: list[Path] = []
    for pattern in ARTIFACT_PATTERNS:
        artifacts.extend(sorted(report_dir.glob(pattern)))
    return artifacts


def upload_to_s3(
    artifacts: list[Path],
    bucket: str,
    prefix: str = "",
) -> list[str]:
    """Upload artifacts to S3. Returns list of uploaded S3 keys."""
    import boto3

    s3 = boto3.client("s3")
    uploaded: list[str] = []

    for artifact in artifacts:
        key = f"{prefix}{artifact.name}" if prefix else artifact.name
        logger.info(f"Uploading {artifact.name} → s3://{bucket}/{key}")
        s3.upload_file(
            str(artifact),
            bucket,
            key,
            ExtraArgs={"ContentType": "application/json"},
        )
        uploaded.append(key)

    return uploaded


@click.command()
@click.option("--bucket", required=True, help="S3 bucket name")
@click.option("--prefix", default="stock-recommender/reports/", help="S3 key prefix")
@click.option("--dry-run", is_flag=True, help="List artifacts without uploading")
def main(bucket: str, prefix: str, dry_run: bool) -> None:
    """Upload report artifacts to S3."""
    artifacts = find_artifacts()

    if not artifacts:
        click.echo("No artifacts found in data/reports/")
        return

    click.echo(f"Found {len(artifacts)} artifact(s):")
    for a in artifacts:
        size_kb = a.stat().st_size / 1024
        click.echo(f"  {a.name} ({size_kb:.1f} KB)")

    if dry_run:
        click.echo("Dry run — no uploads performed.")
        return

    uploaded = upload_to_s3(artifacts, bucket, prefix)
    click.echo(f"Uploaded {len(uploaded)} artifact(s) to s3://{bucket}/{prefix}")


if __name__ == "__main__":
    main()
