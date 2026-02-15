"""Tests for Optuna hyperparameter optimization."""

from unittest.mock import Mock, patch

import pytest


@pytest.fixture
def mock_backtester():
    """Mock backtester for optimization tests."""
    backtester = Mock()
    backtester.run.return_value = {
        "metrics": {
            "sharpe_ratio": 1.5,
            "max_drawdown_pct": -10.0,
            "net_return_pct": 25.0,
            "win_rate": 55.0,
            "total_trades": 50,
        },
        "trades": [],
    }
    return backtester


@pytest.fixture
def base_config():
    """Base configuration for optimization."""
    return {
        "decision_engine": {
            "ai_provider": "ensemble",
            "risk_per_trade": 0.01,
            "stop_loss_percentage": 0.02,
        },
        "ensemble": {
            "enabled_providers": ["local", "cli", "codex"],
            "provider_weights": {"local": 0.4, "cli": 0.3, "codex": 0.3},
            "voting_strategy": "weighted",
        },
    }


class TestOptunaOptimizer:
    """Test Optuna hyperparameter optimizer."""

    def test_optimizer_initialization(self, base_config):
        """Test optimizer can be initialized with config."""
        from finance_feedback_engine.optimization.optuna_optimizer import (
            OptunaOptimizer,
        )

        optimizer = OptunaOptimizer(
            config=base_config,
            asset_pair="BTCUSD",
            start_date="2024-01-01",
            end_date="2024-06-01",
        )

        assert optimizer.asset_pair == "BTCUSD"
        assert optimizer.start_date == "2024-01-01"
        assert optimizer.end_date == "2024-06-01"

    def test_objective_function_runs(self, base_config, mock_backtester):
        """Test objective function executes backtest and returns score."""
        from finance_feedback_engine.optimization.optuna_optimizer import (
            OptunaOptimizer,
        )

        optimizer = OptunaOptimizer(
            config=base_config,
            asset_pair="BTCUSD",
            start_date="2024-01-01",
            end_date="2024-06-01",
        )

        # Mock trial
        trial = Mock()
        trial.suggest_float.side_effect = [0.015, 0.025, 0.04]  # risk, stop_loss, take_profit
        trial.suggest_categorical.return_value = "weighted"

        with patch.object(
            optimizer, "_run_backtest", return_value=mock_backtester.run()
        ):
            score = optimizer.objective(trial)

        assert isinstance(score, float)
        assert score > 0  # Should return positive score (Sharpe ratio)

    def test_parameter_suggestions(self, base_config):
        """Test optimizer suggests parameters in valid ranges."""
        from finance_feedback_engine.optimization.optuna_optimizer import (
            OptunaOptimizer,
        )

        optimizer = OptunaOptimizer(
            config=base_config,
            asset_pair="BTCUSD",
            start_date="2024-01-01",
            end_date="2024-06-01",
        )

        trial = Mock()
        trial.suggest_float.return_value = 0.015
        trial.suggest_categorical.return_value = "weighted"

        with patch.object(
            optimizer,
            "_run_backtest",
            return_value={"metrics": {"sharpe_ratio": 1.5}, "trades": []},
        ):
            optimizer.objective(trial)

        # Verify parameter ranges were suggested
        assert (
            trial.suggest_float.call_count >= 2
        )  # risk_per_trade, stop_loss_percentage

    def test_optimize_runs_trials(self, base_config, mock_backtester):
        """Test optimize method runs multiple trials."""
        from finance_feedback_engine.optimization.optuna_optimizer import (
            OptunaOptimizer,
        )

        optimizer = OptunaOptimizer(
            config=base_config,
            asset_pair="BTCUSD",
            start_date="2024-01-01",
            end_date="2024-06-01",
        )

        with patch.object(
            optimizer, "_run_backtest", return_value=mock_backtester.run()
        ):
            study = optimizer.optimize(n_trials=5, show_progress=False)

        assert study is not None
        assert len(study.trials) == 5

    def test_get_best_params(self, base_config, mock_backtester):
        """Test getting best parameters after optimization."""
        from finance_feedback_engine.optimization.optuna_optimizer import (
            OptunaOptimizer,
        )

        optimizer = OptunaOptimizer(
            config=base_config,
            asset_pair="BTCUSD",
            start_date="2024-01-01",
            end_date="2024-06-01",
        )

        with patch.object(
            optimizer, "_run_backtest", return_value=mock_backtester.run()
        ):
            study = optimizer.optimize(n_trials=3, show_progress=False)
            best_params = optimizer.get_best_params(study)

        assert isinstance(best_params, dict)
        assert "risk_per_trade" in best_params
        assert "stop_loss_percentage" in best_params

    def test_save_best_config(self, base_config, mock_backtester, tmp_path):
        """Test saving best configuration to file."""
        from finance_feedback_engine.optimization.optuna_optimizer import (
            OptunaOptimizer,
        )

        optimizer = OptunaOptimizer(
            config=base_config,
            asset_pair="BTCUSD",
            start_date="2024-01-01",
            end_date="2024-06-01",
        )

        with patch.object(
            optimizer, "_run_backtest", return_value=mock_backtester.run()
        ):
            study = optimizer.optimize(n_trials=3, show_progress=False)
            output_path = tmp_path / "best_config.yaml"
            optimizer.save_best_config(study, str(output_path))

        assert output_path.exists()


class TestMultiObjectiveOptimization:
    """Test multi-objective optimization (Sharpe + max drawdown)."""

    def test_multi_objective_function(self, base_config, mock_backtester):
        """Test multi-objective returns tuple of metrics."""
        from finance_feedback_engine.optimization.optuna_optimizer import (
            OptunaOptimizer,
        )

        optimizer = OptunaOptimizer(
            config=base_config,
            asset_pair="BTCUSD",
            start_date="2024-01-01",
            end_date="2024-06-01",
            multi_objective=True,
        )

        trial = Mock()
        trial.suggest_float.side_effect = [0.015, 0.025, 0.04]  # risk, stop_loss, take_profit
        trial.suggest_categorical.return_value = "weighted"

        with patch.object(
            optimizer, "_run_backtest", return_value=mock_backtester.run()
        ):
            result = optimizer.objective(trial)

        assert isinstance(result, tuple)
        assert len(result) == 2  # (sharpe, -drawdown)


class TestParameterSearchSpace:
    """Test parameter search space configuration."""

    def test_custom_search_space(self, base_config):
        """Test custom parameter ranges can be specified."""
        from finance_feedback_engine.optimization.optuna_optimizer import (
            OptunaOptimizer,
        )

        search_space = {
            "risk_per_trade": (0.005, 0.03),
            "stop_loss_percentage": (0.01, 0.05),
        }

        optimizer = OptunaOptimizer(
            config=base_config,
            asset_pair="BTCUSD",
            start_date="2024-01-01",
            end_date="2024-06-01",
            search_space=search_space,
        )

        assert optimizer.search_space == search_space

    def test_provider_weight_optimization(self, base_config, mock_backtester):
        """Test optimizer can tune provider weights."""
        from finance_feedback_engine.optimization.optuna_optimizer import (
            OptunaOptimizer,
        )

        optimizer = OptunaOptimizer(
            config=base_config,
            asset_pair="BTCUSD",
            start_date="2024-01-01",
            end_date="2024-06-01",
            optimize_weights=True,
        )

        trial = Mock()
        trial.suggest_float.side_effect = [0.015, 0.025, 0.04, 0.4, 0.3, 0.3]  # risk, stop_loss, take_profit, weights...
        trial.suggest_categorical.return_value = "weighted"

        with patch.object(
            optimizer, "_run_backtest", return_value=mock_backtester.run()
        ):
            optimizer.objective(trial)

        # Should suggest weights for each provider (3 params + 3 weights = 6)
        assert trial.suggest_float.call_count >= 6


class TestOptimizationResults:
    """Test optimization results reporting."""

    def test_generate_report(self, base_config, mock_backtester):
        """Test generating optimization report."""
        from finance_feedback_engine.optimization.optuna_optimizer import (
            OptunaOptimizer,
        )

        optimizer = OptunaOptimizer(
            config=base_config,
            asset_pair="BTCUSD",
            start_date="2024-01-01",
            end_date="2024-06-01",
        )

        with patch.object(
            optimizer, "_run_backtest", return_value=mock_backtester.run()
        ):
            study = optimizer.optimize(n_trials=5, show_progress=False)
            report = optimizer.generate_report(study)

        assert isinstance(report, dict)
        assert "best_params" in report
        assert "best_value" in report
        assert "n_trials" in report

    def test_optimization_history(self, base_config, mock_backtester):
        """Test retrieving optimization history."""
        from finance_feedback_engine.optimization.optuna_optimizer import (
            OptunaOptimizer,
        )

        optimizer = OptunaOptimizer(
            config=base_config,
            asset_pair="BTCUSD",
            start_date="2024-01-01",
            end_date="2024-06-01",
        )

        with patch.object(
            optimizer, "_run_backtest", return_value=mock_backtester.run()
        ):
            study = optimizer.optimize(n_trials=5, show_progress=False)
            history = optimizer.get_optimization_history(study)

        assert isinstance(history, list)
        assert len(history) == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
