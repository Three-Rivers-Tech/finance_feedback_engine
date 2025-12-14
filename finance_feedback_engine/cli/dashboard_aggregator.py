"""Dashboard data aggregator for live agent view.

Centralizes data collection from all agent subsystems for dashboard display.
"""

import logging
import time
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class DashboardDataAggregator:
    """Collects and normalizes data from all agent subsystems for dashboard display."""

    def __init__(self, agent, engine, trade_monitor, portfolio_memory):
        """
        Initialize dashboard data aggregator.

        Args:
            agent: TradingLoopAgent instance
            engine: FinanceFeedbackEngine instance
            trade_monitor: TradeMonitor instance
            portfolio_memory: PortfolioMemoryEngine instance
        """
        self.agent = agent
        self.engine = engine
        self.trade_monitor = trade_monitor
        self.portfolio_memory = portfolio_memory
        self._start_time = time.time()

    def get_agent_status(self) -> Dict[str, Any]:
        """
        Get agent state, cycle count, daily trades, uptime, kill-switch status.

        Returns:
            Dict with agent status information
        """
        try:
            # Get current state
            state = getattr(self.agent, 'state', None)
            state_name = state.name if state else "UNKNOWN"

            # Get counters
            cycle_count = getattr(self.agent, '_cycle_count', 0)
            daily_trades = getattr(self.agent, 'daily_trade_count', 0)

            # Calculate uptime
            agent_start = getattr(self.agent, '_start_time', self._start_time)
            uptime_seconds = time.time() - agent_start

            # Get kill-switch configuration
            config = getattr(self.agent, 'config', None)
            kill_switch_active = False
            loss_threshold = 0.0
            gain_threshold = 0.0
            current_pnl_pct = 0.0

            if config:
                loss_threshold = getattr(config, 'kill_switch_loss_pct', 0.0) or 0.0
                gain_threshold = getattr(config, 'kill_switch_gain_pct', 0.0) or 0.0
                kill_switch_active = loss_threshold > 0 or gain_threshold > 0

                # Calculate current P&L percentage for kill-switch monitoring
                try:
                    portfolio_ctx = self.trade_monitor.monitoring_context_provider.get_monitoring_context()
                    risk_metrics = portfolio_ctx.get('risk_metrics', {})
                    current_pnl_pct = risk_metrics.get('unrealized_pnl_percent', 0.0) or 0.0
                except Exception as e:
                    logger.debug(f"Error getting P&L for kill-switch: {e}")

            # Get max daily trades limit
            max_daily_trades = getattr(config, 'max_daily_trades', 5) if config else 5

            return {
                'state': state_name,
                'cycle_count': cycle_count,
                'daily_trades': daily_trades,
                'max_daily_trades': max_daily_trades,
                'uptime_seconds': uptime_seconds,
                'kill_switch': {
                    'active': kill_switch_active,
                    'loss_threshold': loss_threshold,
                    'gain_threshold': gain_threshold,
                    'current_pnl_pct': current_pnl_pct
                }
            }
        except Exception as e:
            logger.error(f"Error getting agent status: {e}")
            return {
                'state': "ERROR",
                'cycle_count': 0,
                'daily_trades': 0,
                'max_daily_trades': 5,
                'uptime_seconds': 0,
                'kill_switch': {
                    'active': False,
                    'loss_threshold': 0.0,
                    'gain_threshold': 0.0,
                    'current_pnl_pct': 0.0
                }
            }

    def get_portfolio_snapshot(self) -> Dict[str, Any]:
        """
        Get portfolio balance, P&L, exposure, leverage, concentration, risk metrics.

        Returns:
            Dict with portfolio snapshot data
        """
        try:
            context = self.trade_monitor.monitoring_context_provider.get_monitoring_context()
            risk_metrics = context.get('risk_metrics', {})
            position_concentration = context.get('position_concentration', {})

            # Extract balance and P&L
            balance = risk_metrics.get('account_value', 0.0) or 0.0
            unrealized_pnl = risk_metrics.get('unrealized_pnl', 0.0) or 0.0
            unrealized_pnl_pct = risk_metrics.get('unrealized_pnl_percent', 0.0) or 0.0

            # Extract exposure and leverage
            total_exposure = risk_metrics.get('total_exposure_usd', 0.0) or 0.0
            leverage = risk_metrics.get('leverage_estimate', 0.0) or 0.0

            # Extract concentration metrics
            largest_position_pct = position_concentration.get('largest_position_pct', 0.0) or 0.0
            diversification_score = position_concentration.get('diversification_score', 0.0) or 0.0
            num_positions = position_concentration.get('num_positions', 0) or 0

            # Calculate risk check status
            risk_checks = self._evaluate_risk_limits(context)

            return {
                'balance': balance,
                'unrealized_pnl': unrealized_pnl,
                'unrealized_pnl_pct': unrealized_pnl_pct,
                'total_exposure': total_exposure,
                'leverage': leverage,
                'num_positions': num_positions,
                'largest_position_pct': largest_position_pct,
                'diversification_score': diversification_score,
                'risk_checks': risk_checks
            }
        except Exception as e:
            logger.error(f"Error getting portfolio snapshot: {e}")
            return {
                'balance': 0.0,
                'unrealized_pnl': 0.0,
                'unrealized_pnl_pct': 0.0,
                'total_exposure': 0.0,
                'leverage': 0.0,
                'num_positions': 0,
                'largest_position_pct': 0.0,
                'diversification_score': 0.0,
                'risk_checks': {
                    'drawdown': {'status': 'unknown', 'current': 0.0, 'limit': 0.0},
                    'var': {'status': 'unknown', 'current': 0.0, 'limit': 0.0},
                    'concentration': {'status': 'unknown'}
                }
            }

    def _evaluate_risk_limits(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate portfolio against risk limits.

        Args:
            context: Monitoring context from provider

        Returns:
            Dict with risk check results
        """
        try:
            risk_metrics = context.get('risk_metrics', {})

            # Get config for limits
            config = getattr(self.agent, 'config', None)

            # Drawdown check
            drawdown_pct = abs(risk_metrics.get('unrealized_pnl_percent', 0.0) or 0.0)
            drawdown_limit = getattr(config, 'portfolio_stop_loss_percentage', 0.15) if config else 0.15
            drawdown_status = 'ok' if drawdown_pct < drawdown_limit * 0.8 else 'warning' if drawdown_pct < drawdown_limit else 'critical'

            # VaR check (simplified - would need actual VaR calculation)
            # For now, use exposure as proxy
            var_pct = (risk_metrics.get('total_exposure_usd', 0.0) / max(risk_metrics.get('account_value', 1.0), 1.0)) * 100 if risk_metrics.get('account_value', 0.0) > 0 else 0.0
            var_limit = 500  # 500% (5x leverage limit)
            var_status = 'ok' if var_pct < var_limit * 0.8 else 'warning' if var_pct < var_limit else 'critical'

            # Concentration check
            position_concentration = context.get('position_concentration', {})
            largest_pos_pct = position_concentration.get('largest_position_pct', 0.0) or 0.0
            concentration_status = 'ok' if largest_pos_pct < 0.4 else 'warning' if largest_pos_pct < 0.5 else 'critical'

            return {
                'drawdown': {
                    'status': drawdown_status,
                    'current': drawdown_pct,
                    'limit': drawdown_limit
                },
                'var': {
                    'status': var_status,
                    'current': var_pct,
                    'limit': var_limit
                },
                'concentration': {
                    'status': concentration_status,
                    'current': largest_pos_pct,
                    'limit': 0.5
                }
            }
        except Exception as e:
            logger.debug(f"Error evaluating risk limits: {e}")
            return {
                'drawdown': {'status': 'unknown', 'current': 0.0, 'limit': 0.0},
                'var': {'status': 'unknown', 'current': 0.0, 'limit': 0.0},
                'concentration': {'status': 'unknown', 'current': 0.0, 'limit': 0.0}
            }

    def get_active_trades(self) -> List[Dict[str, Any]]:
        """
        Get live trades with real-time P&L, peak, drawdown, duration.

        Returns:
            List of active trade dictionaries
        """
        try:
            trades = []
            active_trackers = getattr(self.trade_monitor, 'active_trackers', {})

            for trade_id, tracker in active_trackers.items():
                try:
                    # Get tracker status
                    status = tracker.get_current_status()

                    # Extract trade info
                    product_id = status.get('product_id', 'UNKNOWN')
                    side = status.get('side', 'UNKNOWN')
                    entry_price = status.get('entry_price', 0.0)
                    current_price = status.get('current_price', 0.0)
                    pnl = status.get('current_pnl', 0.0)
                    peak_pnl = status.get('peak_pnl', 0.0)
                    max_drawdown = status.get('max_drawdown', 0.0)
                    entry_time = status.get('entry_time')

                    # Calculate duration
                    duration_hours = 0.0
                    if entry_time:
                        if isinstance(entry_time, str):
                            entry_dt = datetime.fromisoformat(entry_time.replace('Z', '+00:00'))
                            duration_hours = (datetime.now(entry_dt.tzinfo) - entry_dt).total_seconds() / 3600
                        elif isinstance(entry_time, datetime):
                            duration_hours = (datetime.now(entry_time.tzinfo) - entry_time).total_seconds() / 3600

                    # Calculate P&L percentage
                    pnl_pct = 0.0
                    if entry_price and entry_price > 0:
                        pnl_pct = ((current_price - entry_price) / entry_price) * 100
                        if side == 'SHORT':
                            pnl_pct = -pnl_pct

                    trades.append({
                        'trade_id': trade_id,
                        'asset_pair': product_id,
                        'side': side,
                        'entry_price': entry_price,
                        'current_price': current_price,
                        'pnl': pnl,
                        'pnl_pct': pnl_pct,
                        'peak_pnl': peak_pnl,
                        'max_drawdown': max_drawdown,
                        'duration_hours': duration_hours
                    })
                except Exception as e:
                    logger.debug(f"Error processing trade {trade_id}: {e}")
                    continue

            return trades
        except Exception as e:
            logger.error(f"Error getting active trades: {e}")
            return []

    def get_market_pulse(self) -> List[Dict[str, Any]]:
        """
        Get watchlist assets with pulse data (confluence, trends, signals).

        Returns:
            List of market pulse dictionaries
        """
        try:
            pulse_data = []
            config = getattr(self.agent, 'config', None)
            watchlist = getattr(config, 'watchlist', ['BTCUSD', 'ETHUSD', 'EURUSD']) if config else ['BTCUSD', 'ETHUSD', 'EURUSD']

            for asset in watchlist:
                try:
                    # Get latest market context
                    pulse = self.trade_monitor.get_latest_market_context(asset)
                    if not pulse:
                        continue

                    # Extract price info
                    last_price = pulse.get('last_price', 0.0)
                    change_1m_pct = pulse.get('change_1m', 0.0)

                    # Extract trend alignment
                    trend_alignment = pulse.get('trend_alignment', {})
                    direction = trend_alignment.get('direction', 'UNKNOWN')
                    confluence_strength = trend_alignment.get('confluence_strength', 0.0) or 0.0

                    # Determine signal strength
                    signal_strength = 'WEAK'
                    if confluence_strength >= 80:
                        signal_strength = 'STRONG'
                    elif confluence_strength >= 60:
                        signal_strength = 'MEDIUM'

                    pulse_data.append({
                        'asset': asset,
                        'last_price': last_price,
                        'change_1m_pct': change_1m_pct,
                        'trend': direction,
                        'confluence': confluence_strength,
                        'signal_strength': signal_strength
                    })
                except Exception as e:
                    logger.debug(f"Error getting pulse for {asset}: {e}")
                    continue

            return pulse_data
        except Exception as e:
            logger.error(f"Error getting market pulse: {e}")
            return []

    def get_recent_decisions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent decision log with reasoning, approvals/rejections.

        Args:
            limit: Maximum number of decisions to return

        Returns:
            List of decision dictionaries
        """
        try:
            decisions = []

            # Check if agent has event queue
            if hasattr(self.agent, '_dashboard_event_queue'):
                queue = self.agent._dashboard_event_queue

                # Drain queue into list (non-blocking)
                temp_events = []
                while not queue.empty() and len(temp_events) < limit * 2:
                    try:
                        event = queue.get_nowait()
                        temp_events.append(event)
                    except:
                        break

                # Filter for decision events
                for event in temp_events:
                    if event.get('type') in ['decision_approved', 'decision_rejected']:
                        timestamp = event.get('timestamp', time.time())
                        time_str = datetime.fromtimestamp(timestamp).strftime('%H:%M:%S')

                        decisions.append({
                            'timestamp': time_str,
                            'asset': event.get('asset', 'UNKNOWN'),
                            'action': event.get('action', 'UNKNOWN'),
                            'confidence': event.get('confidence', 0),
                            'status': 'APPROVED' if event['type'] == 'decision_approved' else 'REJECTED',
                            'reasoning': event.get('reasoning', '') if event['type'] == 'decision_approved' else '',
                            'rejection_reason': event.get('reason', '') if event['type'] == 'decision_rejected' else ''
                        })

                        if len(decisions) >= limit:
                            break

            return decisions[:limit]
        except Exception as e:
            logger.error(f"Error getting recent decisions: {e}")
            return []

    def get_performance_stats(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get performance metrics: win rate, total P&L, best/worst, streak.

        Args:
            hours: Lookback period in hours

        Returns:
            Dict with performance statistics
        """
        try:
            # Get context from portfolio memory
            context = self.portfolio_memory.generate_context(max_recent=100)

            # Extract recent performance
            recent_perf = context.get('recent_performance', {})
            trades_count = recent_perf.get('total_trades', 0) or 0
            win_rate = recent_perf.get('win_rate', 0.0) or 0.0
            total_pnl = recent_perf.get('total_pnl', 0.0) or 0.0

            # Calculate average P&L
            avg_pnl = total_pnl / trades_count if trades_count > 0 else 0.0

            # Get best and worst trades (from experience replay)
            best_trade = {'pnl': 0.0, 'asset': 'N/A'}
            worst_trade = {'pnl': 0.0, 'asset': 'N/A'}

            trades = context.get('recent_trades', [])
            if trades:
                sorted_trades = sorted(trades, key=lambda t: t.get('realized_pnl', 0.0) or 0.0)
                if sorted_trades:
                    worst = sorted_trades[0]
                    best = sorted_trades[-1]
                    best_trade = {
                        'pnl': best.get('realized_pnl', 0.0),
                        'asset': best.get('product_id', 'N/A')
                    }
                    worst_trade = {
                        'pnl': worst.get('realized_pnl', 0.0),
                        'asset': worst.get('product_id', 'N/A')
                    }

            # Get current streak
            current_streak = context.get('current_streak', {'type': 'NONE', 'count': 0})
            streak_type = current_streak.get('type', 'NONE')
            streak_count = current_streak.get('count', 0)

            return {
                'trades_count': trades_count,
                'win_rate': win_rate,
                'total_pnl': total_pnl,
                'avg_pnl': avg_pnl,
                'best_trade': best_trade,
                'worst_trade': worst_trade,
                'streak': {
                    'type': streak_type,
                    'count': streak_count
                }
            }
        except Exception as e:
            logger.error(f"Error getting performance stats: {e}")
            return {
                'trades_count': 0,
                'win_rate': 0.0,
                'total_pnl': 0.0,
                'avg_pnl': 0.0,
                'best_trade': {'pnl': 0.0, 'asset': 'N/A'},
                'worst_trade': {'pnl': 0.0, 'asset': 'N/A'},
                'streak': {'type': 'NONE', 'count': 0}
            }
