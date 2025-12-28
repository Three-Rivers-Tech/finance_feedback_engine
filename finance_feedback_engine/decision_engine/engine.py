"""Decision engine for generating AI-powered trading decisions."""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

import pytz

from finance_feedback_engine.memory.vector_store import VectorMemory
from finance_feedback_engine.utils.config_loader import normalize_decision_config

logger = logging.getLogger(__name__)
try:
    from opentelemetry import trace

    tracer = trace.get_tracer(__name__)
except Exception:  # OpenTelemetry optional
    tracer = None


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

    def __init__(
        self, config: Dict[str, Any], data_provider=None, backtest_mode: bool = False
    ):
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
        self.config = config
        self.data_provider = data_provider
        self.backtest_mode = backtest_mode

        # Initialize specialized managers
        from .ai_decision_manager import AIDecisionManager
        from .decision_validator import DecisionValidator
        from .market_analysis import MarketAnalysisContext
        from .position_sizing import PositionSizingCalculator

        self.ai_manager = AIDecisionManager(config, backtest_mode)
        self.market_analyzer = MarketAnalysisContext(config, data_provider)
        self.validator = DecisionValidator(config, backtest_mode)
        self.position_sizing_calc = PositionSizingCalculator(config)

        # Local models and priority configuration
        decision_config = normalize_decision_config(config)
        self.local_models = decision_config.get("local_models", [])
        self.local_priority = decision_config.get("local_priority", False)

        # Extract portfolio risk parameters from decision_engine config
        self.portfolio_stop_loss_percentage = decision_config.get(
            "portfolio_stop_loss_percentage", 0.02
        )
        self.portfolio_take_profit_percentage = decision_config.get(
            "portfolio_take_profit_percentage", 0.05
        )

        # Convert legacy percentage format (>=1.0) to decimal (e.g., 2.0 -> 0.02).
        # This allows configs like "2" for 2%, while standard format is a decimal fraction (0.02).
        if self.portfolio_stop_loss_percentage >= 1.0:
            original_value = self.portfolio_stop_loss_percentage
            self.portfolio_stop_loss_percentage = (
                self.portfolio_stop_loss_percentage / 100
            )
            logger.warning(
                "DecisionEngine: portfolio_stop_loss_percentage=%s interpreted as legacy "
                "percentage format; converted to decimal fraction=%s. "
                "To avoid this warning, configure a value between 0 and 1.",
                original_value,
                self.portfolio_stop_loss_percentage,
            )
        if self.portfolio_take_profit_percentage >= 1.0:
            original_value = self.portfolio_take_profit_percentage
            self.portfolio_take_profit_percentage = (
                self.portfolio_take_profit_percentage / 100
            )
            logger.warning(
                "DecisionEngine: portfolio_take_profit_percentage=%s interpreted as legacy "
                "percentage format; converted to decimal fraction=%s. "
                "To avoid this warning, configure a value between 0 and 1.",
                original_value,
                self.portfolio_take_profit_percentage,
            )

        # Validate local_models
        if not isinstance(self.local_models, list):
            raise ValueError(
                f"local_models must be a list, got {type(self.local_models)}"
            )

        # Validate local_priority
        valid_priority_values = (True, False, "soft")
        if isinstance(self.local_priority, str):
            if self.local_priority not in valid_priority_values:
                raise ValueError(
                    f"local_priority string must be 'soft', got '{self.local_priority}'"
                )
        elif not isinstance(self.local_priority, (bool, int, float)):
            raise ValueError(
                f"local_priority must be bool, int, float, or 'soft', got {type(self.local_priority)}"
            )

        logger.info(f"Local models configured: {self.local_models}")
        logger.info(f"Local priority: {self.local_priority}")

        # Monitoring context provider (optional, set via set_monitoring_context)
        self.monitoring_provider = None

        # Initialize vector memory for semantic search (optional)
        self.vector_memory = None
        try:
            # Accept either direct path or nested config keys
            # Check top-level 'memory' key first (full config), then fall back to original config (backward compatibility)
            vm_cfg = config.get("memory", {})
            if not isinstance(vm_cfg, dict):
                vm_cfg = {}
            storage_path = (
                vm_cfg.get("vector_store_path")
                or vm_cfg.get("vector_memory_path")
                or vm_cfg.get("dir")
                or "data/memory/vectors.pkl"
            )
            self.vector_memory = VectorMemory(storage_path)
            logger.info("Vector memory initialized successfully")
        except Exception as e:
            logger.warning(
                f"Failed to initialize vector memory: {e}. Proceeding without semantic search."
            )

        logger.info(
            f"Decision engine initialized with provider: {self.ai_manager.ai_provider}"
        )

    @property
    def ai_provider(self):
        """Get the AI provider from the AI manager."""
        return self.ai_manager.ai_provider

    @property
    def decision_threshold(self):
        """Get decision threshold from config. Supports flat and nested config structures."""
        decision_config = normalize_decision_config(self.config)
        return decision_config.get("decision_threshold", 0.6)

    @property
    def ensemble_manager(self):
        """
        Get the ensemble manager currently used by the AI manager.

        Note:
            This is a delegated view of ``self.ai_manager.ensemble_manager``.
            Accessing or mutating this property will directly interact with the
            underlying ``ai_manager`` instance rather than a separate copy on
            ``DecisionEngine`` itself.
        """
        return self.ai_manager.ensemble_manager

    @ensemble_manager.setter
    def ensemble_manager(self, value):
        """
        Set the ensemble manager on the underlying AI manager.

        Warning:
            This setter directly updates ``self.ai_manager.ensemble_manager``.
            As a result, any code that also holds a reference to the same
            ``ai_manager`` will observe this change. This tight coupling is
            intentional (e.g. for testing and configuration wiring), but it
            means that ``engine.ensemble_manager = X`` has the side effect of
            mutating shared internal state.
        """
        self.ai_manager.ensemble_manager = value

    def _calculate_price_change(self, market_data: Dict[str, Any]) -> float:
        """Calculate price change percentage. Delegates to market analyzer."""
        if getattr(self, "market_analyzer", None) is None:
            raise RuntimeError(
                "market_analyzer is not initialized on DecisionEngine; "
                "_calculate_price_change cannot be called without it."
            )
        try:
            return self.market_analyzer._calculate_price_change(market_data)
        except Exception as exc:  # pragma: no cover - defensive wrapper
            raise RuntimeError(
                "Failed to calculate price change via market_analyzer."
            ) from exc

    def _calculate_volatility(self, market_data: Dict[str, Any]) -> float:
        """Calculate volatility. Delegates to market analyzer."""
        if getattr(self, "market_analyzer", None) is None:
            raise RuntimeError(
                "market_analyzer is not initialized on DecisionEngine; "
                "_calculate_volatility cannot be called without it."
            )
        try:
            return self.market_analyzer._calculate_volatility(market_data)
        except Exception as exc:  # pragma: no cover - defensive wrapper
            raise RuntimeError(
                "Failed to calculate volatility via market_analyzer."
            ) from exc

    async def _mock_ai_inference(self, prompt: str) -> Dict[str, Any]:
        """
        Simulate AI inference for backtesting.
        """
        logger.info("Mock AI inference")
        # Delegating to the AI manager for consistent behavior
        return await self.ai_manager._mock_ai_inference(prompt)

    async def _detect_market_regime(self, asset_pair: str) -> str:
        """
        Detect the current market regime using historical data.

        Args:
            asset_pair: Asset pair to analyze

        Returns:
            Market regime string
        """
        # Delegating to the market analyzer
        return await self.market_analyzer._detect_market_regime(asset_pair)

    def _create_ai_prompt(self, context: Dict[str, Any]) -> str:
        """
        Create AI prompt for decision making.

        Args:
            context: Decision context

        Returns:
            AI prompt string
        """
        asset_pair = context["asset_pair"]
        market_data = context["market_data"]
        balance = context["balance"]
        price_change = context["price_change"]
        volatility = context["volatility"]

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
        market_status = context.get("market_status", {})
        data_freshness = context.get("data_freshness", {})
        utc_now = datetime.utcnow().replace(tzinfo=pytz.UTC)
        ny_tz = pytz.timezone("America/New_York")
        ny_time = utc_now.astimezone(ny_tz).strftime("%Y-%m-%d %H:%M:%S %Z")
        utc_time = utc_now.strftime("%Y-%m-%d %H:%M:%S UTC")

        # Market status info
        is_open = market_status.get("is_open", True)
        session = market_status.get("session", "Unknown")
        time_to_close = market_status.get("time_to_close", 0)
        market_warning = market_status.get("warning", "")

        # Data freshness info
        is_fresh = data_freshness.get("is_fresh", True)
        age_str = data_freshness.get("age_minutes", "Unknown")
        freshness_msg = data_freshness.get("message", "")

        # Emoji indicators
        status_emoji = "✅" if is_open else "🔴"
        freshness_emoji = (
            "✅" if is_fresh else "⚠️" if "WARNING" in freshness_msg else "🔴"
        )

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
        if market_data.get("type") == "crypto":
            market_info += f"""
VOLUME & MARKET DATA:
---------------------
Volume: {market_data.get('volume', 0):,.0f}
Market Cap: ${market_data.get('market_cap', 0):,.0f}
"""

        # Add technical indicators if available
        if "rsi" in market_data:
            market_info += f"""
TECHNICAL INDICATORS:
---------------------
RSI (14): {market_data.get('rsi', 0):.2f} ({market_data.get('rsi_signal', 'neutral')})
"""

        # Add news sentiment if available
        if "sentiment" in market_data and market_data["sentiment"].get("available"):
            sentiment = market_data["sentiment"]
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
        if "macro" in market_data and market_data["macro"].get("available"):
            macro = market_data["macro"]
            market_info += """
MACROECONOMIC CONTEXT:
----------------------
"""
            for indicator, data in macro.get("indicators", {}).items():
                readable_name = indicator.replace("_", " ").title()
                market_info += (
                    f"{readable_name}: {data.get('value')} (as of {data.get('date')})\n"
                )

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
        portfolio = context.get("portfolio")
        if portfolio and portfolio.get("holdings"):
            total_value = portfolio.get("total_value_usd", 0)
            num_assets = portfolio.get("num_assets", 0)
            unrealized_pnl = portfolio.get("unrealized_pnl")

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
            for holding in portfolio.get("holdings", []):
                currency = holding.get("currency")
                amount = holding.get("amount", 0)
                value_usd = holding.get("value_usd", 0)
                allocation = holding.get("allocation_pct", 0)
                market_info += (
                    f"  {currency}: {amount:.6f} "
                    f"(${value_usd:,.2f} - {allocation:.1f}%)\n"
                )

            # Check if we already hold the asset being analyzed
            asset_base = asset_pair.replace("USD", "").replace("USDT", "")
            current_holding = None
            for holding in portfolio.get("holdings", []):
                if holding.get("currency") == asset_base:
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
        memory_context = context.get("memory_context")
        if memory_context and memory_context.get("has_history"):
            memory_text = self._format_memory_context(memory_context)
            market_info += f"\n{memory_text}\n"

        # Add transaction cost context if available
        cost_context = context.get("transaction_cost_context")
        if cost_context and cost_context.get("has_data"):
            cost_text = self._format_cost_context(cost_context)
            market_info += f"\n{cost_text}\n"

        # Add live monitoring context if available
        monitoring_context = context.get("monitoring_context")
        if monitoring_context and monitoring_context.get("has_monitoring_data"):
            monitoring_text = self.monitoring_provider.format_for_ai_prompt(
                monitoring_context
            )
            market_info += f"\n{monitoring_text}\n"

        # Add historical similarity analysis if available
        semantic_memory = context.get("semantic_memory")
        if semantic_memory and self._should_include_semantic_memory():
            similarity_text = self._format_semantic_memory(semantic_memory)
            market_info += f"\n{similarity_text}\n"

        # Prepend market regime if available
        regime = context.get("regime", "UNKNOWN")
        regime_prefix = ""
        if regime != "UNKNOWN":
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

    def _format_memory_context(self, context: Dict[str, Any]) -> str:
        """Format portfolio memory context for AI prompts."""
        if not context or not context.get("has_history"):
            return "No historical trading data available."

        lines = [
            "=== PORTFOLIO MEMORY CONTEXT ===",
            f"Historical trades: {context.get('total_historical_trades', 0)}",
            f"Recent trades analyzed: {context.get('recent_trades_analyzed', 0)}",
            "",
            "Recent Performance:",
            f"  Win Rate: {context.get('recent_performance', {}).get('win_rate', 0):.1f}%",
            f"  Total P&L: ${context.get('recent_performance', {}).get('total_pnl', 0):.2f}",
            f"  Wins: {context.get('recent_performance', {}).get('winning_trades', 0)}, "
            f"Losses: {context.get('recent_performance', {}).get('losing_trades', 0)}",
        ]

        streak = context.get("current_streak", {})
        if streak.get("type"):
            lines.append(
                f"  Current Streak: {streak.get('count', 0)} {streak.get('type')} trades"
            )

        lines.append("\nAction Performance:")
        for action, stats in context.get("action_performance", {}).items():
            lines.append(
                f"  {action}: {stats.get('win_rate', 0):.1f}% win rate, "
                f"${stats.get('total_pnl', 0):.2f} P&L ({stats.get('count', 0)} trades)"
            )

        provider_perf = context.get("provider_performance", {})
        if provider_perf:
            lines.append("\nProvider Performance:")
            for provider, stats in provider_perf.items():
                lines.append(
                    f"  {provider}: {stats.get('win_rate', 0):.1f}% win rate "
                    f"({stats.get('count', 0)} trades)"
                )

        if context.get("asset_specific"):
            asset_stats = context["asset_specific"]
            lines.append(f"\n{context.get('asset_pair', 'This Asset')} Specific:")
            lines.append(
                f"  {asset_stats.get('total_trades', 0)} trades, "
                f"{asset_stats.get('win_rate', 0):.1f}% win rate, "
                f"${asset_stats.get('total_pnl', 0):.2f} total P&L"
            )

        long_term = context.get("long_term_performance")
        if long_term and long_term.get("has_data"):
            lines.append("\nLong-Term Performance:")
            lines.append(f"  Period: last {long_term.get('period_days', 0)} days")
            lines.append(
                f"  Trades: {long_term.get('total_trades', 0)} | Win Rate: {long_term.get('win_rate', 0):.1f}%"
            )
            lines.append(
                f"  Profit Factor: {long_term.get('profit_factor', 0):.2f} | ROI: {long_term.get('roi_percentage', 0):.2f}%"
            )
            lines.append(f"  Realized P&L: ${long_term.get('realized_pnl', 0):.2f}")
            avg_win = long_term.get("avg_win")
            avg_loss = long_term.get("avg_loss")
            if avg_win is not None and avg_loss is not None:
                lines.append(f"  Avg Win: ${avg_win:.2f} | Avg Loss: ${avg_loss:.2f}")
            best = long_term.get("best_trade")
            worst = long_term.get("worst_trade")
            if best is not None and worst is not None:
                lines.append(f"  Best Trade: ${best:.2f} | Worst Trade: ${worst:.2f}")

        lines.append("=" * 35)
        return "\n".join(lines)

    def _format_cost_context(self, cost_context: Dict[str, Any]) -> str:
        """
        Format transaction cost context for AI prompts.

        Args:
            cost_context: Cost metrics from portfolio memory

        Returns:
            Formatted cost context string
        """
        if not cost_context or not cost_context.get("has_data"):
            return ""

        sample_size = cost_context.get("sample_size", 0)
        has_partial = cost_context.get("has_partial_window", False)

        lines = [
            "=== TRANSACTION COST ANALYSIS ===",
            f"Data from last {sample_size} trades"
            + (" (partial window)" if has_partial else ""),
            "",
            "Average Transaction Costs:",
            f"  Total Cost: {cost_context.get('avg_total_cost_pct', 0):.3f}% of position value",
            f"  - Slippage: {cost_context.get('avg_slippage_pct', 0):.3f}%",
            f"  - Trading Fees: {cost_context.get('avg_fee_pct', 0):.3f}%",
            f"  - Bid-Ask Spread: {cost_context.get('avg_spread_pct', 0):.3f}%",
            "",
            "Break-Even Requirement:",
            f"  Price must move {cost_context.get('break_even_requirement', 0):.3f}% in your favor",
            "  just to cover transaction costs before making any profit.",
            "",
            "Cost-Aware Decision Making:",
            "  - Short-term trades (<1 day) need strong conviction to justify costs",
            f"  - Minimum expected profit should exceed {cost_context.get('avg_total_cost_pct', 0) * 3:.2f}% (3x costs)",
            "  - Consider holding period: longer holds amortize costs better",
            "  - High-frequency trading erodes returns through cumulative costs",
        ]

        # Add outlier filtering info if available
        outliers_filtered = cost_context.get("outliers_filtered", 0)
        if outliers_filtered > 0:
            lines.append(
                f"  - Note: {outliers_filtered} outlier trades filtered for accuracy"
            )

        lines.append("=" * 35)
        return "\n".join(lines)

    async def _query_ai(
        self,
        prompt: str,
        asset_pair: Optional[str] = None,
        market_data: Optional[Dict[str, Any]] = None,
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
        # Delegating to the AI manager
        return await self.ai_manager.query_ai(prompt, asset_pair, market_data)

    def _resolve_veto_threshold(self, context: Dict[str, Any]) -> float:
        """
        Resolve the veto threshold using config defaults and adaptive memory context.
        """
        decision_cfg = normalize_decision_config(self.config)
        base_threshold = float(decision_cfg.get("veto_threshold", 0.6))

        # Adaptive threshold from portfolio memory context (if provided)
        memory_context = context.get("memory_context") or {}
        if isinstance(memory_context, dict):
            adaptive_threshold = memory_context.get("veto_threshold_recommendation")
            if isinstance(adaptive_threshold, (int, float)):
                base_threshold = adaptive_threshold

        # Clamp to sane bounds
        return max(0.1, min(0.9, base_threshold))

    def _apply_veto_logic(
        self, ai_response: Dict[str, Any], context: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
        """
        Apply optional veto logic before returning the final AI response.

        Veto metadata is added when the sentiment_veto feature flag is enabled and
        the provider supplies either a boolean veto signal or a veto_score above
        the configured/adaptive threshold.

        Returns a tuple of (possibly adjusted response, veto_metadata or None).
        """
        features_cfg = self.config.get("features", {})
        if not features_cfg.get("sentiment_veto"):
            return ai_response, None

        veto_score = ai_response.get("veto_score")
        veto_flag = bool(ai_response.get("veto"))

        if veto_score is None and not veto_flag:
            return ai_response, None

        threshold = self._resolve_veto_threshold(context)
        applied = veto_flag or (
            isinstance(veto_score, (int, float)) and veto_score >= threshold
        )

        veto_metadata = {
            "applied": applied,
            "score": veto_score,
            "threshold": threshold,
            "source": ai_response.get("veto_source", "sentiment"),
            "reason": ai_response.get("veto_reason"),
        }

        if not applied:
            return ai_response, veto_metadata

        adjusted_response = dict(ai_response)
        adjusted_response["action"] = "HOLD"
        adjusted_response["confidence"] = 0
        if not adjusted_response.get("reasoning"):
            adjusted_response["reasoning"] = "Veto applied due to high risk signal"

        return adjusted_response, veto_metadata

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

        bull_provider = self.ensemble_manager.debate_providers.get("bull")
        bear_provider = self.ensemble_manager.debate_providers.get("bear")
        judge_provider = self.ensemble_manager.debate_providers.get("judge")

        failed_debate_providers = []
        bull_case = None
        bear_case = None
        judge_decision = None

        # Query bull provider (bullish case)
        try:
            bull_case = await self._query_single_provider(bull_provider, prompt)
            if not self.ensemble_manager._is_valid_provider_response(
                bull_case, bull_provider
            ):
                logger.warning(
                    f"Debate: {bull_provider} (bull) returned invalid response"
                )
                failed_debate_providers.append(bull_provider)
                bull_case = None
            else:
                logger.info(
                    f"Debate: {bull_provider} (bull) -> {bull_case.get('action')} ({bull_case.get('confidence')}%)"
                )
        except Exception as e:
            logger.error(f"Debate: {bull_provider} (bull) failed: {e}")
            failed_debate_providers.append(bull_provider)

        # Query bear provider (bearish case)
        try:
            bear_case = await self._query_single_provider(bear_provider, prompt)
            if not self.ensemble_manager._is_valid_provider_response(
                bear_case, bear_provider
            ):
                logger.warning(
                    f"Debate: {bear_provider} (bear) returned invalid response"
                )
                failed_debate_providers.append(bear_provider)
                bear_case = None
            else:
                logger.info(
                    f"Debate: {bear_provider} (bear) -> {bear_case.get('action')} ({bear_case.get('confidence')}%)"
                )
        except Exception as e:
            logger.error(f"Debate: {bear_provider} (bear) failed: {e}")
            failed_debate_providers.append(bear_provider)

        # Query judge provider (final decision)
        try:
            judge_decision = await self._query_single_provider(judge_provider, prompt)
            if not self.ensemble_manager._is_valid_provider_response(
                judge_decision, judge_provider
            ):
                logger.warning(
                    f"Debate: {judge_provider} (judge) returned invalid response"
                )
                failed_debate_providers.append(judge_provider)
                judge_decision = None
            else:
                logger.info(
                    f"Debate: {judge_provider} (judge) -> {judge_decision.get('action')} ({judge_decision.get('confidence')}%)"
                )
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
            failed_debate_providers=failed_debate_providers,
        )

        return final_decision

    async def _query_single_provider(
        self, provider_name: str, prompt: str
    ) -> Dict[str, Any]:
        """Helper to query a single, specified AI provider."""
        # Import inline to avoid circular dependencies
        from .provider_tiers import is_ollama_model

        # Route Ollama models to local inference with specific model
        if is_ollama_model(provider_name):
            return await self._local_ai_inference(prompt, model_name=provider_name)

        # Route abstract provider names
        if provider_name == "local":
            return await self._local_ai_inference(prompt)
        elif provider_name == "cli":
            return await self._cli_ai_inference(prompt)
        elif provider_name == "codex":
            return await self._codex_ai_inference(prompt)
        elif provider_name == "qwen":
            # Qwen CLI provider (routed to CLI)
            return await self._cli_ai_inference(prompt)
        elif provider_name == "gemini":
            return await self._gemini_ai_inference(prompt)
        else:
            # Unknown provider - raise error, let ensemble manager handle
            raise ValueError(f"Unknown AI provider: {provider_name}")

    async def _ensemble_ai_inference(
        self,
        prompt: str,
        asset_pair: Optional[str] = None,
        market_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Centralized ensemble logic with debate mode and two-phase support."""
        # Debate mode: structured debate with bull, bear, and judge providers
        if self.ensemble_manager.debate_mode:
            return await self._debate_mode_inference(prompt)

        # Two-phase logic: escalate to premium providers if Phase 1 confidence is low
        if (
            self.ensemble_manager.config.get("ensemble", {})
            .get("two_phase", {})
            .get("enabled", False)
        ):
            return await self.ensemble_manager.aggregate_decisions_two_phase(
                prompt,
                asset_pair,
                market_data,
                lambda provider, prompt_text: self._query_single_provider(
                    provider, prompt_text
                ),
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
        logger.info(
            f"Using simple parallel ensemble with {len(self.ensemble_manager.enabled_providers)} providers"
        )

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
                if self.ensemble_manager._is_valid_provider_response(
                    decision, provider
                ):
                    provider_decisions[provider] = decision
                    logger.debug(
                        f"Provider {provider} -> {decision.get('action')} ({decision.get('confidence')}%)"
                    )
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
        final = await self.ensemble_manager.aggregate_decisions(
            provider_decisions=provider_decisions, failed_providers=failed_providers
        )

        # Enrich metadata with provider tracing details
        try:
            # Import inline to avoid circular dependencies
            from .provider_tiers import is_ollama_model

            queried = list(self.ensemble_manager.enabled_providers)
            local_models_used = [
                p
                for p in provider_decisions.keys()
                if p == "local" or is_ollama_model(p)
            ]

            meta = final.setdefault("ensemble_metadata", {})
            meta["providers_queried"] = queried
            # successful providers are already captured in providers_used, but add explicit alias
            meta["providers_succeeded"] = list(provider_decisions.keys())
            meta["local_models_used"] = local_models_used
        except Exception as e:
            logger.debug(f"Metadata enrichment failed: {e}")

        return final

    async def _local_ai_inference(
        self, prompt: str, model_name: Optional[str] = None
    ) -> Dict[str, Any]:
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

        from .decision_validation import build_fallback_decision

        try:
            from .local_llm_provider import LocalLLMProvider

            # Create config with model override if specified
            provider_config = dict(
                self.config,
                model_name=model_name or self.config.get("model_name", "default"),
            )
            provider = LocalLLMProvider(provider_config)
            # Run synchronous query in a separate thread
            return await asyncio.to_thread(provider.query, prompt)
        except ImportError as e:
            logger.error(
                f"Local LLM failed due to missing import: {e}",
                extra={
                    "provider": "local",
                    "model": model_name or self.config.get("model_name", "default"),
                    "failure_type": "dependency",
                    "error_class": type(e).__name__,
                    "ensemble_mode": self.ai_provider == "ensemble",
                },
            )
            # Re-raise in ensemble mode for proper provider failure tracking
            if self.ai_provider == "ensemble":
                raise
            return build_fallback_decision(
                "Local LLM import error, using fallback decision."
            )
        except RuntimeError as e:
            logger.error(
                f"Local LLM failed due to runtime error: {e}",
                extra={
                    "provider": "local",
                    "model": model_name or self.config.get("model_name", "default"),
                    "failure_type": "infrastructure",
                    "error_class": type(e).__name__,
                    "ensemble_mode": self.ai_provider == "ensemble",
                },
            )
            # Re-raise in ensemble mode for proper provider failure tracking
            if self.ai_provider == "ensemble":
                raise
            return build_fallback_decision(
                f"Local LLM runtime error: {str(e)}, using fallback decision."
            )
        except Exception as e:
            logger.error(
                f"Local LLM failed due to unexpected error: {e}",
                extra={
                    "provider": "local",
                    "model": model_name or self.config.get("model_name", "default"),
                    "failure_type": "unknown",
                    "error_class": type(e).__name__,
                    "ensemble_mode": self.ai_provider == "ensemble",
                },
            )
            # Re-raise in ensemble mode for proper provider failure tracking
            if self.ai_provider == "ensemble":
                raise
            return build_fallback_decision(
                f"Local LLM unexpected error: {str(e)}, using fallback decision."
            )

    async def _cli_ai_inference(self, prompt: str) -> Dict[str, Any]:
        logger.info("CLI AI inference (placeholder)")
        await asyncio.sleep(0.01)
        return {
            "action": "HOLD",
            "confidence": 50,
            "reasoning": "CLI placeholder",
            "amount": 0.0,
        }

    async def _codex_ai_inference(self, prompt: str) -> Dict[str, Any]:
        logger.info("Codex AI inference (placeholder)")
        await asyncio.sleep(0.01)
        return {
            "action": "HOLD",
            "confidence": 50,
            "reasoning": "Codex placeholder",
            "amount": 0.0,
        }

    async def _gemini_ai_inference(self, prompt: str) -> Dict[str, Any]:
        logger.info("Gemini AI inference (placeholder)")
        await asyncio.sleep(0.01)
        return {
            "action": "HOLD",
            "confidence": 50,
            "reasoning": "Gemini placeholder",
            "amount": 0.0,
        }

    def _is_valid_provider_response(
        self, decision: Dict[str, Any], provider: str
    ) -> bool:
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

        if "action" not in decision or "confidence" not in decision:
            logger.warning(
                f"Provider {provider}: missing required keys 'action' or 'confidence'"
            )
            return False

        if decision.get("action") not in ["BUY", "SELL", "HOLD"]:
            logger.warning(
                f"Provider {provider}: invalid action '{decision.get('action')}'"
            )
            return False

        conf = decision.get("confidence")
        if not isinstance(conf, (int, float)):
            logger.warning(f"Provider {provider}: confidence is not numeric")
            return False
        if not (0 <= conf <= 100):
            logger.warning(
                f"Provider {provider}: Confidence {conf} out of range [0, 100]"
            )
            return False

        if "reasoning" in decision and not decision["reasoning"].strip():
            logger.warning(f"Provider {provider}: reasoning is empty")
            return False
        return True

    @staticmethod
    def _determine_position_type(action: str) -> Optional[str]:
        """
        Determine position type from action.

        Args:
            action: Trading action (BUY, SELL, or HOLD)

        Returns:
            Position type: 'LONG' for BUY, 'SHORT' for SELL, None for HOLD
        """
        if action == "BUY":
            return "LONG"
        elif action == "SELL":
            return "SHORT"
        return None

    def _select_relevant_balance(
        self, balance: Dict[str, float], asset_pair: str, asset_type: str
    ) -> tuple:
        """
        Select platform-specific balance based on asset type.

        Args:
            balance: Full balance dictionary (may contain multiple platforms)
            asset_pair: Asset pair being traded
            asset_type: Asset type ('crypto', 'forex', 'unknown')

        Returns:
            Tuple of (relevant_balance, balance_source, is_crypto, is_forex)
        """
        # Delegating to the market analyzer
        return self.market_analyzer._select_relevant_balance(
            balance, asset_pair, asset_type
        )

    def _has_existing_position(
        self,
        asset_pair: str,
        portfolio: Optional[Dict],
        monitoring_context: Optional[Dict],
    ) -> bool:
        """
        Check if there's an existing position in portfolio or active trades.

        Args:
            asset_pair: Asset pair to check
            portfolio: Portfolio breakdown with holdings
            monitoring_context: Monitoring context with active positions

        Returns:
            True if existing position found, False otherwise
        """
        # Delegating to the market analyzer
        return self.market_analyzer._has_existing_position(
            asset_pair, portfolio, monitoring_context
        )

    def _calculate_position_sizing_params(
        self,
        context: Dict[str, Any],
        current_price: float,
        action: str,
        has_existing_position: bool,
        relevant_balance: Dict[str, float],
        balance_source: str,
        signal_only_default: bool = False,
    ) -> Dict[str, Any]:
        """
        Calculate all position sizing parameters.

        Args:
            context: Decision context with market data and config
            current_price: Current asset price
            action: Trading action (BUY, SELL, HOLD)
            has_existing_position: Whether an existing position exists
            relevant_balance: Platform-specific balance
            balance_source: Name of balance source (for logging)
            signal_only_default: Whether signal-only mode is enabled

        Returns:
            Dict with keys:
            - recommended_position_size: Position size in units
            - stop_loss_price: Stop loss price level
            - sizing_stop_loss_percentage: Stop loss percentage used
            - risk_percentage: Risk percentage used
            - signal_only: Whether this is signal-only mode
        """
        # Delegating to the position sizing calculator
        return self.position_sizing_calc.calculate_position_sizing_params(
            context,
            current_price,
            action,
            has_existing_position,
            relevant_balance,
            balance_source,
            signal_only_default,
        )

    def _create_decision(
        self, asset_pair: str, context: Dict[str, Any], ai_response: Dict[str, Any]
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
        # Extract basic decision parameters
        balance = context.get("balance", {})
        action = ai_response.get("action", "HOLD")
        asset_type = context["market_data"].get("type", "unknown")

        # Select relevant balance based on asset type
        (
            relevant_balance,
            balance_source,
            is_crypto,
            is_forex,
        ) = self._select_relevant_balance(balance, asset_pair, asset_type)

        # Check for existing position
        has_existing_position = self._has_existing_position(
            asset_pair, context.get("portfolio"), context.get("monitoring_context")
        )

        # Calculate position sizing parameters
        # Prefer decision_engine.signal_only_default (used across the codebase/tests),
        # fall back to top-level for backward compatibility.
        # Use centralized config normalization to support nested/flat shapes
        decision_cfg = normalize_decision_config(self.config)
        signal_only_default = bool(
            decision_cfg.get(
                "signal_only_default", self.config.get("signal_only_default", False)
            )
        )
        sizing_params = self._calculate_position_sizing_params(
            context=context,
            current_price=context["market_data"].get("close", 0),
            action=action,
            has_existing_position=has_existing_position,
            relevant_balance=relevant_balance,
            balance_source=balance_source,
            signal_only_default=signal_only_default,
        )

        # Delegating to the decision validator
        decision = self.validator.create_decision(
            asset_pair=asset_pair,
            context=context,
            ai_response=ai_response,
            position_sizing_result=sizing_params,
            relevant_balance=relevant_balance,
            balance_source=balance_source,
            has_existing_position=has_existing_position,
            is_crypto=is_crypto,
            is_forex=is_forex,
        )

        # Update the AI provider and model name from the AI manager
        decision["ai_provider"] = self.ai_manager.ai_provider
        decision["model_name"] = self.ai_manager.model_name

        return decision

    def calculate_dynamic_stop_loss(
        self,
        current_price: float,
        context: Dict[str, Any],
        default_percentage: float = 0.02,
        atr_multiplier: float = 2.0,
        min_percentage: float = 0.01,
        max_percentage: float = 0.05,
    ) -> float:
        """
        Calculate dynamic stop-loss percentage based on market volatility (ATR).

        Args:
            current_price: Current asset price
            context: Decision context containing market_data and monitoring_context
            default_percentage: Fallback stop-loss percentage if ATR unavailable (default: 0.02 = 2%)
            atr_multiplier: Multiple of ATR to use for stop-loss (default: 2.0)
            min_percentage: Minimum stop-loss percentage (default: 0.01 = 1%)
            max_percentage: Maximum stop-loss percentage (default: 0.05 = 5%)

        Returns:
            Stop-loss percentage as decimal (e.g., 0.02 for 2%)
        """
        # Delegating to the position sizing calculator
        return self.position_sizing_calc.calculate_dynamic_stop_loss(
            current_price,
            context,
            default_percentage,
            atr_multiplier,
            min_percentage,
            max_percentage,
        )

    def calculate_position_size(
        self,
        account_balance: float,
        risk_percentage: float = 0.01,
        entry_price: float = 0,
        stop_loss_percentage: float = 0.02,
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
        # Delegating to the position sizing calculator
        return self.position_sizing_calc.calculate_position_size(
            account_balance, risk_percentage, entry_price, stop_loss_percentage
        )

    def set_monitoring_context(self, monitoring_provider):
        """
        Set the monitoring context provider for live trade awareness.

        Args:
            monitoring_provider: MonitoringContextProvider instance
        """
        self.monitoring_provider = monitoring_provider
        self.market_analyzer.monitoring_provider = (
            monitoring_provider  # Also update the analyzer
        )
        logger.info("Monitoring context provider attached to decision engine")

    async def generate_decision(
        self,
        asset_pair: str,
        market_data: Dict[str, Any],
        balance: Dict[str, float],
        portfolio: Optional[Dict[str, Any]] = None,
        memory_context: Optional[Dict[str, Any]] = None,
        monitoring_context: Optional[Dict[str, Any]] = None,
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
        # Root span for decision generation
        if tracer:
            span_cm = tracer.start_as_current_span(
                "decision.generate",
                attributes={
                    "asset_pair": asset_pair,
                    "portfolio_present": bool(portfolio),
                    "memory_present": bool(memory_context),
                },
            )
        else:
            span_cm = None
        if span_cm:
            span_cm.__enter__()
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
                monitoring_context = self.monitoring_provider.get_monitoring_context(
                    asset_pair=asset_pair
                )
                # Handle active_positions as either list or dict
                active_pos = monitoring_context.get("active_positions", [])
                if isinstance(active_pos, dict):
                    num_positions = len(active_pos.get("futures", []))
                elif isinstance(active_pos, list):
                    num_positions = len(active_pos)
                else:
                    num_positions = 0

                logger.info(
                    "Monitoring context loaded: %d active positions, %d slots",
                    num_positions,
                    monitoring_context.get("slots_available", 0),
                )
                if tracer:
                    cur = trace.get_current_span()
                    cur.set_attribute("monitor.active_positions", num_positions)
                    cur.set_attribute(
                        "monitor.slots_available",
                        monitoring_context.get("slots_available", 0),
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
            monitoring_context,
        )

        # Retrieve semantic memory
        if self.vector_memory:
            query = f"Asset: {asset_pair}. Market: {market_data.get('trend', 'neutral')}, RSI {market_data.get('rsi', 'N/A')}. Volatility: {context.get('volatility', 'N/A')}."
            try:
                similar = self.vector_memory.find_similar(query, top_k=3)
                context["semantic_memory"] = similar
            except Exception as e:
                logger.error(
                    f"Failed to retrieve semantic memory for asset {asset_pair} with query '{query}': {e}"
                )
                context["semantic_memory"] = []

        # Generate AI prompt
        prompt = self._create_ai_prompt(context)

        # Compress context window to reduce token usage
        prompt = self._compress_context_window(prompt, max_tokens=3000)

        # Get AI recommendation (pass asset_pair and market_data for two-phase ensemble)
        ai_response = await self._query_ai(
            prompt, asset_pair=asset_pair, market_data=market_data
        )

        # Apply optional veto logic before final decision creation
        ai_response, veto_metadata = self._apply_veto_logic(ai_response, context)
        if veto_metadata:
            ai_response["veto_metadata"] = veto_metadata

        # Validate AI response action to ensure it's one of the allowed values
        if ai_response.get("action") not in ["BUY", "SELL", "HOLD"]:
            logger.warning(
                f"AI provider returned an invalid action: "
                f"'{ai_response.get('action')}'. Defaulting to 'HOLD'."
            )
            ai_response["action"] = "HOLD"

        # Create structured decision object
        decision = self._create_decision(asset_pair, context, ai_response)
        if span_cm:
            span_cm.__exit__(None, None, None)

        return decision

    async def _create_decision_context(
        self,
        asset_pair: str,
        market_data: Dict[str, Any],
        balance: Dict[str, float],
        portfolio: Optional[Dict[str, Any]] = None,
        memory_context: Optional[Dict[str, Any]] = None,
        monitoring_context: Optional[Dict[str, Any]] = None,
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
        # Delegating to the market analyzer
        return await self.market_analyzer.create_decision_context(
            asset_pair,
            market_data,
            balance,
            portfolio,
            memory_context,
            monitoring_context,
        )

    def _should_include_semantic_memory(self) -> bool:
        """
        Determine whether to include semantic memory in the prompt.
        This helps control prompt length to avoid context window overflow.
        """
        # For now, include semantic memory but we'll implement smart truncation later
        return True

    def _format_semantic_memory(self, semantic_memory: list) -> str:
        """
        Format semantic memory for inclusion in AI prompts with intelligent truncation.

        Args:
            semantic_memory: List of similar historical decisions/trades

        Returns:
            Formatted string with truncated semantic memory
        """
        if not semantic_memory:
            return "No similar historical patterns found."

        # Format the most relevant similar memories with truncation
        formatted_memories = []
        for i, memory in enumerate(semantic_memory):
            if i >= 3:  # Only include top 3 most similar memories
                break

            # Extract key fields from memory with truncation
            asset = memory.get("asset_pair", "N/A")
            action = memory.get("action", "N/A")
            outcome = memory.get("outcome", "N/A")
            confidence = memory.get("confidence", 0)
            reasoning = str(memory.get("reasoning", ""))[
                :200
            ]  # Truncate reasoning to 200 chars

            formatted_memory = (
                f"Pattern #{i+1}: {asset} | Action: {action} | "
                f"Outcome: {outcome} | Confidence: {confidence}% | "
                f"Reasoning: {reasoning}..."
            )
            formatted_memories.append(formatted_memory)

        return "HISTORICAL SIMILAR PATTERNS:\n" + "\n".join(formatted_memories)

    def _compress_context_window(self, prompt: str, max_tokens: int = 3000) -> str:
        """
        Compress the context window to fit within maximum token limits.

        Args:
            prompt: Original prompt string
            max_tokens: Maximum token count allowed (default 3000 to stay under 4k limit)

        Returns:
            Compressed prompt string
        """
        try:
            import tiktoken

            # Get encoding for the model (using gpt-3.5-turbo as a proxy for tokenization)
            encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
            tokens = encoding.encode(prompt)

            if len(tokens) <= max_tokens:
                return prompt

            # If we have too many tokens, we'll intelligently compress
            # by truncating less critical sections first
            lines = prompt.split("\n")

            # Identify sections to compress
            compressed_lines = []
            current_token_count = 0

            # Keep essential sections like the main instruction and asset info
            essential_parts = [
                "Asset Pair:",
                "TASK:",
                "ANALYSIS OUTPUT REQUIRED:",
                "ACCOUNT BALANCE:",
            ]

            for line in lines:
                # Check if this is an essential part
                is_essential = any(essential in line for essential in essential_parts)

                # Temporary tokenization to estimate this line's tokens
                line_tokens = len(encoding.encode(line))

                # If adding this line would exceed the limit
                if current_token_count + line_tokens > max_tokens and not is_essential:
                    # Skip less critical information
                    continue
                elif (
                    current_token_count + line_tokens > max_tokens * 0.95
                ):  # 95% of max
                    # If we're near the limit, stop adding unless it's essential
                    if is_essential:
                        compressed_lines.append(line)
                        current_token_count += line_tokens
                    else:
                        break
                else:
                    compressed_lines.append(line)
                    current_token_count += line_tokens

            compressed_prompt = "\n".join(compressed_lines)

            # If still too long, perform more aggressive compression
            if current_token_count > max_tokens:
                # Additional strategy: truncate long data sections
                sections = compressed_prompt.split("===")
                main_sections = []
                temp_prompt = ""

                for section in sections:
                    temp_prompt += section + "==="  # Add back separator
                    temp_tokens = len(encoding.encode(temp_prompt))

                    if temp_tokens > max_tokens:
                        # Try to compress this section by removing some content
                        lines_in_section = section.split("\n")
                        compressed_section = []
                        section_token_count = 0

                        for line in lines_in_section:
                            line_tokens = len(encoding.encode(line))

                            if (
                                section_token_count + line_tokens
                                <= max_tokens - current_token_count
                            ):
                                compressed_section.append(line)
                                section_token_count += line_tokens
                            else:
                                # Add a truncation note if needed
                                compressed_section.append(
                                    "... [SECTION TRUNCATED FOR LENGTH]"
                                )
                                break
                        main_sections.append("\n".join(compressed_section))
                        break
                    else:
                        main_sections.append(section)
                        current_token_count = temp_tokens

                compressed_prompt = "===".join(main_sections)

            return compressed_prompt

        except ImportError:
            # If tiktoken is not available, estimate using word-based tokenization
            # Rough estimate: 1 token ≈ 4 characters or 0.75 words
            estimated_tokens = len(prompt) // 4
            if estimated_tokens <= max_tokens:
                return prompt
            else:
                # Truncate to approximately max_tokens
                truncate_at = max_tokens * 4
                return prompt[:truncate_at] + "... [TRUNCATED FOR LENGTH]"

        if len(tokens) <= max_tokens:
            return prompt

        # If we have too many tokens, we'll intelligently compress
        # by truncating less critical sections first
        lines = prompt.split("\n")

        # Identify sections to compress
        compressed_lines = []
        current_token_count = 0

        # Keep essential sections like the main instruction and asset info
        essential_parts = [
            "Asset Pair:",
            "TASK:",
            "ANALYSIS OUTPUT REQUIRED:",
            "ACCOUNT BALANCE:",
        ]

        for line in lines:
            # Check if this is an essential part
            is_essential = any(essential in line for essential in essential_parts)

            # Temporary tokenization to estimate this line's tokens
            line_tokens = len(encoding.encode(line))

            # If adding this line would exceed the limit
            if current_token_count + line_tokens > max_tokens and not is_essential:
                # Skip less critical information
                continue
            elif current_token_count + line_tokens > max_tokens * 0.95:  # 95% of max
                # If we're near the limit, stop adding unless it's essential
                if is_essential:
                    compressed_lines.append(line)
                    current_token_count += line_tokens
                else:
                    break
            else:
                compressed_lines.append(line)
                current_token_count += line_tokens

        compressed_prompt = "\n".join(compressed_lines)

        # If still too long, perform more aggressive compression
        if current_token_count > max_tokens:
            # Additional strategy: truncate long data sections
            sections = compressed_prompt.split("===")
            main_sections = []
            temp_prompt = ""

            for section in sections:
                temp_prompt += section + "==="  # Add back separator
                temp_tokens = len(encoding.encode(temp_prompt))

                if temp_tokens > max_tokens:
                    # Try to compress this section by removing some content
                    lines_in_section = section.split("\n")
                    compressed_section = []
                    section_token_count = 0

                    for line in lines_in_section:
                        line_tokens = len(encoding.encode(line))

                        if (
                            section_token_count + line_tokens
                            <= max_tokens - current_token_count
                        ):
                            compressed_section.append(line)
                            section_token_count += line_tokens
                        else:
                            # Add a truncation note if needed
                            compressed_section.append(
                                "... [SECTION TRUNCATED FOR LENGTH]"
                            )
                            break
                    main_sections.append("\n".join(compressed_section))
                    break
                else:
                    main_sections.append(section)
                    current_token_count = temp_tokens

            compressed_prompt = "===".join(main_sections)

        return compressed_prompt
