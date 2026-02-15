#!/usr/bin/env python3
import asyncio
import os
import sys
sys.path.insert(0, '.')

from finance_feedback_engine.trading_platforms.coinbase_platform import CoinbasePlatform

async def check_balances():
    platform = CoinbasePlatform(
        api_key=os.getenv('COINBASE_API_KEY'),
        api_secret=os.getenv('COINBASE_API_SECRET'),
        use_sandbox=False
    )
    
    print('=== RAW COINBASE API RESPONSES ===')
    try:
        # Check all accounts
        print('\n1. All Accounts (Brokerage API):')
        accounts_resp = await platform._request('GET', '/api/v3/brokerage/accounts')
        accounts = accounts_resp.get('accounts', [])
        print(f'Total accounts: {len(accounts)}')
        
        non_zero = [a for a in accounts if float(a.get('available_balance', {}).get('value', 0)) > 0]
        print(f'Accounts with balance: {len(non_zero)}')
        
        for acc in non_zero:
            curr = acc.get('currency')
            avail = acc.get('available_balance', {}).get('value', '0')
            hold = acc.get('hold', {}).get('value', '0')
            print(f'  {curr}: ${avail} available, ${hold} on hold')
        
        # Show first 5 zero-balance accounts
        print('\nSample zero-balance accounts:')
        for acc in accounts[:5]:
            curr = acc.get('currency')
            avail = acc.get('available_balance', {}).get('value', '0')
            print(f'  {curr}: ${avail}')
        
        # Check futures positions
        print('\n2. Futures Positions (CFM API):')
        try:
            positions_resp = await platform._request('GET', '/api/v3/brokerage/cfm/positions')
            print(f'Response: {positions_resp}')
        except Exception as pe:
            print(f'Positions API error: {pe}')
        
        # Try intx API (newer futures API)
        print('\n3. Futures Balances (INTX API):')
        try:
            intx_resp = await platform._request('GET', '/api/v1/portfolios')
            print(f'Response: {intx_resp}')
        except Exception as ie:
            print(f'INTX API error: {ie}')
        
    except Exception as e:
        print(f'FATAL ERROR: {e}')
        import traceback
        traceback.print_exc()

asyncio.run(check_balances())
