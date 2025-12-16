"""Test suite for enhanced asset pair validation functions."""

import pytest

from finance_feedback_engine.utils.validation import (
    standardize_asset_pair,
    validate_asset_pair_composition,
    validate_asset_pair_format,
)


def test_standardize_asset_pair():
    """Test the standardize_asset_pair function."""
    # Test basic functionality
    assert standardize_asset_pair("btcusd") == "BTCUSD"
    assert standardize_asset_pair("eur_usd") == "EURUSD"
    assert standardize_asset_pair("EUR-USD") == "EURUSD"
    assert standardize_asset_pair("eth/usd") == "ETHUSD"
    assert standardize_asset_pair("BTC USD") == "BTCUSD"

    # Test edge cases
    assert standardize_asset_pair("BTC-_/USD") == "BTCUSD"
    assert standardize_asset_pair("btc-usd") == "BTCUSD"
    assert standardize_asset_pair("eth/usd") == "ETHUSD"
    assert standardize_asset_pair("gbp jpy") == "GBPJPY"

    # Test already standardized
    assert standardize_asset_pair("BTCUSD") == "BTCUSD"
    assert standardize_asset_pair("EURUSD") == "EURUSD"
    assert standardize_asset_pair("ETHUSD") == "ETHUSD"


def test_invalid_standardize_asset_pair():
    """Test invalid inputs for standardize_asset_pair function."""
    with pytest.raises(ValueError):
        standardize_asset_pair("")

    with pytest.raises(ValueError):
        standardize_asset_pair("___---")

    with pytest.raises(ValueError):
        standardize_asset_pair(None)


def test_validate_asset_pair_format():
    """Test the validate_asset_pair_format function."""
    # Valid formats
    assert validate_asset_pair_format("BTCUSD") is True
    assert validate_asset_pair_format("EURUSD") is True
    assert validate_asset_pair_format("ETHUSD") is True
    assert validate_asset_pair_format("GBPJPY") is True

    # Invalid formats
    assert validate_asset_pair_format("") is False
    assert validate_asset_pair_format("btcusd") is False  # lowercase
    assert validate_asset_pair_format("BTC-USD") is False  # has separator
    assert validate_asset_pair_format("BTC_USD") is False  # has separator
    assert validate_asset_pair_format("BTC/USD") is False  # has separator
    assert validate_asset_pair_format("BTC USD") is False  # has space
    assert validate_asset_pair_format("BTC?USD") is False  # has special char
    assert (
        validate_asset_pair_format("BTC") is False
    )  # too short (default min_length=6)
    assert (
        validate_asset_pair_format("BTCUS") is False
    )  # too short (default min_length=6)

    # Test with custom min_length
    assert validate_asset_pair_format("BTCUS", min_length=5) is True
    assert validate_asset_pair_format("BTCU", min_length=4) is True
    assert validate_asset_pair_format("BTC", min_length=4) is False


def test_validate_asset_pair_composition():
    """Test the validate_asset_pair_composition function."""
    # Valid compositions
    is_valid, msg = validate_asset_pair_composition("BTCUSD")
    assert is_valid is True
    assert "BTCUSD" in msg

    is_valid, msg = validate_asset_pair_composition("EURUSD")
    assert is_valid is True
    assert "EURUSD" in msg

    is_valid, msg = validate_asset_pair_composition("ETHUSD")
    assert is_valid is True
    assert "ETHUSD" in msg

    # Invalid compositions
    is_valid, msg = validate_asset_pair_composition("")
    assert is_valid is False
    assert "invalid format" in msg

    is_valid, msg = validate_asset_pair_composition("BTC-USD")
    assert is_valid is False
    assert "invalid format" in msg

    is_valid, msg = validate_asset_pair_composition("BTC")  # Too short (< 6 chars)
    assert is_valid is False
    assert "invalid format" in msg  # Fails format validation first due to length

    is_valid, msg = validate_asset_pair_composition("XYZABC")
    is_valid, msg = validate_asset_pair_composition("XYZABC")
    # Valid format but warns about unknown currency
    assert is_valid is True
    assert "unknown" in msg.lower() or "XYZABC" in msg


if __name__ == "__main__":
    test_standardize_asset_pair()
    test_invalid_standardize_asset_pair()
    test_validate_asset_pair_format()
    test_validate_asset_pair_composition()
    print("All tests passed!")
