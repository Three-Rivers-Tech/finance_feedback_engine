#!/usr/bin/env python3
"""Direct Coinbase API balance check - minimal dependencies"""
import asyncio
import aiohttp
import json
import time
import hmac
import hashlib
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv('COINBASE_API_KEY')
API_SECRET = os.getenv('COINBASE_API_SECRET')
BASE_URL = 'https://api.coinbase.com'

async def coinbase_request(method, path, params=None):
    """Make authenticated Coinbase API request"""
    timestamp = str(int(time.time()))
    
    # Build message to sign
    message = f'{timestamp}{method}{path}'
    if params:
        message += json.dumps(params)
    
    # Create signature
    signature = hmac.new(
        API_SECRET.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    headers = {
        'CB-ACCESS-KEY': API_KEY,
        'CB-ACCESS-SIGN': signature,
        'CB-ACCESS-TIMESTAMP': timestamp,
        'Content-Type': 'application/json'
    }
    
    async with aiohttp.ClientSession() as session:
        url = f'{BASE_URL}{path}'
        async with session.request(method, url, headers=headers, json=params) as resp:
            return await resp.json()

async def main():
    print('=== COINBASE PRODUCTION ACCOUNT BALANCES ===\n')
    
    # Try brokerage accounts API
    print('1. Checking Brokerage Accounts API...')
    try:
        accounts = await coinbase_request('GET', '/api/v3/brokerage/accounts')
        
        if 'accounts' in accounts:
            all_accounts = accounts['accounts']
            print(f'   Total accounts: {len(all_accounts)}')
            
            # Find non-zero balances
            funded = [a for a in all_accounts if float(a.get('available_balance', {}).get('value', 0)) > 0]
            
            if funded:
                print(f'   Accounts with funds: {len(funded)}\n')
                for acc in funded:
                    curr = acc['currency']
                    avail = acc['available_balance']['value']
                    hold = acc.get('hold', {}).get('value', '0')
                    print(f'   ✅ {curr}: ${avail} available, ${hold} on hold')
            else:
                print('   ⚠️  No funded accounts found')
                print(f'\n   Sample accounts (first 5):')
                for acc in all_accounts[:5]:
                    curr = acc['currency']
                    avail = acc.get('available_balance', {}).get('value', '0')
                    print(f'      {curr}: ${avail}')
        else:
            print(f'   ❌ Unexpected response: {accounts}')
    except Exception as e:
        print(f'   ❌ Error: {e}')
    
    # Try futures positions
    print('\n2. Checking Futures Positions (CFM API)...')
    try:
        positions = await coinbase_request('GET', '/api/v3/brokerage/cfm/positions')
        print(f'   Response: {positions}')
    except Exception as e:
        print(f'   ❌ Error: {e}')
    
    # Try portfolios
    print('\n3. Checking Portfolios...')
    try:
        portfolios = await coinbase_request('GET', '/api/v3/brokerage/portfolios')
        print(f'   Response: {json.dumps(portfolios, indent=2)[:500]}...')
    except Exception as e:
        print(f'   ❌ Error: {e}')

if __name__ == '__main__':
    asyncio.run(main())
