"""
Base data provider with shared infrastructure.

Eliminates duplication across AlphaVantage, Coinbase, Oanda, and other providers.
Provides common functionality: rate limiting, circuit breaking, HTTP clients, timeouts.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging
import asyncio
import aiohttp
from aiohttp_retry import RetryClient, ExponentialRetry

from finance_feedback_engine.utils.rate_limiter import RateLimiter
from finance_feedback_engine.utils.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)


class BaseDataProvider(ABC):
    """
    Abstract base class for all data providers.

    Provides shared infrastructure:
    - Rate limiting (configurable per provider)
    - Circuit breaking (fault tolerance)
    - HTTP client management (connection pooling)
    - Timeout configuration
    - Error handling

    TEMPLATE METHOD pattern - defines algorithm structure,
    subclasses implement specific details.

    Design Principles:
    - SINGLE RESPONSIBILITY: Infrastructure management only
    - OPEN/CLOSED: Open for extension (subclassing), closed for modification
    - DEPENDENCY INVERSION: Depends on abstractions (RateLimiter, CircuitBreaker)
    """

    # Subclasses must override these properties
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the data provider (e.g., 'AlphaVantage', 'Coinbase')."""
        pass

    @property
    @abstractmethod
    def base_url(self) -> str:
        """Base URL for API requests."""
        pass

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        rate_limiter: Optional[RateLimiter] = None,
        session: Optional[aiohttp.ClientSession] = None
    ):
        """
        Initialize base provider with shared infrastructure.

        Args:
            config: Configuration dictionary (optional)
            rate_limiter: Shared rate limiter (optional, creates default if None)
            session: Shared aiohttp session (optional, creates owned session if None)
        """
        self.config = config or {}
        self._owned_session = session is None
        self.session = session
        self._session_lock = asyncio.Lock()
        self._context_count = 0  # Track async context manager depth

        # Initialize rate limiter (use shared or create new)
        self.rate_limiter = rate_limiter or self._create_default_rate_limiter()

        # Initialize circuit breaker
        self.circuit_breaker = self._create_circuit_breaker()

        # Configure timeouts
        self._configure_timeouts()

        logger.info(f"{self.provider_name} provider initialized")

    def _create_default_rate_limiter(self) -> RateLimiter:
        """
        Create default rate limiter for this provider.

        Subclasses can override for provider-specific rate limits.

        Returns:
            RateLimiter instance with conservative defaults
        """
        # Get provider-specific config or use defaults
        rate_config = self.config.get('rate_limiter', {})

        return RateLimiter(
            tokens_per_second=rate_config.get('tokens_per_second', 5.0),
            max_tokens=rate_config.get('max_tokens', 15)
        )

    def _create_circuit_breaker(self) -> CircuitBreaker:
        """
        Create circuit breaker for this provider.

        Subclasses can override for custom failure thresholds.

        Returns:
            CircuitBreaker instance configured for this provider
        """
        cb_config = self.config.get('circuit_breaker', {})

        return CircuitBreaker(
            failure_threshold=cb_config.get('failure_threshold', 5),
            recovery_timeout=cb_config.get('recovery_timeout', 60.0),
            expected_exception=aiohttp.ClientError,
            name=f"{self.provider_name}-API"
        )

    def _configure_timeouts(self):
        """Configure API timeout values from config."""
        api_timeouts = self.config.get('api_timeouts', {})

        self.timeout_default = api_timeouts.get('default', 10)
        self.timeout_market_data = api_timeouts.get('market_data', self.timeout_default)
        self.timeout_sentiment = api_timeouts.get('sentiment', 15)

        logger.debug(
            f"{self.provider_name} timeouts configured: "
            f"default={self.timeout_default}s, "
            f"market={self.timeout_market_data}s, "
            f"sentiment={self.timeout_sentiment}s"
        )

    async def _ensure_session(self):
        """Ensure aiohttp session exists (lazy initialization)."""
        if self.session is None:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout)
            self._owned_session = True
            logger.debug(f"{self.provider_name} created new aiohttp session")

    async def close(self):
        """Close aiohttp session if owned by this provider."""
        if self.session and self._owned_session:
            await self.session.close()
            self.session = None
            logger.debug(f"{self.provider_name} closed session")

    async def __aenter__(self):
        """
        Async context manager entry.

        Supports nested async with usage: only closes session when all contexts exit.
        """
        async with self._session_lock:
            await self._ensure_session()
            self._context_count += 1
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Async context manager exit.

        Only closes the session when all nested contexts have exited.
        """
        async with self._session_lock:
            if self._context_count > 0:
                self._context_count -= 1
            if self._context_count == 0:
                await self.close()
        return False

    # Abstract methods that subclasses MUST implement
    @abstractmethod
    async def fetch_market_data(self, asset_pair: str) -> Dict[str, Any]:
        """
        Fetch market data for asset pair.

        Subclasses MUST implement this method with provider-specific logic.

        Args:
            asset_pair: Asset pair to fetch (e.g., "BTCUSD")

        Returns:
            Market data dictionary

        Raises:
            Provider-specific exceptions
        """
        pass

    @abstractmethod
    def normalize_asset_pair(self, asset_pair: str) -> str:
        """
        Normalize asset pair to provider's format.

        Different providers use different formats:
        - AlphaVantage: "BTC" (symbol only)
        - Coinbase: "BTC-USD" (dash separator)
        - Oanda: "EUR_USD" (underscore separator)

        Args:
            asset_pair: Standardized asset pair (e.g., "BTCUSD")

        Returns:
            Provider-specific format
        """
        pass

    async def _make_http_request(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        method: str = 'GET'
    ) -> Dict[str, Any]:
        """
        Make HTTP request with rate limiting and circuit breaking.

        TEMPLATE METHOD - shared logic for all providers.
        Handles:
        - Rate limiting (prevents API throttling)
        - Circuit breaking (fault tolerance)
        - Retries with exponential backoff
        - Timeout management

        Args:
            url: Full URL to request
            params: Query parameters (optional)
            headers: HTTP headers (optional)
            timeout: Request timeout in seconds (optional, uses default if None)
            method: HTTP method (default: GET)

        Returns:
            JSON response as dictionary

        Raises:
            aiohttp.ClientError: On HTTP errors
            CircuitBreakerOpenError: When circuit breaker is open
        """
        await self._ensure_session()

        # Apply rate limiting BEFORE making request
        await self.rate_limiter.acquire()

        # Define the actual request function
        async def _request():
            timeout_val = timeout or self.timeout_default
            client_timeout = aiohttp.ClientTimeout(total=timeout_val)

            # Use RetryClient for automatic retries with exponential backoff
            retry_options = ExponentialRetry(attempts=3)
            async with RetryClient(
                client_session=self.session,
                retry_options=retry_options
            ) as retry_client:
                async with retry_client.request(
                    method,
                    url,
                    params=params,
                    headers=headers,
                    timeout=client_timeout
                ) as response:
                    response.raise_for_status()
                    return await response.json()

        # Execute with circuit breaker protection
        try:
            result = await self.circuit_breaker.call(_request)
            logger.debug(f"{self.provider_name} HTTP {method} {url} - SUCCESS")
            return result
        except Exception as e:
            logger.error(f"{self.provider_name} HTTP {method} {url} - FAILED: {e}")
            raise

    def _validate_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate API response structure.

        Subclasses can override for provider-specific validation.

        Args:
            response: Raw API response

        Returns:
            Validated response

        Raises:
            ValueError: If response is invalid
        """
        if not isinstance(response, dict):
            raise ValueError(f"{self.provider_name}: Invalid response type, expected dict")

        return response


# Error classes for common provider failures
class DataProviderError(Exception):
    """Base exception for data provider errors."""
    pass


class RateLimitExceededError(DataProviderError):
    """Raised when API rate limit is exceeded."""
    pass


class InvalidAssetPairError(DataProviderError):
    """Raised when asset pair format is invalid."""
    pass


class DataUnavailableError(DataProviderError):
    """Raised when requested data is not available."""
    pass
