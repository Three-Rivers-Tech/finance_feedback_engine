"""Trading platforms module initialization."""

from .base_platform import BaseTradingPlatform
from .coinbase_platform import CoinbaseAdvancedPlatform
from .oanda_platform import OandaPlatform
from .platform_factory import PlatformFactory

__all__ = [
    "BaseTradingPlatform",
    "CoinbaseAdvancedPlatform", 
    "OandaPlatform",
    "PlatformFactory"
]
