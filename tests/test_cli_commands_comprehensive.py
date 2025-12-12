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


def test_portfolio_backtest_command():
    """Test portfolio-backtest with minimal mocking."""
    runner = CliRunner()
    fake_engine = MagicMock()
    fake_engine.historical_data_provider = MagicMock()
    fake_engine.decision_engine = MagicMock()

    class FakePortfolioBacktester:
        def __init__(self, *args, **kwargs):
            pass
        def run_backtest(self, **kwargs):
            return {"portfolio_metrics": {"final_balance": 11000.0}, "asset_results": {}}

    with patch("finance_feedback_engine.cli.main.load_tiered_config", return_value={}):
        with patch("finance_feedback_engine.cli.main.FinanceFeedbackEngine", return_value=fake_engine):
            with patch("finance_feedback_engine.backtesting.portfolio_backtester.PortfolioBacktester", FakePortfolioBacktester):
                res = runner.invoke(cli, ["portfolio-backtest", "BTCUSD", "ETHUSD", "--start", "2024-01-01", "--end", "2024-01-31"])
                assert res.exit_code == 0, res.output


def test_walk_forward_command():
    """Test walk-forward analysis with mocked optimizer."""
    runner = CliRunner()
    fake_engine = MagicMock()
    fake_engine.historical_data_provider = MagicMock()
    fake_engine.decision_engine = MagicMock()

    class FakeWalkForward:
        def __init__(self, *args, **kwargs):
            pass
        def run(self, *args, **kwargs):
            return {"train_metrics": {"win_rate": 0.6}, "test_metrics": {"win_rate": 0.55}}

    with patch("finance_feedback_engine.cli.main.load_tiered_config", return_value={}):
        with patch("finance_feedback_engine.cli.main.FinanceFeedbackEngine", return_value=fake_engine):
            with patch("finance_feedback_engine.cli.main.WalkForwardOptimizer", FakeWalkForward):
                res = runner.invoke(cli, ["walk-forward", "BTCUSD", "--start-date", "2024-01-01", "--end-date", "2024-06-01"])
                assert res.exit_code == 0, res.output


def test_monte_carlo_command():
    """Test monte-carlo simulation with mocked simulator."""
    runner = CliRunner()
    fake_engine = MagicMock()
    fake_engine.historical_data_provider = MagicMock()
    fake_engine.decision_engine = MagicMock()

    class FakeMonteCarlo:
        def __init__(self, *args, **kwargs):
            pass
        def run(self, *args, **kwargs):
            return {"mean_final_balance": 10500.0, "std_final_balance": 200.0}

    with patch("finance_feedback_engine.cli.main.load_tiered_config", return_value={}):
        with patch("finance_feedback_engine.cli.main.FinanceFeedbackEngine", return_value=fake_engine):
            with patch("finance_feedback_engine.cli.main.MonteCarloSimulator", FakeMonteCarlo):
                res = runner.invoke(cli, ["monte-carlo", "BTCUSD", "--start-date", "2024-01-01", "--end-date", "2024-01-31"])
                assert res.exit_code == 0, res.output


def test_learning_report_command():
    """Test learning-report with mocked memory engine."""
    runner = CliRunner()
    fake_engine = MagicMock()
    fake_memory = MagicMock()
    fake_memory.generate_learning_validation_metrics.return_value = {
        "total_trades_analyzed": 100,
        "sample_efficiency": {"achieved_threshold": True, "trades_to_60pct_win_rate": 50, "learning_speed_per_100_trades": 0.15},
        "cumulative_regret": {"cumulative_regret": 10.0, "optimal_provider": "ensemble", "optimal_avg_pnl": 5.0, "avg_regret_per_trade": 0.1},
        "concept_drift": {"drift_severity": "LOW", "drift_score": 0.02, "window_win_rates": [0.6, 0.62]},
        "thompson_sampling": {"exploration_rate": 0.2, "exploitation_convergence": 0.8, "dominant_provider": "local", "provider_distribution": {}},
        "learning_curve": {
            "first_100_trades": {"win_rate": 0.5, "avg_pnl": 1.0},
            "last_100_trades": {"win_rate": 0.6, "avg_pnl": 2.0},
            "win_rate_improvement_pct": 20.0,
            "pnl_improvement_pct": 100.0,
            "learning_detected": True
        },
        "research_methods": {"sample_efficiency": "DQN paper"}
    }
    fake_engine.memory_engine = fake_memory

    with patch("finance_feedback_engine.cli.main.load_tiered_config", return_value={}):
        with patch("finance_feedback_engine.cli.main.FinanceFeedbackEngine", return_value=fake_engine):
            res = runner.invoke(cli, ["learning-report"])
            assert res.exit_code == 0, res.output


def test_prune_memory_command_no_confirm():
    """Test prune-memory when no pruning is needed."""
    runner = CliRunner()
    fake_engine = MagicMock()
    fake_memory = MagicMock()
    fake_memory.trade_outcomes = [{"pnl": 1.0}] * 50  # only 50 trades
    fake_engine.memory_engine = fake_memory

    with patch("finance_feedback_engine.cli.main.load_tiered_config", return_value={}):
        with patch("finance_feedback_engine.cli.main.FinanceFeedbackEngine", return_value=fake_engine):
            res = runner.invoke(cli, ["prune-memory", "--keep-recent", "1000"])
            assert res.exit_code == 0, res.output


def test_prune_memory_command_with_pruning():
    """Test prune-memory when pruning is needed and confirmed."""
    runner = CliRunner()
    fake_engine = MagicMock()
    fake_memory = MagicMock()
    fake_memory.trade_outcomes = [{"pnl": 1.0}] * 2000
    fake_memory.save = MagicMock()
    fake_engine.memory_engine = fake_memory

    with patch("finance_feedback_engine.cli.main.load_tiered_config", return_value={}):
        with patch("finance_feedback_engine.cli.main.FinanceFeedbackEngine", return_value=fake_engine):
            with patch("finance_feedback_engine.cli.main.Prompt.ask", return_value="yes"):
                res = runner.invoke(cli, ["prune-memory", "--keep-recent", "500"])
                assert res.exit_code == 0, res.output
                assert len(fake_memory.trade_outcomes) == 500


def test_retrain_meta_learner_no_history():
    """Test retrain-meta-learner when no trade history exists."""
    runner = CliRunner()
    fake_engine = MagicMock()
    fake_memory = MagicMock()
    fake_memory.trade_outcomes = None  # No history
    fake_engine.memory_engine = fake_memory

    with patch("finance_feedback_engine.cli.main.load_tiered_config", return_value={}):
        with patch("finance_feedback_engine.cli.main.FinanceFeedbackEngine", return_value=fake_engine):
            res = runner.invoke(cli, ["retrain-meta-learner"])
            assert res.exit_code == 0, res.output


def test_retrain_meta_learner_force():
    """Test retrain-meta-learner with --force flag."""
    runner = CliRunner()
    fake_engine = MagicMock()
    fake_memory = MagicMock()
    fake_memory.trade_outcomes = [{"pnl": 1.0}] * 30
    fake_memory.get_strategy_performance_summary.return_value = {
        "stacking": {"win_rate": 60.0, "total_trades": 30}
    }
    fake_engine.memory_engine = fake_memory

    def fake_train():
        pass

    with patch("finance_feedback_engine.cli.main.load_tiered_config", return_value={}):
        with patch("finance_feedback_engine.cli.main.FinanceFeedbackEngine", return_value=fake_engine):
            with patch("train_meta_learner.run_training", fake_train):
                res = runner.invoke(cli, ["retrain-meta-learner", "--force"])
                assert res.exit_code == 0, res.output


def test_run_agent_command():
    """Test run-agent command with mocked agent."""
    runner = CliRunner()
    fake_engine = MagicMock()
    fake_agent = MagicMock()

    # Mock agent.run as an async coroutine
    async def fake_run():
        return None
    fake_agent.run = fake_run

    with patch("finance_feedback_engine.cli.main.load_tiered_config", return_value={}):
        with patch("finance_feedback_engine.cli.main.FinanceFeedbackEngine", return_value=fake_engine):
            with patch("finance_feedback_engine.cli.main._initialize_agent", return_value=fake_agent):
                with patch("finance_feedback_engine.cli.main.console.input", return_value=""):  # Skip config editor
                    # Don't use --setup flag as it triggers config-editor; just run minimal agent
                    res = runner.invoke(cli, ["run-agent", "--autonomous"])
                    assert res.exit_code == 0, res.output


def test_install_deps_command():
    """Test install-deps basic invocation."""
    runner = CliRunner()

    with patch("finance_feedback_engine.cli.main.load_tiered_config", return_value={}):
        with patch("finance_feedback_engine.cli.main._check_dependencies", return_value=([], [])):
            res = runner.invoke(cli, ["install-deps"])
            assert res.exit_code == 0, res.output


def test_update_ai_command():
    """Test update-ai basic invocation."""
    runner = CliRunner()

    with patch("finance_feedback_engine.cli.main.load_tiered_config", return_value={}):
        with patch("finance_feedback_engine.cli.main._check_dependencies", return_value=([], [])):
            res = runner.invoke(cli, ["update-ai"])
            assert res.exit_code == 0, res.output


def test_config_editor_command():
    """Test config-editor basic invocation with mocked prompts."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        Path("config").mkdir()
        Path("config/config.yaml").write_text("trading_platform: mock\n")

        with patch("finance_feedback_engine.cli.main.load_config", return_value={"trading_platform": "mock"}):
            with patch("finance_feedback_engine.cli.main.Prompt.ask", side_effect=["", "", "", "", "", ""]):  # Empty answers to skip all prompts
                with patch("finance_feedback_engine.cli.main.console.input", return_value="n"):  # Don't save
                    res = runner.invoke(cli, ["config-editor"])
                    # Command may exit with 0 or 1 depending on save choice
                    assert res.exit_code in [0, 1], res.output
