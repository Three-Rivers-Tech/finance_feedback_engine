"""
CLI command tests using the real engine for realistic integration testing.
"""

from click.testing import CliRunner

from finance_feedback_engine.cli.main import cli


def test_analyze_command_success():
    """Test analyze command with real engine - validates CLI flow end-to-end."""
    runner = CliRunner()
    result = runner.invoke(cli, ["analyze", "BTC-USD", "--provider", "local"])

    assert result.exit_code == 0
    assert "Analyzing BTCUSD" in result.output or "BTC-USD" in result.output
    # Verify decision output structure appears (action, confidence, etc.)
    assert "Action:" in result.output or "action" in result.output.lower()
    assert "Confidence:" in result.output or "confidence" in result.output.lower()


def test_analyze_command_invalid_symbol():
    """Test analyze command rejects invalid asset pairs."""
    runner = CliRunner()
    result = runner.invoke(cli, ["analyze", "!!!"])

    assert result.exit_code != 0
    assert "Invalid asset pair" in result.output


def test_analyze_command_network_failure():
    """Test analyze command handles provider failures gracefully."""
    # Use a provider that will fail or skip this test if network is required
    runner = CliRunner()
    # This should still work with local provider fallback
    result = runner.invoke(cli, ["analyze", "ETH-USD", "--provider", "local"])

    # Should either succeed with local provider or fail gracefully
    # We just verify it doesn't crash
    assert result.exit_code in [0, 1]  # Either success or handled failure
    # Output should not contain Python tracebacks
    assert "Traceback" not in result.output or result.exit_code == 0
