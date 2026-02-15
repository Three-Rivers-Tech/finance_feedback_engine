"""Abstract base class and utilities for portfolio retrieval across platforms.

This module provides a reusable pattern for extracting portfolio/account information
from trading platforms, eliminating code duplication across platform implementations.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from finance_feedback_engine.monitoring import error_tracking

logger = logging.getLogger(__name__)


class PortfolioRetrievingError(Exception):
    """Raised when portfolio retrieval fails."""
    pass


class AbstractPortfolioRetriever(ABC):
    """
    Abstract base class for platform-specific portfolio retrieval.

    Standardizes the portfolio retrieval pattern across Coinbase, Oanda, and other platforms.
    Each platform implements this interface with its own API-specific logic.

    The interface separates:
    - Platform setup/authentication (done in __init__ by platform)
    - Account data fetching (get_account_info)
    - Position parsing (parse_positions)
    - Holdings parsing (parse_holdings)
    - Result assembly (assemble_result)

    This reduces code duplication from ~400 LOC across 3 platforms to ~150 LOC here.
    """

    def __init__(self, platform_name: str):
        """Initialize the retriever.

        Args:
            platform_name: Name of the platform (e.g., "coinbase", "oanda")
        """
        self.platform_name = platform_name

    def get_portfolio_breakdown(self) -> Dict[str, Any]:
        """
        Get complete portfolio breakdown.

        This is the main entry point. It orchestrates the retrieval steps:
        1. Get account info (balance, currency, etc.)
        2. Get positions (futures, forex, etc.)
        3. Get holdings (spot, cash balances, etc.)
        4. Assemble results

        Returns:
            Dictionary with portfolio metrics

        Raises:
            PortfolioRetrievingError: If retrieval fails
        """
        logger.info(f"Fetching {self.platform_name} portfolio breakdown")

        try:
            account_info = self.get_account_info()
            positions = self.parse_positions(account_info)
            holdings = self.parse_holdings(account_info)

            return self.assemble_result(account_info, positions, holdings)

        except PortfolioRetrievingError:
            raise
        except Exception as e:
            logger.error(f"Portfolio retrieval failed: {e}", exc_info=True)

            # Report to error tracker
            try:
                error_tracking.capture_exception(e, extra={
                    "platform_name": self.platform_name,
                    "stage": "get_portfolio_breakdown",
                    "account_info_available": "account_info" in locals()
                })
            except (ImportError, AttributeError, RuntimeError) as err:
                # Don't fail on error tracking failure
                logger.debug(
                    "Error tracking capture failed for %s: %s",
                    self.platform_name,
                    err,
                )
                pass

            raise PortfolioRetrievingError(
                f"Failed to retrieve {self.platform_name} portfolio: {str(e)}"
            ) from e

    @abstractmethod
    def get_account_info(self) -> Dict[str, Any]:
        """
        Fetch raw account information from platform API.

        Returns:
            Dictionary with account data from API (structure varies by platform)

        Raises:
            PortfolioRetrievingError: If API call fails
        """
        pass

    @abstractmethod
    def parse_positions(self, account_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse positions from account info.

        Args:
            account_info: Result from get_account_info()

        Returns:
            List of position dictionaries (can be PositionInfo objects)
        """
        pass

    @abstractmethod
    def parse_holdings(self, account_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse holdings (spot balances, cash, etc.) from account info.

        Args:
            account_info: Result from get_account_info()

        Returns:
            List of holding dictionaries (spot positions, currencies, etc.)
        """
        pass

    @abstractmethod
    def assemble_result(
        self,
        account_info: Dict[str, Any],
        positions: List[Dict[str, Any]],
        holdings: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Assemble final portfolio breakdown result.

        Args:
            account_info: Result from get_account_info()
            positions: Result from parse_positions()
            holdings: Result from parse_holdings()

        Returns:
            Dictionary with keys like:
            - total_value_usd
            - num_assets
            - positions (list)
            - holdings (list)
            - ... (platform-specific keys)
        """
        pass

    def _safe_get(self, obj: Any, key: str, default: Any = None) -> Any:
        """
        Safely get value from dict or object attribute.

        Handles both dict-like and object-like API responses.

        Args:
            obj: Object or dict to access
            key: Key or attribute name
            default: Default value if not found

        Returns:
            The value, or default if not found
        """
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        """
        Safely convert value to float.

        Handles None, strings, dict values, etc.

        Args:
            value: Value to convert
            default: Default if conversion fails

        Returns:
            Float value or default
        """
        if value is None:
            return default

        # Handle dict with 'value' key (common in APIs)
        if isinstance(value, dict):
            value = value.get("value", default)

        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _get_first_matching(
        self,
        obj: Any,
        field_names: List[str],
        default: Any = None
    ) -> Any:
        """
        Get first matching field from list of possible names.

        Useful when API response format is inconsistent or has multiple
        names for the same field.

        Args:
            obj: Object or dict to access
            field_names: List of field names to try in order
            default: Default if none found

        Returns:
            First matching value, or default
        """
        for field_name in field_names:
            value = self._safe_get(obj, field_name)
            if value is not None and value != "":
                return value
        return default


class PortfolioRetrieverFactory:
    """Factory for creating platform-specific portfolio retrievers."""

    _retrievers: Dict[str, type] = {}

    @classmethod
    def register(cls, platform_name: str, retriever_class: type) -> None:
        """
        Register a portfolio retriever for a platform.

        Args:
            platform_name: Platform name (e.g., "coinbase", "oanda")
            retriever_class: Class inheriting from AbstractPortfolioRetriever
        """
        cls._retrievers[platform_name.lower()] = retriever_class
        logger.debug(f"Registered portfolio retriever for {platform_name}")

    @classmethod
    def create(cls, platform_name: str, *args, **kwargs) -> AbstractPortfolioRetriever:
        """
        Create a portfolio retriever for the given platform.

        Args:
            platform_name: Platform name
            *args, **kwargs: Arguments to pass to retriever constructor

        Returns:
            Portfolio retriever instance

        Raises:
            ValueError: If platform not registered
        """
        platform_key = platform_name.lower()
        if platform_key not in cls._retrievers:
            raise ValueError(
                f"No portfolio retriever registered for platform '{platform_name}'. "
                f"Available: {list(cls._retrievers.keys())}"
            )

        retriever_class = cls._retrievers[platform_key]
        return retriever_class(*args, **kwargs)

    @classmethod
    def list_platforms(cls) -> List[str]:
        """Get list of registered platform names."""
        return list(cls._retrievers.keys())
