"""Unified trading platform to manage multiple accounts."""

import logging
from typing import Any, Dict, List


from finance_feedback_engine.utils.asset_classifier import classify_asset_pair
from finance_feedback_engine.utils.circuit_breaker import CircuitBreaker
from finance_feedback_engine.utils.validation import standardize_asset_pair
from finance_feedback_engine.exceptions import TradingError

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
        # Cache last known-good per-platform balances to preserve context during
        # transient upstream/auth/network failures.
        self._last_good_balances: Dict[str, Dict[str, float]] = {}

        # Support both 'coinbase' and 'coinbase_advanced' keys
        coinbase_creds = credentials.get("coinbase") or credentials.get(
            "coinbase_advanced"
        )
        if coinbase_creds:
            logger.info("Initializing Coinbase Advanced platform for unified access.")
            self.platforms["coinbase"] = CoinbaseAdvancedPlatform(coinbase_creds)

        oanda_creds = credentials.get("oanda")
        if oanda_creds:
            oanda_api_key = str(oanda_creds.get("api_key", "") or "")
            oanda_account_id = str(oanda_creds.get("account_id", "") or "")
            has_real_oanda_creds = (
                bool(oanda_api_key)
                and bool(oanda_account_id)
                and not oanda_api_key.startswith("YOUR_")
                and not oanda_account_id.startswith("YOUR_")
            )
            if has_real_oanda_creds:
                logger.info("Initializing Oanda platform for unified access.")
                self.platforms["oanda"] = OandaPlatform(oanda_creds)
            else:
                logger.info("Skipping Oanda platform initialization due to missing or placeholder credentials.")

        paper_creds = credentials.get("paper") or credentials.get("mock") or credentials.get("sandbox")
        if paper_creds is not None:
            # Build a sane default balance when only cash is provided
            initial_balance = None
            if isinstance(paper_creds, dict):
                initial_balance = paper_creds.get("initial_balance")
                # Allow simple numeric cash override
                if initial_balance is None:
                    cash_val = paper_creds.get("initial_cash_usd") or paper_creds.get("cash")
                    if isinstance(cash_val, (int, float)):
                        initial_balance = {
                            "FUTURES_USD": round(float(cash_val), 2),
                        }
                # If no balance provided at all, seed a futures-only 10k paper account
                if initial_balance is None:
                    initial_balance = {
                        "FUTURES_USD": 10000.0,
                    }
            else:
                initial_balance = {
                    "FUTURES_USD": 6000.0,
                    "SPOT_USD": 3000.0,
                    "SPOT_USDC": 1000.0,
                }

            logger.info("Initializing paper trading platform for unified access.")
            self.platforms["paper"] = MockTradingPlatform(
                paper_creds if isinstance(paper_creds, dict) else {},
                initial_balance=initial_balance,
            )

        if not self.platforms:
            raise ValueError("No platforms were configured for UnifiedTradingPlatform.")

        self._paper_execution_enabled = self._is_paper_execution_enabled()

    def _is_paper_execution_enabled(self) -> bool:
        """Return True when config explicitly enables paper/mock execution routing."""
        paper_defaults = (self.config.get("paper_trading_defaults") or {})
        paper_cfg = (self.config.get("paper_trading") or {})
        feature_flags = (self.config.get("features") or {})
        return bool(
            paper_defaults.get("enabled")
            or paper_cfg.get("enabled")
            or feature_flags.get("paper_trading_mode")
        )

    def _resolve_target_platform_name(self, asset_class: str) -> str | None:
        """Pick the execution venue for a decision."""
        if self._paper_execution_enabled and "paper" in self.platforms:
            return "paper"

        if asset_class == "crypto":
            return "coinbase" if "coinbase" in self.platforms else ("paper" if "paper" in self.platforms else None)
        if asset_class == "forex":
            return "oanda" if "oanda" in self.platforms else ("paper" if "paper" in self.platforms else None)

        return "paper" if "paper" in self.platforms and self._paper_execution_enabled else None

    def _resolve_active_execution_platform_name(self) -> str | None:
        """Return the platform name that portfolio/risk consumers should treat as active."""
        if self._paper_execution_enabled and "paper" in self.platforms:
            return "paper"
        for preferred in ("coinbase", "oanda", "paper"):
            if preferred in self.platforms:
                return preferred
        return next(iter(self.platforms.keys()), None)

    def _attach_active_platform_metadata(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Expose active-platform aliases so higher layers do not hard-code coinbase."""
        platform_breakdowns = payload.get("platform_breakdowns") or {}
        active_name = self._resolve_active_execution_platform_name()
        active_breakdown = platform_breakdowns.get(active_name) if active_name else {}
        if not active_breakdown and platform_breakdowns:
            active_name, active_breakdown = next(iter(platform_breakdowns.items()))

        active_breakdown = active_breakdown or {}
        futures_summary = active_breakdown.get("futures_summary") or {}

        payload["active_execution_platform"] = active_name
        payload["active_platform_breakdown"] = active_breakdown
        if futures_summary:
            payload["futures_summary"] = futures_summary
            payload["buying_power"] = futures_summary.get("buying_power", payload.get("buying_power", 0.0))
            payload["initial_margin"] = futures_summary.get("initial_margin", payload.get("initial_margin", 0.0))
            payload["total_balance_usd"] = futures_summary.get("total_balance_usd", payload.get("total_balance_usd", payload.get("cash_balance_usd", 0.0)))

        return payload

    def _iter_portfolio_telemetry_platforms(self):
        """Yield only the platform(s) that should contribute to portfolio telemetry."""
        active_name = self._resolve_active_execution_platform_name()
        if self._paper_execution_enabled and active_name and active_name in self.platforms:
            return [(active_name, self.platforms[active_name])]
        return list(self.platforms.items())

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
                balances = platform.get_balance() or {}
                if balances:
                    # Keep a per-platform last known-good snapshot for fail-closed context continuity
                    self._last_good_balances[name] = dict(balances)
                for asset, balance in balances.items():
                    combined_balances[f"{name}_{asset}"] = balance
            except ConnectionError as e:
                logger.error(
                    "Connection error getting balance from platform",
                    extra={
                        "platform": name,
                        "platform_class": platform.__class__.__name__,
                        "error": str(e),
                        "error_type": "connection"
                    },
                    exc_info=True
                )
                cached = self._last_good_balances.get(name)
                if cached:
                    logger.warning(
                        "Using cached %s balance snapshot after connection error",
                        name,
                    )
                    for asset, balance in cached.items():
                        combined_balances[f"{name}_{asset}"] = balance
                # TODO: Alert on repeated platform connection failures (THR-XXX)
            except (ValueError, TypeError, KeyError) as e:
                logger.error(
                    "Data validation error getting balance from platform",
                    extra={
                        "platform": name,
                        "platform_class": platform.__class__.__name__,
                        "error": str(e),
                        "error_type": "validation"
                    }
                )
                cached = self._last_good_balances.get(name)
                if cached:
                    logger.warning(
                        "Using cached %s balance snapshot after validation error",
                        name,
                    )
                    for asset, balance in cached.items():
                        combined_balances[f"{name}_{asset}"] = balance
                # TODO: Track data validation errors for platform health monitoring (THR-XXX)
            except TradingError as e:
                logger.warning(
                    "Trading error getting balance from platform; using cached snapshot when available",
                    extra={
                        "platform": name,
                        "platform_class": platform.__class__.__name__,
                        "error": str(e),
                        "error_type": "trading"
                    }
                )
                cached = self._last_good_balances.get(name)
                if cached:
                    logger.warning(
                        "Using cached %s balance snapshot after trading error",
                        name,
                    )
                    for asset, balance in cached.items():
                        combined_balances[f"{name}_{asset}"] = balance
            except Exception as e:
                logger.error(
                    "Unexpected error getting balance from platform",
                    extra={
                        "platform": name,
                        "platform_class": platform.__class__.__name__,
                        "error": str(e),
                        "error_type": type(e).__name__
                    },
                    exc_info=True
                )
                cached = self._last_good_balances.get(name)
                if cached:
                    logger.warning(
                        "Using cached %s balance snapshot after unexpected error",
                        name,
                    )
                    for asset, balance in cached.items():
                        combined_balances[f"{name}_{asset}"] = balance
                # TODO: Alert on unknown platform errors (THR-XXX)

        return combined_balances

    def execute_trade(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a trade on the appropriate platform based on the asset pair.

        - Crypto (BTC, ETH) trades are routed to Coinbase.
        - Forex (e.g., EUR_USD) trades are routed to Oanda.
        """
        # Standardize the asset pair before routing to avoid misclassification
        raw_pair = decision.get("asset_pair", "")
        asset_pair = standardize_asset_pair(raw_pair)

        # Classify asset and route to appropriate platform
        asset_class = classify_asset_pair(asset_pair)

        target_platform_name = self._resolve_target_platform_name(asset_class)
        target_platform = self.platforms.get(target_platform_name) if target_platform_name else None

        if target_platform:
            logger.info(
                "Routing trade for %s to %s",
                asset_pair,
                target_platform_name or target_platform.__class__.__name__,
            )
            # Ensure a circuit breaker is present; lazily attach if missing
            cb = (
                target_platform.get_execute_breaker()
                if hasattr(target_platform, "get_execute_breaker")
                else None
            )
            if cb is None:
                breaker_config = self.config.get("platform_execute_circuit_breaker", {})
                failure_threshold = int(breaker_config.get("failure_threshold", 5))
                recovery_timeout = float(
                    breaker_config.get("recovery_timeout_seconds", 15)
                )
                cb = CircuitBreaker(
                    failure_threshold=failure_threshold,
                    recovery_timeout=recovery_timeout,
                    name=f"execute_trade:{target_platform.__class__.__name__.lower()}",
                )
                if getattr(target_platform, "set_execute_breaker", None):
                    target_platform.set_execute_breaker(cb)
                else:
                    setattr(target_platform, "_execute_breaker", cb)

            # Use breaker for sync execution path
            result = cb.call_sync(target_platform.execute_trade, decision)
            # Emit circuit breaker state metric (low cardinality)
            try:
                from finance_feedback_engine.monitoring.prometheus import (
                    update_circuit_breaker_state,
                )
                from finance_feedback_engine.utils.circuit_breaker import CircuitState

                state_map = {
                    CircuitState.CLOSED.value: 0,
                    CircuitState.OPEN.value: 1,
                    CircuitState.HALF_OPEN.value: 2,
                }
                update_circuit_breaker_state(
                    service=target_platform.__class__.__name__.lower(),
                    state=state_map.get(cb.state.value, 0),
                )
            except Exception:
                pass
            return result
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
            except ConnectionError as e:
                logger.error(
                    "Connection error fetching active positions from platform",
                    extra={
                        "platform": name,
                        "platform_class": platform_instance.__class__.__name__,
                        "error": str(e),
                        "error_type": "connection"
                    },
                    exc_info=True
                )
                # Continue with other platforms - fail-safe mode
                # TODO: Alert when position fetching fails (THR-XXX)
            except (ValueError, TypeError, KeyError) as e:
                logger.error(
                    "Data validation error fetching active positions",
                    extra={
                        "platform": name,
                        "platform_class": platform_instance.__class__.__name__,
                        "error": str(e),
                        "error_type": "validation"
                    }
                )
                # Continue with other platforms
                # TODO: Track validation errors for platform health (THR-XXX)
            except Exception as e:
                logger.error(
                    "Unexpected error fetching active positions from platform",
                    extra={
                        "platform": name,
                        "platform_class": platform_instance.__class__.__name__,
                        "error": str(e),
                        "error_type": type(e).__name__
                    },
                    exc_info=True
                )
                # Continue with other platforms - fail-safe mode
                # TODO: Alert on unknown platform errors (THR-XXX)
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
        futures_value_usd = 0
        spot_value_usd = 0

        platform_breakdowns = {}

        for name, platform in self._iter_portfolio_telemetry_platforms():
            try:
                breakdown = platform.get_portfolio_breakdown()
                platform_breakdowns[name] = breakdown

                total_value_usd += breakdown.get("total_value_usd", 0)
                # Capture unrealized P&L if the platform exposes it
                total_unrealized += breakdown.get("unrealized_pnl", 0.0)
                
                # Aggregate futures and spot values for position sizing
                futures_value_usd += breakdown.get("futures_value_usd", 0)
                spot_value_usd += breakdown.get("spot_value_usd", 0)

                # Capture cash/balance if provided by the platform
                bal = breakdown.get("balance") or breakdown.get("total_balance_usd")
                if bal is not None:
                    try:
                        cash_balances[name] = float(bal)
                    except (ValueError, TypeError):  # More specific exception
                        cash_balances[name] = 0.0

                # Add platform prefix to holdings
                holdings = breakdown.get("holdings", [])
                for holding in holdings:
                    holding["platform"] = name
                all_holdings.extend(holdings)

                num_assets += breakdown.get("num_assets", 0)

            except (ValueError, TypeError, KeyError, AttributeError) as e:
                # Added AttributeError for None returns
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

        return self._attach_active_platform_metadata({
            "total_value_usd": total_value_usd,
            "futures_value_usd": futures_value_usd,
            "spot_value_usd": spot_value_usd,
            "cash_balance_usd": cash_balance_usd,
            "per_platform_cash": cash_balances,
            "num_assets": num_assets,
            "holdings": all_holdings,
            "platform_breakdowns": platform_breakdowns,
            "unrealized_pnl": total_unrealized,
        })

    async def aget_portfolio_breakdown(self) -> Dict[str, Any]:
        """
        Async version of get_portfolio_breakdown.
        
        Get a combined portfolio breakdown from all platforms by running calls concurrently.
        Merges portfolio data from Coinbase (futures) and Oanda (forex).
        """
        import asyncio
        from typing import List, Coroutine
        
        async def _get_platform_breakdown(name: str, platform) -> Dict[str, Any]:
            """Wrapper to handle async/sync calls and exceptions for a single platform."""
            try:
                if hasattr(platform, 'aget_portfolio_breakdown'):
                    return await platform.aget_portfolio_breakdown()
                else:
                    # Run blocking sync call in a separate thread to avoid blocking event loop
                    loop = asyncio.get_running_loop()
                    return await loop.run_in_executor(None, platform.get_portfolio_breakdown)
            except (ValueError, TypeError, KeyError, AttributeError) as e:
                # Added AttributeError and return empty dict on failure
                logger.error("Failed to get portfolio breakdown from %s: %s", name, e)
                return {}

        # Create a list of concurrent tasks
        tasks: List[Coroutine] = [
            _get_platform_breakdown(name, platform)
            for name, platform in self._iter_portfolio_telemetry_platforms()
        ]

        # Run all tasks in parallel
        results = await asyncio.gather(*tasks)

        # --- Aggregation Logic ---
        total_value_usd = 0
        total_unrealized = 0.0
        all_holdings = []
        num_assets = 0
        cash_balances = {}
        futures_value_usd = 0
        spot_value_usd = 0
        platform_breakdowns = {}
        platform_names = [name for name, _ in self._iter_portfolio_telemetry_platforms()]

        for i, breakdown in enumerate(results):
            name = platform_names[i]
            if not breakdown:  # Skip failed or empty results
                continue

            platform_breakdowns[name] = breakdown

            total_value_usd += breakdown.get("total_value_usd", 0)
            total_unrealized += breakdown.get("unrealized_pnl", 0.0)
            futures_value_usd += breakdown.get("futures_value_usd", 0)
            spot_value_usd += breakdown.get("spot_value_usd", 0)

            bal = breakdown.get("balance") or breakdown.get("total_balance_usd")
            if bal is not None:
                try:
                    cash_balances[name] = float(bal)
                except (ValueError, TypeError):  # More specific exception
                    cash_balances[name] = 0.0

            holdings = breakdown.get("holdings", [])
            for holding in holdings:
                holding["platform"] = name
            all_holdings.extend(holdings)

            num_assets += breakdown.get("num_assets", 0)

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

        return self._attach_active_platform_metadata({
            "total_value_usd": total_value_usd,
            "futures_value_usd": futures_value_usd,
            "spot_value_usd": spot_value_usd,
            "cash_balance_usd": cash_balance_usd,
            "per_platform_cash": cash_balances,
            "num_assets": num_assets,
            "holdings": all_holdings,
            "platform_breakdowns": platform_breakdowns,
            "unrealized_pnl": total_unrealized,
        })

    def update_position_prices(self, price_updates: Dict[str, float]) -> None:
        """Forward mark-to-market updates to sub-platforms, especially paper/mock."""
        for name, platform in self.platforms.items():
            try:
                platform.update_position_prices(price_updates)
            except Exception as e:
                logger.debug(
                    "Failed MTM price update for %s platform: %s",
                    name,
                    e,
                    exc_info=True,
                )

    def test_connection(self) -> Dict[str, bool]:
        """
        Test connectivity across all configured platforms.

        Returns:
            Dictionary with aggregated validation results from all platforms.
            Will return True for each check if ANY platform passes it.
        """
        aggregated_results = {
            "api_auth": False,
            "account_active": False,
            "trading_enabled": False,
            "balance_available": False,
            "market_data_access": False,
        }

        platform_results = {}

        for name, platform in self.platforms.items():
            try:
                logger.info("Testing connection for %s platform", name)
                result = platform.test_connection()
                platform_results[name] = result

                # Aggregate: if ANY platform succeeds for a check, mark it as True
                for key in aggregated_results:
                    if result.get(key, False):
                        aggregated_results[key] = True

            except Exception as e:
                logger.error("Failed to test connection for %s: %s", name, e)
                platform_results[name] = {
                    "error": str(e),
                    "api_auth": False,
                    "account_active": False,
                    "trading_enabled": False,
                    "balance_available": False,
                    "market_data_access": False,
                }

        if not platform_results:
            raise ValueError("No platforms available to test connection")

        # Log per-platform results for debugging
        logger.info("Platform connection test results: %s", platform_results)

        return aggregated_results
