#!/usr/bin/env python3
"""Test asset pair input validation and standardization."""

from finance_feedback_engine.utils.validation import standardize_asset_pair


def test_uppercase_conversion():
    """Test lowercase to uppercase conversion."""
    assert standardize_asset_pair("btcusd") == "BTCUSD"
    assert standardize_asset_pair("eurusd") == "EURUSD"
    assert standardize_asset_pair("ethusd") == "ETHUSD"
    print("✓ Uppercase conversion tests passed")


def test_separator_removal():
    """Test removal of various separators."""
    # Underscores
    assert standardize_asset_pair("BTC_USD") == "BTCUSD"
    assert standardize_asset_pair("eur_usd") == "EURUSD"

    # Dashes
    assert standardize_asset_pair("BTC-USD") == "BTCUSD"
    assert standardize_asset_pair("EUR-USD") == "EURUSD"

    # Slashes
    assert standardize_asset_pair("BTC/USD") == "BTCUSD"
    assert standardize_asset_pair("ETH/USD") == "ETHUSD"

    # Spaces
    assert standardize_asset_pair("BTC USD") == "BTCUSD"
    assert standardize_asset_pair("EUR USD") == "EURUSD"

    # Mixed separators
    assert standardize_asset_pair("BTC-_/USD") == "BTCUSD"

    print("✓ Separator removal tests passed")


def test_combined_transformations():
    """Test combined uppercase + separator removal."""
    assert standardize_asset_pair("btc-usd") == "BTCUSD"
    assert standardize_asset_pair("eur_usd") == "EURUSD"
    assert standardize_asset_pair("eth/usd") == "ETHUSD"
    assert standardize_asset_pair("gbp jpy") == "GBPJPY"
    print("✓ Combined transformation tests passed")


def test_already_standardized():
    """Test already standardized inputs remain unchanged."""
    assert standardize_asset_pair("BTCUSD") == "BTCUSD"
    assert standardize_asset_pair("EURUSD") == "EURUSD"
    assert standardize_asset_pair("ETHUSD") == "ETHUSD"
    print("✓ Already standardized inputs tests passed")


def test_error_cases():
    """Test error handling for invalid inputs."""
    # Empty string
    try:
        standardize_asset_pair("")
        assert False, "Should raise ValueError for empty string"
    except ValueError as e:
        assert "non-empty string" in str(e)

    # Only separators
    try:
        standardize_asset_pair("___---")
        assert False, "Should raise ValueError for only separators"
    except ValueError as e:
        assert "alphanumeric characters" in str(e)

    # None
    try:
        standardize_asset_pair(None)
        assert False, "Should raise ValueError for None"
    except ValueError as e:
        assert "non-empty string" in str(e)

    print("✓ Error handling tests passed")


def test_forex_pairs():
    """Test common forex pair formats."""
    assert standardize_asset_pair("EUR_USD") == "EURUSD"
    assert standardize_asset_pair("GBP_JPY") == "GBPJPY"
    assert standardize_asset_pair("USD_CAD") == "USDCAD"
    assert standardize_asset_pair("AUD_NZD") == "AUDNZD"
    print("✓ Forex pair tests passed")


def test_crypto_pairs():
    """Test common crypto pair formats."""
    assert standardize_asset_pair("BTC_USD") == "BTCUSD"
    assert standardize_asset_pair("ETH_USD") == "ETHUSD"
    assert standardize_asset_pair("btc-usd") == "BTCUSD"
    assert standardize_asset_pair("eth/usd") == "ETHUSD"
    print("✓ Crypto pair tests passed")


def main():
    """Run all tests."""
    print("Asset Pair Standardization Tests")
    print("=" * 60)

    test_uppercase_conversion()
    test_separator_removal()
    test_combined_transformations()
    test_already_standardized()
    test_error_cases()
    test_forex_pairs()
    test_crypto_pairs()

    print("=" * 60)
    print("✅ All tests passed!")


if __name__ == "__main__":
    main()
