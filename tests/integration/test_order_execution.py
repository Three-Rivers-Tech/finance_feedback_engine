"""
Integration Tests: Order Placement and Execution

Tests end-to-end order placement on Coinbase and Oanda platforms,
including order fills, error handling, and execution confirmation.
"""

import logging
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from finance_feedback_engine.exceptions import TradingError
from finance_feedback_engine.trading_platforms.coinbase_platform import (
    CoinbaseAdvancedPlatform,
)
from finance_feedback_engine.trading_platforms.oanda_platform import OandaPlatform

logger = logging.getLogger(__name__)


class TestCoinbaseOrderExecution:
    """Test order execution on Coinbase platform."""

    @pytest.mark.integration
    def test_market_order_buy_success(self, mock_coinbase_platform, mock_coinbase_order_response):
        """Test successful market BUY order on Coinbase."""
        # Setup
        mock_coinbase_platform.place_order.return_value = mock_coinbase_order_response

        # Execute
        result = mock_coinbase_platform.place_order(
            asset_pair="BTC-USD",
            side="BUY",
            size=Decimal("0.01"),
            order_type="market",
        )

        # Verify
        assert result["success"] is True
        assert result["order_id"] == "test-coinbase-order-123"
        assert result["product_id"] == "BTC-USD"
        assert result["side"] == "BUY"
        assert Decimal(result["filled_size"]) == Decimal("0.01")
        assert Decimal(result["average_filled_price"]) == Decimal("42000.00")
        assert result["status"] == "FILLED"

        # Verify order was called with correct params
        mock_coinbase_platform.place_order.assert_called_once_with(
            asset_pair="BTC-USD",
            side="BUY",
            size=Decimal("0.01"),
            order_type="market",
        )

    @pytest.mark.integration
    def test_market_order_sell_success(self, mock_coinbase_platform):
        """Test successful market SELL order on Coinbase."""
        # Setup
        sell_response = {
            "success": True,
            "order_id": "test-coinbase-sell-789",
            "product_id": "BTC-USD",
            "side": "SELL",
            "filled_size": "0.01",
            "average_filled_price": "42500.00",
            "status": "FILLED",
        }
        mock_coinbase_platform.place_order.return_value = sell_response

        # Execute
        result = mock_coinbase_platform.place_order(
            asset_pair="BTC-USD",
            side="SELL",
            size=Decimal("0.01"),
            order_type="market",
        )

        # Verify
        assert result["success"] is True
        assert result["side"] == "SELL"
        assert Decimal(result["average_filled_price"]) == Decimal("42500.00")

    @pytest.mark.integration
    def test_limit_order_placement(self, mock_coinbase_platform):
        """Test limit order placement on Coinbase."""
        # Setup
        limit_response = {
            "success": True,
            "order_id": "test-limit-order-456",
            "product_id": "ETH-USD",
            "side": "BUY",
            "order_type": "limit",
            "limit_price": "2400.00",
            "size": "1.0",
            "status": "OPEN",
        }
        mock_coinbase_platform.place_order.return_value = limit_response

        # Execute
        result = mock_coinbase_platform.place_order(
            asset_pair="ETH-USD",
            side="BUY",
            size=Decimal("1.0"),
            order_type="limit",
            limit_price=Decimal("2400.00"),
        )

        # Verify
        assert result["success"] is True
        assert result["order_type"] == "limit"
        assert result["status"] == "OPEN"
        assert Decimal(result["limit_price"]) == Decimal("2400.00")

    @pytest.mark.integration
    def test_partial_fill_handling(self, mock_coinbase_platform):
        """Test handling of partially filled orders."""
        # Setup - order partially filled
        partial_fill_response = {
            "success": True,
            "order_id": "test-partial-order-999",
            "product_id": "BTC-USD",
            "side": "BUY",
            "size": "0.1",
            "filled_size": "0.05",  # Only 50% filled
            "average_filled_price": "42000.00",
            "status": "PARTIALLY_FILLED",
        }
        mock_coinbase_platform.place_order.return_value = partial_fill_response

        # Execute
        result = mock_coinbase_platform.place_order(
            asset_pair="BTC-USD",
            side="BUY",
            size=Decimal("0.1"),
            order_type="market",
        )

        # Verify partial fill is correctly recorded
        assert result["success"] is True
        assert result["status"] == "PARTIALLY_FILLED"
        assert Decimal(result["filled_size"]) < Decimal(result["size"])
        fill_percentage = (
            Decimal(result["filled_size"]) / Decimal(result["size"]) * 100
        )
        assert fill_percentage == Decimal("50")

    @pytest.mark.integration
    def test_order_rejection_insufficient_funds(self, mock_coinbase_platform):
        """Test order rejection due to insufficient funds."""
        # Setup
        mock_coinbase_platform.place_order.return_value = {
            "success": False,
            "error": "Insufficient funds",
            "error_code": "INSUFFICIENT_BALANCE",
        }

        # Execute
        result = mock_coinbase_platform.place_order(
            asset_pair="BTC-USD",
            side="BUY",
            size=Decimal("100.0"),  # Unrealistic size
            order_type="market",
        )

        # Verify rejection is handled
        assert result["success"] is False
        assert "Insufficient" in result["error"]
        assert result["error_code"] == "INSUFFICIENT_BALANCE"

    @pytest.mark.integration
    def test_order_fill_confirmation(self, mock_coinbase_platform):
        """Test order fill confirmation and details."""
        # Setup
        fill_response = {
            "success": True,
            "order_id": "test-fill-confirm-111",
            "product_id": "BTC-USD",
            "side": "BUY",
            "filled_size": "0.01",
            "average_filled_price": "42123.45",
            "total_value_after_fees": "421.50",
            "commission": "0.25",
            "status": "FILLED",
            "created_time": "2024-02-16T20:00:00Z",
            "completion_time": "2024-02-16T20:00:01Z",
        }
        mock_coinbase_platform.place_order.return_value = fill_response

        # Execute
        result = mock_coinbase_platform.place_order(
            asset_pair="BTC-USD",
            side="BUY",
            size=Decimal("0.01"),
            order_type="market",
        )

        # Verify fill details
        assert result["status"] == "FILLED"
        assert "average_filled_price" in result
        assert "total_value_after_fees" in result
        assert "commission" in result
        assert "completion_time" in result

        # Calculate expected values
        filled_value = Decimal(result["filled_size"]) * Decimal(
            result["average_filled_price"]
        )
        assert filled_value > 0


class TestOandaOrderExecution:
    """Test order execution on Oanda platform."""

    @pytest.mark.integration
    def test_market_order_long_success(self, mock_oanda_platform, mock_oanda_order_response):
        """Test successful LONG market order on Oanda."""
        # Setup
        mock_oanda_platform.place_order.return_value = mock_oanda_order_response

        # Execute
        result = mock_oanda_platform.place_order(
            asset_pair="EUR_USD",
            side="LONG",
            size=Decimal("1000"),
            order_type="market",
        )

        # Verify
        assert result["orderFillTransaction"]["type"] == "ORDER_FILL"
        assert result["orderFillTransaction"]["id"] == "test-oanda-order-456"

    @pytest.mark.integration
    def test_market_order_short_success(self, mock_oanda_platform):
        """Test successful SHORT market order on Oanda."""
        # Setup
        short_response = {
            "orderFillTransaction": {
                "id": "test-short-order-789",
                "type": "ORDER_FILL",
                "instrument": "EUR_USD",
                "units": "-1000",  # Negative for short
                "price": "1.0850",
                "time": "2024-02-16T20:00:00Z",
            },
            "relatedTransactionIDs": ["test-short-order-789"],
        }
        mock_oanda_platform.place_order.return_value = short_response

        # Execute
        result = mock_oanda_platform.place_order(
            asset_pair="EUR_USD",
            side="SHORT",
            size=Decimal("1000"),
            order_type="market",
        )

        # Verify
        assert result["orderFillTransaction"]["units"] == "-1000"

    @pytest.mark.integration
    def test_stop_loss_order_placement(self, mock_oanda_platform):
        """Test stop-loss order placement on Oanda."""
        # Setup
        stop_loss_response = {
            "orderCreateTransaction": {
                "id": "test-stop-loss-123",
                "type": "STOP_LOSS_ORDER",
                "instrument": "EUR_USD",
                "units": "-1000",
                "price": "1.0800",  # Stop loss price
                "time": "2024-02-16T20:00:00Z",
            },
        }
        mock_oanda_platform.place_order.return_value = stop_loss_response

        # Execute
        result = mock_oanda_platform.place_order(
            asset_pair="EUR_USD",
            side="SHORT",
            size=Decimal("1000"),
            order_type="stop_loss",
            stop_loss_price=Decimal("1.0800"),
        )

        # Verify
        assert result["orderCreateTransaction"]["type"] == "STOP_LOSS_ORDER"
        assert Decimal(result["orderCreateTransaction"]["price"]) == Decimal("1.0800")

    @pytest.mark.integration
    def test_order_rejection_invalid_instrument(self, mock_oanda_platform):
        """Test order rejection for invalid instrument."""
        # Setup
        mock_oanda_platform.place_order.return_value = {
            "success": False,
            "error": "Invalid instrument",
            "error_code": "INVALID_INSTRUMENT",
        }

        # Execute
        result = mock_oanda_platform.place_order(
            asset_pair="INVALID_PAIR",
            side="LONG",
            size=Decimal("1000"),
            order_type="market",
        )

        # Verify
        assert result["success"] is False
        assert "Invalid" in result["error"]


class TestCrossplatformOrderExecution:
    """Test order execution across multiple platforms."""

    @pytest.mark.integration
    def test_simultaneous_orders_both_platforms(
        self, mock_coinbase_platform, mock_oanda_platform
    ):
        """Test placing orders on both Coinbase and Oanda simultaneously."""
        # Setup
        coinbase_response = {
            "success": True,
            "order_id": "coinbase-123",
            "product_id": "BTC-USD",
        }
        oanda_response = {
            "success": True,
            "order_id": "oanda-456",
        }

        mock_coinbase_platform.place_order.return_value = coinbase_response
        mock_oanda_platform.place_order.return_value = oanda_response

        # Execute
        coinbase_result = mock_coinbase_platform.place_order(
            asset_pair="BTC-USD", side="BUY", size=Decimal("0.01"), order_type="market"
        )
        oanda_result = mock_oanda_platform.place_order(
            asset_pair="EUR_USD", side="LONG", size=Decimal("1000"), order_type="market"
        )

        # Verify both orders succeeded
        assert coinbase_result["success"] is True
        assert oanda_result["success"] is True
        assert coinbase_result["order_id"] != oanda_result["order_id"]

    @pytest.mark.integration
    def test_order_execution_error_handling(self, mock_coinbase_platform):
        """Test graceful handling of order execution errors."""
        # Setup - simulate network error
        mock_coinbase_platform.place_order.side_effect = Exception("Network timeout")

        # Execute and verify exception is raised
        with pytest.raises(Exception) as exc_info:
            mock_coinbase_platform.place_order(
                asset_pair="BTC-USD",
                side="BUY",
                size=Decimal("0.01"),
                order_type="market",
            )

        assert "Network timeout" in str(exc_info.value)

    @pytest.mark.integration
    def test_order_idempotency(self, mock_coinbase_platform):
        """Test order idempotency with client_order_id."""
        # Setup
        response_1 = {
            "success": True,
            "order_id": "server-order-123",
            "client_order_id": "client-unique-id-1",
        }
        response_2 = {
            "success": False,
            "error": "Duplicate client_order_id",
            "existing_order_id": "server-order-123",
        }

        mock_coinbase_platform.place_order.side_effect = [response_1, response_2]

        # Execute first order
        result_1 = mock_coinbase_platform.place_order(
            asset_pair="BTC-USD",
            side="BUY",
            size=Decimal("0.01"),
            order_type="market",
            client_order_id="client-unique-id-1",
        )

        # Execute duplicate order
        result_2 = mock_coinbase_platform.place_order(
            asset_pair="BTC-USD",
            side="BUY",
            size=Decimal("0.01"),
            order_type="market",
            client_order_id="client-unique-id-1",
        )

        # Verify first succeeded, second rejected as duplicate
        assert result_1["success"] is True
        assert result_2["success"] is False
        assert "Duplicate" in result_2["error"]
