"""Alpha Vantage data provider module."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
from aiohttp_retry import ExponentialRetry, RetryClient

from ..utils.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError
from ..utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class AlphaVantageProvider:
    """
    Data provider for Alpha Vantage Premium API.

    Supports various asset types including cryptocurrencies and forex.
    """

    BASE_URL = "https://www.alphavantage.co/query"

    def __post_init_session_lock(self):
        # Helper to ensure the session lock exists (for pickling/compatibility)
        if not hasattr(self, "_session_lock"):
            import asyncio

            self._session_lock = asyncio.Lock()

    def __init__(
        self,
        api_key: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        session: Optional[aiohttp.ClientSession] = None,
        rate_limiter: Optional[Any] = None,
        is_backtest: bool = False,
    ):
        """
        Initialize Alpha Vantage provider.

        Args:
            api_key: Alpha Vantage API key (premium recommended)
            config: Optional configuration dictionary with timeout settings
            session: Optional aiohttp.ClientSession
            rate_limiter: Optional rate limiter instance
            is_backtest: If True, allows mock data fallback for testing (default: False)
        """
        if not api_key:
            raise ValueError("Alpha Vantage API key is required")
        self.api_key = api_key
        self.config = config or {}
        self.is_backtest = is_backtest
        # Defer aiohttp.ClientSession creation to async request time to avoid
        # requiring a running event loop during synchronous initialization.
        self.session = session

        # Ensure rate limiter is always active - create default if not provided
        self.rate_limiter = rate_limiter or self._create_default_rate_limiter()
        self._owned_session = False
        import asyncio

        self._session_lock = asyncio.Lock()
        self._context_count = 0  # Track active async context manager entries

        # Simple in-memory cache for API responses
        self._cache: Dict[str, Any] = {}
        self._cache_ttl: Dict[str, datetime] = {}

        # Timeout configuration (industry best practice)
        api_timeouts = self.config.get("api_timeouts", {})
        self.timeout_market_data = api_timeouts.get("market_data", 10)
        self.timeout_sentiment = api_timeouts.get("sentiment", 15)
        self.timeout_macro = api_timeouts.get("macro", 10)

        # Circuit breaker for API calls (prevent cascading failures)
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=60.0,
            expected_exception=aiohttp.ClientError,
            name="AlphaVantage-API",
        )

        logger.info(
            "Alpha Vantage provider initialized with timeouts: "
            f"market={self.timeout_market_data}s, "
            f"sentiment={self.timeout_sentiment}s, "
            f"macro={self.timeout_macro}s, "
            "caching=enabled"
        )

    def _get_from_cache(self, key: str, ttl_seconds: int) -> Optional[Dict[str, Any]]:
        """
        Get data from cache if not expired.

        Args:
            key: Cache key
            ttl_seconds: Time-to-live in seconds

        Returns:
            Cached data if valid, None otherwise
        """
        if key in self._cache:
            cache_time = self._cache_ttl.get(key)
            if cache_time:
                age_seconds = (datetime.now(timezone.utc) - cache_time).total_seconds()
                if age_seconds < ttl_seconds:
                    logger.debug(f"Cache hit for {key} (age: {age_seconds:.1f}s)")
                    return self._cache[key]
                else:
                    logger.debug(
                        f"Cache expired for {key} (age: {age_seconds:.1f}s > {ttl_seconds}s)"
                    )
        return None

    def _set_cache(self, key: str, value: Dict[str, Any]):
        """
        Store data in cache with timestamp.

        Args:
            key: Cache key
            value: Data to cache
        """
        self._cache[key] = value
        self._cache_ttl[key] = datetime.now(timezone.utc)
        logger.debug(f"Cached {key}")

    async def close(self):
        """Close the aiohttp session if owned by this provider."""
        if self.session and self._owned_session:
            await self.session.close()

    async def __aenter__(self):
        """Async context manager entry.

        Supports nested async with usage: only closes session when all contexts exit.
        """
        async with self._session_lock:
            await self._ensure_session()
            self._context_count += 1
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit.

        Only closes the session when all nested contexts have exited.
        """
        if self._context_count > 0:
            self._context_count -= 1
        if self._context_count == 0:
            await self.close()

    def __del__(self):
        """Cleanup on garbage collection - warn if session not closed."""
        if self.session and self._owned_session:
            try:
                if not self.session.closed:
                    # Cannot await in __del__, but we can warn
                    logger.warning(
                        "AlphaVantageProvider session not properly closed. "
                        "Use 'await provider.close()' or 'async with provider:' pattern."
                    )
            except Exception:
                # Logging may be shut down during interpreter exit; ignore
                pass
        return False

    async def _async_request(
        self, params: Dict[str, Any], timeout: int
    ) -> Dict[str, Any]:
        """
        Make an asynchronous HTTP request with retries.

        Args:
            params: Request parameters
            timeout: Request timeout

        Returns:
            JSON response
        """
        # Apply rate limiting - always active since rate_limiter is always created
        rate_limiter_acquired = False
        rate_limiter_release = None
        try:
            # Prefer async context manager if available
            if hasattr(self.rate_limiter, "__aenter__") and hasattr(
                self.rate_limiter, "__aexit__"
            ):
                # Use as async context manager for the whole request
                async with self.rate_limiter:
                    return await self._do_async_request(params, timeout)
            elif hasattr(self.rate_limiter, "acquire") and hasattr(
                self.rate_limiter, "release"
            ):
                # Semaphore-like interface: acquire before, release in finally
                await self.rate_limiter.acquire()
                rate_limiter_acquired = True
                rate_limiter_release = self.rate_limiter.release
            elif hasattr(self.rate_limiter, "wait"):
                # Wait-based interface
                await self.rate_limiter.wait()
            elif callable(self.rate_limiter):
                # Direct callable - check if it returns awaitable
                result = self.rate_limiter()
                if hasattr(result, "__await__"):
                    await result
        except Exception as e:
            logger.warning(f"Rate limiter error: {e}")
            # Propagate limiter exceptions to allow upstream handling
            raise

        # Lazily create a session and retry client within an event loop context
        if self.session is None:
            await self._ensure_session()

        # Check if session is closed before making request
        if self.session.closed:
            logger.error(
                "Session is closed before request! Recreating session. "
                "This indicates a session lifecycle issue."
            )
            self.session = None
            await self._ensure_session()

        retry = ExponentialRetry(attempts=3)
        # Initialize RetryClient bound to an existing session
        # CRITICAL FIX: Do NOT close RetryClient as it closes the underlying session
        client = RetryClient(client_session=self.session, retry_options=retry)
        try:
            async with client.get(
                self.BASE_URL, params=params, timeout=timeout
            ) as resp:
                resp.raise_for_status()
                return await resp.json()
        finally:
            # DO NOT close the client - it would close our shared session
            # await client.close()  # REMOVED - this was closing the shared session
            pass
            # Always release the rate limiter if acquired
            if rate_limiter_acquired and rate_limiter_release:
                try:
                    maybe_awaitable = rate_limiter_release()
                    if hasattr(maybe_awaitable, "__await__"):
                        await maybe_awaitable
                except Exception as e:
                    logger.warning(f"Error releasing rate limiter: {e}")

    async def _do_async_request(
        self, params: Dict[str, Any], timeout: int
    ) -> Dict[str, Any]:
        """
        Helper for _async_request to perform the actual HTTP request
        (for use with async context manager rate limiter).
        """
        if self.session is None:
            await self._ensure_session()

        # Check if session is closed before making request
        if self.session.closed:
            logger.error(
                "Session is closed before request in _do_async_request! Recreating session. "
                "This indicates a session lifecycle issue."
            )
            self.session = None
            await self._ensure_session()

        retry = ExponentialRetry(attempts=3)
        client = RetryClient(client_session=self.session, retry_options=retry)
        try:
            async with client.get(
                self.BASE_URL, params=params, timeout=timeout
            ) as resp:
                resp.raise_for_status()
                return await resp.json()
        finally:
            # DO NOT close the client - it would close our shared session
            # await client.close()  # REMOVED - this was closing the shared session
            pass

    async def _ensure_session(self):
        """
        Ensure that self.session is initialized, guarded by a lock to prevent race conditions.
        """
        # Defensive: allow for possible missing lock (e.g., after unpickling)
        self.__post_init_session_lock()
        async with self._session_lock:
            if self.session is None:
                self.session = aiohttp.ClientSession()
                self._owned_session = True

    async def get_market_data(
        self, asset_pair: str, force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Fetch market data for a given asset pair.

        Args:
            asset_pair: Asset pair (e.g., 'BTCUSD', 'EURUSD')
            force_refresh: If True, bypass cache and force fresh API call

        Returns:
            Dictionary containing market data

        Raises:
            CircuitBreakerOpenError: If circuit breaker is open
            ValueError: If data validation fails or data is stale
        """
        logger.info(
            "Fetching market data for %s (force_refresh=%s)", asset_pair, force_refresh
        )

        try:
            # Determine asset type and fetch appropriate data
            if "BTC" in asset_pair or "ETH" in asset_pair:
                market_data = await self._get_crypto_data(
                    asset_pair, force_refresh=force_refresh
                )
            else:
                market_data = await self._get_forex_data(
                    asset_pair, force_refresh=force_refresh
                )

            # Validate data quality
            is_valid, issues = self.validate_market_data(market_data, asset_pair)
            if not is_valid:
                logger.warning(
                    f"Market data validation issues for {asset_pair}: {issues}"
                )
                # Continue with warning, but flag in data
                market_data["validation_warnings"] = issues

            # Enrich with additional context
            market_data = await self._enrich_market_data(market_data, asset_pair)

            return market_data

        except CircuitBreakerOpenError:
            logger.error(f"Circuit breaker open for {asset_pair}")
            raise
        except ValueError as e:
            # Stale data or validation errors - log and re-raise
            logger.error(f"Data validation failed for {asset_pair}: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to fetch market data for {asset_pair}: {e}")
            raise

    # ------------------------------------------------------------------
    # Historical Batch Data
    # ------------------------------------------------------------------
    async def get_historical_data(
        self,
        asset_pair: str,
        start: str,
        end: str,
        timeframe: str = "1h",
    ) -> list:
        """Return a list of OHLC dictionaries within [start,end] for the specified timeframe.

        Supports both daily and intraday timeframes:
        - '1m', '5m', '15m', '30m', '1h': Intraday (last 100 candles from API, may need pagination)
        - '1d': Daily (up to full history available)

        Uses appropriate Alpha Vantage endpoints based on timeframe.
        Falls back to synthetic mock candles if API fails.
        Each candle dict keys: date, open, high, low, close.

        Args:
            asset_pair: Asset pair (e.g., 'BTCUSD', 'EURUSD')
            start: Start date (YYYY-MM-DD format)
            end: End date (YYYY-MM-DD format)
            timeframe: Timeframe ('1m', '5m', '15m', '30m', '1h', '1d'). Defaults to '1h'.

        Returns:
            List of OHLC candle dictionaries
        """
        # Validate timeframe
        valid_timeframes = ["1m", "5m", "15m", "30m", "1h", "1d"]
        if timeframe not in valid_timeframes:
            logger.warning(
                f"Invalid timeframe '{timeframe}', defaulting to '1h'. "
                f"Valid options: {valid_timeframes}"
            )
            timeframe = "1h"

        try:
            start_dt = datetime.strptime(start, "%Y-%m-%d").date()
            end_dt = datetime.strptime(end, "%Y-%m-%d").date()
            if end_dt < start_dt:
                raise ValueError("End date precedes start date")

            # Decide endpoint by asset type
            if "BTC" in asset_pair or "ETH" in asset_pair:
                # Crypto
                if asset_pair.endswith("USD"):
                    symbol = asset_pair[:-3]
                    market = "USD"
                else:
                    symbol = asset_pair[:3]
                    market = asset_pair[3:]

                # Use INTRADAY for intraday, DAILY for daily
                if timeframe == "1d":
                    params = {
                        "function": "DIGITAL_CURRENCY_DAILY",
                        "symbol": symbol,
                        "market": market,
                        "apikey": self.api_key,
                    }
                    series_key = "Time Series (Digital Currency Daily)"
                else:
                    # Intraday: map timeframe to API interval
                    interval_map = {
                        "1m": "1min",
                        "5m": "5min",
                        "15m": "15min",
                        "30m": "30min",
                        "1h": "60min",
                    }
                    interval = interval_map.get(timeframe, "60min")
                    params = {
                        "function": "DIGITAL_CURRENCY_INTRADAY",
                        "symbol": symbol,
                        "market": market,
                        "interval": interval,
                        "apikey": self.api_key,
                    }
                    series_key = f"Time Series Crypto ({interval})"

                data = await self._async_request(params, timeout=15)
            else:
                # Forex
                from_currency = asset_pair[:3]
                to_currency = asset_pair[3:]

                # Use INTRADAY for intraday, DAILY for daily
                if timeframe == "1d":
                    params = {
                        "function": "FX_DAILY",
                        "from_symbol": from_currency,
                        "to_symbol": to_currency,
                        "apikey": self.api_key,
                    }
                    series_key = "Time Series FX (Daily)"
                else:
                    # Intraday: map timeframe to API interval
                    interval_map = {
                        "1m": "1min",
                        "5m": "5min",
                        "15m": "15min",
                        "30m": "30min",
                        "1h": "60min",
                    }
                    interval = interval_map.get(timeframe, "60min")
                    params = {
                        "function": "FX_INTRADAY",
                        "from_symbol": from_currency,
                        "to_symbol": to_currency,
                        "interval": interval,
                        "apikey": self.api_key,
                    }
                    series_key = f"Time Series FX ({interval})"

                data = await self._async_request(params, timeout=15)

            # CRITICAL FIX: Handle multiple possible field names for crypto intraday data
            time_series = None
            if series_key in data:
                time_series = data[series_key]
            else:
                # Try fallback keys for crypto intraday (API response format varies)
                if "BTC" in asset_pair or "ETH" in asset_pair:
                    fallback_keys = [
                        f"Time Series Crypto ({interval})",
                        f"Time Series ({interval})",
                        "Time Series Crypto (60min)",
                        "Time Series (60min)",
                        "Time Series",
                    ]
                    for fallback_key in fallback_keys:
                        if fallback_key in data:
                            logger.info(
                                "Using fallback key '%s' for %s (expected: %s)",
                                fallback_key,
                                asset_pair,
                                series_key,
                            )
                            time_series = data[fallback_key]
                            break

            if not time_series:
                logger.warning(
                    "Historical data unexpected format for %s (timeframe: %s, expected key: %s, available keys: %s)",
                    asset_pair,
                    timeframe,
                    series_key,
                    list(data.keys()),
                )
                return self._generate_mock_series(start_dt, end_dt, timeframe)
            candles = []

            # Parse datetime based on timeframe
            if timeframe == "1d":
                # Daily format: YYYY-MM-DD
                date_format = "%Y-%m-%d"
            else:
                # Intraday format: YYYY-MM-DD HH:MM:SS
                date_format = "%Y-%m-%d %H:%M:%S"

            for timestamp_str, candle_data in time_series.items():
                try:
                    if timeframe == "1d":
                        candle_dt = datetime.strptime(timestamp_str, date_format).date()
                    else:
                        candle_dt = datetime.strptime(timestamp_str, date_format).date()

                    # Filter by date range
                    if candle_dt < start_dt or candle_dt > end_dt:
                        continue

                    # Field name differences for crypto vs forex
                    o_val = (
                        candle_data.get("1a. open (USD)")
                        or candle_data.get("1. open")
                        or candle_data.get("1. open", 0)
                    )
                    h_val = (
                        candle_data.get("2a. high (USD)")
                        or candle_data.get("2. high")
                        or candle_data.get("2. high", 0)
                    )
                    low_val = (
                        candle_data.get("3a. low (USD)")
                        or candle_data.get("3. low")
                        or candle_data.get("3. low", 0)
                    )
                    c_val = (
                        candle_data.get("4a. close (USD)")
                        or candle_data.get("4. close")
                        or candle_data.get("4. close", 0)
                    )
                    candles.append(
                        {
                            "date": timestamp_str,
                            "open": float(o_val),
                            "high": float(h_val),
                            "low": float(low_val),
                            "close": float(c_val),
                        }
                    )
                except (ValueError, TypeError):
                    continue

            # Sort ascending by date
            candles.sort(key=lambda x: x["date"])

            if not candles:
                logger.warning(
                    "No candles extracted for %s (timeframe: %s) in date range %s to %s",
                    asset_pair,
                    timeframe,
                    start_dt,
                    end_dt,
                )
                return self._generate_mock_series(start_dt, end_dt, timeframe)

            logger.info(
                "Fetched %d %s candles for %s from %s to %s",
                len(candles),
                timeframe,
                asset_pair,
                start_dt,
                end_dt,
            )
            return candles

        except Exception as e:  # noqa: BLE001
            logger.error(
                "Historical data fetch failed for %s (timeframe: %s): %s",
                asset_pair,
                timeframe,
                e,
            )
            try:
                start_dt = datetime.strptime(start, "%Y-%m-%d").date()
                end_dt = datetime.strptime(end, "%Y-%m-%d").date()
                return self._generate_mock_series(start_dt, end_dt, timeframe)
            except (ValueError, TypeError):
                return []

    def _generate_mock_series(self, start_dt, end_dt, timeframe: str = "1d") -> list:
        """Synthetic series fallback (linear drift) supporting intraday timeframes.

        Args:
            start_dt: Start date
            end_dt: End date
            timeframe: Timeframe ('1m', '5m', '15m', '30m', '1h', '1d')

        Returns:
            List of mock OHLC candles
        """
        from datetime import timedelta

        base = 100.0
        out = []

        if timeframe == "1d":
            # Daily candles
            span = (end_dt - start_dt).days + 1
            for i in range(span):
                d = start_dt + timedelta(days=i)
                drift = 1 + (i / span) * 0.02  # +2% over full period
                close = base * drift
                out.append(
                    {
                        "date": d.isoformat(),
                        "open": close * 0.995,
                        "high": close * 1.01,
                        "low": close * 0.99,
                        "close": close,
                        "mock": True,
                    }
                )
        else:
            # Intraday candles
            timeframe_to_minutes = {
                "1m": 1,
                "5m": 5,
                "15m": 15,
                "30m": 30,
                "1h": 60,
            }
            minutes_per_candle = timeframe_to_minutes.get(timeframe, 60)

            # Generate intraday candles from start to end
            current = datetime.combine(start_dt, datetime.min.time())
            end_datetime = datetime.combine(end_dt, datetime.max.time())

            candle_index = 0
            while current <= end_datetime:
                # Market hours filter (optional: 0-24 for crypto, 9-17 for forex, skipped here)
                drift = 1 + (candle_index / 1000) * 0.02  # Gentle drift
                volatility = 1 + (candle_index % 10) * 0.001  # Intraday volatility
                close = base * drift * volatility

                out.append(
                    {
                        "date": current.strftime("%Y-%m-%d %H:%M:%S"),
                        "open": close * 0.998,
                        "high": close * 1.005,
                        "low": close * 0.995,
                        "close": close,
                        "mock": True,
                    }
                )

                current += timedelta(minutes=minutes_per_candle)
                candle_index += 1

        return out

    async def _enrich_market_data(
        self, market_data: Dict[str, Any], asset_pair: str
    ) -> Dict[str, Any]:
        """
        Enrich market data with additional metrics and context.

        Args:
            market_data: Base market data
            asset_pair: Asset pair

        Returns:
            Enriched market data
        """
        try:
            # Calculate additional technical indicators
            open_price = market_data.get("open", 0)
            high_price = market_data.get("high", 0)
            low_price = market_data.get("low", 0)
            close_price = market_data.get("close", 0)

            # Price range
            price_range = high_price - low_price
            price_range_pct = (
                (price_range / close_price * 100) if close_price > 0 else 0
            )

            # Body vs wick analysis (candlestick)
            body = abs(close_price - open_price)
            body_pct = (body / close_price * 100) if close_price > 0 else 0

            # Upper and lower wicks
            upper_wick = high_price - max(open_price, close_price)
            lower_wick = min(open_price, close_price) - low_price

            # Trend direction
            is_bullish = close_price > open_price
            trend = (
                "bullish"
                if is_bullish
                else "bearish" if close_price < open_price else "neutral"
            )

            # Position in range (where did it close)
            if price_range > 0:
                close_position_in_range = (close_price - low_price) / price_range
            else:
                close_position_in_range = 0.5

            # Add enrichments
            market_data["price_range"] = price_range
            market_data["price_range_pct"] = price_range_pct
            market_data["body_size"] = body
            market_data["body_pct"] = body_pct
            market_data["upper_wick"] = upper_wick
            market_data["lower_wick"] = lower_wick
            market_data["trend"] = trend
            market_data["is_bullish"] = is_bullish
            market_data["close_position_in_range"] = close_position_in_range

            # Fetch technical indicators if available
            technical_data = await self._get_technical_indicators(asset_pair)
            if technical_data:
                market_data.update(technical_data)

        except Exception as e:  # noqa: BLE001
            logger.warning("Error enriching market data: %s", e)

        return market_data

    async def _get_technical_indicators(self, asset_pair: str) -> Dict[str, Any]:
        """
        Fetch technical indicators from Alpha Vantage.

        Args:
            asset_pair: Asset pair

        Returns:
            Dictionary with technical indicators
        """
        indicators = {}

        try:
            # Determine symbol format
            if "BTC" in asset_pair or "ETH" in asset_pair:
                # For crypto, use the base currency
                symbol = asset_pair[:3] if len(asset_pair) > 3 else asset_pair
            else:
                # For forex, we'll skip detailed indicators for now as AlphaVantage
                # does not directly support technical indicator functions for FX pairs.
                return indicators

            # --- Fetch RSI (Relative Strength Index) ---
            try:
                rsi_params = {
                    "function": "RSI",
                    "symbol": symbol,
                    "interval": "daily",
                    "time_period": 14,
                    "series_type": "close",
                    "apikey": self.api_key,
                }
                rsi_data = await self._async_request(
                    rsi_params, timeout=self.timeout_market_data
                )
                if "Technical Analysis: RSI" in rsi_data:
                    rsi_series = rsi_data["Technical Analysis: RSI"]
                    latest_rsi = list(rsi_series.values())[0]
                    indicators["rsi"] = float(latest_rsi.get("RSI", 0))

                    # Interpret RSI
                    if indicators["rsi"] > 70:
                        indicators["rsi_signal"] = "overbought"
                    elif indicators["rsi"] < 30:
                        indicators["rsi_signal"] = "oversold"
                    else:
                        indicators["rsi_signal"] = "neutral"
            except Exception as e:
                logger.debug(f"Could not fetch RSI for {asset_pair}: {e}")

            # --- Fetch MACD (Moving Average Convergence Divergence) ---
            try:
                macd_params = {
                    "function": "MACD",
                    "symbol": symbol,
                    "interval": "daily",
                    "series_type": "close",
                    "apikey": self.api_key,
                }
                macd_data = await self._async_request(
                    macd_params, timeout=self.timeout_market_data
                )
                if "Technical Analysis: MACD" in macd_data:
                    macd_series = macd_data["Technical Analysis: MACD"]
                    latest_macd = list(macd_series.values())[0]
                    indicators["macd"] = float(latest_macd.get("MACD", 0))
                    indicators["macd_signal"] = float(latest_macd.get("MACD_Signal", 0))
                    indicators["macd_hist"] = float(latest_macd.get("MACD_Hist", 0))
            except Exception as e:
                logger.debug(f"Could not fetch MACD for {asset_pair}: {e}")

            # --- Fetch BBANDS (Bollinger Bands) ---
            try:
                bbands_params = {
                    "function": "BBANDS",
                    "symbol": symbol,
                    "interval": "daily",
                    "time_period": 20,
                    "series_type": "close",
                    "apikey": self.api_key,
                }
                bbands_data = await self._async_request(
                    bbands_params, timeout=self.timeout_market_data
                )
                if "Technical Analysis: BBANDS" in bbands_data:
                    bbands_series = bbands_data["Technical Analysis: BBANDS"]
                    latest_bbands = list(bbands_series.values())[0]
                    indicators["bbands_upper"] = float(
                        latest_bbands.get("Real Upper Band", 0)
                    )
                    indicators["bbands_middle"] = float(
                        latest_bbands.get("Real Middle Band", 0)
                    )
                    indicators["bbands_lower"] = float(
                        latest_bbands.get("Real Lower Band", 0)
                    )
            except Exception as e:
                logger.debug(f"Could not fetch BBANDS for {asset_pair}: {e}")

        except Exception as e:  # noqa: BLE001
            logger.debug("Could not fetch technical indicators: %s", e)

        return indicators

    async def get_market_regime(
        self, asset_pair: str, force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Get market regime with 5-minute caching (Phase 2 optimization).

        Market regime includes: trend (bullish/bearish/sideways), volatility (high/low),
        and momentum indicators.

        Args:
            asset_pair: Asset pair to analyze
            force_refresh: Bypass cache and fetch fresh data

        Returns:
            Dictionary with market regime data
        """
        cache_key = f"regime_{asset_pair}"

        if not force_refresh:
            cached = self._get_from_cache(cache_key, ttl_seconds=300)
            if cached:
                logger.debug(f"Market regime cache hit for {asset_pair}")
                return cached

        # Calculate market regime from recent data
        try:
            # Get recent historical data for regime analysis
            from datetime import timedelta

            end_date = datetime.utcnow().date()
            start_date = end_date - timedelta(days=30)

            candles = await self.get_historical_data(
                asset_pair=asset_pair,
                start=start_date.isoformat(),
                end=end_date.isoformat(),
                timeframe="1d",
            )

            if len(candles) < 10:
                # Not enough data for regime calculation
                regime_data = {
                    "trend": "unknown",
                    "volatility": "unknown",
                    "momentum": "neutral",
                    "confidence": 0,
                }
            else:
                # Calculate simple trend (last 20 days)
                recent_closes = [c["close"] for c in candles[-20:]]
                trend_direction = (
                    "bullish" if recent_closes[-1] > recent_closes[0] else "bearish"
                )

                # Calculate volatility (std dev of returns)
                returns = [
                    (recent_closes[i] - recent_closes[i - 1]) / recent_closes[i - 1]
                    for i in range(1, len(recent_closes))
                ]
                import statistics

                volatility = statistics.stdev(returns) if len(returns) > 1 else 0
                volatility_level = "high" if volatility > 0.03 else "low"

                # Calculate momentum (rate of change)
                momentum_pct = (
                    ((recent_closes[-1] - recent_closes[-5]) / recent_closes[-5] * 100)
                    if len(recent_closes) >= 5
                    else 0
                )
                momentum = "strong" if abs(momentum_pct) > 5 else "weak"

                regime_data = {
                    "trend": trend_direction,
                    "volatility": volatility_level,
                    "volatility_value": volatility,
                    "momentum": momentum,
                    "momentum_pct": momentum_pct,
                    "confidence": 75,
                }

            self._set_cache(cache_key, regime_data)
            return regime_data

        except Exception as e:
            logger.warning(f"Market regime calculation failed for {asset_pair}: {e}")
            return {
                "trend": "unknown",
                "volatility": "unknown",
                "momentum": "neutral",
                "confidence": 0,
                "error": str(e),
            }

    async def get_technical_indicators_cached(
        self, asset_pair: str, indicators: List[str], force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Get technical indicators with smart caching (Phase 2 optimization).

        Fast indicators (RSI, MACD): 60s TTL
        Slow indicators (SMA_200, EMA_200): 300s TTL

        Args:
            asset_pair: Asset pair
            indicators: List of indicator names
            force_refresh: Bypass cache

        Returns:
            Dictionary with indicator values
        """
        cache_key = f"indicators_{asset_pair}_{'_'.join(sorted(indicators))}"

        # Determine TTL based on indicator types
        slow_indicators = ["SMA_200", "EMA_200", "SMA_100", "EMA_100"]
        has_slow = any(ind in slow_indicators for ind in indicators)
        ttl = 300 if has_slow else 60  # 5 min for slow, 1 min for fast

        if not force_refresh:
            cached = self._get_from_cache(cache_key, ttl_seconds=ttl)
            if cached:
                logger.debug(
                    f"Technical indicators cache hit for {asset_pair} (TTL: {ttl}s)"
                )
                return cached

        # Fetch indicators (use existing _get_technical_indicators method)
        indicator_data = await self._get_technical_indicators(asset_pair)

        self._set_cache(cache_key, indicator_data)
        return indicator_data

    async def get_news_sentiment(
        self, asset_pair: str, limit: int = 5, force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Fetch news sentiment data with 15-minute caching (Phase 2 optimization).

        Args:
            asset_pair: Asset pair to get news for
            limit: Maximum number of news items
            force_refresh: Bypass cache

        Returns:
            Dictionary with sentiment analysis
        """
        # Check cache first (15 min TTL)
        cache_key = f"sentiment_{asset_pair}_{limit}"
        if not force_refresh:
            cached = self._get_from_cache(cache_key, ttl_seconds=900)  # 15 minutes
            if cached:
                logger.debug(f"Sentiment cache hit for {asset_pair}")
                return cached

        sentiment_data = {
            "available": False,
            "overall_sentiment": "neutral",
            "sentiment_score": 0.0,
            "news_count": 0,
            "top_topics": [],
        }

        try:
            # Extract ticker/symbol
            if "BTC" in asset_pair:
                tickers = "CRYPTO:BTC"
            elif "ETH" in asset_pair:
                tickers = "CRYPTO:ETH"
            else:
                # For forex, use currency codes
                tickers = asset_pair[:3]

            params = {
                "function": "NEWS_SENTIMENT",
                "tickers": tickers,
                "apikey": self.api_key,
                "limit": limit,
            }

            data = await self._async_request(params, timeout=10)

            if "feed" in data and len(data["feed"]) > 0:
                sentiment_data["available"] = True
                sentiment_data["news_count"] = len(data["feed"])

                # Calculate average sentiment
                sentiment_scores = []
                topics = []

                for article in data["feed"][:limit]:
                    # Overall article sentiment
                    overall_score = float(article.get("overall_sentiment_score", 0))
                    sentiment_scores.append(overall_score)

                    # Extract topics
                    if "topics" in article:
                        for topic in article["topics"]:
                            topics.append(topic.get("topic", ""))

                # Average sentiment
                if sentiment_scores:
                    avg_sentiment = sum(sentiment_scores) / len(sentiment_scores)
                    sentiment_data["sentiment_score"] = avg_sentiment

                    # Classify sentiment
                    if avg_sentiment > 0.15:
                        sentiment_data["overall_sentiment"] = "bullish"
                    elif avg_sentiment < -0.15:
                        sentiment_data["overall_sentiment"] = "bearish"
                    else:
                        sentiment_data["overall_sentiment"] = "neutral"

                # Top topics
                if topics:
                    from collections import Counter

                    topic_counts = Counter(topics)
                    sentiment_data["top_topics"] = [
                        t[0] for t in topic_counts.most_common(3)
                    ]

        except Exception as e:  # noqa: BLE001
            logger.debug("Could not fetch news sentiment: %s", e)

        # Cache the result (even if unavailable, to prevent repeated failed calls)
        self._set_cache(cache_key, sentiment_data)
        return sentiment_data

    async def get_macro_indicators(
        self, indicators: Optional[list] = None
    ) -> Dict[str, Any]:
        """
        Fetch macroeconomic indicators from Alpha Vantage.

        Args:
            indicators: List of indicators to fetch (default: key indicators)

        Returns:
            Dictionary with macro indicators
        """
        if indicators is None:
            indicators = ["REAL_GDP", "INFLATION", "FEDERAL_FUNDS_RATE", "UNEMPLOYMENT"]

        macro_data = {"available": False, "indicators": {}}

        try:
            for indicator in indicators[:3]:  # Limit to avoid rate limits
                params = {"function": indicator, "apikey": self.api_key}

                data = await self._async_request(params, timeout=10)

                if "data" in data and len(data["data"]) > 0:
                    latest = data["data"][0]
                    macro_data["indicators"][indicator] = {
                        "value": latest.get("value", "N/A"),
                        "date": latest.get("date", "N/A"),
                    }
                    macro_data["available"] = True

        except Exception as e:  # noqa: BLE001
            logger.debug("Could not fetch macro indicators: %s", e)

        return macro_data

    async def get_comprehensive_market_data(
        self,
        asset_pair: str,
        include_sentiment: bool = True,
        include_macro: bool = False,
    ) -> Dict[str, Any]:
        """
        Fetch comprehensive market data including price, sentiment, and macro.

        Args:
            asset_pair: Asset pair to analyze
            include_sentiment: Whether to include news sentiment
            include_macro: Whether to include macro indicators

        Returns:
            Comprehensive market data dictionary
        """
        # Get base market data
        market_data = await self.get_market_data(asset_pair)

        # Add sentiment if requested
        if include_sentiment:
            sentiment = await self.get_news_sentiment(asset_pair)
            market_data["sentiment"] = sentiment

        # Add macro indicators if requested
        if include_macro:
            macro = await self.get_macro_indicators()
            market_data["macro"] = macro

        return market_data

    async def get_multi_timeframe_data(
        self,
        asset_pair: str,
        timeframes: Optional[List[str]] = None,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """
        Fetch market data for multiple timeframes with independent validation.

        CRITICAL: Each timeframe is validated independently. Stale data in one
        timeframe does NOT block other timeframes. Returns partial results with
        metadata about each timeframe's status.

        Args:
            asset_pair: Asset pair (e.g., 'BTCUSD', 'EURUSD')
            timeframes: List of timeframes to fetch (default: ['1h', '4h', 'daily'])
            force_refresh: If True, bypass cache and force fresh API call

        Returns:
            Dictionary with results per timeframe:
            {
                "asset_pair": "BTCUSD",
                "timeframes": {
                    "1h": {
                        "status": "success" | "stale" | "error",
                        "data": {...},  # Market data if available
                        "age_seconds": 120,
                        "age_hours": 0.033,
                        "stale_data": False,
                        "error": None  # Error message if failed
                    },
                    "4h": {...},
                    "daily": {...}
                },
                "has_any_fresh_data": True,
                "all_stale": False,
                "fetch_timestamp": "2024-12-17T17:50:00Z"
            }
        """
        if timeframes is None:
            timeframes = ["1h", "4h", "daily"]

        logger.info(
            "Fetching multi-timeframe data for %s: timeframes=%s, force_refresh=%s",
            asset_pair,
            timeframes,
            force_refresh,
        )

        results = {
            "asset_pair": asset_pair,
            "timeframes": {},
            "has_any_fresh_data": False,
            "all_stale": True,
            "fetch_timestamp": datetime.utcnow().isoformat() + "Z",
        }

        # Fetch each timeframe independently
        for timeframe in timeframes:
            try:
                logger.info("Fetching %s data for %s", timeframe, asset_pair)

                # Determine which endpoint to use based on timeframe
                if timeframe == "daily":
                    # Use daily endpoint
                    data = await self.get_market_data(
                        asset_pair, force_refresh=force_refresh
                    )
                else:
                    # For intraday timeframes, we'll use historical data endpoint
                    # Get last 2 candles to have latest data
                    from datetime import timedelta

                    end_date = datetime.utcnow().date()
                    start_date = end_date - timedelta(days=2)

                    candles = await self.get_historical_data(
                        asset_pair=asset_pair,
                        start=start_date.isoformat(),
                        end=end_date.isoformat(),
                        timeframe=timeframe,
                    )

                    if candles:
                        # Convert latest candle to market data format
                        latest = candles[-1]
                        data = {
                            "asset_pair": asset_pair,
                            "timestamp": datetime.utcnow().isoformat(),
                            "date": latest.get("date"),
                            "open": latest.get("open"),
                            "high": latest.get("high"),
                            "low": latest.get("low"),
                            "close": latest.get("close"),
                            "timeframe": timeframe,
                            "type": (
                                "crypto"
                                if "BTC" in asset_pair or "ETH" in asset_pair
                                else "forex"
                            ),
                        }

                        # Add validation for intraday data
                        from ..utils.market_schedule import MarketSchedule
                        from ..utils.validation import validate_data_freshness

                        asset_type = (
                            "crypto"
                            if "BTC" in asset_pair or "ETH" in asset_pair
                            else "forex"
                        )
                        market_status = MarketSchedule.get_market_status(
                            asset_pair=asset_pair, asset_type=asset_type, now_utc=None
                        )

                        # Parse candle timestamp
                        try:
                            candle_dt = datetime.fromisoformat(
                                latest.get("date").replace("Z", "+00:00")
                            )
                            if candle_dt.tzinfo is None:
                                candle_dt = candle_dt.replace(tzinfo=timezone.utc)
                            candle_timestamp = candle_dt.isoformat()
                        except Exception as e:
                            logger.warning("Could not parse candle timestamp: %s", e)
                            candle_timestamp = latest.get("date")

                        is_fresh, age_str, freshness_msg = validate_data_freshness(
                            candle_timestamp,
                            asset_type=asset_type,
                            timeframe=timeframe,
                            market_status=market_status,
                        )

                        data["stale_data"] = not is_fresh
                        data["data_age_hours"] = (
                            float(age_str.split()[0]) if "hours" in age_str else 0
                        )
                        data["freshness_message"] = (
                            freshness_msg if not is_fresh else ""
                        )
                    else:
                        raise ValueError(f"No candles returned for {timeframe}")

                # Extract staleness info
                is_stale = data.get("stale_data", False)
                age_seconds = data.get("data_age_seconds", 0)
                age_hours = data.get("data_age_hours", 0)

                # Determine status
                if is_stale:
                    status = "stale"
                    logger.warning(
                        "%s data for %s is STALE (age: %.2f hours)",
                        timeframe,
                        asset_pair,
                        age_hours,
                    )
                else:
                    status = "success"
                    results["has_any_fresh_data"] = True
                    results["all_stale"] = False
                    logger.info(
                        "%s data for %s is FRESH (age: %.2f hours)",
                        timeframe,
                        asset_pair,
                        age_hours,
                    )

                results["timeframes"][timeframe] = {
                    "status": status,
                    "data": data,
                    "age_seconds": age_seconds,
                    "age_hours": age_hours,
                    "stale_data": is_stale,
                    "error": None,
                }

            except Exception as e:
                # Log error but continue with other timeframes
                logger.error(
                    "Failed to fetch %s data for %s: %s",
                    timeframe,
                    asset_pair,
                    e,
                    exc_info=True,
                )
                results["timeframes"][timeframe] = {
                    "status": "error",
                    "data": None,
                    "age_seconds": None,
                    "age_hours": None,
                    "stale_data": True,
                    "error": str(e),
                }

        # Log summary
        success_count = sum(
            1 for tf in results["timeframes"].values() if tf["status"] == "success"
        )
        stale_count = sum(
            1 for tf in results["timeframes"].values() if tf["status"] == "stale"
        )
        error_count = sum(
            1 for tf in results["timeframes"].values() if tf["status"] == "error"
        )

        logger.info(
            "Multi-timeframe fetch complete for %s: %d success, %d stale, %d errors",
            asset_pair,
            success_count,
            stale_count,
            error_count,
        )

        return results

    async def _get_crypto_data(
        self, asset_pair: str, force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Fetch cryptocurrency data with retry and circuit breaker.

        Args:
            asset_pair: Crypto pair (e.g., 'BTCUSD')
            force_refresh: If True, bypass cache and force fresh API call

        Returns:
            Dictionary containing crypto market data

        Raises:
            ValueError: If data is stale and cannot be refreshed
        """
        # Check cache first (5 min TTL)
        cache_key = f"crypto_{asset_pair}_daily"
        if not force_refresh:
            cached = self._get_from_cache(cache_key, ttl_seconds=300)
            if cached:
                logger.debug(f"Returning cached crypto data for {asset_pair}")
                return cached

        # Extract base and quote currencies
        if asset_pair.endswith("USD"):
            symbol = asset_pair[:-3]
            market = "USD"
        else:
            symbol = asset_pair[:3]
            market = asset_pair[3:]

        params = {
            "function": "DIGITAL_CURRENCY_DAILY",
            "symbol": symbol,
            "market": market,
            "apikey": self.api_key,
        }

        try:
            # Use circuit breaker for API call
            async def api_call():
                return await self._async_request(
                    params, timeout=self.timeout_market_data
                )

            data = await self.circuit_breaker.call(api_call)

            if "Time Series (Digital Currency Daily)" in data:
                time_series = data["Time Series (Digital Currency Daily)"]
                latest_date = list(time_series.keys())[0]
                latest_data = time_series[latest_date]

                # Try different field name formats (API response varies)
                open_price = float(
                    latest_data.get("1a. open (USD)") or latest_data.get("1. open") or 0
                )
                high_price = float(
                    latest_data.get("2a. high (USD)") or latest_data.get("2. high") or 0
                )
                low_price = float(
                    latest_data.get("3a. low (USD)") or latest_data.get("3. low") or 0
                )
                close_price = float(
                    latest_data.get("4a. close (USD)")
                    or latest_data.get("4. close")
                    or 0
                )
                volume = float(latest_data.get("5. volume", 0))
                market_cap = float(latest_data.get("6. market cap (USD)", 0))

                # CRITICAL FIX: Market-aware data freshness validation
                try:
                    from ..utils.market_schedule import MarketSchedule
                    from ..utils.validation import validate_data_freshness

                    # Parse the date and create an ISO timestamp at market close (assume 23:59 UTC)
                    data_date = datetime.strptime(latest_date, "%Y-%m-%d")
                    data_timestamp = (
                        data_date.replace(hour=23, minute=59, second=0).isoformat()
                        + "Z"
                    )

                    # Get market status for context-aware validation
                    market_status = MarketSchedule.get_market_status(
                        asset_pair=asset_pair, asset_type="crypto", now_utc=None
                    )

                    is_fresh, age_str, freshness_msg = validate_data_freshness(
                        data_timestamp,
                        asset_type="crypto",
                        timeframe="daily",
                        market_status=market_status,
                    )

                    if not is_fresh:
                        # CRITICAL CHANGE: Don't raise exception, return data with stale flag
                        logger.error(
                            "Stale crypto data for %s: %s. "
                            "API returned data from %s (%s old). "
                            "Returning data with stale_data flag.",
                            asset_pair,
                            freshness_msg,
                            latest_date,
                            age_str,
                        )
                        # Don't raise - let decision engine handle stale data
                        stale_data_warning = {
                            "stale_data": True,
                            "data_age_seconds": (
                                datetime.utcnow() - data_date
                            ).total_seconds(),
                            "data_age_hours": (
                                datetime.utcnow() - data_date
                            ).total_seconds()
                            / 3600,
                            "data_date": latest_date,
                            "freshness_message": freshness_msg,
                        }
                    else:
                        logger.info(
                            "Data freshness validated for %s: %s old (within threshold)",
                            asset_pair,
                            age_str,
                        )
                        stale_data_warning = {
                            "stale_data": False,
                            "data_age_seconds": (
                                datetime.utcnow() - data_date
                            ).total_seconds(),
                            "data_age_hours": (
                                datetime.utcnow() - data_date
                            ).total_seconds()
                            / 3600,
                            "data_date": latest_date,
                        }

                except ValueError as e:
                    # Validation errors - log and continue with warning
                    logger.warning(
                        "Data freshness validation error for %s: %s", asset_pair, e
                    )
                    stale_data_warning = {
                        "stale_data": True,
                        "validation_error": str(e),
                        "data_date": latest_date,
                    }
                except Exception as e:
                    logger.warning(
                        "Could not validate data freshness for %s: %s", asset_pair, e
                    )
                    stale_data_warning = {"stale_data": False, "data_date": latest_date}

                result = {
                    "asset_pair": asset_pair,
                    "timestamp": datetime.utcnow().isoformat(),
                    "date": latest_date,
                    "open": open_price,
                    "high": high_price,
                    "low": low_price,
                    "close": close_price,
                    "volume": volume,
                    "market_cap": market_cap,
                    "type": "crypto",
                }
                # Add staleness metadata
                result.update(stale_data_warning)

                # Cache the result
                self._set_cache(cache_key, result)

                return result
            else:
                logger.warning(
                    "Unexpected response format for %s: %s", asset_pair, data
                )
                # In live mode, this will raise an exception; in backtest mode, returns mock data
                return self._create_mock_data(asset_pair, "crypto")

        except ValueError:
            # Re-raise stale data errors and mock data violations
            raise
        except Exception as e:  # noqa: BLE001
            logger.error("Error fetching crypto data for %s: %s", asset_pair, e)
            # In live mode, this will raise an exception; in backtest mode, returns mock data
            return self._create_mock_data(asset_pair, "crypto")

    async def _get_forex_data(
        self, asset_pair: str, force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Fetch forex data with retry and circuit breaker.

        Args:
            asset_pair: Forex pair (e.g., 'EURUSD')
            force_refresh: If True, bypass cache and force fresh API call

        Returns:
            Dictionary containing forex market data

        Raises:
            ValueError: If data is stale and cannot be refreshed
        """
        # Check cache first (5 min TTL)
        cache_key = f"forex_{asset_pair}_daily"
        if not force_refresh:
            cached = self._get_from_cache(cache_key, ttl_seconds=300)
            if cached:
                logger.debug(f"Returning cached forex data for {asset_pair}")
                return cached

        from_currency = asset_pair[:3]
        to_currency = asset_pair[3:]

        params = {
            "function": "FX_DAILY",
            "from_symbol": from_currency,
            "to_symbol": to_currency,
            "apikey": self.api_key,
        }

        try:
            # Use circuit breaker for API call
            async def api_call():
                return await self._async_request(
                    params, timeout=self.timeout_market_data
                )

            data = await self.circuit_breaker.call(api_call)

            if "Time Series FX (Daily)" in data:
                time_series = data["Time Series FX (Daily)"]
                latest_date = list(time_series.keys())[0]
                latest_data = time_series[latest_date]

                # CRITICAL FIX: Market-aware data freshness validation for forex
                try:
                    from ..utils.market_schedule import MarketSchedule
                    from ..utils.validation import validate_data_freshness

                    # Parse the date and create an ISO timestamp at market close (assume 23:59 UTC)
                    data_date = datetime.strptime(latest_date, "%Y-%m-%d")
                    data_timestamp = (
                        data_date.replace(hour=23, minute=59, second=0).isoformat()
                        + "Z"
                    )

                    # Get market status for context-aware validation
                    market_status = MarketSchedule.get_market_status(
                        asset_pair=asset_pair, asset_type="forex", now_utc=None
                    )

                    is_fresh, age_str, freshness_msg = validate_data_freshness(
                        data_timestamp,
                        asset_type="forex",
                        timeframe="daily",
                        market_status=market_status,
                    )

                    if not is_fresh:
                        # CRITICAL CHANGE: Don't raise exception, return data with stale flag
                        logger.error(
                            "Stale forex data for %s: %s. "
                            "API returned data from %s (%s old). "
                            "Market status: %s. Returning data with stale_data flag.",
                            asset_pair,
                            freshness_msg,
                            latest_date,
                            age_str,
                            market_status.get("session", "Unknown"),
                        )
                        # Don't raise - let decision engine handle stale data
                        stale_data_warning = {
                            "stale_data": True,
                            "data_age_seconds": (
                                datetime.utcnow() - data_date
                            ).total_seconds(),
                            "data_age_hours": (
                                datetime.utcnow() - data_date
                            ).total_seconds()
                            / 3600,
                            "data_date": latest_date,
                            "freshness_message": freshness_msg,
                            "market_session": market_status.get("session", "Unknown"),
                            "market_open": market_status.get("is_open", True),
                        }
                    else:
                        logger.info(
                            "Data freshness validated for %s: %s old (within threshold), session: %s",
                            asset_pair,
                            age_str,
                            market_status.get("session", "Unknown"),
                        )
                        stale_data_warning = {
                            "stale_data": False,
                            "data_age_seconds": (
                                datetime.utcnow() - data_date
                            ).total_seconds(),
                            "data_age_hours": (
                                datetime.utcnow() - data_date
                            ).total_seconds()
                            / 3600,
                            "data_date": latest_date,
                            "market_session": market_status.get("session", "Unknown"),
                        }

                except ValueError as e:
                    # Validation errors - log and continue with warning
                    logger.warning(
                        "Data freshness validation error for %s: %s", asset_pair, e
                    )
                    stale_data_warning = {
                        "stale_data": True,
                        "validation_error": str(e),
                        "data_date": latest_date,
                    }
                except Exception as e:
                    logger.warning(
                        "Could not validate data freshness for %s: %s", asset_pair, e
                    )
                    stale_data_warning = {"stale_data": False, "data_date": latest_date}

                result = {
                    "asset_pair": asset_pair,
                    "timestamp": datetime.utcnow().isoformat(),
                    "date": latest_date,
                    "open": float(latest_data.get("1. open", 0)),
                    "high": float(latest_data.get("2. high", 0)),
                    "low": float(latest_data.get("3. low", 0)),
                    "close": float(latest_data.get("4. close", 0)),
                    "type": "forex",
                }
                # Add staleness metadata
                result.update(stale_data_warning)

                # Cache the result
                self._set_cache(cache_key, result)

                return result
            else:
                logger.warning(
                    "Unexpected response format for %s: %s", asset_pair, data
                )
                # In live mode, this will raise an exception; in backtest mode, returns mock data
                return self._create_mock_data(asset_pair, "forex")

        except ValueError:
            # Re-raise stale data errors and mock data violations
            raise
        except Exception as e:  # noqa: BLE001
            logger.error("Error fetching forex data for %s: %s", asset_pair, e)
            # In live mode, this will raise an exception; in backtest mode, returns mock data
            return self._create_mock_data(asset_pair, "forex")

    def _create_mock_data(self, asset_pair: str, asset_type: str) -> Dict[str, Any]:
        """
        Create mock data for testing/demo purposes.

        CRITICAL SAFETY: This method is ONLY allowed in backtesting or testing modes.
        In live trading mode, it raises an exception to prevent trading on fake data.

        Args:
            asset_pair: Asset pair
            asset_type: Type of asset (crypto/forex)

        Returns:
            Mock market data

        Raises:
            ValueError: If called in live trading mode (is_backtest=False)
        """
        # CRITICAL SAFETY CHECK: Block mock data in live trading mode
        if not self.is_backtest:
            error_msg = (
                f"CRITICAL SAFETY VIOLATION: Attempted to create mock data for {asset_pair} "
                f"in LIVE TRADING MODE. Mock data generation is ONLY allowed in backtesting/testing. "
                f"This indicates a real market data fetch failure. Trading decisions cannot be made "
                f"on fabricated data in live mode. Check API connectivity, rate limits, and data availability."
            )
            logger.critical(error_msg)
            raise ValueError(error_msg)

        # Mock data is allowed in backtest/test mode
        logger.warning(
            "Creating mock data for %s (BACKTEST MODE ONLY - this would be blocked in live trading)",
            asset_pair,
        )

        base_price = 50000.0 if asset_type == "crypto" else 1.1

        return {
            "asset_pair": asset_pair,
            "timestamp": datetime.utcnow().isoformat(),
            "date": datetime.utcnow().date().isoformat(),
            "open": base_price,
            "high": base_price * 1.02,
            "low": base_price * 0.98,
            "close": base_price * 1.01,
            "volume": 1000000.0 if asset_type == "crypto" else 0,
            "type": asset_type,
            "mock": True,
        }

    def validate_market_data(
        self, data: Dict[str, Any], asset_pair: str
    ) -> Tuple[bool, List[str]]:
        """
        Validate market data quality and completeness.

        Industry best practice: Always validate input data before processing
        to catch stale data, missing fields, or invalid values.

        Args:
            data: Market data dictionary to validate
            asset_pair: Asset pair for logging context

        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []

        # Check for required OHLC fields
        required_fields = ["open", "high", "low", "close"]
        missing_fields = [f for f in required_fields if f not in data or data[f] == 0]
        if missing_fields:
            issues.append(f"Missing OHLC fields: {missing_fields}")

        # Check for stale data (if timestamp available)
        if "timestamp" in data and not data.get("mock", False):
            try:
                data_time = datetime.fromisoformat(
                    data["timestamp"].replace("Z", "+00:00")
                )
                age = datetime.utcnow() - data_time.replace(tzinfo=None)
                if age.total_seconds() > 86400:  # 24 hour threshold for daily data
                    issues.append(
                        f"Market data is stale " f"({age.total_seconds():.0f}s old)"
                    )
            except (ValueError, TypeError) as e:
                issues.append(f"Invalid timestamp format: {e}")

        # Sanity checks on OHLC values
        if all(f in data for f in required_fields):
            high = data["high"]
            low = data["low"]
            close = data["close"]
            open_price = data["open"]

            if high < low:
                issues.append(f"Invalid OHLC: high ({high}) < low ({low})")

            if not (low <= close <= high):
                issues.append(
                    f"Invalid OHLC: close ({close}) " f"not in range [{low}, {high}]"
                )

            if not (low <= open_price <= high):
                issues.append(
                    f"Invalid OHLC: open ({open_price}) "
                    f"not in range [{low}, {high}]"
                )

            # Check for zero or negative prices
            if any(data[f] <= 0 for f in required_fields):
                issues.append("OHLC contains zero or negative values")

        # Return validation result
        is_valid = len(issues) == 0
        if not is_valid:
            logger.warning(f"Market data validation failed for {asset_pair}: {issues}")

        return is_valid, issues

    def _create_default_rate_limiter(self) -> RateLimiter:
        """
        Create a default rate limiter with conservative settings for Alpha Vantage API.
        The default rate is set to 5 requests per minute (0.0833 requests per second)
        with a burst capacity of 5 tokens to handle short bursts of API calls.
        This is well below the free tier limit of 5 requests per minute.
        """
        # Get rate limiter configuration from config or use defaults
        rate_limiter_config = self.config.get("rate_limiter", {})

        # Conservative defaults for Alpha Vantage (5 requests per minute)
        tokens_per_second = rate_limiter_config.get(
            "tokens_per_second", 0.0833
        )  # ~5 per minute
        max_tokens = rate_limiter_config.get("max_tokens", 5)  # Burst capacity

        logger.info(
            f"Creating default rate limiter for AlphaVantage: "
            f"{tokens_per_second:.4f} tokens/sec, max {max_tokens} tokens"
        )

        return RateLimiter(tokens_per_second=tokens_per_second, max_tokens=max_tokens)

    async def warm_cache(self, asset_pairs: List[str]) -> None:
        """
        Pre-populate cache for configured asset pairs (Phase 2 optimization).

        This method is called on startup to warm the cache with frequently-accessed data,
        reducing cold-start latency on the first trading decision.

        Args:
            asset_pairs: List of asset pairs to warm cache for
        """
        logger.info(f"Warming cache for {len(asset_pairs)} asset pairs...")

        for asset_pair in asset_pairs:
            try:
                # Warm market data cache
                (
                    await self._get_crypto_data(asset_pair)
                    if "BTC" in asset_pair or "ETH" in asset_pair
                    else await self._get_forex_data(asset_pair)
                )
                logger.debug(f"✓ Market data cached for {asset_pair}")

                # Warm market regime cache
                await self.get_market_regime(asset_pair)
                logger.debug(f"✓ Market regime cached for {asset_pair}")

                # Warm technical indicators cache (common indicators)
                await self.get_technical_indicators_cached(asset_pair, ["RSI", "MACD"])
                logger.debug(f"✓ Technical indicators cached for {asset_pair}")

            except Exception as e:
                logger.warning(f"Cache warming failed for {asset_pair}: {e}")
                continue

        logger.info(f"Cache warming complete for {len(asset_pairs)} asset pairs")

    def get_circuit_breaker_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics for monitoring."""
        return self.circuit_breaker.get_stats()
