"""Unified trading platform to manage multiple accounts."""

from typing import Dict, Any
import logging

from .base_platform import BaseTradingPlatform
from .coinbase_platform import CoinbaseAdvancedPlatform
from .oanda_platform import OandaPlatform

logger = logging.getLogger(__name__)


class UnifiedTradingPlatform(BaseTradingPlatform):
    """
    A unified trading platform that aggregates data from multiple platforms.
    
    Currently supports Coinbase Advanced (for crypto futures) and Oanda 
    (for forex).
    """

    def __init__(self, credentials: Dict[str, Any]):
        """
        Initialize the unified platform.

        Args:
            credentials: Dictionary containing credentials for sub-platforms,
                         e.g., {'coinbase': {...}, 'oanda': {...}}
        """
        super().__init__(credentials)
        self.platforms: Dict[str, BaseTradingPlatform] = {}

        # Support both 'coinbase' and 'coinbase_advanced' keys
        coinbase_creds = (
            credentials.get('coinbase') or
            credentials.get('coinbase_advanced')
        )
        if coinbase_creds:
            logger.info(
                "Initializing Coinbase Advanced platform for unified access."
            )
            self.platforms['coinbase'] = CoinbaseAdvancedPlatform(
                coinbase_creds
            )
        
        if 'oanda' in credentials and credentials['oanda']:
            logger.info("Initializing Oanda platform for unified access.")
            self.platforms['oanda'] = OandaPlatform(credentials['oanda'])

        if not self.platforms:
            raise ValueError(
                "No platforms were configured for UnifiedTradingPlatform."
            )

    def get_balance(self) -> Dict[str, float]:
        """
        Get combined account balances from all configured platforms.

        Returns:
            Dictionary mapping asset symbols to balances, prefixed with
            platform name. e.g., {'coinbase_FUTURES_USD': 1000.0,
            'oanda_USD': 50000.0}
        """
        combined_balances = {}
        for name, platform in self.platforms.items():
            try:
                balances = platform.get_balance()
                for asset, balance in balances.items():
                    combined_balances[f"{name}_{asset}"] = balance
            except (ValueError, TypeError, KeyError) as e:
                logger.error("Failed to get balance from %s: %s", name, e)
        
        return combined_balances

    def execute_trade(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a trade on the appropriate platform based on the asset pair.

        - Crypto (BTC, ETH) trades are routed to Coinbase.
        - Forex (e.g., EUR_USD) trades are routed to Oanda.
        """
        asset_pair = decision.get('asset_pair', '').upper()
        
        # Determine target platform
        target_platform = None
        # Expanded check for forex pairs, which might be standardized without '_'
        is_forex_pair = (
            '_' in asset_pair or
            any(p in asset_pair for p in ['EUR', 'GBP', 'JPY', 'AUD', 'CAD', 'CHF', 'NZD'])
        )

        if 'BTC' in asset_pair or 'ETH' in asset_pair:
            target_platform = self.platforms.get('coinbase')
        elif is_forex_pair:
            target_platform = self.platforms.get('oanda')

        if target_platform:
            logger.info(
                "Routing trade for %s to %s", 
                asset_pair, 
                target_platform.__class__.__name__
            )
            return target_platform.execute_trade(decision)
        else:
            logger.error(
                "No suitable platform found for asset pair: %s", asset_pair
            )
            return {
                'success': False,
                'error': f"No platform available for asset pair {asset_pair}",
                'decision_id': decision.get('id')
            }

    def get_account_info(self) -> Dict[str, Any]:
        """
        Get combined account information from all platforms.
        """
        combined_info = {}
        for name, platform in self.platforms.items():
            try:
                combined_info[name] = platform.get_account_info()
            except (ValueError, TypeError, KeyError) as e:
                logger.error("Failed to get account info from %s: %s", name, e)
                combined_info[name] = {'error': str(e)}
        return combined_info

    def get_portfolio_breakdown(self) -> Dict[str, Any]:
        """
        Get a combined portfolio breakdown from all platforms.
        
        Merges portfolio data from Coinbase (futures) and Oanda (forex).
        """
        total_value_usd = 0
        total_unrealized = 0.0
        all_holdings = []
        num_assets = 0
        cash_balances = {}
        
        platform_breakdowns = {}

        for name, platform in self.platforms.items():
            try:
                breakdown = platform.get_portfolio_breakdown()
                platform_breakdowns[name] = breakdown
                
                total_value_usd += breakdown.get('total_value_usd', 0)
                # Capture unrealized P&L if the platform exposes it
                total_unrealized += breakdown.get('unrealized_pnl', 0.0)

                # Capture cash/balance if provided by the platform
                bal = (
                    breakdown.get('balance') or
                    breakdown.get('total_balance_usd')
                )
                if bal is not None:
                    try:
                        cash_balances[name] = float(bal)
                    except Exception:
                        cash_balances[name] = 0.0
                
                # Add platform prefix to holdings
                holdings = breakdown.get('holdings', [])
                for holding in holdings:
                    holding['platform'] = name
                all_holdings.extend(holdings)
                
                num_assets += breakdown.get('num_assets', 0)

            except (ValueError, TypeError, KeyError) as e:
                logger.error(
                    "Failed to get portfolio breakdown from %s: %s", name, e
                )

        # Recalculate allocation percentages across the entire portfolio
        if total_value_usd > 0:
            for holding in all_holdings:
                allocation = (
                    holding.get('value_usd', 0) / total_value_usd
                ) * 100
                holding['allocation_pct'] = (
                    allocation if total_value_usd else 0
                )

        # Sum cash balances across platforms
        cash_balance_usd = (
            sum(cash_balances.values()) if cash_balances else 0.0
        )

        return {
            'total_value_usd': total_value_usd,
            'cash_balance_usd': cash_balance_usd,
            'per_platform_cash': cash_balances,
            'num_assets': num_assets,
            'holdings': all_holdings,
            'platform_breakdowns': platform_breakdowns,
            'unrealized_pnl': total_unrealized
        }
