"""Integration tests for portfolio retrievers.

Tests the abstract base class and concrete implementations for each platform.
Ensures portfolio retrieval is correctly abstracted without breaking existing behavior.
"""

import logging
from unittest.mock import Mock, MagicMock

import pytest

from finance_feedback_engine.trading_platforms import (
    PortfolioRetrieverFactory,
    CoinbasePortfolioRetriever,
    OandaPortfolioRetriever,
    MockPortfolioRetriever,
)
from finance_feedback_engine.trading_platforms.portfolio_retriever import (
    PortfolioRetrievingError,
)

pytestmark = [pytest.mark.integration, pytest.mark.external_service]

logger = logging.getLogger(__name__)


class TestPortfolioRetrieverFactory:
    """Test factory registration and creation."""

    def test_factory_lists_registered_platforms(self):
        """Test that factory lists all registered platforms."""
        platforms = PortfolioRetrieverFactory.list_platforms()
        assert "coinbase" in platforms
        assert "oanda" in platforms
        assert "mock" in platforms

    def test_factory_creates_coinbase_retriever(self):
        """Test factory creates Coinbase retriever."""
        retriever = PortfolioRetrieverFactory.create("coinbase", None)
        assert isinstance(retriever, CoinbasePortfolioRetriever)
        assert retriever.platform_name == "coinbase"

    def test_factory_creates_oanda_retriever(self):
        """Test factory creates Oanda retriever."""
        retriever = PortfolioRetrieverFactory.create("oanda", None)
        assert isinstance(retriever, OandaPortfolioRetriever)
        assert retriever.platform_name == "oanda"

    def test_factory_creates_mock_retriever(self):
        """Test factory creates mock retriever."""
        retriever = PortfolioRetrieverFactory.create("mock", None)
        assert isinstance(retriever, MockPortfolioRetriever)
        assert retriever.platform_name == "mock"

    def test_factory_raises_on_unknown_platform(self):
        """Test factory raises error for unknown platform."""
        with pytest.raises(ValueError, match="No portfolio retriever registered"):
            PortfolioRetrieverFactory.create("unknown_platform", None)


class TestMockPortfolioRetriever:
    """Test mock portfolio retriever."""

    def test_retriever_initializes(self):
        """Test mock retriever initializes correctly."""
        mock_client = Mock()
        retriever = MockPortfolioRetriever(mock_client)
        assert retriever.platform_name == "mock"
        assert retriever.client == mock_client

    def test_get_account_info_raises_without_client(self):
        """Test get_account_info raises error without client."""
        retriever = MockPortfolioRetriever(None)
        with pytest.raises(PortfolioRetrievingError):
            retriever.get_account_info()

    def test_get_account_info_returns_balance_and_positions(self):
        """Test get_account_info returns expected structure."""
        mock_client = Mock()
        mock_client._balance = {"FUTURES_USD": 1000, "SPOT_USD": 500}
        mock_client._positions = {"BTCUSD": {"contracts": 1, "entry_price": 40000}}
        mock_client._contract_multiplier = 0.1

        retriever = MockPortfolioRetriever(mock_client)
        account_info = retriever.get_account_info()

        assert "balance" in account_info
        assert "positions" in account_info
        assert account_info["balance"]["FUTURES_USD"] == 1000
        assert account_info["balance"]["SPOT_USD"] == 500

    def test_parse_positions_handles_empty_positions(self):
        """Test parse_positions handles no positions."""
        mock_client = Mock()
        mock_client._balance = {}
        mock_client._positions = {}
        mock_client._contract_multiplier = 0.1

        retriever = MockPortfolioRetriever(mock_client)
        account_info = retriever.get_account_info()
        positions = retriever.parse_positions(account_info)

        assert positions == []

    def test_parse_positions_returns_position_info(self):
        """Test parse_positions returns PositionInfo objects."""
        mock_client = Mock()
        mock_client._balance = {}
        mock_client._positions = {
            "BTCUSD": {
                "contracts": 1,
                "entry_price": 40000,
                "current_price": 41000,
                "side": "LONG",
                "daily_pnl": 100,
            }
        }
        mock_client._contract_multiplier = 0.1

        retriever = MockPortfolioRetriever(mock_client)
        account_info = retriever.get_account_info()
        positions = retriever.parse_positions(account_info)

        assert len(positions) == 1
        pos = positions[0]
        assert pos.get("instrument") == "BTCUSD"
        assert pos.get("contracts") == 1
        assert pos.get("side") == "LONG"
        assert pos.get("entry_price") == 40000
        assert pos.get("current_price") == 41000

    def test_parse_holdings_returns_spot_balances(self):
        """Test parse_holdings returns spot holdings."""
        mock_client = Mock()
        mock_client._balance = {"FUTURES_USD": 1000, "SPOT_USD": 500, "SPOT_USDC": 200}
        mock_client._positions = {}
        mock_client._contract_multiplier = 0.1

        retriever = MockPortfolioRetriever(mock_client)
        account_info = retriever.get_account_info()
        holdings = retriever.parse_holdings(account_info)

        assert len(holdings) == 2
        usd_holding = [h for h in holdings if h["asset"] == "USD"][0]
        assert usd_holding["balance"] == 500
        usdc_holding = [h for h in holdings if h["asset"] == "USDC"][0]
        assert usdc_holding["balance"] == 200

    def test_assemble_result_creates_complete_breakdown(self):
        """Test assemble_result creates complete breakdown."""
        mock_client = Mock()
        mock_client._balance = {"FUTURES_USD": 1000, "SPOT_USD": 500}
        mock_client._positions = {
            "BTCUSD": {
                "contracts": 1,
                "entry_price": 40000,
                "current_price": 41000,
                "side": "LONG",
            }
        }
        mock_client._contract_multiplier = 0.1

        retriever = MockPortfolioRetriever(mock_client)
        account_info = retriever.get_account_info()
        positions = retriever.parse_positions(account_info)
        holdings = retriever.parse_holdings(account_info)
        result = retriever.assemble_result(account_info, positions, holdings)

        assert result["platform"] == "mock"
        assert "total_value_usd" in result
        assert "futures_value_usd" in result
        assert "spot_value_usd" in result
        assert "futures_positions" in result
        assert "holdings" in result
        assert result["futures_value_usd"] == 1000
        assert result["spot_value_usd"] == 500

    def test_get_portfolio_breakdown_orchestrates_steps(self):
        """Test get_portfolio_breakdown orchestrates all steps."""
        mock_client = Mock()
        mock_client._balance = {"FUTURES_USD": 1000, "SPOT_USD": 500}
        mock_client._positions = {
            "BTCUSD": {
                "contracts": 1,
                "entry_price": 40000,
                "current_price": 41000,
                "side": "LONG",
            }
        }
        mock_client._contract_multiplier = 0.1

        retriever = MockPortfolioRetriever(mock_client)
        result = retriever.get_portfolio_breakdown()

        # Verify complete result
        assert result["platform"] == "mock"
        assert result["futures_value_usd"] == 1000
        assert result["spot_value_usd"] == 500
        assert len(result["futures_positions"]) == 1
        assert len(result["holdings"]) == 1


class TestCoinbasePortfolioRetriever:
    """Test Coinbase portfolio retriever."""

    def test_retriever_initializes(self):
        """Test Coinbase retriever initializes correctly."""
        mock_client = Mock()
        retriever = CoinbasePortfolioRetriever(mock_client)
        assert retriever.platform_name == "coinbase"

    def test_get_account_info_raises_without_client(self):
        """Test get_account_info raises error without client."""
        retriever = CoinbasePortfolioRetriever(None)
        with pytest.raises(PortfolioRetrievingError):
            retriever.get_account_info()

    def test_safe_get_handles_dict_and_objects(self):
        """Test _safe_get handles both dicts and objects."""
        retriever = CoinbasePortfolioRetriever(None)

        # Test with dict
        d = {"key": "value"}
        assert retriever._safe_get(d, "key") == "value"
        assert retriever._safe_get(d, "missing") is None
        assert retriever._safe_get(d, "missing", "default") == "default"

        # Test with object
        obj = Mock()
        obj.attr = "value"
        assert retriever._safe_get(obj, "attr") == "value"

    def test_safe_float_converts_values(self):
        """Test _safe_float converts various types."""
        retriever = CoinbasePortfolioRetriever(None)

        assert retriever._safe_float("123.45") == 123.45
        assert retriever._safe_float(123) == 123.0
        assert retriever._safe_float(None) == 0.0
        assert retriever._safe_float("invalid") == 0.0
        assert retriever._safe_float("invalid", 99) == 99

    def test_get_first_matching_returns_first_non_none(self):
        """Test _get_first_matching returns first matching field."""
        retriever = CoinbasePortfolioRetriever(None)
        obj = {"field2": "value2", "field3": "value3"}

        result = retriever._get_first_matching(obj, ["field1", "field2", "field3"])
        assert result == "value2"

        result = retriever._get_first_matching(obj, ["missing1", "missing2"], "default")
        assert result == "default"


class TestOandaPortfolioRetriever:
    """Test Oanda portfolio retriever."""

    def test_retriever_initializes(self):
        """Test Oanda retriever initializes correctly."""
        mock_client = Mock()
        retriever = OandaPortfolioRetriever(mock_client)
        assert retriever.platform_name == "oanda"

    def test_get_account_info_raises_without_client(self):
        """Test get_account_info raises error without client."""
        retriever = OandaPortfolioRetriever(None)
        with pytest.raises(PortfolioRetrievingError):
            retriever.get_account_info()


class TestPortfolioRetrieverHelpers:
    """Test helper functions in portfolio retrievers."""

    def test_safe_get_dict_access(self):
        """Test _safe_get with dict."""
        retriever = MockPortfolioRetriever(None)
        d = {"nested": {"key": "value"}}

        assert retriever._safe_get(d, "nested") == {"key": "value"}
        assert retriever._safe_get(d, "missing", {}) == {}

    def test_safe_float_dict_with_value_key(self):
        """Test _safe_float with dict containing 'value' key."""
        retriever = MockPortfolioRetriever(None)
        value_dict = {"value": "42.5"}

        assert retriever._safe_float(value_dict) == 42.5

    def test_get_first_matching_with_none_values(self):
        """Test _get_first_matching skips None values."""
        retriever = MockPortfolioRetriever(None)
        obj = {"field1": None, "field2": "value2", "field3": "value3"}

        result = retriever._get_first_matching(obj, ["field1", "field2", "field3"])
        assert result == "value2"
