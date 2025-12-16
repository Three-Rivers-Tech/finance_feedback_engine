#!/usr/bin/env python3
"""
Example: Adding a Custom Trading Platform to Finance Feedback Engine

This example demonstrates how to extend the Finance Feedback Engine
with a new trading platform integration.
"""

import sys
from pathlib import Path

# Add parent directory to path so we can import the package
sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import Any, Dict

from finance_feedback_engine.trading_platforms import (
    BaseTradingPlatform,
    PlatformFactory,
)


class BinancePlatform(BaseTradingPlatform):
    """
    Example implementation of Binance trading platform integration.

    This is a demonstration showing how to add a new platform.
    In production, you would implement actual Binance API calls.
    """

    def __init__(self, credentials: Dict[str, Any]):
        """
        Initialize Binance platform.

        Args:
            credentials: Dictionary containing:
                - api_key: Binance API key
                - api_secret: Binance API secret
        """
        super().__init__(credentials)
        self.api_key = credentials.get("api_key")
        self.api_secret = credentials.get("api_secret")
        print("✓ Binance platform initialized")

    def get_balance(self) -> Dict[str, float]:
        """
        Get account balances from Binance.

        Returns:
            Dictionary of asset balances
        """
        print("  Fetching Binance balances...")

        # TODO: Implement actual Binance API call
        # Example using python-binance library:
        # from binance.client import Client
        # client = Client(self.api_key, self.api_secret)
        # balances = client.get_account()['balances']

        # For demonstration, return mock data
        return {"USDT": 15000.0, "BTC": 0.75, "ETH": 3.5, "BNB": 10.0}

    def execute_trade(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a trade on Binance.

        Args:
            decision: Trading decision

        Returns:
            Execution result
        """
        print(
            f"  Executing trade on Binance: {decision['action']} {decision['asset_pair']}"
        )

        # TODO: Implement actual Binance trade execution
        # Example:
        # from binance.client import Client
        # client = Client(self.api_key, self.api_secret)
        # if decision['action'] == 'BUY':
        #     order = client.order_market_buy(
        #         symbol=decision['asset_pair'],
        #         quantity=decision['suggested_amount']
        #     )

        # For demonstration, return mock execution
        return {
            "success": True,
            "platform": "binance",
            "decision_id": decision.get("id"),
            "message": "Trade execution simulation (not implemented)",
            "timestamp": decision.get("timestamp"),
        }

    def get_account_info(self) -> Dict[str, Any]:
        """
        Get Binance account information.

        Returns:
            Account details
        """
        print("  Fetching Binance account info...")

        # TODO: Implement actual Binance API call
        return {
            "platform": "binance",
            "account_type": "spot",
            "status": "active",
            "balances": self.get_balance(),
            "features": ["spot_trading", "margin_trading", "futures"],
        }


def main():
    """Demonstrate adding a custom trading platform."""

    print("=" * 70)
    print("Example: Adding Custom Trading Platform (Binance)")
    print("=" * 70)

    # Step 1: Register the new platform
    print("\n1. Registering Binance platform...")
    PlatformFactory.register_platform("binance", BinancePlatform)
    print("   ✓ Platform registered successfully")

    # Step 2: List all available platforms
    print("\n2. Available platforms:")
    platforms = PlatformFactory.list_platforms()
    for platform in platforms:
        print(f"   • {platform}")

    # Step 3: Create an instance of the new platform
    print("\n3. Creating Binance platform instance...")
    credentials = {
        "api_key": "your_binance_api_key",
        "api_secret": "your_binance_api_secret",
    }
    binance = PlatformFactory.create_platform("binance", credentials)

    # Step 4: Test the platform methods
    print("\n4. Testing Binance platform methods...\n")

    # Test get_balance
    print("   a) Getting balance:")
    balance = binance.get_balance()
    for asset, amount in balance.items():
        print(f"      {asset}: {amount:,.2f}")

    # Test get_account_info
    print("\n   b) Getting account info:")
    account_info = binance.get_account_info()
    print(f"      Platform: {account_info['platform']}")
    print(f"      Account Type: {account_info['account_type']}")
    print(f"      Status: {account_info['status']}")

    # Test execute_trade (mock decision)
    print("\n   c) Testing trade execution:")
    mock_decision = {
        "id": "test-123",
        "asset_pair": "BTCUSDT",
        "action": "BUY",
        "suggested_amount": 0.1,
        "timestamp": "2024-01-01T00:00:00Z",
    }
    result = binance.execute_trade(mock_decision)
    print(f"      Result: {result['message']}")

    print("\n" + "=" * 70)
    print("✓ Custom Platform Integration Complete!")
    print("=" * 70)
    print("\nNext Steps:")
    print("  • Implement actual API calls using the platform's SDK")
    print("  • Add error handling and retry logic")
    print("  • Add authentication and security measures")
    print("  • Test thoroughly with sandbox/testnet")
    print("  • Use the platform in your configuration:")
    print("    trading_platform: 'binance'")
    print()


if __name__ == "__main__":
    main()
