"""Asset classification utility for routing trades to appropriate platforms.

This module provides centralized logic for classifying asset pairs (forex, crypto, etc.)
to enable clean platform routing without hard-coded logic scattered across the codebase.
"""

from typing import Literal, Set
import logging

logger = logging.getLogger(__name__)

AssetClass = Literal['forex', 'crypto', 'unknown']


class AssetClassifier:
    """Classifies asset pairs into asset classes (forex, crypto, etc.)."""

    # Default asset classification rules
    DEFAULT_FOREX_CURRENCIES: Set[str] = {
        'EUR', 'GBP', 'JPY', 'AUD', 'CAD', 'CHF', 'NZD', 'USD',
        'CNY', 'INR', 'MXN', 'BRL', 'ZAR', 'SGD', 'HKD', 'NOK',
        'SEK', 'DKK', 'PLN', 'TRY', 'RUB'
    }

    DEFAULT_CRYPTO_SYMBOLS: Set[str] = {
        'BTC', 'ETH', 'SOL', 'AVAX', 'MATIC', 'ADA', 'DOT', 'LINK',
        'UNI', 'AAVE', 'CRV', 'SUSHI', 'COMP', 'MKR', 'SNX', 'YFI'
    }

    def __init__(
        self,
        forex_currencies: Set[str] = None,
        crypto_symbols: Set[str] = None
    ):
        """
        Initialize the asset classifier.

        Args:
            forex_currencies: Set of forex currency codes (default: common forex pairs)
            crypto_symbols: Set of cryptocurrency symbols (default: common crypto)
        """
        self.forex_currencies = forex_currencies or self.DEFAULT_FOREX_CURRENCIES
        self.crypto_symbols = crypto_symbols or self.DEFAULT_CRYPTO_SYMBOLS

    def classify(self, asset_pair: str) -> AssetClass:
        """
        Classify an asset pair into its asset class.

        Args:
            asset_pair: Asset pair string (e.g., "EURUSD", "EUR_USD", "BTCUSD")

        Returns:
            Asset class: 'forex', 'crypto', or 'unknown'

        Examples:
            >>> classifier = AssetClassifier()
            >>> classifier.classify("EURUSD")
            'forex'
            >>> classifier.classify("EUR_USD")
            'forex'
            >>> classifier.classify("BTCUSD")
            'crypto'
            >>> classifier.classify("BTC-USD")
            'crypto'
        """
        if not asset_pair:
            return 'unknown'

        asset_pair = asset_pair.upper().strip()

        # Check for crypto first (more specific pattern)
        if self._is_crypto(asset_pair):
            return 'crypto'

        # Check for forex
        if self._is_forex(asset_pair):
            return 'forex'

        return 'unknown'

    def _is_forex(self, asset_pair: str) -> bool:
        """
        Check if asset pair is a forex pair.

        Supports formats:
        - EUR_USD (with underscore)
        - EURUSD (6 characters, no separator)
        """
        # Format 1: EUR_USD (with underscore)
        if '_' in asset_pair:
            parts = asset_pair.split('_')
            if (len(parts) == 2 and
                parts[0] in self.forex_currencies and
                parts[1] in self.forex_currencies):
                return True

        # Format 2: EURUSD (6 characters, no separator)
        if len(asset_pair) == 6:
            base = asset_pair[:3]
            quote = asset_pair[3:]
            if base in self.forex_currencies and quote in self.forex_currencies:
                return True

        return False

    def _is_crypto(self, asset_pair: str) -> bool:
        """
        Check if asset pair is a cryptocurrency pair.

        Supports formats:
        - BTCUSD
        - BTC-USD
        - BTC_USD
        """
        # Remove common separators
        normalized = asset_pair.replace('-', '').replace('_', '')

        # Check if any crypto symbol is in the pair
        for symbol in self.crypto_symbols:
            if symbol in normalized:
                return True

        return False


# Singleton instance for convenience
_default_classifier = AssetClassifier()


def classify_asset_pair(asset_pair: str) -> AssetClass:
    """
    Convenience function to classify an asset pair using the default classifier.

    Args:
        asset_pair: Asset pair string

    Returns:
        Asset class: 'forex', 'crypto', or 'unknown'

    Examples:
        >>> classify_asset_pair("EURUSD")
        'forex'
        >>> classify_asset_pair("BTCUSD")
        'crypto'
    """
    return _default_classifier.classify(asset_pair)
