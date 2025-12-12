import json
import pytest, pytest_asyncio, pytest_mock
from pathlib import Path
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

# Target CLI group
from finance_feedback_engine.cli.main import cli


def _mock_engine_for_analyze():
    engine = MagicMock()
    decision = {
        "id": "dec-123",
        "asset_pair": "BTCUSD",
        "action": "BUY",
        "confidence": 85,
    }
    engine.analyze_asset.return_value = decision
    # CLI branches to generate_decision if attribute exists; set it to return same dict
    engine.generate_decision.return_value = decision
    return engine


def test_analyze_command_default_and_with_provider():
    runner = CliRunner()

    with patch("finance_feedback_engine.cli.main.load_tiered_config", return_value={}):
        with patch("finance_feedback_engine.cli.main.FinanceFeedbackEngine") as MockEngine:
            # First run: no provider specified
            MockEngine.return_value = _mock_engine_for_analyze()
            result1 = runner.invoke(cli, ["analyze", "BTCUSD"])
            assert result1.exit_code == 0, result1.output
            # Verify engine constructed once and analyze called with standardized pair
            assert MockEngine.call_count == 1
            # CLI uses generate_decision when attribute exists
            MockEngine.return_value.generate_decision.assert_called_with("BTCUSD")

            # Second run: explicit provider flag should flow into config (checked via call args)
            MockEngine.reset_mock()
            MockEngine.return_value = _mock_engine_for_analyze()
            result2 = runner.invoke(cli, ["analyze", "btc-usd", "--provider", "ensemble"])
            assert result2.exit_code == 0, result2.output
            # Ensure engine was constructed with a config dict having decision_engine.ai_provider
            assert MockEngine.call_count == 1
            passed_config = MockEngine.call_args.args[0]
            assert isinstance(passed_config, dict)
            assert passed_config.get("decision_engine", {}).get("ai_provider") == "ensemble"
            MockEngine.return_value.generate_decision.assert_called_with("BTCUSD")


def test_backtest_command_valid_and_invalid_dates():
    runner = CliRunner()

    fake_engine = MagicMock()
    fake_engine.historical_data_provider = object()
    fake_engine.decision_engine = object()

    # Backtester mock with deterministic output
    class FakeBacktester:
        def __init__(self, **kwargs):
            pass

        def run(self, asset_pair, start_date, end_date, decision_engine):
            return {
                "metrics": {"final_balance": 10500.0},
                "trades": [{"status": "FILLED", "pnl_value": 10.0}],
            }

    def noop_formatter(**kwargs):
        # Avoid Rich-heavy formatting in tests
        pass

    with patch("finance_feedback_engine.cli.main.load_tiered_config", return_value={}):
        with patch("finance_feedback_engine.cli.main.FinanceFeedbackEngine", return_value=fake_engine):
            with patch("finance_feedback_engine.cli.main.Backtester", FakeBacktester):
                with patch(
                    "finance_feedback_engine.cli.backtest_formatter.format_single_asset_backtest",
                    noop_formatter,
                ):
                    # Valid dates
                    ok = runner.invoke(
                        cli,
                        [
                            "backtest",
                            "BTCUSD",
                            "--start",
                            "2024-01-01",
                            "--end",
                            "2024-01-31",
                        ],
                    )
                    assert ok.exit_code == 0, ok.output

                    # Invalid date format
                    bad_format = runner.invoke(
                        cli,
                        [
                            "backtest",
                            "BTCUSD",
                            "--start",
                            "2024/01/01",
                            "--end",
                            "2024-01-31",
                        ],
                    )
                    assert bad_format.exit_code != 0
                    assert "Invalid start date format" in bad_format.output

                    # Invalid range (start >= end)
                    bad_range = runner.invoke(
                        cli,
                        [
                            "backtest",
                            "BTCUSD",
                            "--start",
                            "2024-02-01",
                            "--end",
                            "2024-01-01",
                        ],
                    )
                    assert bad_range.exit_code != 0
                    assert "Invalid date range" in bad_range.output


def test_dashboard_command_with_mocked_aggregator_and_display():
    runner = CliRunner()

    fake_engine = MagicMock()
    fake_engine.trading_platform = object()

    # Aggregator stub that returns predictable data
    class FakeAggregator:
        def __init__(self, platforms):
            self.platforms = platforms

        def get_aggregated_portfolio(self):
            return {"total_value": 12345.67, "platforms": ["mock"]}

    display_called = {"called": False, "data": None}

    def fake_display(data):
        display_called["called"] = True
        display_called["data"] = data

    with patch("finance_feedback_engine.cli.main.load_tiered_config", return_value={}):
        with patch("finance_feedback_engine.cli.main.FinanceFeedbackEngine", return_value=fake_engine):
            with patch("finance_feedback_engine.cli.main.PortfolioDashboardAggregator", FakeAggregator):
                with patch("finance_feedback_engine.cli.main.display_portfolio_dashboard", fake_display):
                    result = runner.invoke(cli, ["dashboard"])
                    assert result.exit_code == 0, result.output
                    assert display_called["called"] is True
                    assert display_called["data"] == {"total_value": 12345.67, "platforms": ["mock"]}


def test_approve_command_yes_and_no():
    runner = CliRunner()

    decision_id = "ABC123"

    # Engine mock for execute_decision
    fake_engine = MagicMock()
    fake_engine.execute_decision.return_value = {"success": True, "message": "ok", "platform": "mock"}

    # Case 1: Reject (no)
    with runner.isolated_filesystem():
        # Create decision file in isolated FS
        Path("data/decisions").mkdir(parents=True, exist_ok=True)
        with open(f"data/decisions/2025-12-12_{decision_id}.json", "w", encoding="utf-8") as f:
            json.dump(
                {
                    "decision_id": decision_id,
                    "asset_pair": "BTCUSD",
                    "action": "BUY",
                    "confidence": 75,
                    "position_size": 0.1,
                    "stop_loss": 2.0,
                    "take_profit": 5.0,
                },
                f,
            )

        with patch("finance_feedback_engine.cli.main.load_tiered_config", return_value={}):
            with patch("finance_feedback_engine.cli.main.FinanceFeedbackEngine", return_value=fake_engine):
                with patch("finance_feedback_engine.cli.main.Prompt.ask", return_value="no"):
                    res_no = runner.invoke(cli, ["approve", decision_id])
                    assert res_no.exit_code == 0, res_no.output
                    approvals_dir = Path("data/approvals")
                    files = list(approvals_dir.glob(f"{decision_id}_rejected.json"))
                    assert len(files) == 1
                    # execute_decision should not be called for rejection
                    fake_engine.execute_decision.assert_not_called()

    # Reset engine call tracking
    fake_engine.reset_mock()

    # Case 2: Approve (yes)
    with runner.isolated_filesystem():
        # Create decision file again for this isolated run
        Path("data/decisions").mkdir(parents=True, exist_ok=True)
        with open(f"data/decisions/2025-12-12_{decision_id}.json", "w", encoding="utf-8") as f:
            json.dump(
                {
                    "decision_id": decision_id,
                    "asset_pair": "BTCUSD",
                    "action": "BUY",
                    "confidence": 75,
                    "position_size": 0.1,
                    "stop_loss": 2.0,
                    "take_profit": 5.0,
                },
                f,
            )

        with patch("finance_feedback_engine.cli.main.load_tiered_config", return_value={}):
            with patch("finance_feedback_engine.cli.main.FinanceFeedbackEngine", return_value=fake_engine):
                with patch("finance_feedback_engine.cli.main.Prompt.ask", return_value="yes"):
                    res_yes = runner.invoke(cli, ["approve", decision_id])
                    assert res_yes.exit_code == 0, res_yes.output
                    approvals_dir = Path("data/approvals")
                    files = list(approvals_dir.glob(f"{decision_id}_approved.json"))
                    assert len(files) == 1
                    fake_engine.execute_decision.assert_called_once_with(decision_id)


def test_balance_command():
    runner = CliRunner()
    fake_engine = MagicMock()
    fake_engine.get_balance.return_value = {"USD": 10000.0, "BTC": 0.5}
    with patch("finance_feedback_engine.cli.main.load_tiered_config", return_value={}):
        with patch("finance_feedback_engine.cli.main.FinanceFeedbackEngine", return_value=fake_engine):
            res = runner.invoke(cli, ["balance"])
            assert res.exit_code == 0, res.output


def test_history_command_basic():
    runner = CliRunner()
    fake_engine = MagicMock()
    fake_engine.get_decision_history.return_value = [
        {"id": "d1", "timestamp": "2025-01-01T00:00:00Z", "asset_pair": "BTCUSD", "action": "BUY", "confidence": 80, "executed": False},
        {"id": "d2", "timestamp": "2025-01-01T01:00:00Z", "asset_pair": "ETHUSD", "action": "SELL", "confidence": 70, "executed": True},
    ]
    with patch("finance_feedback_engine.cli.main.load_tiered_config", return_value={}):
        with patch("finance_feedback_engine.cli.main.FinanceFeedbackEngine", return_value=fake_engine):
            res = runner.invoke(cli, ["history", "--limit", "2"])
            assert res.exit_code == 0, res.output


def test_execute_with_id_calls_engine():
    runner = CliRunner()
    fake_engine = MagicMock()
    fake_engine.execute_decision.return_value = {"success": True, "platform": "mock", "message": "ok"}
    with patch("finance_feedback_engine.cli.main.load_tiered_config", return_value={}):
        with patch("finance_feedback_engine.cli.main.FinanceFeedbackEngine", return_value=fake_engine):
            res = runner.invoke(cli, ["execute", "dec123"])
            assert res.exit_code == 0, res.output
            fake_engine.execute_decision.assert_called_once_with("dec123")


def test_execute_interactive_selection():
    runner = CliRunner()
    fake_engine = MagicMock()
    fake_engine.get_decision_history.return_value = [
        {"id": "pickme", "timestamp": "2025-01-01T00:00:00Z", "asset_pair": "BTCUSD", "action": "BUY", "confidence": 81, "executed": False},
    ]
    fake_engine.execute_decision.return_value = {"success": True, "platform": "mock", "message": "ok"}

    with runner.isolated_filesystem():
        with patch("finance_feedback_engine.cli.main.load_tiered_config", return_value={}):
            with patch("finance_feedback_engine.cli.main.FinanceFeedbackEngine", return_value=fake_engine):
                with patch("finance_feedback_engine.cli.main.console.input", return_value="1"):
                    res = runner.invoke(cli, ["execute"])  # no id triggers selection
                    assert res.exit_code == 0, res.output
                    fake_engine.execute_decision.assert_called_once_with("pickme")


def test_status_command_ok():
    runner = CliRunner()
    fake_engine = MagicMock()
    fake_engine.trading_platform.get_account_info.return_value = {"max_leverage": 5.0}
    with patch("finance_feedback_engine.cli.main.load_tiered_config", return_value={"trading_platform": "mock", "decision_engine": {"ai_provider": "local"}}):
        with patch("finance_feedback_engine.cli.main.FinanceFeedbackEngine", return_value=fake_engine):
            res = runner.invoke(cli, ["status"])
            assert res.exit_code == 0, res.output


def test_wipe_decisions_when_none():
    runner = CliRunner()
    fake_engine = MagicMock()
    fake_engine.decision_store.get_decision_count.return_value = 0
    with patch("finance_feedback_engine.cli.main.load_tiered_config", return_value={}):
        with patch("finance_feedback_engine.cli.main.FinanceFeedbackEngine", return_value=fake_engine):
            res = runner.invoke(cli, ["wipe-decisions"])
            assert res.exit_code == 0, res.output


def test_wipe_decisions_confirmed():
    runner = CliRunner()
    fake_engine = MagicMock()
    fake_engine.decision_store.get_decision_count.return_value = 4
    fake_engine.decision_store.wipe_all_decisions.return_value = 4
    with patch("finance_feedback_engine.cli.main.load_tiered_config", return_value={}):
        with patch("finance_feedback_engine.cli.main.FinanceFeedbackEngine", return_value=fake_engine):
            res = runner.invoke(cli, ["wipe-decisions", "--confirm"])
            assert res.exit_code == 0, res.output
            fake_engine.decision_store.wipe_all_decisions.assert_called_once()


def test_monitor_commands_basic_and_metrics(tmp_path):
    runner = CliRunner()
    # Prepare one metrics file so metrics command has content
    metrics_dir = tmp_path / "data" / "trade_metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    sample = metrics_dir / "trade_001.json"
    sample.write_text(json.dumps({
        "realized_pnl": 12.34,
        "product_id": "BTCUSD",
        "side": "BUY",
        "holding_duration_hours": 1.5,
        "exit_reason": "tp",
        "exit_time": "2025-01-01T01:00:00Z"
    }), encoding="utf-8")

    with runner.isolated_filesystem(temp_dir=tmp_path):
        # start and status should exit cleanly with default config
        with patch("finance_feedback_engine.cli.main.load_tiered_config", return_value={}):
            res_start = runner.invoke(cli, ["monitor", "start"])
            res_status = runner.invoke(cli, ["monitor", "status"])
            assert res_start.exit_code == 0, res_start.output
            assert res_status.exit_code == 0, res_status.output

            res_metrics = runner.invoke(cli, ["monitor", "metrics"])
            assert res_metrics.exit_code == 0, res_metrics.output
