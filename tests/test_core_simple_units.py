"""Simple unit tests for core.py utility methods.

These tests target specific methods without complex mocking to increase
direct core.py coverage.
"""

from unittest.mock import Mock, patch
import pytest


class TestCoreUtilityMethods:
    """Test utility methods in FinanceFeedbackEngine."""

    def test_invalidate_portfolio_cache(self):
        """Test cache invalidation method."""
        with patch("finance_feedback_engine.core.DecisionEngine"), \
             patch("finance_feedback_engine.core.AlphaVantageProvider"), \
             patch("finance_feedback_engine.core.HistoricalDataProvider"), \
             patch("finance_feedback_engine.data_providers.unified_data_provider.UnifiedDataProvider"), \
             patch("finance_feedback_engine.core.validate_at_startup"), \
             patch("finance_feedback_engine.core.validate_credentials"), \
             patch("finance_feedback_engine.core.validate_and_warn"), \
             patch("finance_feedback_engine.core.ensure_models_installed"):
            
            from finance_feedback_engine.core import FinanceFeedbackEngine
            
            config = {
                "alpha_vantage_api_key": "test",
                "trading_platform": "mock",
                "platform_credentials": {},
                "persistence": {"backend": "sqlite", "db_path": ":memory:"},
                "is_backtest": False,
            }
            
            engine = FinanceFeedbackEngine(config)
            
            # Set cache
            engine._portfolio_cache = {"test": "data"}
            engine._portfolio_cache_time = "time"
            
            # Invalidate
            engine.invalidate_portfolio_cache()
            
            # Verify cleared
            assert engine._portfolio_cache is None
            assert engine._portfolio_cache_time is None

    def test_get_balance_delegates_to_platform(self):
        """Test get_balance delegates to trading platform."""
        with patch("finance_feedback_engine.core.DecisionEngine"), \
             patch("finance_feedback_engine.core.AlphaVantageProvider"), \
             patch("finance_feedback_engine.core.HistoricalDataProvider"), \
             patch("finance_feedback_engine.data_providers.unified_data_provider.UnifiedDataProvider"), \
             patch("finance_feedback_engine.core.validate_at_startup"), \
             patch("finance_feedback_engine.core.validate_credentials"), \
             patch("finance_feedback_engine.core.validate_and_warn"), \
             patch("finance_feedback_engine.core.ensure_models_installed"):
            
            from finance_feedback_engine.core import FinanceFeedbackEngine
            
            config = {
                "alpha_vantage_api_key": "test",
                "trading_platform": "mock",
                "platform_credentials": {},
                "persistence": {"backend": "sqlite", "db_path": ":memory:"},
                "is_backtest": False,
            }
            
            engine = FinanceFeedbackEngine(config)
            engine.trading_platform = Mock()
            engine.trading_platform.get_balance = Mock(return_value={"USD": 1000.0})
            
            balance = engine.get_balance()
            
            assert balance == {"USD": 1000.0}
            engine.trading_platform.get_balance.assert_called_once()

    def test_get_decision_history_no_filter(self):
        """Test retrieving decision history without filters."""
        with patch("finance_feedback_engine.core.DecisionEngine"), \
             patch("finance_feedback_engine.core.AlphaVantageProvider"), \
             patch("finance_feedback_engine.core.HistoricalDataProvider"), \
             patch("finance_feedback_engine.data_providers.unified_data_provider.UnifiedDataProvider"), \
             patch("finance_feedback_engine.core.validate_at_startup"), \
             patch("finance_feedback_engine.core.validate_credentials"), \
             patch("finance_feedback_engine.core.validate_and_warn"), \
             patch("finance_feedback_engine.core.ensure_models_installed"):
            
            from finance_feedback_engine.core import FinanceFeedbackEngine
            
            config = {
                "alpha_vantage_api_key": "test",
                "trading_platform": "mock",
                "platform_credentials": {},
                "persistence": {"backend": "sqlite", "db_path": ":memory:"},
                "is_backtest": False,
            }
            
            engine = FinanceFeedbackEngine(config)
            engine.decision_store = Mock()
            engine.decision_store.get_decisions = Mock(return_value=[])
            
            history = engine.get_decision_history(limit=5)
            
            assert isinstance(history, list)
            engine.decision_store.get_decisions.assert_called_once_with(asset_pair=None, limit=5)

    def test_get_decision_history_with_filter(self):
        """Test retrieving filtered decision history."""
        with patch("finance_feedback_engine.core.DecisionEngine"), \
             patch("finance_feedback_engine.core.AlphaVantageProvider"), \
             patch("finance_feedback_engine.core.HistoricalDataProvider"), \
             patch("finance_feedback_engine.data_providers.unified_data_provider.UnifiedDataProvider"), \
             patch("finance_feedback_engine.core.validate_at_startup"), \
             patch("finance_feedback_engine.core.validate_credentials"), \
             patch("finance_feedback_engine.core.validate_and_warn"), \
             patch("finance_feedback_engine.core.ensure_models_installed"):
            
            from finance_feedback_engine.core import FinanceFeedbackEngine
            
            config = {
                "alpha_vantage_api_key": "test",
                "trading_platform": "mock",
                "platform_credentials": {},
                "persistence": {"backend": "sqlite", "db_path": ":memory:"},
                "is_backtest": False,
            }
            
            engine = FinanceFeedbackEngine(config)
            engine.decision_store = Mock()
            engine.decision_store.get_decisions = Mock(return_value=[{"asset_pair": "BTCUSD"}])
            
            history = engine.get_decision_history(asset_pair="BTCUSD", limit=10)
            
            assert len(history) > 0
            engine.decision_store.get_decisions.assert_called_once_with(asset_pair="BTCUSD", limit=10)

    def test_select_fallback_provider_first_non_local(self):
        """Test _select_fallback_provider chooses first non-local provider."""
        with patch("finance_feedback_engine.core.DecisionEngine"), \
             patch("finance_feedback_engine.core.AlphaVantageProvider"), \
             patch("finance_feedback_engine.core.HistoricalDataProvider"), \
             patch("finance_feedback_engine.data_providers.unified_data_provider.UnifiedDataProvider"), \
             patch("finance_feedback_engine.core.validate_at_startup"), \
             patch("finance_feedback_engine.core.validate_credentials"), \
             patch("finance_feedback_engine.core.validate_and_warn"), \
             patch("finance_feedback_engine.core.ensure_models_installed"):
            
            from finance_feedback_engine.core import FinanceFeedbackEngine
            
            config = {
                "alpha_vantage_api_key": "test",
                "trading_platform": "mock",
                "platform_credentials": {},
                "persistence": {"backend": "sqlite", "db_path": ":memory:"},
                "is_backtest": False,
            }
            
            engine = FinanceFeedbackEngine(config)
            
            # Test with cloud provider available
            fallback = engine._select_fallback_provider(["local", "claude", "openai"])
            assert fallback == "claude"
            
            # Test with only local
            fallback = engine._select_fallback_provider(["local"])
            assert fallback is None
            
            # Test with empty list
            fallback = engine._select_fallback_provider([])
            assert fallback is None

    def test_collect_circuit_breaker_issues_closed_state(self):
        """Test _collect_circuit_breaker_issues with CLOSED circuits."""
        with patch("finance_feedback_engine.core.DecisionEngine"), \
             patch("finance_feedback_engine.core.AlphaVantageProvider"), \
             patch("finance_feedback_engine.core.HistoricalDataProvider"), \
             patch("finance_feedback_engine.data_providers.unified_data_provider.UnifiedDataProvider"), \
             patch("finance_feedback_engine.core.validate_at_startup"), \
             patch("finance_feedback_engine.core.validate_credentials"), \
             patch("finance_feedback_engine.core.validate_and_warn"), \
             patch("finance_feedback_engine.core.ensure_models_installed"):
            
            from finance_feedback_engine.core import FinanceFeedbackEngine
            
            config = {
                "alpha_vantage_api_key": "test",
                "trading_platform": "mock",
                "platform_credentials": {},
                "persistence": {"backend": "sqlite", "db_path": ":memory:"},
                "is_backtest": False,
            }
            
            engine = FinanceFeedbackEngine(config)
            
            # CLOSED circuits should not generate issues
            stats = {
                "healthy_provider": {
                    "state": "CLOSED",
                    "last_failure_time": None,
                    "failure_count": 0,
                }
            }
            
            issues = []
            engine._collect_circuit_breaker_issues("test", stats, issues)
            
            assert len(issues) == 0

    def test_get_historical_data_from_lake_no_delta(self):
        """Test get_historical_data_from_lake when Delta Lake disabled."""
        with patch("finance_feedback_engine.core.DecisionEngine"), \
             patch("finance_feedback_engine.core.AlphaVantageProvider"), \
             patch("finance_feedback_engine.core.HistoricalDataProvider"), \
             patch("finance_feedback_engine.data_providers.unified_data_provider.UnifiedDataProvider"), \
             patch("finance_feedback_engine.core.validate_at_startup"), \
             patch("finance_feedback_engine.core.validate_credentials"), \
             patch("finance_feedback_engine.core.validate_and_warn"), \
             patch("finance_feedback_engine.core.ensure_models_installed"):
            
            from finance_feedback_engine.core import FinanceFeedbackEngine
            
            config = {
                "alpha_vantage_api_key": "test",
                "trading_platform": "mock",
                "platform_credentials": {},
                "persistence": {"backend": "sqlite", "db_path": ":memory:"},
                "delta_lake": {"enabled": False},
                "is_backtest": False,
            }
            
            engine = FinanceFeedbackEngine(config)
            engine.delta_lake = None
            
            result = engine.get_historical_data_from_lake("BTCUSD", "1h", 30)
            
            assert result is None
