import json
import os
from datetime import datetime
from typing import Dict, Any, List

class TimeSeriesDataStore:
    """
    Manages the persistence of time-series data to a file-based store.

    This class provides methods to save and load time-series data, with each
    entry timestamped and stored in a structured JSONL format. It is designed
    to be simple and extensible, allowing for future integration with more
    complex database solutions.
    """

    def __init__(self, storage_path: str = "data/time_series_data"):
        self.storage_path = storage_path
        os.makedirs(self.storage_path, exist_ok=True)

    def _get_filepath(self, symbol: str) -> str:
        """Generates a file path for a given symbol."""
        return os.path.join(self.storage_path, f"{symbol.lower()}_timeseries.jsonl")

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
