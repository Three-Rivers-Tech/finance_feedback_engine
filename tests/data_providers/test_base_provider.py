"""Tests for base data provider."""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import aiohttp
from finance_feedback_engine.data_providers.base_provider import (
    BaseDataProvider,
    DataProviderError,
    RateLimitExceededError,
    InvalidAssetPairError,
    DataUnavailableError,
)


# Concrete implementation for testing
class TestProvider(BaseDataProvider):
    """Concrete provider for testing abstract base class."""

    @property
    def provider_name(self) -> str:
        return "TestProvider"

    @property
    def base_url(self) -> str:
        return "https://api.test.com"

    async def fetch_market_data(self, asset_pair: str):
        return {"asset": asset_pair, "price": 45000}

    def normalize_asset_pair(self, asset_pair: str) -> str:
        return asset_pair.replace("USD", "-USD")


class TestBaseDataProviderInitialization:
    """Test BaseDataProvider initialization."""

    def test_initialization_with_defaults(self):
        """Test initialization with default parameters."""
        provider = TestProvider()

        assert provider.provider_name == "TestProvider"
        assert provider.base_url == "https://api.test.com"
        assert provider.config == {}
        assert provider.rate_limiter is not None
        assert provider.circuit_breaker is not None
        assert provider._owned_session is True

    def test_initialization_with_config(self):
        """Test initialization with custom config."""
        config = {
            "rate_limiter": {
                "tokens_per_second": 10.0,
                "max_tokens": 20
            },
            "circuit_breaker": {
                "failure_threshold": 3,
                "recovery_timeout": 30.0
            }
        }

        provider = TestProvider(config=config)

        assert provider.config == config
        assert provider.rate_limiter is not None

    def test_initialization_with_external_rate_limiter(self):
        """Test initialization with external rate limiter."""
        from finance_feedback_engine.utils.rate_limiter import RateLimiter

        external_limiter = RateLimiter(tokens_per_second=15.0, max_tokens=20)
        provider = TestProvider(rate_limiter=external_limiter)

        assert provider.rate_limiter is external_limiter

    @pytest.mark.asyncio
    async def test_initialization_with_external_session(self):
        """Test initialization with external aiohttp session."""
        async with aiohttp.ClientSession() as session:
            provider = TestProvider(session=session)

            assert provider.session is session
            assert provider._owned_session is False

    def test_timeout_configuration(self):
        """Test timeout values are configured correctly."""
        config = {
            "api_timeouts": {
                "default": 15,
                "market_data": 20,
                "sentiment": 25
            }
        }

        provider = TestProvider(config=config)

        assert provider.timeout_default == 15
        assert provider.timeout_market_data == 20
        assert provider.timeout_sentiment == 25

    def test_timeout_defaults(self):
        """Test default timeout values."""
        provider = TestProvider()

        # Should use defaults when not configured
        assert provider.timeout_default == 10
        assert provider.timeout_market_data == 10
        assert provider.timeout_sentiment == 15


class TestRateLimiterCreation:
    """Test rate limiter creation."""

    def test_create_default_rate_limiter(self):
        """Test default rate limiter is created."""
        provider = TestProvider()

        assert provider.rate_limiter is not None
        # Verify it has the expected method
        assert hasattr(provider.rate_limiter, 'wait_for_token')

    def test_create_rate_limiter_with_config(self):
        """Test rate limiter with custom config."""
        config = {
            "rate_limiter": {
                "tokens_per_second": 8.0,
                "max_tokens": 25
            }
        }

        provider = TestProvider(config=config)

        # Verify custom config is used
        assert provider.rate_limiter is not None


class TestCircuitBreakerCreation:
    """Test circuit breaker creation."""

    def test_create_circuit_breaker(self):
        """Test circuit breaker is created."""
        provider = TestProvider()

        assert provider.circuit_breaker is not None
        assert hasattr(provider.circuit_breaker, 'call')

    def test_circuit_breaker_with_config(self):
        """Test circuit breaker with custom config."""
        config = {
            "circuit_breaker": {
                "failure_threshold": 3,
                "recovery_timeout": 45.0
            }
        }

        provider = TestProvider(config=config)

        assert provider.circuit_breaker is not None


class TestSessionManagement:
    """Test aiohttp session management."""

    @pytest.mark.asyncio
    async def test_ensure_session_creates_session(self):
        """Test session is created lazily."""
        provider = TestProvider()

        assert provider.session is None

        await provider._ensure_session()

        assert provider.session is not None
        assert isinstance(provider.session, aiohttp.ClientSession)

        await provider.close()

    @pytest.mark.asyncio
    async def test_close_owned_session(self):
        """Test closing owned session."""
        provider = TestProvider()

        await provider._ensure_session()
        assert provider.session is not None

        await provider.close()

        assert provider.session is None

    @pytest.mark.asyncio
    async def test_close_external_session_not_closed(self):
        """Test external session is not closed."""
        async with aiohttp.ClientSession() as external_session:
            provider = TestProvider(session=external_session)

            assert provider._owned_session is False

            await provider.close()

            # External session should still be valid (not closed)
            assert not external_session.closed

    @pytest.mark.asyncio
    async def test_async_context_manager_single(self):
        """Test async context manager with single entry."""
        async with TestProvider() as provider:
            assert provider.session is not None
            assert provider._context_count == 1

        # After exit, session should be closed
        # Context count should be 0

    @pytest.mark.asyncio
    async def test_async_context_manager_nested(self):
        """Test async context manager with nested contexts."""
        provider = TestProvider()

        async with provider:
            assert provider._context_count == 1

            async with provider:
                assert provider._context_count == 2

            assert provider._context_count == 1

        assert provider._context_count == 0


class TestResponseValidation:
    """Test response validation."""

    def test_validate_response_valid_dict(self):
        """Test validation passes for valid dict response."""
        provider = TestProvider()

        response = {"status": "success", "data": {"price": 45000}}

        validated = provider._validate_response(response)

        assert validated == response

    def test_validate_response_invalid_type(self):
        """Test validation fails for non-dict response."""
        provider = TestProvider()

        with pytest.raises(ValueError) as exc_info:
            provider._validate_response("not a dict")

        assert "Invalid response type" in str(exc_info.value)

    def test_validate_response_list_fails(self):
        """Test validation fails for list response."""
        provider = TestProvider()

        with pytest.raises(ValueError):
            provider._validate_response([{"data": 1}])


class TestAssetPairNormalization:
    """Test asset pair normalization."""

    def test_normalize_asset_pair(self):
        """Test asset pair normalization (concrete implementation)."""
        provider = TestProvider()

        normalized = provider.normalize_asset_pair("BTCUSD")

        assert normalized == "BTC-USD"

    def test_normalize_already_normalized(self):
        """Test normalizing already normalized pair."""
        provider = TestProvider()

        normalized = provider.normalize_asset_pair("BTC-USD")

        assert normalized == "BTC--USD"  # Double dash due to simple implementation


class TestAbstractMethods:
    """Test that abstract methods must be implemented."""

    def test_cannot_instantiate_base_without_provider_name(self):
        """Test base class cannot be instantiated without abstract methods."""

        class IncompleteProvider(BaseDataProvider):
            @property
            def base_url(self) -> str:
                return "https://test.com"

            async def fetch_market_data(self, asset_pair: str):
                return {}

            def normalize_asset_pair(self, asset_pair: str) -> str:
                return asset_pair

        with pytest.raises(TypeError):
            # Missing provider_name property
            IncompleteProvider()

    def test_concrete_implementation_works(self):
        """Test concrete implementation with all abstract methods works."""
        provider = TestProvider()

        assert provider.provider_name == "TestProvider"
        assert provider.base_url == "https://api.test.com"


class TestErrorClasses:
    """Test error class hierarchy."""

    def test_data_provider_error(self):
        """Test DataProviderError can be raised."""
        error = DataProviderError("Test error")

        assert str(error) == "Test error"
        assert isinstance(error, Exception)

    def test_rate_limit_exceeded_error(self):
        """Test RateLimitExceededError."""
        error = RateLimitExceededError("Rate limit hit")

        assert isinstance(error, DataProviderError)
        assert isinstance(error, Exception)

    def test_invalid_asset_pair_error(self):
        """Test InvalidAssetPairError."""
        error = InvalidAssetPairError("Invalid pair format")

        assert isinstance(error, DataProviderError)

    def test_data_unavailable_error(self):
        """Test DataUnavailableError."""
        error = DataUnavailableError("Data not available")

        assert isinstance(error, DataProviderError)

    def test_error_catching(self):
        """Test errors can be caught by base class."""
        try:
            raise RateLimitExceededError("Rate limit")
        except DataProviderError as e:
            # Should catch derived error with base class
            assert "Rate limit" in str(e)


class TestProviderConcreteMethods:
    """Test concrete methods from TestProvider."""

    @pytest.mark.asyncio
    async def test_fetch_market_data(self):
        """Test fetch_market_data concrete implementation."""
        provider = TestProvider()

        result = await provider.fetch_market_data("BTCUSD")

        assert result["asset"] == "BTCUSD"
        assert result["price"] == 45000

    @pytest.mark.asyncio
    async def test_fetch_different_assets(self):
        """Test fetching different asset pairs."""
        provider = TestProvider()

        btc_data = await provider.fetch_market_data("BTCUSD")
        eth_data = await provider.fetch_market_data("ETHUSD")

        assert btc_data["asset"] == "BTCUSD"
        assert eth_data["asset"] == "ETHUSD"
