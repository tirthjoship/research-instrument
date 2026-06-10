from click.testing import CliRunner

from application.cli import cli


def test_backtest_insider_clusters_help():
    res = CliRunner().invoke(cli, ["backtest-insider-clusters", "--help"])
    assert res.exit_code == 0
    assert "insider" in res.output.lower()


def test_backtest_insider_clusters_end_to_end_echo(monkeypatch, tmp_path):
    """Full command path with a fake port: the final echo must only reference
    keys the use case actually emits (regression: KeyError 'n_resolved')."""
    from adapters.data.sec_form345_dataset_adapter import SECForm345DatasetAdapter

    monkeypatch.setattr(SECForm345DatasetAdapter, "get_quarter", lambda self, y, q: [])
    res = CliRunner().invoke(
        cli,
        [
            "backtest-insider-clusters",
            "--start-year",
            "2024",
            "--end-year",
            "2024",
            "--report-dir",
            str(tmp_path),
        ],
    )
    assert res.exit_code == 0, res.output
    assert "VERDICT:" in res.output
    assert (tmp_path / "insider_cluster_falsification_2024.json").exists()
