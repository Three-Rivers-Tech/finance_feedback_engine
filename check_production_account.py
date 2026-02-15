#!/usr/bin/env python3
"""Check production Coinbase account status."""
import os
from dotenv import load_dotenv
load_dotenv()

from coinbase.rest import RESTClient

api_key = os.getenv("COINBASE_API_KEY")
api_secret = os.getenv("COINBASE_API_SECRET")
use_sandbox = os.getenv("COINBASE_USE_SANDBOX", "false").lower() == "true"

base_url = "api-sandbox.coinbase.com" if use_sandbox else "api.coinbase.com"
print(f"Environment: {'SANDBOX' if use_sandbox else 'PRODUCTION'}")
print(f"Base URL: {base_url}\n")

client = RESTClient(api_key=api_key, api_secret=api_secret, base_url=base_url)

# Check futures balance
try:
    futures_response = client.get_futures_balance_summary()
    balance_summary = getattr(futures_response, 'balance_summary', None)
    if balance_summary:
        buying_power = getattr(balance_summary, 'futures_buying_power', None)
        if buying_power:
            print(f"Futures Buying Power: ${getattr(buying_power, 'value', 0)}")
        unrealized_pnl = getattr(balance_summary, 'unrealized_pnl', None)
        if unrealized_pnl:
            print(f"Unrealized P&L: ${getattr(unrealized_pnl, 'value', 0)}")
        total_balance = getattr(balance_summary, 'total_balance', None)
        if total_balance:
            print(f"Total Balance: ${getattr(total_balance, 'value', 0)}")
    else:
        print("No futures balance summary")
except Exception as e:
    print(f"Error fetching futures balance: {e}")

# Check futures positions
try:
    positions_response = client.list_futures_positions()
    positions = getattr(positions_response, 'positions', [])
    print(f"\nOpen Futures Positions: {len(positions)}")
    for pos in positions[:5]:
        product = getattr(pos, 'product_id', 'UNKNOWN')
        side = getattr(pos, 'side', 'UNKNOWN')
        size = getattr(pos, 'number_of_contracts', 0)
        entry_price = getattr(pos, 'entry_vwap_price', 0)
        print(f"  {product} {side} {size} contracts @ ${entry_price}")
except Exception as e:
    print(f"Error fetching positions: {e}")
