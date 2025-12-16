"""Test signal-only mode validation in agent CLI commands."""

from unittest.mock import Mock, patch

import pytest

from finance_feedback_engine.agent.config import (
    AutonomousAgentConfig,
    TradingAgentConfig,
)
from finance_feedback_engine.agent.trading_loop_agent import TradingLoopAgent


class TestSignalOnlyModeValidation:
    """Test signal-only mode validation and safety checks."""

    def test_supports_signal_only_mode_returns_true_when_methods_exist(self):
        """Agent with required methods should support signal-only mode."""
        config = TradingAgentConfig(
            autonomous=AutonomousAgentConfig(enabled=False), asset_pairs=["BTCUSD"]
        )

        with patch("finance_feedback_engine.agent.trading_loop_agent.RiskGatekeeper"):
            agent = TradingLoopAgent(
                config=config,
                engine=Mock(),
                trade_monitor=Mock(),
                portfolio_memory=Mock(),
                trading_platform=Mock(),
            )

        assert agent.supports_signal_only_mode() is True

    def test_initialize_agent_validates_notification_channels_in_signal_mode(self):
        """_initialize_agent should validate notification channels before signal-only mode."""
        from finance_feedback_engine.cli.commands.agent import _initialize_agent

        config = {
            "agent": {"autonomous": {"enabled": False}, "asset_pairs": ["BTCUSD"]},
            "telegram": {"enabled": False, "bot_token": None, "chat_id": None},
            "webhook": {"enabled": False, "url": None},
        }

        mock_engine = Mock()
        mock_engine.trading_platform = Mock()
        mock_engine.memory_engine = Mock()

        with patch("finance_feedback_engine.cli.commands.agent.TradeMonitor"):
            with patch("finance_feedback_engine.cli.commands.agent.TradingLoopAgent"):
                with patch(
                    "finance_feedback_engine.cli.commands.agent.click.confirm",
                    return_value=False,
                ):
                    with pytest.raises(Exception) as exc_info:
                        _initialize_agent(config, mock_engine, 0.05, 0.02, False)

                    assert (
                        "notification" in str(exc_info.value).lower()
                        or "telegram" in str(exc_info.value).lower()
                    )

    def test_initialize_agent_succeeds_with_telegram_configured(self):
        """_initialize_agent should succeed when Telegram is properly configured."""
        from finance_feedback_engine.cli.commands.agent import _initialize_agent

        config = {
            "agent": {"autonomous": {"enabled": False}, "asset_pairs": ["BTCUSD"]},
            "telegram": {
                "enabled": True,
                "bot_token": "valid_token",
                "chat_id": "123456",
            },
            "webhook": {"enabled": False},
        }

        mock_engine = Mock()
        mock_engine.trading_platform = Mock()
        mock_engine.memory_engine = Mock()
        mock_engine.enable_monitoring_integration = Mock()

        mock_trade_monitor = Mock()
        mock_trade_monitor.start = Mock()

        mock_agent = Mock()
        mock_agent.supports_signal_only_mode = Mock(return_value=True)

        with patch(
            "finance_feedback_engine.cli.commands.agent.TradeMonitor",
            return_value=mock_trade_monitor,
        ):
            with patch(
                "finance_feedback_engine.cli.commands.agent.TradingLoopAgent",
                return_value=mock_agent,
            ):
                with patch(
                    "finance_feedback_engine.cli.commands.agent.click.confirm",
                    return_value=False,
                ):
                    agent = _initialize_agent(config, mock_engine, 0.05, 0.02, False)

                    assert agent is not None
                    assert agent.supports_signal_only_mode.called

    def test_agent_rejects_signal_mode_if_not_supported(self):
        """_initialize_agent should abort if agent doesn't support signal-only mode."""
        from finance_feedback_engine.cli.commands.agent import _initialize_agent

        config = {
            "agent": {"autonomous": {"enabled": False}, "asset_pairs": ["BTCUSD"]},
            "telegram": {
                "enabled": True,
                "bot_token": "valid_token",
                "chat_id": "123456",
            },
        }

        mock_engine = Mock()
        mock_engine.trading_platform = Mock()
        mock_engine.memory_engine = Mock()
        mock_engine.enable_monitoring_integration = Mock()

        mock_agent = Mock()
        mock_agent.supports_signal_only_mode = Mock(return_value=False)

        with patch("finance_feedback_engine.cli.commands.agent.TradeMonitor"):
            with patch(
                "finance_feedback_engine.cli.commands.agent.TradingLoopAgent",
                return_value=mock_agent,
            ):
                with patch(
                    "finance_feedback_engine.cli.commands.agent.click.confirm",
                    return_value=False,
                ):
                    with pytest.raises(Exception) as exc_info:
                        _initialize_agent(config, mock_engine, 0.05, 0.02, False)

                    assert "signal" in str(exc_info.value).lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
