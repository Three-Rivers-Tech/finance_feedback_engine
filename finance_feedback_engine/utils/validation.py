"""Input validation utilities."""

import re
import logging

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
