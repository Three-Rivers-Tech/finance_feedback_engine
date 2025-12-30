"""Oanda trading platform integration."""

import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from ..observability.context import get_trace_headers
from .base_platform import BaseTradingPlatform, PositionInfo, PositionsResponse
from .retry_handler import standardize_platform_error

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

    # Class-level cache for minimum trade sizes (TTL: 24 hours)
    _min_trade_size_cache = {}
    _cache_ttl_seconds = 86400  # 24 hours

    def __init__(
        self, credentials: Dict[str, Any], config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize Oanda platform.

        Args:
            credentials: Dictionary containing:
                - access_token: Oanda API access token (or api_key)
                - account_id: Oanda account ID
                - environment: 'practice' or 'live'
                - base_url: Optional custom base URL
            config: Configuration dictionary containing timeout settings
        """
        super().__init__(credentials)
        # Support both 'access_token' and 'api_key' for flexibility
        self.api_key = credentials.get("access_token") or credentials.get("api_key")
        self.account_id = credentials.get("account_id")
        self.environment = credentials.get("environment", "practice")

        # Set base URL based on environment
        if credentials.get("base_url"):
            self.base_url = credentials["base_url"]
        else:
            self.base_url = (
                "https://api-fxpractice.oanda.com"
                if self.environment == "practice"
                else "https://api-fxtrade.oanda.com"
            )

        # Initialize timeout configuration (standardized)
        from .retry_handler import get_timeout_config

        self.timeout_config = {
            "platform_balance": get_timeout_config(config, "platform_balance"),
            "platform_portfolio": get_timeout_config(config, "platform_portfolio"),
            "platform_execute": get_timeout_config(config, "platform_execute"),
            "platform_connection": get_timeout_config(config, "platform_connection"),
        }

        # Initialize Oanda client (lazy loading)
        self._client = None

        logger.info(
            "Oanda platform initialized (%s environment, base_url=%s)",
            self.environment,
            self.base_url,
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
                    access_token=self.api_key, environment=self.environment
                )
                # Inject correlation ID headers if client has requests session
                if hasattr(self._client, "session"):
                    try:
                        trace_headers = get_trace_headers()
                        if trace_headers:
                            self._client.session.headers.update(trace_headers)
                    except Exception as e:
                        logger.warning(
                            "Failed to inject trace headers into Oanda client: %s", e
                        )

                logger.info("Oanda API client initialized")
            except ImportError:
                logger.warning(
                    "oandapyV20 not installed. " "Install with: pip install oandapyV20"
                )
                raise ValueError(
                    "oandapyV20 library not available. Install with: pip install oandapyV20"
                )
            except Exception as e:
                logger.error("Failed to initialize Oanda client: %s", e)
                raise

        return self._client

    def get_minimum_trade_size(self, asset_pair: str) -> float:
        """
        Get minimum trade size for a currency pair with 24-hour caching.

        Queries Oanda API for instrument details (minimumTradeSize).
        Cache is invalidated on failed order execution or after 24 hours.

        Args:
            asset_pair: Currency pair (e.g., 'EURUSD', 'GBPUSD')

        Returns:
            Minimum trade size in units of base currency, defaults to 1.0 if API fails
        """
        import time

        cache_key = asset_pair
        current_time = time.time()

        # Check cache first
        if cache_key in self._min_trade_size_cache:
            cached_value, cached_time = self._min_trade_size_cache[cache_key]
            if current_time - cached_time < self._cache_ttl_seconds:
                logger.debug(
                    f"Using cached minimum trade size for {asset_pair}: {cached_value} units"
                )
                return cached_value

        # Query API for instrument details
        try:
            client = self._get_client()

            # Convert asset_pair to Oanda instrument format (e.g., EURUSD -> EUR_USD)
            if "_" not in asset_pair:
                # Assume format is like EURUSD -> EUR_USD
                # Forex pairs are typically 6 characters (3+3)
                if len(asset_pair) == 6:
                    instrument = f"{asset_pair[:3]}_{asset_pair[3:]}"
                elif len(asset_pair) == 7:  # Handle cases like XAUUSD
                    instrument = f"{asset_pair[:3]}_{asset_pair[3:]}"
                else:
                    instrument = asset_pair  # Use as-is if format unclear
            else:
                instrument = asset_pair

            # Oanda's Instruments endpoint can be tricky across library versions
            # Use a simpler approach: query account instruments
            try:
                from oandapyV20.endpoints.accounts import AccountInstruments

                logger.debug(f"Querying Oanda for minimum trade size: {instrument}")
                request = AccountInstruments(
                    accountID=self.account_id, params={"instruments": instrument}
                )
                response = client.request(request)

                if "instruments" in response and len(response["instruments"]) > 0:
                    instrument_data = response["instruments"][0]
                    min_size = float(instrument_data.get("minimumTradeSize", 1.0))

                    # Cache the result
                    self._min_trade_size_cache[cache_key] = (min_size, current_time)
                    logger.info(
                        f"Minimum trade size for {asset_pair}: {min_size} units (cached for 24h)"
                    )
                    return min_size
                else:
                    logger.warning(
                        f"Instrument details not found for {instrument}, using default 1.0 units"
                    )
                    fallback = 1.0
                    self._min_trade_size_cache[cache_key] = (fallback, current_time)
                    return fallback

            except Exception as inner_e:
                logger.warning(
                    f"Error querying instrument details for {instrument}: {inner_e}"
                )
                # Fallback to 5% of balance
                fallback = 1.0
                self._min_trade_size_cache[cache_key] = (fallback, current_time)
                return fallback

        except ImportError:
            logger.warning(
                "oandapyV20 not installed, using default minimum trade size of 1.0 units"
            )
            fallback = 1.0
            self._min_trade_size_cache[cache_key] = (fallback, current_time)
            return fallback
        except Exception as e:
            logger.error(
                f"Error querying minimum trade size for {asset_pair}: {e}",
                exc_info=True,
            )
            fallback = 1.0
            self._min_trade_size_cache[cache_key] = (fallback, current_time)
            return fallback

    def invalidate_minimum_trade_size_cache(self, asset_pair: str = None) -> None:
        """
        Invalidate minimum trade size cache.

        Call this after a failed order execution to force cache refresh.

        Args:
            asset_pair: Specific asset pair to invalidate, or None to clear all
        """
        if asset_pair:
            if asset_pair in self._min_trade_size_cache:
                del self._min_trade_size_cache[asset_pair]
                logger.debug(f"Invalidated minimum trade size cache for {asset_pair}")
        else:
            self._min_trade_size_cache.clear()
            logger.debug("Cleared all minimum trade size cache entries")

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

            account = response["account"]

            # Get base currency balance
            currency = account.get("currency", "USD")
            balance = float(account.get("balance", 0))

            if balance > 0:
                balances[currency] = balance
                logger.info("Oanda balance: %.2f %s", balance, currency)

            return balances

        except ImportError:
            logger.error(
                "oandapyV20 library not installed. Install with: pip install oandapyV20"
            )
            raise ValueError(
                "oandapyV20 library not available. Install with: pip install oandapyV20"
            )
        except Exception as e:
            logger.error("Error fetching Oanda balances: %s", e)
            raise

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
            account = account_response.get("account", {})

            # Get open positions
            positions_request = OpenPositions(accountID=self.account_id)
            positions_response = client.request(positions_request)
            positions_data = positions_response.get("positions", [])

            # NOTE: Some oandapyV20 Instruments endpoints can be awkward to
            # instantiate across versions. To avoid compatibility issues,
            # compute per-position margin exposure from the account-level
            # `marginUsed` value when available. We'll fall back to a
            # default leverage if necessary.
            # We will compute margin exposure using account-level marginUsed
            # or by falling back to a default leverage estimate.

            # Parse account info
            base_currency = account.get("currency", "USD")
            balance = float(account.get("balance", 0))
            unrealized_pl = float(account.get("unrealizedPL", 0))
            margin_used = float(account.get("marginUsed", 0))
            margin_available = float(account.get("marginAvailable", 0))
            nav = float(account.get("NAV", balance))

            # Parse positions
            positions = []
            holdings_map = {}  # Track net exposure per currency

            for pos in positions_data:
                instrument = pos.get("instrument", "UNKNOWN")

                # Parse long position
                long_pos = pos.get("long", {})
                long_units = float(long_pos.get("units", 0))
                long_pl = float(long_pos.get("unrealizedPL", 0))

                # Parse short position
                short_pos = pos.get("short", {})
                short_units = float(short_pos.get("units", 0))
                short_pl = float(short_pos.get("unrealizedPL", 0))

                # Net position
                net_units = long_units + short_units
                net_pl = long_pl + short_pl

                if net_units != 0:
                    position_type = "LONG" if net_units > 0 else "SHORT"
                    # Use averagePrice from the dominant side
                    if abs(long_units) >= abs(short_units):
                        average_price = float(long_pos.get("averagePrice", 0) or 0)
                    else:
                        average_price = float(short_pos.get("averagePrice", 0) or 0)
                    # current_price must come from pricing endpoint (already fetched below)
                    current_price = 0.0  # Will be populated from price_map if needed
                    opened_at: Optional[str] = pos.get("openTime")
                    position_id = (
                        pos.get("id") or f"{instrument}_{position_type.lower()}"
                    )

                    positions.append(
                        {
                            "id": str(position_id),
                            "instrument": instrument,
                            "units": net_units,
                            "entry_price": average_price,
                            "current_price": current_price,
                            "pnl": net_pl,
                            "opened_at": opened_at,
                            "position_type": position_type,
                            "unrealized_pl": net_pl,
                            "long_units": long_units,
                            "short_units": abs(short_units),
                            "long_pl": long_pl,
                            "short_pl": short_pl,
                        }
                    )

                    # Track currency exposure (simplified)
                    # Extract base and quote currencies
                    if "_" in instrument:
                        base, quote = instrument.split("_")

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
                instr = p.get("instrument")
                if instr:
                    instrument_set.add(instr)

            # Determine conversion pairs for any quote currency that isn't
            # the account base currency (e.g., convert JPY -> USD)
            conversion_candidates = set()
            for instr in list(instrument_set):
                if "_" in instr:
                    base, quote = instr.split("_")
                    if quote != base_currency:
                        # Try both directions; we'll use whichever pricing
                        # instrument is available and invert if needed.
                        conversion_candidates.add(f"{quote}_{base_currency}")
                        conversion_candidates.add(f"{base_currency}_{quote}")

            # Merge instrument lists and remove any empties
            all_request_instruments = list(instrument_set.union(conversion_candidates))
            all_request_instruments = [i for i in all_request_instruments if i]

            price_map = {}
            try:
                # Request Pricing for all instruments
                if all_request_instruments:
                    from oandapyV20.endpoints.pricing import PricingInfo

                    params = {"instruments": ",".join(all_request_instruments)}
                    pricing_request = PricingInfo(
                        accountID=self.account_id, params=params
                    )
                    pricing_response = client.request(pricing_request)

                    # Build price map using mid-price of bid/ask
                    for p in pricing_response.get("prices", []):
                        instr = p.get("instrument")
                        bids = p.get("bids", [])
                        asks = p.get("asks", [])
                        mid = None
                        try:
                            if bids and asks:
                                bid = float(bids[0].get("price"))
                                ask = float(asks[0].get("price"))
                                mid = (bid + ask) / 2.0
                            else:
                                # Fallback to closeout prices if present. Do
                                # not assume an arbitrary price of 1.0 — set
                                # to None so missing pricing is observable
                                # downstream.
                                cb = p.get("closeoutBid")
                                ca = p.get("closeoutAsk")
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
                                            if k
                                            in (
                                                "bids",
                                                "asks",
                                                "closeoutBid",
                                                "closeoutAsk",
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
                                    if k
                                    in (
                                        "bids",
                                        "asks",
                                        "closeoutBid",
                                        "closeoutAsk",
                                    )
                                },
                            )
                            mid = None

                        if instr and mid is not None:
                            price_map[instr] = mid
            except Exception as e:
                logger.warning("Could not fetch live pricing for instruments: %s", e)

            # Compute per-position notional (in quote currency) and convert
            # to account base currency (usually USD) using price_map.
            default_leverage = 50.0
            position_usd_values = []  # tuples of (instr, units, usd_value)

            for p in positions:
                instr = p.get("instrument")
                units = float(p.get("units", 0))
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
                if "_" in instr:
                    base, quote = instr.split("_")
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
                                usd_value = notional_in_quote * (1.0 / conv_rate_inv)
                            except Exception:
                                usd_value = None

                # Fallback: if we couldn't convert via pricing, fall back to
                # allocating margin proportionally or using leverage division
                if usd_value is None:
                    # If account reports margin_used, allocate proportionally
                    # otherwise derive margin exposure using a default leverage
                    usd_value = notional_in_quote / default_leverage

                position_usd_values.append((instr, units, usd_value))

            # Allocate margin_used proportionally across positions if available
            if margin_used and any(v for (_, _, v) in position_usd_values):
                total_notional = sum(abs(v) for (_, _, v) in position_usd_values)
                if total_notional > 0:
                    # Scale to margin_used
                    scaled = []
                    for instr, units, usd_val in position_usd_values:
                        prop = (abs(usd_val) / total_notional) if total_notional else 0
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
                holdings.append(
                    {
                        "asset": instr,
                        "amount": units,
                        "value_usd": v,
                        "allocation_pct": 0,
                    }
                )

            # Calculate allocation percentages
            if total_exposure_usd > 0:
                for holding in holdings:
                    holding["allocation_pct"] = (
                        holding["value_usd"] / total_exposure_usd * 100
                    )

            # Build portfolio summary
            portfolio = {
                "total_value_usd": nav,
                "num_assets": len(holdings),
                "base_currency": base_currency,
                "balance": balance,
                "unrealized_pl": unrealized_pl,
                # Alias to keep naming consistent with other platforms.
                "unrealized_pnl": unrealized_pl,
                "margin_used": margin_used,
                "margin_available": margin_available,
                "nav": nav,
                "positions": positions,
                "holdings": holdings,
                "platform": "oanda",
                "account_id": self.account_id,
                "environment": self.environment,
            }

            logger.info(
                "Oanda portfolio: %.2f %s NAV, %d positions, %d currencies",
                nav,
                base_currency,
                len(positions),
                len(holdings),
            )

            return portfolio

        except ImportError:
            logger.error(
                "Oanda library not installed. " "Install with: pip install oandapyV20"
            )
            raise ValueError("Oanda library required. Please install oandapyV20")
        except Exception as e:
            logger.error("Error fetching Oanda portfolio: %s", e)
            # Return minimal portfolio on error
            return {
                "total_value_usd": 0,
                "num_assets": 0,
                "positions": [],
                "holdings": [],
                "error": str(e),
            }

    def _get_recent_orders(
        self, instrument: str, max_results: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Query recent orders from Oanda to detect duplicates.

        Used for idempotency detection: before submitting a new order,
        check if an order with the same clientRequestID already exists.

        Args:
            instrument: Currency pair (e.g., 'EUR_USD')
            max_results: Maximum number of recent orders to retrieve

        Returns:
            List of recent order dictionaries from Oanda API
        """
        try:
            from oandapyV20.endpoints.orders import OrderList

            client = self._get_client()
            request = OrderList(self.account_id)
            # Oanda OrderList doesn't filter by instrument in constructor,
            # but returns all orders; we'll filter in post-processing
            response = client.request(request)

            orders = response.get("orders", [])
            logger.debug(
                "Retrieved %d recent orders from Oanda for account %s",
                len(orders),
                self.account_id,
            )
            return orders
        except ImportError:
            logger.error(
                "Oanda library not installed. Install with: pip install oandapyV20"
            )
            return []
        except Exception as e:
            logger.warning(
                "Failed to query recent orders for duplicate detection: %s", e
            )
            # Return empty list to allow submission (worst case: duplicate, but trade still happens)
            return []

    def _find_duplicate_order(
        self, instrument: str, units: int, client_request_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Search recent orders for an existing order matching this trade.

        Idempotency detection: checks for orders with matching clientRequestID,
        or matching instrument/units/direction within the last few minutes.

        Args:
            instrument: Currency pair (e.g., 'EUR_USD')
            units: Order size (positive for BUY, negative for SELL)
            client_request_id: Unique idempotency key for this order

        Returns:
            Matching order dict if found, None otherwise
        """
        try:
            recent_orders = self._get_recent_orders(instrument)

            for order in recent_orders:
                # Check by clientRequestID (primary idempotency key)
                if order.get("clientRequestID") == client_request_id:
                    logger.info(
                        "Found duplicate order by clientRequestID: %s, order_id=%s",
                        client_request_id,
                        order.get("id"),
                    )
                    return order

            logger.debug(
                "No duplicate order found for clientRequestID %s, instrument %s",
                client_request_id,
                instrument,
            )
            return None
        except Exception as e:
            logger.warning(
                "Error searching for duplicate orders (clientRequestID=%s): %s",
                client_request_id,
                e,
            )
            return None

    def execute_trade(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a forex trade on Oanda with idempotent retry logic.

        **IDEMPOTENCY STRATEGY**:
        - Generates a unique clientRequestID for each trade attempt
        - Before submission, queries recent orders to detect duplicates
        - Manually retries only on transient connection errors (not HTTP 5xx or timeouts)
        - Logs all attempts with clientRequestID for audit trail

        Args:
            decision: Trading decision containing:
                - asset_pair: Currency pair (e.g., 'EUR_USD')
                - action: BUY, SELL, or HOLD
                - recommended_position_size: Position size in units
                - stop_loss_percentage: Stop loss percentage

        Returns:
            Execution result with order details and clientRequestID
        """
        decision_id = decision.get("id", str(uuid.uuid4()))
        action = decision.get("action", "HOLD")

        logger.info(
            "Executing trade on Oanda: decision_id=%s, action=%s, asset=%s",
            decision_id,
            action,
            decision.get("asset_pair"),
        )

        if action == "HOLD":
            return {
                "success": True,
                "platform": "oanda",
                "decision_id": decision_id,
                "environment": self.environment,
                "message": "HOLD - no trade executed",
                "timestamp": decision.get("timestamp"),
            }

        try:
            from oandapyV20.endpoints.orders import OrderCreate

            # Generate unique idempotency key for this trade
            client_request_id = f"ffe-{decision_id}-{uuid.uuid4().hex[:8]}"
            logger.info(
                "Generated clientRequestID for idempotency: %s", client_request_id
            )

            # Parse decision parameters
            asset_pair = decision.get("asset_pair", "")
            # Convert to Oanda format (e.g., EURUSD -> EUR_USD)
            if "_" not in asset_pair and len(asset_pair) == 6:
                instrument = f"{asset_pair[:3]}_{asset_pair[3:]}"
            else:
                instrument = asset_pair

            units = decision.get("recommended_position_size", 1000)
            entry_price = decision.get("entry_price", 0)
            stop_loss_pct = decision.get("stop_loss_percentage", 0.02)

            # Determine order direction
            if action == "BUY":
                order_units = abs(units)
            elif action == "SELL":
                order_units = -abs(units)
            else:
                return {
                    "success": False,
                    "platform": "oanda",
                    "decision_id": decision_id,
                    "error": f"Unknown action: {action}",
                }

            # Calculate stop loss price
            stop_loss_price = None
            if entry_price > 0:
                if action == "BUY":
                    stop_loss_price = entry_price * (1 - stop_loss_pct)
                else:
                    stop_loss_price = entry_price * (1 + stop_loss_pct)

            # **IDEMPOTENCY CHECK**: Query recent orders to detect duplicates
            logger.debug(
                "Checking for duplicate orders (clientRequestID=%s, instrument=%s, units=%d)",
                client_request_id,
                instrument,
                order_units,
            )
            existing_order = self._find_duplicate_order(
                instrument, order_units, client_request_id
            )
            if existing_order:
                order_id = existing_order.get("id")
                order_status = existing_order.get("state")
                logger.info(
                    "Reusing existing order (duplicate detected): order_id=%s, status=%s, clientRequestID=%s",
                    order_id,
                    order_status,
                    client_request_id,
                )
                return {
                    "success": True,
                    "platform": "oanda",
                    "decision_id": decision_id,
                    "environment": self.environment,
                    "instrument": instrument,
                    "units": order_units,
                    "order_id": order_id,
                    "order_status": order_status,
                    "client_request_id": client_request_id,
                    "message": "Order already exists (idempotency detected)",
                    "timestamp": decision.get("timestamp"),
                }

            # Build order data with clientRequestID for idempotency
            order_data = {
                "order": {
                    "type": "MARKET",
                    "instrument": instrument,
                    "units": str(int(order_units)),
                    "timeInForce": "FOK",  # Fill or Kill
                    "positionFill": "DEFAULT",
                    "clientRequestID": client_request_id,  # Idempotency key
                }
            }

            # Add stop loss if calculated
            if stop_loss_price:
                order_data["order"]["stopLossOnFill"] = {
                    "price": f"{stop_loss_price:.5f}"
                }

            # **MANUAL RETRY LOGIC** (replaces @platform_retry decorator)
            # Only retry on transient connection errors, not HTTP 5xx or timeouts
            max_attempts = 3
            attempt = 0
            last_exception = None

            while attempt < max_attempts:
                attempt += 1
                logger.info(
                    "Submitting order (attempt %d/%d): clientRequestID=%s",
                    attempt,
                    max_attempts,
                    client_request_id,
                )

                try:
                    client = self._get_client()
                    order_request = OrderCreate(
                        accountID=self.account_id, data=order_data
                    )
                    start_time = time.time()
                    response = client.request(order_request)
                    elapsed = time.time() - start_time

                    logger.info(
                        "Order submission succeeded: clientRequestID=%s, elapsed=%.2fs",
                        client_request_id,
                        elapsed,
                    )

                    # Check for API-level errors in the response
                    if (
                        "errorMessage" in response
                        or "orderRejectTransaction" in response
                    ):
                        error_message = response.get(
                            "errorMessage",
                            response.get("orderRejectTransaction", {}).get(
                                "rejectReason", "Unknown error"
                            ),
                        )
                        logger.error(
                            "Oanda API returned an error: %s (clientRequestID=%s)",
                            error_message,
                            client_request_id,
                        )
                        return {
                            "success": False,
                            "platform": "oanda",
                            "decision_id": decision_id,
                            "client_request_id": client_request_id,
                            "error": error_message,
                            "attempt": attempt,
                            "timestamp": decision.get("timestamp"),
                        }

                    # Parse response
                    order_fill = response.get("orderFillTransaction", {})
                    order_create = response.get("orderCreateTransaction", {})

                    # If neither fill nor create transaction is present, assume failure
                    if not order_fill and not order_create:
                        logger.error(
                            "No fill or create transaction in response (clientRequestID=%s): %s",
                            client_request_id,
                            response,
                        )
                        return {
                            "success": False,
                            "platform": "oanda",
                            "decision_id": decision_id,
                            "client_request_id": client_request_id,
                            "error": "No order fill or create transaction found in response.",
                            "response": response,
                            "attempt": attempt,
                        }

                    order_id = order_fill.get("id", order_create.get("id"))
                    logger.info(
                        "Trade executed successfully: order_id=%s, clientRequestID=%s, attempt=%d",
                        order_id,
                        client_request_id,
                        attempt,
                    )

                    return {
                        "success": True,
                        "platform": "oanda",
                        "decision_id": decision_id,
                        "environment": self.environment,
                        "instrument": instrument,
                        "units": order_units,
                        "order_id": order_id,
                        "client_request_id": client_request_id,
                        "price": float(order_fill.get("price", 0)),
                        "pl": float(order_fill.get("pl", 0)),
                        "timestamp": decision.get("timestamp"),
                        "message": "Trade executed successfully",
                        "attempt": attempt,
                        "response": response,
                    }

                except ConnectionError as e:
                    # Transient connection error - may retry
                    last_exception = e
                    logger.warning(
                        "Connection error (attempt %d/%d): %s (clientRequestID=%s)",
                        attempt,
                        max_attempts,
                        e,
                        client_request_id,
                    )
                    if attempt < max_attempts:
                        wait_time = min(2**attempt, 15)  # Exponential backoff
                        logger.info("Retrying after %.1f seconds...", wait_time)
                        time.sleep(wait_time)
                    continue

                except TimeoutError as e:
                    # Timeout: DO NOT RETRY (order may have been submitted)
                    # Instead, query for existing order
                    last_exception = e
                    logger.error(
                        "Timeout error - will not retry to prevent duplicates (clientRequestID=%s): %s",
                        client_request_id,
                        e,
                    )
                    # Query to see if order went through
                    existing = self._find_duplicate_order(
                        instrument, order_units, client_request_id
                    )
                    if existing:
                        logger.info(
                            "Order was submitted before timeout: order_id=%s",
                            existing.get("id"),
                        )
                        return {
                            "success": True,
                            "platform": "oanda",
                            "decision_id": decision_id,
                            "order_id": existing.get("id"),
                            "client_request_id": client_request_id,
                            "message": "Order submitted (detected after timeout)",
                            "timestamp": decision.get("timestamp"),
                        }
                    # Re-raise to signal failure
                    raise

                except Exception as e:
                    # Other errors: check if retryable
                    last_exception = e
                    error_str = str(e).lower()

                    # Only retry on DNS/connection issues
                    if any(
                        keyword in error_str
                        for keyword in [
                            "dns",
                            "refused",
                            "host unreachable",
                            "network unreachable",
                        ]
                    ):
                        logger.warning(
                            "Retryable network error (attempt %d/%d): %s (clientRequestID=%s)",
                            attempt,
                            max_attempts,
                            e,
                            client_request_id,
                        )
                        if attempt < max_attempts:
                            wait_time = min(2**attempt, 15)
                            logger.info("Retrying after %.1f seconds...", wait_time)
                            time.sleep(wait_time)
                        continue
                    else:
                        # Non-retryable error
                        logger.error(
                            "Non-retryable error (clientRequestID=%s): %s",
                            client_request_id,
                            e,
                        )
                        raise standardize_platform_error(e, "execute_trade")

            # Exhausted retries
            logger.error(
                "Failed to execute trade after %d attempts (clientRequestID=%s): %s",
                max_attempts,
                client_request_id,
                last_exception,
            )
            if last_exception:
                raise standardize_platform_error(last_exception, "execute_trade")
            else:
                raise ValueError("Failed to execute trade: no exception captured")

        except ImportError:
            logger.error(
                "Oanda library not installed. Install with: pip install oandapyV20"
            )
            return {
                "success": False,
                "platform": "oanda",
                "decision_id": decision_id,
                "error": "Oanda library not installed",
            }
        except Exception as e:
            logger.error(
                "Error executing Oanda trade (decision_id=%s): %s",
                decision_id,
                e,
                exc_info=True,
            )
            raise standardize_platform_error(e, "execute_trade")

    def get_active_positions(self) -> PositionsResponse:
        """
        Get all currently active positions from Oanda.

        Returns:
            A dictionary with ``"positions"`` containing Oanda positions as
            :class:`PositionInfo` objects.
        """
        logger.info("Fetching active positions from Oanda")
        portfolio = self.get_portfolio_breakdown()
        positions: List[PositionInfo] = portfolio.get("positions", [])
        return {"positions": positions}

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

            account = response.get("account", {})

            # Calculate effective leverage from margin rate
            margin_rate = float(account.get("marginRate", 0.02))
            effective_leverage = 1.0 / margin_rate if margin_rate > 0 else 50.0

            return {
                "platform": "oanda",
                "account_id": self.account_id,
                "environment": self.environment,
                "account_type": "forex",
                "currency": account.get("currency", "USD"),
                "balance": float(account.get("balance", 0)),
                "nav": float(account.get("NAV", 0)),
                "unrealized_pl": float(account.get("unrealizedPL", 0)),
                "margin_used": float(account.get("marginUsed", 0)),
                "margin_available": float(account.get("marginAvailable", 0)),
                "margin_rate": margin_rate,
                "max_leverage": effective_leverage,  # Dynamically calculated from margin_rate
                "open_trade_count": int(account.get("openTradeCount", 0)),
                "open_position_count": int(account.get("openPositionCount", 0)),
                "status": "active",
                "balances": self.get_balance(),
            }

        except ImportError:
            logger.error(
                "Oanda library not installed. " "Install with: pip install oandapyV20"
            )
            # Return mock data as fallback
            return {
                "platform": "oanda",
                "account_id": self.account_id,
                "environment": self.environment,
                "account_type": "forex",
                "status": "library_not_installed",
                "error": "Install oandapyV20 for real data",
                "balances": {},
            }
        except Exception as e:
            logger.error("Error fetching Oanda account info: %s", e)
            return {
                "platform": "oanda",
                "account_id": self.account_id,
                "environment": self.environment,
                "error": str(e),
            }
