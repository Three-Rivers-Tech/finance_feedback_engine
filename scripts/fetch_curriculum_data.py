#!/usr/bin/env python3
"""
Curriculum Learning Historical Data Fetcher
Fetches 2020-2023 data for BTC, ETH, EUR/USD, GBP/USD across M5, M15, H1 timeframes
"""

import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

COINBASE_API_URL = "https://api.exchange.coinbase.com"
OANDA_API_URL = "https://api-fxtrade.oanda.com"

GRANULARITIES = {
    'M5': {'coinbase': 300, 'oanda': 'M5', 'minutes': 5},
    'M15': {'coinbase': 900, 'oanda': 'M15', 'minutes': 15},
    'H1': {'coinbase': 3600, 'oanda': 'H1', 'minutes': 60}
}

def fetch_coinbase_chunk(symbol, start, end, granularity_sec):
    """Fetch one chunk from Coinbase (max 300 candles)"""
    url = f"{COINBASE_API_URL}/products/{symbol}/candles"
    params = {
        'start': start.isoformat(),
        'end': end.isoformat(),
        'granularity': granularity_sec
    }
    
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    
    data = response.json()
    if isinstance(data, list):
        return data
    elif isinstance(data, dict) and 'message' in data:
        print(f"    API message: {data['message']}", flush=True)
        return []
    return []

def fetch_oanda_chunk(symbol, start, end, granularity_str, api_key):
    """Fetch one chunk from Oanda (max 5000 candles)"""
    url = f"{OANDA_API_URL}/v3/instruments/{symbol}/candles"
    headers = {'Authorization': f'Bearer {api_key}'}
    params = {
        'from': start.strftime('%Y-%m-%dT%H:%M:%S.000000000Z'),
        'to': end.strftime('%Y-%m-%dT%H:%M:%S.000000000Z'),
        'granularity': granularity_str,
        'price': 'M'
    }
    
    response = requests.get(url, headers=headers, params=params, timeout=30)
    response.raise_for_status()
    
    data = response.json()
    candles = []
    for candle in data.get('candles', []):
        candles.append({
            'time': candle['time'],
            'open': float(candle['mid']['o']),
            'high': float(candle['mid']['h']),
            'low': float(candle['mid']['l']),
            'close': float(candle['mid']['c']),
            'volume': int(candle['volume'])
        })
    return candles

def fetch_crypto_pair(symbol, start_date, end_date, timeframe):
    """Fetch crypto data from Coinbase with proper chunking"""
    print(f"\n🔸 {symbol} {timeframe} (Coinbase)", flush=True)
    print(f"   Range: {start_date.date()} to {end_date.date()}", flush=True)
    
    gran_sec = GRANULARITIES[timeframe]['coinbase']
    
    # Coinbase limit: 300 candles per request
    candles_per_chunk = 290  # Use 290 to be safe
    minutes_per_chunk = candles_per_chunk * GRANULARITIES[timeframe]['minutes']
    chunk_delta = timedelta(minutes=minutes_per_chunk)
    
    all_candles = []
    current_start = start_date
    chunk_num = 0
    
    while current_start < end_date:
        current_end = min(current_start + chunk_delta, end_date)
        chunk_num += 1
        
        try:
            candles = fetch_coinbase_chunk(symbol, current_start, current_end, gran_sec)
            all_candles.extend(candles)
            
            print(f"   Chunk {chunk_num}: {current_start.date()} - {len(candles)} candles", flush=True)
            
            current_start = current_end
            time.sleep(0.35)  # Rate limit: ~3 req/sec
            
        except Exception as e:
            print(f"   ⚠️  Error at {current_start.date()}: {e}", flush=True)
            time.sleep(2)
            continue
    
    if not all_candles:
        print(f"   ❌ No data fetched", flush=True)
        return pd.DataFrame()
    
    df = pd.DataFrame(all_candles, columns=['time', 'low', 'high', 'open', 'close', 'volume'])
    df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df = df.sort_values('time').drop_duplicates(subset=['time']).reset_index(drop=True)
    
    print(f"   ✅ Total: {len(df):,} candles ({df['time'].min().date()} to {df['time'].max().date()})", flush=True)
    return df

def fetch_forex_pair(symbol, start_date, end_date, timeframe, api_key):
    """Fetch forex data from Oanda with proper chunking"""
    print(f"\n🔸 {symbol} {timeframe} (Oanda)", flush=True)
    print(f"   Range: {start_date.date()} to {end_date.date()}", flush=True)
    
    gran_str = GRANULARITIES[timeframe]['oanda']
    
    # Oanda limit: 5000 candles per request
    candles_per_chunk = 4900
    minutes_per_chunk = candles_per_chunk * GRANULARITIES[timeframe]['minutes']
    chunk_delta = timedelta(minutes=minutes_per_chunk)
    
    all_candles = []
    current_start = start_date
    chunk_num = 0
    
    while current_start < end_date:
        current_end = min(current_start + chunk_delta, end_date)
        chunk_num += 1
        
        try:
            candles = fetch_oanda_chunk(symbol, current_start, current_end, gran_str, api_key)
            all_candles.extend(candles)
            
            print(f"   Chunk {chunk_num}: {current_start.date()} - {len(candles)} candles", flush=True)
            
            current_start = current_end
            time.sleep(0.5)  # Be respectful
            
        except Exception as e:
            print(f"   ⚠️  Error at {current_start.date()}: {e}", flush=True)
            time.sleep(2)
            continue
    
    if not all_candles:
        print(f"   ❌ No data fetched", flush=True)
        return pd.DataFrame()
    
    df = pd.DataFrame(all_candles)
    df['time'] = pd.to_datetime(df['time'], utc=True)
    df = df.sort_values('time').drop_duplicates(subset=['time']).reset_index(drop=True)
    
    print(f"   ✅ Total: {len(df):,} candles ({df['time'].min().date()} to {df['time'].max().date()})", flush=True)
    return df

def main():
    print("=" * 80, flush=True)
    print("CURRICULUM LEARNING DATA ACQUISITION", flush=True)
    print("=" * 80, flush=True)
    print("📅 Date Range: 2020-01-01 to 2023-12-31 (4 years)", flush=True)
    print("⏱️  Timeframes: M5, M15, H1", flush=True)
    print("💱 Pairs: BTC/USD, ETH/USD, EUR/USD, GBP/USD", flush=True)
    print("=" * 80, flush=True)
    
    start_date = datetime(2020, 1, 1, 0, 0, 0)
    end_date = datetime(2023, 12, 31, 23, 59, 59)
    
    output_dir = Path('data/historical/curriculum_2020_2023')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    oanda_api_key = os.getenv('OANDA_API_KEY')
    if not oanda_api_key:
        print("❌ OANDA_API_KEY not found in environment", flush=True)
        return 1
    
    timeframes = ['M5', 'M15', 'H1']
    results = []
    
    # Crypto pairs
    crypto_pairs = [
        ('BTC-USD', 'BTC_USD'),
        ('ETH-USD', 'ETH_USD')
    ]
    
    # Forex pairs
    forex_pairs = [
        ('EUR_USD', 'EUR_USD'),
        ('GBP_USD', 'GBP_USD')
    ]
    
    print("\n📊 PHASE 1: CRYPTOCURRENCY DATA", flush=True)
    print("=" * 80, flush=True)
    
    for symbol, prefix in crypto_pairs:
        for tf in timeframes:
            try:
                df = fetch_crypto_pair(symbol, start_date, end_date, tf)
                
                if not df.empty:
                    filename = f"{prefix}_{tf}_2020_2023.parquet"
                    filepath = output_dir / filename
                    df.to_parquet(filepath, index=False)
                    
                    results.append({
                        'pair': symbol,
                        'timeframe': tf,
                        'filename': filename,
                        'candles': len(df),
                        'start': df['time'].min(),
                        'end': df['time'].max()
                    })
                    
                    print(f"   💾 Saved: {filename}", flush=True)
                
            except Exception as e:
                print(f"   ❌ Failed {symbol} {tf}: {e}", flush=True)
                continue
    
    print("\n📊 PHASE 2: FOREX DATA", flush=True)
    print("=" * 80, flush=True)
    
    for symbol, prefix in forex_pairs:
        for tf in timeframes:
            try:
                df = fetch_forex_pair(symbol, start_date, end_date, tf, oanda_api_key)
                
                if not df.empty:
                    filename = f"{prefix}_{tf}_2020_2023.parquet"
                    filepath = output_dir / filename
                    df.to_parquet(filepath, index=False)
                    
                    results.append({
                        'pair': symbol,
                        'timeframe': tf,
                        'filename': filename,
                        'candles': len(df),
                        'start': df['time'].min(),
                        'end': df['time'].max()
                    })
                    
                    print(f"   💾 Saved: {filename}", flush=True)
                
            except Exception as e:
                print(f"   ❌ Failed {symbol} {tf}: {e}", flush=True)
                continue
    
    # Summary
    print("\n" + "=" * 80, flush=True)
    print("📊 ACQUISITION SUMMARY", flush=True)
    print("=" * 80, flush=True)
    
    summary_df = pd.DataFrame(results)
    if not summary_df.empty:
        summary_file = output_dir / 'acquisition_summary.csv'
        summary_df.to_csv(summary_file, index=False)
        
        print(f"\n✅ Successfully acquired {len(results)} datasets:\n", flush=True)
        for _, row in summary_df.iterrows():
            print(f"   {row['pair']:<12} {row['timeframe']:<4} | {row['candles']:>9,} candles | {row['filename']}", flush=True)
        
        print(f"\n💾 Summary saved: {summary_file}", flush=True)
        print(f"📂 Data directory: {output_dir}", flush=True)
    else:
        print("\n❌ No datasets acquired", flush=True)
        return 1
    
    print("\n🎉 DATA ACQUISITION COMPLETE!", flush=True)
    print("=" * 80, flush=True)
    
    return 0

if __name__ == '__main__':
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user", flush=True)
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}", flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)
