"""Base trading platform interface."""

from abc import ABC, abstractmethod
from typing import Dict, Any
from typing import Optional


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
        # Persistent in-process circuit breaker for execute_trade
        self._execute_breaker = None

    def get_execute_breaker(self):
        """Return the attached CircuitBreaker instance or None."""
        return self._execute_breaker

    def set_execute_breaker(self, breaker: Optional[object]) -> None:
        """Attach a CircuitBreaker instance to this platform."""
        self._execute_breaker = breaker

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

    def get_portfolio_breakdown(self) -> Dict[str, Any]:
        """
        Optional: Get detailed portfolio breakdown.

        Returns:
            Dictionary with detailed portfolio metrics.
        """
        return {
            'total_value_usd': 0,
            'num_assets': 0,
            'holdings': [],
            'error': 'Not implemented'
        }
