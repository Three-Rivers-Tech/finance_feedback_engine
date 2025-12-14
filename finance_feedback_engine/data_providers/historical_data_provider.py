import pandas as pd
from datetime import datetime
from datetime import timezone
from typing import Optional, Union
import logging
import numpy as np
from pathlib import Path

from .alpha_vantage_provider import AlphaVantageProvider
from ..utils.financial_data_validator import FinancialDataValidator
from ..persistence.timeseries_data_store import TimeSeriesDataStore

logger = logging.getLogger(__name__)


class HistoricalDataProvider:
    """
    Manages fetching, processing, and validating historical financial data.

    This class provides a structured way to interact with historical data sources,
    ensuring data quality and consistency before it's used for backtesting,
    training, or analysis.

    Implementation Notes:
    - **Pluggable Data Sources:** Designed to be flexible, allowing integration
      with various historical data APIs (e.g., Alpha Vantage, Yahoo Finance,
      custom databases). The `_fetch_raw_data` method should be implemented
      by subclasses or dynamically configured.
    - **Data Cleaning & Validation:** Integrates a placeholder for data cleaning
      and validation using `FinancialDataValidator` to catch issues like missing
      values, incorrect formats, or outliers.
    - **Standardized Output:** Ensures that fetched data is consistently returned
      as a pandas DataFrame with a DatetimeIndex and standard column names
      (e.g., 'open', 'high', 'low', 'close', 'volume').
    - **Caching/Persistence:** Includes logic for checking local storage before
      fetching from external APIs, reducing API calls and improving performance.
      Integrates with a `TimeSeriesDataStore`.
    - **Resilience:** Implements rate limiting and retry mechanisms to handle
      API call constraints and transient network issues.

    TODO:
    - **Data Transformations:** Add options for common financial data transformations
      (e.g., calculating returns, resampling to different frequencies).
    - **Error Handling:** More granular error handling for API-specific error codes.
    """

    def __init__(self, api_key: str, cache_dir: Optional[Union[str, Path]] = None):
        self.api_key = api_key
        self.cache_dir = Path(cache_dir) if cache_dir else Path("data/historical_cache")
        try:
            if self.cache_dir is not None:
                self.cache_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            logger.debug(
                "Could not create historical cache directory; proceeding without cache."
            )
            self.cache_dir = None

        # Initialize FinancialDataValidator and TimeSeriesDataStore
        self.validator = FinancialDataValidator()
        self.data_store = TimeSeriesDataStore(
            storage_path=str(self.cache_dir) if self.cache_dir else "data/historical_cache"
        )
        logger.info("✅ HistoricalDataProvider initialized with validator and data store")

    def _fetch_raw_data(
        self, asset_pair: str, start_date: datetime, end_date: datetime, timeframe: str = '1h'
    ) -> pd.DataFrame:
        """
        Fetch real historical OHLC data via Alpha Vantage provider.

        Returns a DataFrame indexed by timestamp with columns: open, high, low, close, volume (if available).
        Includes simple file-based caching to reduce repeated API calls.
        """
        # Build cache key (include timeframe in cache key)
        cache_file = None
        try:
            start_str = start_date.strftime("%Y-%m-%d")
            end_str = end_date.strftime("%Y-%m-%d")
            cache_file = self.cache_dir / f"{asset_pair}_{timeframe}_{start_str}_{end_str}.parquet"
            if cache_file.exists():
                df = pd.read_parquet(cache_file)
                # Ensure datetime index
                if not isinstance(df.index, pd.DatetimeIndex):
                    df.index = pd.to_datetime(df.index, utc=True)
                df.index.name = "timestamp"
                logger.info(
                    f"Loaded historical cache for {asset_pair} (timeframe: {timeframe}) {start_str}->{end_str}"
                )
                return df
        except Exception as e:
            logger.debug(f"Historical cache load skipped: {e}")

        # Fetch via Alpha Vantage provider (async method; call in sync context)
        provider = AlphaVantageProvider(api_key=self.api_key)
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")

        candles: list = []
        try:
            import asyncio

            try:
                loop = asyncio.get_running_loop()
                # If already in an event loop, we cannot run; log and return empty
                logger.warning(
                    "Async historical fetch in running loop is unsupported in this context"
                )
                candles = []
            except RuntimeError:
                coro = provider.get_historical_data(
                    asset_pair, start=start_str, end=end_str, timeframe=timeframe
                )
                candles = asyncio.run(coro)
        except Exception as e:
            logger.error(f"Error fetching historical data: {e}")
            candles = []

        if not candles:
            logger.warning(
                f"No historical candles fetched for {asset_pair} (timeframe: {timeframe}) between {start_str} and {end_str}"
            )
            return pd.DataFrame()

        # Convert list of dicts to DataFrame; AlphaVantage returns keys: date, open, high, low, close
        df = pd.DataFrame(candles)
        if "date" not in df.columns:
            logger.warning(
                "Historical data missing 'date' column; cannot construct time index."
            )
            return pd.DataFrame()
        df["timestamp"] = pd.to_datetime(df["date"], utc=True)
        df = df.set_index("timestamp")
        # Map/ensure expected columns
        for col in ["open", "high", "low", "close"]:
            if col not in df.columns:
                df[col] = np.nan
        # Volume may be absent for FX; fill NaN if missing
        if "volume" not in df.columns:
            df["volume"] = np.nan
        df = df[["open", "high", "low", "close", "volume"]].sort_index()

        # Save cache
        try:
            if cache_file is not None:
                df.to_parquet(cache_file)
        except Exception as e:
            logger.debug(f"Could not write historical cache: {e}")

        return df

    def get_historical_data(
        self,
        asset_pair: str,
        start_date: Union[str, datetime],
        end_date: Union[str, datetime],
        timeframe: str = '1h',
    ) -> pd.DataFrame:
        """
        Retrieves historical data for a given asset pair and date range.

        Args:
            asset_pair (str): The asset pair (e.g., "BTCUSD").
            start_date (Union[str, datetime]): The start date for the data (YYYY-MM-DD or datetime object).
            end_date (Union[str, datetime]): The end date for the data (YYYY-MM-DD or datetime object).
            timeframe (str): The timeframe for candles ('1m', '5m', '15m', '30m', '1h', '1d'). Defaults to '1h'.

        Returns:
            pd.DataFrame: A DataFrame with historical data, indexed by datetime,
                          with columns like 'open', 'high', 'low', 'close', 'volume'.

        Raises:
            ValueError: If data cannot be fetched or is invalid.
        """
        if isinstance(start_date, str):
            start_date = datetime.fromisoformat(start_date)
        if isinstance(end_date, str):
            end_date = datetime.fromisoformat(end_date)

        # Ensure UTC timezone for consistency
        if start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=timezone.utc)
        if end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=timezone.utc)

        # Check data_store for cached data first
        cached_data = self.data_store.load_dataframe(asset_pair, start_date, end_date, timeframe)
        if cached_data is not None and not cached_data.empty:
            logger.info(
                f"✅ Loaded {len(cached_data)} candles for {asset_pair} ({timeframe}) from data store cache."
            )
            return cached_data

        # Fetch from API if not cached
        raw_data = self._fetch_raw_data(asset_pair, start_date, end_date, timeframe)

        if raw_data.empty:
            logger.warning(
                f"No historical data fetched for {asset_pair} (timeframe: {timeframe}) between {start_date.date()} and {end_date.date()}."
            )
            return pd.DataFrame()

        # Apply data validation
        # Note: Validator checks for price columns; OHLC data has open/high/low/close
        # We'll validate 'close' as the price column
        validation_df = raw_data.copy()
        if 'close' in validation_df.columns:
            validation_df['price'] = validation_df['close']

        validation_errors = self.validator.validate_dataframe(validation_df)
        if validation_errors:
            logger.warning(
                f"⚠️ Validation warnings in historical data for {asset_pair}: "
                f"{len(validation_errors)} column(s) with issues"
            )
            # Log first few errors for debugging
            for col, errors in list(validation_errors.items())[:3]:
                logger.debug(f"  {col}: {errors[:2]}")  # First 2 errors per column

        # Ensure correct index and column names
        if not isinstance(raw_data.index, pd.DatetimeIndex):
            raw_data.index = pd.to_datetime(raw_data.index, utc=True)
        raw_data.index.name = "timestamp"

        expected_cols = ["open", "high", "low", "close", "volume"]
        for col in expected_cols:
            if col not in raw_data.columns:
                logger.warning(
                    f"Missing expected column '{col}' in historical data for {asset_pair}. Filling with NaN."
                )
                raw_data[col] = np.nan

        # Sort by timestamp to ensure chronological order
        raw_data = raw_data.sort_index()

        # Persist fetched data to data_store
        try:
            self.data_store.save_dataframe(asset_pair, raw_data, start_date, end_date, timeframe)
        except Exception as e:
            logger.warning(f"⚠️ Failed to persist data to data store: {e}")

        logger.info(
            f"✅ Successfully fetched and processed {len(raw_data)} {timeframe} candles for {asset_pair}."
        )
        return raw_data

    def add_returns(self, df: pd.DataFrame, column: str = 'close') -> pd.DataFrame:
        """
        Add return calculations to the DataFrame.

        Args:
            df: Input DataFrame with OHLC data
            column: Column to calculate returns for (default 'close')

        Returns:
            DataFrame with added 'returns' column
        """
        df_copy = df.copy()
        df_copy['returns'] = df_copy[column].pct_change()
        return df_copy

    def resample_data(self, df: pd.DataFrame, new_frequency: str) -> pd.DataFrame:
        """
        Resample the DataFrame to a different frequency.

        Args:
            df: Input DataFrame with OHLC data and datetime index
            new_frequency: New frequency string (e.g., '1H', '4H', '1D')

        Returns:
            Resampled DataFrame
        """
        if df.empty or df.index.empty:
            return df

        # Use OHLCV aggregation rules for resampling
        agg_dict = {
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }
        # Only include columns that exist in the dataframe
        existing_cols = {k: v for k, v in agg_dict.items() if k in df.columns}

        # Preserve other numeric columns with 'last' aggregation
        for col in df.select_dtypes(include=[np.number]).columns:
            if col not in existing_cols:
                existing_cols[col] = 'last'

        resampled = df.resample(new_frequency).agg(existing_cols)
        return resampled

        resampled = df.resample(new_frequency).agg(existing_cols)
        return resampled

    def calculate_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate common technical indicators.

        Args:
            df: Input DataFrame with OHLC data

        Returns:
            DataFrame with added technical indicator columns
        """
        df_copy = df.copy()

        # Simple moving averages
        df_copy['sma_10'] = df_copy['close'].rolling(window=10).mean()
        df_copy['sma_20'] = df_copy['close'].rolling(window=20).mean()

        # Price-based indicators
        df_copy['high_low_pct'] = (df_copy['high'] - df_copy['low']) / df_copy['close']
        df_copy['price_change'] = df_copy['close'] - df_copy['open']

        return df_copy

    def get_data_with_transformations(
        self,
        asset_pair: str,
        start_date: Union[str, datetime],
        end_date: Union[str, datetime],
        timeframe: str = '1h',
        transformations: list = None
    ) -> pd.DataFrame:
        """
        Retrieves historical data with optional transformations applied.

        Args:
            asset_pair: The asset pair (e.g., "BTCUSD")
            start_date: Start date for the data
            end_date: End date for the data
            timeframe: Timeframe for candles
            transformations: List of transformation functions to apply
                           (e.g., ['returns', 'indicators', 'resample_4H'])

        Returns:
            pd.DataFrame: Historical price data with optional transformations applied
        """
        if transformations:
            # Apply resample first to avoid losing computed columns
            resample_transforms = [t for t in transformations if t.startswith('resample_')]
            other_transforms = [t for t in transformations if not t.startswith('resample_')]
            ordered_transforms = resample_transforms + other_transforms

            for transform in ordered_transforms:
                if transform == 'returns':
                    df = self.add_returns(df)
                elif transform == 'indicators':
                    df = self.calculate_technical_indicators(df)
                elif transform.startswith('resample_'):
                    # Extract frequency from transform name, e.g., 'resample_4H'
                    freq = transform.replace('resample_', '')
                    df = self.resample_data(df, freq)
                if transform == 'returns':
                    df = self.add_returns(df)
                elif transform == 'indicators':
                    df = self.calculate_technical_indicators(df)
                elif transform.startswith('resample_'):
                    # Extract frequency from transform name, e.g., 'resample_4H'
                    freq = transform.replace('resample_', '')
                    df = self.resample_data(df, freq)

        return df


# Example Usage (for demonstration within this stub)
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    dummy_api_key = "YOUR_ALPHA_VANTAGE_API_KEY"  # Replace with actual key
    provider = HistoricalDataProvider(dummy_api_key)

    asset = "BTCUSD"
    start = "2023-01-01"
    end = "2023-01-31"

    print(f"Fetching historical data for {asset} from {start} to {end}...")
    try:
        df = provider.get_historical_data(asset, start, end)
        if not df.empty:
            print(f"Data for {asset} (first 5 rows):\n{df.head()}")
            print(f"\nData for {asset} (last 5 rows):\n{df.tail()}")
            print("\nDataFrame Info:\n")
            df.info()
        else:
            print("No data received.")
    except Exception as e:
        print(f"An error occurred: {e}")
