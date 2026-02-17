"""
Integration Tests: Exit Price Recording (EXIT PRICE FIX VALIDATION)

HIGH PRIORITY: Tests for the exit price fix deployed in commit 89bb9d6.
Validates that positions close with real exit prices (not entry prices).
"""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

logger = logging.getLogger(__name__)


class TestExitPriceRecordingFix:
    """Test exit price recording fix (commit 89bb9d6)."""

    @pytest.mark.integration
    @pytest.mark.critical
    def test_exit_price_real_not_entry_price(
        self, trade_outcome_recorder, mock_unified_provider
    ):
        """
        CRITICAL: Test position closes with real exit price (not entry price).
        
        This is the core bug that was fixed - exit_price was hardcoded to entry_price.
        Now it should fetch real market price from UnifiedDataProvider.
        """
        # Setup - open position at $41,000
        entry_time = datetime.now(timezone.utc) - timedelta(minutes=5)
        open_positions = [
            {
                "product_id": "BTC-USD",
                "side": "BUY",
                "size": "0.01",
                "entry_price": "41000.00",
                "current_price": "41000.00",
                "entry_time": entry_time.isoformat(),
            }
        ]
        trade_outcome_recorder.update_positions(open_positions)

        # Mock price provider to return DIFFERENT exit price
        mock_unified_provider.get_current_price.return_value = {
            "price": "42000.00",  # Exit at $42,000 (profit!)
            "provider": "coinbase",
        }

        # Execute - close position
        outcomes = trade_outcome_recorder.update_positions([])

        # Verify exit price is DIFFERENT from entry price
        assert len(outcomes) == 1
        outcome = outcomes[0]
        
        entry_price = Decimal(outcome["entry_price"])
        exit_price = Decimal(outcome["exit_price"])
        
        # THE FIX: Exit price should NOT equal entry price
        assert exit_price != entry_price, (
            "BUG: Exit price equals entry price! "
            "This is the bug that was supposedly fixed in commit 89bb9d6."
        )
        
        # Verify correct values
        assert entry_price == Decimal("41000.00")
        assert exit_price == Decimal("42000.00")
        
        # Verify unified provider was called
        mock_unified_provider.get_current_price.assert_called_with("BTC-USD")

    @pytest.mark.integration
    @pytest.mark.critical
    def test_pnl_calculation_uses_correct_exit_price(
        self, trade_outcome_recorder, mock_unified_provider
    ):
        """
        CRITICAL: Test P&L calculation uses correct exit price.
        
        The bug caused all trades to show $0 P&L because exit_price == entry_price.
        Now P&L should reflect actual price movement.
        """
        # Setup - open position at $41,000
        entry_time = datetime.now(timezone.utc) - timedelta(minutes=5)
        open_positions = [
            {
                "product_id": "BTC-USD",
                "side": "BUY",
                "size": "0.01",
                "entry_price": "41000.00",
                "current_price": "41000.00",
                "entry_time": entry_time.isoformat(),
            }
        ]
        trade_outcome_recorder.update_positions(open_positions)

        # Mock exit price at $42,000 (profitable trade)
        mock_unified_provider.get_current_price.return_value = {
            "price": "42000.00",
            "provider": "coinbase",
        }

        # Execute - close position
        outcomes = trade_outcome_recorder.update_positions([])

        # Verify P&L calculation
        assert len(outcomes) == 1
        outcome = outcomes[0]
        
        realized_pnl = Decimal(outcome["realized_pnl"])
        
        # P&L should be ($42,000 - $41,000) * 0.01 = $10.00
        expected_pnl = (Decimal("42000.00") - Decimal("41000.00")) * Decimal("0.01")
        assert realized_pnl == expected_pnl
        assert realized_pnl == Decimal("10.00")
        
        # Verify ROI percentage
        roi_percent = Decimal(outcome["roi_percent"])
        # ROI = ($10 / $410) * 100 = 2.44%
        expected_roi = (Decimal("10.00") / Decimal("410.00")) * Decimal("100")
        assert abs(roi_percent - expected_roi) < Decimal("0.01")  # Allow rounding

    @pytest.mark.integration
    @pytest.mark.critical
    def test_fallback_to_entry_price_on_provider_failure(
        self, trade_outcome_recorder, mock_unified_provider
    ):
        """
        Test fallback to entry price when provider fails.
        
        The fix includes graceful error handling - if the price provider
        fails, it should fall back to entry price (with warning logged).
        """
        # Setup - open position
        entry_time = datetime.now(timezone.utc) - timedelta(minutes=5)
        open_positions = [
            {
                "product_id": "BTC-USD",
                "side": "BUY",
                "size": "0.01",
                "entry_price": "41000.00",
                "current_price": "41000.00",
                "entry_time": entry_time.isoformat(),
            }
        ]
        trade_outcome_recorder.update_positions(open_positions)

        # Mock provider failure
        mock_unified_provider.get_current_price.side_effect = Exception(
            "Network timeout"
        )

        # Execute - close position (should not crash)
        outcomes = trade_outcome_recorder.update_positions([])

        # Verify fallback to entry price
        assert len(outcomes) == 1
        outcome = outcomes[0]
        
        # Should fall back to entry price
        assert Decimal(outcome["exit_price"]) == Decimal(outcome["entry_price"])
        assert Decimal(outcome["exit_price"]) == Decimal("41000.00")
        
        # P&L should be zero (breakeven fallback)
        assert Decimal(outcome["realized_pnl"]) == Decimal("0.00")

    @pytest.mark.integration
    @pytest.mark.critical
    def test_fallback_when_provider_returns_none(
        self, trade_outcome_recorder, mock_unified_provider
    ):
        """Test fallback when provider returns None or empty dict."""
        # Setup - open position
        entry_time = datetime.now(timezone.utc) - timedelta(minutes=5)
        open_positions = [
            {
                "product_id": "ETH-USD",
                "side": "BUY",
                "size": "1.0",
                "entry_price": "2400.00",
                "current_price": "2400.00",
                "entry_time": entry_time.isoformat(),
            }
        ]
        trade_outcome_recorder.update_positions(open_positions)

        # Mock provider returning None (override side_effect)
        mock_unified_provider.get_current_price = MagicMock(return_value=None)

        # Execute - close position
        outcomes = trade_outcome_recorder.update_positions([])

        # Verify fallback to entry price
        assert len(outcomes) == 1
        assert Decimal(outcomes[0]["exit_price"]) == Decimal("2400.00")

    @pytest.mark.integration
    @pytest.mark.critical
    def test_multiple_positions_close_with_correct_exit_prices(
        self, trade_outcome_recorder, mock_unified_provider
    ):
        """
        Test multiple positions close with correct exit prices.
        
        The bug affected ALL positions - verify the fix works for multiple closures.
        """
        # Setup - open multiple positions
        entry_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        open_positions = [
            {
                "product_id": "BTC-USD",
                "side": "BUY",
                "size": "0.01",
                "entry_price": "41000.00",
                "current_price": "41000.00",
                "entry_time": entry_time.isoformat(),
            },
            {
                "product_id": "ETH-USD",
                "side": "BUY",
                "size": "1.0",
                "entry_price": "2400.00",
                "current_price": "2400.00",
                "entry_time": entry_time.isoformat(),
            },
        ]
        trade_outcome_recorder.update_positions(open_positions)

        # Mock different exit prices for each asset
        def mock_get_price(asset_pair):
            prices = {
                "BTC-USD": {"price": "42000.00", "provider": "coinbase"},
                "ETH-USD": {"price": "2500.00", "provider": "coinbase"},
            }
            return prices.get(asset_pair)

        mock_unified_provider.get_current_price.side_effect = mock_get_price

        # Execute - close all positions
        outcomes = trade_outcome_recorder.update_positions([])

        # Verify both positions closed with correct exit prices
        assert len(outcomes) == 2
        
        # Find outcomes by product
        btc_outcome = next(o for o in outcomes if o["product"] == "BTC-USD")
        eth_outcome = next(o for o in outcomes if o["product"] == "ETH-USD")
        
        # BTC: $41,000 -> $42,000
        assert Decimal(btc_outcome["entry_price"]) == Decimal("41000.00")
        assert Decimal(btc_outcome["exit_price"]) == Decimal("42000.00")
        assert Decimal(btc_outcome["realized_pnl"]) == Decimal("10.00")
        
        # ETH: $2,400 -> $2,500
        assert Decimal(eth_outcome["entry_price"]) == Decimal("2400.00")
        assert Decimal(eth_outcome["exit_price"]) == Decimal("2500.00")
        assert Decimal(eth_outcome["realized_pnl"]) == Decimal("100.00")

    @pytest.mark.integration
    def test_exit_price_provider_logged(
        self, trade_outcome_recorder, mock_unified_provider, caplog
    ):
        """Test that exit price provider is logged."""
        # Setup
        entry_time = datetime.now(timezone.utc) - timedelta(minutes=5)
        open_positions = [
            {
                "product_id": "BTC-USD",
                "side": "BUY",
                "size": "0.01",
                "entry_price": "41000.00",
                "current_price": "41000.00",
                "entry_time": entry_time.isoformat(),
            }
        ]
        trade_outcome_recorder.update_positions(open_positions)

        # Mock price with provider info
        mock_unified_provider.get_current_price.return_value = {
            "price": "42000.00",
            "provider": "coinbase",
        }

        # Execute
        with caplog.at_level(logging.INFO):
            outcomes = trade_outcome_recorder.update_positions([])

        # Verify provider was logged
        assert any("coinbase" in record.message for record in caplog.records)
        assert any("42000" in record.message for record in caplog.records)


class TestExitPriceEdgeCases:
    """Test edge cases in exit price recording."""

    @pytest.mark.integration
    def test_short_position_exit_price(
        self, trade_outcome_recorder, mock_unified_provider
    ):
        """Test exit price recording for SHORT positions."""
        # Setup - short position (profit when price falls)
        entry_time = datetime.now(timezone.utc) - timedelta(minutes=5)
        open_positions = [
            {
                "instrument": "EUR_USD",
                "side": "SHORT",
                "units": "1000",
                "price": "1.0850",  # Entry price
                "current_price": "1.0850",
                "opened_at": entry_time.isoformat(),
            }
        ]
        trade_outcome_recorder.update_positions(open_positions)

        # Mock exit price lower than entry (profitable short)
        # Reset side_effect from fixture so this explicit return is used.
        mock_unified_provider.get_current_price = MagicMock(return_value={
            "price": "1.0800",  # Price fell
            "provider": "oanda",
        })

        # Execute
        outcomes = trade_outcome_recorder.update_positions([])

        # Verify
        assert len(outcomes) == 1
        outcome = outcomes[0]
        
        entry_price = Decimal(outcome["entry_price"])
        exit_price = Decimal(outcome["exit_price"])
        realized_pnl = Decimal(outcome["realized_pnl"])
        
        # Exit price should be different (lower)
        assert exit_price != entry_price
        assert exit_price == Decimal("1.0800")
        assert entry_price == Decimal("1.0850")
        
        # P&L should be positive (profitable short)
        # SHORT: (entry - exit) * size = (1.0850 - 1.0800) * 1000 = 5.00
        assert realized_pnl > 0
        assert realized_pnl == Decimal("5.00")

    @pytest.mark.integration
    def test_recorder_without_unified_provider(self, temp_data_dir):
        """Test recorder without unified_provider (backward compatibility)."""
        from finance_feedback_engine.monitoring.trade_outcome_recorder import (
            TradeOutcomeRecorder,
        )

        # Setup - recorder WITHOUT unified_provider
        recorder = TradeOutcomeRecorder(
            data_dir=str(temp_data_dir),
            use_async=False,
            unified_provider=None,  # No provider
        )

        # Open position
        entry_time = datetime.now(timezone.utc) - timedelta(minutes=5)
        open_positions = [
            {
                "product_id": "BTC-USD",
                "side": "BUY",
                "size": "0.01",
                "entry_price": "41000.00",
                "current_price": "41000.00",
                "entry_time": entry_time.isoformat(),
            }
        ]
        recorder.update_positions(open_positions)

        # Execute - close position
        outcomes = recorder.update_positions([])

        # Verify fallback to entry price (backward compatible)
        assert len(outcomes) == 1
        assert Decimal(outcomes[0]["exit_price"]) == Decimal("41000.00")
        assert Decimal(outcomes[0]["realized_pnl"]) == Decimal("0.00")

    @pytest.mark.integration
    def test_exit_price_with_price_slippage(
        self, trade_outcome_recorder, mock_unified_provider
    ):
        """Test exit price recording with significant price slippage."""
        # Setup - open position
        entry_time = datetime.now(timezone.utc) - timedelta(seconds=30)
        open_positions = [
            {
                "product_id": "BTC-USD",
                "side": "BUY",
                "size": "0.01",
                "entry_price": "41000.00",
                "current_price": "41000.00",
                "entry_time": entry_time.isoformat(),
            }
        ]
        trade_outcome_recorder.update_positions(open_positions)

        # Mock significant slippage (5% price drop in 30 seconds)
        # Reset side_effect from fixture so this explicit return is used.
        mock_unified_provider.get_current_price = MagicMock(return_value={
            "price": "38950.00",  # 5% drop
            "provider": "coinbase",
        })

        # Execute
        outcomes = trade_outcome_recorder.update_positions([])

        # Verify slippage recorded correctly
        assert len(outcomes) == 1
        outcome = outcomes[0]
        
        # Large loss recorded
        realized_pnl = Decimal(outcome["realized_pnl"])
        expected_pnl = (Decimal("38950.00") - Decimal("41000.00")) * Decimal("0.01")
        assert realized_pnl == expected_pnl
        assert realized_pnl == Decimal("-20.50")  # Loss
        
        # ROI is negative
        roi_percent = Decimal(outcome["roi_percent"])
        assert roi_percent < 0
