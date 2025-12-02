"""Unified data provider with cascading fallback across Alpha Vantage, Coinbase, and Oanda."""

from typing import Dict, Any, List, Optional, Tuple
import logging
import time
from datetime import datetime, timedelta

from .alpha_vantage_provider import AlphaVantageProvider
from .coinbase_data import CoinbaseDataProvider
from .oanda_data import OandaDataProvider
from ..utils.rate_limiter import RateLimiter
from ..utils.circuit_breaker import CircuitBreakerOpenError

logger = logging.getLogger(__name__)


class UnifiedDataProvider:
    """
    Unified data provider with intelligent cascading fallback.
    
    Provider priority:
    1. Alpha Vantage (primary - comprehensive data with news/macro)
    2. Coinbase (fallback for crypto assets)
    3. Oanda (fallback for forex pairs)
    
    Features:
    - Automatic provider selection based on asset type
    - Circuit breaker integration per provider
    - 5-minute in-memory caching to reduce API calls
    - Shared rate limiting across all providers
    """

    def __init__(
        self,
        alpha_vantage_api_key: Optional[str] = None,
        coinbase_credentials: Optional[Dict[str, Any]] = None,
        oanda_credentials: Optional[Dict[str, Any]] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize unified data provider.

        Args:
            alpha_vantage_api_key: Alpha Vantage API key
            coinbase_credentials: Coinbase credentials (optional for public data)
            oanda_credentials: Oanda credentials
            config: Additional configuration
        """
        self.config = config or {}
        
        # Shared rate limiter (30 tokens capacity, 6 tokens/min refill)
        self.rate_limiter = RateLimiter(
            tokens_per_second=0.1,  # 6 per minute = 0.1 per second
            max_tokens=30
        )
        
        # Initialize providers
        self.alpha_vantage = None
        self.coinbase = None
        self.oanda = None
        
        if alpha_vantage_api_key:
            try:
                self.alpha_vantage = AlphaVantageProvider(
                    api_key=alpha_vantage_api_key,
                    config=config
                )
                logger.info("Alpha Vantage provider initialized (primary)")
            except Exception as e:
                logger.warning(f"Failed to initialize Alpha Vantage: {e}")
        
        if coinbase_credentials:
            try:
                self.coinbase = CoinbaseDataProvider(
                    credentials=coinbase_credentials,
                    rate_limiter=self.rate_limiter
                )
                logger.info("Coinbase data provider initialized (crypto fallback)")
            except Exception as e:
                logger.warning(f"Failed to initialize Coinbase data: {e}")
        
        if oanda_credentials:
            try:
                self.oanda = OandaDataProvider(
                    credentials=oanda_credentials,
                    rate_limiter=self.rate_limiter
                )
                logger.info("Oanda data provider initialized (forex fallback)")
            except Exception as e:
                logger.warning(f"Failed to initialize Oanda data: {e}")
        
        # In-memory cache: {(asset_pair, granularity): (candles, timestamp)}
        self._cache: Dict[Tuple[str, str], Tuple[List[Dict], float]] = {}
        self._cache_ttl = 300  # 5 minutes
        
        logger.info("UnifiedDataProvider initialized with cascading fallback")

    def _is_crypto(self, asset_pair: str) -> bool:
        """Check if asset pair is crypto."""
        pair = asset_pair.upper()
        crypto_symbols = ['BTC', 'ETH', 'SOL', 'DOGE', 'ADA', 'DOT', 'LINK']
        return any(symbol in pair for symbol in crypto_symbols)

    def _is_forex(self, asset_pair: str) -> bool:
        """Check if asset pair is forex."""
        pair = asset_pair.upper()
        forex_currencies = ['EUR', 'GBP', 'JPY', 'CHF', 'AUD', 'CAD', 'NZD']
        # Check if pair contains forex currencies but not crypto
        has_forex = any(curr in pair for curr in forex_currencies)
        has_usd = 'USD' in pair
        return has_forex and has_usd and not self._is_crypto(pair)

    def _get_cached_candles(
        self,
        asset_pair: str,
        granularity: str
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Get candles from cache if available and fresh.
        
        Args:
            asset_pair: Asset pair
            granularity: Timeframe
        
        Returns:
            Cached candles or None if expired/missing
        """
        cache_key = (asset_pair.upper(), granularity)
        
        if cache_key in self._cache:
            candles, cached_time = self._cache[cache_key]
            age = time.time() - cached_time
            
            if age < self._cache_ttl:
                logger.debug(
                    f"Cache hit for {asset_pair} {granularity} "
                    f"(age: {age:.1f}s)"
                )
                return candles
            else:
                # Expired, remove from cache
                del self._cache[cache_key]
        
        return None

    def _cache_candles(
        self,
        asset_pair: str,
        granularity: str,
        candles: List[Dict[str, Any]]
    ) -> None:
        """
        Store candles in cache.
        
        Args:
            asset_pair: Asset pair
            granularity: Timeframe
            candles: Candle data to cache
        """
        cache_key = (asset_pair.upper(), granularity)
        self._cache[cache_key] = (candles, time.time())
        logger.debug(f"Cached {len(candles)} candles for {asset_pair} {granularity}")

    def get_candles(
        self,
        asset_pair: str,
        granularity: str = '1d',
        limit: int = 300,
        force_provider: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], str]:
        """
        Fetch historical candles with cascading provider fallback.
        
        Args:
            asset_pair: Asset pair (e.g., 'BTCUSD', 'EURUSD')
            granularity: Timeframe ('1m', '5m', '15m', '1h', '4h', '1d')
            limit: Number of candles to fetch
            force_provider: Force specific provider ('alpha_vantage', 'coinbase', 'oanda')
        
        Returns:
            Tuple of (candles list, provider_name used)
        
        Raises:
            ValueError: If all providers fail
        """
        logger.info(f"Fetching {granularity} candles for {asset_pair}")
        
        # Check cache first
        cached = self._get_cached_candles(asset_pair, granularity)
        if cached is not None:
            return cached, 'cache'
        
        # Determine provider priority based on asset type
        is_crypto = self._is_crypto(asset_pair)
        is_forex = self._is_forex(asset_pair)
        
        providers = []
        
        if force_provider:
            # Force specific provider
            if force_provider == 'alpha_vantage' and self.alpha_vantage:
                providers = [('alpha_vantage', self.alpha_vantage)]
            elif force_provider == 'coinbase' and self.coinbase:
                providers = [('coinbase', self.coinbase)]
            elif force_provider == 'oanda' and self.oanda:
                providers = [('oanda', self.oanda)]
        else:
            # Cascading fallback based on asset type
            if is_crypto:
                # Crypto: Alpha Vantage → Coinbase
                if self.alpha_vantage:
                    providers.append(('alpha_vantage', self.alpha_vantage))
                if self.coinbase:
                    providers.append(('coinbase', self.coinbase))
            elif is_forex:
                # Forex: Alpha Vantage → Oanda
                if self.alpha_vantage:
                    providers.append(('alpha_vantage', self.alpha_vantage))
                if self.oanda:
                    providers.append(('oanda', self.oanda))
            else:
                # Unknown: try all in order
                if self.alpha_vantage:
                    providers.append(('alpha_vantage', self.alpha_vantage))
                if self.coinbase:
                    providers.append(('coinbase', self.coinbase))
                if self.oanda:
                    providers.append(('oanda', self.oanda))
        
        # Try each provider in order
        last_error = None
        for provider_name, provider in providers:
            try:
                logger.debug(f"Trying provider: {provider_name}")
                
                # Use provider-specific method if available
                if hasattr(provider, 'get_candles'):
                    candles = provider.get_candles(asset_pair, granularity, limit)
                else:
                    # Alpha Vantage doesn't have get_candles yet, skip for now
                    logger.debug(f"Provider {provider_name} doesn't support get_candles")
                    continue
                
                if candles:
                    # Success! Cache and return
                    self._cache_candles(asset_pair, granularity, candles)
                    logger.info(
                        f"Retrieved {len(candles)} candles from {provider_name}"
                    )
                    return candles, provider_name
                
            except CircuitBreakerOpenError:
                logger.warning(f"Circuit breaker open for {provider_name}")
                last_error = f"{provider_name} circuit breaker open"
                continue
            except Exception as e:
                logger.warning(f"Provider {provider_name} failed: {e}")
                last_error = str(e)
                continue
        
        # All providers failed
        error_msg = f"All providers failed for {asset_pair}. Last error: {last_error}"
        logger.error(error_msg)
        raise ValueError(error_msg)

    def get_multi_timeframe_data(
        self,
        asset_pair: str,
        timeframes: Optional[List[str]] = None
    ) -> Dict[str, Tuple[List[Dict[str, Any]], str]]:
        """
        Fetch data across multiple timeframes.
        
        Args:
            asset_pair: Asset pair
            timeframes: List of timeframes (default: ['1m', '5m', '15m', '1h', '4h', '1d'])
        
        Returns:
            Dictionary mapping timeframe to (candles, provider_name)
        """
        if timeframes is None:
            timeframes = ['1m', '5m', '15m', '1h', '4h', '1d']
        
        results = {}
        
        for tf in timeframes:
            try:
                candles, provider = self.get_candles(asset_pair, tf)
                results[tf] = (candles, provider)
            except Exception as e:
                logger.warning(f"Failed to fetch {tf} data: {e}")
                results[tf] = ([], 'failed')
        
        return results
