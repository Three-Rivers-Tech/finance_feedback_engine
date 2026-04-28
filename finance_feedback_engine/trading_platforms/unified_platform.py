"""Unified trading platform to manage multiple accounts."""

import logging
from typing import Any, Dict, List

from finance_feedback_engine.utils.asset_classifier import classify_asset_pair
from finance_feedback_engine.utils.validation import standardize_asset_pair

from ..config.provider_credentials import resolve_runtime_contract
from .base_platform import BaseTradingPlatform, PositionInfo, PositionsResponse
from .coinbase_platform import CoinbaseAdvancedPlatform
from .mock_platform import MockTradingPlatform
from .oanda_platform import OandaPlatform

logger = logging.getLogger(__name__)


class UnifiedTradingPlatform(BaseTradingPlatform):
    """
    A unified trading platform that aggregates data from multiple platforms.

    Currently supports Coinbase Advanced (for crypto futures) and Oanda
    (for forex).
    """

    def __init__(self, credentials: Dict[str, Any], config: Dict[str, Any] = None):
        """
        Initialize the unified platform.

        Args:
            credentials: Dictionary containing credentials for sub-platforms,
                         e.g., {'coinbase': {...}, 'oanda': {...}}
        """
        super().__init__(credentials)
        self.config = config or {}
        self.platforms: Dict[str, BaseTradingPlatform] = {}

        # Support both 'coinbase' and 'coinbase_advanced' keys
        coinbase_creds = credentials.get("coinbase") or credentials.get(
            "coinbase_advanced"
        )
        if coinbase_creds:
            logger.info("Initializing Coinbase Advanced platform for unified access.")
            self.platforms["coinbase"] = CoinbaseAdvancedPlatform(coinbase_creds)

        if "oanda" in credentials and credentials["oanda"]:
            logger.info("Initializing Oanda platform for unified access.")
            self.platforms["oanda"] = OandaPlatform(credentials["oanda"])

        paper_creds = (
            credentials.get("paper")
            or credentials.get("mock")
            or credentials.get("sandbox")
        )
        if paper_creds is not None:
            initial_balance = None
            if isinstance(paper_creds, dict):
                initial_balance = paper_creds.get("initial_balance")
                if initial_balance is None:
                    cash_val = paper_creds.get("initial_cash_usd") or paper_creds.get(
                        "cash"
                    )
                    if isinstance(cash_val, (int, float)):
                        initial_balance = {"FUTURES_USD": round(float(cash_val), 2)}
            if initial_balance is None:
                initial_balance = {"FUTURES_USD": 10000.0}

            logger.info("Initializing paper trading platform for unified access.")
            self.platforms["paper"] = MockTradingPlatform(
                paper_creds if isinstance(paper_creds, dict) else {},
                initial_balance=initial_balance,
            )

        if not self.platforms:
            raise ValueError("No platforms were configured for UnifiedTradingPlatform.")

        self._paper_execution_enabled = self._is_paper_execution_enabled()

    def _is_paper_execution_enabled(self) -> bool:
        return resolve_runtime_contract(self.config).paper_execution_enabled

    def _resolve_target_platform_name(self, asset_class: str) -> str | None:
        if self._paper_execution_enabled and "paper" in self.platforms:
            return "paper"
        if asset_class == "crypto":
            return (
                "coinbase"
                if "coinbase" in self.platforms
                else ("paper" if "paper" in self.platforms else None)
            )
        if asset_class == "forex":
            return (
                "oanda"
                if "oanda" in self.platforms
                else ("paper" if "paper" in self.platforms else None)
            )
        return "paper" if self._paper_execution_enabled and "paper" in self.platforms else None

    def _resolve_active_execution_platform_name(self) -> str | None:
        if self._paper_execution_enabled and "paper" in self.platforms:
            return "paper"
        for preferred in ("coinbase", "oanda", "paper"):
            if preferred in self.platforms:
                return preferred
        return next(iter(self.platforms.keys()), None)

    def _iter_portfolio_telemetry_platforms(self):
        active_name = self._resolve_active_execution_platform_name()
        if self._paper_execution_enabled and active_name and active_name in self.platforms:
            return [(active_name, self.platforms[active_name])]
        return list(self.platforms.items())

    def _attach_active_platform_metadata(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        platform_breakdowns = payload.get("platform_breakdowns") or {}
        active_name = self._resolve_active_execution_platform_name()
        active_breakdown = platform_breakdowns.get(active_name) if active_name else {}
        active_breakdown = active_breakdown or {}
        futures_summary = active_breakdown.get("futures_summary") or {}

        payload["active_execution_platform"] = active_name
        payload["active_platform_breakdown"] = active_breakdown
        if futures_summary:
            payload["futures_summary"] = futures_summary
            payload["buying_power"] = futures_summary.get(
                "buying_power", payload.get("buying_power", 0.0)
            )
            payload["initial_margin"] = futures_summary.get(
                "initial_margin", payload.get("initial_margin", 0.0)
            )
            payload["total_balance_usd"] = futures_summary.get(
                "total_balance_usd",
                payload.get("total_balance_usd", payload.get("cash_balance_usd", 0.0)),
            )
        return payload

    def get_balance(self) -> Dict[str, float]:
        """
        Get combined account balances from all configured platforms.

        Returns:
            Dictionary mapping asset symbols to balances, prefixed with
            platform name. e.g., {'coinbase_FUTURES_USD': 1000.0,
            'oanda_USD': 50000.0}
        """
        combined_balances = {}
        for name, platform in self._iter_portfolio_telemetry_platforms():
            try:
                balances = platform.get_balance()
                for asset, balance in balances.items():
                    combined_balances[f"{name}_{asset}"] = balance
            except (ValueError, TypeError, KeyError) as e:
                logger.error("Failed to get balance from %s: %s", name, e)

        return combined_balances

    def execute_trade(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a trade on the appropriate platform based on the asset pair.

        - Crypto (BTC, ETH) trades are routed to Coinbase.
        - Forex (e.g., EUR_USD) trades are routed to Oanda.
        """
        asset_pair = standardize_asset_pair(decision.get("asset_pair", ""))

        # Classify asset and route to appropriate platform
        asset_class = classify_asset_pair(asset_pair)

        target_platform_name = self._resolve_target_platform_name(asset_class)
        target_platform = self.platforms.get(target_platform_name) if target_platform_name else None

        if target_platform:
            logger.info(
                "Routing trade for %s to %s",
                asset_pair,
                target_platform.__class__.__name__,
            )
            return target_platform.execute_trade(decision)
        else:
            logger.error("No suitable platform found for asset pair: %s", asset_pair)
            return {
                "success": False,
                "error": f"No platform available for asset pair {asset_pair}",
                "decision_id": decision.get("id"),
            }

    def get_account_info(self) -> Dict[str, Any]:
        """
        Get combined account information from all platforms.
        """
        combined_info = {}
        for name, platform in self._iter_portfolio_telemetry_platforms():
            try:
                combined_info[name] = platform.get_account_info()
            except (ValueError, TypeError, KeyError) as e:
                logger.error("Failed to get account info from %s: %s", name, e)
                combined_info[name] = {"error": str(e)}
        return combined_info

    def get_active_positions(self) -> PositionsResponse:
        """
        Get combined active positions from all configured sub-platforms.

        Returns:
            A dictionary containing a list of active positions, each represented
            by a dictionary with details like instrument, units, PnL, etc.
            Each position will also include a 'platform' key indicating its source.
        """
        all_positions: List[PositionInfo] = []
        for name, platform_instance in self._iter_portfolio_telemetry_platforms():
            try:
                # Call get_active_positions on the sub-platform
                platform_positions_data = platform_instance.get_active_positions()
                for pos in platform_positions_data.get("positions", []):
                    # Add platform name to each position for context in CLI display
                    pos["platform"] = name
                    all_positions.append(pos)
            except Exception as e:
                logger.warning(
                    "Could not fetch active positions from %s platform: %s", name, e
                )
        return {"positions": all_positions}

    def get_portfolio_breakdown(self) -> Dict[str, Any]:
        """
        Get a combined portfolio breakdown from all platforms.

        Merges portfolio data from Coinbase (futures) and Oanda (forex).
        """
        total_value_usd = 0
        total_unrealized = 0.0
        all_holdings = []
        num_assets = 0
        cash_balances = {}

        platform_breakdowns = {}

        for name, platform in self._iter_portfolio_telemetry_platforms():
            try:
                breakdown = platform.get_portfolio_breakdown()
                platform_breakdowns[name] = breakdown

                total_value_usd += breakdown.get("total_value_usd", 0)
                # Capture unrealized P&L if the platform exposes it
                total_unrealized += breakdown.get("unrealized_pnl", 0.0)

                # Capture cash/balance if provided by the platform
                bal = breakdown.get("balance") or breakdown.get("total_balance_usd")
                if bal is not None:
                    try:
                        cash_balances[name] = float(bal)
                    except Exception:
                        cash_balances[name] = 0.0

                # Add platform prefix to holdings
                holdings = breakdown.get("holdings", [])
                for holding in holdings:
                    holding["platform"] = name
                all_holdings.extend(holdings)

                num_assets += breakdown.get("num_assets", 0)

            except (ValueError, TypeError, KeyError) as e:
                logger.error("Failed to get portfolio breakdown from %s: %s", name, e)

        # Recalculate allocation percentages across the entire portfolio.
        # Use total notional exposure (sum of all holdings' values) rather
        # than account balance, so allocations make sense for leveraged positions.
        total_notional_exposure = sum(
            holding.get("value_usd", 0) for holding in all_holdings
        )

        if total_notional_exposure > 0:
            for holding in all_holdings:
                allocation = (
                    holding.get("value_usd", 0) / total_notional_exposure
                ) * 100
                holding["allocation_pct"] = allocation

        # Sum cash balances across platforms
        cash_balance_usd = sum(cash_balances.values()) if cash_balances else 0.0

        return self._attach_active_platform_metadata(
            {
                "total_value_usd": total_value_usd,
                "cash_balance_usd": cash_balance_usd,
                "per_platform_cash": cash_balances,
                "num_assets": num_assets,
                "holdings": all_holdings,
                "platform_breakdowns": platform_breakdowns,
                "unrealized_pnl": total_unrealized,
            }
        )
