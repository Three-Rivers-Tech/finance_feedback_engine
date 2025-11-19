"""Base trading platform interface."""

from abc import ABC, abstractmethod
from typing import Dict, Any


class BaseTradingPlatform(ABC):
    """
    Abstract base class for trading platform integrations.
    
    All platform implementations must inherit from this class.
    """

    def __init__(self, credentials: Dict[str, Any]):
        """
        Initialize the trading platform.

        Args:
            credentials: Platform-specific credentials
        """
        self.credentials = credentials

    @abstractmethod
    def get_balance(self) -> Dict[str, float]:
        """
        Get account balances.

        Returns:
            Dictionary mapping asset symbols to balances
        """
        pass

    @abstractmethod
    def execute_trade(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a trade based on a decision.

        Args:
            decision: Trading decision containing action, asset, amount, etc.

        Returns:
            Execution result
        """
        pass

    @abstractmethod
    def get_account_info(self) -> Dict[str, Any]:
        """
        Get account information.

        Returns:
            Account details
        """
        pass
