"""Core Finance Feedback Engine module."""

import asyncio
import logging
import os
import socket
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import pandas as pd

from .data_providers.alpha_vantage_provider import AlphaVantageProvider
from .data_providers.historical_data_provider import HistoricalDataProvider
from .decision_engine.engine import DecisionEngine
from .exceptions import (
    ConfigurationError,
    FFEMemoryError,
    InsufficientProvidersError,
    ModelInstallationError,
    RiskValidationError,
    TradingError,
)
from .memory.portfolio_memory_adapter import PortfolioMemoryEngineAdapter
from .monitoring.error_tracking import ErrorTracker
from .monitoring.trade_outcome_recorder import TradeOutcomeRecorder
from .observability.metrics import create_counters, get_meter
from .persistence.decision_store import DecisionStore
from .security.validator import validate_at_startup
from .trading_platforms.platform_factory import PlatformFactory
from .utils.credential_validator import validate_credentials
from .utils.config_schema_validator import validate_and_warn
from .utils.cache_metrics import CacheMetrics
from .utils.failure_logger import log_quorum_failure
from .utils.model_installer import ensure_models_installed

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .backtesting.backtester import Backtester


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
        # Run security validation at startup (warns on plaintext credentials)
        config_path = Path(__file__).parent.parent / "config" / "config.yaml"
        validate_at_startup(config_path, raise_on_error=False)

        # Validate credentials (fail fast on placeholder values)
        validate_credentials(config)

        # Validate config schema (warns on misconfigurations)
        validate_and_warn(config)

        self.config = config

        # Initialize error tracking (Phase 2.1)
        self.error_tracker = ErrorTracker(config.get("error_tracking", {}))

        # Portfolio caching infrastructure (Phase 2 optimization)
        self._portfolio_cache = None
        self._portfolio_cache_time = None
        self._portfolio_cache_ttl = 60  # 60 seconds
        self._cache_metrics = CacheMetrics()  # Track cache performance

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
        providers_cfg = config.get("providers", {}) if isinstance(config.get("providers"), dict) else {}
        platform_creds_cfg = (
            config.get("platform_credentials", {})
            if isinstance(config.get("platform_credentials"), dict)
            else {}
        )

        coinbase_credentials = (
            config.get("coinbase")
            or providers_cfg.get("coinbase", {}).get("credentials")
            or platform_creds_cfg.get("coinbase")
        )

        oanda_credentials = (
            config.get("oanda")
            or providers_cfg.get("oanda", {}).get("credentials")
            or platform_creds_cfg.get("oanda")
        )

        # Fallback: extract credentials from platforms list (name/credentials entries)
        if not oanda_credentials or not isinstance(oanda_credentials, dict):
            for platform_cfg in config.get("platforms", []) or []:
                if isinstance(platform_cfg, dict) and str(platform_cfg.get("name", "")).lower() == "oanda":
                    creds = platform_cfg.get("credentials")
                    if isinstance(creds, dict):
                        oanda_credentials = creds
                        break

        if not coinbase_credentials or not isinstance(coinbase_credentials, dict):
            for platform_cfg in config.get("platforms", []) or []:
                if isinstance(platform_cfg, dict) and str(platform_cfg.get("name", "")).lower() in {"coinbase", "coinbase_advanced"}:
                    creds = platform_cfg.get("credentials")
                    if isinstance(creds, dict):
                        coinbase_credentials = creds
                        break

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
                    if paper_enabled and (
                        not platform_creds
                        or any(_is_placeholder(v) for v in platform_creds.values())
                    ):
                        logger.info(
                            "Skipping oanda platform in sandbox mode (missing or placeholder credentials)."
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

        # Initialize persistence
        persistence_config = config.get("persistence", {})
        self.decision_store = DecisionStore(persistence_config)

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
                    hasattr(self.trading_platform, 'execute')
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
        try:
            api_key = os.environ.get("ALPHA_VANTAGE_API_KEY") or self.config.get(
                "alpha_vantage_api_key"
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

        # Live-forex freshness fix: override potentially stale historical close with
        # real-time Oanda pricing when available.
        try:
            if self.unified_provider and self.unified_provider._is_forex(asset_pair):
                live_price = self.unified_provider.get_current_price(asset_pair)
                if live_price and live_price.get("price") is not None:
                    market_data["close"] = float(live_price["price"])
                    market_data["timestamp"] = live_price.get("timestamp")
                    market_data["data_age_seconds"] = 0
                    market_data["live_price_provider"] = live_price.get("provider", "oanda_pricing")
        except Exception as _e:
            logger.debug("Unable to overlay live forex price for %s: %s", asset_pair, _e)

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
        except (KeyError, TypeError) as e:
            logger.warning(
                "Price comparison skipped due to data format issue",
                extra={
                    "asset_pair": asset_pair,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "has_platform_data": bool(platform_price_data),
                    "has_av_price": bool(av_price)
                }
            )
        except Exception as e:
            logger.warning(
                "Price comparison failed unexpectedly",
                extra={
                    "asset_pair": asset_pair,
                    "error": str(e),
                    "error_type": type(e).__name__
                },
                exc_info=True
            )
            # TODO: Alert if price comparison consistently fails (THR-XXX)

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

                logger.debug(
                    "Balance derived from portfolio: %s",
                    balance,
                )

            except (AttributeError, TypeError) as e:
                logger.error(
                    "Portfolio breakdown fetch failed - data format error",
                    extra={
                        "asset_pair": asset_pair,
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "platform_type": type(self.trading_platform).__name__
                    }
                )
                # TODO: Track portfolio fetch data errors for platform health (THR-XXX)
            except asyncio.TimeoutError:
                logger.error(
                    "Portfolio breakdown fetch timed out",
                    extra={
                        "asset_pair": asset_pair,
                        "timeout_seconds": 15.0,
                        "platform_type": type(self.trading_platform).__name__
                    }
                )
                # TODO: Alert on portfolio fetch timeouts - impacts position sizing (THR-XXX)
            except (ConnectionError, ValueError) as e:
                logger.error(
                    "Portfolio breakdown fetch failed - connection/validation error",
                    extra={
                        "asset_pair": asset_pair,
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "platform_type": type(self.trading_platform).__name__
                    },
                    exc_info=True
                )
                # TODO: Alert on repeated connection failures (THR-XXX)
            except Exception as e:
                logger.error(
                    "Portfolio breakdown fetch failed unexpectedly",
                    extra={
                        "asset_pair": asset_pair,
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "platform_type": type(self.trading_platform).__name__
                    },
                    exc_info=True
                )
                # TODO: Alert on unknown portfolio fetch errors (THR-XXX)

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
            except (ValueError, TypeError, KeyError) as e:
                logger.warning(
                    "Transaction cost calculation failed - data issue",
                    extra={
                        "asset_pair": asset_pair,
                        "error": str(e),
                        "error_type": type(e).__name__
                    }
                )
                memory_context["transaction_costs"] = {"has_data": False}
            except Exception as e:
                logger.error(
                    "Transaction cost calculation failed unexpectedly",
                    extra={
                        "asset_pair": asset_pair,
                        "error": str(e),
                        "error_type": type(e).__name__
                    },
                    exc_info=True
                )
                memory_context["transaction_costs"] = {"has_data": False}
                # TODO: Monitor transaction cost calculation failures (THR-XXX)

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
        except Exception as e:
            # Metrics should never break the flow
            logger.warning(
                f"Failed to record decision latency for {asset_pair}: {e}",
                extra={"asset_pair": asset_pair, "duration": _duration}
            )

        # Persist decision
        self.decision_store.save_decision(decision)

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

        return decision

    def get_historical_data_from_lake(
        self, asset_pair: str, timeframe: str, lookback_days: int = 30
    ) -> Optional[pd.DataFrame]:
        """
        Query historical data from Delta Lake (if enabled).

        Args:
            asset_pair: The asset pair to query (e.g., "BTCUSD")
            timeframe: The timeframe to query (e.g., "1d", "1h", "15m")
            lookback_days: Number of days to look back (default 30)

        Returns:
            pandas DataFrame with historical data or None if Delta Lake not available
        """
        if not self.delta_lake:
            logger.warning("Delta Lake not enabled")
            return None

        try:
            from datetime import datetime, timedelta

            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=lookback_days)

            # Query Delta Lake
            df = self.delta_lake.read_table(
                table_name=f"raw_market_data_{timeframe}",
                filters=[
                    f"asset_pair = '{asset_pair}'",
                    f"timestamp >= '{start_date.isoformat()}'",
                ],
            )

            logger.info(
                f"Retrieved {len(df)} records from Delta Lake for {asset_pair} ({timeframe})"
            )
            return df
        except Exception as e:
            logger.error(f"Error querying Delta Lake: {e}")
            return None

    def get_portfolio_breakdown(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get portfolio breakdown with 60-second caching (Phase 2 optimization).

        Args:
            force_refresh: Bypass cache and fetch fresh data

        Returns:
            Portfolio breakdown dict with caching metadata
        """
        # Check cache validity
        if not force_refresh and self._portfolio_cache is not None:
            cache_age = (datetime.now() - self._portfolio_cache_time).total_seconds()
            if cache_age < self._portfolio_cache_ttl:
                logger.debug(f"Portfolio cache hit (age: {cache_age:.1f}s)")
                self._cache_metrics.record_hit("portfolio")
                return {
                    **self._portfolio_cache,
                    "_cached": True,
                    "_cache_age_seconds": cache_age,
                }

        # Fetch fresh data
        logger.debug("Portfolio cache miss - fetching fresh data")
        self._cache_metrics.record_miss("portfolio")
        portfolio = self.trading_platform.get_portfolio_breakdown()

        # Update cache
        self._portfolio_cache = portfolio
        self._portfolio_cache_time = datetime.now()

        return {**portfolio, "_cached": False, "_cache_age_seconds": 0}

    async def get_portfolio_breakdown_async(self) -> Dict[str, Any]:
        """Async variant of get_portfolio_breakdown to avoid event-loop blocking."""
        # Check cache first
        if self._portfolio_cache and self._portfolio_cache_time:
            cache_age = (datetime.now() - self._portfolio_cache_time).total_seconds()
            if cache_age < self._portfolio_cache_ttl:
                logger.debug(
                    f"Portfolio cache hit (age: {cache_age:.1f}s, TTL: {self._portfolio_cache_ttl}s)"
                )
                self._cache_metrics.record_hit("portfolio")
                return {
                    **self._portfolio_cache,
                    "_cached": True,
                    "_cache_age_seconds": cache_age,
                }

        # Fetch fresh data
        logger.debug("Portfolio cache miss - fetching fresh data (async)")
        self._cache_metrics.record_miss("portfolio")
        portfolio = await self.trading_platform.aget_portfolio_breakdown()

        # Update cache
        self._portfolio_cache = portfolio
        self._portfolio_cache_time = datetime.now()

        return {**portfolio, "_cached": False, "_cache_age_seconds": 0}

    def invalidate_portfolio_cache(self):
        """Invalidate portfolio cache (call after trades execute)."""
        self._portfolio_cache = None
        self._portfolio_cache_time = None
        logger.debug("Portfolio cache invalidated")

    def get_balance(self) -> Dict[str, float]:
        """
        Get current balance from trading platform.

        Returns:
            Dictionary of asset balances
        """
        return self.trading_platform.get_balance()

    def get_decision_history(
        self, asset_pair: Optional[str] = None, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Retrieve historical trading decisions.

        Args:
            asset_pair: Optional filter by asset pair
            limit: Maximum number of decisions to retrieve

        Returns:
            List of historical decisions
        """
        return self.decision_store.get_decisions(asset_pair=asset_pair, limit=limit)

    def execute_decision(self, decision_id: str) -> Dict[str, Any]:
        """
        Execute a trading decision (if supported by platform).

        Args:
            decision_id: ID of the decision to execute

        Returns:
            Execution result
        """
        decision = self.decision_store.get_decision_by_id(decision_id)
        if not decision:
            raise ValueError(f"Decision {decision_id} not found")

        # Pre-execution safety checks
        self._preexecution_checks(decision, monitoring_context=None)

        # Mandatory RiskGatekeeper validation before execution (engine-level)
        try:
            # Build monitoring context if available
            monitoring_context = {}
            if hasattr(self, "monitoring_provider") and self.monitoring_provider:
                try:
                    monitoring_context = (
                        self.monitoring_provider.get_monitoring_context(
                            asset_pair=decision.get("asset_pair")
                        )
                    )
                except Exception:
                    monitoring_context = {}

            # Enrich context with asset type and timestamp hints
            try:
                from .utils.asset_classifier import classify_asset_pair

                asset_class = classify_asset_pair(decision.get("asset_pair", ""))
                monitoring_context.setdefault(
                    "asset_type", "crypto" if asset_class == "crypto" else "forex"
                )
            except Exception:
                monitoring_context.setdefault("asset_type", "crypto")
            monitoring_context.setdefault(
                "market_data_timestamp", decision.get("timestamp")
            )

            # Validate decision against risk constraints
            from .risk.gatekeeper import RiskGatekeeper

            gatekeeper = RiskGatekeeper()
            allowed, reason = gatekeeper.validate_trade(decision, monitoring_context)
            if not allowed:
                logger.warning(f"Trade rejected by RiskGatekeeper: {reason}")
                decision["executed"] = False
                decision["execution_time"] = datetime.utcnow().isoformat()
                decision["execution_result"] = {
                    "success": False,
                    "error": reason,
                    "status": "REJECTED_BY_GATEKEEPER",
                }
                self.decision_store.update_decision(decision)
                # Abort execution and return rejection result
                return decision["execution_result"]
        except Exception as e:
            # FAIL-CLOSED: If gatekeeper crashes, block the trade (never execute unvalidated)
            logger.critical(
                f"RiskGatekeeper validation error — BLOCKING TRADE: {e}",
                exc_info=True,
            )
            decision["executed"] = False
            decision["execution_time"] = datetime.utcnow().isoformat()
            decision["execution_result"] = {
                "success": False,
                "error": f"RiskGatekeeper internal error: {e}",
                "status": "BLOCKED_GATEKEEPER_ERROR",
            }
            self.decision_store.update_decision(decision)
            raise RiskValidationError(
                f"Trade blocked: RiskGatekeeper encountered an internal error: {e}"
            ) from e

        # === POSITION SIZE REVALIDATION AT EXECUTION TIME (THR-80) ===
        # Position size was calculated during RISK_CHECK, but risk limits or balance
        # may have changed. Recalculate with CURRENT limits before executing.
        if hasattr(self, "position_sizing_calculator") and self.position_sizing_calculator:
            try:
                sizing = self.position_sizing_calculator.calculate_position_sizing_params(
                    context=decision,
                    current_price=decision.get("entry_price", 0),
                    action=decision.get("action", "UNKNOWN"),
                    has_existing_position=decision.get("has_existing_position", False),
                    relevant_balance=decision.get("relevant_balance", {}),
                    balance_source=decision.get("balance_source", "unknown"),
                )
                if sizing:
                    new_size = sizing.get("recommended_position_size")
                    old_size = decision.get("recommended_position_size")
                    if new_size and old_size and new_size != old_size:
                        logger.warning(
                            f"Position size recalculated at execution time: "
                            f"{old_size} → {new_size} (risk limits may have changed)"
                        )
                    if new_size is not None:
                        decision["recommended_position_size"] = new_size
                        decision["position_size_recalculated_at_execution"] = True
            except Exception as e:
                # Log but don't block — the original sizing from RISK_CHECK is still valid
                logger.warning(f"Position size recalculation failed: {e}")

        # === TWO-PHASE COMMIT: Persist intent BEFORE execution ===
        # PHASE 1: Mark decision as "pending execution" and flush to disk.
        # If the system crashes after this point, we can detect the orphan on restart.
        decision["execution_status"] = "pending"
        decision["execution_started"] = datetime.utcnow().isoformat()
        self.decision_store.update_decision(decision)

        # Use persistent circuit breaker on platform when available
        try:
            breaker = None
            if getattr(self.trading_platform, "get_execute_breaker", None):
                breaker = self.trading_platform.get_execute_breaker()

            # If no breaker on platform, create a local one
            if breaker is None:
                from .utils.circuit_breaker import CircuitBreaker

                cb_name = f"execute_trade:{self.trading_platform.__class__.__name__}"
                breaker = CircuitBreaker(
                    failure_threshold=3, recovery_timeout=60, name=cb_name
                )

            # PHASE 2: Execute trade under circuit breaker protection
            result = breaker.call_sync(self.trading_platform.execute_trade, decision)
        except TradingError as e:
            # Log and update decision with failure
            logger.error(f"Trade execution failed: {e}")
            decision["executed"] = False
            decision["execution_status"] = "failed"
            decision["execution_time"] = datetime.utcnow().isoformat()
            decision["execution_result"] = {"success": False, "error": str(e)}
            self.decision_store.update_decision(decision)
            raise
        except (ConnectionError, socket.timeout, TimeoutError) as e:
            # Log and update decision with failure — status stays "pending" so
            # orphan detection can reconcile with the platform on restart.
            logger.error(
                f"Trade execution failed due to connection/network issue: {e}",
                exc_info=True,
            )
            decision["executed"] = False
            decision["execution_status"] = "pending_unknown"
            decision["execution_time"] = datetime.utcnow().isoformat()
            decision["execution_result"] = {"success": False, "error": str(e)}
            self.decision_store.update_decision(decision)
            raise
        except Exception as e:
            # Log and update decision with failure
            logger.error(f"Trade execution failed: {e}", exc_info=True)
            decision["executed"] = False
            decision["execution_status"] = "failed"
            decision["execution_time"] = datetime.utcnow().isoformat()
            decision["execution_result"] = {"success": False, "error": str(e)}
            self.decision_store.update_decision(decision)
            raise

        # PHASE 3: Post-execution persistence — mark as completed
        decision["executed"] = True
        decision["execution_status"] = "completed"
        decision["execution_time"] = datetime.utcnow().isoformat()
        decision["execution_result"] = result
        
        # Populate decision file fields (THR-235)
        decision["status"] = "executed"
        decision["platform_name"] = result.get("platform", self.config.get("trading_platform"))
        decision["position_size"] = result.get("size") or decision.get("recommended_position_size")
        
        # Store order_id in decision file (THR-236)
        order_id = result.get("order_id")
        if order_id:
            decision["order_id"] = order_id
        
        self.decision_store.update_decision(decision)

        # Invalidate portfolio cache after trade execution (Phase 2 optimization)
        self.invalidate_portfolio_cache()

        # Add order to pending outcomes tracking (THR-236)
        if self.order_status_worker and order_id and result.get("success"):
            try:
                self.order_status_worker.add_pending_order(
                    order_id=order_id,
                    decision_id=decision.get("id"),
                    asset_pair=decision.get("asset_pair"),
                    platform=result.get("platform", self.config.get("trading_platform")),
                    action=decision.get("action"),
                    size=float(decision.get("position_size", 0)),
                    entry_price=float(decision.get("entry_price", 0)) if decision.get("entry_price") else None,
                )
                logger.info(f"Added order {order_id} to pending outcomes tracking")
            except Exception as e:
                logger.warning(f"Failed to add order to pending tracking: {e}")

        # THR-237: Async position polling (fire-and-forget, reduces latency)
        # Background worker (THR-236) handles outcome recording via order ID tracking
        if self.trade_outcome_recorder:
            try:
                # Fetch current positions from platform
                positions_response = self.trading_platform.get_active_positions()
                current_positions = positions_response.get("positions", [])
                
                # Fire-and-forget: queue outcome recording in background
                # This returns immediately (<10ms) instead of blocking (100-500ms)
                self.trade_outcome_recorder.update_positions_async(current_positions)
                logger.debug("Queued async position update (non-blocking)")
                
            except Exception as e:
                logger.warning(f"Failed to queue async position update: {e}")

        return result

    async def execute_decision_async(self, decision_id: str) -> Dict[str, Any]:
        """Async variant of execute_decision to avoid blocking event loop."""
        decision = self.decision_store.get_decision_by_id(decision_id)
        if not decision:
            raise ValueError(f"Decision {decision_id} not found")

        self._preexecution_checks(decision, monitoring_context=None)

        # Mandatory RiskGatekeeper validation before execution (engine-level, async)
        try:
            monitoring_context = {}
            if hasattr(self, "monitoring_provider") and self.monitoring_provider:
                try:
                    monitoring_context = (
                        self.monitoring_provider.get_monitoring_context(
                            asset_pair=decision.get("asset_pair")
                        )
                    )
                except Exception:
                    monitoring_context = {}

            try:
                from .utils.asset_classifier import classify_asset_pair

                asset_class = classify_asset_pair(decision.get("asset_pair", ""))
                monitoring_context.setdefault(
                    "asset_type", "crypto" if asset_class == "crypto" else "forex"
                )
            except Exception:
                monitoring_context.setdefault("asset_type", "crypto")
            monitoring_context.setdefault(
                "market_data_timestamp", decision.get("timestamp")
            )

            from .risk.gatekeeper import RiskGatekeeper

            gatekeeper = RiskGatekeeper()
            allowed, reason = gatekeeper.validate_trade(decision, monitoring_context)
            if not allowed:
                logger.warning(f"Trade rejected by RiskGatekeeper: {reason}")
                decision["executed"] = False
                decision["execution_time"] = datetime.utcnow().isoformat()
                decision["execution_result"] = {
                    "success": False,
                    "error": reason,
                    "status": "REJECTED_BY_GATEKEEPER",
                }
                self.decision_store.update_decision(decision)
                return decision["execution_result"]
        except Exception as e:
            # FAIL-CLOSED: If gatekeeper crashes, block the trade (never execute unvalidated)
            logger.critical(
                f"RiskGatekeeper validation error — BLOCKING TRADE: {e}",
                exc_info=True,
            )
            decision["executed"] = False
            decision["execution_time"] = datetime.utcnow().isoformat()
            decision["execution_result"] = {
                "success": False,
                "error": f"RiskGatekeeper internal error: {e}",
                "status": "BLOCKED_GATEKEEPER_ERROR",
            }
            self.decision_store.update_decision(decision)
            raise RiskValidationError(
                f"Trade blocked: RiskGatekeeper encountered an internal error: {e}"
            ) from e

        # === POSITION SIZE REVALIDATION AT EXECUTION TIME (THR-80) ===
        if hasattr(self, "position_sizing_calculator") and self.position_sizing_calculator:
            try:
                sizing = self.position_sizing_calculator.calculate_position_sizing_params(
                    context=decision,
                    current_price=decision.get("entry_price", 0),
                    action=decision.get("action", "UNKNOWN"),
                    has_existing_position=decision.get("has_existing_position", False),
                    relevant_balance=decision.get("relevant_balance", {}),
                    balance_source=decision.get("balance_source", "unknown"),
                )
                if sizing:
                    new_size = sizing.get("recommended_position_size")
                    old_size = decision.get("recommended_position_size")
                    if new_size and old_size and new_size != old_size:
                        logger.warning(
                            f"Position size recalculated at execution time: "
                            f"{old_size} → {new_size} (risk limits may have changed)"
                        )
                    if new_size is not None:
                        decision["recommended_position_size"] = new_size
                        decision["position_size_recalculated_at_execution"] = True
            except Exception as e:
                logger.warning(f"Position size recalculation failed: {e}")

        # === TWO-PHASE COMMIT: Persist intent BEFORE execution ===
        decision["execution_status"] = "pending"
        decision["execution_started"] = datetime.utcnow().isoformat()
        self.decision_store.update_decision(decision)

        try:
            breaker = None
            if getattr(self.trading_platform, "get_execute_breaker", None):
                breaker = self.trading_platform.get_execute_breaker()

            if breaker is None:
                from .utils.circuit_breaker import CircuitBreaker

                cb_name = f"execute_trade:{self.trading_platform.__class__.__name__}"
                breaker = CircuitBreaker(
                    failure_threshold=3, recovery_timeout=60, name=cb_name
                )

            result = await breaker.call(self.trading_platform.aexecute_trade, decision)
        except TradingError as e:
            logger.error(f"Trade execution failed: {e}")
            decision["executed"] = False
            decision["execution_status"] = "failed"
            decision["execution_time"] = datetime.utcnow().isoformat()
            decision["execution_result"] = {"success": False, "error": str(e)}
            self.decision_store.update_decision(decision)
            raise
        except (ConnectionError, socket.timeout, TimeoutError) as e:
            logger.error(
                f"Trade execution failed due to connection/network issue: {e}",
                exc_info=True,
            )
            decision["executed"] = False
            decision["execution_status"] = "pending_unknown"
            decision["execution_time"] = datetime.utcnow().isoformat()
            decision["execution_result"] = {"success": False, "error": str(e)}
            self.decision_store.update_decision(decision)
            raise
        except Exception as e:
            logger.error(f"Trade execution failed: {e}", exc_info=True)
            decision["executed"] = False
            decision["execution_status"] = "failed"
            decision["execution_time"] = datetime.utcnow().isoformat()
            decision["execution_result"] = {"success": False, "error": str(e)}
            self.decision_store.update_decision(decision)
            raise

        decision["executed"] = True
        decision["execution_status"] = "completed"
        decision["execution_time"] = datetime.utcnow().isoformat()
        decision["execution_result"] = result
        
        # Populate decision file fields (THR-235)
        decision["status"] = "executed"
        decision["platform_name"] = result.get("platform", self.config.get("trading_platform"))
        decision["position_size"] = result.get("size") or decision.get("recommended_position_size")
        
        # Store order_id in decision file (THR-236)
        order_id = result.get("order_id")
        if order_id:
            decision["order_id"] = order_id
        
        self.decision_store.update_decision(decision)

        self.invalidate_portfolio_cache()

        # Add order to pending outcomes tracking (THR-236)
        if self.order_status_worker and order_id and result.get("success"):
            try:
                self.order_status_worker.add_pending_order(
                    order_id=order_id,
                    decision_id=decision.get("id"),
                    asset_pair=decision.get("asset_pair"),
                    platform=result.get("platform", self.config.get("trading_platform")),
                    action=decision.get("action"),
                    size=float(decision.get("position_size", 0)),
                    entry_price=float(decision.get("entry_price", 0)) if decision.get("entry_price") else None,
                )
                logger.info(f"Added order {order_id} to pending outcomes tracking")
            except Exception as e:
                logger.warning(f"Failed to add order to pending tracking: {e}")

        # THR-237: Async position polling (fire-and-forget, reduces latency)
        # Background worker (THR-236) handles outcome recording via order ID tracking
        if self.trade_outcome_recorder:
            try:
                # Fetch current positions from platform
                positions_response = await self.trading_platform.aget_active_positions()
                current_positions = positions_response.get("positions", [])
                
                # Fire-and-forget: queue outcome recording in background
                # This returns immediately (<10ms) instead of blocking (100-500ms)
                self.trade_outcome_recorder.update_positions_async(current_positions)
                logger.debug("Queued async position update (non-blocking)")
                
            except Exception as e:
                logger.warning(f"Failed to queue async position update: {e}")

        return result

    def _preexecution_checks(
        self, decision: Dict[str, Any], monitoring_context: Optional[object] = None
    ) -> None:
        """
        Run pre-execution safety checks before sending orders to the platform.

        NOTE: Risk validation is now centralized in RiskGatekeeper.validate_trade(),
        which is called by the agent RISK_CHECK state. This method no longer enforces
        signal-only blocking (deprecated in favor of explicit approvals/autonomous mode).
        """

        # Block signal-only decisions from execution
        if decision.get("signal_only"):
            raise ValueError(
                "Cannot execute trade in signal-only mode. "
                "Decision is flagged as signal_only."
            )

        # Note: Leverage and concentration checks are now handled by
        # RiskGatekeeper._validate_leverage_and_concentration() which is called
        # during the agent RISK_CHECK state. This consolidates all risk validation
        # in one place and prevents duplication.

    # ===================================================================
    # Portfolio Memory Methods
    # ===================================================================

    def record_trade_outcome(
        self,
        decision_id: str,
        exit_price: float,
        exit_timestamp: Optional[str] = None,
        hit_stop_loss: bool = False,
        hit_take_profit: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """
        Record the outcome of a completed trade for learning.

        Args:
            decision_id: ID of the original decision
            exit_price: Price at which position was closed
            exit_timestamp: When position was closed (default: now)
            hit_stop_loss: Whether stop loss was triggered
            hit_take_profit: Whether take profit was triggered

        Returns:
            TradeOutcome dict if memory engine enabled, None otherwise
        """
        if not self.memory_engine:
            logger.warning(
                "Portfolio memory engine not enabled. " "Cannot record trade outcome."
            )
            return None

        # Get original decision
        decision = self.decision_store.get_decision_by_id(decision_id)
        if not decision:
            raise ValueError(f"Decision {decision_id} not found")

        # Record outcome
        outcome = self.memory_engine.record_trade_outcome(
            decision=decision,
            exit_price=exit_price,
            exit_timestamp=exit_timestamp,
            hit_stop_loss=hit_stop_loss,
            hit_take_profit=hit_take_profit,
        )

        logger.info(
            f"Trade outcome recorded: {outcome.asset_pair} "
            f"P&L: ${outcome.realized_pnl:.2f}"
        )
        # ----- Learning loop: update ensemble weights if available -----
        try:
            ensemble_mgr = getattr(self.decision_engine, "ensemble_manager", None)
            if ensemble_mgr and isinstance(ensemble_mgr, object):
                # Extract provider decisions from original decision if available
                ensemble_meta = decision.get("ensemble_metadata", {})
                provider_decisions = ensemble_meta.get("provider_decisions", {})

                # Determine actual outcome as market-directed action
                # If trade was profitable, actual_outcome == original action
                # Otherwise actual_outcome == opposite action
                original_action = decision.get("action")
                if outcome.was_profitable:
                    actual_outcome = original_action
                else:
                    opposite = {
                        "BUY": "SELL",
                        "SELL": "BUY",
                        "LONG": "SHORT",
                        "SHORT": "LONG",
                    }
                    actual_outcome = opposite.get(original_action, "HOLD")

                # Use P&L percentage as base metric when available (prefer percent)
                base_pct = None
                try:
                    base_pct = getattr(outcome, "pnl_percentage", None)
                except AttributeError:
                    base_pct = None

                if base_pct is None:
                    # Compute percentage from realized pnl if possible
                    try:
                        denom = (outcome.entry_price or 0) * (
                            outcome.position_size
                            or decision.get("recommended_position_size", 0)
                            or 1
                        )
                        base_pct = (
                            ((outcome.realized_pnl or 0.0) / denom * 100.0)
                            if denom
                            else (outcome.realized_pnl or 0.0)
                        )
                    except (ZeroDivisionError, TypeError, AttributeError):
                        base_pct = outcome.realized_pnl or 0.0

                # Time adjustment: reward quicker profitable trades (cap amplification)
                holding = getattr(outcome, "holding_period_hours", None) or 24.0
                speed_factor = 24.0 / max(holding, 1.0 / 24.0)
                speed_factor = max(0.25, min(speed_factor, 4.0))

                # Volatility normalization: if volatility is provided, moderate the score
                vol = (
                    getattr(outcome, "volatility", None)
                    or decision.get("volatility")
                    or 0.0
                )
                vol_factor = 1.0 / (1.0 + abs(vol)) if vol is not None else 1.0

                # Risk penalty: penalize very large position relative to account size
                try:
                    entry_val = (
                        outcome.entry_price or decision.get("entry_price", 0)
                    ) * (
                        outcome.position_size
                        or decision.get("recommended_position_size", 0)
                        or 1
                    )
                    balances = decision.get("balance_snapshot") or {}
                    if isinstance(balances, dict):
                        account_value = sum(
                            v for v in balances.values() if isinstance(v, (int, float))
                        )
                    else:
                        account_value = float(balances) if balances else 0.0
                    risk_frac = (
                        (entry_val / account_value) if account_value > 0 else 0.0
                    )
                    risk_penalty = max(0.1, 1.0 - risk_frac)
                except (ZeroDivisionError, TypeError, ValueError):
                    risk_penalty = 1.0

                # Final normalized performance metric
                perf_metric = float(base_pct * speed_factor * vol_factor * risk_penalty)

                try:
                    ensemble_mgr.update_base_weights(
                        provider_decisions, actual_outcome, perf_metric
                    )
                    logger.info("Ensemble weights updated from trade outcome")
                except (AttributeError, TypeError) as e:
                    logger.warning(
                        f"Failed to update ensemble weights due to data format error: {e}"
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to update ensemble weights: {e}", exc_info=True
                    )
        except (AttributeError, TypeError) as e:
            logger.debug(
                f"No ensemble manager available or learning update skipped: {e}"
            )
        except Exception as e:
            logger.debug(
                f"No ensemble manager available or learning update skipped: {e}",
                exc_info=True,
            )

        return outcome.to_dict()

    def get_performance_snapshot(
        self, window_days: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get portfolio performance snapshot.

        Args:
            window_days: Number of days to analyze (None = all time)

        Returns:
            PerformanceSnapshot dict if memory engine enabled, None otherwise
        """
        if not self.memory_engine:
            logger.warning("Portfolio memory engine not enabled")
            return None

        snapshot = self.memory_engine.analyze_performance(window_days=window_days)

        return snapshot.to_dict()

    def get_memory_context(
        self, asset_pair: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get portfolio memory context for a given asset.

        Args:
            asset_pair: Optional asset pair filter

        Returns:
            Context dict if memory engine enabled, None otherwise
        """
        if not self.memory_engine:
            return None

        return self.memory_engine.generate_context(asset_pair=asset_pair)

    def get_provider_recommendations(self) -> Optional[Dict[str, Any]]:
        """
        Get AI provider weight recommendations based on performance.

        Returns:
            Recommendations dict if memory engine enabled, None otherwise
        """
        if not self.memory_engine:
            logger.warning("Portfolio memory engine not enabled")
            return None

        return self.memory_engine.get_provider_recommendations()

    def save_memory(self) -> None:
        """Save portfolio memory to disk."""
        if self.memory_engine:
            self.memory_engine.save_memory()
            logger.info("Portfolio memory saved")

    def get_memory_summary(self) -> Optional[Dict[str, Any]]:
        """
        Get summary of portfolio memory state.

        Returns:
            Summary dict if memory engine enabled, None otherwise
        """
        if not self.memory_engine:
            return None

        return self.memory_engine.get_summary()

    async def close(self) -> None:
        """
        Cleanup engine resources (async session cleanup for data providers).

        Call this method when shutting down the engine to properly close
        async resources like aiohttp sessions. Can be used in async context
        managers or shutdown hooks.
        """
        import inspect

        try:
            # Stop order status worker (THR-236)
            if hasattr(self, "order_status_worker") and self.order_status_worker:
                try:
                    self.order_status_worker.stop(timeout=10)
                    logger.debug("Order status worker stopped successfully")
                except Exception as e:
                    logger.warning(f"Error stopping order status worker: {e}")
            
            # Close main data provider
            if hasattr(self.data_provider, "close"):
                close_result = self.data_provider.close()
                # Check if result is awaitable (coroutine or awaitable object)
                if inspect.iscoroutine(close_result) or inspect.isawaitable(
                    close_result
                ):
                    await close_result
                logger.debug("Data provider resources closed successfully")

            # Close unified data provider
            if hasattr(self, "unified_provider") and hasattr(self.unified_provider, "close"):
                close_result = self.unified_provider.close()
                if inspect.iscoroutine(close_result) or inspect.isawaitable(
                    close_result
                ):
                    await close_result
                logger.debug("Unified data provider resources closed successfully")

            # Close historical data provider
            if hasattr(self, "historical_data_provider") and hasattr(self.historical_data_provider, "close"):
                close_result = self.historical_data_provider.close()
                if inspect.iscoroutine(close_result) or inspect.isawaitable(
                    close_result
                ):
                    await close_result
                logger.debug("Historical data provider resources closed successfully")

            logger.info("All engine resources closed successfully")
        except Exception as e:
            logger.error(f"Error during engine cleanup: {e}", exc_info=True)

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - cleanup resources."""
        await self.close()
        return False

    def get_cache_metrics(self) -> Dict[str, Any]:
        """
        Get cache performance metrics (Phase 2 optimization).

        Returns:
            Dictionary with cache performance data
        """
        return self._cache_metrics.get_summary()

    def log_cache_performance(self) -> None:
        """Log cache performance summary (Phase 2 optimization)."""
        self._cache_metrics.log_summary()
