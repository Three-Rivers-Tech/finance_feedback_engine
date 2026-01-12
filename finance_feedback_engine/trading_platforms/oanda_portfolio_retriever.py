"""Oanda-specific portfolio retrieval implementation."""

import logging
from typing import Any, Dict, List

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from requests.exceptions import RequestException, Timeout, ConnectionError

from .base_platform import PositionInfo
from .portfolio_retriever import AbstractPortfolioRetriever, PortfolioRetrievingError
from finance_feedback_engine.utils.validation import standardize_asset_pair
from finance_feedback_engine.monitoring import error_tracking

logger = logging.getLogger(__name__)


class OandaPortfolioRetriever(AbstractPortfolioRetriever):
    """Portfolio retriever for Oanda trading platform.

    Handles:
    - Open positions (realized/unrealized PnL)
    - Account balance and trading capital
    - Margin and leverage calculations
    - NAV and account equity
    """

    def __init__(self, client: Any = None):
        """
        Initialize Oanda portfolio retriever.

        Args:
            client: Oanda API client (from OandaPlatform)
        """
        super().__init__("oanda")
        self.client = client

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((RequestException, Timeout, ConnectionError, Exception)),
        reraise=True
    )
    def get_account_info(self) -> Dict[str, Any]:
        """
        Fetch account information from Oanda API with retry logic.

        Returns:
            Dictionary with account data (balance, positions, margin, etc.)

        Raises:
            PortfolioRetrievingError: If API call fails after retries
        """
        if not self.client:
            raise PortfolioRetrievingError("Oanda client not initialized")

        try:
            account_info = self.client.get_account()
            if not account_info:
                raise PortfolioRetrievingError("No account info returned from Oanda API")
            return account_info
        except Exception as e:
            # Capture error for monitoring
            try:
                error_tracking.capture_exception(e, extra={
                    "platform": "oanda",
                    "operation": "get_account_info",
                    "client_initialized": self.client is not None
                })
            except Exception:
                pass  # Don't fail on error tracking failure
            raise PortfolioRetrievingError(f"Failed to fetch Oanda account info: {e}") from e

    def parse_positions(self, account_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse open positions from account info.

        Args:
            account_info: Result from get_account_info()

        Returns:
            List of PositionInfo dictionaries
        """
        positions = []

        try:
            open_positions = self._safe_get(account_info, "openPositions", [])
            if not open_positions:
                logger.debug("No open positions found")
                return positions

            for pos in open_positions:
                try:
                    instrument = self._safe_get(pos, "instrument")
                    if not instrument:
                        logger.warning("Position missing instrument")
                        continue

                    # Normalize instrument identifier
                    normalized_instrument = standardize_asset_pair(instrument)

                    # Get position details
                    long_units = self._safe_float(self._safe_get(pos, "long", {}).get("units", 0))
                    short_units = self._safe_float(self._safe_get(pos, "short", {}).get("units", 0))

                    # Determine net position
                    net_units = long_units + short_units  # short_units will be negative

                    if net_units == 0:
                        logger.debug(f"Position {instrument} has zero net units")
                        continue

                    # Get pricing information
                    long_info = self._safe_get(pos, "long", {})
                    short_info = self._safe_get(pos, "short", {})

                    # Determine which side has the position
                    if long_units > 0:
                        units = long_units
                        side = "LONG"
                        pnl = self._safe_float(long_info.get("unrealizedPL", 0))
                        avg_price = self._safe_float(long_info.get("averagePrice", 0))
                    elif short_units < 0:
                        units = abs(short_units)
                        side = "SHORT"
                        pnl = self._safe_float(short_info.get("unrealizedPL", 0))
                        avg_price = self._safe_float(short_info.get("averagePrice", 0))
                    else:
                        continue

                    # Safe price extraction - find matching instrument
                    prices = self._safe_get(account_info, "prices", [])
                    price_source = {}
                    for price_entry in prices:
                        if self._safe_get(price_entry, "instrument") == instrument:
                            price_source = price_entry
                            break

                    current_price = self._safe_float(
                        price_source.get("closeoutBid", avg_price),
                        avg_price
                    )

                    position_info = PositionInfo(
                        id=f"{normalized_instrument}_{side}",
                        instrument=normalized_instrument,
                        units=units if side == "LONG" else -units,
                        entry_price=avg_price,
                        current_price=current_price,
                        pnl=pnl,
                        side=side,
                        unrealized_pnl=pnl,
                        opened_at=self._safe_get(pos, "openTime"),
                    )

                    positions.append(position_info)

                except Exception as e:
                    logger.warning(f"Error parsing position {self._safe_get(pos, 'instrument')}: {e}")
                    continue

            logger.info(f"Parsed {len(positions)} open positions")
            return positions

        except Exception as e:
            logger.warning(f"Error parsing positions: {e}")
            return []

    def parse_holdings(self, account_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse account balance/holdings from account info.

        Args:
            account_info: Result from get_account_info()

        Returns:
            List of holding dictionaries (for Oanda, just cash balance)
        """
        holdings = []

        try:
            balance = self._safe_float(self._safe_get(account_info, "balance", 0))
            if balance > 0:
                holdings.append({
                    "asset": "USD",
                    "balance": balance,
                    "value_usd": balance,
                })

            return holdings

        except Exception as e:
            logger.warning(f"Error parsing holdings: {e}")
            return []

    def assemble_result(
        self,
        account_info: Dict[str, Any],
        positions: List[Dict[str, Any]],
        holdings: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Assemble final portfolio breakdown.

        Args:
            account_info: Raw account info
            positions: Parsed positions
            holdings: Parsed holdings

        Returns:
            Portfolio breakdown dictionary
        """
        try:
            balance = self._safe_float(self._safe_get(account_info, "balance", 0))
            equity = self._safe_float(self._safe_get(account_info, "equity", balance))
            nav = self._safe_float(self._safe_get(account_info, "NAV", equity))
            unrealized_pnl = self._safe_float(self._safe_get(account_info, "unrealizedPL", 0))

            # Calculate position-based metrics
            positions_value = sum(
                abs(p.get("units", 0)) * p.get("current_price", 0)
                for p in positions
            )

            available_balance = balance - abs(
                sum(p.get("units", 0) * p.get("current_price", 0) for p in positions)
            )

            logger.info(
                f"Portfolio: balance ${balance:.2f}, equity ${equity:.2f}, "
                f"positions ${positions_value:.2f}, NAV ${nav:.2f}"
            )

            return {
                "positions": positions,
                "holdings": holdings,
                "balance": balance,
                "equity": equity,
                "nav": nav,
                "available_balance": available_balance,
                "unrealized_pnl": unrealized_pnl,
                "margin_used": self._safe_float(self._safe_get(account_info, "marginUsed", 0)),
                "margin_available": self._safe_float(self._safe_get(account_info, "marginAvailable", 0)),
                "margin_rate": self._safe_float(self._safe_get(account_info, "marginRate", 0)),
                "total_value_usd": nav,
                "num_assets": len(holdings),
                "platform": "oanda",
            }

        except Exception as e:
            logger.warning(f"Error assembling result: {e}")
            return {
                "positions": positions,
                "holdings": holdings,
                "platform": "oanda",
                "error": str(e),
            }
