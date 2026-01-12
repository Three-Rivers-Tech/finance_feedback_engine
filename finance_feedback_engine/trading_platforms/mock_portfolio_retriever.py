"""Mock portfolio retriever for testing."""

import logging
from typing import Any, Dict, List

from .base_platform import PositionInfo
from .portfolio_retriever import AbstractPortfolioRetriever, PortfolioRetrievingError

logger = logging.getLogger(__name__)


class MockPortfolioRetriever(AbstractPortfolioRetriever):
    """Portfolio retriever for mock trading platform.

    Used for testing and simulation. Provides deterministic data
    matching Coinbase portfolio format.
    """

    def __init__(self, client: Any = None):
        """
        Initialize mock portfolio retriever.

        Args:
            client: Mock API client (from MockPlatform)
        """
        super().__init__("mock")
        self.client = client

    def get_account_info(self) -> Dict[str, Any]:
        """
        Get mock account information.

        Returns:
            Dictionary with mock balance and position data

        Raises:
            PortfolioRetrievingError: If client not initialized
        """
        if not self.client:
            raise PortfolioRetrievingError("Mock client not initialized")

        try:
            return {
                "balance": self.client._balance.copy() if hasattr(self.client, "_balance") else {},
                "positions": self.client._positions.copy() if hasattr(self.client, "_positions") else {},
                "contract_multiplier": getattr(self.client, "_contract_multiplier", 0.1),
            }
        except Exception as e:
            raise PortfolioRetrievingError(f"Failed to fetch mock account info: {e}") from e

    def parse_positions(self, account_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse mock positions.

        Args:
            account_info: Result from get_account_info()

        Returns:
            List of PositionInfo dictionaries
        """
        positions = []
        contract_multiplier = account_info.get("contract_multiplier", 0.1)

        try:
            positions_data = account_info.get("positions", {})

            for asset_pair, pos in positions_data.items():
                try:
                    contracts = pos.get("contracts", 0)
                    if contracts == 0:
                        continue

                    entry_price = pos.get("entry_price", 0)
                    # Use current_price from position if available (set by update_position_prices),
                    # otherwise assume +1% gain for mock
                    current_price = pos.get("current_price", entry_price * 1.01)
                    side = pos.get("side", "LONG")

                    unrealized_pnl = (
                        (current_price - entry_price)
                        * contracts
                        * contract_multiplier
                    )

                    signed_contracts = contracts if side == "LONG" else -contracts

                    position_info = PositionInfo(
                        id=asset_pair,
                        instrument=asset_pair,
                        units=signed_contracts,
                        entry_price=entry_price,
                        current_price=current_price,
                        pnl=unrealized_pnl,
                        side=side,
                        contracts=contracts,
                        unrealized_pnl=unrealized_pnl,
                        daily_pnl=pos.get("daily_pnl", 0.0),
                        leverage=10.0,  # Mock default leverage
                    )

                    positions.append(position_info)

                except Exception as e:
                    logger.warning(f"Error parsing mock position {asset_pair}: {e}")
                    continue

            logger.info(f"Parsed {len(positions)} mock positions")
            return positions

        except Exception as e:
            logger.warning(f"Error parsing mock positions: {e}")
            return []

    def parse_holdings(self, account_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse mock holdings.

        Args:
            account_info: Result from get_account_info()

        Returns:
            List of holding dictionaries
        """
        holdings = []

        try:
            balance = account_info.get("balance", {})
            spot_usd = balance.get("SPOT_USD", 0)
            spot_usdc = balance.get("SPOT_USDC", 0)

            if spot_usd > 0:
                holdings.append({
                    "asset": "USD",
                    "balance": spot_usd,
                    "value_usd": spot_usd,
                })

            if spot_usdc > 0:
                holdings.append({
                    "asset": "USDC",
                    "balance": spot_usdc,
                    "value_usd": spot_usdc,
                })

            return holdings

        except Exception as e:
            logger.warning(f"Error parsing mock holdings: {e}")
            return []

    def assemble_result(
        self,
        account_info: Dict[str, Any],
        positions: List[Dict[str, Any]],
        holdings: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Assemble final mock portfolio breakdown.

        Args:
            account_info: Raw account info
            positions: Parsed positions
            holdings: Parsed holdings

        Returns:
            Portfolio breakdown dictionary
        """
        try:
            balance = account_info.get("balance", {})
            contract_multiplier = account_info.get("contract_multiplier", 0.1)

            futures_balance = balance.get("FUTURES_USD", 0)
            spot_usd = balance.get("SPOT_USD", 0)
            spot_usdc = balance.get("SPOT_USDC", 0)
            spot_value = spot_usd + spot_usdc

            # Calculate totals from positions
            total_unrealized_pnl = sum(p.get("unrealized_pnl", 0) for p in positions)
            total_notional = sum(
                p.get("contracts", 0) * p.get("current_price", 0) * contract_multiplier
                for p in positions
            )

            # Mock futures summary
            buying_power = futures_balance * 2  # Mock 2x buying power
            initial_margin = total_notional / 10 if total_notional > 0 else 0  # Mock 10x leverage

            futures_summary = {
                "total_balance_usd": futures_balance,
                "unrealized_pnl": total_unrealized_pnl,
                "daily_realized_pnl": 0.0,  # Mock
                "buying_power": buying_power,
                "initial_margin": initial_margin,
            }

            total_value = futures_balance + spot_value + total_unrealized_pnl

            logger.info(
                f"Mock portfolio: total_value=${total_value:.2f}, "
                f"futures=${futures_balance:.2f}, spot=${spot_value:.2f}, "
                f"positions={len(positions)}"
            )

            return {
                "futures_positions": positions,
                "futures_summary": futures_summary,
                "holdings": holdings,
                "total_value_usd": total_value,
                "futures_value_usd": futures_balance,
                "spot_value_usd": spot_value,
                "num_assets": len(holdings),
                "unrealized_pnl": total_unrealized_pnl,
                "platform": "mock",
            }

        except Exception as e:
            logger.warning(f"Error assembling mock result: {e}")
            return {
                "futures_positions": positions,
                "holdings": holdings,
                "platform": "mock",
                "error": str(e),
            }
