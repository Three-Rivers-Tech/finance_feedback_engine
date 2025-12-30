"""Coinbase data provider for historical candle data across multiple timeframes."""

import logging
import time
from typing import Any, Dict, List, Optional

from ..utils.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError
from ..utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class CoinbaseDataProvider:
    """
    Coinbase data provider for fetching historical OHLCV candle data.

    Supports multiple timeframes for crypto assets:
    - ONE_MINUTE (60 seconds)
    - FIVE_MINUTE (300 seconds)
    - FIFTEEN_MINUTE (900 seconds)
    - ONE_HOUR (3600 seconds)
    - FOUR_HOUR (14400 seconds)
    - ONE_DAY (86400 seconds)

    Uses Coinbase Advanced Trade API's public candles endpoint.
    Rate limit: 15 requests/second (public data).
    """

    BASE_URL = "https://api.coinbase.com"

    # Granularity mappings (Coinbase uses seconds)
    GRANULARITIES = {
        "1m": 60,
        "5m": 300,
        "15m": 900,
        "1h": 3600,
        "4h": 14400,
        "1d": 86400,
        "ONE_MINUTE": 60,
        "FIVE_MINUTE": 300,
        "FIFTEEN_MINUTE": 900,
        "ONE_HOUR": 3600,
        "FOUR_HOUR": 14400,
        "ONE_DAY": 86400,
    }

    def __init__(
        self,
        credentials: Optional[Dict[str, Any]] = None,
        rate_limiter: Optional[RateLimiter] = None,
    ):
        """
        Initialize Coinbase data provider.

        Args:
            credentials: Optional credentials (not needed for public data)
            rate_limiter: Optional shared rate limiter instance
        """
        self.credentials = credentials or {}

        # Use shared rate limiter or create new one
        # Coinbase allows 15 req/sec for public data, we'll be conservative
        self.rate_limiter = rate_limiter or RateLimiter(
            tokens_per_second=10.0, max_tokens=30  # Conservative limit
        )

        # Circuit breaker for API resilience
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=3, recovery_timeout=60.0, name="CoinbaseData"
        )

        logger.info("CoinbaseDataProvider initialized")

    def _normalize_asset_pair(self, asset_pair: str) -> str:
        """
        Normalize asset pair to Coinbase product ID format.

        Args:
            asset_pair: Asset pair (e.g., 'BTCUSD', 'BTC-USD', 'ETHUSD')

        Returns:
            Coinbase product ID (e.g., 'BTC-USD', 'ETH-USD')
        """
        # Remove any existing separators
        pair = asset_pair.upper().replace("-", "").replace("_", "").replace("/", "")

        # Common crypto symbols
        if pair.startswith("BTC"):
            return "BTC-USD"
        elif pair.startswith("ETH"):
            return "ETH-USD"
        elif pair.startswith("SOL"):
            return "SOL-USD"
        elif pair.startswith("DOGE"):
            return "DOGE-USD"
        elif pair.startswith("ADA"):
            return "ADA-USD"

        # Default format: assume last 3-4 chars are quote currency
        if pair.endswith("USD"):
            base = pair[:-3]
            return f"{base}-USD"
        elif pair.endswith("USDT"):
            base = pair[:-4]
            return f"{base}-USDT"
        elif pair.endswith("USDC"):
            base = pair[:-4]
            return f"{base}-USDC"

        # Fallback: insert hyphen in middle
        mid = len(pair) // 2
        return f"{pair[:mid]}-{pair[mid:]}"

    def get_candles(
        self, asset_pair: str, granularity: str = "1d", limit: int = 300
    ) -> List[Dict[str, Any]]:
        """
        Fetch historical candle data from Coinbase.

        Args:
            asset_pair: Asset pair (e.g., 'BTCUSD', 'ETHUSD')
            granularity: Timeframe ('1m', '5m', '15m', '1h', '4h', '1d')
            limit: Number of candles to fetch (max 300)

        Returns:
            List of candle dictionaries with keys:
            - timestamp: Unix timestamp (seconds)
            - open: Opening price
            - high: Highest price
            - low: Lowest price
            - close: Closing price
            - volume: Trading volume

        Raises:
            CircuitBreakerOpenError: If circuit breaker is open
            ValueError: If API request fails
        """
        logger.info(f"Fetching {granularity} candles for {asset_pair} from Coinbase")

        try:
            # Normalize asset pair to Coinbase format
            product_id = self._normalize_asset_pair(asset_pair)

            # Get granularity in seconds
            granularity_seconds = self.GRANULARITIES.get(granularity)
            if not granularity_seconds:
                raise ValueError(f"Unsupported granularity: {granularity}")

            # Calculate time range
            end_time = int(time.time())
            start_time = end_time - (granularity_seconds * limit)

            # Rate limiting
            self.rate_limiter.wait_for_token()

            # Call circuit breaker protected request
            candles = self.circuit_breaker.call_sync(
                self._fetch_candles_from_api,
                product_id,
                start_time,
                end_time,
                granularity_seconds,
            )

            logger.info(f"Retrieved {len(candles)} candles for {product_id}")
            return candles

        except CircuitBreakerOpenError:
            logger.error("Circuit breaker open for Coinbase data provider")
            raise
        except Exception as e:
            logger.error(f"Failed to fetch Coinbase candles: {e}")
            raise

    def _fetch_candles_from_api(
        self, product_id: str, start: int, end: int, granularity: int
    ) -> List[Dict[str, Any]]:
        """
        Fetch candles from Coinbase API (internal, circuit breaker protected).

        Args:
            product_id: Coinbase product ID (e.g., 'BTC-USD')
            start: Start timestamp (Unix seconds)
            end: End timestamp (Unix seconds)
            granularity: Granularity in seconds

        Returns:
            List of normalized candle dictionaries
        """
        import requests

        # Coinbase public candles endpoint
        url = f"{self.BASE_URL}/api/v3/brokerage/products/{product_id}/candles"

        params = {"start": start, "end": end, "granularity": granularity}

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()

        # Normalize response to standard OHLCV format
        candles = []
        for candle in data.get("candles", []):
            # Coinbase candle format: [timestamp, low, high, open, close, volume]
            candles.append(
                {
                    "timestamp": int(candle["start"]),
                    "open": float(candle["open"]),
                    "high": float(candle["high"]),
                    "low": float(candle["low"]),
                    "close": float(candle["close"]),
                    "volume": float(candle["volume"]),
                }
            )

        # Sort by timestamp (oldest first)
        candles.sort(key=lambda x: x["timestamp"])

        return candles

    def get_latest_price(self, asset_pair: str) -> float:
        """
        Get latest price for asset pair.

        Args:
            asset_pair: Asset pair (e.g., 'BTCUSD')

        Returns:
            Latest price
        """
        candles = self.get_candles(asset_pair, granularity="1m", limit=1)
        if candles:
            return candles[-1]["close"]
        return 0.0

    def list_products(self) -> List[Dict[str, Any]]:
        """
        List all available products from Coinbase Advanced Trade API.

        Fetches the full list of tradeable products for pair discovery.
        Only returns products with status='online' (active trading).

        Returns:
            List of product dictionaries with keys:
            - product_id: Product identifier (e.g., 'BTC-USD')
            - base_currency_id: Base currency (e.g., 'BTC')
            - quote_currency_id: Quote currency (e.g., 'USD')
            - status: Product status ('online', 'offline', etc.)
            - trading_disabled: Boolean indicating if trading is disabled

        Raises:
            CircuitBreakerOpenError: If circuit breaker is open
            ValueError: If API request fails
        """
        logger.info("Fetching product list from Coinbase")

        try:
            # Rate limiting
            self.rate_limiter.wait_for_token()

            # Call circuit breaker protected request
            products = self.circuit_breaker.call_sync(self._fetch_products_from_api)

            # Filter to only online products
            online_products = [
                p
                for p in products
                if p.get("status") == "online" and not p.get("trading_disabled", False)
            ]

            logger.info(
                f"Retrieved {len(online_products)} online products "
                f"(out of {len(products)} total)"
            )
            return online_products

        except CircuitBreakerOpenError:
            logger.error("Circuit breaker open for Coinbase data provider")
            raise
        except Exception as e:
            logger.error(f"Failed to fetch Coinbase products: {e}")
            raise

    def _fetch_products_from_api(self) -> List[Dict[str, Any]]:
        """
        Fetch products from Coinbase API (internal, circuit breaker protected).

        Returns:
            List of product dictionaries
        """
        import requests

        # Coinbase public products endpoint
        url = f"{self.BASE_URL}/api/v3/brokerage/products"

        response = requests.get(url, timeout=10)
        response.raise_for_status()

        data = response.json()

        # Return products list
        return data.get("products", [])
