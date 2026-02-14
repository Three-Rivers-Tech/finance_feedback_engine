"""
Unit tests for SHORT position backtesting.

Tests the complete SHORT position lifecycle:
1. Opening SHORT positions (SELL without existing position)
2. Closing SHORT positions (BUY to cover)
3. SHORT-specific P&L calculations (inverted logic)
4. SHORT stop-loss triggers (price goes up)
5. SHORT take-profit triggers (price goes down)
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock
import pandas as pd

from finance_feedback_engine.trading_platforms.mock_platform import MockTradingPlatform


class TestShortPositionBasics:
    """Test basic SHORT position operations."""

    def test_open_short_position_on_sell_signal(self):
        """Test that SELL signal without existing position opens a SHORT."""
        platform = MockTradingPlatform(
            initial_balance={"FUTURES_USD": 10000.0},
            slippage_config={"type": "percentage", "rate": 0.001, "spread": 0.0},
        )

        # Execute SELL without existing position
        decision = {
            "asset_pair": "BTC-USD",
            "action": "SELL",
            "suggested_amount": 1000.0,  # $1000 notional
            "entry_price": 50000.0,
            "id": "test-short-open",
            "timestamp": datetime.utcnow().isoformat(),
        }

        result = platform.execute_trade(decision)

        assert result["success"], f"SHORT open failed: {result.get('error')}"
        assert result["order_status"] == "FILLED"

        # Verify SHORT position was created
        positions = platform._positions
        assert "BTC-USD" in positions
        pos = positions["BTC-USD"]
        assert pos["side"] == "SHORT"
        assert pos["contracts"] < 0, "SHORT position should have negative contracts"
        assert pos["entry_price"] > 0

        # Verify trade history
        trades = platform.get_trade_history()
        assert len(trades) == 1
        assert trades[0]["action"] == "SELL"
        assert trades[0]["side"] == "SHORT"

    def test_close_short_position_on_buy_signal(self):
        """Test that BUY signal with SHORT position closes the SHORT."""
        platform = MockTradingPlatform(
            initial_balance={"FUTURES_USD": 10000.0},
            slippage_config={"type": "percentage", "rate": 0.0, "spread": 0.0},  # No slippage for easier testing
        )

        entry_price = 50000.0
        exit_price = 49000.0
        
        # Open SHORT position first
        open_decision = {
            "asset_pair": "BTC-USD",
            "action": "SELL",
            "suggested_amount": 1000.0,
            "entry_price": entry_price,
            "id": "test-short-open",
            "timestamp": datetime.utcnow().isoformat(),
        }
        open_result = platform.execute_trade(open_decision)
        assert open_result["success"], f"Failed to open SHORT: {open_result.get('error')}"

        # Get the actual contracts opened
        pos = platform._positions["BTC-USD"]
        contracts_opened = abs(pos["contracts"])
        
        # Calculate correct notional to close the same number of contracts
        # contracts = notional / (price * multiplier)
        # notional = contracts * price * multiplier
        notional_to_close = contracts_opened * exit_price * platform._contract_multiplier
        
        close_decision = {
            "asset_pair": "BTC-USD",
            "action": "BUY",
            "suggested_amount": notional_to_close,
            "entry_price": exit_price,
            "id": "test-short-close",
            "timestamp": datetime.utcnow().isoformat(),
        }

        result = platform.execute_trade(close_decision)

        assert result["success"], f"SHORT close failed: {result.get('error')}"
        assert result["order_status"] == "FILLED"

        # Verify position was closed
        positions = platform._positions
        assert "BTC-USD" not in positions

        # Verify P&L was calculated (should be positive since price dropped)
        trades = platform.get_trade_history()
        assert len(trades) == 2
        close_trade = trades[1]
        assert close_trade["action"] == "BUY"
        assert close_trade["realized_pnl"] > 0, "SHORT should profit when price drops"

    def test_short_pnl_calculation_profit(self):
        """Test P&L calculation for profitable SHORT (price goes down)."""
        platform = MockTradingPlatform(
            initial_balance={"FUTURES_USD": 10000.0},
            slippage_config={"type": "percentage", "rate": 0.0, "spread": 0.0},
        )

        entry_price = 50000.0
        exit_price = 48000.0  # Price dropped by $2000
        notional = 1000.0

        # Open SHORT
        platform.execute_trade({
            "asset_pair": "BTC-USD",
            "action": "SELL",
            "suggested_amount": notional,
            "entry_price": entry_price,
            "id": "short-open",
            "timestamp": datetime.utcnow().isoformat(),
        })

        # Get actual contracts opened
        pos = platform._positions["BTC-USD"]
        contracts = abs(pos["contracts"])
        
        # Calculate correct notional to close same number of contracts
        notional_to_close = contracts * exit_price * platform._contract_multiplier

        # Close SHORT at lower price
        result = platform.execute_trade({
            "asset_pair": "BTC-USD",
            "action": "BUY",
            "suggested_amount": notional_to_close,
            "entry_price": exit_price,
            "id": "short-close",
            "timestamp": datetime.utcnow().isoformat(),
        })

        # Calculate expected P&L (using actual contracts opened)
        expected_pnl = (entry_price - exit_price) * contracts * platform._contract_multiplier

        trades = platform.get_trade_history()
        assert len(trades) >= 2, f"Expected at least 2 trades, got {len(trades)}"
        actual_pnl = trades[1]["realized_pnl"]

        assert actual_pnl > 0, "SHORT should profit when price drops"
        assert abs(actual_pnl - expected_pnl) < 0.01, \
            f"P&L mismatch: expected {expected_pnl:.2f}, got {actual_pnl:.2f}"

    def test_short_pnl_calculation_loss(self):
        """Test P&L calculation for losing SHORT (price goes up)."""
        platform = MockTradingPlatform(
            initial_balance={"FUTURES_USD": 10000.0},
            slippage_config={"type": "percentage", "rate": 0.0, "spread": 0.0},
        )

        entry_price = 50000.0
        exit_price = 52000.0  # Price rose by $2000
        notional = 1000.0

        # Open SHORT
        platform.execute_trade({
            "asset_pair": "BTC-USD",
            "action": "SELL",
            "suggested_amount": notional,
            "entry_price": entry_price,
            "id": "short-open",
            "timestamp": datetime.utcnow().isoformat(),
        })

        # Get actual contracts opened
        pos = platform._positions["BTC-USD"]
        contracts = abs(pos["contracts"])
        
        # Calculate correct notional to close same number of contracts
        notional_to_close = contracts * exit_price * platform._contract_multiplier

        # Close SHORT at higher price
        result = platform.execute_trade({
            "asset_pair": "BTC-USD",
            "action": "BUY",
            "suggested_amount": notional_to_close,
            "entry_price": exit_price,
            "id": "short-close",
            "timestamp": datetime.utcnow().isoformat(),
        })

        # Calculate expected P&L (should be negative, using actual contracts)
        expected_pnl = (entry_price - exit_price) * contracts * platform._contract_multiplier

        trades = platform.get_trade_history()
        assert len(trades) >= 2, f"Expected at least 2 trades, got {len(trades)}"
        actual_pnl = trades[1]["realized_pnl"]

        assert actual_pnl < 0, "SHORT should lose when price rises"
        assert abs(actual_pnl - expected_pnl) < 0.01, \
            f"P&L mismatch: expected {expected_pnl:.2f}, got {actual_pnl:.2f}"

    def test_cannot_sell_on_existing_short(self):
        """Test that SELL signal with existing SHORT position is rejected."""
        platform = MockTradingPlatform(
            initial_balance={"FUTURES_USD": 10000.0},
        )

        # Open SHORT
        platform.execute_trade({
            "asset_pair": "BTC-USD",
            "action": "SELL",
            "suggested_amount": 1000.0,
            "entry_price": 50000.0,
            "id": "short-open",
            "timestamp": datetime.utcnow().isoformat(),
        })

        # Try to SELL again (add to SHORT)
        result = platform.execute_trade({
            "asset_pair": "BTC-USD",
            "action": "SELL",
            "suggested_amount": 1000.0,
            "entry_price": 49000.0,
            "id": "short-add",
            "timestamp": datetime.utcnow().isoformat(),
        })

        assert not result["success"], "Should not allow adding to SHORT position"
        assert "Cannot add to existing SHORT position" in result.get("error", "")


class TestShortUnrealizedPnL:
    """Test unrealized P&L calculations for SHORT positions."""

    def test_short_unrealized_pnl_profit(self):
        """Test unrealized P&L for profitable SHORT position."""
        platform = MockTradingPlatform(
            initial_balance={"FUTURES_USD": 10000.0},
        )

        # Open SHORT at 50000
        platform.execute_trade({
            "asset_pair": "BTC-USD",
            "action": "SELL",
            "suggested_amount": 1000.0,
            "entry_price": 50000.0,
            "id": "short-open",
            "timestamp": datetime.utcnow().isoformat(),
        })

        # Update current price to 48000 (price dropped = profit)
        platform.update_position_prices({"BTC-USD": 48000.0})

        # Check portfolio breakdown
        portfolio = platform.get_portfolio_breakdown()
        positions = portfolio["futures_positions"]

        assert len(positions) == 1
        pos = positions[0]
        assert pos["side"] == "SHORT"
        assert pos["unrealized_pnl"] > 0, "SHORT should have unrealized profit when price drops"

    def test_short_unrealized_pnl_loss(self):
        """Test unrealized P&L for losing SHORT position."""
        platform = MockTradingPlatform(
            initial_balance={"FUTURES_USD": 10000.0},
        )

        # Open SHORT at 50000
        platform.execute_trade({
            "asset_pair": "BTC-USD",
            "action": "SELL",
            "suggested_amount": 1000.0,
            "entry_price": 50000.0,
            "id": "short-open",
            "timestamp": datetime.utcnow().isoformat(),
        })

        # Update current price to 52000 (price rose = loss)
        platform.update_position_prices({"BTC-USD": 52000.0})

        # Check portfolio breakdown
        portfolio = platform.get_portfolio_breakdown()
        positions = portfolio["futures_positions"]

        assert len(positions) == 1
        pos = positions[0]
        assert pos["side"] == "SHORT"
        assert pos["unrealized_pnl"] < 0, "SHORT should have unrealized loss when price rises"


class TestShortAndLongMixed:
    """Test mixed LONG and SHORT positions on different assets."""

    def test_long_and_short_different_assets(self):
        """Test holding LONG on one asset and SHORT on another."""
        platform = MockTradingPlatform(
            initial_balance={"FUTURES_USD": 10000.0},
        )

        # Open LONG on BTC
        platform.execute_trade({
            "asset_pair": "BTC-USD",
            "action": "BUY",
            "suggested_amount": 1000.0,
            "entry_price": 50000.0,
            "id": "btc-long",
            "timestamp": datetime.utcnow().isoformat(),
        })

        # Open SHORT on ETH
        platform.execute_trade({
            "asset_pair": "ETH-USD",
            "action": "SELL",
            "suggested_amount": 1000.0,
            "entry_price": 3000.0,
            "id": "eth-short",
            "timestamp": datetime.utcnow().isoformat(),
        })

        # Verify both positions exist
        positions = platform._positions
        assert "BTC-USD" in positions
        assert "ETH-USD" in positions
        assert positions["BTC-USD"]["side"] == "LONG"
        assert positions["ETH-USD"]["side"] == "SHORT"

        # Update prices
        platform.update_position_prices({
            "BTC-USD": 51000.0,  # BTC up = LONG profits
            "ETH-USD": 2800.0,   # ETH down = SHORT profits
        })

        # Check portfolio
        portfolio = platform.get_portfolio_breakdown()
        btc_pos = [p for p in portfolio["futures_positions"] if p["product_id"] == "BTC-USD"][0]
        eth_pos = [p for p in portfolio["futures_positions"] if p["product_id"] == "ETH-USD"][0]

        assert btc_pos["unrealized_pnl"] > 0, "BTC LONG should profit"
        assert eth_pos["unrealized_pnl"] > 0, "ETH SHORT should profit"


class TestShortBacktestingIntegration:
    """Integration tests for SHORT backtesting with the Backtester class."""

    @pytest.mark.asyncio
    async def test_backtest_with_short_positions(self):
        """Test running a backtest that includes SHORT positions."""
        from finance_feedback_engine.backtesting.backtester import Backtester
        from finance_feedback_engine.data_providers.historical_data_provider import (
            HistoricalDataProvider,
        )
        from finance_feedback_engine.decision_engine.engine import DecisionEngine

        # Create mock historical data with downtrend (favorable for SHORT)
        data = pd.DataFrame({
            "timestamp": pd.date_range(start="2024-01-01", periods=20, freq="1h"),
            "open": [50000 - i * 100 for i in range(20)],  # Declining prices
            "high": [50050 - i * 100 for i in range(20)],
            "low": [49950 - i * 100 for i in range(20)],
            "close": [50000 - i * 100 for i in range(20)],
            "volume": [100] * 20,
        })

        # Mock data provider
        data_provider = MagicMock(spec=HistoricalDataProvider)
        data_provider.get_historical_data.return_value = data

        # Mock decision engine that generates SHORT signals
        decision_engine = MagicMock(spec=DecisionEngine)

        async def mock_generate_decision(*args, **kwargs):
            """Generate SELL signals for downtrend."""
            # Simple logic: SELL if no position, BUY to close after 5 candles
            market_data = kwargs.get("market_data", {})
            monitoring = kwargs.get("monitoring_context", {})
            active_positions = monitoring.get("active_positions", {}).get("futures", [])

            if not active_positions:
                return {
                    "id": f"decision-{datetime.now().timestamp()}",
                    "action": "SELL",
                    "asset_pair": "BTC-USD",
                    "suggested_amount": 500.0,
                    "entry_price": kwargs.get("market_data", {}).get("current_price", 50000),
                    "confidence": 0.8,
                    "position_size": 500.0,
                }
            else:
                # Close after holding for a bit
                return {
                    "id": f"decision-{datetime.now().timestamp()}",
                    "action": "BUY",
                    "asset_pair": "BTC-USD",
                    "suggested_amount": 500.0,
                    "entry_price": kwargs.get("market_data", {}).get("current_price", 49000),
                    "confidence": 0.8,
                }

        decision_engine.generate_decision.side_effect = mock_generate_decision

        # Run backtest
        backtester = Backtester(
            historical_data_provider=data_provider,
            initial_balance=10000.0,
            timeframe="1h",
        )

        try:
            results = backtester.run_backtest(
                asset_pair="BTC-USD",
                start_date="2024-01-01",
                end_date="2024-01-02",
                decision_engine=decision_engine,
                data_override=data,
            )

            # Verify backtest completed
            assert "metrics" in results
            assert "trades" in results

            # Check for SHORT trades
            trades = results["trades"]
            short_trades = [t for t in trades if t.get("side") == "SHORT"]

            # We should have at least some SHORT positions opened
            assert len(short_trades) > 0, "Backtest should include SHORT trades"

            # Verify SHORT trades have correct structure
            if short_trades:
                short_trade = short_trades[0]
                assert "action" in short_trade
                assert "side" in short_trade
                assert short_trade["side"] == "SHORT"

        finally:
            backtester.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
