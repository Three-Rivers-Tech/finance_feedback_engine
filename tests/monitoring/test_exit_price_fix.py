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
            assert outcome["exit_price_source"] == "provider:oanda"
            
            # P&L should be non-zero (1000 units * 0.00014 price diff)
            realized_pnl = Decimal(outcome["realized_pnl"])
            expected_pnl = (Decimal("1.19125") - Decimal("1.19111")) * Decimal("1000")
            assert realized_pnl == expected_pnl
            assert realized_pnl != Decimal("0")
            
            # ROI should be non-zero
            assert Decimal(outcome["roi_percent"]) != Decimal("0")
    
    def test_exit_price_skips_outcome_on_provider_error_without_last_price(self):
        """Verify we skip outcome instead of forcing entry==exit when provider fails."""
        mock_provider = MagicMock()
        mock_provider.get_current_price.side_effect = Exception("Provider unavailable")

        with tempfile.TemporaryDirectory() as temp_dir:
            recorder = TradeOutcomeRecorder(
                data_dir=temp_dir,
                unified_provider=mock_provider
            )

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

            outcomes = recorder.update_positions([])
            assert outcomes == []
    
    def test_exit_price_uses_last_observed_price_when_provider_has_no_data(self):
        """Verify fallback uses last observed price (not entry price) when provider returns None."""
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
                    "last_price": Decimal("3515.00"),
                }
            }

            outcomes = recorder.update_positions([])

            assert len(outcomes) == 1
            outcome = outcomes[0]
            assert outcome["exit_price"] == "3515.00"
            assert outcome["exit_price_source"] == "state:last_price"
            assert Decimal(outcome["realized_pnl"]) > Decimal("0")
    
    def test_exit_price_without_provider_skips_without_last_price(self):
        """Verify no-provider path does not fabricate zero-P&L outcomes."""
        with tempfile.TemporaryDirectory() as temp_dir:
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
            assert outcomes == []
    
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

    def test_regression_market_move_persisted_close_has_distinct_exit_and_nonzero_pnl(self):
        """Regression: persisted close should reflect market move and non-zero realized P&L."""
        mock_provider = MagicMock()
        mock_provider.get_current_price.return_value = {
            "price": 1.18525,
            "provider": "oanda",
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            recorder = TradeOutcomeRecorder(data_dir=temp_dir, unified_provider=mock_provider)
            recorder.open_positions = {
                "EUR_USD_LONG": {
                    "trade_id": "regression-eurusd-1",
                    "product": "EUR_USD",
                    "side": "LONG",
                    "entry_time": "2026-02-17T17:00:00+00:00",
                    "entry_price": Decimal("1.18296"),
                    "entry_size": Decimal("1000"),
                }
            }

            outcomes = recorder.update_positions([])
            assert len(outcomes) == 1

            outcome = outcomes[0]
            assert Decimal(outcome["exit_price"]) != Decimal(outcome["entry_price"])
            assert Decimal(outcome["realized_pnl"]) != Decimal("0")
            assert outcome["exit_price_source"] == "provider:oanda"

            jsonl_files = list((Path(temp_dir) / "trade_outcomes").glob("*.jsonl"))
            assert len(jsonl_files) == 1
            saved_outcome = json.loads(jsonl_files[0].read_text().splitlines()[0])
            assert Decimal(saved_outcome["exit_price"]) == Decimal("1.18525")
            assert Decimal(saved_outcome["entry_price"]) == Decimal("1.18296")
            assert Decimal(saved_outcome["realized_pnl"]) == Decimal("2.29000")

    def test_alert_logged_on_consecutive_flat_closures(self, caplog):
        """Alert when entry==exit persists for multiple consecutive outcomes."""
        recorder = TradeOutcomeRecorder(data_dir=tempfile.mkdtemp(), unified_provider=None)

        base = {
            "exit_time": datetime.now(timezone.utc).isoformat(),
            "entry_size": "1",
            "exit_size": "1",
            "side": "BUY",
            "fees": "0",
            "holding_duration_seconds": 1,
            "roi_percent": "0",
            "exit_price_source": "state:last_price",
        }

        with caplog.at_level("ERROR"):
            for i in range(3):
                outcome = {
                    **base,
                    "trade_id": f"flat-{i}",
                    "product": "EUR_USD",
                    "entry_time": "2026-02-17T17:00:00+00:00",
                    "entry_price": "1.1000",
                    "exit_price": "1.1000",
                    "realized_pnl": "0",
                }
                recorder._save_outcome(outcome)

        assert any("consecutive flat closures" in record.message for record in caplog.records)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
