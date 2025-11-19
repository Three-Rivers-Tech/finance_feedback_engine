"""Trading platform factory."""

from typing import Dict, Any
import logging

from .base_platform import BaseTradingPlatform
from .coinbase_platform import CoinbaseAdvancedPlatform
from .oanda_platform import OandaPlatform

logger = logging.getLogger(__name__)


class PlatformFactory:
    """
    Factory for creating trading platform instances.
    
    Supports easy extension with new platforms.
    """

    _platforms = {
        'coinbase': CoinbaseAdvancedPlatform,
        'coinbase_advanced': CoinbaseAdvancedPlatform,
        'oanda': OandaPlatform,
    }

    @classmethod
    def create_platform(
        cls, 
        platform_name: str, 
        credentials: Dict[str, Any]
    ) -> BaseTradingPlatform:
        """
        Create a trading platform instance.

        Args:
            platform_name: Name of the platform (e.g., 'coinbase', 'oanda')
            credentials: Platform-specific credentials

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
        logger.info(f"Creating platform instance: {platform_name}")
        
        return platform_class(credentials)

    @classmethod
    def register_platform(
        cls, 
        platform_name: str, 
        platform_class: type
    ) -> None:
        """
        Register a new trading platform.

        Args:
            platform_name: Name to register the platform under
            platform_class: Platform class (must inherit from BaseTradingPlatform)

        Raises:
            ValueError: If platform_class doesn't inherit from BaseTradingPlatform
        """
        if not issubclass(platform_class, BaseTradingPlatform):
            raise ValueError(
                f"{platform_class} must inherit from BaseTradingPlatform"
            )
        
        cls._platforms[platform_name.lower()] = platform_class
        logger.info(f"Registered new platform: {platform_name}")

    @classmethod
    def list_platforms(cls) -> list:
        """
        Get list of supported platforms.

        Returns:
            List of platform names
        """
        return list(cls._platforms.keys())
