"""Tests for TradingAgentConfig and AutonomousAgentConfig validators.

Tests the Phase 1 blocking validators:
1. asset_pairs validation (non-empty or signal-only mode)
2. max_drawdown_percent normalization (percentage notation support)
3. stop_loss < profit_target ordering
"""

import pytest
from pydantic import ValidationError

from finance_feedback_engine.agent.config import (
    AutonomousAgentConfig,
    TradingAgentConfig,
)


class TestAssetPairsValidator:
    """Test TradingAgentConfig.asset_pairs validation."""

    def test_asset_pairs_valid_list(self):
        """Valid: asset_pairs with one or more pairs."""
        config = TradingAgentConfig(asset_pairs=["BTCUSD"])
        assert config.asset_pairs == ["BTCUSD"]

    def test_asset_pairs_valid_multiple(self):
        """Valid: asset_pairs with multiple pairs."""
        config = TradingAgentConfig(asset_pairs=["BTCUSD", "ETHUSD", "EURUSD"])
        assert len(config.asset_pairs) == 3

    def test_asset_pairs_default_valid(self):
        """Valid: default asset_pairs is non-empty."""
        config = TradingAgentConfig()
        assert len(config.asset_pairs) > 0

    def test_asset_pairs_empty_raises_error(self):
        """Invalid: empty asset_pairs without signal-only mode."""
        with pytest.raises(ValidationError) as exc_info:
            TradingAgentConfig(asset_pairs=[])

        error_msg = str(exc_info.value)
        assert "asset_pairs cannot be empty" in error_msg
        assert "signal-only mode" in error_msg

    def test_asset_pairs_signal_only_mode_allows_empty(self):
        """Valid: empty asset_pairs allowed in signal-only mode.

        Signal-only mode = autonomous.enabled=false AND
                          require_notifications_for_signal_only=false
        """
        config = TradingAgentConfig(
            asset_pairs=[],
            autonomous=AutonomousAgentConfig(enabled=False),
            require_notifications_for_signal_only=False,
        )
        assert config.asset_pairs == []

    def test_asset_pairs_empty_with_autonomous_enabled_raises_error(self):
        """Invalid: empty asset_pairs with autonomous.enabled=true."""
        with pytest.raises(ValidationError) as exc_info:
            TradingAgentConfig(
                asset_pairs=[],
                autonomous=AutonomousAgentConfig(enabled=True),
                require_notifications_for_signal_only=False,
            )

        error_msg = str(exc_info.value)
        assert "asset_pairs cannot be empty" in error_msg

    def test_asset_pairs_empty_with_notifications_required_raises_error(self):
        """Invalid: empty asset_pairs with require_notifications_for_signal_only=true."""
        with pytest.raises(ValidationError) as exc_info:
            TradingAgentConfig(
                asset_pairs=[],
                autonomous=AutonomousAgentConfig(enabled=False),
                require_notifications_for_signal_only=True,
            )

        error_msg = str(exc_info.value)
        assert "asset_pairs cannot be empty" in error_msg


class TestStopLossProfitTargetValidator:
    """Test AutonomousAgentConfig stop_loss vs profit_target ordering."""

    def test_stop_loss_less_than_profit_target_valid(self):
        """Valid: stop_loss < profit_target."""
        config = AutonomousAgentConfig(
            stop_loss=0.02,
            profit_target=0.05,
        )
        assert config.stop_loss == 0.02
        assert config.profit_target == 0.05

    def test_stop_loss_equal_profit_target_raises_error(self):
        """Invalid: stop_loss == profit_target."""
        with pytest.raises(ValidationError) as exc_info:
            AutonomousAgentConfig(
                stop_loss=0.05,
                profit_target=0.05,
            )

        error_msg = str(exc_info.value)
        assert "stop_loss" in error_msg
        assert "profit_target" in error_msg
        assert "strictly less than" in error_msg

    def test_stop_loss_greater_than_profit_target_raises_error(self):
        """Invalid: stop_loss > profit_target."""
        with pytest.raises(ValidationError) as exc_info:
            AutonomousAgentConfig(
                stop_loss=0.10,
                profit_target=0.05,
            )

        error_msg = str(exc_info.value)
        assert "stop_loss" in error_msg
        assert "profit_target" in error_msg

    def test_default_stop_loss_profit_target_valid(self):
        """Valid: default values (0.02 < 0.05)."""
        config = AutonomousAgentConfig()
        assert config.stop_loss < config.profit_target

    def test_stop_loss_much_smaller_than_profit_target_valid(self):
        """Valid: aggressive profit target."""
        config = AutonomousAgentConfig(
            stop_loss=0.01,
            profit_target=0.20,
        )
        assert config.stop_loss == 0.01
        assert config.profit_target == 0.20

    def test_stop_loss_close_to_profit_target_valid(self):
        """Valid: close values still pass if stop_loss < profit_target."""
        config = AutonomousAgentConfig(
            stop_loss=0.049,
            profit_target=0.05,
        )
        assert config.stop_loss == 0.049
        assert config.profit_target == 0.05


class TestMaxDrawdownPercentValidator:
    """Test max_drawdown_percent normalization."""

    def test_max_drawdown_decimal_notation_valid(self):
        """Valid: decimal notation (0.15 = 15%)."""
        config = TradingAgentConfig(max_drawdown_percent=0.15)
        assert config.max_drawdown_percent == 0.15

    def test_max_drawdown_percentage_notation_normalized(self):
        """Valid: percentage notation auto-normalized (15 -> 0.15)."""
        config = TradingAgentConfig(max_drawdown_percent=15)
        assert config.max_drawdown_percent == 0.15

    def test_max_drawdown_large_percentage_normalized(self):
        """Valid: large percentage normalized (25 -> 0.25)."""
        config = TradingAgentConfig(max_drawdown_percent=25)
        assert config.max_drawdown_percent == 0.25

    def test_max_drawdown_small_decimal_valid(self):
        """Valid: small decimal value (0.05 = 5%)."""
        config = TradingAgentConfig(max_drawdown_percent=0.05)
        assert config.max_drawdown_percent == 0.05

    def test_max_drawdown_default_valid(self):
        """Valid: default value is reasonable (0.15 = 15%)."""
        config = TradingAgentConfig()
        # Default is 0.15
        assert 0 < config.max_drawdown_percent < 1

    def test_max_drawdown_zero_valid(self):
        """Valid: zero is technically allowed (no drawdown tolerance)."""
        config = TradingAgentConfig(max_drawdown_percent=0)
        assert config.max_drawdown_percent == 0

    def test_max_drawdown_one_valid(self):
        """Valid: 1.0 = 100% drawdown allowed."""
        config = TradingAgentConfig(max_drawdown_percent=1.0)
        assert config.max_drawdown_percent == 1.0

    def test_max_drawdown_hundred_normalized(self):
        """Valid: 100 normalized to 1.0."""
        config = TradingAgentConfig(max_drawdown_percent=100)
        assert config.max_drawdown_percent == 1.0


@pytest.mark.integration
class TestIntegrationMultipleValidators:
    """Test interactions between multiple validators."""

    def test_full_valid_config(self):
        """Valid: config with all validators passing."""
        config = TradingAgentConfig(
            asset_pairs=["BTCUSD", "ETHUSD"],
            autonomous=AutonomousAgentConfig(
                enabled=True,
                stop_loss=0.02,
                profit_target=0.05,
            ),
            max_drawdown_percent=25,  # Will be normalized to 0.25
        )
        assert len(config.asset_pairs) == 2
        assert config.autonomous.stop_loss < config.autonomous.profit_target
        assert config.max_drawdown_percent == 0.25

    def test_invalid_asset_pairs_with_invalid_stop_loss(self):
        """Invalid: both asset_pairs and stop_loss validators fail."""
        with pytest.raises(ValidationError):
            TradingAgentConfig(
                asset_pairs=[],
                autonomous=AutonomousAgentConfig(
                    stop_loss=0.10,
                    profit_target=0.05,
                ),
            )

    def test_signal_only_mode_full_config(self):
        """Valid: signal-only mode with all validators passing."""
        config = TradingAgentConfig(
            asset_pairs=[],
            autonomous=AutonomousAgentConfig(
                enabled=False,
                stop_loss=0.02,
                profit_target=0.05,
            ),
            require_notifications_for_signal_only=False,
            max_drawdown_percent=20,
        )
        assert config.asset_pairs == []
        assert config.max_drawdown_percent == 0.20
