"""Oanda trading platform integration."""

from typing import Dict, Any
import logging

from .base_platform import BaseTradingPlatform

logger = logging.getLogger(__name__)


class OandaPlatform(BaseTradingPlatform):
    """
    Oanda trading platform integration for forex trading.
    
    Provides real-time access to:
    - Forex account balance and currency holdings
    - Open positions (long/short)
    - Unrealized/realized PnL
    - Margin and leverage information
    - Trade execution capabilities
    """

    def __init__(self, credentials: Dict[str, Any]):
        """
        Initialize Oanda platform.

        Args:
            credentials: Dictionary containing:
                - access_token: Oanda API access token (or api_key)
                - account_id: Oanda account ID
                - environment: 'practice' or 'live'
                - base_url: Optional custom base URL
        """
        super().__init__(credentials)
        # Support both 'access_token' and 'api_key' for flexibility
        self.api_key = (
            credentials.get('access_token') or credentials.get('api_key')
        )
        self.account_id = credentials.get('account_id')
        self.environment = credentials.get('environment', 'practice')
        
        # Set base URL based on environment
        if credentials.get('base_url'):
            self.base_url = credentials['base_url']
        else:
            self.base_url = (
                "https://api-fxpractice.oanda.com"
                if self.environment == 'practice'
                else "https://api-fxtrade.oanda.com"
            )
        
        # Initialize Oanda client (lazy loading)
        self._client = None
        
        logger.info(
            "Oanda platform initialized (%s environment, base_url=%s)",
            self.environment,
            self.base_url
        )

    def _get_client(self):
        """
        Lazy initialization of Oanda client.

        Returns:
            oandapyV20 API context instance
        """
        if self._client is None:
            try:
                from oandapyV20 import API
                
                # Initialize client with API token and environment
                self._client = API(
                    access_token=self.api_key,
                    environment=self.environment
                )
                logger.info("Oanda API client initialized")
            except ImportError:
                logger.warning(
                    "oandapyV20 not installed. "
                    "Install with: pip install oandapyV20"
                )
                raise ValueError(
                    "Oanda library not available. "
                    "Install oandapyV20"
                )
            except Exception as e:
                logger.error("Failed to initialize Oanda client: %s", e)
                raise
        
        return self._client

    def get_balance(self) -> Dict[str, float]:
        """
        Get account balances from Oanda.
        
        Returns balances for base currency and unrealized positions.

        Returns:
            Dictionary of currency balances (e.g., {'USD': 50000.0})
        """
        logger.info("Fetching Oanda balances")
        
        try:
            from oandapyV20.endpoints.accounts import AccountSummary
            
            client = self._get_client()
            balances = {}
            
            # Get account summary for balance
            request = AccountSummary(accountID=self.account_id)
            response = client.request(request)
            
            if 'account' in response:
                account = response['account']
                
                # Get base currency balance
                currency = account.get('currency', 'USD')
                balance = float(account.get('balance', 0))
                
                if balance > 0:
                    balances[currency] = balance
                    logger.info(
                        "Oanda balance: %.2f %s",
                        balance,
                        currency
                    )
            
            return balances
            
        except ImportError:
            logger.error(
                "Oanda library not installed. "
                "Install with: pip install oandapyV20"
            )
            raise ValueError(
                "Oanda library required for real data. "
                "Please install oandapyV20"
            )
        except Exception as e:
            logger.error("Error fetching Oanda balances: %s", e)
            # Return empty dict on error to allow graceful degradation
            return {}

    def get_portfolio_breakdown(self) -> Dict[str, Any]:
        """
        Get forex trading account breakdown.
        
        Provides detailed view of:
        - Open positions (long/short)
        - Unrealized PnL
        - Margin usage
        - Currency exposure

        Returns:
            Dictionary with forex portfolio metrics:
            - total_value_usd: Total account value in USD
            - num_assets: Number of currency pairs with positions
            - base_currency: Account base currency
            - balance: Account balance
            - unrealized_pl: Unrealized profit/loss
            - margin_used: Margin currently used
            - margin_available: Available margin
            - positions: List of open positions
            - holdings: List of currency exposures
        """
        logger.info("Fetching Oanda forex portfolio breakdown")
        
        try:
            from oandapyV20.endpoints.accounts import AccountDetails
            from oandapyV20.endpoints.positions import OpenPositions
            
            client = self._get_client()
            
            # Get account details
            account_request = AccountDetails(accountID=self.account_id)
            account_response = client.request(account_request)
            account = account_response.get('account', {})
            
            # Get open positions
            positions_request = OpenPositions(accountID=self.account_id)
            positions_response = client.request(positions_request)
            positions_data = positions_response.get('positions', [])
            
            # Parse account info
            base_currency = account.get('currency', 'USD')
            balance = float(account.get('balance', 0))
            unrealized_pl = float(account.get('unrealizedPL', 0))
            margin_used = float(account.get('marginUsed', 0))
            margin_available = float(account.get('marginAvailable', 0))
            nav = float(account.get('NAV', balance))
            
            # Parse positions
            positions = []
            holdings_map = {}  # Track net exposure per currency
            
            for pos in positions_data:
                instrument = pos.get('instrument', 'UNKNOWN')
                
                # Parse long position
                long_pos = pos.get('long', {})
                long_units = float(long_pos.get('units', 0))
                long_pl = float(long_pos.get('unrealizedPL', 0))
                
                # Parse short position
                short_pos = pos.get('short', {})
                short_units = float(short_pos.get('units', 0))
                short_pl = float(short_pos.get('unrealizedPL', 0))
                
                # Net position
                net_units = long_units + short_units
                net_pl = long_pl + short_pl
                
                if net_units != 0:
                    position_type = 'LONG' if net_units > 0 else 'SHORT'
                    
                    positions.append({
                        'instrument': instrument,
                        'position_type': position_type,
                        'units': abs(net_units),
                        'unrealized_pl': net_pl,
                        'long_units': long_units,
                        'short_units': abs(short_units),
                        'long_pl': long_pl,
                        'short_pl': short_pl
                    })
                    
                    # Track currency exposure (simplified)
                    # Extract base and quote currencies
                    if '_' in instrument:
                        base, quote = instrument.split('_')
                        
                        # Add to holdings map
                        if base not in holdings_map:
                            holdings_map[base] = 0
                        holdings_map[base] += net_units
            
            # Convert holdings map to list
            holdings = []
            total_exposure_usd = 0
            
            for currency, amount in holdings_map.items():
                # Estimate USD value (simplified - would need exchange rates)
                # For now, use absolute value as proxy
                usd_value = abs(amount)
                total_exposure_usd += usd_value
                
                holdings.append({
                    'asset': currency,
                    'amount': amount,
                    'value_usd': usd_value,
                    'allocation_pct': 0  # Will calculate after total known
                })
            
            # Calculate allocation percentages
            if total_exposure_usd > 0:
                for holding in holdings:
                    holding['allocation_pct'] = (
                        holding['value_usd'] / total_exposure_usd * 100
                    )
            
            # Build portfolio summary
            portfolio = {
                'total_value_usd': nav,
                'num_assets': len(holdings),
                'base_currency': base_currency,
                'balance': balance,
                'unrealized_pl': unrealized_pl,
                # Alias to keep naming consistent with other platforms/unified view.
                'unrealized_pnl': unrealized_pl,
                'margin_used': margin_used,
                'margin_available': margin_available,
                'nav': nav,
                'positions': positions,
                'holdings': holdings,
                'platform': 'oanda',
                'account_id': self.account_id,
                'environment': self.environment
            }
            
            logger.info(
                "Oanda portfolio: %.2f %s NAV, %d positions, %d currencies",
                nav,
                base_currency,
                len(positions),
                len(holdings)
            )
            
            return portfolio
            
        except ImportError:
            logger.error(
                "Oanda library not installed. "
                "Install with: pip install oandapyV20"
            )
            raise ValueError(
                "Oanda library required. Please install oandapyV20"
            )
        except Exception as e:
            logger.error("Error fetching Oanda portfolio: %s", e)
            # Return minimal portfolio on error
            return {
                'total_value_usd': 0,
                'num_assets': 0,
                'positions': [],
                'holdings': [],
                'error': str(e)
            }

    def execute_trade(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a forex trade on Oanda.

        Args:
            decision: Trading decision containing:
                - asset_pair: Currency pair (e.g., 'EUR_USD')
                - action: BUY, SELL, or HOLD
                - recommended_position_size: Position size in units
                - stop_loss_percentage: Stop loss percentage

        Returns:
            Execution result with order details
        """
        logger.info(f"Executing trade on Oanda: {decision}")
        
        action = decision.get('action', 'HOLD')
        
        if action == 'HOLD':
            return {
                'success': True,
                'platform': 'oanda',
                'decision_id': decision.get('id'),
                'environment': self.environment,
                'message': 'HOLD - no trade executed',
                'timestamp': decision.get('timestamp')
            }
        
        try:
            from oandapyV20.endpoints.orders import OrderCreate
            
            client = self._get_client()
            
            # Parse decision parameters
            asset_pair = decision.get('asset_pair', '')
            # Convert to Oanda format (e.g., EURUSD -> EUR_USD)
            if '_' not in asset_pair and len(asset_pair) == 6:
                instrument = f"{asset_pair[:3]}_{asset_pair[3:]}"
            else:
                instrument = asset_pair
            
            units = decision.get('recommended_position_size', 1000)
            entry_price = decision.get('entry_price', 0)
            stop_loss_pct = decision.get('stop_loss_percentage', 2.0)
            
            # Determine order direction
            if action == 'BUY':
                order_units = abs(units)
            elif action == 'SELL':
                order_units = -abs(units)
            else:
                return {
                    'success': False,
                    'platform': 'oanda',
                    'error': f"Unknown action: {action}"
                }
            
            # Calculate stop loss price
            stop_loss_price = None
            if entry_price > 0:
                if action == 'BUY':
                    stop_loss_price = entry_price * (1 - stop_loss_pct / 100)
                else:
                    stop_loss_price = entry_price * (1 + stop_loss_pct / 100)
            
            # Build order data
            order_data = {
                "order": {
                    "type": "MARKET",
                    "instrument": instrument,
                    "units": str(int(order_units)),
                    "timeInForce": "FOK",  # Fill or Kill
                    "positionFill": "DEFAULT"
                }
            }
            
            # Add stop loss if calculated
            if stop_loss_price:
                order_data["order"]["stopLossOnFill"] = {
                    "price": f"{stop_loss_price:.5f}"
                }
            
            # Execute order
            order_request = OrderCreate(
                accountID=self.account_id,
                data=order_data
            )
            response = client.request(order_request)
            
            # Parse response
            order_fill = response.get('orderFillTransaction', {})
            order_create = response.get('orderCreateTransaction', {})
            
            return {
                'success': True,
                'platform': 'oanda',
                'decision_id': decision.get('id'),
                'environment': self.environment,
                'instrument': instrument,
                'units': order_units,
                'order_id': order_fill.get('id', order_create.get('id')),
                'price': float(order_fill.get('price', 0)),
                'pl': float(order_fill.get('pl', 0)),
                'timestamp': decision.get('timestamp'),
                'message': 'Trade executed successfully',
                'response': response
            }
            
        except ImportError:
            logger.error(
                "Oanda library not installed. "
                "Install with: pip install oandapyV20"
            )
            return {
                'success': False,
                'platform': 'oanda',
                'error': 'Oanda library not installed'
            }
        except Exception as e:
            logger.error("Error executing Oanda trade: %s", e)
            return {
                'success': False,
                'platform': 'oanda',
                'decision_id': decision.get('id'),
                'error': str(e),
                'timestamp': decision.get('timestamp')
            }

    def get_account_info(self) -> Dict[str, Any]:
        """
        Get Oanda account information.

        Returns:
            Account details including balance, margin, and status
        """
        logger.info("Fetching Oanda account info")
        
        try:
            from oandapyV20.endpoints.accounts import AccountDetails
            
            client = self._get_client()
            
            # Get account details
            request = AccountDetails(accountID=self.account_id)
            response = client.request(request)
            
            account = response.get('account', {})
            
            return {
                'platform': 'oanda',
                'account_id': self.account_id,
                'environment': self.environment,
                'account_type': 'forex',
                'currency': account.get('currency', 'USD'),
                'balance': float(account.get('balance', 0)),
                'nav': float(account.get('NAV', 0)),
                'unrealized_pl': float(account.get('unrealizedPL', 0)),
                'margin_used': float(account.get('marginUsed', 0)),
                'margin_available': float(account.get('marginAvailable', 0)),
                'margin_rate': float(account.get('marginRate', 0)),
                'open_trade_count': int(account.get('openTradeCount', 0)),
                'open_position_count': int(account.get('openPositionCount', 0)),
                'status': 'active',
                'balances': self.get_balance()
            }
            
        except ImportError:
            logger.error(
                "Oanda library not installed. "
                "Install with: pip install oandapyV20"
            )
            # Return mock data as fallback
            return {
                'platform': 'oanda',
                'account_id': self.account_id,
                'environment': self.environment,
                'account_type': 'forex',
                'status': 'library_not_installed',
                'error': 'Install oandapyV20 for real data',
                'balances': {}
            }
        except Exception as e:
            logger.error("Error fetching Oanda account info: %s", e)
            return {
                'platform': 'oanda',
                'account_id': self.account_id,
                'environment': self.environment,
                'error': str(e)
            }
