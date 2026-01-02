"""
Tests for Dashboard Data Aggregator.

Covers dashboard_aggregator.py module for live agent dashboard data collection.
"""

import pytest
import time
from datetime import datetime
from unittest.mock import MagicMock, patch
from finance_feedback_engine.cli.dashboard_aggregator import DashboardDataAggregator


class TestDashboardDataAggregator:
    """Test suite for dashboard data aggregator."""

    @pytest.fixture
    def mock_components(self):
        """Create mock components for aggregator."""
        agent = MagicMock()
        agent.state = MagicMock()
        agent.state.name = "IDLE"
        agent._cycle_count = 10
        agent.daily_trade_count = 2
        agent._start_time = time.time() - 3600  # 1 hour ago
        
        config = MagicMock()
        config.kill_switch_loss_pct = 0.05  # 5%
        config.kill_switch_gain_pct = 0.10  # 10%
        config.max_daily_trades = 5
        agent.config = config
        
        engine = MagicMock()
        
        trade_monitor = MagicMock()
        trade_monitor.monitoring_context_provider = MagicMock()
        trade_monitor.monitoring_context_provider.get_monitoring_context.return_value = {
            "risk_metrics": {"unrealized_pnl_percent": 2.5}
        }
        
        portfolio_memory = MagicMock()
        
        return agent, engine, trade_monitor, portfolio_memory

    @pytest.fixture
    def aggregator(self, mock_components):
        """Create aggregator instance."""
        return DashboardDataAggregator(*mock_components)

    def test_initialization(self, mock_components):
        """Test aggregator initialization."""
        agent, engine, trade_monitor, portfolio_memory = mock_components
        
        aggregator = DashboardDataAggregator(agent, engine, trade_monitor, portfolio_memory)
        
        assert aggregator.agent is agent
        assert aggregator.engine is engine
        assert aggregator.trade_monitor is trade_monitor
        assert aggregator.portfolio_memory is portfolio_memory
        assert hasattr(aggregator, '_start_time')

    def test_get_agent_status_basic(self, aggregator):
        """Test getting basic agent status."""
        status = aggregator.get_agent_status()
        
        assert status["state"] == "IDLE"
        assert status["cycle_count"] == 10
        assert status["daily_trades"] == 2
        assert status["uptime_seconds"] >= 3599  # ~1 hour
        assert status["uptime_seconds"] < 3602
        assert status["kill_switch"]["active"] is True
        assert status["kill_switch"]["loss_threshold"] == 0.05
        assert status["kill_switch"]["gain_threshold"] == 0.10
        assert status["kill_switch"]["current_pnl_pct"] == 2.5
        assert status["max_daily_trades"] == 5

    def test_get_agent_status_no_state(self, aggregator):
        """Test agent status when state is missing."""
        aggregator.agent.state = None
        
        status = aggregator.get_agent_status()
        
        assert status["state"] == "UNKNOWN"

    def test_get_agent_status_no_config(self, aggregator):
        """Test agent status when config is missing."""
        aggregator.agent.config = None
        
        status = aggregator.get_agent_status()
        
        assert status["kill_switch"]["active"] is False
        assert status["kill_switch"]["loss_threshold"] == 0.0
        assert status["kill_switch"]["gain_threshold"] == 0.0
        assert status["max_daily_trades"] == 5  # Default

    def test_get_agent_status_kill_switch_inactive(self, aggregator):
        """Test kill switch status when thresholds are zero."""
        aggregator.agent.config.kill_switch_loss_pct = 0.0
        aggregator.agent.config.kill_switch_gain_pct = 0.0
        
        status = aggregator.get_agent_status()
        
        assert status["kill_switch"]["active"] is False

    def test_get_agent_status_missing_counters(self, aggregator):
        """Test status when counters are missing."""
        del aggregator.agent._cycle_count
        del aggregator.agent.daily_trade_count
        
        status = aggregator.get_agent_status()
        
        assert status["cycle_count"] == 0
        assert status["daily_trades"] == 0

    def test_get_agent_status_pnl_error_handling(self, aggregator):
        """Test P&L calculation error handling."""
        aggregator.trade_monitor.monitoring_context_provider.get_monitoring_context.side_effect = \
            Exception("Context error")
        
        status = aggregator.get_agent_status()
        
        # Should handle exception gracefully
        assert status["kill_switch"]["current_pnl_pct"] == 0.0
        assert "state" in status  # Rest of status still works

    def test_get_agent_status_missing_start_time(self, aggregator):
        """Test uptime calculation when agent start time is missing."""
        del aggregator.agent._start_time
        
        status = aggregator.get_agent_status()
        
        # Should fall back to aggregator's start time
        assert "uptime_seconds" in status
        assert status["uptime_seconds"] >= 0

    def test_get_agent_status_none_values_handling(self, aggregator):
        """Test handling of None values in configuration."""
        aggregator.agent.config.kill_switch_loss_pct = None
        aggregator.agent.config.kill_switch_gain_pct = None
        
        status = aggregator.get_agent_status()
        
        assert status["kill_switch"]["loss_threshold"] == 0.0
        assert status["kill_switch"]["gain_threshold"] == 0.0
        assert status["kill_switch"]["active"] is False

    def test_get_agent_status_missing_risk_metrics(self, aggregator):
        """Test when risk metrics are missing from context."""
        aggregator.trade_monitor.monitoring_context_provider.get_monitoring_context.return_value = {}
        
        status = aggregator.get_agent_status()
        
        assert status["kill_switch"]["current_pnl_pct"] == 0.0

    def test_get_agent_status_none_pnl_value(self, aggregator):
        """Test when P&L value is None."""
        aggregator.trade_monitor.monitoring_context_provider.get_monitoring_context.return_value = {
            "risk_metrics": {"unrealized_pnl_percent": None}
        }
        
        status = aggregator.get_agent_status()
        
        assert status["kill_switch"]["current_pnl_pct"] == 0.0


class TestDashboardDataAggregatorEdgeCases:
    """Test edge cases and error conditions."""

    def test_with_minimal_agent(self):
        """Test with agent that has minimal attributes."""
        agent = MagicMock(spec=[])  # No attributes
        engine = MagicMock()
        trade_monitor = MagicMock()
        portfolio_memory = MagicMock()
        
        aggregator = DashboardDataAggregator(agent, engine, trade_monitor, portfolio_memory)
        status = aggregator.get_agent_status()
        
        # Should handle gracefully with defaults
        assert status["state"] == "UNKNOWN"
        assert status["cycle_count"] == 0
        assert status["daily_trades"] == 0

    def test_uptime_calculation_precision(self):
        """Test uptime calculation precision."""
        agent = MagicMock()
        agent.state = MagicMock()
        agent.state.name = "RUNNING"
        agent._start_time = time.time() - 7200  # 2 hours ago
        agent.config = None
        
        aggregator = DashboardDataAggregator(agent, MagicMock(), MagicMock(), MagicMock())
        status = aggregator.get_agent_status()
        
        # Should be approximately 2 hours (7200 seconds)
        assert 7198 <= status["uptime_seconds"] <= 7202

    def test_concurrent_status_calls(self):
        """Test multiple concurrent status calls."""
        agent = MagicMock()
        agent.state = MagicMock()
        agent.state.name = "IDLE"
        agent._cycle_count = 5
        agent.config = None
        
        aggregator = DashboardDataAggregator(agent, MagicMock(), MagicMock(), MagicMock())
        
        # Multiple calls should work independently
        status1 = aggregator.get_agent_status()
        status2 = aggregator.get_agent_status()
        
        assert status1["cycle_count"] == status2["cycle_count"]
        assert status1["state"] == status2["state"]

    def test_state_enum_handling(self):
        """Test various state enum values."""
        test_states = ["IDLE", "PERCEPTION", "REASONING", "RISK_CHECK", "EXECUTION", "LEARNING"]
        
        for state_name in test_states:
            agent = MagicMock()
            agent.state = MagicMock()
            agent.state.name = state_name
            agent.config = None
            
            aggregator = DashboardDataAggregator(agent, MagicMock(), MagicMock(), MagicMock())
            status = aggregator.get_agent_status()
            
            assert status["state"] == state_name

    def test_large_cycle_counts(self):
        """Test with large cycle counts."""
        agent = MagicMock()
        agent.state = MagicMock()
        agent.state.name = "IDLE"
        agent._cycle_count = 999999
        agent.daily_trade_count = 1000
        agent.config = None
        
        aggregator = DashboardDataAggregator(agent, MagicMock(), MagicMock(), MagicMock())
        status = aggregator.get_agent_status()
        
        assert status["cycle_count"] == 999999
        assert status["daily_trades"] == 1000

    def test_negative_pnl_values(self):
        """Test with negative P&L values."""
        agent = MagicMock()
        agent.state = MagicMock()
        agent.state.name = "IDLE"
        agent.config = MagicMock()
        agent.config.kill_switch_loss_pct = 0.05
        agent.config.kill_switch_gain_pct = 0.10
        
        trade_monitor = MagicMock()
        trade_monitor.monitoring_context_provider = MagicMock()
        trade_monitor.monitoring_context_provider.get_monitoring_context.return_value = {
            "risk_metrics": {"unrealized_pnl_percent": -3.5}
        }
        
        aggregator = DashboardDataAggregator(agent, MagicMock(), trade_monitor, MagicMock())
        status = aggregator.get_agent_status()
        
        assert status["kill_switch"]["current_pnl_pct"] == -3.5

    def test_kill_switch_with_only_loss_threshold(self):
        """Test kill switch active with only loss threshold set."""
        agent = MagicMock()
        agent.state = MagicMock()
        agent.state.name = "IDLE"
        agent.config = MagicMock()
        agent.config.kill_switch_loss_pct = 0.05
        agent.config.kill_switch_gain_pct = 0.0
        
        trade_monitor = MagicMock()
        trade_monitor.monitoring_context_provider = MagicMock()
        trade_monitor.monitoring_context_provider.get_monitoring_context.return_value = {}
        
        aggregator = DashboardDataAggregator(agent, MagicMock(), trade_monitor, MagicMock())
        status = aggregator.get_agent_status()
        
        assert status["kill_switch"]["active"] is True
        assert status["kill_switch"]["loss_threshold"] == 0.05
        assert status["kill_switch"]["gain_threshold"] == 0.0

    def test_kill_switch_with_only_gain_threshold(self):
        """Test kill switch active with only gain threshold set."""
        agent = MagicMock()
        agent.state = MagicMock()
        agent.state.name = "IDLE"
        agent.config = MagicMock()
        agent.config.kill_switch_loss_pct = 0.0
        agent.config.kill_switch_gain_pct = 0.15
        
        trade_monitor = MagicMock()
        trade_monitor.monitoring_context_provider = MagicMock()
        trade_monitor.monitoring_context_provider.get_monitoring_context.return_value = {}
        
        aggregator = DashboardDataAggregator(agent, MagicMock(), trade_monitor, MagicMock())
        status = aggregator.get_agent_status()
        
        assert status["kill_switch"]["active"] is True
        assert status["kill_switch"]["loss_threshold"] == 0.0
        assert status["kill_switch"]["gain_threshold"] == 0.15
