"""Mock trading platform for backtesting and testing without real APIs."""

from typing import Dict, Any, Optional
import logging
import uuid
import time
from datetime import datetime

from .base_platform import BaseTradingPlatform

logger = logging.getLogger(__name__)


class MockTradingPlatform(BaseTradingPlatform):
    """
    Mock trading platform that simulates real trading behavior.

    Maintains internal state for balances and positions, applies slippage,
    and provides the same interface as real platforms like CoinbasePlatform.

    Ideal for:
    - Backtesting without API calls
    - Agent testing in safe environments
    - Development and debugging
    """

    def __init__(
        self,
        credentials: Optional[Dict[str, Any]] = None,
        initial_balance: Optional[Dict[str, float]] = None,
        slippage_config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize mock platform.

        Args:
            credentials: Optional credentials dict (unused, for compatibility)
            initial_balance: Starting balances, e.g.:
                {'FUTURES_USD': 10000.0, 'SPOT_USD': 5000.0, 'SPOT_USDC': 3000.0}
            slippage_config: Slippage settings:
                - 'type': 'percentage' or 'fixed'
                - 'rate': slippage rate (default 0.001 = 0.1%)
                - 'spread': bid-ask spread (default 0.0005 = 0.05%)
        """
        super().__init__(credentials or {})

        # Initialize balances
        self._balance = initial_balance or {
            'FUTURES_USD': 10000.0,
            'SPOT_USD': 5000.0,
            'SPOT_USDC': 3000.0
        }

        # Initialize positions tracking
        # Format: {asset_pair: {'contracts': float, 'entry_price': float,
        #          'side': 'LONG'/'SHORT', 'unrealized_pnl': float}}
        self._positions = {}

        # Trading history for analytics
        self._trade_history = []

        # Slippage configuration
        self._slippage_config = slippage_config or {
            'type': 'percentage',
            'rate': 0.001,  # 0.1% slippage
            'spread': 0.0005  # 0.05% spread
        }

        # Coinbase futures contract multiplier
        self._contract_multiplier = 0.1

        # Platform metadata
        self._account_id = f"mock-{uuid.uuid4().hex[:8]}"

        logger.info(
            "MockTradingPlatform initialized with balance: %s, "
            "slippage: %.2f%%",
            self._balance,
            self._slippage_config.get('rate', 0) * 100
        )

    def _apply_slippage(self, price: float, action: str) -> float:
        """
        Apply slippage to execution price.

        Args:
            price: Market price
            action: 'BUY' or 'SELL'

        Returns:
            Adjusted execution price
        """
        slippage_type = self._slippage_config.get('type', 'percentage')
        slippage_rate = self._slippage_config.get('rate', 0.001)
        spread = self._slippage_config.get('spread', 0.0005)

        if slippage_type == 'percentage':
            # BUY: pay more (slippage + spread)
            # SELL: receive less (slippage + spread)
            if action == 'BUY':
                adjusted_price = price * (1 + slippage_rate + spread)
            else:
                adjusted_price = price * (1 - slippage_rate - spread)
        else:
            # Fixed slippage
            if action == 'BUY':
                adjusted_price = price + slippage_rate + spread
            else:
                adjusted_price = price - slippage_rate - spread

        return max(adjusted_price, 0.01)  # Prevent negative prices

    def get_balance(self) -> Dict[str, float]:
        """
        Get account balances.

        Returns:
            Dictionary mapping asset symbols to balances:
            - 'FUTURES_USD': total futures account balance
            - 'SPOT_USD': spot USD balance
            - 'SPOT_USDC': spot USDC balance
        """
        logger.debug("MockPlatform.get_balance() called: %s", self._balance)
        return self._balance.copy()

    def execute_trade(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a simulated trade based on a decision.

        Args:
            decision: Trading decision containing:
                - asset_pair: e.g., 'BTCUSD' or 'BTC-USD'
                - action: 'BUY' or 'SELL'
                - suggested_amount: USD notional size
                - entry_price: Current market price (optional)
                - id: Decision ID

        Returns:
            Execution result matching Coinbase format:
            {
                'success': bool,
                'platform': 'mock',
                'decision_id': str,
                'order_id': str,
                'order_status': str,
                'filled_size': float,
                'execution_price': float,
                'total_value': float,
                'slippage_applied': float,
                'latency_seconds': float,
                'timestamp': str
            }
        """
        start_time = time.time()

        # Extract decision parameters
        action = decision.get('action', '').upper()
        asset_pair = decision.get('asset_pair', '')
        suggested_amount = float(decision.get('suggested_amount', 0))
        entry_price = float(decision.get('entry_price', 50000.0))  # Default BTC price
        decision_id = decision.get('id', uuid.uuid4().hex)

        # Normalize asset pair format (BTCUSD -> BTC-USD)
        if '-' not in asset_pair and '/' not in asset_pair:
            # Assume format like BTCUSD, split into BTC-USD
            if len(asset_pair) >= 6:
                asset_pair_normalized = f"{asset_pair[:-3]}-{asset_pair[-3:]}"
            else:
                asset_pair_normalized = asset_pair
        else:
            asset_pair_normalized = asset_pair.replace('/', '-')

        logger.info(
            "MockPlatform executing: %s %s @ $%.2f (amount: $%.2f)",
            action, asset_pair_normalized, entry_price, suggested_amount
        )

        # Validate inputs
        if action not in ['BUY', 'SELL']:
            logger.error("Invalid action: %s", action)
            return {
                'success': False,
                'platform': 'mock',
                'decision_id': decision_id,
                'error': f'Invalid action: {action}',
                'timestamp': decision.get('timestamp', datetime.utcnow().isoformat())
            }

        if suggested_amount <= 0:
            logger.error("Invalid suggested_amount: %.2f", suggested_amount)
            return {
                'success': False,
                'platform': 'mock',
                'decision_id': decision_id,
                'error': f'Invalid suggested_amount: {suggested_amount}',
                'timestamp': decision.get('timestamp', datetime.utcnow().isoformat())
            }

        # Apply slippage to execution price
        execution_price = self._apply_slippage(entry_price, action)
        slippage_pct = abs((execution_price - entry_price) / entry_price) * 100

        # Calculate position size (contracts for futures)
        contracts = suggested_amount / (execution_price * self._contract_multiplier)

        # Calculate fees (0.06% maker/taker average for Coinbase)
        fee_rate = 0.0006
        fee_amount = suggested_amount * fee_rate

        # Update balances and positions
        try:
            if action == 'BUY':
                # Check sufficient balance
                futures_balance = self._balance.get('FUTURES_USD', 0)
                required_amount = suggested_amount + fee_amount

                if futures_balance < required_amount:
                    logger.warning(
                        "Insufficient balance: %.2f < %.2f required",
                        futures_balance, required_amount
                    )
                    return {
                        'success': False,
                        'platform': 'mock',
                        'decision_id': decision_id,
                        'error': f'Insufficient balance: {futures_balance:.2f} < {required_amount:.2f}',
                        'timestamp': decision.get('timestamp', datetime.utcnow().isoformat())
                    }

                # Deduct from balance
                self._balance['FUTURES_USD'] -= required_amount

                # Update or create position
                if asset_pair_normalized in self._positions:
                    pos = self._positions[asset_pair_normalized]
                    # Average entry price for multiple buys
                    total_contracts = pos['contracts'] + contracts
                    weighted_entry = (
                        (pos['contracts'] * pos['entry_price']) +
                        (contracts * execution_price)
                    ) / total_contracts
                    pos['contracts'] = total_contracts
                    pos['entry_price'] = weighted_entry
                else:
                    self._positions[asset_pair_normalized] = {
                        'contracts': contracts,
                        'entry_price': execution_price,
                        'side': 'LONG',
                        'unrealized_pnl': 0.0,
                        'daily_pnl': 0.0
                    }

            realized_pnl = 0.0
            if action == 'SELL':
                if asset_pair_normalized in self._positions:
                    pos = self._positions[asset_pair_normalized]

                    # Close or reduce long position
                    if pos['contracts'] >= contracts:
                        # Calculate realized P&L
                        pnl = (execution_price - pos['entry_price']) * contracts * self._contract_multiplier
                        self._balance['FUTURES_USD'] += (suggested_amount - fee_amount)

                        # Update position
                        pos['contracts'] -= contracts
                        if pos['contracts'] < 0.01:  # Close position if nearly zero
                            del self._positions[asset_pair_normalized]

                        logger.info("Closed/reduced position, realized P&L: $%.2f", pnl)
                    else:
                        # Not enough contracts to sell
                        logger.warning(
                            "Insufficient position: %.4f contracts < %.4f required",
                            pos['contracts'], contracts
                        )
                        return {
                            'success': False,
                            'platform': 'mock',
                            'decision_id': decision_id,
                            'error': f'Insufficient position: {pos["contracts"]:.4f} < {contracts:.4f}',
                            'timestamp': decision.get('timestamp', datetime.utcnow().isoformat())
                        }
                else:
                    # No position to sell
                    logger.warning("No position to sell for %s", asset_pair_normalized)
                    return {
                        'success': False,
                        'platform': 'mock',
                        'decision_id': decision_id,
                        'error': f'No position to sell for {asset_pair_normalized}',
                        'timestamp': decision.get('timestamp', datetime.utcnow().isoformat())
                    }
            # Record trade in history
            trade_record = {
                'order_id': f"mock-{uuid.uuid4().hex[:8]}",
                'decision_id': decision_id,
                'timestamp': decision.get('timestamp', datetime.utcnow().isoformat()),
                'asset_pair': asset_pair_normalized,
                'action': action,
                'contracts': contracts,
                'execution_price': execution_price,
                'notional_value': suggested_amount,
                'fee_amount': fee_amount,
                'slippage_pct': slippage_pct,
                'realized_pnl': realized_pnl
            }
            self._trade_history.append(trade_record)

            latency = time.time() - start_time

            logger.info(
                "Trade executed successfully: %s %.4f contracts @ $%.2f (slippage: %.3f%%)",
                action, contracts, execution_price, slippage_pct
            )

            return {
                'success': True,
                'platform': 'mock',
                'decision_id': decision_id,
                'order_id': trade_record['order_id'],
                'order_status': 'FILLED',
                'filled_size': contracts,
                'execution_price': execution_price,
                'total_value': suggested_amount,
                'fee_amount': fee_amount,
                'slippage_applied': slippage_pct,
                'latency_seconds': latency,
                'response': trade_record,
                'timestamp': trade_record['timestamp']
            }

        except Exception as e:
            logger.exception("Error executing mock trade")
            return {
                'success': False,
                'platform': 'mock',
                'decision_id': decision_id,
                'error': str(e),
                'latency_seconds': time.time() - start_time,
                'timestamp': decision.get('timestamp', datetime.utcnow().isoformat())
            }

    def get_portfolio_breakdown(self) -> Dict[str, Any]:
        """
        Get detailed portfolio breakdown matching Coinbase format.

        Returns:
            Dictionary with:
            - futures_positions: List of active positions
            - futures_summary: Account summary (balance, PnL, margin, power)
            - holdings: Spot USD/USDC holdings
            - total_value_usd: Combined futures + spot value
            - futures_value_usd: Futures account value
            - spot_value_usd: Spot USD/USDC value
            - num_assets: Number of holdings
            - unrealized_pnl: Total unrealized P&L
            - platform: 'mock'
        """
        futures_balance = self._balance.get('FUTURES_USD', 0)
        spot_usd = self._balance.get('SPOT_USD', 0)
        spot_usdc = self._balance.get('SPOT_USDC', 0)
        spot_value = spot_usd + spot_usdc

        # Build futures positions
        futures_positions = []
        total_unrealized_pnl = 0.0
        total_notional = 0.0

        for asset_pair, pos in self._positions.items():
            # Use current_price from position if available (set by update_position_prices),
            # otherwise assume +1% gain for mock
            if 'current_price' in pos:
                current_price = pos['current_price']
            else:
                current_price = pos['entry_price'] * 1.01

            contracts = pos['contracts']
            notional = contracts * current_price * self._contract_multiplier
            unrealized_pnl = (current_price - pos['entry_price']) * contracts * self._contract_multiplier

            total_unrealized_pnl += unrealized_pnl
            total_notional += notional

            futures_positions.append({
                'product_id': asset_pair,
                'side': pos.get('side', 'LONG'),
                'contracts': contracts,
                'entry_price': pos['entry_price'],
                'current_price': current_price,
                'unrealized_pnl': unrealized_pnl,
                'daily_pnl': pos.get('daily_pnl', 0.0),
                'leverage': 10.0  # Mock default leverage
            })

        # Build holdings list
        holdings = []

        if spot_usd > 0:
            holdings.append({
                'asset': 'USD',
                'amount': spot_usd,
                'value_usd': spot_usd,
                'allocation_pct': 0.0
            })

        if spot_usdc > 0:
            holdings.append({
                'asset': 'USDC',
                'amount': spot_usdc,
                'value_usd': spot_usdc,
                'allocation_pct': 0.0
            })

        # Add futures positions to holdings
        for pos in futures_positions:
            holdings.append({
                'asset': pos['product_id'],
                'amount': pos['contracts'],
                'value_usd': pos['contracts'] * pos['current_price'] * self._contract_multiplier,
                'allocation_pct': 0.0
            })

        # Calculate allocations
        total_value = futures_balance + spot_value + total_unrealized_pnl
        allocation_base = total_notional + spot_value

        if allocation_base > 0:
            for holding in holdings:
                holding['allocation_pct'] = (holding['value_usd'] / allocation_base) * 100

        # Futures summary
        buying_power = futures_balance * 2  # Mock 2x buying power
        initial_margin = total_notional / 10  # Mock 10x leverage

        futures_summary = {
            'total_balance_usd': futures_balance,
            'unrealized_pnl': total_unrealized_pnl,
            'daily_realized_pnl': 0.0,  # Mock
            'buying_power': buying_power,
            'initial_margin': initial_margin
        }

        logger.debug(
            "Portfolio breakdown: total_value=$%.2f, "
            "futures=$%.2f, spot=$%.2f, positions=%d",
            total_value, futures_balance, spot_value, len(futures_positions)
        )

        return {
            'futures_positions': futures_positions,
            'futures_summary': futures_summary,
            'holdings': holdings,
            'total_value_usd': total_value,
            'futures_value_usd': futures_balance,
            'spot_value_usd': spot_value,
            'num_assets': len(holdings),
            'unrealized_pnl': total_unrealized_pnl,
            'platform': 'mock'
        }

    def get_account_info(self) -> Dict[str, Any]:
        """
        Get account information matching Coinbase format.

        Returns:
            Account details with portfolio metrics
        """
        portfolio = self.get_portfolio_breakdown()

        return {
            'platform': 'mock',
            'account_type': 'trading',
            'account_id': self._account_id,
            'status': 'active',
            'mode': 'mock',
            'execution_enabled': True,
            'max_leverage': 10.0,
            'balances': self.get_balance(),
            'portfolio': portfolio
        }

    def reset(self, initial_balance: Optional[Dict[str, float]] = None):
        """
        Reset platform state (useful for backtesting runs).

        Args:
            initial_balance: New starting balance (optional)
        """
        if initial_balance:
            self._balance = initial_balance.copy()
        else:
            self._balance = {
                'FUTURES_USD': 10000.0,
                'SPOT_USD': 5000.0,
                'SPOT_USDC': 3000.0
            }

        self._positions.clear()
        self._trade_history.clear()

        logger.info("MockPlatform reset with balance: %s", self._balance)

    def get_trade_history(self) -> list:
        """
        Get all executed trades.

        Returns:
            List of trade records
        """
        return self._trade_history.copy()

    def get_positions(self) -> Dict[str, Any]:
        """
        Get current positions.

        Returns:
            Dictionary of positions by asset pair
        """
        return self._positions.copy()

    def get_active_positions(self) -> Dict[str, Any]:
        """
        Get all currently active positions.

        Returns:
            A dictionary with a single key "positions" whose value is a
            list of PositionInfo objects, e.g., {"positions": [...]}.
        """
        positions = []

        for asset_pair, pos in self._positions.items():
            # Use current_price from position if available, otherwise use entry_price
            current_price = pos.get('current_price', pos['entry_price'])

            # Calculate P&L
            pnl = (current_price - pos['entry_price']) * pos['contracts'] * self._contract_multiplier

            positions.append({
                'id': f"mock-{asset_pair}",
                'instrument': asset_pair,
                'units': pos['contracts'],
                'entry_price': pos['entry_price'],
                'current_price': current_price,
                'pnl': pnl,
                'opened_at': None,  # Mock doesn't track this
                'platform': 'mock',
                'leverage': 10.0,
                'position_type': pos.get('side', 'LONG')
            })

        return {'positions': positions}

    def update_position_prices(self, price_updates: Dict[str, float]):
        """
        Update current prices for positions (useful for backtesting).

        Args:
            price_updates: Dict mapping asset_pair -> current_price
        """
        for asset_pair, current_price in price_updates.items():
            if asset_pair in self._positions:
                pos = self._positions[asset_pair]
                # Store current price in position
                pos['current_price'] = current_price
                # Update unrealized P&L
                pos['unrealized_pnl'] = (
                    (current_price - pos['entry_price']) *
                    pos['contracts'] *
                    self._contract_multiplier
                )
                logger.debug(
                    "Updated %s price to $%.2f, unrealized P&L: $%.2f",
                    asset_pair, current_price, pos['unrealized_pnl']
                )
