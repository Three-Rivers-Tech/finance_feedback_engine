"""Test signal-only mode validation in agent CLI commands."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from click.testing import CliRunner
from finance_feedback_engine.agent.config import TradingAgentConfig, AutonomousAgentConfig
from finance_feedback_engine.agent.trading_loop_agent import TradingLoopAgent


class TestSignalOnlyModeValidation:
    """Test signal-only mode validation and safety checks."""

    def test_supports_signal_only_mode_returns_true_when_methods_exist(self):
        """Agent with required methods should support signal-only mode."""
        # Create a mock agent with required methods
        config = TradingAgentConfig(
            autonomous=AutonomousAgentConfig(enabled=False),
            asset_pairs=["BTCUSD"]
        )

        with patch('finance_feedback_engine.agent.trading_loop_agent.RiskGatekeeper'):
            agent = TradingLoopAgent(
                config=config,
                engine=Mock(),
                trade_monitor=Mock(),
                portfolio_memory=Mock(),
                trading_platform=Mock()
            )

        # Should return True since all required methods exist
        assert agent.supports_signal_only_mode() is True

    def test_supports_signal_only_mode_returns_false_when_method_missing(self):
        """Agent without required methods should not support signal-only mode."""
        config = TradingAgentConfig(
            autonomous=AutonomousAgentConfig(enabled=False),
            asset_pairs=["BTCUSD"]
        )

        with patch('finance_feedback_engine.agent.trading_loop_agent.RiskGatekeeper'):
            agent = TradingLoopAgent(
                config=config,
                engine=Mock(),
                trade_monitor=Mock(),
                portfolio_memory=Mock(),
                trading_platform=Mock()
            )

        # Mock the agent to simulate missing method
        with patch.object(agent, '_send_signals_to_telegram', create=False) as mock_missing:
            # Delete the attribute to simulate it not existing
            if hasattr(agent, '_send_signals_to_telegram'):
                original_method = agent._send_signals_to_telegram
                delattr(agent.__class__, '_send_signals_to_telegram')
                try:
                    # Should return False when method is missing
                    assert agent.supports_signal_only_mode() is False
                finally:
                    # Restore for other tests
                    agent.__class__._send_signals_to_telegram = original_method

    def test_send_signals_tracks_delivery_failures(self):
        """_send_signals_to_telegram should track and report delivery failures."""
        config = TradingAgentConfig(
            autonomous=AutonomousAgentConfig(enabled=False),
            asset_pairs=["BTCUSD"]
        )

        with patch('finance_feedback_engine.agent.trading_loop_agent.RiskGatekeeper'):
        )

        # Configure telegram as enabled with valid credentials
        config.telegram = {
            'enabled': True,
            'bot_token': 'test_token_123',
            'chat_id': '123456789'
        }

        with patch('finance_feedback_engine.agent.trading_loop_agent.RiskGatekeeper'):
            agent = TradingLoopAgent(
                config=config,
                engine=Mock(),
                trade_monitor=Mock(),
                portfolio_memory=Mock(),
                trading_platform=Mock()
            )

        # Add test decision
        agent._current_decisions = [{
            'id': 'test_decision_002',
            'asset_pair': 'ETHUSD',
            'action': 'SELL',
            'confidence': 75,
            'reasoning': 'Test sell signal',
            'recommended_position_size': 0.5
        }]

        # Mock TelegramBot
        with patch('finance_feedback_engine.agent.trading_loop_agent.TelegramBot') as MockBot:
            mock_bot_instance = Mock()
            MockBot.return_value = mock_bot_instance

            # Call should succeed
            agent._send_signals_to_telegram()

            # Verify bot was created and message sent
            MockBot.assert_called_once_with(token='test_token_123')
            mock_bot_instance.send_message.assert_called_once()

            # Verify message content
            call_args = mock_bot_instance.send_message.call_args
            assert call_args[0][0] == '123456789'  # chat_id
            assert 'ETHUSD' in call_args[0][1]  # message contains asset
            assert 'SELL' in call_args[0][1]  # message contains action

    def test_initialize_agent_validates_notification_channels_in_signal_mode(self):
        """_initialize_agent should validate notification channels before signal-only mode."""
        from finance_feedback_engine.cli.commands.agent import _initialize_agent

        # Config without notification channels
        config = {
            'agent': {
                'autonomous': {
                    'enabled': False
                },
                'asset_pairs': ['BTCUSD']
            },
            'telegram': {
                'enabled': False,
                'bot_token': None,
                'chat_id': None
            },
            'webhook': {
                'enabled': False,
                'url': None
            }
        }

        mock_engine = Mock()
        mock_engine.trading_platform = Mock()
        mock_engine.memory_engine = Mock()

        # Should raise ClickException when no notification channels configured
        with patch('finance_feedback_engine.cli.commands.agent.TradeMonitor'):
            with patch('finance_feedback_engine.cli.commands.agent.TradingLoopAgent'):
                with patch('finance_feedback_engine.cli.commands.agent.click.confirm', return_value=False):
                    with pytest.raises(Exception) as exc_info:
                        _initialize_agent(config, mock_engine, 0.05, 0.02, False)

                    # Should mention notification channels in error
                    assert 'notification' in str(exc_info.value).lower() or 'telegram' in str(exc_info.value).lower()

    def test_initialize_agent_succeeds_with_telegram_configured(self):
        """_initialize_agent should succeed when Telegram is properly configured."""
        from finance_feedback_engine.cli.commands.agent import _initialize_agent

        # Config with valid Telegram
        config = {
            'agent': {
                'autonomous': {
                    'enabled': False
                },
                'asset_pairs': ['BTCUSD']
            },
            'telegram': {
                'enabled': True,
                'bot_token': 'valid_token',
                'chat_id': '123456'
            },
            'webhook': {
                'enabled': False
            }
        }

        mock_engine = Mock()
        mock_engine.trading_platform = Mock()
        mock_engine.memory_engine = Mock()
        mock_engine.enable_monitoring_integration = Mock()

        mock_trade_monitor = Mock()
        mock_trade_monitor.start = Mock()

        mock_agent = Mock()
        mock_agent.supports_signal_only_mode = Mock(return_value=True)

        with patch('finance_feedback_engine.cli.commands.agent.TradeMonitor', return_value=mock_trade_monitor):
            with patch('finance_feedback_engine.cli.commands.agent.TradingLoopAgent', return_value=mock_agent):
                with patch('finance_feedback_engine.cli.commands.agent.click.confirm', return_value=False):
                    agent = _initialize_agent(config, mock_engine, 0.05, 0.02, False)

                    # Should return agent instance
                    assert agent is not None
                    assert agent.supports_signal_only_mode.called

    def test_agent_rejects_signal_mode_if_not_supported(self):
        """_initialize_agent should abort if agent doesn't support signal-only mode."""
        from finance_feedback_engine.cli.commands.agent import _initialize_agent

        config = {
            'agent': {
                'autonomous': {
                    'enabled': False
                },
                'asset_pairs': ['BTCUSD']
            },
            'telegram': {
                'enabled': True,
                'bot_token': 'valid_token',
                'chat_id': '123456'
            }
        }

        mock_engine = Mock()
        mock_engine.trading_platform = Mock()
        mock_engine.memory_engine = Mock()
        mock_engine.enable_monitoring_integration = Mock()

        mock_agent = Mock()
        mock_agent.supports_signal_only_mode = Mock(return_value=False)  # Not supported!

        with patch('finance_feedback_engine.cli.commands.agent.TradeMonitor'):
            with patch('finance_feedback_engine.cli.commands.agent.TradingLoopAgent', return_value=mock_agent):
                with patch('finance_feedback_engine.cli.commands.agent.click.confirm', return_value=False):
                    with pytest.raises(Exception) as exc_info:
                        _initialize_agent(config, mock_engine, 0.05, 0.02, False)

                    # Should mention signal-only mode in error
                    assert 'signal' in str(exc_info.value).lower()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
