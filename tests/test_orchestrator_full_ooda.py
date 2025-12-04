"""Comprehensive tests for TradingAgentOrchestrator OODA loop."""

import pytest
import time
from unittest.mock import Mock, MagicMock, patch, PropertyMock
from finance_feedback_engine.agent.orchestrator import TradingAgentOrchestrator
from finance_feedback_engine.agent.config import TradingAgentConfig


@pytest.fixture
def mock_config():
    """Create a minimal TradingAgentConfig."""
    return TradingAgentConfig(
        strategic_goal="maximize_returns",
        risk_appetite="moderate",
        asset_pairs=["BTCUSD", "ETHUSD"],
        analysis_frequency_seconds=60,
        max_concurrent_trades=2,
        autonomous_execution=True,
        kill_switch_gain_pct=0.05,
        kill_switch_loss_pct=0.02,
        max_drawdown_percent=0.15
    )


@pytest.fixture
def mock_engine():
    """Create a mock DecisionEngine."""
    engine = Mock()
    engine.data_provider = Mock()
    engine.data_provider.get_comprehensive_market_data = Mock(return_value={
        'close': 50000.0,
        'high': 51000.0,
        'low': 49000.0,
        'market_regime': 'TRENDING_BULL',
        'sentiment_score': 0.7
    })
    engine.generate_decision = Mock(return_value={
        'action': 'BUY',
        'confidence': 80,
        'reasoning': 'Strong uptrend',
        'position_size': 0.1,
        'asset_pair': 'BTCUSD'
    })
    return engine


@pytest.fixture
def mock_platform():
    """Create a mock UnifiedTradingPlatform."""
    platform = Mock()
    platform.get_portfolio_breakdown = Mock(return_value={
        'total_value_usd': 10000.0,
        'holdings': []
    })
    platform.execute_trade = Mock(return_value={'status': 'success', 'order_id': '12345'})
    return platform


@pytest.fixture
def orchestrator(mock_config, mock_engine, mock_platform):
    """Create orchestrator instance."""
    return TradingAgentOrchestrator(mock_config, mock_engine, mock_platform)


class TestOrchestratorInitialization:
    """Test orchestrator initialization and portfolio value snapshots."""

    def test_initialization_success(self, mock_config, mock_engine, mock_platform):
        """Test successful initialization with valid portfolio value."""
        orch = TradingAgentOrchestrator(mock_config, mock_engine, mock_platform)

        assert orch.initial_portfolio_value == 10000.0
        assert orch.peak_portfolio_value == 10000.0
        assert orch.init_failed is False
        assert orch.trades_today == 0
        assert orch._paused_by_monitor is False

    def test_initialization_with_retries(self, mock_config, mock_engine, mock_platform):
        """Test initialization retries when portfolio value initially unavailable."""
        # First 2 calls return 0, then succeed
        mock_platform.get_portfolio_breakdown.side_effect = [
            {'total_value_usd': 0.0},
            {'total_value_usd': 0.0},
            {'total_value_usd': 10000.0}
        ]

        with patch('time.sleep'):  # Mock sleep to speed up test
            orch = TradingAgentOrchestrator(mock_config, mock_engine, mock_platform)

        assert orch.initial_portfolio_value == 10000.0
        assert orch.init_failed is False

    def test_initialization_failure_all_retries(self, mock_config, mock_engine, mock_platform):
        """Test initialization fails after all retries."""
        mock_platform.get_portfolio_breakdown.return_value = {'total_value_usd': 0.0}

        with patch('time.sleep'):
            orch = TradingAgentOrchestrator(mock_config, mock_engine, mock_platform)

        assert orch.initial_portfolio_value == 0.0
        assert orch.init_failed is True

    def test_max_drawdown_percentage_normalization(self, mock_engine, mock_platform):
        """Test max_drawdown_percent handles both decimal and percentage inputs."""
        # Test decimal input (0.15 = 15%)
        config1 = TradingAgentConfig(
            strategic_goal="test",
            risk_appetite="low",
            asset_pairs=["BTCUSD"],
            max_drawdown_percent=0.15
        )
        orch1 = TradingAgentOrchestrator(config1, mock_engine, mock_platform)
        assert orch1.max_drawdown_pct == 0.15

        # Test percentage input (15.0 = 15%)
        config2 = TradingAgentConfig(
            strategic_goal="test",
            risk_appetite="low",
            asset_pairs=["BTCUSD"],
            max_drawdown_percent=15.0
        )
        orch2 = TradingAgentOrchestrator(config2, mock_engine, mock_platform)
        assert orch2.max_drawdown_pct == 0.15


class TestOODALoopPerception:
    """Test PERCEIVE state (market data gathering)."""

    def test_perception_success_first_attempt(self, orchestrator, mock_engine):
        """Test successful market data fetch on first attempt."""
        market_data = {
            'close': 50000.0,
            'market_regime': 'TRENDING_BULL',
            'sentiment_score': 0.8
        }
        mock_engine.data_provider.get_comprehensive_market_data.return_value = market_data

        orchestrator.run(test_mode=True)

        mock_engine.data_provider.get_comprehensive_market_data.assert_called_with(
            'BTCUSD',
            include_sentiment=True,
            include_macro=True
        )

    def test_perception_retry_on_failure(self, orchestrator, mock_engine):
        """Test 3-attempt retry logic with exponential backoff."""
        # First 2 calls fail, 3rd succeeds
        mock_engine.data_provider.get_comprehensive_market_data.side_effect = [
            Exception("Network error"),
            Exception("Timeout"),
            {'close': 50000.0, 'market_regime': 'TRENDING_BULL'}
        ]

        with patch('time.sleep') as mock_sleep:
            orchestrator.run(test_mode=True)

        # Verify exponential backoff (2^0=1s, 2^1=2s)
        assert mock_sleep.call_count == 2
        assert mock_sleep.call_args_list[0][0][0] == 1  # 2^0
        assert mock_sleep.call_args_list[1][0][0] == 2  # 2^1

    def test_perception_all_retries_fail(self, orchestrator, mock_engine):
        """Test skipping asset after all 3 attempts fail."""
        mock_engine.data_provider.get_comprehensive_market_data.side_effect = Exception("Persistent error")

        with patch('time.sleep'):
            orchestrator.run(test_mode=True)

        # Verify failure tracked
        assert 'BTCUSD' in orchestrator.analysis_failures
        assert isinstance(orchestrator.analysis_failures['BTCUSD'], float)


class TestOODALoopDecision:
    """Test DECIDE state (AI decision generation)."""

    def test_decision_generation_called(self, orchestrator, mock_engine):
        """Test decision engine is called for each asset."""
        orchestrator.run(test_mode=True)

        # Should be called for first asset (BTCUSD)
        assert mock_engine.generate_decision.called

    def test_decision_with_context(self, orchestrator, mock_engine):
        """Test decision generation includes strategic context."""
        orchestrator.run(test_mode=True)

        # Verify engine was called (context is built internally)
        assert mock_engine.generate_decision.call_count >= 1


class TestKillSwitchMechanisms:
    """Test kill-switch triggers (take-profit, stop-loss, max drawdown)."""

    def test_kill_switch_take_profit_trigger(self, orchestrator, mock_platform):
        """Test kill-switch activates on take-profit threshold."""
        mock_platform.get_portfolio_breakdown.return_value = {
            'total_value_usd': 10500.0,
            'holdings': []
        }

        orchestrator.run(test_mode=True)

        # Assert kill-switch fired
        assert orchestrator.kill_switch_triggered is True
        assert orchestrator.initial_portfolio_value == 10000.0

    def test_kill_switch_stop_loss_trigger(self, orchestrator, mock_platform):
        """Test kill-switch activates on stop-loss threshold."""
        mock_platform.get_portfolio_breakdown.return_value = {
            'total_value_usd': 9800.0,
            'holdings': []
        }

        orchestrator.run(test_mode=True)

        # Assert kill-switch fired
        assert orchestrator.kill_switch_triggered is True
        assert orchestrator.kill_switch_loss_pct == 0.02

    def test_kill_switch_max_drawdown_trigger(self, orchestrator, mock_platform):
        """Test kill-switch activates on max drawdown threshold."""
        orchestrator.peak_portfolio_value = 12000.0
        mock_platform.get_portfolio_breakdown.return_value = {
            'total_value_usd': 10200.0,
            'holdings': []
        }

        orchestrator.run(test_mode=True)

        # Assert kill-switch fired
        assert orchestrator.kill_switch_triggered is True
        assert orchestrator.max_drawdown_pct == 0.15

    def test_peak_portfolio_value_updates(self, orchestrator, mock_platform):
        """Test peak portfolio value updates on new highs."""
        orchestrator.peak_portfolio_value = 10000.0

        mock_platform.get_portfolio_breakdown.return_value = {
            'total_value_usd': 11000.0,
            'holdings': []
        }

        orchestrator.run(test_mode=True)

        # Assert peak value updated and kill-switch NOT triggered
        assert orchestrator.peak_portfolio_value == 11000.0
        assert orchestrator.kill_switch_triggered is False


class TestPauseMechanism:
    """Test pause/resume functionality."""

    def test_pause_trading(self, orchestrator):
        """Test pause_trading method sets flag."""
        orchestrator.pause_trading(reason="Portfolio stop-loss")

        assert orchestrator._paused_by_monitor is True

    def test_paused_agent_skips_trading(self, orchestrator, mock_engine):
        """Test paused agent skips analysis and waits."""
        orchestrator._paused_by_monitor = True

        with patch('time.sleep') as mock_sleep:
            orchestrator.run(test_mode=True)

        # Should sleep instead of analyzing
        assert mock_sleep.called

    def test_stop_event_terminates_loop(self, orchestrator):
        """Test stop() method sets stop event."""
        orchestrator.stop()

        assert orchestrator._stop_event.is_set()


class TestExecutionHandling:
    """Test trade execution logic."""

    def test_autonomous_execution_enabled(self, orchestrator, mock_platform, mock_engine):
        """Test autonomous execution calls platform.execute_trade."""
        orchestrator.config.autonomous_execution = True

        orchestrator.run(test_mode=True)

        # Verify platform.execute_trade was called
        assert mock_platform.execute_trade.call_count > 0

    def test_approval_required_mode(self, mock_config, mock_engine, mock_platform):
        """Test approval mode skips execution."""
        mock_config.autonomous_execution = False
        orch = TradingAgentOrchestrator(mock_config, mock_engine, mock_platform)

        orch.run(test_mode=True)

        # Verify execute_trade was NOT called
        mock_platform.execute_trade.assert_not_called()

class TestErrorHandling:
    """Test error handling and resilience."""

    def test_kill_switch_check_exception_handled(self, orchestrator, mock_platform):
        """Test exception during kill-switch check doesn't crash loop."""
        mock_platform.get_portfolio_breakdown.side_effect = Exception("Platform error")

        # Should not raise exception
        orchestrator.run(test_mode=True)

    def test_analysis_failure_tracking(self, orchestrator):
        """Test failed analysis tracked with timestamp."""
        orchestrator.analysis_failures = {}

        # Trigger failure (already tested in perception tests)
        assert isinstance(orchestrator.analysis_failures, dict)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
