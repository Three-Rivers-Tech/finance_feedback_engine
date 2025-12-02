"""Decision engine for generating AI-powered trading decisions."""

from typing import Dict, Any, Optional, Tuple, List
import logging
import uuid
from datetime import datetime, timedelta
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
import pandas as pd

from finance_feedback_engine.utils.market_regime_detector import MarketRegimeDetector
from finance_feedback_engine.memory.vector_store import VectorMemory

logger = logging.getLogger(__name__)

MAX_WORKERS = 4
ENSEMBLE_TIMEOUT = 30


class DecisionEngine:
    """
    AI-powered decision engine for trading recommendations.
    
    Supports integration with local AI models or CLI-based AI tools.
    
    TRADING FUNDAMENTALS - Long/Short Positions:
    ===========================================
    
    Long Positions (Bullish):
    -------------------------
    - Action: BUY to enter, SELL to exit
    - Expectation: Asset price will RISE
    - Profit: When current price > entry price
    - Loss: When current price < entry price
    - P&L Formula: (Exit Price - Entry Price) x Position Size
    - Example: Buy BTC at $50,000, sell at $55,000 = $5,000 profit per BTC
    
    Short Positions (Bearish):
    --------------------------
    - Action: SELL to enter, BUY to cover/exit
    - Expectation: Asset price will FALL
    - Profit: When current price < entry price
    - Loss: When current price > entry price
    - P&L Formula: (Entry Price - Exit Price) x Position Size
    - Example: Short BTC at $50,000, cover at $45,000 = $5,000 profit per BTC
    
    Position Sizing Principles:
    ---------------------------
    Position size determines how much capital to allocate to a trade.
    Key factors:
    1. Risk Tolerance: Typically 1-2% of total account per trade
    2. Stop Loss Distance: Price level where you exit if wrong
    3. Volatility: Higher volatility requires smaller positions
    4. Account Balance: Never risk entire capital on one trade
    
    Formula: Position Size = (Account Balance x Risk%) / (Entry Price x Stop Loss%)
    
    Example: $10,000 account, 1% risk, $50,000 BTC, 2% stop loss
    → Position Size = ($10,000 x 0.01) / ($50,000 x 0.02) = 0.1 BTC
    
    Profit & Loss Calculation:
    --------------------------
    Unrealized P&L: Open positions (mark-to-market)
    Realized P&L: Closed positions (actual profit/loss locked in)
    
    Long P&L % = ((Current Price - Entry Price) / Entry Price) x 100
    Short P&L % = ((Entry Price - Current Price) / Entry Price) x 100
    
    Risk Management:
    ----------------
    - Always use stop losses to limit downside
    - Position sizing prevents catastrophic losses
    - Diversification across multiple assets
    - Never risk more than you can afford to lose
    """

    def __init__(self, config: Dict[str, Any], data_provider=None):
        """
        Initialize the decision engine.

        Args:
            config: Configuration dictionary. Can be either:
                - Full configuration dictionary containing 'decision_engine' key with settings
                - Direct decision_engine sub-dict (for backward compatibility)
            data_provider: Data provider instance for fetching historical data
                
        The following settings are supported:
            - ai_provider: 'local', 'cli', 'codex', 'ensemble', etc.
            - model_name: Name/path of the model to use
            - prompt_template: Custom prompt template (optional)
            - decision_threshold: Confidence threshold for decisions
            - local_models: List of preferred local models
            - local_priority: Local model priority setting
            - ensemble: Ensemble configuration (if provider='ensemble')
        """
        self.data_provider = data_provider
        # Store original config for backward compatibility lookups
        self._original_config = config
        # Handle both full config and sub-dict formats
        if 'decision_engine' in config:
            # Full config passed
            self.config = config
            decision_config = config['decision_engine']
        else:
            # Sub-dict passed (backward compatibility)
            self.config = {'decision_engine': config}
            decision_config = config
        
        # Extract decision engine configuration
        self.ai_provider = decision_config.get('ai_provider', 'local')
        self.model_name = decision_config.get('model_name', 'default')
        self.decision_threshold = decision_config.get('decision_threshold', 0.7)
        self.portfolio_stop_loss_percentage = decision_config.get('portfolio_stop_loss_percentage', 0.02)
        self.portfolio_take_profit_percentage = decision_config.get('portfolio_take_profit_percentage', 0.05)
        
        # Compatibility: Convert legacy percentage values (>1) to decimals
        if self.portfolio_stop_loss_percentage > 1:
            logger.warning(f"Detected legacy portfolio_stop_loss_percentage {self.portfolio_stop_loss_percentage}%. Converting to decimal: {self.portfolio_stop_loss_percentage/100:.3f}")
            self.portfolio_stop_loss_percentage /= 100
        if self.portfolio_take_profit_percentage > 1:
            logger.warning(f"Detected legacy portfolio_take_profit_percentage {self.portfolio_take_profit_percentage}%. Converting to decimal: {self.portfolio_take_profit_percentage/100:.3f}")
            self.portfolio_take_profit_percentage /= 100
        
        # Local models and priority configuration
        self.local_models = decision_config.get('local_models', [])
        self.local_priority = decision_config.get('local_priority', False)
        
        # Validate local_models
        if not isinstance(self.local_models, list):
            raise ValueError(f"local_models must be a list, got {type(self.local_models)}")
        
        # Validate local_priority
        valid_priority_values = (True, False, "soft")
        if isinstance(self.local_priority, str):
            if self.local_priority not in valid_priority_values:
                raise ValueError(f"local_priority string must be 'soft', got '{self.local_priority}'")
        elif not isinstance(self.local_priority, (bool, int, float)):
            raise ValueError(f"local_priority must be bool, int, float, or 'soft', got {type(self.local_priority)}")
        
        logger.info(f"Local models configured: {self.local_models}")
        logger.info(f"Local priority: {self.local_priority}")
        
        # Monitoring context provider (optional, set via set_monitoring_context)
        self.monitoring_provider = None
        
        # Initialize ensemble manager if using ensemble mode
        self.ensemble_manager = None
        if self.ai_provider == 'ensemble':
            from .ensemble_manager import EnsembleDecisionManager
            self.ensemble_manager = EnsembleDecisionManager(config)
            logger.info("Ensemble mode enabled")
        
        # Initialize vector memory for semantic search (optional)
        self.vector_memory = None
        try:
            # Accept either direct path or nested config keys
            # Check top-level 'memory' key first (full config), then fall back to original config (backward compatibility)
            vm_cfg = self.config.get('memory') or self._original_config.get('memory', {})
            if not isinstance(vm_cfg, dict):
                vm_cfg = {}
            storage_path = (
                vm_cfg.get('vector_store_path')
                or vm_cfg.get('vector_memory_path')
                or vm_cfg.get('dir')
                or 'data/memory/vectors.pkl'
            )
            self.vector_memory = VectorMemory(storage_path)
            logger.info("Vector memory initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize vector memory: {e}. Proceeding without semantic search.")
        
        logger.info(f"Decision engine initialized with provider: {self.ai_provider}")
    
    def set_monitoring_context(self, monitoring_provider):
        """
        Set the monitoring context provider for live trade awareness.
        
        Args:
            monitoring_provider: MonitoringContextProvider instance
        """
        self.monitoring_provider = monitoring_provider
        logger.info("Monitoring context provider attached to decision engine")

    def generate_decision(
        self,
        asset_pair: str,
        market_data: Dict[str, Any],
        balance: Dict[str, float],
        portfolio: Optional[Dict[str, Any]] = None,
        memory_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate a trading decision based on market data and balances.

        Args:
            asset_pair: Asset pair being analyzed
            market_data: Current market data
            balance: Account balances
            portfolio: Optional portfolio breakdown with holdings/allocations
            memory_context: Optional historical performance context

        Returns:
            Trading decision with recommendation
        """
        logger.info("Generating decision for %s", asset_pair)
        
        # Get live monitoring context if available
        monitoring_context = None
        if self.monitoring_provider:
            try:
                monitoring_context = (
                    self.monitoring_provider.get_monitoring_context(
                        asset_pair=asset_pair
                    )
                )
                logger.info(
                    "Monitoring context loaded: %d active positions, %d slots",
                    len(monitoring_context.get('active_positions', {}).get('futures', [])),
                    monitoring_context.get('slots_available', 0)
                )
            except Exception as e:
                logger.warning("Could not load monitoring context: %s", e)
        
        # Create decision context
        context = self._create_decision_context(
            asset_pair,
            market_data,
            balance,
            portfolio,
            memory_context,
            monitoring_context
        )
        
        # Retrieve semantic memory
        if self.vector_memory:
            query = f"Asset: {asset_pair}. Market: {market_data.get('trend', 'neutral')}, RSI {market_data.get('rsi', 'N/A')}. Volatility: {context.get('volatility', 'N/A')}."
            try:
                similar = self.vector_memory.find_similar(query, top_k=3)
                context['semantic_memory'] = similar
            except Exception as e:
                logger.error(f"Failed to retrieve semantic memory for asset {asset_pair} with query '{query}': {e}")
                context['semantic_memory'] = []
        
        # Generate AI prompt
        prompt = self._create_ai_prompt(context)
        
        # Get AI recommendation
        ai_response = self._query_ai(prompt)
        
        # Parse and structure decision
        decision = self._create_decision(
            asset_pair=asset_pair,
            context=context,
            ai_response=ai_response
        )
        
        return decision
    
    
    def _specific_local_inference(self, prompt: str, model_name: str) -> Dict[str, Any]:
        """Query a specific local model by name."""
        logger.info(f"Using specific local model: {model_name}")
        try:
            from .local_llm_provider import LocalLLMProvider
            
            # Create temporary config overriding the model_name and including local settings
            temp_config = self.config.copy()
            temp_config['model_name'] = model_name
            temp_config.setdefault('decision_engine', {})
            temp_config['decision_engine']['local_models'] = self.local_models
            temp_config['decision_engine']['local_priority'] = self.local_priority
            
            provider = LocalLLMProvider(temp_config)
            response = provider.query(prompt)
            return response
        except Exception as e:
            logger.warning(f"Local model {model_name} failed: {e}")
            return self._rule_based_decision(prompt)


    def _create_decision_context(
        self,
        asset_pair: str,
        market_data: Dict[str, Any],
        balance: Dict[str, float],
        portfolio: Optional[Dict[str, Any]] = None,
        memory_context: Optional[Dict[str, Any]] = None,
        monitoring_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create context for decision making.

        Args:
            asset_pair: Asset pair
            market_data: Market data
            balance: Balances
            portfolio: Optional portfolio breakdown
            memory_context: Optional historical performance context
            monitoring_context: Optional live monitoring context

        Returns:
            Decision context
        """
        context = {
            'asset_pair': asset_pair,
            'market_data': market_data,
            'balance': balance,
            'portfolio': portfolio,
            'memory_context': memory_context,
            'monitoring_context': monitoring_context,
            'timestamp': datetime.utcnow().isoformat(),
            'price_change': self._calculate_price_change(market_data),
            'volatility': self._calculate_volatility(market_data)
        }

        # Detect market regime using historical data
        regime = self._detect_market_regime(asset_pair)
        context['regime'] = regime

        # --- Inject multi-timeframe pulse context (if internal TradeMonitor running) ---
        try:
            if self.monitoring_provider and getattr(self.monitoring_provider, 'trade_monitor', None):
                tm = self.monitoring_provider.trade_monitor
                if tm:
                    mt_ctx = tm.get_latest_market_context(asset_pair)
                    if mt_ctx:
                        context['multi_timeframe_trend'] = mt_ctx.get('trend_alignment', {})
                        context['multi_timeframe_entry_signals'] = mt_ctx.get('entry_signals', {})
                        context['multi_timeframe_sources'] = mt_ctx.get('data_sources', {})
                        # Data source path (ordered list of providers actually used per timeframe)
                        ds_map = mt_ctx.get('data_sources', {})
                        context['data_source_path'] = [v for _, v in sorted(ds_map.items())]
                        # Pulse age seconds (approximate)
                        try:
                            import time
                            pulse_age = time.time() - tm._last_pulse_time
                        except Exception:
                            pulse_age = None
                        context['monitor_pulse_age_seconds'] = pulse_age
        except Exception as e:
            logger.debug(f"Multi-timeframe injection failed: {e}")

        # --- Inject real VaR & correlation analysis ---
        try:
            from finance_feedback_engine.risk.var_calculator import VaRCalculator
            from finance_feedback_engine.risk.correlation_analyzer import CorrelationAnalyzer
            var_calc = VaRCalculator()
            corr_analyzer = CorrelationAnalyzer()
            # Portfolio breakdowns for dual-platform risk (if available)
            coinbase_holdings = portfolio.get('coinbase_holdings', {}) if portfolio else {}
            coinbase_history = portfolio.get('coinbase_price_history', {}) if portfolio else {}
            oanda_holdings = portfolio.get('oanda_holdings', {}) if portfolio else {}
            oanda_history = portfolio.get('oanda_price_history', {}) if portfolio else {}
            # Compute VaR (95% and 99%)
            var_95 = var_calc.calculate_dual_portfolio_var(
                coinbase_holdings, coinbase_history, oanda_holdings, oanda_history, confidence_level=0.95
            )
            var_99 = var_calc.calculate_dual_portfolio_var(
                coinbase_holdings, coinbase_history, oanda_holdings, oanda_history, confidence_level=0.99
            )
            context['var_snapshot'] = {
                'portfolio_value': var_95.get('total_portfolio_value', 0.0),
                'var_95': var_95['combined_var']['var_usd'] if 'combined_var' in var_95 else 0.0,
                'var_99': var_99['combined_var']['var_usd'] if 'combined_var' in var_99 else 0.0,
                'data_quality': var_95.get('coinbase_var', {}).get('data_quality', 'unknown')
            }
            # Correlation analysis
            correlation_result = corr_analyzer.analyze_dual_platform_correlations(
                coinbase_holdings, coinbase_history, oanda_holdings, oanda_history
            )
            context['correlation_alerts'] = correlation_result.get('overall_warnings', [])
            context['correlation_summary'] = corr_analyzer.format_correlation_summary(correlation_result)
        except Exception as e:
            logger.debug(f"Risk context injection failed: {e}")
            # Fallback to placeholder if error
            port_val = 0.0
            if portfolio:
                port_val = portfolio.get('total_value_usd', 0.0)
            context['var_snapshot'] = {
                'portfolio_value': port_val,
                'var_95': 0.0,
                'var_99': 0.0,
                'data_quality': 'placeholder'
            }
            context['correlation_alerts'] = []
            context['correlation_summary'] = ''

        return context

    def _detect_market_regime(self, asset_pair: str) -> str:
        """
        Detect the current market regime using historical data.

        Args:
            asset_pair: Asset pair to analyze

        Returns:
            Market regime string
        """
        if not self.data_provider:
            logger.warning("No data provider available for regime detection")
            return "UNKNOWN"

        try:
            # Get last 30 days of historical data
            end_date = datetime.utcnow().date()
            start_date = end_date - timedelta(days=30)
            
            historical_data = self.data_provider.get_historical_data(
                asset_pair,
                start_date.strftime("%Y-%m-%d"),
                end_date.strftime("%Y-%m-%d")
            )
            
            if not historical_data or len(historical_data) < 14:
                logger.warning("Insufficient historical data for regime detection")
                return "UNKNOWN"
            
            # Create detector and detect regime
            detector = MarketRegimeDetector()
            # Convert list of dicts to DataFrame
            if isinstance(historical_data, list):
                df = pd.DataFrame(historical_data)
            else:
                df = historical_data
            regime = detector.detect_regime(df)
            
            logger.info("Detected market regime: %s", regime)
            return regime
            
        except Exception as e:
            logger.error("Error detecting market regime: %s", e)
            return "UNKNOWN"

    def _calculate_price_change(self, market_data: Dict[str, Any]) -> float:
        """Calculate price change percentage."""
        open_price = market_data.get('open', 0)
        close_price = market_data.get('close', 0)
        
        if open_price == 0:
            return 0.0
        
        return ((close_price - open_price) / open_price) * 100

    def _calculate_volatility(self, market_data: Dict[str, Any]) -> float:
        """Calculate simple volatility indicator."""
        high = market_data.get('high', 0)
        low = market_data.get('low', 0)
        close = market_data.get('close', 0)
        
        if close == 0:
            return 0.0
        
        return ((high - low) / close) * 100

    def calculate_position_size(
        self,
        account_balance: float,
        risk_percentage: float = 0.01,
        entry_price: float = 0,
        stop_loss_percentage: float = 0.02
    ) -> float:
        """
        Calculate appropriate position size based on risk management.

        Args:
            account_balance: Total account balance
            risk_percentage: Percentage of account to risk as decimal fraction (default 0.01 = 1%)
            entry_price: Entry price for the position
            stop_loss_percentage: Stop loss distance as decimal fraction (default 0.02 = 2%)

        Returns:
            Suggested position size in units of asset
        """
        if entry_price == 0 or stop_loss_percentage == 0:
            return 0.0
        
        # Amount willing to risk in dollar terms
        risk_amount = account_balance * risk_percentage
        
        # Price distance of stop loss
        stop_loss_distance = entry_price * stop_loss_percentage
        
        # Position size = Risk Amount / Stop Loss Distance
        position_size = risk_amount / stop_loss_distance
        
        return position_size

    def calculate_pnl(
        self,
        entry_price: float,
        current_price: float,
        position_size: float,
        position_type: str = 'LONG',
        unrealized: bool = False,
    ) -> Dict[str, float]:
        """
        Calculate profit and loss for a position.

        Args:
            entry_price: Price at which position was entered
            current_price: Current market price
            position_size: Size of the position
            position_type: 'LONG' or 'SHORT'
            unrealized: Whether the P&L is unrealized (open position)

        Returns:
            Dictionary with P&L metrics
        """
        if entry_price == 0:
            return {
                'pnl_dollars': 0.0,
                'pnl_percentage': 0.0,
                'unrealized': unrealized
            }
        
        if position_type.upper() == 'LONG':
            # Long: profit when price rises
            pnl_dollars = (current_price - entry_price) * position_size
            pnl_percentage = ((current_price - entry_price) / entry_price) * 100
        else:  # SHORT
            # Short: profit when price falls
            pnl_dollars = (entry_price - current_price) * position_size
            pnl_percentage = ((entry_price - current_price) / entry_price) * 100
        
        return {
            'pnl_dollars': pnl_dollars,
            'pnl_percentage': pnl_percentage,
            'unrealized': unrealized
        }

    def _create_ai_prompt(self, context: Dict[str, Any]) -> str:
        """
        Create AI prompt for decision making.

        Args:
            context: Decision context

        Returns:
            AI prompt string
        """
        asset_pair = context['asset_pair']
        market_data = context['market_data']
        balance = context['balance']
        price_change = context['price_change']
        volatility = context['volatility']

        # Build comprehensive market data section
        market_info = f"""Asset Pair: {asset_pair}
Asset Type: {market_data.get('type', 'unknown')}
Date: {market_data.get('date', 'N/A')}

PRICE DATA:
-----------
Open: ${market_data.get('open', 0):.2f}
High: ${market_data.get('high', 0):.2f}
Low: ${market_data.get('low', 0):.2f}
Close: ${market_data.get('close', 0):.2f}
Price Change: {price_change:.2f}%
Price Range: ${market_data.get('price_range', 0):.2f} ({market_data.get('price_range_pct', 0):.2f}%)

CANDLESTICK ANALYSIS:
---------------------
Trend: {market_data.get('trend', 'neutral')}
Body Size: ${market_data.get('body_size', 0):.2f} ({market_data.get('body_pct', 0):.2f}% of close)
Upper Wick: ${market_data.get('upper_wick', 0):.2f}
Lower Wick: ${market_data.get('lower_wick', 0):.2f}
Close Position: {market_data.get('close_position_in_range', 0.5):.1%} in daily range
"""

        # Add volume/market cap for crypto
        if market_data.get('type') == 'crypto':
            market_info += f"""
VOLUME & MARKET DATA:
---------------------
Volume: {market_data.get('volume', 0):,.0f}
Market Cap: ${market_data.get('market_cap', 0):,.0f}
"""

        # Add technical indicators if available
        if 'rsi' in market_data:
            market_info += f"""
TECHNICAL INDICATORS:
---------------------
RSI (14): {market_data.get('rsi', 0):.2f} ({market_data.get('rsi_signal', 'neutral')})
"""

        # Add news sentiment if available
        if 'sentiment' in market_data and market_data['sentiment'].get('available'):
            sentiment = market_data['sentiment']
            market_info += f"""
NEWS SENTIMENT ANALYSIS:
------------------------
Overall Sentiment: {sentiment.get('overall_sentiment', 'neutral').upper()}
Sentiment Score: {sentiment.get('sentiment_score', 0):.3f} (range: -1 to +1)
News Articles Analyzed: {sentiment.get('news_count', 0)}
Top Topics: {', '.join(sentiment.get('top_topics', [])[:3]) if sentiment.get('top_topics') else 'N/A'}

Sentiment Interpretation:
- Positive (>0.15): Bullish news momentum
- Negative (<-0.15): Bearish news momentum  
- Neutral (-0.15 to 0.15): Mixed or balanced coverage
"""

        # Add macroeconomic indicators if available
        if 'macro' in market_data and market_data['macro'].get('available'):
            macro = market_data['macro']
            market_info += f"""
MACROECONOMIC CONTEXT:
----------------------
"""
            for indicator, data in macro.get('indicators', {}).items():
                readable_name = indicator.replace('_', ' ').title()
                market_info += f"{readable_name}: {data.get('value')} (as of {data.get('date')})\n"
            
            market_info += """
Macro Impact Considerations:
- High inflation: May favor real assets (crypto/commodities) over fiat
- Rising rates: Typically bearish for risk assets
- Strong GDP: Generally positive for markets
- High unemployment: May signal economic weakness
"""

        # Add volatility analysis
        market_info += f"""
VOLATILITY ANALYSIS:
--------------------
Intraday Volatility: {volatility:.2f}%
"""

        # Add portfolio information if available
        portfolio = context.get('portfolio')
        if portfolio and portfolio.get('holdings'):
            total_value = portfolio.get('total_value_usd', 0)
            num_assets = portfolio.get('num_assets', 0)
            unrealized_pnl = portfolio.get('unrealized_pnl')

            market_info += """
CURRENT PORTFOLIO:
------------------
"""
            market_info += (
                f"Total Portfolio Value: ${total_value:,.2f}\n"
                f"Number of Assets: {num_assets}\n"
            )
            if unrealized_pnl is not None:
                market_info += f"Unrealized P&L: ${unrealized_pnl:,.2f}\n"

            market_info += "\nHoldings:\n"
            for holding in portfolio.get('holdings', []):
                currency = holding.get('currency')
                amount = holding.get('amount', 0)
                value_usd = holding.get('value_usd', 0)
                allocation = holding.get('allocation_pct', 0)
                market_info += (
                    f"  {currency}: {amount:.6f} "
                    f"(${value_usd:,.2f} - {allocation:.1f}%)\n"
                )
            
            # Check if we already hold the asset being analyzed
            asset_base = asset_pair.replace('USD', '').replace('USDT', '')
            current_holding = None
            for holding in portfolio.get('holdings', []):
                if holding.get('currency') == asset_base:
                    current_holding = holding
                    break
            
            if current_holding:
                market_info += f"""
EXISTING POSITION IN {asset_base}:
Amount: {current_holding.get('amount', 0):.6f}
Current Value: ${current_holding.get('value_usd', 0):,.2f}
Allocation: {current_holding.get('allocation_pct', 0):.1f}%
"""
        
        # Add portfolio memory context if available
        memory_context = context.get('memory_context')
        if memory_context and memory_context.get('has_history'):
            memory_text = self._format_memory_context(memory_context)
            market_info += f"\n{memory_text}\n"
        
        # Add live monitoring context if available
        monitoring_context = context.get('monitoring_context')
        if monitoring_context and monitoring_context.get('has_monitoring_data'):
            monitoring_text = self.monitoring_provider.format_for_ai_prompt(
                monitoring_context
            )
            market_info += f"\n{monitoring_text}\n"

        # Add historical similarity analysis if available
        semantic_memory = context.get('semantic_memory')
        if semantic_memory:
            similarity_text = self._format_semantic_memory(semantic_memory)
            market_info += f"\n{similarity_text}\n"

        # Prepend market regime if available
        regime = context.get('regime', 'UNKNOWN')
        regime_prefix = ""
        if regime != 'UNKNOWN':
            regime_prefix = f"CURRENT MARKET REGIME: {regime}. Adjust your strategy to favor trend-following indicators.\n\n"

        prompt = f"""{regime_prefix}You are an educational trading analysis system demonstrating technical and fundamental market analysis for learning purposes.

TASK: Analyze the following market data and demonstrate what a technical analysis would suggest. This is for educational/research purposes only, not actual financial advice.

{market_info}

Account Balance: {balance}

EDUCATIONAL CONTEXT - Trading Position Types:
=============================================
This analysis will demonstrate understanding of LONG and SHORT position mechanics for educational purposes.

A LONG position represents buying an asset with expectation of price appreciation:
- Entry: BUY action when technical indicators suggest bullish momentum
- Exit: SELL action to close position
- Profit scenario: When price rises above entry price
- Loss scenario: When price falls below entry price
- Formula: P&L = (Exit Price - Entry Price) × Position Size

A SHORT position represents selling an asset with expectation of price depreciation:
- Entry: SELL action when technical indicators suggest bearish momentum
- Exit: BUY action to close/cover position
- Profit scenario: When price falls below entry price
- Loss scenario: When price rises above entry price
- Formula: P&L = (Entry Price - Exit Price) × Position Size

POSITION SIZING CALCULATION (Educational):
==========================================
Position sizing demonstrates risk management principles for INDIVIDUAL TRADES:
1. Risk tolerance (typically 1-2% of account balance per trade)
2. Stop-loss distance: Price level where you exit if wrong for an individual trade.
3. Volatility consideration (higher volatility = smaller position)
4. Account preservation (never risk entire capital on one trade)
Formula: Position Size = (Account Balance × Risk %) / (Entry Price × Stop Loss %)

OVERALL PORTFOLIO RISK MANAGEMENT:
==================================
The system aims to manage the ENTIRE PORTFOLIO'S risk and reward, not just individual trades.
- Portfolio Stop-Loss: {self.portfolio_stop_loss_percentage:.2%} maximum acceptable loss for the entire portfolio.
- Portfolio Take-Profit: {self.portfolio_take_profit_percentage:.2%} target profit for the entire portfolio.
These overall limits should influence the conservativeness of individual trade recommendations.


PROFIT & LOSS CALCULATION (Educational):
========================================
For LONG: P&L = (Current Price - Entry Price) / Entry Price × 100%
For SHORT: P&L = (Entry Price - Current Price) / Entry Price × 100%
Unrealized P&L: Open positions (not yet closed)
Realized P&L: Closed positions (actual profit/loss)

TECHNICAL ANALYSIS FRAMEWORK:
=============================
Demonstrate analysis considering:
- Candlestick patterns (long wicks suggest rejection, large body suggests conviction)
- Close position in range (near high = bullish signal, near low = bearish signal)
- RSI levels (>70 overbought, <30 oversold, if provided)
- Volatility metrics (high volatility = higher risk assessment)
- Volume trends (for crypto, if provided)
- Overall trend direction
- News sentiment (bullish/bearish/neutral, if provided)
- Sentiment score magnitude (stronger scores = stronger signals)
- Macroeconomic context (inflation, rates, GDP, if provided)
- Macro headwinds/tailwinds for the asset class

Signal Integration Framework:
- Bullish sentiment + positive technicals = strong buy signal
- Bearish sentiment + negative technicals = strong sell signal
- Conflicting signals (e.g., bullish technicals, bearish sentiment) = caution/hold signal
- High inflation/rates may favor crypto over fiat currencies
- Economic weakness may indicate risk-off behavior

ANALYSIS OUTPUT REQUIRED:
=========================
Demonstrate a technical analysis for {asset_pair} showing:
1. Signal Type: BUY (long signal), SELL (short signal), or HOLD (neutral)
2. Signal Strength: 0-100% (how strong the technical indicators align)
3. Technical Reasoning: Brief explanation of what the indicators show (reference long/short mechanics)
4. Example Position Size: Demonstrate position sizing calculation for risk management education

Format response as a structured technical analysis demonstration.
"""
        return prompt
    
    def _format_semantic_memory(self, semantic_memory: List[Tuple[str, float, Dict[str, Any]]]) -> str:
        """
        Format semantic memory for AI prompt.
        
        Args:
            semantic_memory: List of tuples (decision_id, similarity_score, metadata)
            
        Returns:
            Formatted string for prompt
        """
        if not semantic_memory:
            return ""
        
        lines = [
            "=" * 60,
            "HISTORICAL SIMILARITY ANALYSIS",
            "=" * 60,
        ]
        
        for i, (decision_id, similarity, metadata) in enumerate(semantic_memory, 1):
            decision = metadata.get('decision', {})
            outcome = metadata.get('outcome', {})
            
            # Extract key info
            date = decision.get('market_data', {}).get('date', 'N/A')
            action = decision.get('action', 'HOLD')
            was_profitable = outcome.get('was_profitable', False)
            pnl_percentage = outcome.get('pnl_percentage', 0.0)
            
            # Format outcome
            if was_profitable:
                outcome_str = f"WON (+{pnl_percentage:.1f}%)"
            else:
                outcome_str = f"LOST ({pnl_percentage:.1f}%)"
            
            # Extract context from market_data in decision
            market_data = decision.get('market_data', {})
            trend = market_data.get('trend', 'neutral')
            rsi = market_data.get('rsi', 'N/A')
            context_parts = []
            if trend != 'neutral':
                context_parts.append(f"{trend.title()} trend")
            if rsi != 'N/A':
                context_parts.append(f"RSI {rsi:.0f}")
            context_str = ", ".join(context_parts) if context_parts else "Neutral conditions"
            
            # Format the match line
            match_line = f"match_{i}: [Sim: {similarity:.2f}] ({date}) -> We {action.upper()} and {outcome_str}. Context: {context_str}."
            lines.append(match_line)
        
        # Add the instruction
        lines.extend([
            "",
            "If the retrieved historical trades resulted in losses (❌), be highly skeptical of a similar setup today."
        ])
        
        return "\n".join(lines)
    
    def _format_memory_context(self, memory_context: Dict[str, Any]) -> str:
        """
        Format memory context for AI prompt.
        
        Args:
            memory_context: Memory context from PortfolioMemoryEngine
        
        Returns:
            Formatted string for prompt
        """
        lines = [
            "",
            "=" * 60,
            "PORTFOLIO MEMORY & LEARNING CONTEXT",
            "=" * 60,
            f"Historical Trades: {memory_context.get('total_historical_trades', 0)}",
            f"Recent Trades Analyzed: {memory_context.get('recent_trades_analyzed', 0)}",
            "",
        ]
        
        # Long-term performance (e.g., 90 days)
        long_term = memory_context.get('long_term_performance', {})
        if long_term and long_term.get('has_data'):
            period_days = long_term.get('period_days', 90)
            lines.extend([
                f"LONG-TERM PERFORMANCE ({period_days} days):",
                "-" * 60,
                f"  Total Realized P&L: "
                f"${long_term.get('realized_pnl', 0):.2f}",
                f"  Total Trades: {long_term.get('total_trades', 0)}",
                f"  Win Rate: {long_term.get('win_rate', 0):.1f}%",
                f"  Profit Factor: {long_term.get('profit_factor', 0):.2f}",
                f"  ROI: {long_term.get('roi_percentage', 0):.1f}%",
                "",
                f"  Average Win: ${long_term.get('avg_win', 0):.2f}",
                f"  Average Loss: ${long_term.get('avg_loss', 0):.2f}",
                f"  Best Trade: ${long_term.get('best_trade', 0):.2f}",
                f"  Worst Trade: ${long_term.get('worst_trade', 0):.2f}",
                "",
                f"  Recent Momentum: "
                f"{long_term.get('recent_momentum', 'N/A')}",
            ])
            
            sharpe = long_term.get('sharpe_ratio')
            if sharpe is not None:
                lines.append(f"  Sharpe Ratio: {sharpe:.2f}")
            
            avg_holding = long_term.get('average_holding_hours')
            if avg_holding is not None:
                lines.append(
                    f"  Average Holding Period: {avg_holding:.1f} hours"
                )
            
            lines.append("")
        
        # Recent performance
        lines.append("Recent Performance:")
        recent_perf = memory_context.get('recent_performance', {})
        lines.append(
            f"  Win Rate: {recent_perf.get('win_rate', 0):.1f}%"
        )
        lines.append(
            f"  Total P&L: ${recent_perf.get('total_pnl', 0):.2f}"
        )
        lines.append(
            f"  Wins: {recent_perf.get('winning_trades', 0)}, "
            f"Losses: {recent_perf.get('losing_trades', 0)}"
        )
        
        # Current streak
        streak = memory_context.get('current_streak', {})
        if streak.get('type'):
            lines.append(
                f"  Current Streak: {streak.get('count', 0)} "
                f"{streak.get('type', '')} trades"
            )
        
        # Action performance
        action_perf = memory_context.get('action_performance', {})
        if action_perf:
            lines.append("")
            lines.append("Historical Action Performance:")
            for action, stats in action_perf.items():
                lines.append(
                    f"  {action}: {stats.get('win_rate', 0):.1f}% win rate, "
                    f"${stats.get('total_pnl', 0):.2f} P&L "
                    f"({stats.get('count', 0)} trades)"
                )
        
        # Asset-specific history
        if memory_context.get('asset_specific'):
            asset_stats = memory_context['asset_specific']
            lines.append("")
            lines.append(
                f"{memory_context.get('asset_pair', 'This Asset')} "
                f"Historical Performance:"
            )
            lines.append(
                f"  {asset_stats.get('total_trades', 0)} trades, "
                f"{asset_stats.get('win_rate', 0):.1f}% win rate, "
                f"${asset_stats.get('total_pnl', 0):.2f} total P&L"
            )
        
        lines.append("=" * 60)
        lines.append("")
        
        # Performance-based guidance for AI
        if long_term and long_term.get('has_data'):
            lines.append(
                "PERFORMANCE GUIDANCE FOR DECISION:"
            )
            
            # Check if long-term performance is poor
            lt_pnl = long_term.get('realized_pnl', 0)
            lt_win_rate = long_term.get('win_rate', 50)
            momentum = long_term.get('recent_momentum', 'stable')
            
            if lt_pnl < 0 and lt_win_rate < 45:
                lines.append(
                    "⚠ CAUTION: Long-term performance is negative. "
                    "Consider being more conservative."
                )
            elif lt_pnl > 0 and lt_win_rate > 60:
                lines.append(
                    "✓ Long-term performance is strong. "
                    "Current strategy is working well."
                )
            
            if momentum == 'declining':
                lines.append(
                    "⚠ Performance momentum is DECLINING. "
                    "Recent trades performing worse than earlier ones."
                )
            elif momentum == 'improving':
                lines.append(
                    "✓ Performance momentum is IMPROVING. "
                    "Recent trades performing better."
                )
            
            lines.append("")
        
        lines.append(
            "IMPORTANT: Consider this historical performance when making "
            "your recommendation."
        )
        lines.append(
            "If recent performance is poor, consider being more conservative."
        )
        lines.append(
            "If specific actions (BUY/SELL) have performed poorly, factor "
            "that into your decision."
        )
        lines.append("")
        
        return "\n".join(lines)

    def _query_ai(self, prompt: str) -> Dict[str, Any]:
        """
        Query the AI model for a decision.

        Args:
            prompt: AI prompt

        Returns:
            AI response
        """
        logger.info(f"Querying AI provider: {self.ai_provider}")
        
        # Ensemble mode: query multiple providers and aggregate
        if self.ai_provider == 'ensemble':
            return self._ensemble_ai_inference(prompt)
        
        # Route to appropriate single provider
        if self.ai_provider == 'local':
            return self._local_ai_inference(prompt)
        elif self.ai_provider == 'cli':
            return self._cli_ai_inference(prompt)
        elif self.ai_provider == 'codex':
            return self._codex_ai_inference(prompt)
        elif self.ai_provider == 'qwen':
            return self._qwen_ai_inference(prompt)
        # elif self.ai_provider == 'gemini':
        #     return self._gemini_ai_inference(prompt)
        else:
            return self._rule_based_decision(prompt)

    def _local_ai_inference(self, prompt: str) -> Dict[str, Any]:
        """
        Local AI inference using Ollama LLM.

        Args:
            prompt: AI prompt

        Returns:
            AI response from local LLM
        """
        logger.info("Using local LLM AI inference (Ollama)")
        
        try:
            from .local_llm_provider import LocalLLMProvider
            
            provider = LocalLLMProvider(self.config)
            return provider.query(prompt)
        except (ImportError, RuntimeError) as e:
            logger.warning(f"Local LLM unavailable, using rule-based fallback: {e}")
            return self._rule_based_decision(prompt)

    def _cli_ai_inference(self, prompt: str) -> Dict[str, Any]:
        """
        CLI-based AI inference using GitHub Copilot CLI.

        Args:
            prompt: AI prompt

        Returns:
            AI response from Copilot CLI
        """
        logger.info("Using GitHub Copilot CLI AI inference")
        
        try:
            from .copilot_cli_provider import CopilotCLIProvider
            
            provider = CopilotCLIProvider(self.config)
            return provider.query(prompt)
        except (ImportError, ValueError) as e:
            logger.warning(f"Copilot CLI unavailable, using fallback: {e}")
            return {
                'action': 'HOLD',
                'confidence': 50,
                'reasoning': 'Copilot CLI unavailable, using fallback decision.',
                'amount': 0
            }

    def _codex_ai_inference(self, prompt: str) -> Dict[str, Any]:
        """
        CLI-based AI inference using Codex CLI.

        Args:
            prompt: AI prompt

        Returns:
            AI response from Codex CLI
        """
        logger.info("Using Codex CLI AI inference")
        
        try:
            from .codex_cli_provider import CodexCLIProvider
            
            provider = CodexCLIProvider(self.config)
            return provider.query(prompt)
        except (ImportError, ValueError) as e:
            logger.warning(f"Codex CLI unavailable, using fallback: {e}")
            return {
                'action': 'HOLD',
                'confidence': 50,
                'reasoning': 'Codex CLI unavailable, using fallback decision.',
                'amount': 0
            }

    def _qwen_ai_inference(self, prompt: str) -> Dict[str, Any]:
        """
        CLI-based AI inference using Qwen CLI.

        Args:
            prompt: AI prompt

        Returns:
            AI response from Qwen CLI
        """
        logger.info("Using Qwen CLI AI inference")
        
        try:
            from .qwen_cli_provider import QwenCLIProvider
            
            provider = QwenCLIProvider(self.config)
            return provider.query(prompt)
        except (ImportError, ValueError) as e:
            logger.warning(f"Qwen CLI unavailable, using fallback: {e}")
            return {
                'action': 'HOLD',
                'confidence': 50,
                'reasoning': 'Qwen CLI unavailable, using fallback decision.',
                'amount': 0
            }

    # def _gemini_ai_inference(self, prompt: str) -> Dict[str, Any]:
    #     """
    #     CLI-based AI inference using Gemini CLI.
    #
    #     Args:
    #         prompt: AI prompt
    #
    #     Returns:
    #         AI response from Gemini CLI
    #     """
    #     logger.info("Using Gemini CLI AI inference")
    #     
    #     try:
    #         from .gemini_cli_provider import GeminiCLIProvider
    #         
    #         provider = GeminiCLIProvider(self.config)
    #         return provider.query(prompt)
    #     except (ImportError, ValueError) as e:
    #         logger.warning(f"Gemini CLI unavailable, using fallback: {e}")
    #         return {
    #             'action': 'HOLD',
    #             'confidence': 50,
    #             'reasoning': 'Gemini CLI unavailable, using fallback.',
    #             'amount': 0
    #         }

    def _get_all_local_models(self) -> list[str]:
        """Get a list of all available local Ollama models."""
        try:
            result = subprocess.run(
                ['ollama', 'list'],
                capture_output=True,
                text=True,
                timeout=10,
                check=False
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if len(lines) <= 1:
                    return []
                
                # First line is header, skip it
                model_lines = lines[1:]
                
                # Extract model name from each line (first column)
                model_names = [line.split()[0] for line in model_lines if line]
                logger.info(f"Discovered local models: {model_names}")
                return model_names
            else:
                logger.warning("Could not list local models, 'ollama list' failed.")
                return []
        except FileNotFoundError:
            logger.warning("Ollama command not found, cannot discover local models.")
            return []
        except Exception as e:
            logger.error(f"Error discovering local models: {e}")
            return []

    def _query_single_provider(self, provider: str, prompt: str) -> Tuple[str, Optional[Dict[str, Any]]]:
        """
        Query a single AI provider and handle its response.

        Args:
            provider: The name of the provider to query.
            prompt: The prompt to send to the provider.

        Returns:
            A tuple of (provider_name, decision_dict) or (provider_name, None) on failure.
        """
        try:
            decision = None
            local_provider_map = (
                self.config.get('local_providers')
                if isinstance(self.config.get('local_providers'), dict)
                else {}
            )
            all_discovered_local_models = self._get_all_local_models()

            # Consult configured local_models first
            if provider in self.local_models:
                decision = self._specific_local_inference(prompt, provider)
            elif provider == 'local' and self.local_models:
                decision = self._specific_local_inference(prompt, self.local_models[0])
            elif provider == 'local':
                if 'local' in local_provider_map:
                    model_name = local_provider_map['local']
                    decision = self._specific_local_inference(prompt, model_name)
                else:
                    decision = self._local_ai_inference(prompt)
            elif provider in local_provider_map:
                model_name = local_provider_map[provider]
                decision = self._specific_local_inference(prompt, model_name)
            elif provider in all_discovered_local_models:
                decision = self._specific_local_inference(prompt, provider)
            elif provider == 'cli':
                decision = self._cli_ai_inference(prompt)
            elif provider == 'codex':
                decision = self._codex_ai_inference(prompt)
            elif provider == 'qwen':
                decision = self._qwen_ai_inference(prompt)
            else:
                logger.warning(f"Unknown provider: {provider}")
                return provider, None

            if decision is None:
                logger.warning(f"Provider {provider} did not return a decision.")
                return provider, None

            if self._is_valid_provider_response(decision, provider):
                logger.info(
                    f"{provider}: {decision['action']} "
                    f"({decision['confidence']}%)"
                )
                return provider, decision
            else:
                logger.warning(
                    f"Provider {provider} returned fallback/invalid "
                    f"response, treating as failure"
                )
                return provider, None
        except Exception as e:
            logger.warning(f"Provider {provider} failed: {e}")
            return provider, None

    def _ensemble_ai_inference(self, prompt: str) -> Dict[str, Any]:
        """
        Ensemble AI inference using multiple providers with weighted voting.
        Dynamically adjusts weights when providers fail to respond.

        Args:
            prompt: AI prompt

        Returns:
            Aggregated decision from ensemble with failure handling
        """
        logger.info("Using ensemble AI inference")
        
        if not self.ensemble_manager:
            logger.error("Ensemble manager not initialized")
            return self._rule_based_decision(prompt)
        
        # Check for debate mode
        if self.ensemble_manager.debate_mode:
            return self._debate_ai_inference(prompt)
        
        # Get enabled providers from ensemble config
        enabled_providers = self.ensemble_manager.enabled_providers.copy()
        
        all_discovered_local_models = self._get_all_local_models()

        # Discover and add all available local models if 'all_local' is specified
        if 'all_local' in enabled_providers:
            enabled_providers.remove('all_local')
            for model_name in all_discovered_local_models:
                if model_name not in enabled_providers:
                    enabled_providers.append(model_name)

        # If 'local' is configured, expand it into specific local model names
        # so the ensemble queries both the primary and the required secondary
        # local models (if available or configured).
        if 'local' in enabled_providers:
            try:
                # Import here to avoid top-level import cycles
                from .local_llm_provider import LocalLLMProvider

                primary_model = LocalLLMProvider.DEFAULT_MODEL
                secondary_model = getattr(
                    LocalLLMProvider, 'SECONDARY_MODEL', None
                )
            except Exception:
                # Fallback to known defaults if import fails
                primary_model = 'llama3.2:3b-instruct-fp16'
                secondary_model = 'deepseek-r1:8b'

            # Remove the abstract 'local' provider and replace with actual
            # model names
            enabled_providers = [p for p in enabled_providers if p != 'local']

            # If user provided a mapping for local_providers, prefer that
            local_provider_map = (
                self.config.get('local_providers')
                if isinstance(self.config.get('local_providers'), dict)
                else {}
            )
            mapped_local = local_provider_map.get('local')
            if mapped_local:
                if mapped_local not in enabled_providers:
                    enabled_providers.append(mapped_local)
            else:
                # Append primary and secondary model names
                if primary_model and primary_model not in enabled_providers:
                    enabled_providers.append(primary_model)
                if (
                    secondary_model
                    and secondary_model not in enabled_providers
                ):
                    enabled_providers.append(secondary_model)
        
        provider_decisions = {}
        failed_providers = []

        # Partition providers into local (GPU-bound) and remote groups
        local_candidates = []
        if self.local_models:
            for model in self.local_models:
                if model in enabled_providers:
                    local_candidates.append(model)
        else:
            local_provider_map = (
                self.config.get('local_providers')
                if isinstance(self.config.get('local_providers'), dict)
                else {}
            )
            all_discovered_local_models = self._get_all_local_models()
            local_candidates = [
                p for p in enabled_providers
                if p == 'local' or p in local_provider_map or p in all_discovered_local_models
            ]
        remote_candidates = [p for p in enabled_providers if p not in local_candidates]

        # Execute remote providers concurrently with per-task timeouts
        if remote_candidates:
            logger.info(f"Querying {len(remote_candidates)} remote providers concurrently")
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                future_to_provider = {
                    executor.submit(self._query_single_provider, provider, prompt): provider
                    for provider in remote_candidates
                }
                for future in as_completed(future_to_provider):
                    provider = future_to_provider[future]
                    try:
                        provider_name, decision = future.result(timeout=10)  # per-task timeout
                        if decision:
                            provider_decisions[provider_name] = decision
                        else:
                            failed_providers.append(provider_name)
                    except TimeoutError:
                        logger.warning(f"Provider {provider} timed out")
                        failed_providers.append(provider)
                    except Exception as e:
                        logger.warning(f"Provider {provider} failed: {e}")
                        failed_providers.append(provider)

        # Execute local providers sequentially to avoid GPU memory conflicts
        if local_candidates:
            logger.info(f"Querying {len(local_candidates)} local providers sequentially")
            for provider in local_candidates:
                logger.info(f"Querying provider: {provider}")
                provider_name, decision = self._query_single_provider(provider, prompt)
                if decision:
                    provider_decisions[provider_name] = decision
                else:
                    failed_providers.append(provider_name)

        # Filter to valid provider decisions only
        valid_provider_decisions = {}
        for p, d in provider_decisions.items():
            if self._is_valid_provider_response(d, p):
                valid_provider_decisions[p] = d
            else:
                failed_providers.append(p)  # treat invalid as failed

        # Compute adjusted_weights if local_priority
        adjusted_weights = None
        if self.local_priority:
            boost_factor = 1.0
            if self.local_priority is True:
                boost_factor = 2.0
            elif isinstance(self.local_priority, (int, float)):
                boost_factor = self.local_priority
            elif self.local_priority == "soft":
                boost_factor = 1.5
            adjusted_weights = {}
            for p in valid_provider_decisions:
                base_weight = self.ensemble_manager.provider_weights.get(p, 1.0)
                if p in local_candidates:
                    adjusted_weights[p] = base_weight * boost_factor
                else:
                    adjusted_weights[p] = base_weight
            # Normalize
            total = sum(adjusted_weights.values())
            if total > 0:
                adjusted_weights = {p: w / total for p, w in adjusted_weights.items()}

        # Handle complete failure case
        if not valid_provider_decisions:
            logger.error(
                "All %d providers failed or invalid, using rule-based fallback",
                len(enabled_providers),
            )
            fallback = self._rule_based_decision(prompt)
            fallback['ensemble_metadata'] = {
                'providers_used': [],
                'providers_failed': failed_providers,
                'all_providers_failed': True,
                'fallback_used': True
            }
            return fallback
        
        # Log success/failure summary
        logger.info(
            f"Ensemble query complete: {len(valid_provider_decisions)} valid, "
            f"{len(failed_providers)} failed/invalid"
        )
        
        # Aggregate decisions with failure information
        aggregated = self.ensemble_manager.aggregate_decisions(
            valid_provider_decisions,
            failed_providers=failed_providers,
            adjusted_weights=adjusted_weights
        )
        
        # Add local metadata
        aggregated['ensemble_metadata']['local_models_used'] = [p for p in valid_provider_decisions if p in local_candidates]
        aggregated['ensemble_metadata']['local_priority_applied'] = self.local_priority is not None
        
        return aggregated

    def _debate_ai_inference(self, prompt: str) -> Dict[str, Any]:
        """
        Debate mode AI inference using bull, bear, and judge providers.
        
        Args:
            prompt: Base AI prompt with market data
            
        Returns:
            Final decision from judge provider
        """
        logger.info("Using debate mode AI inference")
        
        debate_providers = self.ensemble_manager.debate_providers
        
        # Create bull case prompt
        bull_prompt = self._create_debate_prompt(prompt, 'bull')
        bull_provider = debate_providers['bull']
        logger.info(f"Querying bull case provider: {bull_provider}")
        bull_name, bull_decision = self._query_single_provider(bull_provider, bull_prompt)
        if not bull_decision:
            logger.error(f"Bull provider {bull_provider} failed, falling back to regular ensemble")
            return self._ensemble_ai_inference(prompt)
        
        # Create bear case prompt
        bear_prompt = self._create_debate_prompt(prompt, 'bear')
        bear_provider = debate_providers['bear']
        logger.info(f"Querying bear case provider: {bear_provider}")
        bear_name, bear_decision = self._query_single_provider(bear_provider, bear_prompt)
        if not bear_decision:
            logger.error(f"Bear provider {bear_provider} failed, falling back to regular ensemble")
            return self._ensemble_ai_inference(prompt)
        
        # Create judge prompt with both cases
        judge_prompt = self._create_judge_prompt(prompt, bull_decision, bear_decision)
        judge_provider = debate_providers['judge']
        logger.info(f"Querying judge provider: {judge_provider}")
        judge_name, judge_decision = self._query_single_provider(judge_provider, judge_prompt)
        if not judge_decision:
            logger.error(f"Judge provider {judge_provider} failed, falling back to regular ensemble")
            return self._ensemble_ai_inference(prompt)
        
        # Synthesize debate decision
        final_decision = self.ensemble_manager.debate_decisions(
            bull_decision, bear_decision, judge_decision
        )
        
        return final_decision

    def _create_debate_prompt(self, base_prompt: str, role: str) -> str:
        """
        Create debate prompt for bull or bear role.
        
        Args:
            base_prompt: Base market analysis prompt
            role: 'bull' or 'bear'
            
        Returns:
            Modified prompt for the debate role
        """
        if role == 'bull':
            debate_instruction = """
DEBATE ROLE: BULLISH ADVOCATE
============================
You are arguing the BULLISH case for this asset. Focus exclusively on positive factors, technical strengths, and reasons to BUY or HOLD LONG.

Key Guidelines:
- Emphasize bullish technical indicators (RSI oversold, upward trends, support levels)
- Highlight positive news sentiment and macroeconomic tailwinds
- Argue for long positions and upward price movement
- Downplay or explain away bearish signals as temporary
- Provide strong reasoning for why the asset will RISE

Present your bullish case with confidence and conviction.
"""
        elif role == 'bear':
            debate_instruction = """
DEBATE ROLE: BEARISH ADVOCATE  
============================
You are arguing the BEARISH case for this asset. Focus exclusively on negative factors, technical weaknesses, and reasons to SELL or HOLD SHORT.

Key Guidelines:
- Emphasize bearish technical indicators (RSI overbought, downward trends, resistance levels)
- Highlight negative news sentiment and macroeconomic headwinds
- Argue for short positions and downward price movement
- Downplay or explain away bullish signals as temporary
- Provide strong reasoning for why the asset will FALL

Present your bearish case with confidence and conviction.
"""
        else:
            raise ValueError(f"Unknown debate role: {role}")
        
        # Insert debate instruction before the analysis section
        # Find the position to insert
        analysis_marker = "ANALYSIS OUTPUT REQUIRED:"
        if analysis_marker in base_prompt:
            insert_pos = base_prompt.find(analysis_marker)
            modified_prompt = (
                base_prompt[:insert_pos] + 
                debate_instruction + "\n\n" +
                base_prompt[insert_pos:]
            )
        else:
            modified_prompt = debate_instruction + "\n\n" + base_prompt
            
        return modified_prompt

    def _create_judge_prompt(self, base_prompt: str, bull_case: Dict[str, Any], bear_case: Dict[str, Any]) -> str:
        """
        Create judge prompt that includes both bull and bear cases.
        
        Args:
            base_prompt: Base market analysis prompt
            bull_case: Decision from bullish provider
            bear_case: Decision from bearish provider
            
        Returns:
            Judge prompt with debate cases
        """
        judge_instruction = """
DEBATE ROLE: IMPARTIAL JUDGE
===========================
You are the final arbiter in this debate between bullish and bearish advocates.

Your task is to evaluate both arguments and make the definitive BUY/SELL/HOLD decision.

DEBATE CASES:
=============

BULLISH CASE:
-------------
""" + bull_case.get('reasoning', 'No reasoning provided') + f"""
Action: {bull_case.get('action', 'HOLD')}
Confidence: {bull_case.get('confidence', 50)}%

BEARISH CASE:
-------------
""" + bear_case.get('reasoning', 'No reasoning provided') + f"""
Action: {bear_case.get('action', 'HOLD')}
Confidence: {bear_case.get('confidence', 50)}%

JUDGE GUIDELINES:
================
- Consider the strength of technical evidence in both cases
- Evaluate which argument better explains current market conditions
- Factor in news sentiment and macroeconomic context
- Determine which position (long/short) has stronger supporting evidence
- Make a clear BUY/SELL/HOLD decision with high confidence
- If arguments are equally compelling, consider HOLD
- Base decision on market fundamentals, not debate rhetoric

Present your judgment with clear reasoning and final decision.
"""
        
        # Replace the original analysis section with judge instruction
        analysis_marker = "ANALYSIS OUTPUT REQUIRED:"
        if analysis_marker in base_prompt:
            insert_pos = base_prompt.find(analysis_marker)
            modified_prompt = (
                base_prompt[:insert_pos] + 
                judge_instruction
            )
        else:
            modified_prompt = base_prompt + "\n\n" + judge_instruction
            
        return modified_prompt

    def _is_valid_provider_response(
        self,
        decision: Dict[str, Any],
        provider: str
    ) -> bool:
        """
        Check if provider response is valid (not a fallback).

        Args:
            decision: Decision dict from provider
            provider: Provider name

        Returns:
            True if valid response, False if fallback/invalid
        """
        # Check for fallback indicators in reasoning
        reasoning = decision.get('reasoning', '')
        if not isinstance(reasoning, str) or not reasoning.strip():
            return False
        reasoning_lower = reasoning.lower()
        fallback_keywords = [
            'unavailable',
            'fallback',
            'failed to',
            'error',
            'could not'
        ]
        
        if any(keyword in reasoning_lower for keyword in fallback_keywords):
            return False
        
        # Check for valid action
        if decision.get('action') not in ['BUY', 'SELL', 'HOLD']:
            return False
        
        # Check for valid confidence range
        confidence = decision.get('confidence', 0)
        if (
            not isinstance(confidence, (int, float)) or
            confidence < 0 or
            confidence > 100
        ):
            return False
        
        amount = decision.get('amount', 0)
        # Treat missing/None as zero, but reject negative or non-numeric
        if amount is None:
            amount = 0
        if not isinstance(amount, (int, float)):
            try:
                amount = float(amount)
            except (TypeError, ValueError):
                return False
        if amount < 0:
            return False
        
        # Normalize amount back onto the decision for downstream consumers
        decision['amount'] = float(amount)
        
        return True

    def _rule_based_decision(self, prompt: str) -> Dict[str, Any]:
        """
        Simple rule-based decision as fallback.

        Args:
            prompt: Context prompt

        Returns:
            Rule-based decision
        """
        logger.info("Using rule-based decision")
        
        # Extract price change from prompt
        if 'Price Change:' in prompt:
            try:
                price_change_line = [
                    line for line in prompt.split('\n')
                    if 'Price Change:' in line
                ][0]
                price_change = float(
                    price_change_line.split(':')[1]
                    .strip()
                    .replace('%', '')
                )
                
                if price_change > 2:
                    return {
                        'action': 'SELL',
                        'confidence': 65,
                        'reasoning': 'Price increased; taking profit.',
                        'amount': 0.1,
                    }
                elif price_change < -2:
                    return {
                        'action': 'BUY',
                        'confidence': 70,
                        'reasoning': 'Price dropped; buying opportunity.',
                        'amount': 0.1,
                    }
            except Exception as e:
                logger.error(f"Error parsing price change: {e}")
        
        return {
            'action': 'HOLD',
            'confidence': 60,
            'reasoning': 'No strong signal detected.',
            'amount': 0
        }

    def _create_decision(
        self,
        asset_pair: str,
        context: Dict[str, Any],
        ai_response: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create structured decision object.

        Args:
            asset_pair: Asset pair
            context: Decision context
            ai_response: AI recommendation

        Returns:
            Structured decision
        """
        decision_id = str(uuid.uuid4())
        
        # Logic gate: only calculate position sizing when balance data exists
        current_price = context['market_data'].get('close', 0)
        balance = context.get('balance', {})
        action = ai_response.get('action', 'HOLD')
        
        # Determine asset type (crypto vs forex) for balance selection
        asset_type = context['market_data'].get('type', 'unknown')
        is_crypto = (
            'BTC' in asset_pair
            or 'ETH' in asset_pair
            or asset_type == 'crypto'
        )
        is_forex = '_' in asset_pair or asset_type == 'forex'
        
        # Extract the appropriate balance based on asset type
        # Crypto: Use Coinbase balances (coinbase_*)
        # Forex: Use Oanda balances (oanda_*)
        relevant_balance = {}
        if balance and isinstance(balance, dict):
            if is_crypto:
                # Filter for Coinbase balances
                relevant_balance = {
                    k: v for k, v in balance.items()
                    if k.startswith('coinbase_')
                }
            elif is_forex:
                # Filter for Oanda balances
                relevant_balance = {
                    k: v for k, v in balance.items()
                    if k.startswith('oanda_')
                }
            else:
                # Unknown type, use all balances as fallback
                relevant_balance = balance
        
        # Check if relevant balance data is available and valid
        has_valid_balance = (
            relevant_balance
            and len(relevant_balance) > 0
            and sum(relevant_balance.values()) > 0
        )
        
        # Check for existing position in this asset
        portfolio = context.get('portfolio')
        asset_base = (
            asset_pair.replace('USD', '')
            .replace('USDT', '')
            .replace('_', '')
        )
        has_existing_position = False
        
        if portfolio and portfolio.get('holdings'):
            for holding in portfolio.get('holdings', []):
                if (
                    holding.get('currency') == asset_base
                    and holding.get('amount', 0) > 0
                ):
                    has_existing_position = True
                    break
        
        # Check monitoring context for active positions (futures/margin)
        monitoring_context = context.get('monitoring_context')
        if monitoring_context and not has_existing_position:
            active_positions = monitoring_context.get('active_positions', {})
            futures_positions = active_positions.get('futures', [])
            for position in futures_positions:
                if asset_pair in position.get('product_id', ''):
                    has_existing_position = True
                    break
        
        # Determine position type based on action
        position_type = (
            'LONG'
            if action == 'BUY'
            else 'SHORT'
            if action == 'SELL'
            else None
        )

        # Calculate position sizing based on action and existing position
        # HOLD: Only show position sizing if there's an existing position
        # BUY/SELL: Always calculate position sizing if balance is available
        # But skip if signal_only_default is enabled
        signal_only_default = self.config.get('signal_only_default', False)
        should_calculate_position = (
            has_valid_balance
            and not signal_only_default
            and (
                action in ['BUY', 'SELL']
                or (action == 'HOLD' and has_existing_position)
            )
        )
        
        if should_calculate_position:
            total_balance = sum(relevant_balance.values())
            balance_source = (
                'Coinbase' if is_crypto else 'Oanda' if is_forex else 'Combined'
            )
            
            # Get risk parameters from the agent config
            agent_config = self.config.get('agent', {})
            risk_percentage = agent_config.get('risk_percentage', 0.01)
            # TODO: Replace this fixed percentage with a dynamic stop-loss calculation
            # based on volatility (e.g., ATR) or market structure.
            sizing_stop_loss_percentage = agent_config.get('sizing_stop_loss_percentage', 0.02)

            # Compatibility: Convert legacy percentage values (>1) to decimals
            if risk_percentage > 1:
                logger.warning(f"Detected legacy risk_percentage {risk_percentage}%. Converting to decimal: {risk_percentage/100:.3f}")
                risk_percentage /= 100
            if sizing_stop_loss_percentage > 1:
                logger.warning(f"Detected legacy sizing_stop_loss_percentage {sizing_stop_loss_percentage}%. Converting to decimal: {sizing_stop_loss_percentage/100:.3f}")
                sizing_stop_loss_percentage /= 100

            recommended_position_size = self.calculate_position_size(
                account_balance=total_balance,
                risk_percentage=risk_percentage,
                entry_price=current_price,
                stop_loss_percentage=sizing_stop_loss_percentage
            )
            signal_only = False
            
            # Calculate the stop loss price
            stop_loss_price = 0
            if position_type == 'LONG' and current_price > 0:
                stop_loss_price = current_price * (1 - sizing_stop_loss_percentage)
            elif position_type == 'SHORT' and current_price > 0:
                stop_loss_price = current_price * (1 + sizing_stop_loss_percentage)

            if action == 'HOLD' and has_existing_position:
                logger.info(
                    "HOLD with existing position: sizing (%.4f units) from %s",
                    recommended_position_size,
                    balance_source,
                )
            else:
                logger.info(
                    "Position sizing: %.4f units (balance: $%.2f from %s, risk: %s%%, sl: %s%%)",
                    recommended_position_size,
                    total_balance,
                    balance_source,
                    risk_percentage,
                    sizing_stop_loss_percentage,
                )
        else:
            # Signal-only mode: No position sizing when balance is unavailable
            # or when HOLD without an existing position
            recommended_position_size = None
            sizing_stop_loss_percentage = None
            risk_percentage = None
            stop_loss_price = None
            signal_only = True
            
            if action == 'HOLD' and not has_existing_position:
                logger.info(
                    "HOLD without existing position - no position sizing shown"
                )
            elif signal_only_default:
                logger.info(
                    "Signal-only mode enabled by default - no position sizing shown"
                )
            elif not has_valid_balance:
                balance_type = (
                    'Coinbase'
                    if is_crypto
                    else 'Oanda'
                    if is_forex
                    else 'platform'
                )
                logger.warning(
                    "No valid %s balance for %s - providing signal only",
                    balance_type,
                    asset_pair,
                )
            else:
                logger.warning(
                    "Portfolio data unavailable - providing signal only"
                )

        # Override suggested_amount to 0 for HOLD with no position
        suggested_amount = ai_response.get('amount', 0)
        if action == 'HOLD' and not has_existing_position:
            suggested_amount = 0
            logger.debug(
                "Overriding suggested_amount to 0 (HOLD with no position)"
            )
        
        # For non-signal-only BUY/SELL, use calculated position size converted to USD notional
        if not signal_only and action in ['BUY', 'SELL'] and recommended_position_size and current_price > 0:
            # For crypto futures, position size is USD notional value when USD or USDT is quote
            if is_crypto and (asset_pair.endswith('USD') or asset_pair.endswith('USDT')):
                suggested_amount = recommended_position_size * current_price
                logger.info(
                    "Position sizing: $%.2f USD notional for crypto futures (%.6f units @ $%.2f)",
                    suggested_amount,
                    recommended_position_size,
                    current_price
                )
            else:
                # For forex or other, use unit amount
                suggested_amount = recommended_position_size
        
        decision = {
            'id': decision_id,
            'asset_pair': asset_pair,
            'timestamp': datetime.utcnow().isoformat(),
            'action': action,
            'confidence': ai_response.get('confidence', 50),
            'reasoning': ai_response.get('reasoning', 'No reasoning provided'),
            'suggested_amount': suggested_amount,
            'recommended_position_size': recommended_position_size,
            'position_type': position_type,
            'entry_price': current_price,
            'stop_loss_price': stop_loss_price,
            'stop_loss_fraction': sizing_stop_loss_percentage,
            'take_profit_percentage': None, # Individual trade TP is not explicitly set by the DecisionEngine
            'risk_percentage': risk_percentage,
            'signal_only': signal_only,
            'portfolio_stop_loss_percentage': self.portfolio_stop_loss_percentage,
            'portfolio_take_profit_percentage': self.portfolio_take_profit_percentage,
            'market_data': context['market_data'],
            'balance_snapshot': context['balance'],
            'price_change': context['price_change'],
            'volatility': context['volatility'],
            # Surface portfolio unrealized P&L if available from platform data
            'portfolio_unrealized_pnl': (
                context.get('portfolio', {}) or {}
            ).get('unrealized_pnl'),
            'executed': False,
            'ai_provider': self.ai_provider,
            'model_name': self.model_name,
            # --- Multi-timeframe and risk context fields ---
            'multi_timeframe_trend': context.get('multi_timeframe_trend'),
            'multi_timeframe_entry_signals': context.get('multi_timeframe_entry_signals'),
            'multi_timeframe_sources': context.get('multi_timeframe_sources'),
            'data_source_path': context.get('data_source_path'),
            'monitor_pulse_age_seconds': context.get('monitor_pulse_age_seconds'),
            'var_snapshot': context.get('var_snapshot'),
            'correlation_alerts': context.get('correlation_alerts'),
            'correlation_summary': context.get('correlation_summary')
        }
        
        # Add ensemble metadata if available
        if 'ensemble_metadata' in ai_response:
            decision['ensemble_metadata'] = ai_response['ensemble_metadata']
        
        # Add action_votes if available (from weighted voting)
        if 'action_votes' in ai_response:
            decision['action_votes'] = ai_response['action_votes']
        
        # Add meta_features if available (from stacking)
        if 'meta_features' in ai_response:
            decision['meta_features'] = ai_response['meta_features']
        
        logger.info(
            "Decision created: %s %s (confidence: %s%%)",
            decision['action'],
            asset_pair,
            decision['confidence'],
        )
        
        return decision
