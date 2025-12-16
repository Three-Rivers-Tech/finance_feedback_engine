"""Trading platforms module initialization."""

from .base_platform import BaseTradingPlatform
from .coinbase_platform import CoinbaseAdvancedPlatform
from .mock_platform import MockTradingPlatform
from .oanda_platform import OandaPlatform
from .platform_factory import PlatformFactory
from .unified_platform import UnifiedTradingPlatform

__all__ = [
    "BaseTradingPlatform",
    "CoinbaseAdvancedPlatform",
    "OandaPlatform",
    "UnifiedTradingPlatform",
    "MockTradingPlatform",
    "PlatformFactory",
]
