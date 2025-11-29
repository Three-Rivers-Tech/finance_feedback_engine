"""Core Finance Feedback Engine module."""

from typing import Dict, Any, Optional, List
import socket
from datetime import datetime
import logging

from .data_providers.alpha_vantage_provider import AlphaVantageProvider
from .trading_platforms.platform_factory import PlatformFactory
from .decision_engine.engine import DecisionEngine
from .persistence.decision_store import DecisionStore
from .backtesting.backtester import Backtester
from .memory.portfolio_memory import PortfolioMemoryEngine

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
        
        # Initialize data provider
        import os
        api_key = os.environ.get('ALPHA_VANTAGE_API_KEY') \
            or config.get('alpha_vantage_api_key')
        self.data_provider = AlphaVantageProvider(
            api_key=api_key,
            config=config
        )
        
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
        
        self.trading_platform = PlatformFactory.create_platform(
            platform_name, platform_credentials
        )
        
        # Initialize decision engine
        self.decision_engine = DecisionEngine(config, self.data_provider)
        
        # Initialize persistence
        persistence_config = config.get('persistence', {})
        self.decision_store = DecisionStore(persistence_config)

        # Initialize portfolio memory engine
        memory_enabled = config.get('portfolio_memory', {}).get('enabled', False)
        self.memory_engine: Optional[PortfolioMemoryEngine] = None
        if memory_enabled:
            self.memory_engine = PortfolioMemoryEngine(config)
            logger.info("Portfolio Memory Engine enabled")
        
        # Initialize monitoring context provider (lazy init)
        self.monitoring_provider = None
        self.trade_monitor = None
        self._monitoring_enabled = config.get('monitoring', {}).get(
            'enable_context_integration', True
        )
        
        # Auto-enable monitoring integration if enabled in config
        if self._monitoring_enabled:
            self._auto_enable_monitoring()

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
        except Exception as e:
            logger.warning(
                "Could not auto-enable monitoring context: %s", e
            )
    
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

    def analyze_asset(
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
        market_data = self.data_provider.get_comprehensive_market_data(
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
            except Exception as e:
                logger.warning("Could not fetch portfolio breakdown: %s", e)
        
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
        
        # Generate decision using AI engine
        decision = self.decision_engine.generate_decision(
            asset_pair=asset_pair,
            market_data=market_data,
            balance=balance,
            portfolio=portfolio,
            memory_context=memory_context
        )
        
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
            result = breaker.call(self.trading_platform.execute_trade, decision)
        except Exception as e:
            # Log and update decision with failure
            logger.error(f"Trade execution failed: {e}")
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
            raise ValueError("Decision is in signal-only mode; execution blocked")

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

    def backtest(
        self,
        asset_pair: str,
        start: str,
        end: str,
        strategy: str = 'sma_crossover',
        short_window: Optional[int] = None,
        long_window: Optional[int] = None,
        initial_balance: Optional[float] = None,
        fee_percentage: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Run a historical strategy simulation.

        Args:
            asset_pair: Symbol pair (e.g. 'BTCUSD').
            start: Start date (YYYY-MM-DD).
            end: End date (YYYY-MM-DD).
            strategy: Strategy identifier (currently only 'sma_crossover').
            short_window: Override for short SMA window.
            long_window: Override for long SMA window.
            initial_balance: Override starting balance.
            fee_percentage: Override per trade fee percent.
        Returns:
            Dict with strategy metadata, performance metrics and trade log.
        """
        if self._backtester is None:
            bt_conf = self.config.get('backtesting', {})
            self._backtester = Backtester(self.data_provider, bt_conf)
        return self._backtester.run(
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
                except Exception:
                    risk_penalty = 1.0

                # Final normalized performance metric
                perf_metric = float(base_pct * speed_factor * vol_factor * risk_penalty)

                try:
                    ensemble_mgr.update_provider_weights(
                        provider_decisions,
                        actual_outcome,
                        perf_metric
                    )
                    logger.info("Ensemble weights updated from trade outcome")
                except Exception as e:
                    logger.warning(f"Failed to update ensemble weights: {e}")
        except Exception as e:
            logger.debug(f"No ensemble manager available or learning update skipped: {e}")

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
