#!/usr/bin/env python3
"""Quick test of data fetching functionality - 1 week of BTC data"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timedelta
import pandas as pd
import requests

COINBASE_API_URL = "https://api.exchange.coinbase.com"

def test_coinbase_fetch():
    """Test Coinbase API with 1 week of BTC/USD M5 data"""
    print("Testing Coinbase API fetch...")
    
    start_date = datetime(2023, 1, 1, 0, 0, 0)
    end_date = datetime(2023, 1, 2, 0, 0, 0)  # Just 1 day for test
    
    url = f"{COINBASE_API_URL}/products/BTC-USD/candles"
    params = {
        'start': start_date.isoformat(),
        'end': end_date.isoformat(),
        'granularity': 300  # 5 minutes
    }
    
    print(f"URL: {url}")
    print(f"Params: {params}")
    
    try:
        response = requests.get(url, params=params, timeout=10)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response type: {type(data)}")
            
            if isinstance(data, list):
                print(f"✅ Fetched {len(data)} candles")
                if data:
                    df = pd.DataFrame(data, columns=['time', 'low', 'high', 'open', 'close', 'volume'])
                    df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
                    print(f"Date range: {df['time'].min()} to {df['time'].max()}")
                    print(f"\nSample data:\n{df.head()}")
                    return True
            else:
                print(f"Unexpected response: {data}")
                return False
        else:
            print(f"Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_coinbase_fetch()
    sys.exit(0 if success else 1)
