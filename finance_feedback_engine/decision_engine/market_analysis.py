"""Market analysis context for trading decisions."""

import asyncio
from datetime import datetime, timedelta
import logging
import pandas as pd
import pytz
from typing import Dict, Any, Optional

from finance_feedback_engine.utils.market_regime_detector import MarketRegimeDetector
from finance_feedback_engine.utils.market_schedule import MarketSchedule
from finance_feedback_engine.utils.validation import validate_data_freshness

logger = logging.getLogger(__name__)


class MarketAnalysisContext:
    """
    Manager for market analysis and context creation.
    """

    def __init__(self, config: Dict[str, Any], data_provider=None, monitoring_provider=None):
        self.config = config
        self.data_provider = data_provider
        self.monitoring_provider = monitoring_provider
        
        # Initialize market schedule for session awareness
        self.market_schedule = MarketSchedule()

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

    def _select_relevant_balance(
        self,
        balance: Dict[str, float],
        asset_pair: str,
        asset_type: str
    ) -> tuple:
        """
        Select platform-specific balance based on asset type.

        Extracts the appropriate balance for the asset being traded:
        - Crypto: Coinbase balances (FUTURES_USD, SPOT_USD, SPOT_USDC, or coinbase_*)
        - Forex: Oanda balances (oanda_*)
        - Unknown: All balances

        Args:
            balance: Full balance dictionary (may contain multiple platforms)
            asset_pair: Asset pair being traded
            asset_type: Asset type ('crypto', 'forex', 'unknown')

        Returns:
            Tuple of (relevant_balance, balance_source, is_crypto, is_forex)
        """
        # Determine asset classification
        is_crypto = (
            'BTC' in asset_pair
            or 'ETH' in asset_pair
            or asset_type == 'crypto'
        )
        is_forex = '_' in asset_pair or asset_type == 'forex'

        # Extract the appropriate balance based on asset type
        relevant_balance = {}
        balance_source = 'Unknown'

        if balance and isinstance(balance, dict):
            if is_crypto:
                # Filter for Coinbase balances - check for both new format and legacy format
                # New format: FUTURES_USD, SPOT_USD, SPOT_USDC (from coinbase_advanced)
                # Legacy format: coinbase_* prefixed keys
                coinbase_keys = [
                    k for k in balance.keys()
                    if k.startswith('coinbase_')
                    or k in ['FUTURES_USD', 'SPOT_USD', 'SPOT_USDC']
                ]

                if coinbase_keys:
                    relevant_balance = {k: balance[k] for k in coinbase_keys}
                    balance_source = 'Coinbase'

                    # Log available balance sources for debugging
                    logger.debug(
                        "Coinbase balance keys found: %s (total: $%.2f)",
                        ', '.join(coinbase_keys),
                        sum(relevant_balance.values())
                    )

            elif is_forex:
                # Filter for Oanda balances
                relevant_balance = {
                    k: v for k, v in balance.items()
                    if k.startswith('oanda_')
                }
                balance_source = 'Oanda'
            else:
                # Unknown type, use all balances as fallback
                relevant_balance = balance
                balance_source = 'Combined'

            # Fallback: Check for unified cash balance keys when platform-specific keys are absent
            if not relevant_balance:
                # Try USD, USDC, or other generic keys
                fallback_keys = [k for k in ['USD', 'USDC', 'USDT'] if k in balance]
                if fallback_keys:
                    relevant_balance = {k: balance[k] for k in fallback_keys}
                    balance_source = '/'.join(fallback_keys)
                    logger.debug(
                        "Using fallback balance keys: %s (total: $%.2f)",
                        balance_source,
                        sum(relevant_balance.values())
                    )

        return relevant_balance, balance_source, is_crypto, is_forex

    def _has_existing_position(
        self,
        asset_pair: str,
        portfolio: Optional[Dict],
        monitoring_context: Optional[Dict]
    ) -> bool:
        """
        Check if there's an existing position in portfolio or active trades.

        Checks both:
        1. Spot holdings in portfolio
        2. Futures/margin positions in monitoring context

        Args:
            asset_pair: Asset pair to check
            portfolio: Portfolio breakdown with holdings
            monitoring_context: Monitoring context with active positions

        Returns:
            True if existing position found, False otherwise
        """
        # Extract base currency from asset pair
        # IMPORTANT: Replace USDT before USD to avoid "BTCUSDT" -> "BTCT"
        asset_base = (
            asset_pair.replace('USDT', '')
            .replace('USD', '')
            .replace('_', '')
        )

        has_position = False

        # Check portfolio holdings
        if portfolio and portfolio.get('holdings'):
            for holding in portfolio.get('holdings', []):
                if (
                    holding.get('currency') == asset_base
                    and holding.get('amount', 0) > 0
                ):
                    has_position = True
                    break

        # Check monitoring context for active positions (futures/margin)
        if monitoring_context and not has_position:
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
                    has_position = True
                    break

        return has_position

    def _format_memory_context(self, context: Dict[str, Any]) -> str:
        """Format portfolio memory context for AI prompts."""
        if not context or not context.get('has_history'):
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

        streak = context.get('current_streak', {})
        if streak.get('type'):
            lines.append(
                f"  Current Streak: {streak.get('count', 0)} {streak.get('type')} trades"
            )

        lines.append("\nAction Performance:")
        for action, stats in context.get('action_performance', {}).items():
            lines.append(
                f"  {action}: {stats.get('win_rate', 0):.1f}% win rate, "
                f"${stats.get('total_pnl', 0):.2f} P&L ({stats.get('count', 0)} trades)"
            )

        provider_perf = context.get('provider_performance', {})
        if provider_perf:
            lines.append("\nProvider Performance:")
            for provider, stats in provider_perf.items():
                lines.append(
                    f"  {provider}: {stats.get('win_rate', 0):.1f}% win rate "
                    f"({stats.get('count', 0)} trades)"
                )

        if context.get('asset_specific'):
            asset_stats = context['asset_specific']
            lines.append(
                f"\n{context.get('asset_pair', 'This Asset')} Specific:"
            )
            lines.append(
                f"  {asset_stats.get('total_trades', 0)} trades, "
                f"{asset_stats.get('win_rate', 0):.1f}% win rate, "
                f"${asset_stats.get('total_pnl', 0):.2f} total P&L"
            )

        long_term = context.get('long_term_performance')
        if long_term and long_term.get('has_data'):
            lines.append("\nLong-Term Performance:")
            lines.append(
                f"  Period: last {long_term.get('period_days', 0)} days"
            )
            lines.append(
                f"  Trades: {long_term.get('total_trades', 0)} | Win Rate: {long_term.get('win_rate', 0):.1f}%"
            )
            lines.append(
                f"  Profit Factor: {long_term.get('profit_factor', 0):.2f} | ROI: {long_term.get('roi_percentage', 0):.2f}%"
            )
            lines.append(
                f"  Realized P&L: ${long_term.get('realized_pnl', 0):.2f}"
            )
            avg_win = long_term.get('avg_win')
            avg_loss = long_term.get('avg_loss')
            if avg_win is not None and avg_loss is not None:
                lines.append(
                    f"  Avg Win: ${avg_win:.2f} | Avg Loss: ${avg_loss:.2f}"
                )
            best = long_term.get('best_trade')
            worst = long_term.get('worst_trade')
            if best is not None and worst is not None:
                lines.append(
                    f"  Best Trade: ${best:.2f} | Worst Trade: ${worst:.2f}"
                )

        lines.append("=" * 35)
        return "\n".join(lines)

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
            asset = memory.get('asset_pair', 'N/A')
            action = memory.get('action', 'N/A')
            outcome = memory.get('outcome', 'N/A')
            confidence = memory.get('confidence', 0)
            reasoning = str(memory.get('reasoning', ''))[:200]  # Truncate reasoning to 200 chars

            formatted_memory = (
                f"Pattern #{i+1}: {asset} | Action: {action} | "
                f"Outcome: {outcome} | Confidence: {confidence}% | "
                f"Reasoning: {reasoning}..."
            )
            formatted_memories.append(formatted_memory)

        return "HISTORICAL SIMILAR PATTERNS:\n" + "\n".join(formatted_memories)

    async def create_decision_context(
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