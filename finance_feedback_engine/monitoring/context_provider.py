"""Monitoring context provider for AI decision pipeline integration."""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class MonitoringContextProvider:
    """
    Provides real-time monitoring context for AI decision making.
    
    Aggregates:
    - Active open positions (from trade monitor)
    - Recent trade performance (from metrics collector)
    - Real-time P&L exposure
    - Portfolio risk metrics
    - Position concentration analysis
    
    Integrates with DecisionEngine to give AI models full awareness
    of actual trading state when making new decisions.
    """
    
    def __init__(self, platform, trade_monitor=None, metrics_collector=None):
        """
        Initialize monitoring context provider.
        
        Args:
            platform: Trading platform instance
            trade_monitor: Optional TradeMonitor instance for active trades
            metrics_collector: Optional TradeMetricsCollector for history
        """
        self.platform = platform
        self.trade_monitor = trade_monitor
        self.metrics_collector = metrics_collector
        
        logger.info("MonitoringContextProvider initialized")
    
    def get_monitoring_context(
        self,
        asset_pair: Optional[str] = None,
        lookback_hours: int = 24
    ) -> Dict[str, Any]:
        """
        Get comprehensive monitoring context for AI decision making.
        
        Args:
            asset_pair: Specific asset to focus on (None = all assets)
            lookback_hours: Hours to look back for recent trades
            
        Returns:
            Dictionary with monitoring context including:
            - active_positions: Live positions from platform
            - active_trades_count: Number of monitored trades
            - recent_performance: Recent trade metrics
            - risk_metrics: Exposure and risk analysis
            - position_concentration: Asset allocation breakdown
        """
        context = {
            'timestamp': datetime.utcnow().isoformat(),
            'has_monitoring_data': False,
            'active_positions': [],
            'active_trades_count': 0,
            'recent_performance': {},
            'risk_metrics': {},
            'position_concentration': {},
        }
        
        try:
            # Get active positions from platform
            if hasattr(self.platform, 'get_portfolio_breakdown'):
                portfolio = self.platform.get_portfolio_breakdown()
                
                # Extract active positions
                futures_positions = portfolio.get('futures_positions', [])
                holdings = portfolio.get('holdings', [])
                
                # Filter by asset pair if specified
                if asset_pair:
                    futures_positions = [
                        p for p in futures_positions
                        if asset_pair in p.get('product_id', '')
                    ]
                    holdings = [
                        h for h in holdings
                        if asset_pair in h.get('asset', '')
                    ]
                
                context['active_positions'] = {
                    'futures': futures_positions,
                    'spot': holdings
                }
                
                # Calculate risk metrics from active positions
                context['risk_metrics'] = self._calculate_risk_metrics(
                    futures_positions,
                    portfolio
                )
                
                # Position concentration analysis
                context['position_concentration'] = (
                    self._analyze_concentration(portfolio)
                )
                
                context['has_monitoring_data'] = True
                
        except Exception as e:
            logger.warning(f"Could not fetch active positions: {e}")
        
        # Get active trade monitoring data
        if self.trade_monitor:
            try:
                context['active_trades_count'] = len(
                    self.trade_monitor.active_trackers
                )
                context['max_concurrent_trades'] = (
                    self.trade_monitor.MAX_CONCURRENT_TRADES
                )
                context['slots_available'] = (
                    self.trade_monitor.MAX_CONCURRENT_TRADES -
                    len(self.trade_monitor.active_trackers)
                )
            except Exception as e:
                logger.warning(f"Could not fetch active trades: {e}")
        
        # Get recent performance metrics
        if self.metrics_collector:
            try:
                context['recent_performance'] = (
                    self._get_recent_performance(
                        asset_pair,
                        lookback_hours
                    )
                )
            except Exception as e:
                logger.warning(f"Could not fetch recent performance: {e}")
        
        return context
    
    def _calculate_risk_metrics(
        self,
        futures_positions: List[Dict[str, Any]],
        portfolio: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calculate risk metrics from active positions.
        
        Returns:
            Risk metrics including:
            - total_exposure_usd: Total notional value of positions
            - unrealized_pnl: Total unrealized P&L
            - long_exposure: Value of long positions
            - short_exposure: Value of short positions
            - net_exposure: Long - Short exposure
            - leverage_estimate: Rough leverage ratio
        """
        total_exposure = 0.0
        unrealized_pnl = 0.0
        long_exposure = 0.0
        short_exposure = 0.0
        
        for pos in futures_positions:
            contracts = pos.get('contracts', 0)
            current_price = pos.get('current_price', 0)
            side = pos.get('side', 'LONG')
            
            notional = abs(contracts * current_price)
            total_exposure += notional
            unrealized_pnl += pos.get('unrealized_pnl', 0)
            
            if side == 'LONG':
                long_exposure += notional
            else:
                short_exposure += notional
        
        total_value = portfolio.get('total_value_usd', 1)
        leverage = total_exposure / total_value if total_value > 0 else 0
        
        return {
            'total_exposure_usd': total_exposure,
            'unrealized_pnl': unrealized_pnl,
            'long_exposure': long_exposure,
            'short_exposure': short_exposure,
            'net_exposure': long_exposure - short_exposure,
            'leverage_estimate': leverage,
            'account_value': total_value
        }
    
    def _analyze_concentration(
        self,
        portfolio: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze position concentration across assets.
        
        Returns:
            Concentration metrics including:
            - num_positions: Number of open positions
            - largest_position_pct: Largest single position as % of portfolio
            - top_3_concentration: % in top 3 positions
            - diversification_score: 0-100 (higher = more diversified)
        """
        futures_positions = portfolio.get('futures_positions', [])
        total_value = portfolio.get('total_value_usd', 1)
        
        if not futures_positions or total_value <= 0:
            return {
                'num_positions': 0,
                'largest_position_pct': 0,
                'top_3_concentration': 0,
                'diversification_score': 0
            }
        
        # Calculate position sizes as % of portfolio
        position_sizes = []
        for pos in futures_positions:
            contracts = abs(pos.get('contracts', 0))
            current_price = pos.get('current_price', 0)
            notional = contracts * current_price
            pct = (notional / total_value) * 100
            position_sizes.append(pct)
        
        position_sizes.sort(reverse=True)
        
        largest_pct = position_sizes[0] if position_sizes else 0
        top_3_pct = sum(position_sizes[:3])
        
        # Diversification score (simplified Herfindahl index)
        # Lower concentration = higher score
        herfindahl = sum(p**2 for p in position_sizes) / 10000
        diversification = max(0, 100 - (herfindahl * 100))
        
        return {
            'num_positions': len(futures_positions),
            'largest_position_pct': largest_pct,
            'top_3_concentration': top_3_pct,
            'diversification_score': diversification
        }
    
    def _get_recent_performance(
        self,
        asset_pair: Optional[str],
        lookback_hours: int
    ) -> Dict[str, Any]:
        """
        Get recent trade performance metrics.
        
        Returns:
            Recent performance including:
            - trades_count: Number of trades in lookback period
            - win_rate: % of profitable trades
            - avg_pnl: Average P&L per trade
            - total_pnl: Total P&L in period
        """
        if not self.metrics_collector:
            return {}
        
        try:
            # Get all metrics files
            metrics_dir = Path("data/trade_metrics")
            if not metrics_dir.exists():
                return {}
            
            cutoff_time = datetime.utcnow() - timedelta(hours=lookback_hours)
            recent_trades = []
            
            for metric_file in metrics_dir.glob("trade_*.json"):
                try:
                    with open(metric_file, 'r', encoding='utf-8') as f:
                        metrics = json.load(f)
                    
                    # Check if within lookback period
                    entry_time_str = metrics.get('entry_time', '')
                    if entry_time_str.endswith('Z'):
                        entry_time_str = entry_time_str[:-1] + '+00:00'
                    entry_time = datetime.fromisoformat(entry_time_str)
                    
                    if entry_time >= cutoff_time:
                        # Filter by asset if specified
                        if asset_pair:
                            product = metrics.get('product_id', '')
                            if asset_pair not in product:
                                continue
                        
                        recent_trades.append(metrics)
                
                except Exception as e:
                    logger.debug(f"Error reading metric file: {e}")
                    continue
            
            if not recent_trades:
                return {
                    'trades_count': 0,
                    'lookback_hours': lookback_hours
                }
            
            # Calculate aggregate metrics
            profitable = sum(
                1 for t in recent_trades
                if t.get('realized_pnl', 0) > 0
            )
            total_pnl = sum(t.get('realized_pnl', 0) for t in recent_trades)
            
            return {
                'trades_count': len(recent_trades),
                'win_rate': (profitable / len(recent_trades)) * 100,
                'avg_pnl': total_pnl / len(recent_trades),
                'total_pnl': total_pnl,
                'lookback_hours': lookback_hours
            }
            
        except Exception as e:
            logger.error(f"Error getting recent performance: {e}")
            return {}
    
    def format_for_ai_prompt(self, context: Dict[str, Any]) -> str:
        """
        Format monitoring context for inclusion in AI prompts.
        
        Args:
            context: Monitoring context from get_monitoring_context()
            
        Returns:
            Formatted string for AI prompt injection
        """
        if not context.get('has_monitoring_data'):
            return "\nNo active trading positions currently.\n"
        
        lines = ["\n=== LIVE TRADING CONTEXT ==="]
        
        # Active positions summary
        active_pos = context.get('active_positions', {})
        futures = active_pos.get('futures', [])
        
        if futures:
            lines.append(f"\nActive Positions: {len(futures)}")
            for pos in futures:
                side = pos.get('side', 'UNKNOWN')
                product = pos.get('product_id', 'N/A')
                contracts = pos.get('contracts', 0)
                entry = pos.get('entry_price', 0)
                current = pos.get('current_price', 0)
                pnl = pos.get('unrealized_pnl', 0)
                
                pnl_sign = '+' if pnl >= 0 else ''
                lines.append(
                    f"  • {side} {product}: {contracts:.2f} contracts "
                    f"@ ${entry:.2f} (current ${current:.2f}) "
                    f"| P&L: {pnl_sign}${pnl:.2f}"
                )
        else:
            lines.append("\nNo active positions")
        
        # Risk metrics
        risk = context.get('risk_metrics', {})
        if risk:
            lines.append(f"\nRisk Exposure:")
            lines.append(
                f"  • Total Exposure: ${risk.get('total_exposure_usd', 0):,.2f}"
            )
            lines.append(
                f"  • Unrealized P&L: ${risk.get('unrealized_pnl', 0):,.2f}"
            )
            lines.append(
                f"  • Leverage: {risk.get('leverage_estimate', 0):.2f}x"
            )
            lines.append(
                f"  • Net Exposure: ${risk.get('net_exposure', 0):,.2f}"
            )
        
        # Position concentration
        conc = context.get('position_concentration', {})
        if conc and conc.get('num_positions', 0) > 0:
            lines.append(f"\nPosition Concentration:")
            lines.append(
                f"  • Largest Position: "
                f"{conc.get('largest_position_pct', 0):.1f}% of portfolio"
            )
            lines.append(
                f"  • Diversification Score: "
                f"{conc.get('diversification_score', 0):.0f}/100"
            )
        
        # Active trade slots
        if context.get('max_concurrent_trades'):
            lines.append(
                f"\nMonitoring Capacity: "
                f"{context.get('active_trades_count', 0)}/"
                f"{context.get('max_concurrent_trades', 0)} slots used "
                f"({context.get('slots_available', 0)} available)"
            )
        
        # Recent performance
        perf = context.get('recent_performance', {})
        if perf.get('trades_count', 0) > 0:
            lines.append(
                f"\nRecent Performance "
                f"({perf.get('lookback_hours', 24)}h):"
            )
            lines.append(
                f"  • Trades: {perf.get('trades_count', 0)} "
                f"| Win Rate: {perf.get('win_rate', 0):.1f}%"
            )
            lines.append(
                f"  • Total P&L: ${perf.get('total_pnl', 0):,.2f} "
                f"| Avg: ${perf.get('avg_pnl', 0):.2f}"
            )
        
        lines.append("=" * 30 + "\n")
        
        return "\n".join(lines)
