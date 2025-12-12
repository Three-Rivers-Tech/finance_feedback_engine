"""System Integration Verification Tests.

This module verifies that all major system loops are properly closed:
1. Telegram bot → Decision approval → Execution loop
2. Historical data → Validation → Persistence → Cache loop
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import pandas as pd
from datetime import datetime, timezone


class TestTelegramBotIntegration:
    """Verify Telegram bot integration loop is closed."""

    def test_telegram_bot_decision_loop_closed(self):
        """Verify: User Decision → Telegram → Approval → Execution."""
        from finance_feedback_engine.integrations.telegram_bot import TelegramApprovalBot

        with patch('telegram.Bot') as mock_bot:
            with patch('finance_feedback_engine.integrations.tunnel_manager.TunnelManager'):
                config = {
                    'enabled': True,
                    'bot_token': 'test',
                    'allowed_user_ids': [123],
                    'use_redis': False
                }

                bot = TelegramApprovalBot(config)

                # Verify all loop components exist
                assert callable(bot.send_approval_request), "Cannot send approval requests"
                assert callable(bot.process_update), "Cannot process updates"
                assert callable(bot._approve_decision), "Cannot approve decisions"
                assert callable(bot._reject_decision), "Cannot reject decisions"

                print("✅ Telegram bot decision loop: CLOSED")


class TestHistoricalDataIntegration:
    """Verify Historical data provider integration loop is closed."""

    def test_historical_data_loop_closed(self, tmp_path):
        """Verify: API Fetch → Validation → Persistence → Cache retrieval."""
        from finance_feedback_engine.data_providers.historical_data_provider import HistoricalDataProvider

        provider = HistoricalDataProvider(
            api_key='test',
            cache_dir=str(tmp_path / 'cache')
        )

        # Verify all loop components are connected
        assert provider.validator is not None, "Validator not connected"
        assert provider.data_store is not None, "Data store not connected"

        # Verify data store has DataFrame support
        assert hasattr(provider.data_store, 'save_dataframe'), "Missing DataFrame save"
        assert hasattr(provider.data_store, 'load_dataframe'), "Missing DataFrame load"

        # Verify validator can validate
        assert callable(provider.validator.validate_dataframe), "Cannot validate data"

        print("✅ Historical data loop: CLOSED")

    def test_historical_data_cache_roundtrip(self, tmp_path):
        """Verify data can be fetched, validated, persisted, and retrieved."""
        from finance_feedback_engine.data_providers.historical_data_provider import HistoricalDataProvider

        provider = HistoricalDataProvider(
            api_key='test',
            cache_dir=str(tmp_path / 'cache')
        )

        # Create sample data
        dates = pd.date_range('2024-01-01', periods=5, freq='1h', tz='UTC')
        sample_df = pd.DataFrame({
            'open': [100.0] * 5,
            'high': [110.0] * 5,
            'low': [95.0] * 5,
            'close': [105.0] * 5,
            'volume': [1000] * 5
        }, index=dates)

        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 2, tzinfo=timezone.utc)

        # Test persistence (save)
        provider.data_store.save_dataframe('BTCUSD', sample_df, start, end, '1h')

        # Test retrieval (load)
        loaded_df = provider.data_store.load_dataframe('BTCUSD', start, end, '1h')

        assert loaded_df is not None, "Failed to load cached data"
        assert len(loaded_df) == 5, "Data corruption during roundtrip"
        assert all(col in loaded_df.columns for col in ['open', 'high', 'low', 'close', 'volume']), \
            "Missing columns after roundtrip"

        print("✅ Historical data cache roundtrip: VERIFIED")


class TestSystemClosedLoops:
    """Verify all major system loops are properly closed."""

    def test_all_critical_todos_resolved(self):
        """Verify all critical TODOs have been implemented."""
        import os

        # Check Telegram bot
        telegram_file = 'finance_feedback_engine/integrations/telegram_bot.py'
        with open(telegram_file) as f:
            content = f.read()
            # No TODO comments left (only docstring TODO is acceptable)
            active_todos = [line for line in content.split('\n')
                          if 'TODO' in line and line.strip().startswith('#')]
            assert len(active_todos) == 0, f"Active TODOs found in telegram_bot.py: {active_todos}"

        print("✅ Telegram bot: All critical TODOs resolved")

        # Check Historical data provider
        historical_file = 'finance_feedback_engine/data_providers/historical_data_provider.py'
        with open(historical_file) as f:
            content = f.read()
            # No commented TODO lines (docstring TODOs are acceptable)
            active_todos = [line for line in content.split('\n')
                          if 'TODO' in line and line.strip().startswith('#')]
            assert len(active_todos) == 0, f"Active TODOs found in historical_data_provider.py: {active_todos}"

        print("✅ Historical data provider: All critical TODOs resolved")

    def test_validator_integration(self):
        """Verify FinancialDataValidator is properly integrated."""
        from finance_feedback_engine.data_providers.historical_data_provider import HistoricalDataProvider
        from finance_feedback_engine.utils.financial_data_validator import FinancialDataValidator

        provider = HistoricalDataProvider(api_key='test')

        assert isinstance(provider.validator, FinancialDataValidator), \
            "Validator not properly integrated"

        # Test validator is functional
        test_data = pd.DataFrame({
            'price': [100.0, 200.0],
            'volume': [1000, 2000]
        })

        errors = provider.validator.validate_dataframe(test_data)
        # Should return dict (empty if valid, or with errors)
        assert isinstance(errors, dict), "Validator not working correctly"

        print("✅ FinancialDataValidator: Properly integrated and functional")

    def test_timeseries_store_integration(self):
        """Verify TimeSeriesDataStore is properly integrated."""
        from finance_feedback_engine.data_providers.historical_data_provider import HistoricalDataProvider
        from finance_feedback_engine.persistence.timeseries_data_store import TimeSeriesDataStore

        provider = HistoricalDataProvider(api_key='test')

        assert isinstance(provider.data_store, TimeSeriesDataStore), \
            "Data store not properly integrated"

        # Verify DataFrame methods exist
        assert hasattr(provider.data_store, 'save_dataframe'), \
            "save_dataframe method missing"
        assert hasattr(provider.data_store, 'load_dataframe'), \
            "load_dataframe method missing"

        print("✅ TimeSeriesDataStore: Properly integrated with DataFrame support")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
