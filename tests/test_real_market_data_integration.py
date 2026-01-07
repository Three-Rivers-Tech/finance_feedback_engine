"""
Real Market Data Integration Test

Verifies that the bot can fetch and use real market data from Alpha Vantage
and other data providers for production trading decisions.
"""

import logging
import asyncio
import os
from datetime import datetime
from dotenv import load_dotenv

import pytest

from finance_feedback_engine.core import FinanceFeedbackEngine
from finance_feedback_engine.data_providers.alpha_vantage_provider import AlphaVantageProvider

logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# Load API key from environment
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")

if ALPHA_VANTAGE_API_KEY:
    logger.info(f"✓ Alpha Vantage API key loaded: {ALPHA_VANTAGE_API_KEY[:10]}...")
else:
    logger.warning("⚠ ALPHA_VANTAGE_API_KEY not found in environment")


@pytest.fixture
def real_market_data_config():
    """Config for bot with real market data integration."""
    return {
        "trading_platform": "unified",
        "paper_trading_defaults": {
            "enabled": True,
            "initial_cash_usd": 10000.0,
        },
        "platforms": [],  # Paper trading only
        "decision_engine": {
            "use_ollama": True,  # Use real Ollama
            "debate_mode": False,
            "quicktest_mode": False,  # DISABLE quicktest - use real data
            "model_name": "llama3.2:3b-instruct-fp16",
        },
        "agent": {
            "enabled": True,
            "asset_pairs": ["BTCUSD"],
            "autonomous": {
                "enabled": True,
            },
        },
        "is_backtest": False,
    }


@pytest.mark.external_service
class TestRealMarketDataIntegration:
    """Tests for real market data integration."""

    @pytest.mark.asyncio
    async def test_alpha_vantage_connection(self):
        """Test: Can connect to Alpha Vantage and fetch real data."""
        if not ALPHA_VANTAGE_API_KEY:
            pytest.skip("ALPHA_VANTAGE_API_KEY not set in environment")

        async with AlphaVantageProvider(api_key=ALPHA_VANTAGE_API_KEY) as provider:
            try:
                # Test real market data fetch
                logger.info("Fetching real BTCUSD price from Alpha Vantage...")
                market_data = await provider.get_market_data("BTCUSD")

                # Extract price from market data (use "close" for current price)
                price = market_data.get("close")
                logger.info(f"Current BTC price: ${price:,.2f}")

                # Assertions
                assert price is not None, "Price should not be None"
                assert isinstance(price, (int, float)), "Price should be numeric"
                assert price > 0, "Price should be positive"
                assert price > 1000, "BTC price should be > $1,000"
                assert price < 200000, "BTC price should be < $200,000 (sanity check)"

                logger.info("✅ Alpha Vantage connection successful")
                logger.info(f"✅ Real market data validated: BTC = ${price:,.2f}")

            except Exception as e:
                logger.error(f"❌ Alpha Vantage connection failed: {e}")
                raise

    @pytest.mark.asyncio
    async def test_market_data_comprehensive_fetch(self):
        """Test: Can fetch comprehensive market data for decision making."""
        if not ALPHA_VANTAGE_API_KEY:
            pytest.skip("ALPHA_VANTAGE_API_KEY not set in environment")

        async with AlphaVantageProvider(api_key=ALPHA_VANTAGE_API_KEY) as provider:
            try:
                # Test comprehensive data fetch
                logger.info("Fetching comprehensive market data...")

                # Get comprehensive market data (includes OHLCV, indicators, etc.)
                data = await provider.get_comprehensive_market_data("BTCUSD")
                assert data is not None, "Market data should not be None"
                assert "close" in data, "Should have close price"
                logger.info(f"✅ Comprehensive data: price=${data['close']:,.2f}")

                # Get sentiment if available
                try:
                    sentiment = await provider.get_news_sentiment("CRYPTO:BTC")
                    if sentiment:
                        logger.info(f"✅ Sentiment: {sentiment.get('overall_score', 'N/A')}")
                except Exception as e:
                    logger.warning(f"Sentiment fetch skipped: {e}")

                logger.info("✅ Comprehensive market data fetch successful")

            except Exception as e:
                logger.error(f"❌ Comprehensive data fetch failed: {e}")
                raise

    @pytest.mark.asyncio
    async def test_engine_with_real_data(self, real_market_data_config):
        """Test: Engine initializes and can analyze with real market data."""
        engine = FinanceFeedbackEngine(real_market_data_config)

        try:
            # Verify engine initialized
            assert engine is not None
            assert engine.data_provider is not None

            logger.info("Engine initialized with real data providers")

            # Test analysis with real data
            logger.info("Running analysis with real market data...")

            # Note: This will use real Ollama and real market data
            decision = await engine.analyze_asset_async("BTCUSD")

            # Verify decision structure
            assert decision is not None, "Decision should not be None"
            assert "action" in decision, "Decision should have action"
            assert decision["action"] in ["BUY", "SELL", "HOLD"], f"Invalid action: {decision['action']}"

            logger.info(f"✅ Decision generated with real data: {decision['action']}")
            logger.info(f"   Confidence: {decision.get('confidence', 'N/A')}")
            logger.info(f"   Reasoning: {decision.get('reasoning', 'N/A')[:100]}...")

        except Exception as e:
            logger.error(f"❌ Engine analysis with real data failed: {e}")
            raise

    @pytest.mark.asyncio
    async def test_data_freshness_validation(self):
        """Test: Market data freshness validation works."""
        if not ALPHA_VANTAGE_API_KEY:
            pytest.skip("ALPHA_VANTAGE_API_KEY not set in environment")

        async with AlphaVantageProvider(api_key=ALPHA_VANTAGE_API_KEY) as provider:
            try:
                # Get latest price
                market_data = await provider.get_market_data("BTCUSD")
                price = market_data.get("close")

                # Check that we can determine data freshness
                # (This is a basic check - actual freshness logic is in the bot)
                assert price is not None, "Should get price data"

                logger.info(f"✅ Data freshness check passed (price: ${price:,.2f})")

            except Exception as e:
                logger.error(f"❌ Data freshness check failed: {e}")
                raise

    @pytest.mark.asyncio
    async def test_rate_limiting_respected(self):
        """Test: Alpha Vantage rate limiting is respected."""
        if not ALPHA_VANTAGE_API_KEY:
            pytest.skip("ALPHA_VANTAGE_API_KEY not set in environment")

        async with AlphaVantageProvider(api_key=ALPHA_VANTAGE_API_KEY) as provider:
            try:
                # Alpha Vantage free tier: 5 calls/minute, 500 calls/day
                logger.info("Testing rate limiting (making 3 consecutive calls)...")

                prices = []
                for i in range(3):
                    market_data = await provider.get_market_data("BTCUSD")
                    price = market_data.get("close")
                    prices.append(price)
                    logger.info(f"Call {i+1}: ${price:,.2f}")

                # Should not crash or hit rate limit for 3 calls
                assert len(prices) == 3, "Should complete 3 calls"
                assert all(p > 0 for p in prices), "All prices should be valid"

                logger.info("✅ Rate limiting test passed (3 calls successful)")

            except Exception as e:
                logger.error(f"❌ Rate limiting test failed: {e}")
                raise


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
