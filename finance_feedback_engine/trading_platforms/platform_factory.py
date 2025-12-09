"""Trading platform factory."""

from typing import Dict, Any
import logging

from .base_platform import BaseTradingPlatform
from .coinbase_platform import CoinbaseAdvancedPlatform
from .oanda_platform import OandaPlatform
from .unified_platform import UnifiedTradingPlatform
from .mock_platform import MockTradingPlatform

logger = logging.getLogger(__name__)


class PlatformFactory:
    """
    Factory for creating trading platform instances.

    Supports easy extension with new platforms.
    """

    # A lightweight explicit mock platform for testing and interactive
    # sessions where external SDKs are not available. Consumers must opt
    # into the mock platform by setting `trading_platform: mock` in the
    # configuration.
    class MockPlatform(BaseTradingPlatform):
        def __init__(self, credentials: Dict[str, Any]):
            super().__init__(credentials)

        def get_balance(self) -> Dict[str, float]:
            return {
                "FUTURES_USD": 20000.0,
                "SPOT_USD": 3000.0,
                "SPOT_USDC": 2000.0
            }

        def execute_trade(self, decision: Dict[str, Any]) -> Dict[str, Any]:
            return {"success": True, "message": "simulated trade (mock)"}

        def get_account_info(self) -> Dict[str, Any]:
            return {"platform": "mock", "mock": True}

        def get_portfolio_breakdown(self) -> Dict[str, Any]:
            """Return mock portfolio data for testing dashboard."""
            futures_value = 20000.00
            spot_value = 5000.00  # USD + USDC
            total_value = futures_value + spot_value

            return {
                'total_value_usd': total_value,
                'futures_value_usd': futures_value,
                'spot_value_usd': spot_value,
                'num_assets': 2,
                'unrealized_pnl': 500.00,
                'holdings': [
                    {
                        'asset': 'USD',
                        'amount': 3000.00,
                        'value_usd': 3000.00,
                        'allocation_pct': (3000.00 / total_value) * 100
                    },
                    {
                        'asset': 'USDC',
                        'amount': 2000.00,
                        'value_usd': 2000.00,
                        'allocation_pct': (2000.00 / total_value) * 100
                    }
                ],
                'futures_summary': {
                    'total_balance_usd': futures_value,
                    'unrealized_pnl': 500.00,
                    'daily_realized_pnl': 150.00,
                    'buying_power': 40000.00,
                    'initial_margin': 5000.00
                },
                'futures_positions': []
            }

    _platforms = {
        'coinbase': CoinbaseAdvancedPlatform,
        'coinbase_advanced': CoinbaseAdvancedPlatform,
        'oanda': OandaPlatform,
        'unified': UnifiedTradingPlatform,
        'mock': MockTradingPlatform,  # Comprehensive mock with state tracking
        'mock_simple': MockPlatform,  # Lightweight inline mock (legacy)
    }

    @classmethod
    def create_platform(
        cls, platform_name: str, credentials: Dict[str, Any]
    ) -> BaseTradingPlatform:
        """
        Create a trading platform instance.

        Args:
            platform_name: Name of the platform (e.g., 'coinbase', 'oanda')
            credentials: Platform-specific credentials OR full config dict
                        for unified platform

        Returns:
            Trading platform instance

        Raises:
            ValueError: If platform is not supported
        """
        platform_name = platform_name.lower()

        if platform_name not in cls._platforms:
            available = ', '.join(cls._platforms.keys())
            raise ValueError(
                f"Platform '{platform_name}' not supported. "
                f"Available platforms: {available}"
            )

        platform_class = cls._platforms[platform_name]
        logger.info("Creating platform instance: %s", platform_name)

        # Instantiate the platform class directly. If an external SDK is
        # missing and this raises, propagate the error so callers are
        # explicitly aware and can choose the explicit 'mock' platform.
        instance = platform_class(credentials)

        # Attach a persistent circuit breaker on the instance if possible
        try:
            from ..utils.circuit_breaker import CircuitBreaker

            # Only attach if not already present
            if not getattr(instance, 'get_execute_breaker', None) or instance.get_execute_breaker() is None:
                breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=60, name=f"execute_trade:{platform_name}")
                # Use set_execute_breaker accessor if available
                if getattr(instance, 'set_execute_breaker', None):
                    instance.set_execute_breaker(breaker)
                else:
                    # Fallback to setting attribute directly
                    setattr(instance, '_execute_breaker', breaker)
        except Exception:
            # If circuit breaker module not available, continue without it
            logger.debug("CircuitBreaker not attached (unavailable)")

        return instance

    @classmethod
    def register_platform(
        cls, platform_name: str, platform_class: type
    ) -> None:
        """
        Register a new trading platform.

        Args:
            platform_name: Name to register the platform under
            platform_class: Platform class (must inherit from
                            BaseTradingPlatform)

        Raises:
            ValueError: If platform_class doesn't inherit from
                        BaseTradingPlatform
        """
        if not issubclass(platform_class, BaseTradingPlatform):
            raise ValueError(
                f"{platform_class} must inherit from BaseTradingPlatform"
            )

        cls._platforms[platform_name.lower()] = platform_class
        logger.info("Registered new platform: %s", platform_name)

    @classmethod
    def list_platforms(cls) -> list:
        """
        Get list of supported platforms.

        Returns:
            List of platform names
        """
        return list(cls._platforms.keys())
