"""Core Finance Feedback Engine module."""

from typing import Dict, Any, Optional, List
import socket
import os
from datetime import datetime
import logging

from .data_providers.alpha_vantage_provider import AlphaVantageProvider
from .data_providers.historical_data_provider import HistoricalDataProvider
from .trading_platforms.platform_factory import PlatformFactory
from .decision_engine.engine import DecisionEngine
from .persistence.decision_store import DecisionStore
from .memory.portfolio_memory import PortfolioMemoryEngine
from .utils.model_installer import ensure_models_installed
from .utils.failure_logger import log_quorum_failure
from .exceptions import (
    InsufficientProvidersError,
    ModelInstallationError,
    ConfigurationError,
    APIError,
    DataProviderError,
    PersistenceError,
    TradingError,
    MemoryError
)

logger = logging.getLogger(__name__)


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
        self.config = config

        # Ensure Ollama models are installed (one-time setup)
        try:
            logger.info("Checking Ollama model installation...")
            ensure_models_installed()
        except ModelInstallationError as e:
            logger.warning(f"Model installation check failed: {e}")
            # Continue anyway - system may work with fewer models
        except Exception as e:
            logger.warning(f"Unexpected error during model installation check: {e}", exc_info=True)
            # Continue anyway - system may work with fewer models

        # Initialize data provider
        api_key = os.environ.get('ALPHA_VANTAGE_API_KEY') \
            or config.get('alpha_vantage_api_key')
        self.data_provider = AlphaVantageProvider(
            api_key=api_key,
            config=config
        )

        # Initialize historical data provider for backtesting
        self.historical_data_provider = HistoricalDataProvider(api_key=api_key)

        # Initialize trading platform
        platform_name = config.get('trading_platform', 'coinbase')

        # Handle unified/multi-platform mode
        if platform_name.lower() == 'unified':
            # Convert platforms list to unified credentials format
            platforms_list = config.get('platforms', [])
            if not platforms_list:
                raise ValueError(
                    "Unified platform mode requires 'platforms' list in config. "
                    "Example:\n"
                    "platforms:\n"
                    "  - name: coinbase_advanced\n"
                    "    credentials: {...}\n"
                    "  - name: oanda\n"
                    "    credentials: {...}"
                )

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

                platform_key = platform_config.get('name', '').lower()
                platform_creds = platform_config.get('credentials', {})

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
                if platform_key in ['coinbase', 'coinbase_advanced']:
                    unified_credentials['coinbase'] = platform_creds
                elif platform_key == 'oanda':
                    unified_credentials['oanda'] = platform_creds
                else:
                    logger.warning(
                        f"Unknown platform in unified config: {platform_key}"
                    )

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
            platform_credentials = config.get('platform_credentials', {})

        try:
            self.trading_platform = PlatformFactory.create_platform(
                platform_name, platform_credentials
            )
        except Exception as e:
            logger.error(f"Failed to create trading platform {platform_name}: {e}", exc_info=True)
            raise ConfigurationError(f"Platform configuration error: {e}") from e

        # Initialize decision engine
        self.decision_engine = DecisionEngine(config, self.data_provider)

        # Initialize persistence
        persistence_config = config.get('persistence', {})
        self.decision_store = DecisionStore(persistence_config)

        # Initialize portfolio memory engine
        memory_enabled = config.get('portfolio_memory', {}).get('enabled', False)
        self.memory_engine: Optional[PortfolioMemoryEngine] = None
        if memory_enabled:
            # Auto-load persisted memory if exists
            memory_path = "data/memory/portfolio_memory.json"
            if os.path.exists(memory_path):
                try:
                    self.memory_engine = PortfolioMemoryEngine.load_from_disk(memory_path)
                    logger.info(f"Loaded portfolio memory from {memory_path}")
                except (FileNotFoundError, PermissionError) as e:
                    logger.warning(f"Failed to load portfolio memory: {e}, starting fresh")
                    self.memory_engine = PortfolioMemoryEngine(config)
                except MemoryError as e:
                    logger.warning(f"Failed to load portfolio memory due to memory error: {e}, starting fresh")
                    self.memory_engine = PortfolioMemoryEngine(config)
                except Exception as e:
                    logger.warning(f"Unexpected error loading portfolio memory: {e}, starting fresh", exc_info=True)
                    self.memory_engine = PortfolioMemoryEngine(config)
            else:
                self.memory_engine = PortfolioMemoryEngine(config)
                logger.info("No persisted memory found, starting fresh")

            logger.info("Portfolio Memory Engine enabled")

        # Initialize monitoring context provider (lazy init)
        self.monitoring_provider = None
        self.trade_monitor = None
        self._monitoring_enabled = config.get('monitoring', {}).get(
            'enable_context_integration', True
        )
        self._auto_start_monitor_flag = config.get('monitoring', {}).get(
            'enabled', False
        )
        self._monitor_manual_cli = config.get('monitoring', {}).get(
            'manual_cli', False
        )
        self._monitor_pulse_interval = config.get('monitoring', {}).get(
            'pulse_interval_seconds', 300
        )

        # Auto-enable monitoring integration if enabled in config
        if self._monitoring_enabled:
            self._auto_enable_monitoring()
        # Optionally start internal TradeMonitor (no direct CLI control)
        if self._auto_start_monitor_flag:
            self._auto_start_trade_monitor()

        # Backtester (lazy init holder)
        self._backtester: Optional[Backtester] = None

        logger.info("Finance Feedback Engine initialized successfully")

    def _auto_enable_monitoring(self):
        """Auto-enable monitoring integration with default settings."""
        try:
            from .monitoring import (
                MonitoringContextProvider,
                TradeMetricsCollector
            )

            # Create metrics collector
            metrics_collector = TradeMetricsCollector()

            # Create monitoring provider (no trade monitor needed for context)
            self.monitoring_provider = MonitoringContextProvider(
                platform=self.trading_platform,
                trade_monitor=None,  # Optional, can add later
                metrics_collector=metrics_collector
            )

            # Attach to decision engine
            self.decision_engine.set_monitoring_context(
                self.monitoring_provider
            )

            logger.info(
                "Monitoring context auto-enabled - "
                "AI has position awareness by default"
            )
        except ImportError as e:
            logger.warning(
                "Could not auto-enable monitoring context due to import error: %s", e
            )
        except Exception as e:
            logger.warning(
                "Could not auto-enable monitoring context: %s", e, exc_info=True
            )

    def _auto_start_trade_monitor(self):
        """Start internal TradeMonitor if enabled in config.

        Creates unified data/timeframe providers if available; falls back gracefully
        so that monitoring remains passive and non-blocking.
        """
        if self.trade_monitor is not None:
            logger.info("TradeMonitor already started internally; skipping")
            return
        try:
            from .monitoring.trade_monitor import TradeMonitor
            # Attempt to import unified data provider + timeframe aggregator
            unified_dp = None
            timeframe_agg = None
            try:
                from .data_providers.unified_data_provider import UnifiedDataProvider
                from .data_providers.timeframe_aggregator import TimeframeAggregator
                providers_cfg = (self.config or {}).get('providers', {})
                av_key = None
                coinbase_creds = None
                oanda_creds = None
                try:
                    av_key = providers_cfg.get('alpha_vantage', {}).get('api_key')
                except (AttributeError, TypeError):
                    av_key = None
                try:
                    coinbase_creds = providers_cfg.get('coinbase', {}).get('credentials')
                except (AttributeError, TypeError):
                    coinbase_creds = None
                try:
                    oanda_creds = providers_cfg.get('oanda', {}).get('credentials')
                except (AttributeError, TypeError):
                    oanda_creds = None

                unified_dp = UnifiedDataProvider(
                    alpha_vantage_api_key=av_key,
                    coinbase_credentials=coinbase_creds,
                    oanda_credentials=oanda_creds,
                    config=self.config
                )
                timeframe_agg = TimeframeAggregator(unified_dp)
            except ImportError as e:
                logger.warning(f"Unified/timeframe providers unavailable for monitor: {e}")

            self.trade_monitor = TradeMonitor(
                platform=self.trading_platform,
                detection_interval=30,
                poll_interval=30,
                unified_data_provider=unified_dp,
                timeframe_aggregator=timeframe_agg,
                pulse_interval=self._monitor_pulse_interval
            )
            self.trade_monitor.start()
            logger.info(
                "Internal TradeMonitor started (pulse=%ss, manual_cli=%s)",
                self._monitor_pulse_interval,
                self._monitor_manual_cli
            )
        except Exception as e:
            logger.warning(f"Failed to auto-start TradeMonitor: {e}", exc_info=True)

    def enable_monitoring_integration(
        self,
        trade_monitor=None,
        metrics_collector=None
    ):
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
            metrics_collector=metrics_collector
        )

        # Attach to decision engine
        self.decision_engine.set_monitoring_context(
            self.monitoring_provider
        )

        logger.info(
            "Monitoring context integration enabled - "
            "AI will have full awareness of active positions/trades"
        )

    async def analyze_asset(
        self,
        asset_pair: str,
        include_sentiment: bool = True,
        include_macro: bool = False,
        use_memory_context: bool = True,
    ) -> Dict[str, Any]:
        """Analyze an asset and generate trading decision.

        Args:
            asset_pair: Asset pair to analyze (e.g., 'BTCUSD', 'EURUSD')
            include_sentiment: Include news sentiment analysis (default: True)
            include_macro: Include macroeconomic indicators (default: False)
            use_memory_context: Include portfolio memory context (default: True)

        Returns:
            Dictionary containing analysis results and decision
        """
        from .utils.validation import standardize_asset_pair

        # Standardize asset pair input (uppercase, remove separators)
        asset_pair = standardize_asset_pair(asset_pair)

        logger.info("Analyzing asset: %s", asset_pair)

        # Fetch comprehensive market data
        market_data = await self.data_provider.get_comprehensive_market_data(
            asset_pair,
            include_sentiment=include_sentiment,
            include_macro=include_macro
        )

        # Get current balance from trading platform
        balance = self.trading_platform.get_balance()

        # Get portfolio breakdown if platform supports it
        portfolio = None
        if hasattr(self.trading_platform, 'get_portfolio_breakdown'):
            try:
                portfolio = self.trading_platform.get_portfolio_breakdown()
                logger.info(
                    "Portfolio loaded: $%.2f across %d assets",
                    portfolio.get('total_value_usd', 0),
                    portfolio.get('num_assets', 0)
                )
            except (AttributeError, TypeError) as e:
                logger.warning("Could not fetch portfolio breakdown due to data format error: %s", e)
            except Exception as e:
                logger.warning("Could not fetch portfolio breakdown: %s", e, exc_info=True)

        # Get memory context if enabled
        memory_context = None
        if use_memory_context and self.memory_engine:
            memory_context = self.memory_engine.generate_context(
                asset_pair=asset_pair
            )
            logger.info(
                "Memory context loaded: %d historical trades",
                memory_context.get('total_historical_trades', 0)
            )

        # Generate decision using AI engine (with Phase 1 quorum failure handling)
        try:
            decision = await self.decision_engine.generate_decision(
                asset_pair=asset_pair,
                market_data=market_data,
                balance=balance,
                portfolio=portfolio,
                memory_context=memory_context
            )
        except InsufficientProvidersError as e:
            # Phase 1 quorum failure - log and return NO_DECISION
            logger.error("Phase 1 quorum failure for %s: %s", asset_pair, e)

            asset_type = market_data.get('type', 'unknown')

            # Extract provider information from the exception object
            providers_succeeded = getattr(e, 'providers_succeeded', [])
            providers_failed = getattr(e, 'providers_failed', [])

            # Combine succeeded and failed to get all attempted providers
            providers_attempted = providers_succeeded + providers_failed

            # Log failure for monitoring
            log_path = log_quorum_failure(
                asset=asset_pair,
                asset_type=asset_type,
                providers_attempted=providers_attempted,
                providers_succeeded=providers_succeeded,
                quorum_required=3,
                config=self.config
            )

            # Return NO_DECISION with detailed reasoning
            decision = {
                'action': 'NO_DECISION',
                'confidence': 0,
                'reasoning': (
                    f'Phase 1 quorum failure: {str(e)}. '
                    f'Manual position review required. '
                    f'See failure log: {log_path}'
                ),
                'amount': 0,
                'asset_pair': asset_pair,
                'timestamp': datetime.now().isoformat(),
                'ensemble_metadata': {
                    'error_type': 'quorum_failure',
                    'error_message': str(e)
                }
            }

        # Persist decision
        self.decision_store.save_decision(decision)

        return decision

    def get_balance(self) -> Dict[str, float]:
        """
        Get current balance from trading platform.

        Returns:
            Dictionary of asset balances
        """
        return self.trading_platform.get_balance()

    def get_decision_history(
        self,
        asset_pair: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Retrieve historical trading decisions.

        Args:
            asset_pair: Optional filter by asset pair
            limit: Maximum number of decisions to retrieve

        Returns:
            List of historical decisions
        """
        return self.decision_store.get_decisions(
            asset_pair=asset_pair,
            limit=limit
        )

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

        # Use persistent circuit breaker on platform when available
        try:
            breaker = None
            if getattr(self.trading_platform, 'get_execute_breaker', None):
                breaker = self.trading_platform.get_execute_breaker()

            # If no breaker on platform, create a local one
            if breaker is None:
                from .utils.circuit_breaker import CircuitBreaker
                cb_name = f"execute_trade:{self.trading_platform.__class__.__name__}"
                breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=60, name=cb_name)

            # Execute trade under circuit breaker protection
            result = breaker.call_sync(self.trading_platform.execute_trade, decision)
        except TradingError as e:
            # Log and update decision with failure
            logger.error(f"Trade execution failed: {e}")
            decision['executed'] = False
            decision['execution_time'] = datetime.utcnow().isoformat()
            decision['execution_result'] = {'success': False, 'error': str(e)}
            self.decision_store.update_decision(decision)
            raise
        except Exception as e:
            # Log and update decision with failure
            logger.error(f"Trade execution failed: {e}", exc_info=True)
            decision['executed'] = False
            decision['execution_time'] = datetime.utcnow().isoformat()
            decision['execution_result'] = {'success': False, 'error': str(e)}
            self.decision_store.update_decision(decision)
            raise

        # Update decision with successful execution result
        decision['executed'] = True
        decision['execution_time'] = datetime.utcnow().isoformat()
        decision['execution_result'] = result
        self.decision_store.update_decision(decision)

        return result

    def _preexecution_checks(self, decision: Dict[str, Any], monitoring_context: Optional[object] = None) -> None:
        """
        Run pre-execution safety checks before sending orders to the platform.
        """
        # Block execution if signal_only mode
        if decision.get('signal_only', False):
            raise ValueError(
                "Decision is in signal-only mode; execution blocked. "
                "To allow execution: provide platform balances (configure credentials) "
                "or disable signal-only via config key 'signal_only_default: false'."
            )

        # If monitoring provider available, get context and run simple risk checks
        try:
            provider = self.monitoring_provider or monitoring_context
            if provider:
                ctx = provider.get_monitoring_context(asset_pair=decision.get('asset_pair'))
                risk = ctx.get('risk_metrics', {})
                leverage = risk.get('leverage_estimate', 0)
                largest_pct = ctx.get('position_concentration', {}).get('largest_position_pct', 0)

                # Simple safety thresholds — configurable later via config
                max_leverage = self.config.get('safety', {}).get('max_leverage', 5.0)
                max_concentration = self.config.get('safety', {}).get('max_position_pct', 25.0)

                if leverage and leverage > max_leverage:
                    raise ValueError(f"Execution blocked: leverage {leverage:.2f} exceeds max {max_leverage}")

                if largest_pct and largest_pct > max_concentration:
                    raise ValueError(
                        f"Execution blocked: largest position {largest_pct:.1f}% exceeds max {max_concentration}%"
                    )
        except (TimeoutError, ConnectionError, socket.timeout) as e:
            # If monitoring fetch fails due to known transient issues, allow execution but log warning
            logger.warning(f"Pre-execution monitoring checks failed due to network/timeout; proceeding cautiously: {e}")
        except Exception as e:
            # For any other error, re-raise to block execution and surface the problem
            logger.error(f"Critical error during pre-execution monitoring checks: {e}")
            raise

    async def backtest(
        self,
        asset_pair: str,
        start: str,
        end: str,
        strategy: str = "sma_crossover",
        short_window: Optional[int] = None,
        long_window: Optional[int] = None,
        initial_balance: Optional[float] = None,
        fee_percentage: Optional[float] = None,
    ) -> Dict[str, Any]:
        """DEPRECATED: Use AdvancedBacktester directly via CLI.

        This method is maintained for backward compatibility but will be removed.
        Use: python main.py backtest ASSET --start DATE --end DATE

        Args:
            asset_pair: Symbol pair (e.g. 'BTCUSD').
            start: Start date (YYYY-MM-DD).
            end: End date (YYYY-MM-DD).
            strategy: Strategy identifier (deprecated, still passed to legacy Backtester).
            short_window: Override for short SMA window (deprecated, still passed to legacy Backtester).
            long_window: Override for long SMA window (deprecated, still passed to legacy Backtester).
            initial_balance: Override starting balance.
            fee_percentage: Override per trade fee percent.
        Returns:
            Dict with strategy metadata, performance metrics and trade log.
        """
        import warnings
        warnings.warn(
            "FinanceFeedbackEngine.backtest() is deprecated. "
            "Use AdvancedBacktester directly via CLI: python main.py backtest ASSET --start DATE --end DATE",
            DeprecationWarning,
            stacklevel=2
        )
        if self._backtester is None:
            bt_conf = self.config.get('backtesting', {})
            self._backtester = Backtester(self.data_provider, bt_conf)
        return await self._backtester.run(
            asset_pair=asset_pair,
            start=start,
            end=end,
            strategy_name=strategy,
            short_window=short_window,
            long_window=long_window,
            initial_balance=initial_balance,
            fee_percentage=fee_percentage,
        )

    # ===================================================================
    # Portfolio Memory Methods
    # ===================================================================

    def record_trade_outcome(
        self,
        decision_id: str,
        exit_price: float,
        exit_timestamp: Optional[str] = None,
        hit_stop_loss: bool = False,
        hit_take_profit: bool = False
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
                "Portfolio memory engine not enabled. "
                "Cannot record trade outcome."
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
            hit_take_profit=hit_take_profit
        )

        logger.info(
            f"Trade outcome recorded: {outcome.asset_pair} "
            f"P&L: ${outcome.realized_pnl:.2f}"
        )
        # ----- Learning loop: update ensemble weights if available -----
        try:
            ensemble_mgr = getattr(self.decision_engine, 'ensemble_manager', None)
            if ensemble_mgr and isinstance(ensemble_mgr, object):
                # Extract provider decisions from original decision if available
                ensemble_meta = decision.get('ensemble_metadata', {})
                provider_decisions = ensemble_meta.get('provider_decisions', {})

                # Determine actual outcome as market-directed action
                # If trade was profitable, actual_outcome == original action
                # Otherwise actual_outcome == opposite action
                original_action = decision.get('action')
                if outcome.was_profitable:
                    actual_outcome = original_action
                else:
                    opposite = {'BUY': 'SELL', 'SELL': 'BUY', 'LONG': 'SHORT', 'SHORT': 'LONG'}
                    actual_outcome = opposite.get(original_action, 'HOLD')

                # Use P&L percentage as base metric when available (prefer percent)
                base_pct = None
                try:
                    base_pct = getattr(outcome, 'pnl_percentage', None)
                except Exception:
                    base_pct = None

                if base_pct is None:
                    # Compute percentage from realized pnl if possible
                    try:
                        denom = (outcome.entry_price or 0) * (outcome.position_size or decision.get('recommended_position_size', 0) or 1)
                        base_pct = ((outcome.realized_pnl or 0.0) / denom * 100.0) if denom else (outcome.realized_pnl or 0.0)
                    except Exception:
                        base_pct = (outcome.realized_pnl or 0.0)

                # Time adjustment: reward quicker profitable trades (cap amplification)
                holding = getattr(outcome, 'holding_period_hours', None) or 24.0
                speed_factor = 24.0 / max(holding, 1.0/24.0)
                speed_factor = max(0.25, min(speed_factor, 4.0))

                # Volatility normalization: if volatility is provided, moderate the score
                vol = getattr(outcome, 'volatility', None) or decision.get('volatility') or 0.0
                vol_factor = 1.0 / (1.0 + abs(vol)) if vol is not None else 1.0

                # Risk penalty: penalize very large position relative to account size
                try:
                    entry_val = (outcome.entry_price or decision.get('entry_price', 0)) * (outcome.position_size or decision.get('recommended_position_size', 0) or 1)
                    balances = decision.get('balance_snapshot') or {}
                    if isinstance(balances, dict):
                        account_value = sum(v for v in balances.values() if isinstance(v, (int, float)))
                    else:
                        account_value = float(balances) if balances else 0.0
                    risk_frac = (entry_val / account_value) if account_value > 0 else 0.0
                    risk_penalty = max(0.1, 1.0 - risk_frac)
                except (ZeroDivisionError, TypeError, ValueError):
                    risk_penalty = 1.0

                # Final normalized performance metric
                perf_metric = float(base_pct * speed_factor * vol_factor * risk_penalty)

                try:
                    ensemble_mgr.update_base_weights(
                        provider_decisions,
                        actual_outcome,
                        perf_metric
                    )
                    logger.info("Ensemble weights updated from trade outcome")
                except (AttributeError, TypeError) as e:
                    logger.warning(f"Failed to update ensemble weights due to data format error: {e}")
                except Exception as e:
                    logger.warning(f"Failed to update ensemble weights: {e}", exc_info=True)
        except (AttributeError, TypeError) as e:
            logger.debug(f"No ensemble manager available or learning update skipped: {e}")
        except Exception as e:
            logger.debug(f"No ensemble manager available or learning update skipped: {e}", exc_info=True)

        return outcome.to_dict()

    def get_performance_snapshot(
        self,
        window_days: Optional[int] = None
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

        snapshot = self.memory_engine.analyze_performance(
            window_days=window_days
        )

        return snapshot.to_dict()

    def get_memory_context(
        self,
        asset_pair: Optional[str] = None
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
            if hasattr(self.data_provider, 'close'):
                close_result = self.data_provider.close()
                # Check if result is awaitable (coroutine or awaitable object)
                if inspect.iscoroutine(close_result) or inspect.isawaitable(close_result):
                    await close_result
                logger.info("Data provider resources closed successfully")
        except Exception as e:
            logger.error(f"Error during engine cleanup: {e}", exc_info=True)

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - cleanup resources."""
        await self.close()
        return False
