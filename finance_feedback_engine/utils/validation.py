"""Input validation utilities."""

import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

# Configurable staleness thresholds (in minutes) via environment variables.
# Free-tier data providers (e.g., Alpha Vantage) often have 15-60 min delays,
# so the defaults are relaxed to avoid false CRITICAL alerts.
CRYPTO_INTRADAY_STALE_MINUTES = float(
    os.getenv("FFE_CRYPTO_INTRADAY_STALE_MINUTES", "90")
)
CRYPTO_INTRADAY_WARN_MINUTES = float(
    os.getenv("FFE_CRYPTO_INTRADAY_WARN_MINUTES", "30")
)
FOREX_INTRADAY_STALE_MINUTES = float(
    os.getenv("FFE_FOREX_INTRADAY_STALE_MINUTES", "90")
)
FOREX_INTRADAY_WARN_MINUTES = float(
    os.getenv("FFE_FOREX_INTRADAY_WARN_MINUTES", "30")
)

logger = logging.getLogger(__name__)


def standardize_asset_pair(asset_pair: str) -> str:
    """
    Standardize asset pair input for Alpha Vantage API compatibility.

    Converts user input to the format expected by Alpha Vantage:
    - Uppercase letters only
    - No separators (removes underscores, dashes, slashes, spaces)
    - Preserves alphanumeric characters

    Examples:
        'btcusd' -> 'BTCUSD'
        'eur_usd' -> 'EURUSD'
        'EUR-USD' -> 'EURUSD'
        'eth/usd' -> 'ETHUSD'
        'BTC USD' -> 'BTCUSD'

    Args:
        asset_pair: User input asset pair (any case, with/without separators)

    Returns:
        Standardized uppercase asset pair without separators

    Raises:
        ValueError: If input is empty or contains only invalid characters
    """
    if not asset_pair or not isinstance(asset_pair, str):
        raise ValueError("Asset pair must be a non-empty string")

    # Remove all non-alphanumeric characters and convert to uppercase
    standardized = re.sub(r"[^A-Za-z0-9]", "", asset_pair).upper()

    if not standardized:
        raise ValueError(
            f"Invalid asset pair '{asset_pair}': "
            "must contain alphanumeric characters"
        )

    # Validate minimum length (at least 6 chars for typical pairs like BTCUSD)
    if len(standardized) < 6:
        logger.warning(
            "Asset pair '%s' is unusually short (standardized: '%s')",
            asset_pair,
            standardized,
        )

    logger.debug("Standardized asset pair: '%s' -> '%s'", asset_pair, standardized)

    return standardized


def validate_asset_pair_format(asset_pair: str, min_length: int = 6) -> bool:
    """
    Validates the format of an asset pair string.

    Args:
        asset_pair: The asset pair to validate (should be standardized: 'BTCUSD')
        min_length: Minimum required length (default: 6 for typical pairs)

    Returns:
        bool: True if valid, False otherwise
    """
    if not asset_pair or not isinstance(asset_pair, str):
        return False

    # Should be uppercase with only alphanumeric characters
    if not re.match(r"^[A-Z0-9]+$", asset_pair):
        return False

    # Check minimum length
    if len(asset_pair) < min_length:
        return False

    return True


def validate_asset_pair_composition(asset_pair: str) -> Tuple[bool, str]:
    """
    Validates that an asset pair has a valid composition (base/quote).

    Args:
        asset_pair: The asset pair to validate (should be standardized: 'BTCUSD')

    Returns:
        Tuple of (is_valid, message)
    """
    if not validate_asset_pair_format(asset_pair):
        return False, f"Asset pair '{asset_pair}' has invalid format"

    # Should have a reasonable base/quote split (at least 2-3 chars each)
    if len(asset_pair) < 4:  # Too short for any meaningful base/quote
        return False, f"Asset pair '{asset_pair}' is too short to be valid"

    # Check for common base currency prefixes
    known_base_currencies = {
        "BTC",
        "ETH",
        "XRP",
        "LTC",
        "BCH",
        "ADA",
        "DOT",
        "LINK",
        "SOL",
        "DOGE",
        "AVAX",
        "MATIC",
        "UNI",
        "SAND",
        "MANA",
        "AAVE",
        "SUSHI",
        "EUR",
        "GBP",
        "JPY",
        "CHF",
        "CAD",
        "AUD",
        "NZD",
        "SGD",
        "HKD",
        "USD",
        "USDT",
        "USDC",
        "DAI",
    }

    # Check the first few characters for known base currencies
    base_length = min(4, len(asset_pair))  # Check up to first 4 chars
    base_part = asset_pair[:base_length]

    found_base = False
    for currency in known_base_currencies:
        if base_part.startswith(currency):
            found_base = True
            # Extract the potential quote currency part
            quote_part = asset_pair[len(currency) :]
            # Ensure quote part is not empty and contains valid currency characters
            if quote_part and all(c.isalpha() for c in quote_part):
                # Validate that quote part is a recognized currency
                if (
                    quote_part in known_base_currencies
                ):  # Using same list for quote currencies
                    return (
                        True,
                        f"Asset pair '{asset_pair}' has valid base/quote composition",
                    )
                else:
                    logger.warning(
                        "Asset pair '%s' has unknown quote currency: %s",
                        asset_pair,
                        quote_part,
                    )
                    # For now, treat unknown quote currencies as valid but with warning
                    return (
                        True,
                        f"Asset pair '{asset_pair}' has unknown quote currency: {quote_part}",
                    )
            else:
                logger.warning(
                    "Asset pair '%s' has invalid quote currency format: %s",
                    asset_pair,
                    quote_part,
                )
                return (
                    False,
                    f"Asset pair '{asset_pair}' has invalid quote currency: {quote_part}",
                )

    if not found_base:
        logger.warning(
            "Asset pair '%s' starts with an unknown base currency: %s",
            asset_pair,
            base_part,
        )
        # For now, treat unknown base currencies as valid but with warning
        return True, f"Asset pair '{asset_pair}' has unknown base currency"

    return True, f"Asset pair '{asset_pair}' has valid base/quote composition"


def validate_data_freshness(
    data_timestamp: str,
    asset_type: str = "crypto",
    timeframe: str = "intraday",
    market_status: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, str, str]:
    """Validate that data is fresh enough for trading decisions.

    Protects against stale data from API lag or connectivity issues.
    Supports different freshness thresholds by asset type, timeframe, and market status.

    Args:
        data_timestamp: ISO 8601 formatted timestamp (e.g., '2024-12-08T14:30:00Z'
            or '2024-12-08T14:30:00+00:00'). Must be UTC or have explicit Z suffix.
        asset_type: One of "crypto", "forex", "stocks" (case-insensitive).
        timeframe: Timeframe of data: "1h", "4h", "daily", "intraday" (default).
        market_status: Optional market status dict from MarketSchedule.get_market_status()

    Returns:
        Tuple of (is_fresh, age_str, warning_message) where:
            - is_fresh (bool): True if data is within acceptable freshness threshold
            - age_str (str): Human-readable age (e.g., "2.5 minutes", "45 seconds")
            - warning_message (str): Descriptive message; empty string if fresh

    Raises:
        ValueError: If timestamp cannot be parsed as ISO 8601 UTC datetime
    """
    if not data_timestamp or not isinstance(data_timestamp, str):
        raise ValueError("data_timestamp must be a non-empty ISO 8601 string")

    # Parse ISO 8601 timestamp with UTC support
    try:
        # Handle 'Z' suffix (indicates UTC)
        clean_timestamp = data_timestamp.replace("Z", "+00:00")

        # Parse timestamp
        dt_obj = datetime.fromisoformat(clean_timestamp)

        # Ensure timezone is set (assume UTC if naive)
        if dt_obj.tzinfo is None:
            dt_obj = dt_obj.replace(tzinfo=timezone.utc)
        elif dt_obj.tzinfo != timezone.utc:
            # Convert to UTC if in different timezone
            dt_obj = dt_obj.astimezone(timezone.utc)
    except (ValueError, TypeError) as e:
        raise ValueError(
            f"Invalid data_timestamp '{data_timestamp}': "
            f"must be ISO 8601 UTC format (e.g., '2024-12-08T14:30:00Z'). Error: {e}"
        )

    # Calculate age in minutes
    now_utc = datetime.now(timezone.utc)
    age_delta = now_utc - dt_obj
    age_minutes = age_delta.total_seconds() / 60

    # Format age as human-readable string
    if age_minutes < 1:
        seconds = age_delta.total_seconds()
        age_str = f"{seconds:.1f} seconds"
    elif age_minutes < 60:
        age_str = f"{age_minutes:.1f} minutes"
    else:
        hours = age_minutes / 60
        age_str = f"{hours:.2f} hours"

    # Determine thresholds and warnings by asset type, timeframe, and market status
    asset_kind = (asset_type or "crypto").lower()
    timeframe_kind = (timeframe or "intraday").lower()
    warning_msg = ""
    is_fresh = True
    epsilon = 1e-6  # tolerate tiny timing drift when calculating age

    # Market-aware threshold adjustment
    is_market_open = True
    is_weekend = False
    if market_status:
        is_market_open = market_status.get("is_open", True)
        is_weekend = market_status.get("session") == "Weekend"

    if asset_kind == "crypto":
        # Crypto: 24/7 markets with 15-minute threshold for intraday, 24h for daily
        if timeframe_kind == "daily":
            # Daily crypto data: 24-hour threshold (daily candles update once per day)
            if age_minutes > 24 * 60:  # 24 hours
                is_fresh = False
                warning_msg = (
                    f"CRITICAL: Crypto daily data is {age_str} old "
                    f"(threshold: 24 hours). Data too stale for trading."
                )
                logger.error(warning_msg)
            elif age_minutes > 2 * 60:  # 2 hours warning
                is_fresh = True
                warning_msg = (
                    f"WARNING: Crypto daily data is {age_str} old "
                    f"(warning: 2 hours). Consider refreshing."
                )
                logger.warning(warning_msg)
        else:
            # Intraday crypto: configurable threshold (default 90min for free-tier providers)
            if (age_minutes - CRYPTO_INTRADAY_STALE_MINUTES) > epsilon:
                is_fresh = False
                warning_msg = (
                    f"CRITICAL: Crypto {timeframe_kind} data is {age_str} old "
                    f"(threshold: {CRYPTO_INTRADAY_STALE_MINUTES:.0f} minutes). Stale market data detected."
                )
                logger.error(warning_msg)
            elif age_minutes >= CRYPTO_INTRADAY_WARN_MINUTES:
                is_fresh = True
                warning_msg = (
                    f"WARNING: Crypto {timeframe_kind} data is {age_str} old "
                    f"(warning: {CRYPTO_INTRADAY_WARN_MINUTES:.0f} minutes). Consider refreshing."
                )
                logger.warning(warning_msg)

    elif asset_kind == "forex":
        # Forex: Market-aware thresholds
        if timeframe_kind == "daily":
            # Daily forex: 24-hour threshold during market hours, 48h on weekends
            threshold_hours = 48 if is_weekend else 24
            if age_minutes > threshold_hours * 60:
                is_fresh = False
                warning_msg = (
                    f"CRITICAL: Forex daily data is {age_str} old "
                    f"(threshold: {threshold_hours} hours, weekend={is_weekend}). Data too stale."
                )
                logger.error(warning_msg)
            elif age_minutes > 4 * 60:  # 4 hours warning
                is_fresh = True
                warning_msg = (
                    f"WARNING: Forex daily data is {age_str} old "
                    f"(warning: 4 hours). Consider refreshing."
                )
                logger.warning(warning_msg)
        else:
            # Intraday forex: 15 min during market hours, 24h on weekends
            if is_weekend or not is_market_open:
                # Weekend/closed: Allow 24-hour old data
                if age_minutes > 24 * 60:
                    is_fresh = False
                    warning_msg = (
                        f"CRITICAL: Forex {timeframe_kind} data is {age_str} old "
                        f"(weekend threshold: 24 hours). Data too stale."
                    )
                    logger.error(warning_msg)
                elif age_minutes > 2 * 60:  # 2 hours warning
                    is_fresh = True
                    warning_msg = (
                        f"WARNING: Forex {timeframe_kind} weekend data is {age_str} old. "
                        f"Weekend data expected to be older."
                    )
                    logger.warning(warning_msg)
            else:
                # Market hours: configurable threshold (default 90min for free-tier providers)
                if (age_minutes - FOREX_INTRADAY_STALE_MINUTES) > epsilon:
                    is_fresh = False
                    warning_msg = (
                        f"CRITICAL: Forex {timeframe_kind} data is {age_str} old "
                        f"(threshold: {FOREX_INTRADAY_STALE_MINUTES:.0f} minutes). Stale market data detected."
                    )
                    logger.error(warning_msg)
                elif age_minutes >= FOREX_INTRADAY_WARN_MINUTES:
                    is_fresh = True
                    warning_msg = (
                        f"WARNING: Forex {timeframe_kind} data is {age_str} old "
                        f"(warning: {FOREX_INTRADAY_WARN_MINUTES:.0f} minutes). Consider refreshing."
                    )
                    logger.warning(warning_msg)
    elif asset_kind == "stocks":
        # Stocks: Market-aware thresholds
        if timeframe_kind == "daily":
            # Daily stock data: 24-hour threshold during market hours, 48h outside
            threshold_hours = 24 if is_market_open else 48
            if age_minutes > threshold_hours * 60:
                is_fresh = False
                warning_msg = (
                    f"CRITICAL: Stock daily data is {age_str} old "
                    f"(threshold: {threshold_hours} hours, market_open={is_market_open}). "
                    f"Data too stale."
                )
                logger.error(warning_msg)
            elif age_minutes > 4 * 60:  # 4 hours warning
                is_fresh = True
                warning_msg = (
                    f"WARNING: Stock daily data is {age_str} old "
                    f"(warning: 4 hours). Consider refreshing."
                )
                logger.warning(warning_msg)
        else:  # intraday
            if not is_market_open:
                # Outside market hours: Allow 24-hour old data
                if age_minutes > 24 * 60:
                    is_fresh = False
                    warning_msg = (
                        f"CRITICAL: Stock {timeframe_kind} data is {age_str} old "
                        f"(off-hours threshold: 24 hours). Data too stale."
                    )
                    logger.error(warning_msg)
                elif age_minutes > 2 * 60:
                    is_fresh = True
                    warning_msg = (
                        f"WARNING: Stock {timeframe_kind} data is {age_str} old "
                        f"(market closed). Data expected to be older."
                    )
                    logger.warning(warning_msg)
            else:
                # Market hours: 1-hour threshold (more lenient than forex/crypto)
                if age_minutes > 60:
                    is_fresh = False
                    warning_msg = (
                        f"CRITICAL: Stock {timeframe_kind} data is {age_str} old "
                        f"(threshold: 1 hour). Stale market data detected."
                    )
                    logger.error(warning_msg)
                elif age_minutes >= 15:
                    is_fresh = True
                    warning_msg = (
                        f"WARNING: Stock {timeframe_kind} data is {age_str} old "
                        f"(warning: 15 minutes). Consider refreshing."
                    )
                    logger.warning(warning_msg)
    else:
        # Unknown asset type: default to crypto thresholds
        if (age_minutes - CRYPTO_INTRADAY_STALE_MINUTES) > epsilon:
            is_fresh = False
            warning_msg = (
                f"CRITICAL: Data is {age_str} old (threshold: {CRYPTO_INTRADAY_STALE_MINUTES:.0f} minutes). "
                f"Stale market data detected. Recommend skipping trade."
            )
            logger.error(warning_msg)
        elif age_minutes >= CRYPTO_INTRADAY_WARN_MINUTES:
            is_fresh = True
            warning_msg = (
                f"WARNING: Data is {age_str} old "
                f"(warning threshold: 5 minutes). Consider refreshing."
            )
            logger.warning(warning_msg)

    logger.debug(
        "Data freshness check: asset_type=%s, age=%s, is_fresh=%s",
        asset_kind,
        age_str,
        is_fresh,
    )

    return is_fresh, age_str, warning_msg
