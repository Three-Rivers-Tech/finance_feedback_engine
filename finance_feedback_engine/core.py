"""Core Finance Feedback Engine module."""

from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

from .data_providers.alpha_vantage_provider import AlphaVantageProvider
from .trading_platforms.platform_factory import PlatformFactory
from .decision_engine.engine import DecisionEngine
from .persistence.decision_store import DecisionStore

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
        self.data_provider = AlphaVantageProvider(
            api_key=config.get('alpha_vantage_api_key')
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
        
        logger.info("Finance Feedback Engine initialized successfully")

    def analyze_asset(self, asset_pair: str) -> Dict[str, Any]:
        """
        Analyze an asset and generate trading decision.

        Args:
            asset_pair: Asset pair to analyze (e.g., 'BTCUSD', 'EURUSD')

        Returns:
            Dictionary containing analysis results and decision
        """
        logger.info(f"Analyzing asset: {asset_pair}")
        
        # Fetch market data
        market_data = self.data_provider.get_market_data(asset_pair)
        
        # Get current balance from trading platform
        balance = self.trading_platform.get_balance()
        
        # Generate decision using AI engine
        decision = self.decision_engine.generate_decision(
            asset_pair=asset_pair,
            market_data=market_data,
            balance=balance
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
