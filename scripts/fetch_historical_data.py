#!/usr/bin/env python3
"""
Fetch historical data for FFE curriculum learning optimization.
Supports Coinbase Pro (crypto) and Oanda (forex) data sources.
"""

import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

COINBASE_API_URL = "https://api.exchange.coinbase.com"
OANDA_API_URL = "https://api-fxtrade.oanda.com"  # or fxpractice for demo

def fetch_coinbase_candles(symbol, start_date, end_date, granularity=300):
    """
    Fetch historical candles from Coinbase Pro.
    
    Args:
        symbol: Trading pair (e.g., 'BTC-USD')
        start_date: Start date (datetime)
        end_date: End date (datetime)
        granularity: Candle size in seconds (300 = 5 min)
    
    Returns:
        DataFrame with OHLCV data
    """
    print(f"Fetching {symbol} from Coinbase Pro ({start_date} to {end_date})...")
    
    all_candles = []
    current_start = start_date
    
    while current_start < end_date:
        # Coinbase limits to 300 candles per request
        current_end = min(current_start + timedelta(hours=25), end_date)
        
        url = f"{COINBASE_API_URL}/products/{symbol}/candles"
        params = {
            'start': current_start.isoformat(),
            'end': current_end.isoformat(),
            'granularity': granularity
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            candles = response.json()
            
            if candles:
                all_candles.extend(candles)
                print(f"  Fetched {len(candles)} candles ({current_start.date()} to {current_end.date()})")
            
            current_start = current_end
            time.sleep(0.11)  # Respect rate limit (10 req/sec = 100ms + margin)
            
        except Exception as e:
            print(f"  Error fetching {symbol}: {e}")
            time.sleep(1)
            continue
    
    # Convert to DataFrame
    df = pd.DataFrame(all_candles, columns=['time', 'low', 'high', 'open', 'close', 'volume'])
    df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df = df.sort_values('time').reset_index(drop=True)
    
    print(f"✅ {symbol}: {len(df)} candles fetched ({df['time'].min()} to {df['time'].max()})")
    return df

def fetch_oanda_candles(symbol, start_date, end_date, granularity='M5'):
    """
    Fetch historical candles from Oanda.
    
    Args:
        symbol: Instrument (e.g., 'EUR_USD')
        start_date: Start date (datetime)
        end_date: End date (datetime)
        granularity: Candle size (M5 = 5 min)
    
    Returns:
        DataFrame with OHLCV data
    """
    print(f"Fetching {symbol} from Oanda ({start_date} to {end_date})...")
    
    api_key = os.getenv('OANDA_API_KEY')
    if not api_key:
        raise ValueError("OANDA_API_KEY not found in environment")
    
    all_candles = []
    current_start = start_date
    
    while current_start < end_date:
        # Oanda limits to 5000 candles per request
        current_end = min(current_start + timedelta(days=17), end_date)
        
        url = f"{OANDA_API_URL}/v3/instruments/{symbol}/candles"
        headers = {'Authorization': f'Bearer {api_key}'}
        params = {
            'from': current_start.isoformat() + 'Z',
            'to': current_end.isoformat() + 'Z',
            'granularity': granularity,
            'price': 'M'  # Mid prices
        }
        
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            
            candles = data.get('candles', [])
            if candles:
                for candle in candles:
                    all_candles.append({
                        'time': candle['time'],
                        'open': float(candle['mid']['o']),
                        'high': float(candle['mid']['h']),
                        'low': float(candle['mid']['l']),
                        'close': float(candle['mid']['c']),
                        'volume': int(candle['volume'])
                    })
                
                print(f"  Fetched {len(candles)} candles ({current_start.date()} to {current_end.date()})")
            
            current_start = current_end
            time.sleep(0.2)  # Be nice to Oanda API
            
        except Exception as e:
            print(f"  Error fetching {symbol}: {e}")
            time.sleep(1)
            continue
    
    # Convert to DataFrame
    df = pd.DataFrame(all_candles)
    df['time'] = pd.to_datetime(df['time'], utc=True)
    df = df.sort_values('time').reset_index(drop=True)
    
    print(f"✅ {symbol}: {len(df)} candles fetched ({df['time'].min()} to {df['time'].max()})")
    return df

def main():
    # Date range: 2020-2023
    start_date = datetime(2020, 1, 1, tzinfo=None)
    end_date = datetime(2024, 1, 1, tzinfo=None)
    
    output_dir = Path('data/historical/curriculum_2020_2023')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Crypto (Coinbase)
    crypto_pairs = [
        ('BTC-USD', 'BTC_USD'),
        ('ETH-USD', 'ETH_USD')
    ]
    
    for coinbase_symbol, file_prefix in crypto_pairs:
        df = fetch_coinbase_candles(coinbase_symbol, start_date, end_date, granularity=300)
        output_file = output_dir / f"{file_prefix}_M5_2020_2023.parquet"
        df.to_parquet(output_file, index=False)
        print(f"💾 Saved to {output_file}\n")
    
    # Forex (Oanda)
    forex_pairs = [
        ('EUR_USD', 'EUR_USD'),
        ('GBP_USD', 'GBP_USD')
    ]
    
    for oanda_symbol, file_prefix in forex_pairs:
        df = fetch_oanda_candles(oanda_symbol, start_date, end_date, granularity='M5')
        output_file = output_dir / f"{file_prefix}_M5_2020_2023.parquet"
        df.to_parquet(output_file, index=False)
        print(f"💾 Saved to {output_file}\n")
    
    print("🎉 Historical data fetch complete!")
    print(f"📂 Data saved to: {output_dir}")

if __name__ == '__main__':
    main()
