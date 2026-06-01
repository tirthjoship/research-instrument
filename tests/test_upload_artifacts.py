"""Tests for upload_artifacts — artifact discovery only (S3 mocked)."""

from __future__ import annotations

from pathlib import Path

from scripts.upload_artifacts import find_artifacts


def test_find_artifacts_finds_backtest_reports(tmp_path: Path) -> None:
    (tmp_path / "backtest_report_20260529_171152.json").write_text("{}")
    (tmp_path / "shap_importance.json").write_text("{}")
    (tmp_path / "unrelated.txt").write_text("nope")

    artifacts = find_artifacts(report_dir=tmp_path)
    names = [a.name for a in artifacts]
    assert "backtest_report_20260529_171152.json" in names
    assert "shap_importance.json" in names
    assert "unrelated.txt" not in names


def test_find_artifacts_empty_dir(tmp_path: Path) -> None:
    artifacts = find_artifacts(report_dir=tmp_path)
    assert artifacts == []
