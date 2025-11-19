"""Alpha Vantage data provider module."""

from typing import Dict, Any, Optional
import logging
import requests
from datetime import datetime

logger = logging.getLogger(__name__)


class AlphaVantageProvider:
    """
    Data provider for Alpha Vantage Premium API.
    
    Supports various asset types including cryptocurrencies and forex.
    """

    BASE_URL = "https://www.alphavantage.co/query"

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Alpha Vantage provider.

        Args:
            api_key: Alpha Vantage API key (premium recommended)
        """
        if not api_key:
            raise ValueError("Alpha Vantage API key is required")
        self.api_key = api_key
        logger.info("Alpha Vantage provider initialized")

    def get_market_data(self, asset_pair: str) -> Dict[str, Any]:
        """
        Fetch market data for a given asset pair.

        Args:
            asset_pair: Asset pair (e.g., 'BTCUSD', 'EURUSD')

        Returns:
            Dictionary containing market data
        """
        logger.info(f"Fetching market data for {asset_pair}")
        
        # Determine asset type and fetch appropriate data
        if 'BTC' in asset_pair or 'ETH' in asset_pair:
            return self._get_crypto_data(asset_pair)
        else:
            return self._get_forex_data(asset_pair)

    def _get_crypto_data(self, asset_pair: str) -> Dict[str, Any]:
        """
        Fetch cryptocurrency data.

        Args:
            asset_pair: Crypto pair (e.g., 'BTCUSD')

        Returns:
            Dictionary containing crypto market data
        """
        # Extract base and quote currencies
        if asset_pair.endswith('USD'):
            symbol = asset_pair[:-3]
            market = 'USD'
        else:
            symbol = asset_pair[:3]
            market = asset_pair[3:]

        params = {
            'function': 'DIGITAL_CURRENCY_DAILY',
            'symbol': symbol,
            'market': market,
            'apikey': self.api_key
        }

        try:
            response = requests.get(self.BASE_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if 'Time Series (Digital Currency Daily)' in data:
                time_series = data['Time Series (Digital Currency Daily)']
                latest_date = list(time_series.keys())[0]
                latest_data = time_series[latest_date]

                return {
                    'asset_pair': asset_pair,
                    'timestamp': datetime.utcnow().isoformat(),
                    'date': latest_date,
                    'open': float(latest_data.get('1a. open (USD)', 0)),
                    'high': float(latest_data.get('2a. high (USD)', 0)),
                    'low': float(latest_data.get('3a. low (USD)', 0)),
                    'close': float(latest_data.get('4a. close (USD)', 0)),
                    'volume': float(latest_data.get('5. volume', 0)),
                    'market_cap': float(latest_data.get('6. market cap (USD)', 0)),
                    'type': 'crypto'
                }
            else:
                logger.warning(f"Unexpected response format: {data}")
                return self._create_mock_data(asset_pair, 'crypto')

        except Exception as e:
            logger.error(f"Error fetching crypto data: {e}")
            return self._create_mock_data(asset_pair, 'crypto')

    def _get_forex_data(self, asset_pair: str) -> Dict[str, Any]:
        """
        Fetch forex data.

        Args:
            asset_pair: Forex pair (e.g., 'EURUSD')

        Returns:
            Dictionary containing forex market data
        """
        from_currency = asset_pair[:3]
        to_currency = asset_pair[3:]

        params = {
            'function': 'FX_DAILY',
            'from_symbol': from_currency,
            'to_symbol': to_currency,
            'apikey': self.api_key
        }

        try:
            response = requests.get(self.BASE_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if 'Time Series FX (Daily)' in data:
                time_series = data['Time Series FX (Daily)']
                latest_date = list(time_series.keys())[0]
                latest_data = time_series[latest_date]

                return {
                    'asset_pair': asset_pair,
                    'timestamp': datetime.utcnow().isoformat(),
                    'date': latest_date,
                    'open': float(latest_data.get('1. open', 0)),
                    'high': float(latest_data.get('2. high', 0)),
                    'low': float(latest_data.get('3. low', 0)),
                    'close': float(latest_data.get('4. close', 0)),
                    'type': 'forex'
                }
            else:
                logger.warning(f"Unexpected response format: {data}")
                return self._create_mock_data(asset_pair, 'forex')

        except Exception as e:
            logger.error(f"Error fetching forex data: {e}")
            return self._create_mock_data(asset_pair, 'forex')

    def _create_mock_data(self, asset_pair: str, asset_type: str) -> Dict[str, Any]:
        """
        Create mock data for testing/demo purposes.

        Args:
            asset_pair: Asset pair
            asset_type: Type of asset (crypto/forex)

        Returns:
            Mock market data
        """
        logger.info(f"Creating mock data for {asset_pair}")
        
        base_price = 50000.0 if asset_type == 'crypto' else 1.1
        
        return {
            'asset_pair': asset_pair,
            'timestamp': datetime.utcnow().isoformat(),
            'date': datetime.utcnow().date().isoformat(),
            'open': base_price,
            'high': base_price * 1.02,
            'low': base_price * 0.98,
            'close': base_price * 1.01,
            'volume': 1000000.0 if asset_type == 'crypto' else 0,
            'type': asset_type,
            'mock': True
        }
