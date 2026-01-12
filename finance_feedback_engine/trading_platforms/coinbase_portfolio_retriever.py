"""Coinbase-specific portfolio retrieval implementation."""

import logging
from typing import Any, Dict, List, Optional

from requests.exceptions import RequestException

from .base_platform import PositionInfo
from .portfolio_retriever import AbstractPortfolioRetriever, PortfolioRetrievingError

logger = logging.getLogger(__name__)


def _get_attr_value(obj: Any, attr: str, default: Any = None) -> Any:
    """
    Safely get attribute from object or dict.

    Args:
        obj: Object or dict to get attribute from
        attr: Attribute name
        default: Default value if attribute not found

    Returns:
        Attribute value or default
    """
    if isinstance(obj, dict):
        return obj.get(attr, default)
    return getattr(obj, attr, default)


def _to_float_value(v: Any) -> float:
    """
    Convert value to float, handling both dict and object formats.

    Args:
        v: Value to convert (can be dict with 'value' key, object with 'value' attr, or direct number)

    Returns:
        Float value
    """
    if isinstance(v, dict):
        return float(v.get("value", 0) or 0)
    return float(getattr(v, "value", v) or 0)


class CoinbasePortfolioRetriever(AbstractPortfolioRetriever):
    """Portfolio retriever for Coinbase Advanced platform.

    Handles:
    - Futures positions (long/short with leverage)
    - Spot USD/USDC balances
    - Futures summary (balance, PnL, margin, buying power)
    - Position margin/leverage calculations

    Uses stable API endpoints (get_futures_balance_summary, list_futures_positions, get_accounts)
    and gracefully falls back to portfolio breakdown endpoints if needed.
    """

    def __init__(self, client: Any = None):
        """
        Initialize Coinbase portfolio retriever.

        Args:
            client: Coinbase API client (from CoinbaseAdvancedPlatform)
        """
        super().__init__("coinbase")
        self.client = client

    def get_account_info(self) -> Dict[str, Any]:
        """
        Fetch account information from Coinbase API.

        Returns:
            Dictionary with:
            - futures_response: Balance summary response
            - positions_response: Futures positions response
            - accounts_response: Spot accounts response
            - breakdown_response: Portfolio breakdown (optional)

        Raises:
            PortfolioRetrievingError: If API calls fail
        """
        if not self.client:
            raise PortfolioRetrievingError("Coinbase client not initialized")

        try:
            account_info = {}

            # Try stable endpoints first
            if (
                hasattr(self.client, "get_futures_balance_summary")
                and hasattr(self.client, "list_futures_positions")
                and hasattr(self.client, "get_accounts")
            ):
                logger.debug("Using stable Coinbase API endpoints")

                try:
                    account_info["futures_response"] = self.client.get_futures_balance_summary()
                except RequestException:
                    raise
                except Exception as e:
                    logger.warning("Could not fetch futures summary: %s", e)
                    account_info["futures_response"] = None

                try:
                    account_info["positions_response"] = self.client.list_futures_positions()
                except RequestException:
                    raise
                except Exception as e:
                    logger.warning("Could not fetch futures positions: %s", e)
                    account_info["positions_response"] = None

                try:
                    account_info["accounts_response"] = self.client.get_accounts()
                except RequestException:
                    raise
                except Exception as e:
                    logger.warning("Could not fetch spot accounts: %s", e)
                    account_info["accounts_response"] = None

            # Fallback to portfolio breakdown endpoints
            if not account_info or all(v is None for v in account_info.values()):
                logger.debug("Falling back to Coinbase portfolio breakdown endpoints")

                try:
                    portfolios_response = self.client.get_portfolios()
                    if hasattr(portfolios_response, "portfolios"):
                        portfolios = portfolios_response.portfolios
                    else:
                        portfolios = portfolios_response.get("portfolios", [])

                    if portfolios:
                        portfolio_uuid = portfolios[0].get("uuid") if isinstance(portfolios[0], dict) else portfolios[0].uuid
                        account_info["breakdown_response"] = self.client.get_portfolio_breakdown(
                            portfolio_uuid=portfolio_uuid
                        )
                except Exception as e:
                    logger.warning("Could not fetch portfolio breakdown: %s", e)
                    raise PortfolioRetrievingError(f"All portfolio retrieval methods failed: {e}") from e

            return account_info

        except PortfolioRetrievingError:
            raise
        except Exception as e:
            raise PortfolioRetrievingError(f"Failed to fetch Coinbase account info: {e}") from e

    def parse_positions(self, account_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse futures positions from account info.

        Args:
            account_info: Result from get_account_info()

        Returns:
            List of PositionInfo dictionaries
        """
        positions = []

        # Try stable endpoint first
        positions_response = account_info.get("positions_response")
        if positions_response:
            try:
                positions_list = getattr(positions_response, "positions", None) or []
                positions.extend(self._parse_stable_positions(positions_list))
            except Exception as e:
                logger.warning("Error parsing stable positions: %s", e)

        # Try portfolio breakdown endpoint
        breakdown_response = account_info.get("breakdown_response")
        if breakdown_response and not positions:
            try:
                breakdown_data = breakdown_response.get("breakdown") if isinstance(breakdown_response, dict) else breakdown_response.breakdown
                futures_positions_data = breakdown_data.get("futures_positions", [])
                perp_positions_data = breakdown_data.get("perp_positions", [])
                positions_list = futures_positions_data + perp_positions_data
                positions.extend(self._parse_breakdown_positions(positions_list))
            except Exception as e:
                logger.warning("Error parsing breakdown positions: %s", e)

        return positions

    def _parse_stable_positions(self, positions_list: List[Any]) -> List[PositionInfo]:
        """Parse positions from stable API endpoint."""
        positions = []
        default_leverage = 10.0

        for pos in positions_list:
            try:
                product_id = self._safe_get(pos, "product_id")
                instrument = product_id or "UNKNOWN"
                side = (self._safe_get(pos, "side", "") or "").upper()

                # Try multiple field names for contract size
                contracts = 0.0
                for field_name in ["number_of_contracts", "amount", "size"]:
                    val = self._safe_get(pos, field_name)
                    if val:
                        contracts = self._safe_float(val)
                        if contracts != 0:
                            break

                if contracts == 0:
                    logger.debug(f"Position {instrument} has zero contracts")
                    continue

                signed_contracts = contracts if side == "LONG" else -contracts
                entry_price = self._safe_float(self._safe_get(pos, "avg_entry_price"))
                current_price = self._safe_float(self._safe_get(pos, "current_price"))
                unrealized_pnl = self._safe_float(self._safe_get(pos, "unrealized_pnl"))

                # Try multiple leverage field names
                leverage = self._get_first_matching(pos, [
                    "leverage", "leverage_ratio", "margin_leverage",
                    "leverage_level", "leverage_amount"
                ], default_leverage)
                leverage = self._safe_float(leverage, default_leverage)

                position_info = PositionInfo(
                    id=str(self._safe_get(pos, "id") or instrument),
                    instrument=instrument,
                    units=signed_contracts,
                    entry_price=entry_price,
                    current_price=current_price,
                    pnl=unrealized_pnl,
                    opened_at=self._safe_get(pos, "created_at") or self._safe_get(pos, "open_time"),
                    product_id=product_id,
                    side=side,
                    contracts=contracts,
                    unrealized_pnl=unrealized_pnl,
                    daily_pnl=self._safe_float(self._safe_get(pos, "daily_realized_pnl")),
                    leverage=leverage,
                )

                positions.append(position_info)

            except Exception as e:
                logger.warning(f"Error parsing position {self._safe_get(pos, 'product_id')}: {e}")
                continue

        return positions

    def _parse_breakdown_positions(self, positions_list: List[Any]) -> List[PositionInfo]:
        """Parse positions from portfolio breakdown endpoint."""
        positions = []
        default_leverage = 10.0

        for pos in positions_list:
            try:
                product_id = self._safe_get(pos, "product_id")
                instrument = product_id or "UNKNOWN"
                side = (self._safe_get(pos, "side", "") or "").upper()

                contracts = 0.0
                for field_name in ["number_of_contracts", "amount", "size"]:
                    val = self._safe_get(pos, field_name)
                    if val:
                        contracts = self._safe_float(val)
                        if contracts != 0:
                            break

                if contracts == 0:
                    continue

                signed_contracts = contracts if side == "LONG" else -contracts
                entry_price = self._safe_float(self._safe_get(pos, "avg_entry_price"))
                current_price = self._safe_float(self._safe_get(pos, "current_price"))
                unrealized_pnl = self._safe_float(self._safe_get(pos, "unrealized_pnl"))

                leverage = self._get_first_matching(pos, [
                    "leverage", "leverage_ratio", "margin_leverage",
                    "leverage_level", "leverage_amount"
                ], default_leverage)
                leverage = self._safe_float(leverage, default_leverage)

                position_info = PositionInfo(
                    id=str(self._safe_get(pos, "id") or instrument),
                    instrument=instrument,
                    units=signed_contracts,
                    entry_price=entry_price,
                    current_price=current_price,
                    pnl=unrealized_pnl,
                    opened_at=self._safe_get(pos, "created_at") or self._safe_get(pos, "open_time"),
                    product_id=product_id,
                    side=side,
                    contracts=contracts,
                    unrealized_pnl=unrealized_pnl,
                    daily_pnl=self._safe_float(self._safe_get(pos, "daily_realized_pnl")),
                    leverage=leverage,
                )

                positions.append(position_info)

            except Exception as e:
                logger.warning(f"Error parsing position: {e}")
                continue

        logger.info(f"Parsed {len(positions)} active futures positions")
        return positions

    def parse_holdings(self, account_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse spot holdings from account info.

        Args:
            account_info: Result from get_account_info()

        Returns:
            List of holding dictionaries
        """
        holdings = []
        spot_value_usd = 0.0

        # Try stable endpoint first (get_accounts)
        accounts_response = account_info.get("accounts_response")
        if accounts_response:
            try:
                accounts = getattr(accounts_response, "accounts", None) or []
                for account in accounts:
                    currency = (getattr(account, "currency", "") or "").upper()
                    if currency not in ("USD", "USDC"):
                        continue

                    available_balance = getattr(account, "available_balance", None)
                    balance_value = getattr(available_balance, "value", None) if available_balance else None
                    amount = float(balance_value or 0)

                    if amount > 0:
                        holdings.append({"asset": currency, "balance": amount})
                        spot_value_usd += amount

                return holdings

            except Exception as e:
                logger.warning(f"Error parsing accounts: {e}")

        # Try portfolio breakdown endpoint
        breakdown_response = account_info.get("breakdown_response")
        if breakdown_response:
            try:
                breakdown_data = breakdown_response.get("breakdown") if isinstance(breakdown_response, dict) else breakdown_response.breakdown
                spot_positions = breakdown_data.get("spot_positions", [])

                for position in spot_positions:
                    asset = position.get("asset")
                    if asset in ["USD", "USDC"]:
                        available_fiat = float(position.get("available_to_trade_fiat", 0))
                        if available_fiat > 0:
                            holdings.append({
                                "asset": asset,
                                "balance": available_fiat,
                                "value_usd": available_fiat,
                            })
                            spot_value_usd += available_fiat

                return holdings

            except Exception as e:
                logger.warning(f"Error parsing spot positions: {e}")

        return holdings

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
        futures_value_usd = 0.0
        futures_summary = {}

        # Calculate futures value from balance summary
        futures_response = account_info.get("futures_response")
        if futures_response:
            try:
                balance_summary = _get_attr_value(futures_response, "balance_summary")
                if balance_summary:
                    futures_value_usd = _to_float_value(
                        _get_attr_value(balance_summary, "futures_buying_power", 0)
                    )
                    futures_summary = {
                        "total_balance_usd": futures_value_usd,
                        "unrealized_pnl": _to_float_value(
                            _get_attr_value(balance_summary, "unrealized_pnl", 0)
                        ),
                        "daily_realized_pnl": _to_float_value(
                            _get_attr_value(balance_summary, "daily_realized_pnl", 0)
                        ),
                        "buying_power": _to_float_value(
                            _get_attr_value(balance_summary, "futures_buying_power", 0)
                        ),
                        "initial_margin": _to_float_value(
                            _get_attr_value(balance_summary, "initial_margin", 0)
                        ),
                    }
            except Exception as e:
                logger.warning(f"Error extracting futures summary: {e}")

        # Calculate spot value
        spot_value_usd = sum(h.get("balance", 0) for h in holdings if h.get("balance"))

        logger.info(
            f"Portfolio: futures ${futures_value_usd:.2f}, spot ${spot_value_usd:.2f}, "
            f"total ${futures_value_usd + spot_value_usd:.2f}"
        )

        return {
            "futures_positions": positions,
            "futures_summary": futures_summary,
            "holdings": holdings,
            "total_value_usd": futures_value_usd + spot_value_usd,
            "futures_value_usd": futures_value_usd,
            "spot_value_usd": spot_value_usd,
            "num_assets": len(holdings),
            "unrealized_pnl": futures_summary.get("unrealized_pnl", 0.0),
            "platform": "coinbase",
        }
