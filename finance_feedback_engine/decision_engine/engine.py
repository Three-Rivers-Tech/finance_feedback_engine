"""Decision engine for generating AI-powered trading decisions."""

from typing import Dict, Any, Optional
import logging
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)


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
    - P&L Formula: (Exit Price - Entry Price) × Position Size
    - Example: Buy BTC at $50,000, sell at $55,000 = $5,000 profit per BTC
    
    Short Positions (Bearish):
    --------------------------
    - Action: SELL to enter, BUY to cover/exit
    - Expectation: Asset price will FALL
    - Profit: When current price < entry price
    - Loss: When current price > entry price
    - P&L Formula: (Entry Price - Exit Price) × Position Size
    - Example: Short BTC at $50,000, cover at $45,000 = $5,000 profit per BTC
    
    Position Sizing Principles:
    ---------------------------
    Position size determines how much capital to allocate to a trade.
    Key factors:
    1. Risk Tolerance: Typically 1-2% of total account per trade
    2. Stop Loss Distance: Price level where you exit if wrong
    3. Volatility: Higher volatility requires smaller positions
    4. Account Balance: Never risk entire capital on one trade
    
    Formula: Position Size = (Account Balance × Risk%) / (Entry Price × Stop Loss%)
    
    Example: $10,000 account, 1% risk, $50,000 BTC, 2% stop loss
    → Position Size = ($10,000 × 0.01) / ($50,000 × 0.02) = 0.1 BTC
    
    Profit & Loss Calculation:
    --------------------------
    Unrealized P&L: Open positions (mark-to-market)
    Realized P&L: Closed positions (actual profit/loss locked in)
    
    Long P&L % = ((Current Price - Entry Price) / Entry Price) × 100
    Short P&L % = ((Entry Price - Current Price) / Entry Price) × 100
    
    Risk Management:
    ----------------
    - Always use stop losses to limit downside
    - Position sizing prevents catastrophic losses
    - Diversification across multiple assets
    - Never risk more than you can afford to lose
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the decision engine.

        Args:
            config: Configuration dictionary containing:
                - ai_provider: 'local', 'cli', 'codex', or 'ensemble'
                - model_name: Name/path of the model to use
                - prompt_template: Custom prompt template (optional)
                - decision_threshold: Confidence threshold for decisions
                - ensemble: Ensemble configuration (if provider='ensemble')
        """
        self.config = config
        self.ai_provider = config.get('ai_provider', 'local')
        self.model_name = config.get('model_name', 'default')
        self.decision_threshold = config.get('decision_threshold', 0.7)
        
        # Initialize ensemble manager if using ensemble mode
        self.ensemble_manager = None
        if self.ai_provider == 'ensemble':
            from .ensemble_manager import EnsembleDecisionManager
            self.ensemble_manager = EnsembleDecisionManager(config)
            logger.info("Ensemble mode enabled")
        
        logger.info(f"Decision engine initialized with provider: {self.ai_provider}")

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
        
        # Create decision context
        context = self._create_decision_context(
            asset_pair, market_data, balance, portfolio, memory_context
        )
        
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

    def _create_decision_context(
        self,
        asset_pair: str,
        market_data: Dict[str, Any],
        balance: Dict[str, float],
        portfolio: Optional[Dict[str, Any]] = None,
        memory_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create context for decision making.

        Args:
            asset_pair: Asset pair
            market_data: Market data
            balance: Balances
            portfolio: Optional portfolio breakdown
            memory_context: Optional historical performance context

        Returns:
            Decision context
        """
        context = {
            'asset_pair': asset_pair,
            'market_data': market_data,
            'balance': balance,
            'portfolio': portfolio,
            'memory_context': memory_context,
            'timestamp': datetime.utcnow().isoformat(),
            'price_change': self._calculate_price_change(market_data),
            'volatility': self._calculate_volatility(market_data)
        }
        return context

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
        risk_percentage: float = 1.0,
        entry_price: float = 0,
        stop_loss_percentage: float = 2.0
    ) -> float:
        """
        Calculate appropriate position size based on risk management.

        Args:
            account_balance: Total account balance
            risk_percentage: Percentage of account to risk (default 1%)
            entry_price: Entry price for the position
            stop_loss_percentage: Stop loss distance as % (default 2%)

        Returns:
            Suggested position size in units of asset
        """
        if entry_price == 0 or stop_loss_percentage == 0:
            return 0.0
        
        # Amount willing to risk in dollar terms
        risk_amount = account_balance * (risk_percentage / 100)
        
        # Price distance of stop loss
        stop_loss_distance = entry_price * (stop_loss_percentage / 100)
        
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

        prompt = f"""You are a financial trading advisor. Analyze the following market data and provide a trading recommendation.

{market_info}

Account Balance: {balance}

TRADING CONTEXT - Long/Short Positions:
===================================
A LONG position means buying an asset with the expectation that its price will RISE.
- Enter: BUY action when bullish (expecting price increase)
- Exit: SELL action to close position
- Profit: When price rises above entry price
- Loss: When price falls below entry price
- Formula: P&L = (Exit Price - Entry Price) × Position Size

A SHORT position means selling an asset with the expectation that its price will FALL.
- Enter: SELL action when bearish (expecting price decrease)
- Exit: BUY action to close/cover position
- Profit: When price falls below entry price
- Loss: When price rises above entry price
- Formula: P&L = (Entry Price - Exit Price) × Position Size

POSITION SIZING PRINCIPLES:
===========================
Position size should be calculated based on:
1. Risk tolerance (typically 1-2% of account balance per trade)
2. Stop-loss distance (price distance to exit if wrong)
3. Volatility (higher volatility = smaller position)
4. Account balance (never risk entire capital)
Formula: Position Size = (Account Balance × Risk %) / (Entry Price × Stop Loss %)

PROFIT & LOSS CALCULATION:
==========================
For LONG: P&L = (Current Price - Entry Price) / Entry Price × 100%
For SHORT: P&L = (Entry Price - Current Price) / Entry Price × 100%
Unrealized P&L: Open positions (not yet closed)
Realized P&L: Closed positions (actual profit/loss)

ANALYSIS GUIDELINES:
====================
Consider the following in your analysis:
- Candlestick patterns (long wicks suggest rejection, large body suggests conviction)
- Close position in range (near high = bullish, near low = bearish)
- RSI levels (>70 overbought, <30 oversold, if provided)
- Volatility (high volatility = higher risk)
- Volume trends (for crypto, if provided)
- Overall trend direction
- News sentiment (bullish/bearish/neutral, if provided)
- Sentiment score magnitude (stronger scores = stronger signals)
- Macroeconomic context (inflation, rates, GDP, if provided)
- Macro headwinds/tailwinds for the asset class

Sentiment & Macro Integration:
- Bullish sentiment + positive technicals = strong buy signal
- Bearish sentiment + negative technicals = strong sell signal
- Conflicting signals (e.g., bullish technicals, bearish sentiment) = caution/hold
- High inflation/rates may favor crypto over fiat currencies
- Economic weakness may increase risk-off behavior

Based on this information, should we BUY (go long), SELL (go short or close), or HOLD {asset_pair}?
Provide:
1. Action (BUY/SELL/HOLD)
2. Confidence (0-100%)
3. Reasoning (brief explanation including long/short context)
4. Suggested position size (considering risk management)
"""
        return prompt
    
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
            "Recent Performance:"
        ]
        
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
        
        # Get enabled providers from ensemble config
        enabled = self.ensemble_manager.enabled_providers
        
        # Query each provider and track failures
        provider_decisions = {}
        failed_providers = []
        
        for provider in enabled:
            try:
                if provider == 'local':
                    decision = self._local_ai_inference(prompt)
                elif provider == 'cli':
                    decision = self._cli_ai_inference(prompt)
                elif provider == 'codex':
                    decision = self._codex_ai_inference(prompt)
                elif provider == 'qwen':
                    decision = self._qwen_ai_inference(prompt)
                else:
                    logger.warning(f"Unknown provider: {provider}")
                    failed_providers.append(provider)
                    continue
                
                # Check if the decision is a valid response (not a fallback)
                if self._is_valid_provider_response(decision, provider):
                    provider_decisions[provider] = decision
                    logger.info(
                        f"{provider}: {decision['action']} "
                        f"({decision['confidence']}%)"
                    )
                else:
                    # Provider returned fallback response, treat as failure
                    logger.warning(
                        f"Provider {provider} returned fallback/invalid "
                        f"response, treating as failure"
                    )
                    failed_providers.append(provider)
                
            except Exception as e:
                logger.warning(f"Provider {provider} failed: {e}")
                failed_providers.append(provider)
                continue
        
        # Handle complete failure case
        if not provider_decisions:
            logger.error(
                f"All {len(enabled)} providers failed, using rule-based "
                f"fallback"
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
            f"Ensemble query complete: {len(provider_decisions)} succeeded, "
            f"{len(failed_providers)} failed"
        )
        
        # Aggregate decisions with failure information
        aggregated = self.ensemble_manager.aggregate_decisions(
            provider_decisions,
            failed_providers=failed_providers
        )
        
        return aggregated

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
                        'reasoning': 'Price increased significantly, taking profit.',
                        'amount': 0.1
                    }
                elif price_change < -2:
                    return {
                        'action': 'BUY',
                        'confidence': 70,
                        'reasoning': 'Price dropped, good buying opportunity.',
                        'amount': 0.1
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
        
        # Logic gate: Only calculate position sizing if we have valid balance data
        current_price = context['market_data'].get('close', 0)
        balance = context.get('balance', {})
        
        # Check if balance data is available and valid
        has_valid_balance = (
            balance and 
            isinstance(balance, dict) and 
            len(balance) > 0 and 
            sum(balance.values()) > 0
        )
        
        # Calculate position sizing only if balance is available
        if has_valid_balance:
            total_balance = sum(balance.values())
            
            # Use 1% risk with 2% stop loss as default conservative values
            recommended_position_size = self.calculate_position_size(
                account_balance=total_balance,
                risk_percentage=1.0,
                entry_price=current_price,
                stop_loss_percentage=2.0
            )
            stop_loss_percentage = 2.0
            risk_percentage = 1.0
            signal_only = False
            logger.info(
                "Position sizing calculated: %.4f units (balance: $%.2f)",
                recommended_position_size,
                total_balance
            )
        else:
            # Signal-only mode: No position sizing when balance unavailable
            recommended_position_size = None
            stop_loss_percentage = None
            risk_percentage = None
            signal_only = True
            logger.warning(
                "Portfolio data unavailable - providing signal only (no position sizing)"
            )
        
        # Determine position type based on action
        action = ai_response.get('action', 'HOLD')
        position_type = 'LONG' if action == 'BUY' else 'SHORT' if action == 'SELL' else None
        
        decision = {
            'id': decision_id,
            'asset_pair': asset_pair,
            'timestamp': datetime.utcnow().isoformat(),
            'action': action,
            'confidence': ai_response.get('confidence', 50),
            'reasoning': ai_response.get('reasoning', 'No reasoning provided'),
            'suggested_amount': ai_response.get('amount', 0),
            'recommended_position_size': recommended_position_size,  # None if signal_only
            'position_type': position_type,  # LONG, SHORT, or None
            'entry_price': current_price,
            'stop_loss_percentage': stop_loss_percentage,  # None if signal_only
            'risk_percentage': risk_percentage,  # None if signal_only
            'signal_only': signal_only,  # True when position sizing unavailable
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
            'model_name': self.model_name
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
        
        logger.info(f"Decision created: {decision['action']} {asset_pair} (confidence: {decision['confidence']}%)")
        
        return decision
