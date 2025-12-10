from click.testing import CliRunner
from finance_feedback_engine.cli.main import cli

def test_analyze_command():
    runner = CliRunner()
    result = runner.invoke(cli, ['analyze', 'ETH-USD'])
    assert result.exit_code == 0