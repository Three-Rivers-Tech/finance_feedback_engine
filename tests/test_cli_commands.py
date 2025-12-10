"""
CLI command tests kept lightweight to avoid external API calls while
still validating key behaviors.
"""

import pytest
from click.testing import CliRunner
from finance_feedback_engine.cli import main as cli_main
from finance_feedback_engine.cli.main import cli


def _patch_cli(monkeypatch, analyze_result=None, analyze_exception=None):
    """Patch CLI dependencies to avoid network calls and capture inputs."""

    captured = {}

    class FakeEngine:
        def __init__(self, config):
            captured["config"] = config

        def analyze_asset(self, asset_pair):
            captured["asset_pair"] = asset_pair
            if analyze_exception:
                raise analyze_exception
            return analyze_result

    monkeypatch.setattr(cli_main, "FinanceFeedbackEngine", FakeEngine)
    monkeypatch.setattr(cli_main, "load_tiered_config", lambda: {"trading_platform": "mock"})

    return captured


def test_analyze_command_success(monkeypatch):
    decision = {
        "id": "dec-123",
        "asset_pair": "ETHUSD",
        "action": "BUY",
        "confidence": 82,
        "reasoning": "Mocked decision for testing",
        "market_data": {"open": 2000.0, "close": 2010.0},
    }

    captured = _patch_cli(monkeypatch, analyze_result=decision)
    runner = CliRunner()
    result = runner.invoke(cli, ["analyze", "ETH-USD"])

    assert result.exit_code == 0
    assert captured["asset_pair"] == "ETHUSD"
    assert "Analyzing ETHUSD" in result.stdout
    assert "Trading Decision Generated" in result.stdout
    # Click's CliRunner strips rich formatting, so check for plain text version
    assert "Action: BUY" in result.stdout or "Action: [bold]BUY" in result.stdout
    assert "Confidence: 82%" in result.stdout
    assert "Decision ID: dec-123" in result.stdout


def test_analyze_command_invalid_symbol(monkeypatch):
    _patch_cli(monkeypatch, analyze_result={"action": "SELL"})
    runner = CliRunner()
    result = runner.invoke(cli, ["analyze", "!!!"])

    assert result.exit_code != 0
    assert "Invalid asset pair" in result.stdout
    assert "Trading Decision Generated" not in result.stdout


def test_analyze_command_network_failure(monkeypatch):
    captured = _patch_cli(monkeypatch, analyze_exception=TimeoutError("Network down"))
    runner = CliRunner()
    result = runner.invoke(cli, ["analyze", "ETH-USD"])

    assert result.exit_code != 0
    assert captured.get("asset_pair") == "ETHUSD"
    assert "Network down" in result.stdout
    assert "Trading Decision Generated" not in result.stdout
