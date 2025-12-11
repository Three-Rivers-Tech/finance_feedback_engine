"""Decision engine for generating AI-powered trading decisions."""

from typing import Dict, Any, Optional, Tuple, List
import logging
import uuid
from datetime import datetime, timedelta
import subprocess
import pandas as pd
import pytz
import asyncio

from finance_feedback_engine.utils.market_regime_detector import MarketRegimeDetector
from finance_feedback_engine.memory.vector_store import VectorMemory
from finance_feedback_engine.utils.failure_logger import send_telegram_notification
from finance_feedback_engine.utils.market_schedule import MarketSchedule
from finance_feedback_engine.utils.validation import validate_data_freshness

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

    def __init__(self, config: Dict[str, Any], data_provider=None, backtest_mode: bool = False):
        """
        Initialize the decision engine.

        Args:
            config: Configuration dictionary. Can be either:
                - Full configuration dictionary containing 'decision_engine' key with settings
                - Direct decision_engine sub-dict (for backward compatibility)
            data_provider: Data provider instance for fetching historical data
            backtest_mode: If True, use rule-based decisions instead of AI queries (faster backtesting)

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
        self.backtest_mode = backtest_mode
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

        # Initialize market schedule for session awareness
        self.market_schedule = MarketSchedule()

        # Initialize ensemble manager if using ensemble mode
        self.ensemble_manager = None
        if self.ai_provider == 'ensemble':
            self._get_ensemble_manager()
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

    def _get_ensemble_manager(self):
        """Lazily create and cache the ensemble manager."""
        if self.ensemble_manager is None:
            from .ensemble_manager import EnsembleDecisionManager
            self.ensemble_manager = EnsembleDecisionManager(self.config)
        return self.ensemble_manager

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

    async def _mock_ai_inference(self, prompt: str) -> Dict[str, Any]:
        """
        Simulate AI inference for backtesting.
        """
        logger.info("Mock AI inference")
        # Simulate some asynchronous work
        await asyncio.sleep(0.01) # Small delay to simulate async operation
        return {
            "action": "HOLD",
            "confidence": 50,
            "reasoning": "Mock decision for backtesting",
            "amount": 0.0
        }

    async def _detect_market_regime(self, asset_pair: str) -> str:
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

            # Fetch historical data (handle both sync and async providers)
            import asyncio
            historical_data_method = self.data_provider.get_historical_data(
                asset_pair,
                start_date.strftime("%Y-%m-%d"),
                end_date.strftime("%Y-%m-%d")
            )

            # Await the historical data method directly
            historical_data = await historical_data_method

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

        # Add temporal context (market schedule and data freshness)
        market_status = context.get('market_status', {})
        data_freshness = context.get('data_freshness', {})
        utc_now = datetime.utcnow().replace(tzinfo=pytz.UTC)
        ny_tz = pytz.timezone('America/New_York')
        ny_time = utc_now.astimezone(ny_tz).strftime('%Y-%m-%d %H:%M:%S %Z')
        utc_time = utc_now.strftime('%Y-%m-%d %H:%M:%S UTC')

        # Market status info
        is_open = market_status.get('is_open', True)
        session = market_status.get('session', 'Unknown')
        time_to_close = market_status.get('time_to_close', 0)
        market_warning = market_status.get('warning', '')

        # Data freshness info
        is_fresh = data_freshness.get('is_fresh', True)
        age_str = data_freshness.get('age_minutes', 'Unknown')
        freshness_msg = data_freshness.get('message', '')

        # Emoji indicators
        status_emoji = "✅" if is_open else "🔴"
        freshness_emoji = "✅" if is_fresh else "⚠️" if "WARNING" in freshness_msg else "🔴"

        # Build temporal context section
        market_info += f"""
TEMPORAL CONTEXT:
-----------------
Current Time: {utc_time} (NY: {ny_time})
Market Status: {status_emoji} {"OPEN" if is_open else "CLOSED"} ({session} Session)
Time to Close: {time_to_close} mins
Data Age: {age_str} {freshness_emoji}"""

        if market_warning:
            market_info += f"\nMarket Warning: {market_warning}"
        if freshness_msg:
            market_info += f"\nFreshness Alert: {freshness_msg}"

        market_info += """

TIME-BASED RULES (MANDATORY):
-----------------------------
1. ⚠️ If Market Status is CLOSED: You MUST recommend HOLD.
   - Rationale: Cannot execute trades when markets are closed.
   - Exception: Crypto markets (24/7) are exempt from this rule.

2. ⚠️ If Data is STALE (marked with 🔴 or ⚠️): You MUST recommend HOLD.
   - Rationale: Trading on outdated data leads to poor execution prices.
   - Fresh data is critical for accurate decision-making.

3. ⚠️ Friday Afternoon Forex Warning (if applicable):
   - Be extremely cautious of holding positions over the weekend.
   - Weekend gap risk: Markets reopen Monday with potential price jumps.
   - Prefer closing positions or reducing exposure before Friday close.

4. 📊 Session-Based Strategy Adjustments:
   - Asian Session: Expect lower volatility; favor range-bound strategies.
   - London Session: Moderate volatility; good for trend following.
   - New York Session: High volatility; peak trading activity.
   - Overlap Session (London + NY): Highest liquidity and volatility.

⚠️ CRITICAL: You MUST acknowledge the Market Status and Data Freshness in your reasoning.
   Failure to do so indicates you ignored critical temporal constraints.
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

    async def _query_ai(
        self,
        prompt: str,
        asset_pair: Optional[str] = None,
        market_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Query the AI model for a decision.

        Args:
            prompt: AI prompt
            asset_pair: Optional asset pair for two-phase routing
            market_data: Optional market data for two-phase routing

        Returns:
            AI response
        """
        logger.info(f"Querying AI provider: {self.ai_provider}")

        # Mock mode: fast random decisions for backtesting
        if self.ai_provider == 'mock':
            return await self._mock_ai_inference(prompt)

        # Ensemble mode: query multiple providers and aggregate
        if self.ai_provider == 'ensemble':
            return await self._ensemble_ai_inference(prompt, asset_pair=asset_pair, market_data=market_data)

        # Route to appropriate single provider
        if self.ai_provider == 'local':
            return await self._local_ai_inference(prompt)
        elif self.ai_provider == 'cli':
            return await self._cli_ai_inference(prompt)
        elif self.ai_provider == 'codex':
            return await self._codex_ai_inference(prompt)
        elif self.ai_provider == 'qwen':
            # Qwen CLI provider
            return await self._cli_ai_inference(prompt)
        elif self.ai_provider == 'gemini':
            return await self._gemini_ai_inference(prompt)
        else:
            raise ValueError(f"Unknown AI provider: {self.ai_provider}")

    async def _debate_mode_inference(self, prompt: str) -> Dict[str, Any]:
        """
        Execute debate mode: structured debate with bull, bear, and judge providers.

        Flow:
        1. Query bull provider (bullish stance)
        2. Query bear provider (bearish stance)
        3. Query judge provider (final decision based on debate)
        4. Synthesize decisions via ensemble_manager.debate_decisions()

        Returns:
            Decision with debate metadata
        """
        logger.info("Using debate mode ensemble")

        bull_provider = self.ensemble_manager.debate_providers.get('bull')
        bear_provider = self.ensemble_manager.debate_providers.get('bear')
        judge_provider = self.ensemble_manager.debate_providers.get('judge')

        failed_debate_providers = []
        bull_case = None
        bear_case = None
        judge_decision = None

        # Query bull provider (bullish case)
        try:
            bull_case = await self._query_single_provider(bull_provider, prompt)
            if not self.ensemble_manager._is_valid_provider_response(bull_case, bull_provider):
                logger.warning(f"Debate: {bull_provider} (bull) returned invalid response")
                failed_debate_providers.append(bull_provider)
                bull_case = None
            else:
                logger.info(f"Debate: {bull_provider} (bull) -> {bull_case.get('action')} ({bull_case.get('confidence')}%)")
        except Exception as e:
            logger.error(f"Debate: {bull_provider} (bull) failed: {e}")
            failed_debate_providers.append(bull_provider)

        # Query bear provider (bearish case)
        try:
            bear_case = await self._query_single_provider(bear_provider, prompt)
            if not self.ensemble_manager._is_valid_provider_response(bear_case, bear_provider):
                logger.warning(f"Debate: {bear_provider} (bear) returned invalid response")
                failed_debate_providers.append(bear_provider)
                bear_case = None
            else:
                logger.info(f"Debate: {bear_provider} (bear) -> {bear_case.get('action')} ({bear_case.get('confidence')}%)")
        except Exception as e:
            logger.error(f"Debate: {bear_provider} (bear) failed: {e}")
            failed_debate_providers.append(bear_provider)

        # Query judge provider (final decision)
        try:
            judge_decision = await self._query_single_provider(judge_provider, prompt)
            if not self.ensemble_manager._is_valid_provider_response(judge_decision, judge_provider):
                logger.warning(f"Debate: {judge_provider} (judge) returned invalid response")
                failed_debate_providers.append(judge_provider)
                judge_decision = None
            else:
                logger.info(f"Debate: {judge_provider} (judge) -> {judge_decision.get('action')} ({judge_decision.get('confidence')}%)")
        except Exception as e:
            logger.error(f"Debate: {judge_provider} (judge) failed: {e}")
            failed_debate_providers.append(judge_provider)

        # Error: if any debate provider failed, raise error
        if bull_case is None or bear_case is None or judge_decision is None:
            logger.error("Debate mode: Critical debate providers failed")
            raise RuntimeError(
                f"Debate mode failed: Missing providers - "
                f"bull={'OK' if bull_case else 'FAILED'}, "
                f"bear={'OK' if bear_case else 'FAILED'}, "
                f"judge={'OK' if judge_decision else 'FAILED'}"
            )

        # Synthesize debate decisions
        final_decision = self.ensemble_manager.debate_decisions(
            bull_case=bull_case,
            bear_case=bear_case,
            judge_decision=judge_decision,
            failed_debate_providers=failed_debate_providers
        )

        return final_decision

    async def _query_single_provider(self, provider_name: str, prompt: str) -> Dict[str, Any]:
        """Helper to query a single, specified AI provider."""
        # Import inline to avoid circular dependencies
        from .provider_tiers import is_ollama_model

        # Route Ollama models to local inference with specific model
        if is_ollama_model(provider_name):
            return await self._local_ai_inference(prompt, model_name=provider_name)

        # Route abstract provider names
        if provider_name == 'local':
            return await self._local_ai_inference(prompt)
        elif provider_name == 'cli':
            return await self._cli_ai_inference(prompt)
        elif provider_name == 'codex':
            return await self._codex_ai_inference(prompt)
        elif provider_name == 'qwen':
            # Qwen CLI provider (routed to CLI)
            return await self._cli_ai_inference(prompt)
        elif provider_name == 'gemini':
            return await self._gemini_ai_inference(prompt)
        else:
            # Unknown provider - raise error, let ensemble manager handle
            raise ValueError(f"Unknown AI provider: {provider_name}")

    async def _ensemble_ai_inference(
        self,
        prompt: str,
        asset_pair: Optional[str] = None,
        market_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Centralized ensemble logic with debate mode and two-phase support."""
        # Debate mode: structured debate with bull, bear, and judge providers
        if self.ensemble_manager.debate_mode:
            return await self._debate_mode_inference(prompt)

        # Two-phase logic: escalate to premium providers if Phase 1 confidence is low
        if self.ensemble_manager.config.get('ensemble', {}).get('two_phase', {}).get('enabled', False):
            return await self.ensemble_manager.aggregate_decisions_two_phase(
                prompt, asset_pair, market_data,
                lambda provider, prompt_text: self._query_single_provider(provider, prompt_text)
            )
        # Fallback to simple parallel query if two-phase is off
        return await self._simple_parallel_ensemble(prompt)

    async def _simple_parallel_ensemble(self, prompt: str) -> Dict[str, Any]:
        """
        Simple parallel ensemble: query all enabled providers concurrently and aggregate.

        Used when two-phase escalation is disabled. Queries all enabled providers
        in parallel (up to MAX_WORKERS threads) and aggregates results using the
        ensemble manager's standard aggregation method.

        Args:
            prompt: AI prompt to send to all providers

        Returns:
            Aggregated decision from all provider responses
        """
        logger.info(f"Using simple parallel ensemble with {len(self.ensemble_manager.enabled_providers)} providers")

        provider_decisions = {}
        failed_providers = []

        tasks = [
            self._query_single_provider(provider, prompt)
            for provider in self.ensemble_manager.enabled_providers
        ]

        # Use asyncio.gather to run tasks concurrently with a timeout
        # Note: ENSEMBLE_TIMEOUT is a global constant at the top of the file
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for provider, result in zip(self.ensemble_manager.enabled_providers, results):
            if isinstance(result, Exception):
                logger.error(f"Provider {provider} failed: {result}")
                failed_providers.append(provider)
            else:
                decision = result
                if self.ensemble_manager._is_valid_provider_response(decision, provider):
                    provider_decisions[provider] = decision
                    logger.debug(f"Provider {provider} -> {decision.get('action')} ({decision.get('confidence')}%)")
                else:
                    logger.warning(f"Provider {provider} returned invalid response")
                    failed_providers.append(provider)

        # Raise error if all providers failed
        if not provider_decisions:
            logger.error("All providers failed in parallel ensemble")
            raise RuntimeError(
                f"All {len(self.ensemble_manager.enabled_providers)} ensemble providers failed. "
                f"Failed providers: {failed_providers}"
            )

        # Aggregate results using ensemble manager
        return await self.ensemble_manager.aggregate_decisions(
            provider_decisions=provider_decisions,
            failed_providers=failed_providers
        )

    async def _local_ai_inference(self, prompt: str, model_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Local AI inference using Ollama LLM.

        Args:
            prompt: AI prompt
            model_name: Optional specific Ollama model to use (overrides config)

        Returns:
            AI response from local LLM
        """
        model_info = f" (model: {model_name})" if model_name else ""
        logger.info(f"Using local LLM AI inference (Ollama){model_info}")

        try:
            from .local_llm_provider import LocalLLMProvider

            # Create config with model override if specified
            provider_config = dict(self.config, model_name=model_name or self.config.get('model_name', 'default'))
            provider = LocalLLMProvider(provider_config)
            # Run synchronous query in a separate thread
            return await asyncio.to_thread(provider.query, prompt)
        except (ImportError, RuntimeError) as e:
            logger.error(f"Local LLM failed: {e}")
            raise

    async def _cli_ai_inference(self, prompt: str) -> Dict[str, Any]:
        logger.info("CLI AI inference (placeholder)")
        await asyncio.sleep(0.01)
        return {"action": "HOLD", "confidence": 50, "reasoning": "CLI placeholder", "amount": 0.0}

    async def _codex_ai_inference(self, prompt: str) -> Dict[str, Any]:
        logger.info("Codex AI inference (placeholder)")
        await asyncio.sleep(0.01)
        return {"action": "HOLD", "confidence": 50, "reasoning": "Codex placeholder", "amount": 0.0}

    async def _gemini_ai_inference(self, prompt: str) -> Dict[str, Any]:
        logger.info("Gemini AI inference (placeholder)")
        await asyncio.sleep(0.01)
        return {"action": "HOLD", "confidence": 50, "reasoning": "Gemini placeholder", "amount": 0.0}

    def _is_valid_provider_response(self, decision: Dict[str, Any], provider: str) -> bool:
        """
        Validate that a provider response dict is well-formed.

        Args:
            decision: Decision dictionary from provider to validate
            provider: Name of the provider for logging

        Returns:
            True if valid, False otherwise
        """
        if not isinstance(decision, dict):
            logger.warning(f"Provider {provider}: decision is not a dict")
            return False

        if 'action' not in decision or 'confidence' not in decision:
            logger.warning(f"Provider {provider}: missing required keys 'action' or 'confidence'")
            return False

        if decision.get('action') not in ['BUY', 'SELL', 'HOLD']:
            logger.warning(f"Provider {provider}: invalid action '{decision.get('action')}'")
            return False

        conf = decision.get('confidence')
        if not isinstance(conf, (int, float)):
            logger.warning(f"Provider {provider}: confidence is not numeric")
            return False
        if not (0 <= conf <= 100):
            logger.warning(f"Provider {provider}: Confidence {conf} out of range [0, 100]")
            return False

        if 'reasoning' in decision and not decision['reasoning'].strip():
            logger.warning(f"Provider {provider}: reasoning is empty")
            return False
        return True

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

            # Fallback for unified cash balance when platform-specific keys are absent
            if not relevant_balance and 'USD' in balance:
                relevant_balance = {'USD': balance['USD']}

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
            active_positions = monitoring_context.get('active_positions', [])
            # Handle both dict format (live) and list format (backtest)
            if isinstance(active_positions, dict):
                futures_positions = active_positions.get('futures', [])
            elif isinstance(active_positions, list):
                futures_positions = active_positions
            else:
                futures_positions = []

            for position in futures_positions:
                if isinstance(position, dict) and asset_pair in position.get('product_id', ''):
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
            # Signal-only mode: Calculate position sizing for human approval
            # Even without balance, provide suggested sizing for Telegram human-in-the-loop
            signal_only = True

            # Use default balance for position sizing calculation
            # This provides a recommendation that humans can approve/adjust
            default_balance = 10000.0  # Default $10k for sizing recommendations

            # Get risk parameters from the agent config
            agent_config = self.config.get('agent', {})
            risk_percentage = agent_config.get('risk_percentage', 0.01)
            sizing_stop_loss_percentage = agent_config.get('sizing_stop_loss_percentage', 0.02)

            # Compatibility: Convert legacy percentage values (>1) to decimals
            if risk_percentage > 1:
                logger.warning(f"Detected legacy risk_percentage {risk_percentage}%. Converting to decimal: {risk_percentage/100:.3f}")
                risk_percentage /= 100
            if sizing_stop_loss_percentage > 1:
                logger.warning(f"Detected legacy sizing_stop_loss_percentage {sizing_stop_loss_percentage}%. Converting to decimal: {sizing_stop_loss_percentage/100:.3f}")
                sizing_stop_loss_percentage /= 100

            if action == 'HOLD' and not has_existing_position:
                # HOLD without position: no sizing needed
                recommended_position_size = None
                sizing_stop_loss_percentage = None
                risk_percentage = None
                stop_loss_price = None
                logger.info(
                    "HOLD without existing position - no position sizing shown"
                )
            else:
                # Calculate position sizing for human approval
                recommended_position_size = self.calculate_position_size(
                    account_balance=default_balance,
                    risk_percentage=risk_percentage,
                    entry_price=current_price,
                    stop_loss_percentage=sizing_stop_loss_percentage
                )

                if current_price > 0 and sizing_stop_loss_percentage > 0:
                    stop_loss_price = (
                        current_price * (1 - sizing_stop_loss_percentage)
                        if action == 'BUY'
                        else current_price * (1 + sizing_stop_loss_percentage)
                    )
                else:
                    stop_loss_price = None

                if signal_only_default:
                    logger.info(
                        "Signal-only mode: Position sizing calculated for human approval (%.4f units based on $%.2f default balance)",
                        recommended_position_size,
                        default_balance
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
                        "No valid %s balance for %s - using default $%.2f for sizing recommendation (%.4f units for human approval)",
                        balance_type,
                        asset_pair,
                        default_balance,
                        recommended_position_size
                    )
                else:
                    logger.warning(
                        "Portfolio data unavailable - using default $%.2f for sizing recommendation (%.4f units for human approval)",
                        default_balance,
                        recommended_position_size
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
            'backtest_mode': self.backtest_mode,  # Track if decision was generated in backtest context
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

    def set_monitoring_context(self, monitoring_provider):
        """
        Set the monitoring context provider for live trade awareness.

        Args:
            monitoring_provider: MonitoringContextProvider instance
        """
        self.monitoring_provider = monitoring_provider
        logger.info("Monitoring context provider attached to decision engine")

    async def generate_decision(
        self,
        asset_pair: str,
        market_data: Dict[str, Any],
        balance: Dict[str, float],
        portfolio: Optional[Dict[str, Any]] = None,
        memory_context: Optional[Dict[str, Any]] = None,
        monitoring_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate a trading decision based on market data and balances.

        Args:
            asset_pair: Asset pair being analyzed
            market_data: Current market data
            balance: Account balances
            portfolio: Optional portfolio breakdown with holdings/allocations
            memory_context: Optional historical performance context
            monitoring_context: Optional monitoring context with active positions and pulse

        Returns:
            Trading decision with recommendation
        """
        logger.info("Generating decision for %s", asset_pair)

        # NOTE: backtest_mode flag is deprecated - backtests should use real AI providers
        # to accurately simulate production behavior. Keeping the parameter for backward
        # compatibility but it no longer changes decision logic.
        if self.backtest_mode:
            logger.warning(
                "backtest_mode=True is deprecated. Backtests now use real AI providers "
                "for accurate simulation. Use 'mock' provider for fast rule-based testing."
            )

        # Merge monitoring context from parameter with live monitoring provider
        # Parameter takes precedence (for backtesting)
        if monitoring_context is None and self.monitoring_provider:
            try:
                monitoring_context = (
                    self.monitoring_provider.get_monitoring_context(
                        asset_pair=asset_pair
                    )
                )
                # Handle active_positions as either list or dict
                active_pos = monitoring_context.get('active_positions', [])
                if isinstance(active_pos, dict):
                    num_positions = len(active_pos.get('futures', []))
                elif isinstance(active_pos, list):
                    num_positions = len(active_pos)
                else:
                    num_positions = 0

                logger.info(
                    "Monitoring context loaded: %d active positions, %d slots",
                    num_positions,
                    monitoring_context.get('slots_available', 0)
                )
            except Exception as e:
                logger.warning("Could not load monitoring context: %s", e)
        elif monitoring_context:
            logger.debug("Using provided monitoring context (backtesting mode)")

        # Create decision context
        context = await self._create_decision_context(
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

        # Get AI recommendation (pass asset_pair and market_data for two-phase ensemble)
        ai_response = await self._query_ai(prompt, asset_pair=asset_pair, market_data=market_data)

        # Validate AI response action to ensure it's one of the allowed values
        if ai_response.get('action') not in ['BUY', 'SELL', 'HOLD']:
            logger.warning(
                f"AI provider returned an invalid action: "
                f"'{ai_response.get('action')}'. Defaulting to 'HOLD'."
            )
            ai_response['action'] = 'HOLD'

        # Create structured decision object
        decision = self._create_decision(asset_pair, context, ai_response)

        return decision

    async def _create_decision_context(
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
        regime = await self._detect_market_regime(asset_pair)
        context['regime'] = regime

        # Add market schedule status
        asset_type = market_data.get('asset_type', 'crypto')
        try:
            market_status = self.market_schedule.get_market_status(asset_pair, asset_type)
            context['market_status'] = market_status if market_status else {}
        except Exception as e:
            logger.warning(f"Failed to get market status: {e}")
            context['market_status'] = {}

        # Validate data freshness
        data_timestamp = market_data.get('date')
        if data_timestamp is None:
            data_timestamp = market_data.get('timestamp')

        if data_timestamp is not None:
            try:
                is_fresh, age_minutes, freshness_message = validate_data_freshness(
                    data_timestamp, asset_type
                )
                context['data_freshness'] = {
                    'is_fresh': is_fresh,
                    'age_minutes': age_minutes,
                    'message': freshness_message
                }
            except Exception as e:
                logger.warning(f"Failed to validate data freshness: {e}")
                context['data_freshness'] = {
                    'is_fresh': False,
                    'age_minutes': None,
                    'message': f'Validation error: {str(e)}'
                }
        else:
            context['data_freshness'] = {
                'is_fresh': False,
                'age_minutes': None,
                'message': 'No timestamp available in market data'
            }

        # Note: Multi-timeframe pulse now injected via monitoring_context
        # (see MonitoringContextProvider.get_monitoring_context and format_for_ai_prompt)

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
