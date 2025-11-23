"""Core Finance Feedback Engine module."""

from typing import Dict, Any, Optional, List
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
        platform_credentials = config.get('platform_credentials', {})
        self.trading_platform = PlatformFactory.create_platform(
            platform_name, platform_credentials
        )
        
        # Initialize decision engine
        decision_config = config.get('decision_engine', {})
        self.decision_engine = DecisionEngine(decision_config)
        
        # Initialize persistence
        persistence_config = config.get('persistence', {})
        self.decision_store = DecisionStore(persistence_config)

        # Initialize portfolio memory engine
        memory_enabled = config.get('portfolio_memory', {}).get('enabled', False)
        self.memory_engine: Optional[PortfolioMemoryEngine] = None
        if memory_enabled:
            self.memory_engine = PortfolioMemoryEngine(config)
            logger.info("Portfolio Memory Engine enabled")

        # Backtester (lazy init holder)
        self._backtester: Optional[Backtester] = None

        logger.info("Finance Feedback Engine initialized successfully")

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
        
        result = self.trading_platform.execute_trade(decision)
        
        # Update decision with execution result
        decision['executed'] = True
        decision['execution_time'] = datetime.utcnow().isoformat()
        decision['execution_result'] = result
        self.decision_store.update_decision(decision)
        
        return result

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
