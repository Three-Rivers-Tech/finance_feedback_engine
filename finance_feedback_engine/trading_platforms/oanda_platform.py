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
            # Instruments endpoint provides marginRate per instrument
            # Instruments import removed; some oandapyV20 versions differ
            # in constructor signatures and may raise instantiation errors.

            client = self._get_client()

            # Get account details
            account_request = AccountDetails(accountID=self.account_id)
            account_response = client.request(account_request)
            account = account_response.get('account', {})

            # Get open positions
            positions_request = OpenPositions(accountID=self.account_id)
            positions_response = client.request(positions_request)
            positions_data = positions_response.get('positions', [])

            # NOTE: Some oandapyV20 Instruments endpoints can be awkward to
            # instantiate across versions. To avoid compatibility issues,
            # compute per-position margin exposure from the account-level
            # `marginUsed` value when available. We'll fall back to a
            # default leverage if necessary.
            # We will compute margin exposure using account-level marginUsed
            # or by falling back to a default leverage estimate.

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

            # Convert holdings map to list and compute USD values using live
            # pricing where possible. We'll request pricing for all instruments
            # we have positions in plus any necessary conversion pairs to
            # convert the quote currency into the account base currency.
            holdings = []
            total_exposure_usd = 0.0

            # Build set of instruments to request pricing for
            instrument_set = set()
            for p in positions:
                instr = p.get('instrument')
                if instr:
                    instrument_set.add(instr)

            # Determine conversion pairs for any quote currency that isn't
            # the account base currency (e.g., convert JPY -> USD)
            conversion_candidates = set()
            for instr in list(instrument_set):
                if '_' in instr:
                    base, quote = instr.split('_')
                    if quote != base_currency:
                        # Try both directions; we'll use whichever pricing
                        # instrument is available and invert if needed.
                        conversion_candidates.add(f"{quote}_{base_currency}")
                        conversion_candidates.add(f"{base_currency}_{quote}")

            # Merge instrument lists and remove any empties
            all_request_instruments = list(
                instrument_set.union(conversion_candidates)
            )
            all_request_instruments = [
                i for i in all_request_instruments if i
            ]

            price_map = {}
            try:
                # Request Pricing for all instruments
                if all_request_instruments:
                    from oandapyV20.endpoints.pricing import PricingInfo

                    params = {
                        "instruments": ",".join(all_request_instruments)
                    }
                    pricing_request = PricingInfo(
                        accountID=self.account_id, params=params
                    )
                    pricing_response = client.request(pricing_request)

                    # Build price map using mid-price of bid/ask
                    for p in pricing_response.get('prices', []):
                        instr = p.get('instrument')
                        bids = p.get('bids', [])
                        asks = p.get('asks', [])
                        mid = None
                        try:
                            if bids and asks:
                                bid = float(bids[0].get('price'))
                                ask = float(asks[0].get('price'))
                                mid = (bid + ask) / 2.0
                            else:
                                # Fallback to closeout prices if present. Do
                                # not assume an arbitrary price of 1.0 — set
                                # to None so missing pricing is observable
                                # downstream.
                                cb = p.get('closeoutBid')
                                ca = p.get('closeoutAsk')
                                if cb is not None or ca is not None:
                                    try:
                                        mid = float(cb or ca)
                                    except Exception:
                                        logger.warning(
                                            "Invalid closeout prices for %s: "
                                            "cb=%s ca=%s",
                                            instr,
                                            cb,
                                            ca,
                                        )
                                        mid = None
                                else:
                                    logger.warning(
                                        (
                                            "Missing bids/asks and closeout prices "
                                            "for instrument %s. Payload: %s"
                                        ),
                                        instr,
                                        {
                                            k: v
                                            for k, v in p.items()
                                            if k in (
                                                'bids',
                                                'asks',
                                                'closeoutBid',
                                                'closeoutAsk',
                                            )
                                        },
                                    )
                                    mid = None
                        except Exception as exc:
                            # Log exception and the payload to make gaps
                            # observable
                            logger.warning(
                                "Exception while parsing pricing for %s: %s. "
                                "Payload: %s",
                                instr,
                                exc,
                                {
                                    k: v
                                    for k, v in p.items()
                                    if k in (
                                        'bids',
                                        'asks',
                                        'closeoutBid',
                                        'closeoutAsk',
                                    )
                                },
                            )
                            mid = None

                        if instr and mid is not None:
                            price_map[instr] = mid
            except Exception as e:
                logger.warning(
                    "Could not fetch live pricing for instruments: %s",
                    e
                )

            # Compute per-position notional (in quote currency) and convert
            # to account base currency (usually USD) using price_map.
            default_leverage = 50.0
            position_usd_values = []  # tuples of (instr, units, usd_value)

            for p in positions:
                instr = p.get('instrument')
                units = float(p.get('units', 0))
                price = price_map.get(instr)

                # notional is in quote currency (price is quote per base)
                if price is None:
                    logger.warning(
                        "Missing price for instrument %s; cannot compute "
                        "notional. Payload price_map entry: %s",
                        instr,
                        price_map.get(instr),
                    )
                    notional_in_quote = 0.0
                else:
                    notional_in_quote = abs(units) * price

                # If the quote currency matches account base, we're done
                usd_value = None
                if '_' in instr:
                    base, quote = instr.split('_')
                    if quote == base_currency:
                        usd_value = notional_in_quote
                    else:
                        # Try direct conversion: quote -> account base
                        direct = f"{quote}_{base_currency}"
                        inverse = f"{base_currency}_{quote}"

                        if direct in price_map:
                            conv_rate = price_map[direct]
                            usd_value = notional_in_quote * conv_rate
                        elif inverse in price_map and price_map.get(inverse):
                            conv_rate_inv = price_map[inverse]
                            try:
                                usd_value = (
                                    notional_in_quote * (1.0 / conv_rate_inv)
                                )
                            except Exception:
                                usd_value = None

                # Fallback: if we couldn't convert via pricing, fall back to
                # allocating margin proportionally or using leverage division
                if usd_value is None:
                    # If account reports margin_used, allocate proportionally
                    # otherwise derive margin exposure using a default leverage
                    usd_value = (notional_in_quote / default_leverage)

                position_usd_values.append((instr, units, usd_value))

            # Allocate margin_used proportionally across positions if available
            if margin_used and any(v for (_, _, v) in position_usd_values):
                total_notional = sum(
                    abs(v) for (_, _, v) in position_usd_values
                )
                if total_notional > 0:
                    # Scale to margin_used
                    scaled = []
                    for instr, units, usd_val in position_usd_values:
                        prop = (
                            (abs(usd_val) / total_notional)
                            if total_notional
                            else 0
                        )
                        scaled_val = prop * margin_used
                        scaled.append((instr, units, scaled_val))
                    position_usd_values = scaled

            # Build holdings list and compute total exposure
            for instr, units, usd_value in position_usd_values:
                try:
                    v = float(usd_value)
                except Exception:
                    v = 0.0
                total_exposure_usd += v
                holdings.append({
                    'asset': instr,
                    'amount': units,
                    'value_usd': v,
                    'allocation_pct': 0
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
                # Alias to keep naming consistent with other platforms.
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
            stop_loss_pct = decision.get('stop_loss_percentage', 0.02)

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
                    stop_loss_price = entry_price * (1 - stop_loss_pct)
                else:
                    stop_loss_price = entry_price * (1 + stop_loss_pct)

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

            # Check for API-level errors in the response
            if 'errorMessage' in response or 'orderRejectTransaction' in response:
                error_message = response.get('errorMessage', response.get('orderRejectTransaction', {}).get('rejectReason', 'Unknown error'))
                logger.error(f"Oanda API returned an error: {error_message}")
                return {
                    'success': False,
                    'platform': 'oanda',
                    'decision_id': decision.get('id'),
                    'error': error_message,
                    'timestamp': decision.get('timestamp')
                }

            # Parse response
            order_fill = response.get('orderFillTransaction', {})
            order_create = response.get('orderCreateTransaction', {})

            # If neither fill nor create transaction is present, assume failure
            if not order_fill and not order_create:
                logger.error(f"Oanda trade execution failed: No fill or create transaction in response. Full response: {response}")
                return {
                    'success': False,
                    'platform': 'oanda',
                    'decision_id': decision.get('id'),
                    'error': 'No order fill or create transaction found in response.',
                    'response': response
                }

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
            Account details including balance, margin, and leverage
        """
        logger.info("Fetching Oanda account info")

        try:
            from oandapyV20.endpoints.accounts import AccountDetails

            client = self._get_client()

            # Get account details
            request = AccountDetails(accountID=self.account_id)
            response = client.request(request)

            account = response.get('account', {})

            # Calculate effective leverage from margin rate
            margin_rate = float(account.get('marginRate', 0.02))
            effective_leverage = 1.0 / margin_rate if margin_rate > 0 else 50.0

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
                'margin_rate': margin_rate,
                'max_leverage': effective_leverage,  # Dynamically calculated from margin_rate
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
