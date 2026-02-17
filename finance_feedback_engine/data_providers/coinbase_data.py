"""Coinbase data provider for historical candle data across multiple timeframes."""

import base64
import hashlib
import hmac
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

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

    GRANULARITY_ENUMS = {
        "1m": "ONE_MINUTE",
        "5m": "FIVE_MINUTE",
        "15m": "FIFTEEN_MINUTE",
        "1h": "ONE_HOUR",
        "4h": "FOUR_HOUR",
        "1d": "ONE_DAY",
        "ONE_MINUTE": "ONE_MINUTE",
        "FIVE_MINUTE": "FIVE_MINUTE",
        "FIFTEEN_MINUTE": "FIFTEEN_MINUTE",
        "ONE_HOUR": "ONE_HOUR",
        "FOUR_HOUR": "FOUR_HOUR",
        "ONE_DAY": "ONE_DAY",
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

        # Coinbase v3 API requires named granularity, not numeric seconds
        GRANULARITY_NAMES = {
            60: "ONE_MINUTE", 300: "FIVE_MINUTE", 900: "FIFTEEN_MINUTE",
            1800: "THIRTY_MINUTE", 3600: "ONE_HOUR", 21600: "SIX_HOUR", 86400: "ONE_DAY",
        }
        granularity_name = GRANULARITY_NAMES.get(int(granularity), str(granularity))
        params = {"start": start, "end": end, "granularity": granularity_name}

        # Build auth headers (JWT for Cloud keys, HMAC for legacy keys)
        request_path = f"/api/v3/brokerage/products/{product_id}/candles"
        auth_headers = self._build_auth_headers("GET", request_path)
        response = requests.get(url, params=params, headers=auth_headers or None, timeout=10)
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

    def _build_auth_headers(self, method: str, request_path: str, query_string: str = "") -> Dict[str, str]:
        """Build Coinbase auth headers (JWT for CDP Cloud keys, HMAC for legacy keys)."""
        api_key = self.credentials.get("api_key") or self.credentials.get("CB_ACCESS_KEY")
        api_secret = self.credentials.get("api_secret") or self.credentials.get("CB_ACCESS_SECRET")
        if not api_key or not api_secret:
            return {}

        # Coinbase Cloud (CDP) keys use JWT auth (key format: organizations/.../apiKeys/...).
        if str(api_key).startswith("organizations/"):
            try:
                import jwt
                from cryptography.hazmat.primitives import serialization
                import secrets
            except ImportError as exc:
                raise RuntimeError(
                    "PyJWT and cryptography are required for Coinbase Cloud key authentication"
                ) from exc

            now = int(time.time())
            payload = {
                "sub": api_key,
                "iss": "cdp",
                "nbf": now,
                "exp": now + 120,
                "uri": f"{method.upper()} api.coinbase.com{request_path}",
            }

            secret = str(api_secret).strip()
            if "\\n" in secret:
                secret = secret.replace("\\n", "\n")

            private_key = serialization.load_pem_private_key(
                secret.encode("utf-8"), password=None
            )
            token = jwt.encode(
                payload,
                private_key,
                algorithm="ES256",
                headers={"kid": api_key, "nonce": secrets.token_hex()},
            )
            return {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

        # Legacy Coinbase keys use HMAC headers.
        timestamp = str(int(time.time()))
        message = f"{timestamp}{method.upper()}{request_path}{query_string}"
        try:
            secret_bytes = base64.b64decode(api_secret)
        except Exception:
            secret_bytes = str(api_secret).encode("utf-8")

        signature = base64.b64encode(
            hmac.new(secret_bytes, message.encode("utf-8"), hashlib.sha256).digest()
        ).decode("utf-8")

        return {
            "CB-ACCESS-KEY": api_key,
            "CB-ACCESS-SIGN": signature,
            "CB-ACCESS-TIMESTAMP": timestamp,
        }

    def get_historical_candles(
        self, product_id: str, count: int = 500, granularity: str = "ONE_HOUR"
    ) -> List[Dict[str, Any]]:
        """
        Fetch historical candles in Coinbase Advanced Trade format.

        Args:
            product_id: Coinbase product (e.g., BTC-USD, ETH-USD)
            count: Number of candles to fetch
            granularity: Coinbase granularity enum (e.g., ONE_HOUR)

        Returns:
            List of OHLCV dicts: date, open, high, low, close, volume
        """
        import requests

        normalized_product = self._normalize_asset_pair(product_id)
        granularity_enum = self.GRANULARITY_ENUMS.get(granularity, granularity)
        granularity_seconds = self.GRANULARITIES.get(granularity_enum)
        if not granularity_seconds:
            raise ValueError(f"Unsupported granularity: {granularity}")

        end_ts = int(time.time())
        start_ts = end_ts - (granularity_seconds * max(1, count))

        payload: Dict[str, Any] = {}

        # Prefer official Coinbase SDK with credentials when available.
        api_key = self.credentials.get("api_key") or self.credentials.get("CB_ACCESS_KEY")
        api_secret = self.credentials.get("api_secret") or self.credentials.get("CB_ACCESS_SECRET")
        if api_key and api_secret:
            try:
                from coinbase.rest import RESTClient

                use_sandbox = bool(self.credentials.get("use_sandbox", False))
                base_url = "api-sandbox.coinbase.com" if use_sandbox else "api.coinbase.com"
                client = RESTClient(api_key=api_key, api_secret=api_secret, base_url=base_url)
                sdk_response = client.get_candles(
                    product_id=normalized_product,
                    start=str(start_ts),
                    end=str(end_ts),
                    granularity=granularity_enum,
                )
                payload = sdk_response if isinstance(sdk_response, dict) else sdk_response.to_dict()
            except Exception as sdk_error:
                logger.warning(
                    "Coinbase SDK candle fetch failed for %s (%s). Falling back to direct API request.",
                    normalized_product,
                    sdk_error,
                )

        if not payload:
            request_path = f"/api/v3/brokerage/products/{normalized_product}/candles"
            params = {
                "start": start_ts,
                "end": end_ts,
                "granularity": granularity_enum,
            }
            query_string = f"?{urlencode(params)}"

            headers = self._build_auth_headers("GET", request_path, query_string)

            self.rate_limiter.wait_for_token()
            response = self.circuit_breaker.call_sync(
                requests.get,
                f"{self.BASE_URL}{request_path}",
                params=params,
                headers=headers or None,
                timeout=10,
            )
            response.raise_for_status()
            payload = response.json()

        candles = []
        for candle in payload.get("candles", []):
            ts = int(candle.get("start", 0))
            date = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
            candles.append(
                {
                    "date": date,
                    "open": float(candle.get("open", 0)),
                    "high": float(candle.get("high", 0)),
                    "low": float(candle.get("low", 0)),
                    "close": float(candle.get("close", 0)),
                    "volume": float(candle.get("volume", 0)),
                }
            )

        candles.sort(key=lambda x: x["date"])
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
