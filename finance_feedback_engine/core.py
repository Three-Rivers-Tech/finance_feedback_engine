"""Core Finance Feedback Engine module."""

import asyncio
import json
import logging
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional


from .data_providers.alpha_vantage_provider import AlphaVantageProvider
from .data_providers.historical_data_provider import HistoricalDataProvider
from .decision_engine.engine import DecisionEngine
from .decision_engine.policy_actions import get_legacy_action_compatibility, is_policy_action
from .exceptions import (
    ConfigurationError,
    FFEMemoryError,
    InsufficientProvidersError,
    ModelInstallationError,
)
from .memory.portfolio_memory_adapter import PortfolioMemoryEngineAdapter
from .monitoring.error_tracking import ErrorTracker
from .monitoring.trade_outcome_recorder import TradeOutcomeRecorder
from .observability.metrics import create_counters, get_meter
from .persistence.decision_store import DecisionStore
from .config.provider_credentials import resolve_provider_credentials
from .security.validator import validate_at_startup
from .trading_platforms.platform_factory import PlatformFactory
from .utils.credential_validator import validate_credentials
from .utils.config_schema_validator import validate_and_warn
from .utils.cache_metrics import CacheMetrics
from .utils.circuit_breaker import CircuitBreaker
from .utils.failure_logger import log_quorum_failure
from .utils.model_installer import ensure_models_installed
from .utils.versioning import get_version_info

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    pass


class FinanceFeedbackEngine:
    """
    Main engine for managing trading decisions with AI feedback.

    This engine coordinates between:
    - Data providers (Alpha Vantage)
    - Trading platforms (Coinbase, Oanda, etc.)
    - Decision engine (AI-powered)
    - Persistence layer
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the Finance Feedback Engine.

        Args:
            config: Configuration dictionary containing:
                - alpha_vantage_api_key: API key for Alpha Vantage
                - trading_platform: Platform name (e.g., 'coinbase', 'oanda')
                - platform_credentials: Platform-specific credentials
                - decision_engine: Decision engine configuration
                - persistence: Persistence configuration
        """
        # TODO(non-blocking): Coinbase-only runtime is healthy, but Oanda startup/init noise still leaks through
        # some legacy unified/dual-portfolio paths. Clean this up at the source when refactoring active platform
        # modeling so disabled providers/platforms cannot be observed by downstream startup, risk, or portfolio code.
        # Run security validation at startup (warns on plaintext credentials)
        config_path = Path(__file__).parent.parent / "config" / "config.yaml"
        validate_at_startup(config_path, raise_on_error=False)

        # Validate credentials (fail fast on placeholder values)
        validate_credentials(config)

        # Validate config schema (warns on misconfigurations)
        validate_and_warn(config)

        self.config = config

        version_info = get_version_info()
        logger.info(
            "Finance Feedback Engine starting | version=%s sha=%s describe=%s branch=%s",
            version_info.get("version"),
            version_info.get("git_sha"),
            version_info.get("git_describe"),
            version_info.get("git_branch"),
        )

        # Initialize error tracking (Phase 2.1)
        self.error_tracker = ErrorTracker(config.get("error_tracking", {}))

        # Portfolio caching infrastructure (Phase 2 optimization)
        self._portfolio_cache = None
        self._portfolio_cache_time = None
        self._portfolio_cache_ttl = 60  # 60 seconds
        self._cache_metrics = CacheMetrics()  # Track cache performance
        # Keep last known-good consolidated balance snapshot to avoid temporary
        # balance context loss during transient upstream issues.
        self._last_good_balance: Dict[str, float] = {}
        self._last_balance_telemetry: Dict[str, Any] = {
            "balance_source": None,
            "used_cached_balance": False,
            "balance_total": None,
            "balance_keys": [],
            "updated_at": None,
        }

        # Ensure Ollama models are installed (one-time setup)
        try:
            logger.info("Checking Ollama model installation...")
            ensure_models_installed()
        except ModelInstallationError as e:
            logger.warning(f"Model installation check failed: {e}")
            # Continue anyway - system may work with fewer models
        except (ImportError, RuntimeError, OSError) as e:
            logger.warning(f"Error during model installation check: {e}", exc_info=True)
            # Continue anyway - system may work with fewer models
        except Exception as e:
            logger.warning(
                f"Unexpected error during model installation check: {e}", exc_info=True
            )
            # Continue anyway - system may work with fewer models

        # Initialize data provider
        api_key = os.environ.get("ALPHA_VANTAGE_API_KEY") or config.get(
            "alpha_vantage_api_key"
        )
        # Detect if running in backtest mode (default: False for live trading safety)
        is_backtest = config.get("is_backtest", False)
        self.data_provider = AlphaVantageProvider(
            api_key=api_key, config=config, is_backtest=is_backtest
        )

        # Initialize historical data provider for backtesting
        self.historical_data_provider = HistoricalDataProvider(api_key=api_key)

        # Initialize unified data provider for real-time platform price monitoring
        # This provides real-time price data from Coinbase/Oanda for validation
        # against potentially stale Alpha Vantage data (THR-22 fix)
        from .data_providers.unified_data_provider import UnifiedDataProvider

        # Resolve provider credentials from multiple config layouts.
        # This codebase supports both legacy flat config and newer nested layouts
        # (providers/platforms sections). If we miss Oanda credentials here,
        # UnifiedDataProvider cannot initialize Oanda and forex price lookups
        # silently fall back to stale non-exchange data.
        provider_credentials = resolve_provider_credentials(config)
        enabled_platforms = {str(name).lower() for name in (config.get("enabled_platforms") or [])}
        agent_cfg = config.get("agent") or {}
        asset_pairs = [str(p).upper() for p in (agent_cfg.get("asset_pairs") or [])]
        crypto_markers = ("BTC", "ETH", "SOL", "DOGE", "ADA", "DOT", "LINK")
        fiat_markers = ("EUR", "GBP", "JPY", "CHF", "AUD", "NZD", "CAD")
        crypto_only_runtime = bool(asset_pairs) and all(
            any(sym in pair for sym in crypto_markers) and not any(code in pair for code in fiat_markers)
            for pair in asset_pairs
        )
        coinbase_credentials = provider_credentials.coinbase
        oanda_credentials = provider_credentials.oanda
        if crypto_only_runtime and enabled_platforms and 'oanda' not in enabled_platforms:
            oanda_credentials = None

        self.unified_provider = UnifiedDataProvider(
            alpha_vantage_api_key=api_key,
            coinbase_credentials=coinbase_credentials,
            oanda_credentials=oanda_credentials,
            config=config,
            cache_ttl=120,  # 2-minute cache for real-time price monitoring
        )
        logger.info("Unified data provider initialized for real-time price monitoring")

        # Initialize trading platform (skip in backtest mode)
        platform_name = config.get("trading_platform", "coinbase")

        paper_defaults = (config.get("paper_trading_defaults") or {})
        paper_enabled = bool(paper_defaults.get("enabled"))
        try:
            paper_initial_cash = float(paper_defaults.get("initial_cash_usd", 10000.0))
        except (ValueError, TypeError) as e:
            logger.warning(
                f"Invalid paper_initial_cash value, using default 10000.0: {e}",
                extra={"config_value": paper_defaults.get("initial_cash_usd")}
            )
            paper_initial_cash = 10000.0

        # Initialize Delta Lake integration (if enabled)
        delta_lake_config = config.get("delta_lake", {})
        if delta_lake_config.get("enabled", False):
            try:
                from finance_feedback_engine.pipelines.storage.delta_lake_manager import (
                    DeltaLakeManager,
                )

                self.delta_lake = DeltaLakeManager(
                    storage_path=delta_lake_config.get("storage_path", "./delta_lake"),
                    table_prefix=delta_lake_config.get("table_prefix", "ffe"),
                )
                logger.info("Delta Lake integration enabled")
            except ImportError:
                logger.warning("Delta Lake not available, skipping integration")
                self.delta_lake = None
        else:
            self.delta_lake = None
            logger.debug("Delta Lake integration disabled")

        # Handle unified/multi-platform mode (skip if backtesting)
        if not is_backtest and platform_name.lower() == "unified":
            # Convert platforms list to unified credentials format
            platforms_list = config.get("platforms", [])

            def _build_paper_balance(cash: float) -> Dict[str, float]:
                cash = float(cash)
                return {
                    "FUTURES_USD": round(cash * 0.6, 2),
                    "SPOT_USD": round(cash * 0.3, 2),
                    "SPOT_USDC": round(cash * 0.1, 2),
                }

            def _is_placeholder(value: Any) -> bool:
                return isinstance(value, str) and value.startswith("YOUR_")

            # Transform platforms list into nested dict format
            unified_credentials = {}
            for platform_config in platforms_list:
                # Validate platform config structure
                if not isinstance(platform_config, dict):
                    logger.warning(
                        f"Skipping invalid platform config (not a dict): "
                        f"{platform_config}"
                    )
                    continue

                platform_key = platform_config.get("name", "").lower()
                platform_creds = platform_config.get("credentials", {})

                # Validate name is non-empty string
                if not platform_key or not isinstance(platform_key, str):
                    logger.warning(
                        f"Skipping platform config with invalid/missing "
                        f"'name': {platform_config}"
                    )
                    continue

                # Validate credentials is a dict
                if not isinstance(platform_creds, dict):
                    logger.warning(
                        f"Skipping platform '{platform_key}' with invalid "
                        f"'credentials' (expected dict, got "
                        f"{type(platform_creds).__name__})"
                    )
                    continue

                # Normalize key names (coinbase_advanced -> coinbase)
                if platform_key in ["coinbase", "coinbase_advanced"]:
                    if paper_enabled and (
                        not platform_creds
                        or any(_is_placeholder(v) for v in platform_creds.values())
                    ):
                        logger.info(
                            "Skipping coinbase platform in sandbox mode (missing or placeholder credentials)."
                        )
                        continue
                    unified_credentials["coinbase"] = platform_creds
                elif platform_key == "oanda":
                    if (crypto_only_runtime and enabled_platforms and 'oanda' not in enabled_platforms) or (
                        paper_enabled and (
                            not platform_creds
                            or any(_is_placeholder(v) for v in platform_creds.values())
                        )
                    ):
                        logger.info(
                            "Skipping oanda platform in crypto-only or sandbox mode (missing, placeholder, or disabled credentials)."
                        )
                        continue
                    unified_credentials["oanda"] = platform_creds
                elif platform_key in ["mock", "paper", "sandbox"]:
                    # Paper/sandbox mode for unified platform
                    paper_creds = dict(platform_creds)
                    if "initial_balance" not in paper_creds:
                        paper_creds["initial_balance"] = _build_paper_balance(
                            paper_initial_cash
                        )
                    unified_credentials["paper"] = paper_creds
                else:
                    logger.warning(
                        f"Unknown platform in unified config: {platform_key}"
                    )

            # If no explicit platforms were provided, fall back to paper-trading defaults
            if not unified_credentials and paper_enabled:
                unified_credentials["paper"] = {
                    "initial_balance": _build_paper_balance(paper_initial_cash)
                }

            # Priority 2: Auto-enable paper in development when no platforms configured
            if not unified_credentials and os.environ.get("ENVIRONMENT", "").lower() == "development":
                logger.info("Development environment detected with no platforms; auto-enabling paper trading")
                unified_credentials["paper"] = {
                    "initial_balance": _build_paper_balance(paper_initial_cash)
                }

            # Ensure we have at least one valid platform configured
            if not unified_credentials:
                logger.error(
                    "No valid platforms configured in 'platforms' list. "
                    "Each platform must have 'name' (string) and "
                    "'credentials' (dict). "
                    f"Received: {platforms_list}"
                )
                raise ValueError(
                    "Unified platform mode requires at least one valid "
                    "platform with 'name' and 'credentials'"
                )

            platform_credentials = unified_credentials
        else:
            # Single platform mode (legacy)
            platform_credentials = config.get("platform_credentials", {})

        if not is_backtest:
            try:
                self.trading_platform = PlatformFactory.create_platform(
                    platform_name, platform_credentials, config
                )
                logger.info(
                    f"✅ Trading platform '{platform_name}' initialized successfully"
                )
            except (ValueError, KeyError, TypeError) as e:
                error_msg = str(e).lower()
                if (
                    "pem" in error_msg
                    or "credential" in error_msg
                    or "api key" in error_msg
                ):
                    logger.warning(
                        f"⚠️  Platform credentials incomplete or invalid: {e}\n"
                        f"💡 Trading and monitoring features will be limited.\n"
                        f"   Set valid credentials via environment variables or config/config.local.yaml"
                    )
                    # Use mock platform as fallback for analysis-only mode
                    from .trading_platforms.mock_platform import MockTradingPlatform

                    self.trading_platform = MockTradingPlatform({})
                    logger.info("📊 Running in analysis-only mode (mock platform)")
                else:
                    logger.error(
                        f"Failed to create trading platform {platform_name}: {e}",
                        exc_info=True,
                    )
                    raise ConfigurationError(
                        f"Platform configuration error: {e}"
                    ) from e
            except Exception as e:
                logger.error(
                    f"Failed to create trading platform {platform_name}: {e}",
                    exc_info=True,
                )
                raise ConfigurationError(f"Platform configuration error: {e}") from e
        else:
            # Backtest mode: do not initialize a live trading platform
            self.trading_platform = None
            logger.info(
                "Backtest mode detected: skipping live trading platform initialization"
            )

        # Initialize decision engine
        self.decision_engine = DecisionEngine(config, self.data_provider)

        # Backward-compatible alias used by trading loop and execution revalidation paths.
        # DecisionEngine stores this as `position_sizing_calc`.
        self.position_sizing_calculator = getattr(
            self.decision_engine, "position_sizing_calc", None
        )

        # Initialize persistence
        persistence_config = config.get("persistence", {})
        self.decision_store = DecisionStore(persistence_config)

        execution_cb_config = config.get("platform_execute_circuit_breaker", {})
        self._execution_breaker = CircuitBreaker(
            failure_threshold=int(execution_cb_config.get("failure_threshold", 5)),
            recovery_timeout=float(execution_cb_config.get("recovery_timeout_seconds", 15)),
            name="finance_feedback_engine.execute_decision",
        )

        # Initialize Prometheus metrics
        self._meter = get_meter(__name__)
        self._metrics = create_counters(self._meter)
        logger.info("Prometheus metrics initialized")

        # Initialize portfolio memory engine
        memory_enabled = config.get("portfolio_memory", {}).get("enabled", False)
        self.memory_engine: Optional[PortfolioMemoryEngineAdapter] = None
        if memory_enabled:
            # Auto-load persisted memory if exists
            memory_path = "data/memory/portfolio_memory.json"
            if os.path.exists(memory_path):
                try:
                    self.memory_engine = PortfolioMemoryEngineAdapter.load_from_disk(
                        memory_path
                    )
                    logger.info(f"Loaded portfolio memory from {memory_path} (using new adapter)")
                except (FileNotFoundError, PermissionError) as e:
                    logger.warning(
                        f"Failed to load portfolio memory: {e}, starting fresh"
                    )
                    self.memory_engine = PortfolioMemoryEngineAdapter(config)
                except FFEMemoryError as e:
                    logger.warning(
                        f"Failed to load portfolio memory due to memory error: {e}, starting fresh"
                    )
                    self.memory_engine = PortfolioMemoryEngineAdapter(config)
                except (OSError, IOError) as e:
                    logger.warning(
                        f"IO error loading portfolio memory: {e}, starting fresh",
                        exc_info=True,
                    )
                    self.memory_engine = PortfolioMemoryEngineAdapter(config)
                except Exception as e:
                    logger.warning(
                        f"Unexpected error loading portfolio memory: {e}, starting fresh",
                        exc_info=True,
                    )
                    self.memory_engine = PortfolioMemoryEngineAdapter(config)
            else:
                self.memory_engine = PortfolioMemoryEngineAdapter(config)
                logger.info("No persisted memory found, starting fresh (using new adapter)")

            logger.info("Portfolio Memory Engine enabled")

        # Backward-compatible alias expected by legacy callers/tests
        self.portfolio_memory = self.memory_engine

        # Initialize trade outcome recorder (THR-235)
        self.trade_outcome_recorder: Optional[TradeOutcomeRecorder] = None
        self.order_status_worker = None
        outcome_recording_enabled = config.get("trade_outcome_recording", {}).get("enabled", True)
        if outcome_recording_enabled and not is_backtest:
            try:
                self.trade_outcome_recorder = TradeOutcomeRecorder(
                    data_dir="data",
                    unified_provider=self.unified_provider
                )
                logger.info("Trade Outcome Recorder initialized with unified data provider")
                
                # Initialize order status worker (THR-236)
                from .monitoring.order_status_worker import OrderStatusWorker
                
                self.order_status_worker = OrderStatusWorker(
                    trading_platform=self.trading_platform,
                    outcome_recorder=self.trade_outcome_recorder,
                    data_dir="data",
                    poll_interval=30,
                )
                # Start the background worker
                self.order_status_worker.start()
                logger.info("Order Status Worker initialized and started")
            except Exception as e:
                logger.warning(f"Failed to initialize Trade Outcome Recorder: {e}")
                self.trade_outcome_recorder = None
                self.order_status_worker = None

        # Initialize monitoring context provider (lazy init)
        self.monitoring_provider = None
        self.trade_monitor = None
        self._monitoring_enabled = config.get("monitoring", {}).get(
            "enable_context_integration", True
        )
        self._auto_start_monitor_flag = config.get("monitoring", {}).get(
            "enabled", False
        )
        self._monitor_manual_cli = config.get("monitoring", {}).get("manual_cli", False)
        self._monitor_pulse_interval = config.get("monitoring", {}).get(
            "pulse_interval_seconds", 300
        )

        # In backtest mode, force-disable monitoring and trade monitor startup
        if is_backtest:
            self._monitoring_enabled = False
            self._auto_start_monitor_flag = False
            logger.info(
                "Backtest mode: monitoring integration and TradeMonitor auto-start are disabled"
            )
        else:
            # Auto-enable monitoring integration if enabled in config
            if self._monitoring_enabled:
                self._auto_enable_monitoring()
            # Optionally start internal TradeMonitor (no direct CLI control)
            if self._auto_start_monitor_flag:
                self._auto_start_trade_monitor()

        logger.info("Finance Feedback Engine initialized successfully")

        # Run startup health checks
        self._run_startup_health_checks()


    def _load_decision_for_execution(self, decision_id: str) -> tuple[Optional[Dict[str, Any]], str]:
        """Load a decision from the canonical store, with a small legacy fallback."""
        decision = self.decision_store.get_decision_by_id(decision_id)
        if decision:
            return decision, "store"

        legacy_candidates = [
            self.decision_store.storage_path / f"{decision_id}.json",
            self.decision_store.storage_path.parent / f"{decision_id}.json",
        ]
        for candidate in legacy_candidates:
            if candidate.exists():
                try:
                    return json.loads(candidate.read_text()), "legacy-file"
                except Exception as e:
                    raise ValueError(f"Failed to load decision {decision_id}: {e}") from e

        return None, "missing"

    def _prepare_execution_decision(self, decision_id: str, decision: Dict[str, Any]) -> Dict[str, Any]:
        prepared = dict(decision)
        prepared.setdefault("id", decision_id)
        prepared.setdefault("timestamp", datetime.now(UTC).isoformat())
        if prepared.get("policy_action") and not prepared.get("action"):
            prepared["action"] = self._normalize_execution_action(prepared)

        market_data = prepared.get("market_data") or {}
        if prepared.get("entry_price") is None:
            close_price = market_data.get("close")
            if isinstance(close_price, (int, float)) and close_price > 0:
                prepared["entry_price"] = float(close_price)

        if prepared.get("recommended_position_size") is None:
            if prepared.get("position_size") is not None:
                prepared["recommended_position_size"] = prepared.get("position_size")
            elif prepared.get("current_position_size") is not None:
                prepared["recommended_position_size"] = prepared.get("current_position_size")

        normalized_action = self._normalize_execution_action(prepared)
        current_amount = prepared.get("suggested_amount")
        needs_backfill = current_amount is None
        if normalized_action in {"BUY", "SELL"}:
            try:
                needs_backfill = needs_backfill or float(current_amount) <= 0
            except (TypeError, ValueError):
                needs_backfill = True

        if needs_backfill:
            if prepared.get("amount") is not None:
                prepared["suggested_amount"] = prepared.get("amount")
            else:
                size = prepared.get("recommended_position_size")
                price = prepared.get("entry_price")
                try:
                    if size is not None and price is not None:
                        prepared["suggested_amount"] = float(size) * float(price)
                except (TypeError, ValueError):
                    pass

        return prepared


    @staticmethod
    def _normalize_execution_action(decision: Dict[str, Any]) -> str:
        raw_action = decision.get("policy_action") or decision.get("action") or "HOLD"
        if is_policy_action(raw_action):
            return get_legacy_action_compatibility(raw_action) or "HOLD"
        return str(raw_action).upper()

    def _validate_execution_decision(self, decision: Dict[str, Any]) -> List[str]:
        errors: List[str] = []
        action = self._normalize_execution_action(decision)
        if action not in {"BUY", "SELL", "HOLD"}:
            errors.append(f"Invalid action '{action}'")

        try:
            confidence = int(decision.get("confidence", -1))
            if not 0 <= confidence <= 100:
                errors.append(f"Confidence {confidence} out of range [0, 100]")
        except (TypeError, ValueError) as e:
            errors.append(f"Invalid confidence value: {e}")

        if action in {"BUY", "SELL"}:
            amount = decision.get("suggested_amount")
            try:
                if amount is None or float(amount) <= 0:
                    errors.append("Decision missing positive suggested_amount")
            except (TypeError, ValueError):
                errors.append("Decision missing positive suggested_amount")

        return errors

    def execute_decision(
        self, decision_id: str, modified_decision: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Backward-compatible execution entrypoint used by CLI/bot/test paths."""
        source = "modified"
        if modified_decision is not None:
            decision = dict(modified_decision)
        else:
            decision, source = self._load_decision_for_execution(decision_id)
            if decision is None:
                raise ValueError(f"Decision {decision_id} not found")

        decision = self._prepare_execution_decision(decision_id, decision)
        errors = self._validate_execution_decision(decision)
        if errors:
            message = "; ".join(errors)
            if source == "store":
                logger.warning("Decision %s failed execution validation: %s", decision_id, message)
                return {"success": False, "decision_id": decision_id, "message": message, "error": message}
            raise ValueError(message)

        if self.trading_platform is None:
            raise RuntimeError("Trading platform is not initialized")

        result = self._execution_breaker.call_sync(self.trading_platform.execute_trade, decision)
        decision["execution_result"] = result
        decision["executed_at"] = datetime.now(UTC).isoformat()
        if decision.get("policy_action") and not decision.get("action"):
            decision["action"] = self._normalize_execution_action(decision)
        if result.get("execution_price") and not decision.get("entry_price"):
            decision["entry_price"] = result.get("execution_price")

        if source in {"store", "modified"}:
            try:
                self.decision_store.update_decision(decision)
            except Exception:
                logger.exception("Failed to persist execution result for decision %s", decision_id)

        return result

    async def execute_decision_async(
        self, decision_id: str, modified_decision: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Async execution entrypoint used by autonomous agent execution paths."""
        source = "modified"
        if modified_decision is not None:
            decision = dict(modified_decision)
        else:
            decision, source = self._load_decision_for_execution(decision_id)
            if decision is None:
                raise ValueError(f"Decision {decision_id} not found")

        decision = self._prepare_execution_decision(decision_id, decision)
        errors = self._validate_execution_decision(decision)
        if errors:
            message = "; ".join(errors)
            if source == "store":
                logger.warning("Decision %s failed async execution validation: %s", decision_id, message)
                return {"success": False, "decision_id": decision_id, "message": message, "error": message}
            raise ValueError(message)

        if self.trading_platform is None:
            raise RuntimeError("Trading platform is not initialized")

        async_execute = getattr(self.trading_platform, "aexecute_trade", None)
        if async_execute is None:
            async_execute = getattr(self.trading_platform, "aexecute", None)
        if async_execute is None:
            logger.info("Trading platform has no async execution hook; falling back to sync execute_trade for %s", decision_id)
            return await asyncio.to_thread(
                self.execute_decision, decision_id, modified_decision
            )

        result = await self._execution_breaker.call(async_execute, decision)
        decision["execution_result"] = result
        decision["executed_at"] = datetime.now(UTC).isoformat()
        if decision.get("policy_action") and not decision.get("action"):
            decision["action"] = self._normalize_execution_action(decision)
        if result.get("execution_price") and not decision.get("entry_price"):
            decision["entry_price"] = result.get("execution_price")

        if source in {"store", "modified"}:
            try:
                self.decision_store.update_decision(decision)
            except Exception:
                logger.exception("Failed to persist async execution result for decision %s", decision_id)

        return result

    def record_trade_outcome(
        self,
        decision_or_id: Any,
        exit_price: Optional[float] = None,
        exit_timestamp: Optional[str] = None,
        hit_stop_loss: bool = False,
        hit_take_profit: bool = False,
    ) -> Any:
        """Backward-compatible outcome recorder shim."""
        if not self.memory_engine:
            raise RuntimeError("Portfolio memory is not enabled")

        if isinstance(decision_or_id, str):
            decision, _ = self._load_decision_for_execution(decision_or_id)
            if decision is None:
                raise ValueError(f"Decision {decision_or_id} not found")
        else:
            decision = decision_or_id

        legacy_engine = getattr(self.memory_engine, "_legacy_engine", None)
        coordinator = getattr(self.memory_engine, "_coordinator", None)
        if legacy_engine is None:
            raise RuntimeError("Portfolio memory legacy engine unavailable")

        outcome = legacy_engine.record_trade_outcome(
            decision,
            exit_price=exit_price,
            exit_timestamp=exit_timestamp,
            hit_stop_loss=hit_stop_loss,
            hit_take_profit=hit_take_profit,
        )

        if coordinator is not None:
            coordinator.record_trade_outcome(outcome)
        else:
            self.memory_engine.record_trade_outcome(outcome)

        ensemble_metadata = (decision.get("ensemble_metadata") or {}) if isinstance(decision, dict) else {}
        provider_decisions = self._normalize_learning_provider_decisions(
            ensemble_metadata
        )
        ensemble_manager = getattr(self.decision_engine, "ensemble_manager", None)
        if provider_decisions and ensemble_manager and hasattr(ensemble_manager, "update_base_weights"):
            try:
                performance_metric = getattr(outcome, "pnl_percentage", None)
                if performance_metric is None:
                    performance_metric = getattr(outcome, "realized_pnl", 0.0)
                recovery_metadata = decision.get("recovery_metadata") or {}
                shadowed_from_decision_id = recovery_metadata.get(
                    "shadowed_from_decision_id"
                )
                logger.info(
                    "Adaptive learning handoff | decision_id=%s | ai_provider=%s | shadowed_from_decision_id=%s | provider_decisions=%s | actual_outcome=%s | performance_metric=%s",
                    getattr(outcome, "decision_id", decision.get("id", "unknown")),
                    decision.get("ai_provider"),
                    shadowed_from_decision_id,
                    sorted(provider_decisions.keys()),
                    str(getattr(outcome, "action", decision.get("action", "HOLD"))).upper(),
                    float(performance_metric or 0.0),
                )
                ensemble_manager.update_base_weights(
                    provider_decisions,
                    str(getattr(outcome, "action", decision.get("action", "HOLD"))).upper(),
                    float(performance_metric or 0.0),
                )
            except Exception:
                logger.exception("Failed to update ensemble weights for decision %s", getattr(outcome, "decision_id", "unknown"))

        return outcome

    @staticmethod
    def _normalize_learning_provider_decisions(
        ensemble_metadata: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Dict[str, Any]]]:
        """Normalize ensemble metadata into a dict suitable for the learning pipeline.

        When role_decisions are present (debate mode), return seat-keyed dict
        (bull/bear/judge) so adaptive learning tracks per-seat performance
        instead of per-model. This is critical when multiple seats use the
        same underlying model — model-keyed dicts collapse N seats into 1.

        Falls back to provider_decisions for non-debate (legacy) ensembles.
        """
        if not isinstance(ensemble_metadata, dict):
            return None

        # Prefer role_decisions (seat-keyed) for debate mode learning.
        # This avoids the single-model collapse problem where 3 seats using
        # the same model produce only 1 provider_decisions entry.
        role_decisions = ensemble_metadata.get("role_decisions")
        if isinstance(role_decisions, dict) and role_decisions:
            seat_decisions: Dict[str, Dict[str, Any]] = {}
            for role_name, role_decision in role_decisions.items():
                if not isinstance(role_decision, dict):
                    continue
                # Key by role (bull/bear/judge), strip the "role" field itself
                seat_decisions[str(role_name)] = {
                    key: value for key, value in role_decision.items() if key != "role"
                }
            if seat_decisions:
                return seat_decisions

        # Fallback: legacy provider-keyed decisions (non-debate ensembles)
        provider_decisions = ensemble_metadata.get("provider_decisions")
        if isinstance(provider_decisions, dict):
            normalized = {
                str(provider): details
                for provider, details in provider_decisions.items()
                if provider and isinstance(details, dict)
            }
            return normalized or None

        return None

    def _run_startup_health_checks(self):
        """
        Run health checks on data providers at startup.

        Verifies connectivity and basic functionality without blocking initialization.
        Logs warnings for any issues found.
        """
        logger.info("Running startup health checks...")

        health_check_results = {
            "alpha_vantage": False,
            "unified_provider": False,
            "trading_platform": False
        }

        # Check Alpha Vantage connectivity
        try:
            if self.data_provider:
                # Simple ping check - list available functions
                logger.debug("Checking Alpha Vantage provider health...")
                # The provider is initialized, assume healthy if no exception during init
                health_check_results["alpha_vantage"] = True
                logger.info("✓ Alpha Vantage provider: Healthy")
        except Exception as e:
            logger.warning(f"✗ Alpha Vantage provider health check failed: {e}")

        # Check Unified Data Provider connectivity
        try:
            if self.unified_provider:
                logger.debug("Checking Unified Data Provider health...")
                # Check if at least one provider is available
                has_provider = (
                    self.unified_provider.alpha_vantage is not None or
                    self.unified_provider.coinbase is not None or
                    self.unified_provider.oanda is not None
                )
                if has_provider:
                    health_check_results["unified_provider"] = True
                    logger.info("✓ Unified Data Provider: Healthy (at least 1 provider available)")
                else:
                    logger.warning("✗ Unified Data Provider: No providers initialized")
        except Exception as e:
            logger.warning(f"✗ Unified Data Provider health check failed: {e}")

        # Check Trading Platform connectivity (skip in backtest mode)
        try:
            if self.trading_platform and not self.config.get("is_backtest", False):
                logger.debug("Checking trading platform health...")
                # Check if platform has basic methods
                has_methods = (
                    hasattr(self.trading_platform, 'get_balance') and
                    hasattr(self.trading_platform, 'execute_trade')
                )
                if has_methods:
                    health_check_results["trading_platform"] = True
                    logger.info(f"✓ Trading platform ({self.config.get('trading_platform', 'unknown')}): Healthy")
                else:
                    logger.warning("✗ Trading platform: Missing required methods")
        except Exception as e:
            logger.warning(f"✗ Trading platform health check failed: {e}")

        # Summary
        healthy_count = sum(health_check_results.values())
        total_count = len([k for k, v in health_check_results.items() if k != "trading_platform" or not self.config.get("is_backtest", False)])

        if healthy_count == total_count:
            logger.info(f"✓ Startup health checks passed ({healthy_count}/{total_count})")
        else:
            logger.warning(
                f"⚠ Startup health checks: {healthy_count}/{total_count} healthy. "
                "Some providers may be unavailable."
            )

    def _auto_enable_monitoring(self):
        """Auto-enable monitoring integration with default settings."""
        try:
            from .monitoring import MonitoringContextProvider, TradeMetricsCollector

            # Create metrics collector
            metrics_collector = TradeMetricsCollector()

            # Create monitoring provider (no trade monitor needed for context)
            self.monitoring_provider = MonitoringContextProvider(
                platform=self.trading_platform,
                trade_monitor=None,  # Optional, can add later
                metrics_collector=metrics_collector,
            )

            # Attach to decision engine
            self.decision_engine.set_monitoring_context(self.monitoring_provider)

            logger.info(
                "Monitoring context auto-enabled - "
                "AI has position awareness by default"
            )
        except ImportError as e:
            logger.warning(
                f"Failed to enable monitoring context (import error): {e}"
            )
        except Exception as e:
            logger.error(
                f"Failed to enable monitoring context: {e}", exc_info=True
            )

    def validate_agent_readiness(self) -> tuple[bool, list[str]]:
        """
        Validate that all runtime dependencies are available before agent start.

        Performs comprehensive pre-flight checks including:
        - Ensemble provider configuration
        - Risk limit validation
        - Ollama connectivity (if local provider enabled)
        - Asset pair validation

        This method should be called by TradingLoopAgent before entering the OODA loop
        to ensure all preconditions are met for autonomous trading.

        Returns:
            tuple[bool, list[str]]: (is_ready, error_messages)
                - is_ready: True if all checks pass, False otherwise
                - error_messages: List of human-readable error messages (empty if ready)

        Example:
            >>> engine = FinanceFeedbackEngine(config)
            >>> is_ready, errors = engine.validate_agent_readiness()
            >>> if not is_ready:
            ...     for error in errors:
            ...         print(f"ERROR: {error}")
            ...     raise RuntimeError("Agent not ready for autonomous trading")
        """
        errors: List[str] = []

        # Check 1: Ensemble provider configuration
        ai_provider = self.config.get("decision_engine", {}).get("ai_provider", "local")
        if ai_provider == "ensemble":
            ensemble_config = self.config.get("ensemble", {})
            enabled_providers = ensemble_config.get("enabled_providers") or ensemble_config.get("providers", [])

            if not enabled_providers or len(enabled_providers) == 0:
                errors.append(
                    "Ensemble mode enabled but no providers configured. "
                    "Add at least one provider to config.ensemble.enabled_providers "
                    "(e.g., ['local', 'claude'])"
                )

            # Check 2: Ollama connectivity (if local provider enabled)
            if enabled_providers and "local" in enabled_providers:
                ollama_host = self.config.get("ollama", {}).get("host", "http://localhost:11434")
                try:
                    import socket
                    import urllib.parse

                    # Parse host URL to get hostname and port
                    parsed = urllib.parse.urlparse(ollama_host)
                    host = parsed.hostname or "localhost"
                    port = parsed.port or 11434

                    # Quick TCP connectivity check (don't make full HTTP request)
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(2.0)  # 2 second timeout
                    result = sock.connect_ex((host, port))
                    sock.close()

                    if result != 0:
                        errors.append(
                            f"Ollama not reachable at {ollama_host} (TCP connection failed). "
                            f"Ensure Ollama is running: 'docker start ollama' or 'ollama serve'. "
                            f"To disable local provider, remove 'local' from ensemble.enabled_providers"
                        )
                except Exception as e:
                    logger.debug(f"Ollama connectivity check failed with exception: {e}")
                    errors.append(
                        f"Failed to check Ollama connectivity at {ollama_host}: {e}. "
                        f"Ensure Ollama is accessible or remove 'local' from ensemble.enabled_providers"
                    )

        # Check 3: Risk limits validation
        agent_config = self.config.get("agent", {})
        max_drawdown = agent_config.get("max_drawdown_percent", 0.15)

        # Normalize percentage notation (15 -> 0.15)
        if max_drawdown > 1.0:
            max_drawdown = max_drawdown / 100.0

        if max_drawdown <= 0:
            errors.append(
                "max_drawdown_percent must be greater than 0 for risk management. "
                "Set config.agent.max_drawdown_percent to a reasonable value "
                "(e.g., 0.15 for 15% drawdown limit)"
            )

        # Check 4: Asset pairs validation (already handled by Pydantic validator in Phase 1)
        # This check is redundant with the model validator but provides runtime verification
        asset_pairs = agent_config.get("asset_pairs", [])
        autonomous_enabled = agent_config.get("autonomous", {}).get("enabled", False)
        require_notifications = agent_config.get("require_notifications_for_signal_only", True)
        is_signal_only = not autonomous_enabled and not require_notifications

        if not asset_pairs and not is_signal_only:
            errors.append(
                "No asset pairs configured and not in signal-only mode. "
                "Add at least one trading pair to config.agent.asset_pairs "
                "(e.g., ['BTCUSD', 'ETHUSD']) or enable signal-only mode"
            )

        # Phase 2 Pre-flight: Trading platform connectivity (lightweight)
        try:
            if hasattr(self, "trading_platform") and self.trading_platform:
                # Check for execute_trade (UnifiedTradingPlatform) or execute (legacy)
                has_execute = (
                    hasattr(self.trading_platform, "execute_trade")
                    or hasattr(self.trading_platform, "execute")
                )
                has_methods = (
                    hasattr(self.trading_platform, "get_balance")
                    and has_execute
                )
                if not has_methods:
                    errors.append(
                        "Trading platform missing required methods (get_balance/execute_trade). "
                        "Verify platform initialization and credentials."
                    )
        except Exception as e:
            logger.debug(f"Trading platform readiness check failed: {e}")
            errors.append(
                "Failed to verify trading platform readiness. Check credentials and connectivity."
            )

        # Phase 2 Pre-flight: Data provider credentials present
        # Only check for the Alpha Vantage key when the alpha_vantage provider is
        # explicitly configured in data_providers (i.e. the section exists), not
        # merely referenced as a default preference.  This mirrors the pattern used
        # for the Ollama check above, which is skipped unless "local" appears in the
        # ensemble provider list.
        try:
            data_providers_cfg = self.config.get("data_providers", {})
            alpha_vantage_explicitly_configured = (
                "alpha_vantage" in data_providers_cfg
                or "alpha_vantage_api_key" in self.config
            )
            if alpha_vantage_explicitly_configured:
                api_key = (
                    os.environ.get("ALPHA_VANTAGE_API_KEY")
                    or self.config.get("alpha_vantage_api_key")
                    or data_providers_cfg.get("alpha_vantage", {}).get("api_key")
                )
                if not api_key:
                    errors.append(
                        "Alpha Vantage API key missing. Set ALPHA_VANTAGE_API_KEY or configure in config.local.yaml."
                    )
        except Exception:
            # Non-fatal; init may succeed if alternative providers are wired later
            logger.debug("Alpha Vantage key readiness check failed", exc_info=True)

        # Return results
        is_ready = len(errors) == 0
        if is_ready:
            logger.info("✅ Agent readiness validation passed - all checks OK")
        else:
            logger.error(
                f"❌ Agent readiness validation failed with {len(errors)} error(s)"
            )
            for i, error in enumerate(errors, 1):
                logger.error(f"  {i}. {error}")

        return (is_ready, errors)

    def get_portfolio_breakdown(self) -> Dict[str, Any]:
        """Sync portfolio breakdown proxy to trading platform."""
        if not self.trading_platform:
            raise AttributeError("Trading platform is not initialized")
        if hasattr(self.trading_platform, "get_portfolio_breakdown"):
            return self.trading_platform.get_portfolio_breakdown()
        raise AttributeError(
            f"{type(self.trading_platform).__name__} does not implement portfolio breakdown"
        )

    async def get_portfolio_breakdown_async(self) -> Dict[str, Any]:
        """Async portfolio breakdown proxy with safe fallback.

        Prefer platform async API when available; otherwise run sync call in a thread.
        """
        if not self.trading_platform:
            raise AttributeError("Trading platform is not initialized")

        if hasattr(self.trading_platform, "aget_portfolio_breakdown"):
            return await self.trading_platform.aget_portfolio_breakdown()

        if hasattr(self.trading_platform, "get_portfolio_breakdown"):
            return await asyncio.to_thread(self.trading_platform.get_portfolio_breakdown)

        raise AttributeError(
            f"{type(self.trading_platform).__name__} does not implement portfolio breakdown"
        )

    def perform_health_check(self) -> tuple[bool, list[str]]:
        """
        Perform runtime health checks on critical systems.

        This method is called periodically during agent operation (every N decisions)
        to monitor system health and detect degradation. Unlike validate_agent_readiness(),
        which is a blocking pre-flight check, health_check() is soft monitoring that
        logs issues but doesn't interrupt agent operation.

        Checks Performed:
        1. Provider Availability: Verify at least one ensemble provider is responsive
        2. Decision Engine Responsiveness: Check AI provider connectivity (non-blocking)
        3. Trading Platform Connectivity: Verify platform API is reachable
        4. Circuit Breaker Status: Alert if any circuit is OPEN for >5 minutes

        Returns:
            tuple[bool, list[str]]: (is_healthy, issues)
                - is_healthy: True if all checks pass, False if issues detected
                - issues: List of health issues (empty if healthy)
                         Issues are informational (soft alerts) not blocking failures

        Example:
            >>> is_healthy, issues = engine.perform_health_check()
            >>> if not is_healthy:
            ...     logger.warning(f"Health issues detected: {issues}")
            ...     # Continue operation but monitor closely
        """
        issues: List[str] = []

        # Lazy init: track whether we've already performed Ollama failover
        if not hasattr(self, "_ollama_failover_active"):
            self._ollama_failover_active = False

        # Check 1: Provider Availability
        # Verify at least one ensemble provider is available
        try:
            enabled_providers = self.config.get("ensemble", {}).get("enabled_providers", [])
            if not enabled_providers:
                issues.append(
                    "No ensemble providers configured (should not happen - caught in pre-flight validation)"
                )
            else:
                # Check if any providers are available (non-blocking)
                # This is best-effort; don't fail if we can't verify all providers
                available_count = 0
                unavailable_providers = []
                local_unavailable = False

                for provider in enabled_providers:
                    if provider == "local":
                        # Quick TCP check for Ollama (2s timeout, non-blocking)
                        try:
                            import socket
                            import urllib.parse

                            ollama_host = self.config.get("ollama", {}).get("host", "http://localhost:11434")
                            parsed = urllib.parse.urlparse(ollama_host)
                            host = parsed.hostname or "localhost"
                            port = parsed.port or 11434

                            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            sock.settimeout(1.0)  # 1s for periodic check (faster than pre-flight)
                            result = sock.connect_ex((host, port))
                            sock.close()

                            if result == 0:
                                available_count += 1
                            else:
                                unavailable_providers.append(f"local (Ollama at {ollama_host})")
                                local_unavailable = True
                        except Exception as e:
                            unavailable_providers.append(f"local (connectivity check failed: {e})")
                            local_unavailable = True
                    else:
                        # Cloud provider (openai, anthropic, etc.) - assume available
                        # unless we have specific error tracking
                        available_count += 1

                if available_count == 0:
                    issues.append(
                        f"No ensemble providers available. Unavailable: {', '.join(unavailable_providers)}. "
                        f"Agent may switch to fallback or degrade gracefully."
                    )
                    if local_unavailable:
                        self._trigger_ollama_failover(unavailable_providers, issues)
                elif unavailable_providers and available_count < len(enabled_providers):
                    # Some providers available but some are down
                    logger.warning(
                        f"Partial provider availability: {available_count}/{len(enabled_providers)} available. "
                        f"Unavailable: {', '.join(unavailable_providers)}"
                    )
                    # This is a warning but not a critical issue (other providers available)
                    if local_unavailable:
                        self._trigger_ollama_failover(unavailable_providers, issues)
        except Exception as e:
            issues.append(
                f"Failed to check provider availability: {e}. "
                f"Falling back to manual provider management."
            )

        # Check 2: Decision Engine Responsiveness
        # Check if decision engine and its providers are accessible
        try:
            if hasattr(self, "decision_engine") and self.decision_engine:
                if hasattr(self.decision_engine, "circuit_breaker_stats"):
                    try:
                        cb_stats = self.decision_engine.circuit_breaker_stats()
                        self._collect_circuit_breaker_issues(
                            component="decision_engine",
                            stats=cb_stats,
                            issues=issues,
                        )
                    except Exception as e:
                        logger.debug(f"Failed to check circuit breaker stats: {e}")
        except Exception as e:
            logger.debug(f"Failed to check decision engine responsiveness: {e}")

        # Check 2b: Data provider circuit breaker status (if available)
        try:
            if hasattr(self, "data_provider") and hasattr(
                self.data_provider, "get_circuit_breaker_stats"
            ):
                dp_stats = self.data_provider.get_circuit_breaker_stats()
                self._collect_circuit_breaker_issues(
                    component="data_provider",
                    stats=dp_stats if dp_stats else {},
                    issues=issues,
                )
        except Exception as e:
            logger.debug(f"Failed to check data provider circuit breaker stats: {e}")

        # Check 3: Trading Platform Connectivity
        # Verify platform API is reachable
        try:
            if hasattr(self, "trading_platform") and self.trading_platform:
                platform_name = getattr(self.trading_platform, "name", "Unknown")
                # Check if platform has a health check method
                if hasattr(self.trading_platform, "health_check"):
                    try:
                        is_healthy, error_msg = self.trading_platform.health_check()
                        if not is_healthy:
                            issues.append(
                                f"Trading platform '{platform_name}' health check failed: {error_msg}. "
                                f"Orders may be temporarily unavailable."
                            )
                    except Exception as e:
                        logger.debug(f"Failed to call platform health check: {e}")
                # Circuit breaker stats on platforms (if implemented)
                if hasattr(self.trading_platform, "get_circuit_breaker_stats"):
                    try:
                        tp_stats = self.trading_platform.get_circuit_breaker_stats()
                        self._collect_circuit_breaker_issues(
                            component="trading_platform",
                            stats=tp_stats if tp_stats else {},
                            issues=issues,
                        )
                    except Exception as e:
                        logger.debug(f"Failed to fetch trading platform circuit stats: {e}")
                # Otherwise, assume platform is OK (no health check method)
        except Exception as e:
            logger.debug(f"Failed to check trading platform connectivity: {e}")

        # Check 4: Circuit Breaker Monitoring
        # Already handled in Check 2 above

        # Log results
        is_healthy = len(issues) == 0
        if is_healthy:
            logger.debug("✅ System health check passed - all systems nominal")
        else:
            logger.warning(
                f"⚠️  System health issues detected ({len(issues)} issue(s))"
            )
            for i, issue in enumerate(issues, 1):
                logger.warning(f"  {i}. {issue}")

        return (is_healthy, issues)

    def _collect_circuit_breaker_issues(
        self, component: str, stats: Dict[str, Any], issues: List[str]
    ) -> None:
        """Analyze circuit breaker stats and append any long-lived OPEN states."""
        if not isinstance(stats, dict):
            return

        now = time.time()
        for name, cb_stats in stats.items():
            state = cb_stats.get("state")
            if state == "OPEN":
                last_failure = cb_stats.get("last_failure_time") or now
                open_duration = now - last_failure
                if open_duration >= 300:  # 5 minutes
                    issues.append(
                        f"Circuit breaker '{component}:{name}' OPEN for {open_duration:.0f}s. "
                        "Service likely unavailable; consider failover or recovery actions."
                    )
            elif state == "HALF_OPEN":
                issues.append(
                    f"Circuit breaker '{component}:{name}' HALF_OPEN - monitoring recovery."
                )

    def _trigger_ollama_failover(
        self, unavailable_providers: List[str], issues: List[str]
    ) -> None:
        """Switch ensemble away from local provider when Ollama is unavailable."""
        if self._ollama_failover_active:
            return

        fallback_provider = self._select_fallback_provider(
            self.config.get("ensemble", {}).get("enabled_providers", [])
        )

        if not fallback_provider:
            issues.append(
                "Ollama unavailable and no cloud providers configured for failover."
            )
            return

        try:
            ensemble_manager = getattr(self.decision_engine, "ensemble_manager", None)
            if ensemble_manager and hasattr(ensemble_manager, "apply_failover"):
                ensemble_manager.apply_failover("local", fallback_provider)
                # Keep top-level config synchronized
                self.config.setdefault("ensemble", {})["enabled_providers"] = list(
                    ensemble_manager.enabled_providers
                )
                self.config["ensemble"]["provider_weights"] = dict(
                    ensemble_manager.base_weights
                )
                self._ollama_failover_active = True
                issues.append(
                    f"Ollama unavailable; triggered failover to '{fallback_provider}'. "
                    f"Unavailable: {', '.join(unavailable_providers)}"
                )
                logger.warning(
                    "Ollama unavailable; triggered ensemble failover to '%s'. Unavailable: %s",
                    fallback_provider,
                    ", ".join(unavailable_providers),
                )
        except Exception as e:  # pragma: no cover - defensive
            issues.append(f"Failed to apply Ollama failover: {e}")

    def _select_fallback_provider(self, enabled_providers: List[str]) -> Optional[str]:
        """Choose the first non-local provider as a failover target."""
        for provider in enabled_providers:
            if provider != "local":
                return provider
        return None

    def _auto_start_trade_monitor(self):
        """Start internal TradeMonitor if enabled in config.

        Creates unified data/timeframe providers if available; falls back gracefully
        so that monitoring remains passive and non-blocking.
        """
        if self.trade_monitor is not None:
            logger.info("TradeMonitor already started internally; skipping")
            return
        try:
            # Ensure numba can cache compiled functions in a writable location inside the container
            if "NUMBA_CACHE_DIR" not in os.environ:
                try:
                    numba_cache_dir = "/tmp/numba_cache"
                    Path(numba_cache_dir).mkdir(parents=True, exist_ok=True)
                    os.environ["NUMBA_CACHE_DIR"] = numba_cache_dir
                    logger.debug(
                        "NUMBA_CACHE_DIR set to %s for pandas-ta imports", numba_cache_dir
                    )
                except Exception as cache_err:  # pragma: no cover - defensive
                    logger.warning(
                        "Could not prepare NUMBA cache directory: %s", cache_err
                    )

            from .monitoring.trade_monitor import TradeMonitor

            # Attempt to import unified data provider + timeframe aggregator
            unified_dp = None
            timeframe_agg = None
            try:
                from .data_providers.timeframe_aggregator import TimeframeAggregator
                from .data_providers.unified_data_provider import UnifiedDataProvider

                providers_cfg = (self.config or {}).get("providers", {})
                av_key = None
                coinbase_creds = None
                oanda_creds = None
                try:
                    av_key = providers_cfg.get("alpha_vantage", {}).get("api_key")
                except (AttributeError, TypeError):
                    av_key = None
                try:
                    coinbase_creds = providers_cfg.get("coinbase", {}).get(
                        "credentials"
                    )
                except (AttributeError, TypeError):
                    coinbase_creds = None
                try:
                    oanda_creds = providers_cfg.get("oanda", {}).get("credentials")
                except (AttributeError, TypeError):
                    oanda_creds = None

                unified_dp = UnifiedDataProvider(
                    alpha_vantage_api_key=av_key,
                    coinbase_credentials=coinbase_creds,
                    oanda_credentials=oanda_creds,
                    config=self.config,
                )
                timeframe_agg = TimeframeAggregator(unified_dp)
            except ImportError as e:
                logger.warning(
                    f"Unified/timeframe providers unavailable for monitor: {e}"
                )

            self.trade_monitor = TradeMonitor(
                platform=self.trading_platform,
                detection_interval=30,
                poll_interval=30,
                unified_data_provider=unified_dp,
                timeframe_aggregator=timeframe_agg,
                pulse_interval=self._monitor_pulse_interval,
            )
            self.trade_monitor.start()
            logger.info(
                "Internal TradeMonitor started (pulse=%ss, manual_cli=%s)",
                self._monitor_pulse_interval,
                self._monitor_manual_cli,
            )
        except (ImportError, ValueError, AttributeError) as e:
            logger.warning(
                f"Failed to auto-start TradeMonitor due to configuration error: {e}",
                exc_info=True,
            )
        except Exception as e:
            logger.warning(f"Failed to auto-start TradeMonitor: {e}", exc_info=True)

    def enable_monitoring_integration(self, trade_monitor=None, metrics_collector=None):
        """
        Enable live monitoring context integration for AI decisions.

        Args:
            trade_monitor: Optional TradeMonitor instance
            metrics_collector: Optional TradeMetricsCollector instance
        """
        from .monitoring import MonitoringContextProvider

        self.trade_monitor = trade_monitor
        self.monitoring_provider = MonitoringContextProvider(
            platform=self.trading_platform,
            trade_monitor=trade_monitor,
            metrics_collector=metrics_collector,
        )

        # Attach to decision engine
        self.decision_engine.set_monitoring_context(self.monitoring_provider)

        logger.info(
            "Monitoring context integration enabled - "
            "AI will have full awareness of active positions/trades"
        )

    def analyze_asset(
        self,
        asset_pair: str,
        include_sentiment: bool = True,
        include_macro: bool = False,
        use_memory_context: bool = True,
        provider: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Analyze an asset and generate a trading decision (sync API).

        The engine internally performs async I/O (e.g. data-provider calls). For
        synchronous callers, this method runs the async implementation in an
        event loop and returns the resolved decision dict.

        If you are already in an async context (event loop running), call
        [`FinanceFeedbackEngine.analyze_asset_async()`](finance_feedback_engine/core.py:450).
        """
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(
                self.analyze_asset_async(
                    asset_pair=asset_pair,
                    include_sentiment=include_sentiment,
                    include_macro=include_macro,
                    use_memory_context=use_memory_context,
                )
            )

        raise RuntimeError(
            "FinanceFeedbackEngine.analyze_asset() cannot be called when an event loop is running. "
            "Use await FinanceFeedbackEngine.analyze_asset_async(...) instead."
        )

    def _should_refresh_balance_for_asset(
        self,
        balance: Dict[str, float],
        asset_pair: str,
    ) -> bool:
        """Return True when direct balance refresh is needed for sizing.

        Triggers when:
        1) No positive balance values exist at all, OR
        2) Asset-specific platform keys are missing/zero (e.g. forex without
           positive oanda_* balance keys).
        """
        # Base condition: no positive cash at all
        has_any_positive = any(float(v or 0) > 0 for v in balance.values())
        if not has_any_positive:
            return True

        try:
            from .utils.asset_classifier import classify_asset_pair

            asset_class = classify_asset_pair(asset_pair)
        except Exception:
            asset_class = "unknown"

        if asset_class == "forex":
            # Forex execution routes to Oanda, so require positive Oanda balance
            return not any(
                k.startswith("oanda_") and float(v or 0) > 0
                for k, v in balance.items()
            )

        if asset_class == "crypto":
            # Crypto execution routes to Coinbase
            return not any(
                (k.startswith("coinbase_") or k in {"FUTURES_USD", "SPOT_USD", "SPOT_USDC"})
                and float(v or 0) > 0
                for k, v in balance.items()
            )

        return False

    async def analyze_asset_async(
        self,
        asset_pair: str,
        include_sentiment: bool = True,
        include_macro: bool = False,
        use_memory_context: bool = True,
    ) -> Dict[str, Any]:
        """Analyze an asset and generate trading decision (async API)."""
        from .utils.validation import standardize_asset_pair

        # Standardize asset pair input (uppercase, remove separators)
        asset_pair = standardize_asset_pair(asset_pair)

        logger.info("Analyzing asset: %s", asset_pair)

        # Fetch comprehensive market data
        market_data = await self.data_provider.get_comprehensive_market_data(
            asset_pair, include_sentiment=include_sentiment, include_macro=include_macro
        )

        # Compare Alpha Vantage price with real-time platform data (THR-22 fix)
        # This validates data quality and detects price divergence
        try:
            platform_price_data = self.unified_provider.get_current_price(asset_pair)
            av_price = market_data.get("close")
            data_age_minutes = market_data.get("data_age_seconds", 0) / 60.0

            if platform_price_data and av_price:
                platform_price = platform_price_data["price"]
                provider_name = platform_price_data["provider"]

                # Calculate divergence: abs((platform - av) / av) * 100
                divergence_pct = abs((platform_price - av_price) / av_price) * 100

                # Record metric (will add to metrics.py next)
                try:
                    from .observability.metrics import record_price_divergence
                    record_price_divergence(asset_pair, provider_name, divergence_pct)
                except Exception:
                    pass  # Metrics should never break the flow

                # Log comparison with warning if divergence >2%
                if divergence_pct > 2.0:
                    logger.warning(
                        f"⚠️ Price divergence: {divergence_pct:.2f}% - "
                        f"Alpha Vantage ${av_price:.2f} ({data_age_minutes:.1f}min old) vs "
                        f"{provider_name} ${platform_price:.2f} (live)"
                    )
                else:
                    logger.info(
                        f"Price check: Alpha Vantage ${av_price:.2f} ({data_age_minutes:.1f}min old) vs "
                        f"{provider_name} ${platform_price:.2f} (live) | Divergence: {divergence_pct:.2f}%"
                    )
            elif not platform_price_data:
                logger.info(
                    f"Price check: Alpha Vantage ${av_price:.2f} ({data_age_minutes:.1f}min old) | "
                    f"Platform price unavailable"
                )
        except Exception as e:
            logger.debug(f"Price comparison failed for {asset_pair}: {e}")

        # Get portfolio breakdown with caching (Phase 2 optimization)
        # This replaces the separate get_balance() call (which was redundant)
        portfolio = None
        balance = {}  # Will be derived from portfolio if available

        if hasattr(self.trading_platform, "get_portfolio_breakdown"):
            try:
                # Use async version to avoid blocking the event loop
                # Add timeout to prevent indefinite waiting on API calls
                portfolio = await asyncio.wait_for(
                    self.get_portfolio_breakdown_async(),
                    timeout=15.0  # 15 second timeout for portfolio fetch
                )
                logger.info(
                    "Portfolio loaded: $%.2f across %d assets",
                    portfolio.get("total_value_usd", 0),
                    portfolio.get("num_assets", 0),
                )

                # Derive balance from portfolio breakdown to avoid redundant API call
                # Portfolio contains futures_value_usd and spot_value_usd from the same
                # API calls that get_balance() would make separately
                if portfolio.get("futures_value_usd") is not None:
                    balance["FUTURES_USD"] = portfolio.get("futures_value_usd", 0)
                if portfolio.get("spot_value_usd") is not None:
                    balance["SPOT_USD"] = portfolio.get("spot_value_usd", 0)

                platform_breakdowns = portfolio.get("platform_breakdowns") or {}
                if isinstance(platform_breakdowns, dict):
                    oanda_breakdown = platform_breakdowns.get("oanda") or {}
                    oanda_summary = oanda_breakdown.get("summary") or {}
                    oanda_balance = oanda_summary.get("balance", oanda_breakdown.get("total_value_usd"))
                    try:
                        oanda_balance_num = float(oanda_balance)
                    except (TypeError, ValueError):
                        oanda_balance_num = 0.0
                    if oanda_balance_num > 0:
                        balance["oanda_USD"] = oanda_balance_num

                logger.debug(
                    "Balance derived from portfolio: %s",
                    balance,
                )

            except (AttributeError, TypeError) as e:
                logger.warning(
                    "Could not fetch portfolio breakdown due to data format error: %s",
                    e,
                )
            except (ConnectionError, TimeoutError, ValueError) as e:
                logger.warning(
                    "Could not fetch portfolio breakdown due to connection issue: %s",
                    e,
                    exc_info=True,
                )
            except Exception as e:
                logger.warning(
                    "Could not fetch portfolio breakdown: %s", e, exc_info=True
                )

        # Get memory context if enabled
        memory_context = None
        if use_memory_context and self.memory_engine:
            memory_context = self.memory_engine.generate_context(asset_pair=asset_pair)
            logger.info(
                "Memory context loaded: %d historical trades",
                memory_context.get("total_historical_trades", 0),
            )

            # Add transaction cost analysis to memory context
            # Calculate rolling 20-trade cost averages for AI awareness
            try:
                cost_stats = self.memory_engine.calculate_rolling_cost_averages(
                    window=20, exclude_outlier_pct=0.10
                )
                memory_context["transaction_costs"] = cost_stats
                if cost_stats.get("has_data"):
                    logger.info(
                        "Transaction costs: avg %.3f%% (from %d trades)",
                        cost_stats.get("avg_total_cost_pct", 0),
                        cost_stats.get("sample_size", 0),
                    )
            except Exception as e:
                logger.warning(f"Could not calculate transaction costs: {e}")
                memory_context["transaction_costs"] = {"has_data": False}

        # Generate decision using AI engine (with Phase 1 quorum failure handling)
        from .monitoring.prometheus import (
            record_decision_latency,
            update_decision_confidence,
        )

        _decision_start = time.perf_counter()
        try:
            decision = await self.decision_engine.generate_decision(
                asset_pair=asset_pair,
                market_data=market_data,
                balance=balance,
                portfolio=portfolio,
                memory_context=memory_context,
            )
            if isinstance(decision, dict):
                logger.info(
                    "CORE post-generate shape for %s: origin=%s regime=%s has_ensemble=%s has_pre_reasoning=%s filtered=%s",
                    asset_pair,
                    decision.get("decision_origin"),
                    decision.get("market_regime"),
                    bool(decision.get("ensemble_metadata")),
                    bool(decision.get("pre_reasoning")),
                    decision.get("filtered_reason_code"),
                )
        except InsufficientProvidersError as e:
            # Phase 1 quorum failure - log and return NO_DECISION
            logger.error("Phase 1 quorum failure for %s: %s", asset_pair, e)

            asset_type = market_data.get("type", "unknown")

            # Extract provider information from the exception object
            providers_succeeded = getattr(e, "providers_succeeded", [])
            providers_failed = getattr(e, "providers_failed", [])

            # Combine succeeded and failed to get all attempted providers
            providers_attempted = providers_succeeded + providers_failed

            # Log failure for monitoring
            log_path = log_quorum_failure(
                asset=asset_pair,
                asset_type=asset_type,
                providers_attempted=providers_attempted,
                providers_succeeded=providers_succeeded,
                quorum_required=3,
                config=self.config,
            )

            # Return NO_DECISION with detailed reasoning
            decision = {
                "action": "NO_DECISION",
                "confidence": 0,
                "reasoning": (
                    f"Phase 1 quorum failure: {str(e)}. "
                    f"Manual position review required. "
                    f"See failure log: {log_path}"
                ),
                "amount": 0,
                "asset_pair": asset_pair,
                "timestamp": datetime.now().isoformat(),
                "ai_provider": self.decision_engine.ai_provider,
                "ensemble_metadata": {
                    "error_type": "quorum_failure",
                    "error_message": str(e),
                },
            }
        except Exception as e:
            # Capture unexpected exceptions for error tracking
            self.error_tracker.capture_exception(
                e,
                {
                    "asset_pair": asset_pair,
                    "module": "core",
                    "operation": "analyze_asset",
                    "include_sentiment": include_sentiment,
                    "include_macro": include_macro,
                },
            )
            # Re-raise to preserve existing error handling behavior
            raise

        # Record aggregated decision latency metric
        try:
            _duration = time.perf_counter() - _decision_start
            record_decision_latency(
                provider="ensemble", asset_pair=asset_pair, duration_seconds=_duration
            )
        except Exception:
            # Metrics should never break the flow
            pass

        # Persist decision. Mark the in-memory object so downstream agent stages can
        # update the same artifact instead of saving a duplicate file/log entry.
        logger.info(
            "CORE pre-save shape for %s: origin=%s regime=%s has_ensemble=%s has_pre_reasoning=%s filtered=%s",
            asset_pair,
            decision.get("decision_origin") if isinstance(decision, dict) else None,
            decision.get("market_regime") if isinstance(decision, dict) else None,
            bool(decision.get("ensemble_metadata")) if isinstance(decision, dict) else False,
            bool(decision.get("pre_reasoning")) if isinstance(decision, dict) else False,
            decision.get("filtered_reason_code") if isinstance(decision, dict) else None,
        )
        self.decision_store.save_decision(decision)
        if isinstance(decision, dict):
            decision["_persisted_to_store"] = True

        # Record metrics: decision created
        action = decision.get("action", "UNKNOWN")
        # Determine asset type from market data or use heuristic
        crypto_symbols = {
            "BTC",
            "ETH",
            "SOL",
            "DOGE",
            "XRP",
            "ADA",
            "LTC",
            "AVAX",
            "DOT",
            "MATIC",
        }
        asset_type = (
            "crypto" if any(sym in asset_pair for sym in crypto_symbols) else "forex"
        )
        # Consider removing asset_pair label to avoid high cardinality
        if self._metrics:
            self._metrics["ffe_decisions_created_total"].add(
                1, {"action": action, "asset_type": asset_type}
            )

        # Update decision confidence gauge (aggregated)
        try:
            conf = float(decision.get("confidence", 0))
            update_decision_confidence(
                asset_pair=asset_pair, action=action, confidence=conf
            )
        except Exception:
            pass

        logger.info(
            "CORE return shape for %s: origin=%s regime=%s has_ensemble=%s has_pre_reasoning=%s filtered=%s",
            asset_pair,
            decision.get("decision_origin") if isinstance(decision, dict) else None,
            decision.get("market_regime") if isinstance(decision, dict) else None,
            bool(decision.get("ensemble_metadata")) if isinstance(decision, dict) else False,
            bool(decision.get("pre_reasoning")) if isinstance(decision, dict) else False,
            decision.get("filtered_reason_code") if isinstance(decision, dict) else None,
        )
        return decision
