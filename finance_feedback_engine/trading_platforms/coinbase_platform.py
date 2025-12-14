"""Coinbase Advanced trading platform integration."""

from typing import Any, Dict, List, Optional
import logging
import uuid
import time
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type
from requests.exceptions import RequestException

from .base_platform import BaseTradingPlatform, PositionInfo, PositionsResponse

logger = logging.getLogger(__name__)


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

    def _format_product_id(self, asset_pair: str) -> str:
        """
        Normalize various asset pair formats to Coinbase's product ID style.

        Accepts formats like:
        - "BTCUSD"
        - "BTC-USD"
        - "BTC/USD"

        Returns:
        - "BTC-USD" (Coinbase Advanced expected format)
        """
        try:
            if not asset_pair:
                logger.warning("Empty asset_pair provided to _format_product_id")
                raise ValueError("asset_pair cannot be empty")

            # Remove whitespace and standardize separators
            s = str(asset_pair).strip().upper()
            s = s.replace('/', '-')

            # If already contains '-', ensure single hyphen separator
            if '-' in s:
                parts = [p for p in s.split('-') if p]
                if len(parts) == 2:
                    return f"{parts[0]}-{parts[1]}"
                # Fallback: join first two segments
                if len(parts) > 2:
                    return f"{parts[0]}-{parts[1]}"
                return s # If we got here with a hyphen but can't parse, return as is

            # No separator case like BTCUSD or ETHUSDC
            # Split by known quote currency suffixes
            # Order by length (longest first) to prefer longer matches
            known_quotes = (
                'USDT', 'USDC', 'USD',
                'EUR', 'GBP', 'JPY', 'AUD', 'CAD',
                'BTC', 'ETH',
            )
            for quote in known_quotes:
                if s.endswith(quote) and len(s) > len(quote):
                    base = s[:-len(quote)]
                    if base:
                        return f"{base}-{quote}"

            # If unable to parse, return original normalized string
            return s
        except ValueError:
            # Let validation errors (like empty input) propagate to caller
            raise
        except Exception as e:
            # Be resilient: return the input unchanged on unexpected parsing errors
            # but let validation errors (empty input) propagate
            logger.error("Unexpected error formatting product_id: %s", e)
            return asset_pair

    def get_balance(self) -> Dict[str, float]:
        """
        Get account balances including futures and spot USD/USDC.

        Returns futures trading account balance and spot USD/USDC balances.

        Returns:
            Dictionary with:
            - 'FUTURES_USD': total futures account balance
            - 'SPOT_USD': spot USD balance (if any)
            - 'SPOT_USDC': spot USDC balance (if any)
        """
        logger.info("Fetching account balances (futures + spot USD/USDC)")

        # Assumption: The 'available_balance' from client.get_accounts() for spot USD/USDC
        # does not include staked amounts. Staked assets are typically not considered
        # 'available' for trading and thus are implicitly excluded from this calculation
        # for funds usable in futures trading. If staked assets were included in 'available_balance',
        # additional API calls or specific fields would be needed to differentiate them.

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

            # Get spot balances for USD and USDC
            try:
                accounts_response = client.get_accounts()
                accounts_list = getattr(accounts_response, 'accounts', [])

                for account in accounts_list:
                    # Use attribute access for Coinbase Account objects
                    currency = getattr(account, 'currency', '')
                    if currency in ['USD', 'USDC']:
                        account_id = getattr(account, 'id', '')
                        truncated_id = account_id[-4:] if account_id else 'N/A'
                        available_balance = getattr(account, 'available_balance', None)
                        available_balance_value = getattr(available_balance, 'value', 'N/A') if available_balance else 'N/A'
                        logger.debug("Inspecting spot account for %s: id=...%s, available_balance=%s", currency, truncated_id, available_balance_value)
                        if available_balance:
                            balance_value = float(
                                getattr(available_balance, 'value', 0)
                            )

                            if balance_value > 0:
                                balances[f'SPOT_{currency}'] = balance_value
                                logger.info(
                                    "Spot %s balance: $%.2f",
                                    currency, balance_value
                                )
            except Exception as e:
                logger.warning("Could not fetch spot balances: %s", e)

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
        Get complete account breakdown including futures and spot USD/USDC.

        Returns futures positions plus spot USD/USDC balances.

        Returns:
            Dictionary with:
            - futures_positions: List of active long/short positions
            - futures_summary: Account summary (balance, PnL, margin, power)
            - holdings: Spot USD/USDC holdings
            - total_value_usd: Combined futures + spot value
            - futures_value_usd: Futures account value
            - spot_value_usd: Spot USD/USDC value
            - num_assets: Number of holdings (spot only)
        """
        logger.info("Fetching complete account breakdown")

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
                        'unrealized_pnl': float(
                            unrealized_pnl.get('value', 0)
                        ),
                        'daily_realized_pnl': float(
                            daily_pnl.get('value', 0)
                        ),
                        'buying_power': float(buying_power.get('value', 0)),
                        'initial_margin': float(
                            initial_margin.get('value', 0)
                        )
                    }

                    logger.info("Futures account balance: $%.2f", futures_value)

                # Get individual futures positions (long/short)
                positions_response = client.list_futures_positions()
                positions_list = getattr(
                    positions_response, 'positions', []
                )

                # Default leverage assumption for Coinbase perpetuals when
                # API does not provide an explicit leverage field. This is
                # a conservative hard-coded default used only for portfolio
                # margin/allocation calculations (signal-only mode).
                default_leverage = 10.0

                for pos in positions_list:
                    # pos may be a dict-like or an object with attributes.
                    # Use safe accessors to avoid TypeError/AttributeError or
                    # blocking calls caused by unexpected objects.
                    def safe_get(o, key, default=None):
                        try:
                            if isinstance(o, dict):
                                return o.get(key, default)
                            return getattr(o, key, default)
                        except Exception:
                            return default

                    # Try a set of possible leverage field names that the API
                    # might return. If found and parseable, store as a float;
                    # otherwise fall back to `default_leverage`.
                    raw_leverage = None
                    for key in ('leverage', 'leverage_ratio', 'margin_leverage', 'leverage_level', 'leverage_amount'):
                        candidate = safe_get(pos, key, None)
                        if candidate is not None:
                            raw_leverage = candidate
                            break

                    parsed_leverage = None
                    if raw_leverage is not None:
                        try:
                            parsed_leverage = float(raw_leverage)
                        except Exception:
                            parsed_leverage = None

                    leverage_value = parsed_leverage if parsed_leverage and parsed_leverage > 0 else default_leverage

                    product_id = safe_get(pos, 'product_id', None)
                    instrument = product_id or 'UNKNOWN'
                    side = (safe_get(pos, 'side', '') or '').upper()
                    contracts = float(safe_get(pos, 'number_of_contracts', 0))
                    signed_contracts = contracts if side == 'LONG' else -contracts
                    entry_price = float(safe_get(pos, 'avg_entry_price', 0))
                    current_price = float(safe_get(pos, 'current_price', 0))
                    unrealized_pnl = float(safe_get(pos, 'unrealized_pnl', 0))
                    opened_at: Optional[str] = (
                        safe_get(pos, 'created_at', None) or
                        safe_get(pos, 'open_time', None)
                    )

                    position_id = (
                        safe_get(pos, 'id', None)
                        or instrument
                        or f"coinbase_position_{len(futures_positions)}"
                    )

                    futures_positions.append({
                        'id': str(position_id),
                        'instrument': instrument,
                        'units': signed_contracts,
                        'entry_price': entry_price,
                        'current_price': current_price,
                        'pnl': unrealized_pnl,
                        'opened_at': opened_at,
                        'product_id': product_id,
                        'side': side,  # LONG or SHORT
                        'contracts': contracts,
                        'unrealized_pnl': unrealized_pnl,
                        'daily_pnl': float(safe_get(pos, 'daily_realized_pnl', 0)),
                        'leverage': leverage_value
                    })

                logger.info(
                    "Retrieved %d active futures positions (long/short)",
                    len(futures_positions)
                )

            except Exception as e:
                logger.error("Error fetching futures data: %s", e)
                raise

            # Get spot USD/USDC balances
            holdings = []
            spot_value = 0.0

            try:
                accounts_response = client.get_accounts()
                accounts_list = getattr(accounts_response, 'accounts', [])

                for account in accounts_list:
                    # Use attribute access for Coinbase Account objects
                    currency = getattr(account, 'currency', '')
                    if currency in ['USD', 'USDC']:
                        available_balance = getattr(
                            account, 'available_balance', None
                        )
                        if available_balance:
                            balance_value = float(
                                getattr(available_balance, 'value', 0)
                            )

                            if balance_value > 0:
                                holdings.append({
                                    'asset': currency,
                                    'amount': balance_value,
                                    'value_usd': balance_value,
                                    'allocation_pct': 0.0  # Calculate below
                                })
                                spot_value += balance_value
                                logger.info(
                                    "Spot %s: $%.2f", currency, balance_value
                                )
            except Exception as e:
                logger.warning("Could not fetch spot balances: %s", e)

            # Add futures positions to holdings with leverage adjustment.
            # Also sum margin exposures into futures_value if available.
            futures_margin_total = 0.0
            futures_notional_total = 0.0
            # Reuse the same default used above; if the block that created
            # `futures_positions` didn't run (e.g., positions API failed),
            # fallback here as well.
            default_leverage = locals().get('default_leverage', 10.0)

            for pos in futures_positions:
                # Ensure we have a safe numeric leverage value. `pos['leverage']`
                # is set above (when reading the API) to either a parsed float
                # or the `default_leverage` so this conversion should succeed.
                try:
                    leverage = float(pos.get('leverage', default_leverage))
                except Exception:
                    leverage = default_leverage

                contracts = float(pos.get('contracts', 0.0))
                current_price = float(pos.get('current_price', 0.0))

                # Coinbase perpetual futures have a contract multiplier of 0.1
                # (each contract represents 0.1 of the underlying asset, e.g., 0.1 ETH)
                contract_multiplier = 0.1
                notional = contracts * current_price * contract_multiplier

                margin = notional / leverage if leverage > 0 else notional
                futures_margin_total += margin
                futures_notional_total += notional

                holdings.append({
                    'asset': pos.get('product_id'),
                    'amount': contracts,
                    'value_usd': notional,  # Use notional for allocation calculations
                    'allocation_pct': 0.0
                })

            # Calculate total value and allocations. For allocation purposes,
            # use total notional exposure (not account balance).
            # This gives meaningful allocation percentages for leveraged positions.
            total_notional = futures_notional_total + spot_value
            total_value = futures_value + spot_value

            if total_notional > 0:
                for holding in holdings:
                    try:
                        holding_value = float(holding.get('value_usd', 0))
                        holding['allocation_pct'] = (
                            (holding_value / total_notional) * 100
                        )
                    except Exception:
                        holding['allocation_pct'] = 0.0

            logger.info(
                "Total portfolio value: $%.2f "
                "(futures: $%.2f, spot: $%.2f)",
                total_value, futures_value, spot_value
            )

            return {
                'futures_positions': futures_positions,
                'futures_summary': futures_summary,
                'holdings': holdings,
                'total_value_usd': total_value,
                'futures_value_usd': futures_value,
                'spot_value_usd': spot_value,
                'num_assets': len(holdings),
                # Expose unrealized P&L at the portfolio level for downstream
                # consumers.
                'unrealized_pnl': futures_summary.get('unrealized_pnl', 0.0),
                'platform': 'coinbase'
            }

        except Exception as e:
            logger.error("Error fetching portfolio breakdown: %s", e)
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(2),
        retry=retry_if_exception_type((RequestException, ConnectionError, TimeoutError))
    )
    def execute_trade(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a trade on Coinbase.

        Args:
            decision: Trading decision, expecting:
                - asset_pair: e.g., 'BTC-USD'
                - action: 'BUY' or 'SELL'
                - suggested_amount: The USD notional size for the market order

        Returns:
            Execution result
        """
        logger.info(
            "Trade execution requested: %s $%s %s",
            decision.get('action'),
            decision.get('suggested_amount', 0),
            decision.get('asset_pair')
        )

        client = self._get_client()
        action = decision.get('action')
        asset_pair = decision.get('asset_pair')
        product_id = self._format_product_id(asset_pair)
        size_in_usd = str(decision.get('suggested_amount', 0))
        client_order_id = f"ffe-{decision.get('id', uuid.uuid4().hex)}"

        # Check for existing order with the same client_order_id to avoid duplicates
        try:
            existing_orders = client.list_orders(client_order_id=client_order_id)
            # Validate that existing_orders is a list-like object with at least one item
            if existing_orders and hasattr(existing_orders, '__iter__') and len(existing_orders) > 0:
                existing_order = existing_orders[0]
                order_id = getattr(existing_order, 'id', None)
                order_status = getattr(existing_order, 'status', 'UNKNOWN')
                if not order_id:
                    raise ValueError("Existing order missing 'id' attribute")
                logger.info("Found existing order with client_order_id %s, reusing", client_order_id)
                return {
                    'success': True,
                    'platform': 'coinbase_advanced',
                    'decision_id': decision.get('id'),
                    'order_id': order_id,
                    'order_status': order_status,
                    'latency_seconds': 0,
                    'response': existing_order,
                    'timestamp': decision.get('timestamp')
                }
        except Exception as e:
            logger.debug("No existing order found or error checking: %s", e)

        if action not in ['BUY', 'SELL'] or float(size_in_usd) <= 0:
            logger.warning("Invalid trade decision: %s", decision)
            return {
                'success': False,
                'platform': 'coinbase_advanced',
                'decision_id': decision.get('id'),
                'error': 'Invalid action or size',
                'timestamp': decision.get('timestamp')
            }

        try:
            start_time = time.time()

            if action == 'BUY':
                order_result = client.market_order_buy(
                    client_order_id=client_order_id,
                    product_id=product_id,
                    quote_size=size_in_usd
                )
            else: # SELL
                # Fetch current price to calculate base size
                try:
                    product_response = client.get_product(product_id=product_id)
                    current_price = float(getattr(product_response, 'price', 0))
                    if current_price <= 0:
                        raise ValueError(f"Invalid price for {product_id}: {current_price}")
                    base_size_value = float(size_in_usd) / current_price
                    # Format with appropriate precision (8 decimals is standard for crypto)
                    base_size = f"{base_size_value:.8f}"
                    logger.info("Calculated base_size for SELL: %s (price: %.2f, usd_size: %s)", base_size, current_price, size_in_usd)
                except Exception as e:
                    logger.error("Failed to calculate base_size for SELL: %s", e)
                    raise

                order_result = client.market_order_sell(
                    client_order_id=client_order_id,
                    product_id=product_id,
                    base_size=base_size
                )

            latency = time.time() - start_time
            logger.info("Coinbase API call latency: %.2f seconds", latency)
            logger.info("Trade execution result: %s", order_result)

            # Log order details
            order_id = order_result.get('order_id')
            order_status = order_result.get('status')
            filled_size = order_result.get('filled_size')
            total_value = order_result.get('total_value')
            logger.info(
                "Order details - ID: %s, Status: %s, Filled Size: %s, Total Value: %s",
                order_id, order_status, filled_size, total_value
            )

            success = order_result.get('success', False)
            if success:
                return {
                    'success': True,
                    'platform': 'coinbase_advanced',
                    'decision_id': decision.get('id'),
                    'order_id': order_result.get('order_id'),
                    'order_status': order_result.get('status'),
                    'latency_seconds': latency,
                    'response': order_result,
                    'timestamp': decision.get('timestamp')
                }
            else:
                error_details = order_result.get('error_details', 'No error details')
                logger.error("Trade execution failed: %s", error_details)
                return {
                    'success': False,
                    'platform': 'coinbase_advanced',
                    'decision_id': decision.get('id'),
                    'error': 'Order creation failed',
                    'error_details': error_details,
                    'latency_seconds': latency,
                    'response': order_result,
                    'timestamp': decision.get('timestamp')
                }

        except (RequestException, ConnectionError, TimeoutError):
            raise  # Allow retry decorator to handle retryable exceptions
        except Exception as e:
            latency = time.time() - start_time if 'start_time' in locals() else -1
            logger.exception("Exception during trade execution")
            return {
                'success': False,
                'platform': 'coinbase_advanced',
                'decision_id': decision.get('id'),
                'error': str(e),
                'latency_seconds': latency,
                'timestamp': decision.get('timestamp')
            }

    def get_active_positions(self) -> PositionsResponse:
        """
        Get all currently active positions from Coinbase.

        Returns:
            A dictionary with ``"positions"`` containing Coinbase futures
            positions as :class:`PositionInfo` objects.
        """
        logger.info("Fetching active positions from Coinbase")
        portfolio = self.get_portfolio_breakdown()
        positions: List[PositionInfo] = portfolio.get('futures_positions', [])
        return {'positions': positions}
        """
        Get Coinbase account information including portfolio breakdown.

        Returns:
            Account details with portfolio metrics and leverage info
        """
        logger.info("Fetching Coinbase account info")

        try:
            portfolio = self.get_portfolio_breakdown()

            # Extract max leverage from futures positions (Coinbase sets this per product)
            max_leverage = 1.0  # Spot default
            futures_positions = portfolio.get('futures_positions', [])
            if futures_positions:
                leverages = [pos.get('leverage', 1.0) for pos in futures_positions if pos.get('leverage')]
                max_leverage = max(leverages) if leverages else 10.0  # Default to 10x if not specified

            return {
                'platform': 'coinbase_advanced',
                'account_type': 'trading',
                'status': 'active',
                'mode': 'signal_only',
                'execution_enabled': False,
                'max_leverage': max_leverage,  # Dynamically fetched from current positions
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
