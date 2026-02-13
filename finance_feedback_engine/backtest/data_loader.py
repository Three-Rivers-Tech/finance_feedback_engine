"""
Historical Data Manager (THR-300 Task A)

Fetches and caches historical candles from broker APIs.
"""

import logging
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
import json

logger = logging.getLogger(__name__)


class HistoricalDataManager:
    """Manages historical market data with caching."""
    
    CACHE_DIR = Path("data/historical")
    
    # Supported granularities (Oanda format)
    GRANULARITIES = {
        "M1": 60,           # 1 minute
        "M5": 300,          # 5 minutes  
        "M15": 900,         # 15 minutes
        "M30": 1800,        # 30 minutes
        "H1": 3600,         # 1 hour
        "H4": 14400,        # 4 hours
        "D": 86400,         # 1 day
    }
    
    def __init__(self, cache_format: str = "parquet"):
        """
        Initialize data manager.
        
        Args:
            cache_format: 'parquet' (default) or 'csv'
        """
        self.cache_format = cache_format
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"HistoricalDataManager initialized (cache: {cache_format})")
    
    def fetch_history(
        self,
        symbol: str,
        granularity: str = "M5",
        count: int = 5000,
        platform = None,
        use_cache: bool = True
    ) -> pd.DataFrame:
        """
        Fetch historical candles with caching.
        
        Args:
            symbol: Trading pair (e.g., 'EUR_USD', 'BTC-USD')
            granularity: Timeframe ('M1', 'M5', 'H1', 'D')
            count: Number of candles to fetch
            platform: Trading platform instance (required if not using cache)
            use_cache: Whether to use cached data if available
        
        Returns:
            DataFrame with columns: time, open, high, low, close, volume
        """
        if granularity not in self.GRANULARITIES:
            raise ValueError(f"Unsupported granularity: {granularity}. Use: {list(self.GRANULARITIES.keys())}")
        
        # Generate cache filename
        cache_file = self._get_cache_path(symbol, granularity, count)
        
        # Try to load from cache
        if use_cache and cache_file.exists():
            try:
                df = self._load_from_cache(cache_file)
                logger.info(f"Loaded {len(df)} candles from cache: {cache_file.name}")
                return df
            except Exception as e:
                logger.warning(f"Failed to load cache: {e}, fetching fresh data")
        
        # Fetch from platform
        if platform is None:
            raise ValueError("Platform instance required to fetch fresh data")
        
        logger.info(f"Fetching {count} {granularity} candles for {symbol}...")
        
        try:
            # Determine platform type and fetch accordingly
            platform_name = platform.__class__.__name__.lower()
            
            # For unified platform, use the underlying Oanda or Coinbase platform
            if "unified" in platform_name:
                # Access platforms dictionary
                platforms = getattr(platform, 'platforms', {})
                
                # Try Oanda first (best for forex like EUR_USD)
                if 'oanda' in platforms:
                    df = self._fetch_from_oanda(platforms['oanda'], symbol, granularity, count)
                elif 'coinbase' in platforms:
                    df = self._fetch_from_coinbase(platforms['coinbase'], symbol, granularity, count)
                else:
                    raise ValueError(f"Unified platform has no sub-platforms. Available: {list(platforms.keys())}")
            elif "oanda" in platform_name:
                df = self._fetch_from_oanda(platform, symbol, granularity, count)
            elif "coinbase" in platform_name:
                df = self._fetch_from_coinbase(platform, symbol, granularity, count)
            else:
                raise ValueError(f"Unsupported platform: {platform_name}")
            
            # Save to cache
            if not df.empty:
                self._save_to_cache(df, cache_file)
                logger.info(f"Cached {len(df)} candles to {cache_file.name}")
            
            return df
            
        except Exception as e:
            logger.error(f"Failed to fetch historical data: {e}")
            raise
    
    def _fetch_from_oanda(
        self,
        platform,
        symbol: str,
        granularity: str,
        count: int
    ) -> pd.DataFrame:
        """Fetch data from Oanda platform."""
        from oandapyV20.endpoints.instruments import InstrumentsCandles
        
        client = platform._get_client()
        
        params = {
            "granularity": granularity,
            "count": min(count, 5000),  # Oanda max 5000 per request
        }
        
        request = InstrumentsCandles(instrument=symbol, params=params)
        response = client.request(request)
        
        candles = response.get("candles", [])
        
        if not candles:
            logger.warning(f"No candles returned for {symbol} {granularity}")
            return pd.DataFrame()
        
        # Parse candles into DataFrame
        data = []
        for candle in candles:
            if not candle.get("complete"):
                continue  # Skip incomplete candles
            
            mid = candle.get("mid", {})
            data.append({
                "time": pd.to_datetime(candle["time"]),
                "open": float(mid.get("o", 0)),
                "high": float(mid.get("h", 0)),
                "low": float(mid.get("l", 0)),
                "close": float(mid.get("c", 0)),
                "volume": int(candle.get("volume", 0))
            })
        
        df = pd.DataFrame(data)
        df = df.sort_values("time").reset_index(drop=True)
        
        logger.info(f"Fetched {len(df)} candles from Oanda")
        return df
    
    def _fetch_from_coinbase(
        self,
        platform,
        symbol: str,
        granularity: str,
        count: int
    ) -> pd.DataFrame:
        """Fetch data from Coinbase platform."""
        # Convert granularity to seconds
        granularity_seconds = self.GRANULARITIES[granularity]
        
        # Calculate time range (Coinbase uses start/end times)
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(seconds=granularity_seconds * count)
        
        # Coinbase Advanced Trade API uses different product format
        # EUR_USD → EUR-USD
        symbol_formatted = symbol.replace("_", "-")
        
        try:
            # This would require Coinbase candles endpoint implementation
            # For now, raise NotImplementedError
            raise NotImplementedError("Coinbase historical data fetching not yet implemented")
        except Exception as e:
            logger.error(f"Coinbase data fetch failed: {e}")
            raise
    
    def _get_cache_path(self, symbol: str, granularity: str, count: int) -> Path:
        """Generate cache file path."""
        filename = f"{symbol}_{granularity}_{count}.{self.cache_format}"
        return self.CACHE_DIR / filename
    
    def _load_from_cache(self, cache_file: Path) -> pd.DataFrame:
        """Load DataFrame from cache file."""
        if self.cache_format == "parquet":
            df = pd.read_parquet(cache_file)
        else:  # csv
            df = pd.read_csv(cache_file, parse_dates=["time"])
        
        return df
    
    def _save_to_cache(self, df: pd.DataFrame, cache_file: Path) -> None:
        """Save DataFrame to cache file."""
        if self.cache_format == "parquet":
            df.to_parquet(cache_file, index=False)
        else:  # csv
            df.to_csv(cache_file, index=False)
    
    def clear_cache(self, symbol: Optional[str] = None):
        """
        Clear cached data.
        
        Args:
            symbol: If provided, only clear this symbol's cache. Otherwise clear all.
        """
        if symbol:
            pattern = f"{symbol}_*"
        else:
            pattern = "*"
        
        count = 0
        for cache_file in self.CACHE_DIR.glob(f"{pattern}.{self.cache_format}"):
            cache_file.unlink()
            count += 1
        
        logger.info(f"Cleared {count} cached file(s)")
    
    def list_cached_data(self) -> list:
        """List all cached datasets."""
        cached = []
        
        for cache_file in self.CACHE_DIR.glob(f"*.{self.cache_format}"):
            # Parse filename: SYMBOL_GRANULARITY_COUNT.format
            parts = cache_file.stem.split("_")
            if len(parts) >= 3:
                cached.append({
                    "symbol": "_".join(parts[:-2]),
                    "granularity": parts[-2],
                    "count": parts[-1],
                    "file": cache_file.name,
                    "size_mb": cache_file.stat().st_size / 1024 / 1024
                })
        
        return cached
