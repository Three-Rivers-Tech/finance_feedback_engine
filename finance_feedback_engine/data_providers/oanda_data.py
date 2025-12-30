"""Oanda data provider for historical candle data across multiple timeframes."""

import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..utils.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError
from ..utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class OandaDataProvider:
    """
    Oanda data provider for fetching historical OHLCV candle data.

    Supports multiple timeframes for forex pairs:
    - ONE_MINUTE (M1)
    - FIVE_MINUTE (M5)
    - FIFTEEN_MINUTE (M15)
    - ONE_HOUR (H1)
    - FOUR_HOUR (H4)
    - ONE_DAY (D)

    Uses Oanda v20 REST API's candles endpoint.
    Rate limit: 120 requests per 20 seconds.
    """

    # Granularity mappings (Oanda format)
    GRANULARITIES = {
        "1m": "M1",
        "5m": "M5",
        "15m": "M15",
        "1h": "H1",
        "4h": "H4",
        "1d": "D",
        "ONE_MINUTE": "M1",
        "FIVE_MINUTE": "M5",
        "FIFTEEN_MINUTE": "M15",
        "ONE_HOUR": "H1",
        "FOUR_HOUR": "H4",
        "ONE_DAY": "D",
    }

    def __init__(
        self, credentials: Dict[str, Any], rate_limiter: Optional[RateLimiter] = None
    ):
        """
        Initialize Oanda data provider.

        Args:
            credentials: Dictionary containing:
                - access_token: Oanda API token
                - account_id: Oanda account ID
                - environment: 'practice' or 'live'
            rate_limiter: Optional shared rate limiter instance
        """
        self.api_key = credentials.get("access_token") or credentials.get("api_key")
        self.account_id = credentials.get("account_id")
        self.environment = credentials.get("environment", "practice")

        # Set base URL based on environment
        if credentials.get("base_url"):
            self.base_url = credentials["base_url"]
        else:
            self.base_url = (
                "https://api-fxpractice.oanda.com"
                if self.environment == "practice"
                else "https://api-fxtrade.oanda.com"
            )

        # Use shared rate limiter or create new one
        # Oanda: 120 req/20sec = 6 req/sec, we'll be conservative
        self.rate_limiter = rate_limiter or RateLimiter(
            tokens_per_second=5.0, max_tokens=30  # Conservative limit
        )

        # Circuit breaker for API resilience
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=3, recovery_timeout=60.0, name="OandaData"
        )

        logger.info(f"OandaDataProvider initialized ({self.environment} environment)")

    def _normalize_asset_pair(self, asset_pair: str) -> str:
        """
        Normalize asset pair to Oanda instrument format.

        Args:
            asset_pair: Asset pair (e.g., 'EURUSD', 'EUR_USD', 'EUR/USD')

        Returns:
            Oanda instrument (e.g., 'EUR_USD', 'GBP_USD')
        """
        # Remove any existing separators
        pair = asset_pair.upper().replace("-", "").replace("_", "").replace("/", "")

        # Common forex pairs
        forex_map = {
            "EURUSD": "EUR_USD",
            "GBPUSD": "GBP_USD",
            "USDJPY": "USD_JPY",
            "USDCHF": "USD_CHF",
            "AUDUSD": "AUD_USD",
            "USDCAD": "USD_CAD",
            "NZDUSD": "NZD_USD",
            "EURGBP": "EUR_GBP",
            "EURJPY": "EUR_JPY",
            "GBPJPY": "GBP_JPY",
        }

        if pair in forex_map:
            return forex_map[pair]

        # Default format: insert underscore after 3 chars (standard forex format)
        if len(pair) == 6:
            return f"{pair[:3]}_{pair[3:]}"

        # Fallback: return as-is
        return pair

    def get_candles(
        self, asset_pair: str, granularity: str = "1d", limit: int = 300
    ) -> List[Dict[str, Any]]:
        """
        Fetch historical candle data from Oanda.

        Args:
            asset_pair: Asset pair (e.g., 'EURUSD', 'GBPUSD')
            granularity: Timeframe ('1m', '5m', '15m', '1h', '4h', '1d')
            limit: Number of candles to fetch (max 5000)

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
        logger.info(f"Fetching {granularity} candles for {asset_pair} from Oanda")

        try:
            # Normalize asset pair to Oanda format
            instrument = self._normalize_asset_pair(asset_pair)

            # Get granularity in Oanda format
            oanda_granularity = self.GRANULARITIES.get(granularity)
            if not oanda_granularity:
                raise ValueError(f"Unsupported granularity: {granularity}")

            # Rate limiting
            self.rate_limiter.wait_for_token()

            # Call circuit breaker protected request
            candles = self.circuit_breaker.call_sync(
                self._fetch_candles_from_api, instrument, oanda_granularity, limit
            )

            logger.info(f"Retrieved {len(candles)} candles for {instrument}")
            return candles

        except CircuitBreakerOpenError:
            logger.error("Circuit breaker open for Oanda data provider")
            raise
        except Exception as e:
            logger.error(f"Failed to fetch Oanda candles: {e}")
            raise

    def _fetch_candles_from_api(
        self, instrument: str, granularity: str, count: int
    ) -> List[Dict[str, Any]]:
        """
        Fetch candles from Oanda API (internal, circuit breaker protected).

        Args:
            instrument: Oanda instrument (e.g., 'EUR_USD')
            granularity: Oanda granularity (e.g., 'M5', 'H1', 'D')
            count: Number of candles to fetch

        Returns:
            List of normalized candle dictionaries
        """
        import requests

        # Oanda candles endpoint
        url = f"{self.base_url}/v3/instruments/{instrument}/candles"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        params = {
            "granularity": granularity,
            "count": min(count, 5000),  # Oanda max is 5000
        }

        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()

        # Normalize response to standard OHLCV format
        candles = []
        for candle in data.get("candles", []):
            if not candle.get("complete", True):
                # Skip incomplete candles
                continue

            mid = candle.get("mid", {})

            # Parse timestamp (RFC3339 format)
            timestamp_str = candle.get("time", "")
            try:
                dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                timestamp = int(dt.timestamp())
            except Exception:
                # Fallback: use current time
                timestamp = int(time.time())

            candles.append(
                {
                    "timestamp": timestamp,
                    "open": float(mid.get("o", 0)),
                    "high": float(mid.get("h", 0)),
                    "low": float(mid.get("l", 0)),
                    "close": float(mid.get("c", 0)),
                    "volume": int(candle.get("volume", 0)),
                }
            )

        # Sort by timestamp (oldest first)
        candles.sort(key=lambda x: x["timestamp"])

        return candles

    def get_latest_price(self, asset_pair: str) -> float:
        """
        Get latest price for asset pair.

        Args:
            asset_pair: Asset pair (e.g., 'EURUSD')

        Returns:
            Latest price
        """
        candles = self.get_candles(asset_pair, granularity="1m", limit=1)
        if candles:
            return candles[-1]["close"]
        return 0.0

    def list_instruments(self) -> List[Dict[str, Any]]:
        """
        List all available instruments from Oanda.

        Fetches the full list of tradeable instruments for pair discovery.
        Only returns currency pairs (type='CURRENCY').

        Returns:
            List of instrument dictionaries with keys:
            - name: Instrument name (e.g., 'EUR_USD')
            - type: Instrument type ('CURRENCY', 'CFD', 'METAL', etc.)
            - displayName: Human-readable name
            - pipLocation: Pip location for price formatting
            - minimumTradeSize: Minimum trade size

        Raises:
            CircuitBreakerOpenError: If circuit breaker is open
            ValueError: If API request fails
        """
        logger.info("Fetching instrument list from Oanda")

        try:
            # Rate limiting
            self.rate_limiter.wait_for_token()

            # Call circuit breaker protected request
            instruments = self.circuit_breaker.call_sync(
                self._fetch_instruments_from_api
            )

            # Filter to only currency pairs
            currency_pairs = [i for i in instruments if i.get("type") == "CURRENCY"]

            logger.info(
                f"Retrieved {len(currency_pairs)} currency pairs "
                f"(out of {len(instruments)} total instruments)"
            )
            return currency_pairs

        except CircuitBreakerOpenError:
            logger.error("Circuit breaker open for Oanda data provider")
            raise
        except Exception as e:
            logger.error(f"Failed to fetch Oanda instruments: {e}")
            raise

    def _fetch_instruments_from_api(self) -> List[Dict[str, Any]]:
        """
        Fetch instruments from Oanda API (internal, circuit breaker protected).

        Returns:
            List of instrument dictionaries
        """
        import requests

        # Oanda instruments endpoint
        url = f"{self.base_url}/v3/accounts/{self.account_id}/instruments"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        data = response.json()

        # Return instruments list
        return data.get("instruments", [])
