"""Coinbase Advanced trading platform integration."""

from typing import Dict, Any
import logging

from .base_platform import BaseTradingPlatform

logger = logging.getLogger(__name__)

# Minimum balance threshold to filter dust (very small amounts)
DUST_THRESHOLD_USD = 0.01  # $0.01


class CoinbaseAdvancedPlatform(BaseTradingPlatform):
    """
    Coinbase Advanced trading platform integration.
    
    **STRATEGY FOCUS**: Perpetual futures long/short trading only.
    No spot holdings or position accumulation - pure futures trading.
    
    Provides real-time access to:
    - Futures account balance and margin
    - Active long/short positions
    - Unrealized/realized PnL
    - Buying power and margin requirements
    """

    def __init__(self, credentials: Dict[str, Any]):
        """
        Initialize Coinbase Advanced platform.

        Args:
            credentials: Dictionary containing:
                - api_key: Coinbase API key
                - api_secret: Coinbase API secret
                - passphrase: Optional passphrase (for legacy API)
                - use_sandbox: Optional bool for sandbox environment
        """
        super().__init__(credentials)
        self.api_key = credentials.get('api_key')
        self.api_secret = credentials.get('api_secret')
        self.passphrase = credentials.get('passphrase')
        self.use_sandbox = credentials.get('use_sandbox', False)
        
        # Initialize Coinbase client (lazy loading)
        self._client = None
        
        logger.info(
            "Coinbase Advanced platform initialized "
            "(sandbox=%s)", self.use_sandbox
        )

    def _get_client(self):
        """
        Lazy initialization of Coinbase client.

        Returns:
            Coinbase REST client instance
        """
        if self._client is None:
            try:
                from coinbase.rest import RESTClient
                
                # Initialize client with API credentials
                # Note: coinbase-advanced-py handles base_url internally
                self._client = RESTClient(
                    api_key=self.api_key,
                    api_secret=self.api_secret
                )
                logger.info("Coinbase REST client initialized")
            except ImportError:
                logger.warning(
                    "coinbase-advanced-py not installed. "
                    "Install with: pip install coinbase-advanced-py"
                )
                raise ValueError(
                    "Coinbase Advanced library not available. "
                    "Install coinbase-advanced-py"
                )
            except Exception as e:
                logger.error("Failed to initialize Coinbase client: %s", e)
                raise
        
        return self._client

    def get_balance(self) -> Dict[str, float]:
        """
        Get futures account balance.
        
        Returns futures trading account balance only.
        Strategy focus: perpetual futures long/short, no spot holdings.

        Returns:
            Dictionary with 'FUTURES_USD': total futures account balance
        """
        logger.info("Fetching futures account balance")
        
        try:
            client = self._get_client()
            balances = {}
            
            # Get futures balance summary
            try:
                futures_summary = client.get_futures_balance_summary()
                balance_summary = getattr(
                    futures_summary, 'balance_summary', None
                )
                
                if balance_summary:
                    # balance_summary supports dict-style access
                    total_usd_balance = balance_summary['total_usd_balance']
                    futures_usd = float(total_usd_balance.get('value', 0))
                    
                    if futures_usd > 0:
                        balances['FUTURES_USD'] = futures_usd
                        logger.info("Futures balance: $%.2f USD", futures_usd)
                    
            except Exception as e:
                logger.warning("Could not fetch futures balance: %s", e)
            
            return balances
            
        except ImportError:
            logger.error(
                "Coinbase library not installed. "
                "Install with: pip install coinbase-advanced-py"
            )
            raise ValueError(
                "Coinbase Advanced library required for real data. "
                "Please install coinbase-advanced-py"
            )
        except Exception as e:
            logger.error("Error fetching Coinbase balances: %s", e)
            raise

    def get_portfolio_breakdown(self) -> Dict[str, Any]:
        """
        Get futures trading account breakdown.
        
        Focus: Perpetual futures long/short positions only.
        No spot holdings - this is a pure futures trading strategy.

        Returns:
            Dictionary with futures trading metrics:
            - futures_positions: List of active long/short positions
            - futures_summary: Account summary (balance, PnL, margin, buying power)
            - total_value_usd: Total futures account value
        """
        logger.info("Fetching futures trading account breakdown")
        
        try:
            client = self._get_client()
            
            # Get futures balance and summary
            futures_positions = []
            futures_summary = {}
            futures_value = 0.0
            
            try:
                futures_response = client.get_futures_balance_summary()
                balance_summary = getattr(
                    futures_response, 'balance_summary', None
                )
                
                if balance_summary:
                    # balance_summary supports dict-style access
                    total_usd_balance = balance_summary['total_usd_balance']
                    unrealized_pnl = balance_summary['unrealized_pnl']
                    daily_pnl = balance_summary['daily_realized_pnl']
                    buying_power = balance_summary['futures_buying_power']
                    initial_margin = balance_summary['initial_margin']
                    
                    futures_value = float(total_usd_balance.get('value', 0))
                    
                    futures_summary = {
                        'total_balance_usd': futures_value,
                        'unrealized_pnl': float(unrealized_pnl.get('value', 0)),
                        'daily_realized_pnl': float(daily_pnl.get('value', 0)),
                        'buying_power': float(buying_power.get('value', 0)),
                        'initial_margin': float(initial_margin.get('value', 0))
                    }
                    
                    logger.info("Futures account balance: $%.2f", futures_value)
                
                # Get individual futures positions (long/short)
                positions_response = client.list_futures_positions()
                positions_list = getattr(
                    positions_response, 'positions', []
                )
                
                for pos in positions_list:
                    # pos supports dict-style access
                    futures_positions.append({
                        'product_id': pos['product_id'],
                        'side': pos['side'],  # LONG or SHORT
                        'contracts': float(pos['number_of_contracts']),
                        'entry_price': float(pos['avg_entry_price']),
                        'current_price': float(pos['current_price']),
                        'unrealized_pnl': float(pos['unrealized_pnl']),
                        'daily_pnl': float(pos['daily_realized_pnl'])
                    })
                    
                logger.info(
                    "Retrieved %d active futures positions (long/short)",
                    len(futures_positions)
                )
                
            except Exception as e:
                logger.error("Error fetching futures data: %s", e)
                raise
            
            return {
                'futures_positions': futures_positions,
                'futures_summary': futures_summary,
                'total_value_usd': futures_value,
                'futures_value_usd': futures_value,
                'spot_value_usd': 0.0,  # Not used - futures only
                'holdings': [],  # Not used - futures only
                'num_assets': 0  # Not used - futures only
            }
            
        except Exception as e:
            logger.error("Error fetching portfolio breakdown: %s", e)
            raise

    def execute_trade(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a trade on Coinbase.

        Args:
            decision: Trading decision

        Returns:
            Execution result
        """
        logger.info(
            "Trade execution requested: %s", decision.get('action')
        )
        
        # Execution not implemented yet - signals only mode
        return {
            'success': False,
            'platform': 'coinbase_advanced',
            'decision_id': decision.get('id'),
            'message': (
                'Signal-only mode: Trade execution not enabled. '
                'Portfolio tracking active for learning.'
            ),
            'timestamp': decision.get('timestamp')
        }

    def get_account_info(self) -> Dict[str, Any]:
        """
        Get Coinbase account information including portfolio breakdown.

        Returns:
            Account details with portfolio metrics
        """
        logger.info("Fetching Coinbase account info")
        
        try:
            portfolio = self.get_portfolio_breakdown()
            
            return {
                'platform': 'coinbase_advanced',
                'account_type': 'trading',
                'status': 'active',
                'mode': 'signal_only',
                'execution_enabled': False,
                'balances': self.get_balance(),
                'portfolio': portfolio
            }
        except Exception as e:
            logger.error("Error fetching account info: %s", e)
            return {
                'platform': 'coinbase_advanced',
                'account_type': 'unknown',
                'status': 'error',
                'error': str(e)
            }
