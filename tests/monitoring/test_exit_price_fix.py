"""
Test suite for FFE Exit Price Fix (verifying real-time exit price recording).

This test validates that TradeOutcomeRecorder fetches actual market prices
when positions close, rather than using the entry price placeholder.
"""

import pytest
from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock
from pathlib import Path
import tempfile
import json

from finance_feedback_engine.monitoring.trade_outcome_recorder import TradeOutcomeRecorder


class TestExitPriceFix:
    """Test suite for exit price fix using UnifiedDataProvider."""
    
    def test_exit_price_uses_unified_provider(self):
        """Verify exit price fetched from unified_provider, not entry price."""
        # Create mock unified provider
        mock_provider = MagicMock()
        mock_provider.get_current_price.return_value = {
            "price": 1.19125,
            "provider": "oanda",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Create recorder with temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            recorder = TradeOutcomeRecorder(
                data_dir=temp_dir,
                unified_provider=mock_provider
            )
            
            # Simulate an open position
            recorder.open_positions = {
                "EUR_USD_LONG": {
                    "trade_id": "test-trade-123",
                    "product": "EUR_USD",
                    "side": "LONG",
                    "entry_time": "2026-02-16T20:00:00+00:00",
                    "entry_price": Decimal("1.19111"),
                    "entry_size": Decimal("1000"),
                }
            }
            
            # Update with empty positions (triggers close detection)
            outcomes = recorder.update_positions([])
            
            # Verify unified provider was called
            mock_provider.get_current_price.assert_called_once_with("EUR_USD")
            
            # Verify outcome was created with real exit price
            assert len(outcomes) == 1
            outcome = outcomes[0]
            
            # Exit price should be the market price, NOT entry price
            assert outcome["exit_price"] == "1.19125"
            assert outcome["exit_price"] != outcome["entry_price"]
            
            # P&L should be non-zero (1000 units * 0.00014 price diff)
            realized_pnl = Decimal(outcome["realized_pnl"])
            expected_pnl = (Decimal("1.19125") - Decimal("1.19111")) * Decimal("1000")
            assert realized_pnl == expected_pnl
            assert realized_pnl != Decimal("0")
            
            # ROI should be non-zero
            assert Decimal(outcome["roi_percent"]) != Decimal("0")
    
    def test_exit_price_fallback_on_provider_error(self):
        """Verify fallback to entry price when provider fails."""
        # Create mock unified provider that raises an exception
        mock_provider = MagicMock()
        mock_provider.get_current_price.side_effect = Exception("Provider unavailable")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            recorder = TradeOutcomeRecorder(
                data_dir=temp_dir,
                unified_provider=mock_provider
            )
            
            # Simulate an open position
            recorder.open_positions = {
                "BTC-USD_LONG": {
                    "trade_id": "test-trade-456",
                    "product": "BTC-USD",
                    "side": "LONG",
                    "entry_time": "2026-02-16T20:00:00+00:00",
                    "entry_price": Decimal("69500.00"),
                    "entry_size": Decimal("0.001"),
                }
            }
            
            # Update with empty positions
            outcomes = recorder.update_positions([])
            
            # Verify fallback behavior
            assert len(outcomes) == 1
            outcome = outcomes[0]
            
            # Should fall back to entry price
            assert outcome["exit_price"] == outcome["entry_price"]
            assert outcome["exit_price"] == "69500.00"
            
            # P&L should be zero (fallback behavior)
            assert Decimal(outcome["realized_pnl"]) == Decimal("0")
    
    def test_exit_price_fallback_on_no_price_data(self):
        """Verify fallback when provider returns None or empty."""
        mock_provider = MagicMock()
        mock_provider.get_current_price.return_value = None
        
        with tempfile.TemporaryDirectory() as temp_dir:
            recorder = TradeOutcomeRecorder(
                data_dir=temp_dir,
                unified_provider=mock_provider
            )
            
            recorder.open_positions = {
                "ETH-USD_LONG": {
                    "trade_id": "test-trade-789",
                    "product": "ETH-USD",
                    "side": "LONG",
                    "entry_time": "2026-02-16T20:00:00+00:00",
                    "entry_price": Decimal("3500.00"),
                    "entry_size": Decimal("0.1"),
                }
            }
            
            outcomes = recorder.update_positions([])
            
            assert len(outcomes) == 1
            outcome = outcomes[0]
            
            # Should fall back to entry price
            assert outcome["exit_price"] == "3500.00"
            assert Decimal(outcome["realized_pnl"]) == Decimal("0")
    
    def test_exit_price_without_provider(self):
        """Verify backward compatibility when no provider is passed."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create recorder WITHOUT unified_provider
            recorder = TradeOutcomeRecorder(
                data_dir=temp_dir,
                unified_provider=None
            )
            
            recorder.open_positions = {
                "EUR_USD_LONG": {
                    "trade_id": "test-trade-999",
                    "product": "EUR_USD",
                    "side": "LONG",
                    "entry_time": "2026-02-16T20:00:00+00:00",
                    "entry_price": Decimal("1.19111"),
                    "entry_size": Decimal("1000"),
                }
            }
            
            outcomes = recorder.update_positions([])
            
            assert len(outcomes) == 1
            outcome = outcomes[0]
            
            # Should use entry price (backward compatible behavior)
            assert outcome["exit_price"] == "1.19111"
            assert Decimal(outcome["realized_pnl"]) == Decimal("0")
    
    def test_exit_price_recorded_to_file(self):
        """Verify outcome with real exit price is persisted to JSONL."""
        mock_provider = MagicMock()
        mock_provider.get_current_price.return_value = {
            "price": 1.19150,
            "provider": "coinbase",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            recorder = TradeOutcomeRecorder(
                data_dir=temp_dir,
                unified_provider=mock_provider
            )
            
            recorder.open_positions = {
                "EUR_USD_LONG": {
                    "trade_id": "test-trade-file",
                    "product": "EUR_USD",
                    "side": "LONG",
                    "entry_time": "2026-02-16T20:00:00+00:00",
                    "entry_price": Decimal("1.19111"),
                    "entry_size": Decimal("1000"),
                }
            }
            
            outcomes = recorder.update_positions([])
            
            # Verify file was created
            outcomes_dir = Path(temp_dir) / "trade_outcomes"
            assert outcomes_dir.exists()
            
            # Find the JSONL file
            jsonl_files = list(outcomes_dir.glob("*.jsonl"))
            assert len(jsonl_files) == 1
            
            # Read and verify content
            with open(jsonl_files[0], "r") as f:
                line = f.readline()
                saved_outcome = json.loads(line)
            
            # Verify real exit price was saved
            assert Decimal(saved_outcome["exit_price"]) == Decimal("1.19150")
            assert Decimal(saved_outcome["entry_price"]) == Decimal("1.19111")
            assert Decimal(saved_outcome["realized_pnl"]) > Decimal("0")
    
    def test_multiple_positions_closing_simultaneously(self):
        """Test that multiple positions get correct exit prices."""
        mock_provider = MagicMock()
        
        # Different prices for different assets
        def mock_get_price(product):
            prices = {
                "EUR_USD": {"price": 1.19125, "provider": "oanda"},
                "BTC-USD": {"price": 69550.00, "provider": "coinbase"},
                "ETH-USD": {"price": 3515.00, "provider": "coinbase"},
            }
            return prices.get(product)
        
        mock_provider.get_current_price.side_effect = mock_get_price
        
        with tempfile.TemporaryDirectory() as temp_dir:
            recorder = TradeOutcomeRecorder(
                data_dir=temp_dir,
                unified_provider=mock_provider
            )
            
            # Multiple open positions
            recorder.open_positions = {
                "EUR_USD_LONG": {
                    "trade_id": "trade-1",
                    "product": "EUR_USD",
                    "side": "LONG",
                    "entry_time": "2026-02-16T20:00:00+00:00",
                    "entry_price": Decimal("1.19111"),
                    "entry_size": Decimal("1000"),
                },
                "BTC-USD_LONG": {
                    "trade_id": "trade-2",
                    "product": "BTC-USD",
                    "side": "LONG",
                    "entry_time": "2026-02-16T20:05:00+00:00",
                    "entry_price": Decimal("69500.00"),
                    "entry_size": Decimal("0.001"),
                },
                "ETH-USD_LONG": {
                    "trade_id": "trade-3",
                    "product": "ETH-USD",
                    "side": "LONG",
                    "entry_time": "2026-02-16T20:10:00+00:00",
                    "entry_price": Decimal("3500.00"),
                    "entry_size": Decimal("0.1"),
                },
            }
            
            # Close all positions
            outcomes = recorder.update_positions([])
            
            # Verify all outcomes have real exit prices
            assert len(outcomes) == 3
            
            outcomes_by_product = {o["product"]: o for o in outcomes}
            
            # EUR_USD
            assert Decimal(outcomes_by_product["EUR_USD"]["exit_price"]) == Decimal("1.19125")
            assert Decimal(outcomes_by_product["EUR_USD"]["realized_pnl"]) > Decimal("0")
            
            # BTC-USD
            assert Decimal(outcomes_by_product["BTC-USD"]["exit_price"]) == Decimal("69550.00")
            assert Decimal(outcomes_by_product["BTC-USD"]["realized_pnl"]) > Decimal("0")
            
            # ETH-USD
            assert Decimal(outcomes_by_product["ETH-USD"]["exit_price"]) == Decimal("3515.00")
            assert Decimal(outcomes_by_product["ETH-USD"]["realized_pnl"]) > Decimal("0")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
