from click.testing import CliRunner

from application.cli import cli


def test_backtest_insider_clusters_help():
    res = CliRunner().invoke(cli, ["backtest-insider-clusters", "--help"])
    assert res.exit_code == 0
    assert "insider" in res.output.lower()
