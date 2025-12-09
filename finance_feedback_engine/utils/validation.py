"""Input validation utilities."""

import re
import logging
from datetime import datetime, timezone
from typing import Tuple

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
    standardized = re.sub(r'[^A-Za-z0-9]', '', asset_pair).upper()

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
            standardized
        )

    logger.debug(
        "Standardized asset pair: '%s' -> '%s'",
        asset_pair,
        standardized
    )

    return standardized


def validate_data_freshness(
    data_timestamp: str,
    asset_type: str = "crypto",
    timeframe: str = "intraday"
) -> Tuple[bool, str, str]:
    """Validate that data is fresh enough for trading decisions.

    Protects against stale data from API lag or connectivity issues.
    Supports different freshness thresholds by asset type and timeframe.

    Args:
        data_timestamp: ISO 8601 formatted timestamp (e.g., '2024-12-08T14:30:00Z'
            or '2024-12-08T14:30:00+00:00'). Must be UTC or have explicit Z suffix.
        asset_type: One of "crypto", "forex", "stocks" (case-insensitive).
        timeframe: For stocks only: "daily" or "intraday" (default). Ignored for crypto/forex.

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

    # Determine thresholds and warnings by asset type
    asset_kind = (asset_type or "crypto").lower()
    warning_msg = ""
    is_fresh = True

    if asset_kind in ("crypto", "forex"):
        # Crypto and Forex: 5 min warning, 15 min critical
        if age_minutes > 15:
            is_fresh = False
            warning_msg = (
                f"CRITICAL: {asset_kind.capitalize()} data is {age_str} old "
                f"(threshold: 15 minutes). Stale market data detected. "
                f"Recommend skipping trade."
            )
            logger.error(warning_msg)
        elif age_minutes > 5:
            is_fresh = True  # Still usable but warn
            warning_msg = (
                f"WARNING: {asset_kind.capitalize()} data is {age_str} old "
                f"(warning threshold: 5 minutes). Consider refreshing."
            )
            logger.warning(warning_msg)
    elif asset_kind == "stocks":
        # Stocks: Different threshold for daily vs intraday
        timeframe_kind = (timeframe or "intraday").lower()
        if timeframe_kind == "daily":
            # Daily data: 24 hour warning threshold
            if age_minutes > 24 * 60:  # 24 hours
                is_fresh = True  # Still usable (daily data ages slower)
                warning_msg = (
                    f"WARNING: Stock daily data is {age_str} old "
                    f"(warning threshold: 24 hours). Consider refreshing."
                )
                logger.warning(warning_msg)
        else:  # intraday (default)
            # Intraday: 15 minute warning
            if age_minutes > 15:
                is_fresh = False
                warning_msg = (
                    f"CRITICAL: Stock intraday data is {age_str} old "
                    f"(threshold: 15 minutes). Stale market data detected. "
                    f"Recommend skipping trade."
                )
                logger.error(warning_msg)
            elif age_minutes > 5:
                is_fresh = True  # Still usable but warn
                warning_msg = (
                    f"WARNING: Stock intraday data is {age_str} old "
                    f"(warning threshold: 5 minutes). Consider refreshing."
                )
                logger.warning(warning_msg)
    else:
        # Unknown asset type: default to crypto thresholds
        if age_minutes > 15:
            is_fresh = False
            warning_msg = (
                f"CRITICAL: Data is {age_str} old (threshold: 15 minutes). "
                f"Stale market data detected. Recommend skipping trade."
            )
            logger.error(warning_msg)
        elif age_minutes > 5:
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
        is_fresh
    )

    return is_fresh, age_str, warning_msg
