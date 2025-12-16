"""Tests for asset classifier utility."""

import pytest

from finance_feedback_engine.utils.asset_classifier import (
    AssetClassifier,
    classify_asset_pair,
)


class TestAssetClassifier:
    """Test suite for AssetClassifier class."""

    def test_forex_classification_with_underscore(self):
        """Test forex pair classification with underscore separator."""
        classifier = AssetClassifier()
        assert classifier.classify("EUR_USD") == "forex"
        assert classifier.classify("GBP_JPY") == "forex"
        assert classifier.classify("AUD_CAD") == "forex"

    def test_forex_classification_without_separator(self):
        """Test forex pair classification without separator (6 chars)."""
        classifier = AssetClassifier()
        assert classifier.classify("EURUSD") == "forex"
        assert classifier.classify("GBPJPY") == "forex"
        assert classifier.classify("AUDCAD") == "forex"

    def test_crypto_classification(self):
        """Test cryptocurrency pair classification."""
        classifier = AssetClassifier()
        assert classifier.classify("BTCUSD") == "crypto"
        assert classifier.classify("ETHUSD") == "crypto"
        assert classifier.classify("SOLUSD") == "crypto"

    def test_crypto_classification_with_separators(self):
        """Test crypto classification with various separators."""
        classifier = AssetClassifier()
        assert classifier.classify("BTC-USD") == "crypto"
        assert classifier.classify("BTC_USD") == "crypto"
        assert classifier.classify("ETH-USD") == "crypto"

    def test_unknown_classification(self):
        """Test unknown asset pair classification."""
        classifier = AssetClassifier()
        assert classifier.classify("UNKNOWN") == "unknown"
        assert classifier.classify("ABCDEF") == "unknown"
        assert classifier.classify("XYZ") == "unknown"

    def test_empty_string(self):
        """Test handling of empty string."""
        classifier = AssetClassifier()
        assert classifier.classify("") == "unknown"
        assert classifier.classify("   ") == "unknown"

    def test_case_insensitive(self):
        """Test that classification is case-insensitive."""
        classifier = AssetClassifier()
        assert classifier.classify("eurusd") == "forex"
        assert classifier.classify("Btcusd") == "crypto"
        assert classifier.classify("gBp_JpY") == "forex"

    def test_custom_forex_currencies(self):
        """Test custom forex currency configuration."""
        custom_forex = {"AAA", "BBB", "CCC"}
        classifier = AssetClassifier(forex_currencies=custom_forex)

        assert classifier.classify("AAABBB") == "forex"
        assert classifier.classify("AAA_BBB") == "forex"
        # Standard pairs should not be forex with custom config
        assert classifier.classify("EURUSD") == "unknown"

    def test_custom_crypto_symbols(self):
        """Test custom crypto symbol configuration."""
        custom_crypto = {"XXX", "YYY"}
        classifier = AssetClassifier(crypto_symbols=custom_crypto)

        assert classifier.classify("XXXUSD") == "crypto"
        assert classifier.classify("YYY-USD") == "crypto"
        # Standard crypto should not be detected with custom config
        assert classifier.classify("BTCUSD") == "unknown"

    def test_convenience_function(self):
        """Test the convenience function classify_asset_pair."""
        assert classify_asset_pair("EURUSD") == "forex"
        assert classify_asset_pair("BTCUSD") == "crypto"
        assert classify_asset_pair("UNKNOWN") == "unknown"

    def test_extended_forex_currencies(self):
        """Test extended forex currency support (CNY, INR, etc.)."""
        classifier = AssetClassifier()
        assert classifier.classify("USDCNY") == "forex"
        assert classifier.classify("USD_CNY") == "forex"
        assert classifier.classify("USDINR") == "forex"
        assert classifier.classify("GBPSGD") == "forex"

    def test_extended_crypto_symbols(self):
        """Test extended cryptocurrency support."""
        classifier = AssetClassifier()
        assert classifier.classify("SOLUSD") == "crypto"
        assert classifier.classify("AVAXUSD") == "crypto"
        assert classifier.classify("LINKUSD") == "crypto"
        assert classifier.classify("UNIUSD") == "crypto"

    def test_crypto_takes_precedence(self):
        """Test that crypto classification takes precedence over forex."""
        classifier = AssetClassifier()
        # BTC should be classified as crypto, not forex (even though USD is a forex currency)
        assert classifier.classify("BTCUSD") == "crypto"
        assert classifier.classify("ETHGBP") == "crypto"
