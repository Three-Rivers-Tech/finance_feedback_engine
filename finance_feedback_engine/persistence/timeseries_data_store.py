import json
import os
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class TimeSeriesDataStore:
    """
    Manages the persistence of time-series data to a file-based store.

    This class provides methods to save and load time-series data, with each
    entry timestamped and stored in a structured format. Supports both JSONL
    for individual entries and Parquet for DataFrame storage.
    """

    def __init__(self, storage_path: str = "data/time_series_data"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

    def _get_filepath(self, symbol: str) -> str:
        """Generates a file path for a given symbol (JSONL format)."""
        return os.path.join(self.storage_path, f"{symbol.lower()}_timeseries.jsonl")

    def _get_dataframe_filepath(
        self, asset_pair: str, start_date: datetime, end_date: datetime, timeframe: str
    ) -> Path:
        """
        Generate file path for DataFrame storage (Parquet format).

        Args:
            asset_pair: Asset pair symbol
            start_date: Start date for the data
            end_date: End date for the data
            timeframe: Timeframe (e.g., '1h', '1d')

        Returns:
            Path to parquet file
        """
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")
        filename = f"{asset_pair.lower()}_{timeframe}_{start_str}_{end_str}.parquet"
        return self.storage_path / filename

    def save_data(self, symbol: str, data_entry: Dict[str, Any]):
        """
        Appends a single time-series data entry to the store for a given symbol.

        This method uses JSONL (JSON Lines) format for append-only writes, which
        eliminates race conditions that could occur with read-modify-write patterns
        when multiple processes write concurrently.

        Args:
            symbol (str): The trading symbol (e.g., "BTCUSD", "IBM").
            data_entry (Dict[str, Any]): A dictionary containing the time-series
                                         data point, expected to have a 'timestamp' key.
        """
        filepath = self._get_filepath(symbol)
        
        # Ensure timestamp is string for JSON serialization
        if isinstance(data_entry.get('timestamp'), datetime):
            data_entry['timestamp'] = data_entry['timestamp'].isoformat()
        
        # Append new entry as a single JSON line (JSONL format)
        with open(filepath, 'a', encoding='utf-8') as f:
            json.dump(data_entry, f)
            f.write('\n')

    def load_data(self, symbol: str) -> List[Dict[str, Any]]:
        """
        Loads all time-series data for a given symbol.

        Args:
            symbol (str): The trading symbol.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries, each representing a
                                  time-series data point. Returns an empty list
                                  if no data is found.
        """
        filepath = self._get_filepath(symbol)
        if not os.path.exists(filepath):
            return []

        data = []
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:  # Skip empty lines
                    try:
                        data.append(json.loads(line))
                    except json.JSONDecodeError:
                        # Skip malformed lines but continue processing
                        continue
        return data

    def save_dataframe(
        self,
        asset_pair: str,
        df: pd.DataFrame,
        start_date: datetime,
        end_date: datetime,
        timeframe: str
    ) -> None:
        """
        Save a DataFrame of historical OHLCV data to Parquet format.

        Args:
            asset_pair: Asset pair symbol
            df: DataFrame with OHLCV data
            start_date: Start date of the data
            end_date: End date of the data
            timeframe: Timeframe (e.g., '1h', '1d')
        """
        if df.empty:
            logger.warning(f"Not saving empty DataFrame for {asset_pair}")
            return

        try:
            filepath = self._get_dataframe_filepath(asset_pair, start_date, end_date, timeframe)
            df.to_parquet(filepath)
            logger.info(
                f"✅ Saved {len(df)} candles for {asset_pair} ({timeframe}) to {filepath.name}"
            )
        except Exception as e:
            logger.error(f"❌ Failed to save DataFrame for {asset_pair}: {e}")
            raise

    def load_dataframe(
        self,
        asset_pair: str,
        start_date: datetime,
        end_date: datetime,
        timeframe: str
    ) -> Optional[pd.DataFrame]:
        """
        Load a DataFrame of historical OHLCV data from Parquet format.

        Args:
            asset_pair: Asset pair symbol
            start_date: Start date of the data
            end_date: End date of the data
            timeframe: Timeframe (e.g., '1h', '1d')

        Returns:
            DataFrame if found, None otherwise
        """
        try:
            filepath = self._get_dataframe_filepath(asset_pair, start_date, end_date, timeframe)

            if not filepath.exists():
                return None

            df = pd.read_parquet(filepath)

            # Ensure datetime index
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index, utc=True)
            df.index.name = "timestamp"

            logger.info(
                f"✅ Loaded {len(df)} candles for {asset_pair} ({timeframe}) from cache"
            )
            return df

        except Exception as e:
            logger.warning(f"⚠️ Failed to load DataFrame for {asset_pair}: {e}")
            return None
