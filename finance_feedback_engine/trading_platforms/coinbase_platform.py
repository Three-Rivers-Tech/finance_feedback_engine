"""Coinbase Advanced trading platform integration."""

import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from requests.exceptions import RequestException
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from ..observability.context import get_trace_headers
from .base_platform import BaseTradingPlatform, PositionInfo

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

    **TRACING STRATEGY**:
    - Client initialization: Defensively injects trace headers (correlation ID, traceparent)
      with full validation of client.session.headers before mutation.
    - Per-request headers: Call _inject_trace_headers_per_request() before API calls for
      fresh correlation IDs. For truly per-request tracing without manual calls, consider:
      1. Using requests.hooks={'response': callback} if Coinbase client exposes the session
      2. Creating a custom session subclass with per-request header injection
      3. Wrapping all API calls with @contextmanager to auto-inject headers
    - Fallback: If session.headers lacks update() method, headers are set individually.
    - Error handling: All header injection failures are logged but non-fatal.
    """

    # Class-level cache for minimum order sizes (TTL: 24 hours)
    _min_order_size_cache = {}
    _cache_ttl_seconds = 86400  # 24 hours

    def __init__(
        self, credentials: Dict[str, Any], config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize Coinbase Advanced platform.

        Args:
            credentials: Dictionary containing:
                - api_key: Coinbase API key
                - api_secret: Coinbase API secret
                - passphrase: Optional passphrase (for legacy API)
                - use_sandbox: Optional bool for sandbox environment
            config: Configuration dictionary containing timeout settings
        """
        super().__init__(credentials)
        self.api_key = credentials.get("api_key")
        self.api_secret = credentials.get("api_secret")
        self.passphrase = credentials.get("passphrase")
        self.use_sandbox = credentials.get("use_sandbox", False)

        # Initialize timeout configuration
        api_timeouts = (config or {}).get("api_timeouts", {})
        self.timeout_config = {
            "platform_balance": api_timeouts.get("platform_balance", 5),
            "platform_portfolio": api_timeouts.get("platform_portfolio", 10),
            "platform_execute": api_timeouts.get("platform_execute", 30),
            "platform_connection": api_timeouts.get("platform_connection", 3),
        }

        # Initialize Coinbase client (lazy loading)
        self._client = None

        logger.info(
            "Coinbase Advanced platform initialized " "(sandbox=%s)", self.use_sandbox
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
                # For CDP API keys (organizations/.../apiKeys/...), pass directly
                self._client = RESTClient(
                    api_key=self.api_key, api_secret=self.api_secret
                )

                # Inject correlation ID headers defensively
                try:
                    trace_headers = get_trace_headers()
                    if not isinstance(trace_headers, dict) or not trace_headers:
                        logger.debug(
                            "Trace headers invalid or empty, skipping injection"
                        )
                    elif hasattr(self._client, "session") and hasattr(
                        self._client.session, "headers"
                    ):
                        session_headers = self._client.session.headers
                        # Check if headers is dict-like with update method or is a dict
                        if hasattr(session_headers, "update"):
                            try:
                                session_headers.update(trace_headers)
                            except TypeError as e:
                                logger.warning(
                                    f"Failed to update session headers with trace context: {e}"
                                )
                        else:
                            # Fallback: set headers individually if update not available
                            for key, value in trace_headers.items():
                                try:
                                    session_headers[key] = value
                                except TypeError as e:
                                    logger.warning(f"Failed to set header {key}: {e}")
                    else:
                        logger.debug(
                            "Client session or headers attribute not found, "
                            "correlation headers not injected"
                        )
                except Exception as e:
                    logger.warning(
                        f"Unexpected error injecting trace headers: {e}", exc_info=True
                    )

                logger.info("Coinbase REST client initialized with CDP API format")
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
                logger.error(
                    "Failed to initialize Coinbase client: %s", e, exc_info=True
                )
                raise

        return self._client

    def _format_product_id(self, asset_pair: str) -> str:
        """
        Normalize various asset pair formats to Coinbase's product ID style.

        Args:
            asset_pair: Asset pair in various formats (e.g., "BTCUSD", "BTC/USD", "BTC-USD")

        Returns:
            Normalized product ID in Coinbase format (e.g., "BTC-USD")
        """
        try:
            if asset_pair is None:
                raise ValueError("asset_pair cannot be empty")

            if not asset_pair:
                raise ValueError("asset_pair cannot be empty")

            # Remove whitespace and standardize separators
            s = str(asset_pair).strip().upper()
            if not s:
                raise ValueError("asset_pair cannot be empty")
            s = s.replace("/", "-")

            # If already contains '-', ensure single hyphen separator
            if "-" in s:
                parts = [p for p in s.split("-") if p]
                if len(parts) == 2:
                    return f"{parts[0]}-{parts[1]}"
                # Fallback: join first two segments
                if len(parts) > 2:
                    return f"{parts[0]}-{parts[1]}"
                return s  # If we got here with a hyphen but can't parse, return as is

            # No separator case like BTCUSD or ETHUSDC
            # Split by known quote currency suffixes
            # Order by length (longest first) to prefer longer matches
            known_quotes = (
                "USDT",
                "USDC",
                "USD",
                "EUR",
                "GBP",
                "JPY",
                "AUD",
                "CAD",
                "BTC",
                "ETH",
            )
            for quote in known_quotes:
                if s.endswith(quote) and len(s) > len(quote):
                    base = s[: -len(quote)]
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

    def _inject_trace_headers_per_request(self) -> None:
        """
        Inject trace headers (correlation ID, traceparent) before each request.

        This ensures each request gets a fresh correlation context and should be called
        before making API requests to maintain per-request tracing.

        Note: For persistent per-request hooks, consider using requests hooks
        (e.g., response = session.request(..., hooks={'response': callback}))
        or middleware if available in the Coinbase client.
        """
        try:
            trace_headers = get_trace_headers()
            if not isinstance(trace_headers, dict) or not trace_headers:
                return
            if not hasattr(self._client, "session") or not hasattr(
                self._client.session, "headers"
            ):
                return
            session_headers = self._client.session.headers
            if hasattr(session_headers, "update"):
                try:
                    session_headers.update(trace_headers)
                except TypeError as e:
                    logger.warning(
                        f"Failed to update session headers with trace context: {e}"
                    )
            else:
                # Fallback: set headers individually
                for key, value in trace_headers.items():
                    try:
                        session_headers[key] = value
                    except TypeError as e:
                        logger.debug(f"Failed to set header {key}: {e}")
        except Exception as e:
            logger.debug(
                f"Error injecting per-request trace headers: {e}", exc_info=True
            )

    def get_minimum_order_size(self, asset_pair: str) -> float:
        """
        Get minimum order size for an asset pair with 24-hour caching.

        Queries Coinbase Advanced Trade API for product details (quote_min_size).
        Cache is invalidated on failed order execution or after 24 hours.

        Args:
            asset_pair: Trading pair (e.g., 'BTCUSD', 'ETHUSD')

        Returns:
            Minimum order size in quote currency (USD), defaults to 10.0 if API fails
        """
        import time

        cache_key = asset_pair
        current_time = time.time()

        # Check cache first
        if cache_key in self._min_order_size_cache:
            cached_value, cached_time = self._min_order_size_cache[cache_key]
            if current_time - cached_time < self._cache_ttl_seconds:
                logger.debug(
                    f"Using cached minimum order size for {asset_pair}: ${cached_value:.2f}"
                )
                return cached_value

        # Query API for product details
        try:
            client = self._get_client()

            # Convert asset_pair to Coinbase product ID format (e.g., BTCUSD -> BTC-USD)
            # Handle both BTCUSD and BTC-USD formats
            if "-" not in asset_pair:
                # Assume format is like BTCUSD -> BTC-USD
                # Common crypto assets are 3-4 characters
                if asset_pair.endswith("USD") or asset_pair.endswith("USDT"):
                    base = (
                        asset_pair[:-3]
                        if asset_pair.endswith("USD")
                        else asset_pair[:-4]
                    )
                    quote = (
                        asset_pair[-3:]
                        if asset_pair.endswith("USD")
                        else asset_pair[-4:]
                    )
                    product_id = f"{base}-{quote}"
                else:
                    product_id = asset_pair  # Use as-is if format unclear
            else:
                product_id = asset_pair

            # Get product details
            logger.debug(f"Querying Coinbase for minimum order size: {product_id}")
            product = client.get_product(product_id=product_id)

            if product and "quote_increment" in product:
                # quote_min_size is the minimum order size in quote currency
                min_size = float(product.get("quote_min_size", 10.0))

                # Cache the result
                self._min_order_size_cache[cache_key] = (min_size, current_time)
                logger.info(
                    f"Minimum order size for {asset_pair}: ${min_size:.2f} (cached for 24h)"
                )
                return min_size
            else:
                logger.warning(
                    f"Product details missing quote_min_size for {product_id}, using default $10"
                )
                fallback = 10.0
                self._min_order_size_cache[cache_key] = (fallback, current_time)
                return fallback

        except Exception as e:
            logger.error(
                f"Error querying minimum order size for {asset_pair}: {e}",
                exc_info=True,
            )
            # Return fallback and cache it temporarily
            fallback = 10.0
            self._min_order_size_cache[cache_key] = (fallback, current_time)
            return fallback

    def invalidate_minimum_order_size_cache(self, asset_pair: str = None) -> None:
        """
        Invalidate minimum order size cache.

        Call this after a failed order execution to force cache refresh.

        Args:
            asset_pair: Specific asset pair to invalidate, or None to clear all
        """
        if asset_pair:
            if asset_pair in self._min_order_size_cache:
                del self._min_order_size_cache[asset_pair]
                logger.debug(f"Invalidated minimum order size cache for {asset_pair}")
        else:
            self._min_order_size_cache.clear()
            logger.debug("Cleared all minimum order size cache entries")

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
                balance_summary = getattr(futures_summary, "balance_summary", None)

                if balance_summary:
                    # balance_summary supports dict-style access
                    total_usd_balance = balance_summary["total_usd_balance"]
                    if isinstance(total_usd_balance, dict):
                        futures_usd = float(total_usd_balance.get("value", 0) or 0)
                    else:
                        futures_usd = float(getattr(total_usd_balance, "value", 0) or 0)

                    if futures_usd > 0:
                        balances["FUTURES_USD"] = futures_usd
                        logger.info("Futures balance: $%.2f USD", futures_usd)

            except Exception as e:
                logger.warning("Could not fetch futures balance: %s", e)

            # Get spot balances via accounts endpoint (preferred in unit tests)
            try:
                accounts_response = client.get_accounts()
                accounts = getattr(accounts_response, "accounts", None) or []

                for account in accounts:
                    currency = (getattr(account, "currency", "") or "").upper()
                    if currency not in ("USD", "USDC"):
                        continue

                    available_balance = getattr(account, "available_balance", None)
                    balance_value = getattr(available_balance, "value", None)
                    spot_amount = float(balance_value or 0)
                    if spot_amount > 0:
                        balances[f"SPOT_{currency}"] = spot_amount
                        logger.info("Spot %s: $%.2f", currency, spot_amount)
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
            try:
                client = self._get_client()
            except ImportError:
                logger.error(
                    "Coinbase library not installed. Install with: pip install coinbase-advanced-py"
                )
                raise ValueError(
                    "Coinbase Advanced library required for real data. Please install coinbase-advanced-py"
                )

            # Prefer stable endpoints used by unit tests: futures summary + futures positions + accounts.
            if (
                hasattr(client, "get_futures_balance_summary")
                and hasattr(client, "list_futures_positions")
                and hasattr(client, "get_accounts")
            ):
                futures_value_usd = 0.0
                futures_positions: list[Any] = []
                futures_summary: dict[str, Any] = {}

                try:
                    futures_response = client.get_futures_balance_summary()
                    balance_summary = getattr(futures_response, "balance_summary", None)
                    if balance_summary:

                        def _to_float_value(v: Any) -> float:
                            if isinstance(v, dict):
                                return float(v.get("value", 0) or 0)
                            return float(getattr(v, "value", v) or 0)

                        def _get_attr_value(obj: Any, attr: str, default: Any = 0) -> Any:
                            """Safely get attribute from object or dict."""
                            if isinstance(obj, dict):
                                return obj.get(attr, default)
                            return getattr(obj, attr, default)

                        futures_value_usd = _to_float_value(
                            _get_attr_value(balance_summary, "total_usd_balance", 0)
                        )
                        futures_summary = {
                            "total_balance_usd": futures_value_usd,
                            "unrealized_pnl": _to_float_value(
                                _get_attr_value(balance_summary, "unrealized_pnl", 0)
                            ),
                            "daily_realized_pnl": _to_float_value(
                                _get_attr_value(balance_summary, "daily_realized_pnl", 0)
                            ),
                            "buying_power": _to_float_value(
                                _get_attr_value(balance_summary, "futures_buying_power", 0)
                            ),
                            "initial_margin": _to_float_value(
                                _get_attr_value(balance_summary, "initial_margin", 0)
                            ),
                        }
                except RequestException:
                    # Network errors should propagate for portfolio breakdown.
                    raise
                except Exception as e:
                    logger.warning("Could not fetch futures summary: %s", e)

                try:
                    positions_response = client.list_futures_positions()
                    futures_positions = list(
                        getattr(positions_response, "positions", None) or []
                    )
                except RequestException:
                    raise
                except Exception as e:
                    logger.warning("Could not fetch futures positions: %s", e)

                holdings: list[dict[str, Any]] = []
                spot_value_usd = 0.0
                try:
                    accounts_response = client.get_accounts()
                    accounts = getattr(accounts_response, "accounts", None) or []
                    for account in accounts:
                        currency = (getattr(account, "currency", "") or "").upper()
                        if currency not in ("USD", "USDC"):
                            continue
                        available_balance = getattr(account, "available_balance", None)
                        balance_value = getattr(available_balance, "value", None)
                        amount = float(balance_value or 0)
                        if amount > 0:
                            holdings.append({"asset": currency, "balance": amount})
                            spot_value_usd += amount
                except RequestException:
                    raise
                except Exception as e:
                    logger.warning("Could not fetch spot holdings: %s", e)

                return {
                    "futures_positions": futures_positions,
                    "futures_summary": futures_summary,
                    "holdings": holdings,
                    "total_value_usd": futures_value_usd + spot_value_usd,
                    "futures_value_usd": futures_value_usd,
                    "spot_value_usd": spot_value_usd,
                    "num_assets": len(holdings),
                }

            # Get portfolio breakdown (CDP API - bracket notation)
            portfolios_response = client.get_portfolios()
            portfolios = portfolios_response.portfolios

            if not portfolios:
                logger.warning("No portfolios found")
                return {}

            portfolio_uuid = portfolios[0]["uuid"]
            breakdown = client.get_portfolio_breakdown(portfolio_uuid=portfolio_uuid)
            breakdown_data = breakdown["breakdown"]  # Object supports bracket notation

            # Get futures/perp summary
            futures_positions = []
            futures_summary = {}
            futures_value = 0.0

            try:
                portfolio_balances = breakdown_data["portfolio_balances"]
                futures_value = float(
                    portfolio_balances["total_futures_balance"]["value"]
                )
                futures_unrealized_pnl = float(
                    portfolio_balances["futures_unrealized_pnl"]["value"]
                )
                perp_unrealized_pnl = float(
                    portfolio_balances["perp_unrealized_pnl"]["value"]
                )

                if (
                    futures_value > 0
                    or futures_unrealized_pnl != 0
                    or perp_unrealized_pnl != 0
                ):
                    futures_summary = {
                        "total_balance_usd": futures_value,
                        "unrealized_pnl": futures_unrealized_pnl + perp_unrealized_pnl,
                        "daily_realized_pnl": 0.0,
                        "buying_power": 0.0,
                        "initial_margin": 0.0,
                    }
                    logger.info("Futures account balance: $%.2f", futures_value)

                # Get individual futures and perp positions
                futures_positions_data = breakdown_data["futures_positions"]
                perp_positions_data = breakdown_data["perp_positions"]
                positions_list = futures_positions_data + perp_positions_data

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
                    for key in (
                        "leverage",
                        "leverage_ratio",
                        "margin_leverage",
                        "leverage_level",
                        "leverage_amount",
                    ):
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

                    leverage_value = (
                        parsed_leverage
                        if parsed_leverage and parsed_leverage > 0
                        else default_leverage
                    )

                    product_id = safe_get(pos, "product_id", None)
                    instrument = product_id or "UNKNOWN"
                    side = (safe_get(pos, "side", "") or "").upper()

                    # Try multiple field names for contract size
                    # number_of_contracts: standard Coinbase API field (string)
                    # amount: some response formats use this
                    # size: alternative field name
                    contracts = 0.0
                    for field_name in ["number_of_contracts", "amount", "size"]:
                        val = safe_get(pos, field_name, None)
                        if val is not None and val != 0:
                            try:
                                contracts = float(val)
                                if contracts != 0:
                                    logger.debug(
                                        f"Position {instrument}: found size in field '{field_name}' = {contracts}"
                                    )
                                    break
                            except (ValueError, TypeError):
                                continue

                    # Debug: log all fields for zero-size positions
                    if contracts == 0 and product_id:
                        logger.warning(
                            f"Position {product_id} has zero contracts. Available fields: {dict(pos) if isinstance(pos, dict) else {k: getattr(pos, k, '?') for k in dir(pos) if not k.startswith('_')}}"
                        )

                    signed_contracts = contracts if side == "LONG" else -contracts
                    entry_price = float(safe_get(pos, "avg_entry_price", 0))
                    current_price = float(safe_get(pos, "current_price", 0))
                    unrealized_pnl = float(safe_get(pos, "unrealized_pnl", 0))
                    opened_at: Optional[str] = safe_get(
                        pos, "created_at", None
                    ) or safe_get(pos, "open_time", None)

                    position_id = (
                        safe_get(pos, "id", None)
                        or instrument
                        or f"coinbase_position_{len(futures_positions)}"
                    )

                    # Create PositionInfo instance for type safety
                    position_info = PositionInfo(
                        id=str(position_id),
                        instrument=instrument,
                        units=signed_contracts,
                        entry_price=entry_price,
                        current_price=current_price,
                        pnl=unrealized_pnl,
                        opened_at=opened_at,
                        product_id=product_id,
                        side=side,
                        contracts=contracts,
                        unrealized_pnl=unrealized_pnl,
                        daily_pnl=float(safe_get(pos, "daily_realized_pnl", 0)),
                        leverage=leverage_value,
                    )

                    futures_positions.append(position_info)

                logger.info(
                    "Retrieved %d active futures positions (long/short)",
                    len(futures_positions),
                )

            except Exception as e:
                logger.error("Error fetching futures data: %s", e)
                raise

            # Get spot USD/USDC from portfolio breakdown
            holdings = []
            spot_value = 0.0

            try:
                spot_positions = breakdown_data["spot_positions"]

                for position in spot_positions:
                    asset = position["asset"]
                    if asset in ["USD", "USDC"]:
                        available_fiat = float(position["available_to_trade_fiat"])

                        if available_fiat > 0:
                            holdings.append(
                                {
                                    "asset": asset,
                                    "amount": available_fiat,
                                    "value_usd": available_fiat,
                                    "allocation_pct": 0.0,  # Calculate below
                                }
                            )
                            spot_value += available_fiat
                            logger.info("Spot %s: $%.2f", asset, available_fiat)
            except Exception as e:
                logger.warning("Could not fetch spot balances: %s", e)

            # Add futures positions to holdings with leverage adjustment.
            # Also sum margin exposures into futures_value if available.
            futures_margin_total = 0.0
            futures_notional_total = 0.0
            # Reuse the same default used above; if the block that created
            # `futures_positions` didn't run (e.g., positions API failed),
            # fallback here as well.
            default_leverage = locals().get("default_leverage", 10.0)

            for pos in futures_positions:
                # Ensure we have a safe numeric leverage value. `pos['leverage']`
                # is set above (when reading the API) to either a parsed float
                # or the `default_leverage` so this conversion should succeed.
                try:
                    leverage = float(pos.get("leverage", default_leverage))
                except Exception:
                    leverage = default_leverage

                contracts = float(pos.get("contracts", 0.0))
                current_price = float(pos.get("current_price", 0.0))

                # Coinbase perpetual futures have a contract multiplier of 0.1
                # (each contract represents 0.1 of the underlying asset, e.g., 0.1 ETH)
                contract_multiplier = 0.1
                notional = contracts * current_price * contract_multiplier

                margin = notional / leverage if leverage > 0 else notional
                futures_margin_total += margin
                futures_notional_total += notional

                holdings.append(
                    {
                        "asset": pos.get("product_id"),
                        "amount": contracts,
                        "value_usd": notional,  # Use notional for allocation calculations
                        "allocation_pct": 0.0,
                    }
                )

            # Calculate total value and allocations. For allocation purposes,
            # use total notional exposure (not account balance).
            # This gives meaningful allocation percentages for leveraged positions.
            total_notional = futures_notional_total + spot_value
            total_value = futures_value + spot_value

            if total_notional > 0:
                for holding in holdings:
                    try:
                        holding_value = float(holding.get("value_usd", 0))
                        holding["allocation_pct"] = (
                            holding_value / total_notional
                        ) * 100
                    except Exception:
                        holding["allocation_pct"] = 0.0

            logger.info(
                "Total portfolio value: $%.2f " "(futures: $%.2f, spot: $%.2f)",
                total_value,
                futures_value,
                spot_value,
            )

            return {
                "futures_positions": futures_positions,
                "futures_summary": futures_summary,
                "holdings": holdings,
                "total_value_usd": total_value,
                "futures_value_usd": futures_value,
                "spot_value_usd": spot_value,
                "num_assets": len(holdings),
                # Expose unrealized P&L at the portfolio level for downstream
                # consumers.
                "unrealized_pnl": futures_summary.get("unrealized_pnl", 0.0),
                "platform": "coinbase",
            }

        except Exception as e:
            logger.error("Error fetching portfolio breakdown: %s", e)
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(2),
        retry=retry_if_exception_type(
            (RequestException, ConnectionError, TimeoutError)
        ),
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
            decision.get("action"),
            decision.get("suggested_amount", 0),
            decision.get("asset_pair"),
        )

        client = self._get_client()
        action = decision.get("action")
        asset_pair = decision.get("asset_pair")
        product_id = self._format_product_id(asset_pair)
        size_in_usd = str(decision.get("suggested_amount", 0))
        client_order_id = f"ffe-{decision.get('id', uuid.uuid4().hex)}"

        # Check for existing order with the same client_order_id to avoid duplicates
        try:
            existing_orders = client.list_orders(client_order_id=client_order_id)
            # Validate that existing_orders is a list-like object with at least one item
            if (
                existing_orders
                and hasattr(existing_orders, "__iter__")
                and len(existing_orders) > 0
            ):
                existing_order = existing_orders[0]
                order_id = getattr(existing_order, "id", None)
                order_status = getattr(existing_order, "status", "UNKNOWN")
                if not order_id:
                    raise ValueError("Existing order missing 'id' attribute")
                logger.info(
                    "Found existing order with client_order_id %s, reusing",
                    client_order_id,
                )
                return {
                    "success": True,
                    "platform": "coinbase_advanced",
                    "decision_id": decision.get("id"),
                    "order_id": order_id,
                    "order_status": order_status,
                    "latency_seconds": 0,
                    "response": existing_order,
                    "timestamp": decision.get("timestamp"),
                }
        except Exception as e:
            logger.debug("No existing order found or error checking: %s", e)

        if action not in ["BUY", "SELL"] or float(size_in_usd) <= 0:
            logger.warning("Invalid trade decision: %s", decision)
            return {
                "success": False,
                "platform": "coinbase_advanced",
                "decision_id": decision.get("id"),
                "error": "Invalid action or size",
                "timestamp": decision.get("timestamp"),
            }

        try:
            start_time = time.time()

            if action == "BUY":
                order_result = client.market_order_buy(
                    client_order_id=client_order_id,
                    product_id=product_id,
                    quote_size=size_in_usd,
                )
            else:  # SELL
                # Fetch current price to calculate base size
                try:
                    product_response = client.get_product(product_id=product_id)
                    current_price = float(getattr(product_response, "price", 0))
                    if current_price <= 0:
                        raise ValueError(
                            f"Invalid price for {product_id}: {current_price}"
                        )
                    base_size_value = float(size_in_usd) / current_price
                    # Format with appropriate precision (8 decimals is standard for crypto)
                    base_size = f"{base_size_value:.8f}"
                    logger.info(
                        "Calculated base_size for SELL: %s (price: %.2f, usd_size: %s)",
                        base_size,
                        current_price,
                        size_in_usd,
                    )
                except Exception as e:
                    logger.error("Failed to calculate base_size for SELL: %s", e)
                    raise

                order_result = client.market_order_sell(
                    client_order_id=client_order_id,
                    product_id=product_id,
                    base_size=base_size,
                )

            latency = time.time() - start_time
            logger.info("Coinbase API call latency: %.2f seconds", latency)
            logger.info("Trade execution result: %s", order_result)

            # Log order details
            order_id = order_result.get("order_id")
            order_status = order_result.get("status")
            filled_size = order_result.get("filled_size")
            total_value = order_result.get("total_value")
            logger.info(
                "Order details - ID: %s, Status: %s, Filled Size: %s, Total Value: %s",
                order_id,
                order_status,
                filled_size,
                total_value,
            )

            success = order_result.get("success", False)
            if success:
                return {
                    "success": True,
                    "platform": "coinbase_advanced",
                    "decision_id": decision.get("id"),
                    "order_id": order_result.get("order_id"),
                    "order_status": order_result.get("status"),
                    "latency_seconds": latency,
                    "response": order_result,
                    "timestamp": decision.get("timestamp"),
                }
            else:
                error_details = order_result.get("error_details", "No error details")
                logger.error("Trade execution failed: %s", error_details)
                return {
                    "success": False,
                    "platform": "coinbase_advanced",
                    "decision_id": decision.get("id"),
                    "error": "Order creation failed",
                    "error_details": error_details,
                    "latency_seconds": latency,
                    "response": order_result,
                    "timestamp": decision.get("timestamp"),
                }

        except (RequestException, ConnectionError, TimeoutError):
            raise  # Allow retry decorator to handle retryable exceptions
        except Exception as e:
            latency = time.time() - start_time if "start_time" in locals() else -1
            logger.exception("Exception during trade execution")
            return {
                "success": False,
                "platform": "coinbase_advanced",
                "decision_id": decision.get("id"),
                "error": str(e),
                "latency_seconds": latency,
                "timestamp": decision.get("timestamp"),
            }

    def get_active_positions(self) -> Dict[str, Any]:
        """
        Get all currently active positions from Coinbase.

        Returns:
            A dictionary with ``"positions"`` containing Coinbase futures
            positions as dictionaries.
        """
        logger.info("Fetching active positions from Coinbase")
        portfolio = self.get_portfolio_breakdown()
        positions: List[Dict[str, Any]] = portfolio.get("futures_positions", [])
        return {"positions": positions}

    def get_account_info(self) -> Dict[str, Any]:
        """
        Get Coinbase account information.

        Returns:
            Account details including platform, balance, and leverage info
        """
        logger.info("Fetching Coinbase account info")

        try:
            portfolio = self.get_portfolio_breakdown()

            # Extract max leverage from futures positions (Coinbase sets this per product)
            max_leverage = 1.0  # Spot default
            futures_positions = portfolio.get("futures_positions", [])
            if futures_positions:
                leverages = [
                    pos.get("leverage", 1.0)
                    for pos in futures_positions
                    if pos.get("leverage")
                ]
                max_leverage = (
                    max(leverages) if leverages else 10.0
                )  # Default to 10x if not specified

            return {
                "platform": "coinbase_advanced",
                "account_type": "trading",
                "status": "active",
                "mode": "signal_only",
                "execution_enabled": False,
                "max_leverage": max_leverage,  # Dynamically fetched from current positions
                "balances": self.get_balance(),
                "portfolio": portfolio,
            }
        except Exception as e:
            logger.error("Error fetching account info: %s", e)
            return {
                "platform": "coinbase_advanced",
                "account_type": "unknown",
                "status": "error",
                "error": str(e),
            }
