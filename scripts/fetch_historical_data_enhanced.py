#!/usr/bin/env python3
"""
Enhanced historical data fetcher for FFE curriculum learning optimization.
Supports multiple timeframes: M5, M15, H1
Fetches 2020-2023 data for crypto (Coinbase) and forex (Oanda).
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
OANDA_API_URL = "https://api-fxtrade.oanda.com"  # Production API

# Granularity mappings
COINBASE_GRANULARITIES = {
    'M5': 300,     # 5 minutes
    'M15': 900,    # 15 minutes
    'H1': 3600     # 1 hour
}

OANDA_GRANULARITIES = {
    'M5': 'M5',
    'M15': 'M15',
    'H1': 'H1'
}

def fetch_coinbase_candles(symbol, start_date, end_date, granularity_name='M5'):
    """
    Fetch historical candles from Coinbase Pro.
    
    Args:
        symbol: Trading pair (e.g., 'BTC-USD')
        start_date: Start date (datetime)
        end_date: End date (datetime)
        granularity_name: Timeframe (M5, M15, H1)
    
    Returns:
        DataFrame with OHLCV data
    """
    granularity = COINBASE_GRANULARITIES[granularity_name]
    print(f"\n🔹 Fetching {symbol} {granularity_name} from Coinbase Pro ({start_date.date()} to {end_date.date()})...")
    
    all_candles = []
    current_start = start_date
    
    # Coinbase limits to 300 candles per request
    # For M5: 300 * 5min = 25 hours
    # For M15: 300 * 15min = 75 hours (~3 days)
    # For H1: 300 * 1hour = 300 hours (~12.5 days)
    chunk_hours = {
        'M5': 25,
        'M15': 72,
        'H1': 300
    }
    
    chunk_size = timedelta(hours=chunk_hours[granularity_name])
    
    while current_start < end_date:
        current_end = min(current_start + chunk_size, end_date)
        
        url = f"{COINBASE_API_URL}/products/{symbol}/candles"
        params = {
            'start': current_start.isoformat(),
            'end': current_end.isoformat(),
            'granularity': granularity
        }
        
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            candles = response.json()
            
            if isinstance(candles, list) and candles:
                all_candles.extend(candles)
                print(f"  ✓ Fetched {len(candles)} candles ({current_start.date()} to {current_end.date()})")
            elif isinstance(candles, dict) and 'message' in candles:
                print(f"  ⚠️  API message: {candles['message']}")
            
            current_start = current_end
            time.sleep(0.35)  # Respect rate limit (3 req/sec = 333ms)
            
        except requests.exceptions.RequestException as e:
            print(f"  ❌ Error fetching {symbol}: {e}")
            time.sleep(2)
            continue
        except Exception as e:
            print(f"  ❌ Unexpected error: {e}")
            time.sleep(2)
            continue
    
    if not all_candles:
        print(f"  ⚠️  No data fetched for {symbol} {granularity_name}")
        return pd.DataFrame()
    
    # Convert to DataFrame
    df = pd.DataFrame(all_candles, columns=['time', 'low', 'high', 'open', 'close', 'volume'])
    df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df = df.sort_values('time').reset_index(drop=True)
    
    # Remove duplicates
    df = df.drop_duplicates(subset=['time'], keep='first')
    
    print(f"  ✅ {symbol} {granularity_name}: {len(df)} candles ({df['time'].min()} to {df['time'].max()})")
    return df

def fetch_oanda_candles(symbol, start_date, end_date, granularity_name='M5'):
    """
    Fetch historical candles from Oanda.
    
    Args:
        symbol: Instrument (e.g., 'EUR_USD')
        start_date: Start date (datetime)
        end_date: End date (datetime)
        granularity_name: Timeframe (M5, M15, H1)
    
    Returns:
        DataFrame with OHLCV data
    """
    granularity = OANDA_GRANULARITIES[granularity_name]
    print(f"\n🔹 Fetching {symbol} {granularity_name} from Oanda ({start_date.date()} to {end_date.date()})...")
    
    api_key = os.getenv('OANDA_API_KEY')
    if not api_key:
        raise ValueError("OANDA_API_KEY not found in environment")
    
    all_candles = []
    current_start = start_date
    
    # Oanda limits to 5000 candles per request
    # For M5: 5000 * 5min = 25000 min ~= 17.4 days
    # For M15: 5000 * 15min = 75000 min ~= 52 days
    # For H1: 5000 * 1hour = 5000 hours ~= 208 days
    chunk_days = {
        'M5': 17,
        'M15': 50,
        'H1': 200
    }
    
    chunk_size = timedelta(days=chunk_days[granularity_name])
    
    while current_start < end_date:
        current_end = min(current_start + chunk_size, end_date)
        
        url = f"{OANDA_API_URL}/v3/instruments/{symbol}/candles"
        headers = {'Authorization': f'Bearer {api_key}'}
        params = {
            'from': current_start.strftime('%Y-%m-%dT%H:%M:%S.000000000Z'),
            'to': current_end.strftime('%Y-%m-%dT%H:%M:%S.000000000Z'),
            'granularity': granularity,
            'price': 'M'  # Mid prices
        }
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)
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
                
                print(f"  ✓ Fetched {len(candles)} candles ({current_start.date()} to {current_end.date()})")
            
            current_start = current_end
            time.sleep(0.5)  # Be respectful to Oanda API
            
        except requests.exceptions.RequestException as e:
            print(f"  ❌ Error fetching {symbol}: {e}")
            time.sleep(2)
            continue
        except Exception as e:
            print(f"  ❌ Unexpected error: {e}")
            time.sleep(2)
            continue
    
    if not all_candles:
        print(f"  ⚠️  No data fetched for {symbol} {granularity_name}")
        return pd.DataFrame()
    
    # Convert to DataFrame
    df = pd.DataFrame(all_candles)
    df['time'] = pd.to_datetime(df['time'], utc=True)
    df = df.sort_values('time').reset_index(drop=True)
    
    # Remove duplicates
    df = df.drop_duplicates(subset=['time'], keep='first')
    
    print(f"  ✅ {symbol} {granularity_name}: {len(df)} candles ({df['time'].min()} to {df['time'].max()})")
    return df

def validate_data(df, symbol, timeframe, start_date, end_date):
    """
    Validate fetched data for completeness.
    
    Returns:
        dict with validation results
    """
    if df.empty:
        return {
            'valid': False,
            'reason': 'No data fetched',
            'gap_count': 0,
            'coverage_pct': 0.0
        }
    
    # Check date range coverage
    actual_start = df['time'].min()
    actual_end = df['time'].max()
    
    # Calculate expected number of candles
    timeframe_minutes = {
        'M5': 5,
        'M15': 15,
        'H1': 60
    }
    
    total_minutes = (end_date - start_date).total_seconds() / 60
    expected_candles = int(total_minutes / timeframe_minutes[timeframe])
    
    # Account for weekends in forex (no trading Sat-Sun)
    if 'USD' in symbol and 'BTC' not in symbol and 'ETH' not in symbol:
        # Rough estimate: remove ~28% for weekends
        expected_candles = int(expected_candles * 0.72)
    
    actual_candles = len(df)
    coverage_pct = (actual_candles / expected_candles) * 100 if expected_candles > 0 else 0
    
    # Check for gaps (simple check: time differences)
    df_sorted = df.sort_values('time')
    time_diffs = df_sorted['time'].diff()
    expected_diff = pd.Timedelta(minutes=timeframe_minutes[timeframe])
    
    # Allow 2x tolerance for gaps (markets close, weekends, etc.)
    gaps = (time_diffs > expected_diff * 2).sum()
    
    valid = coverage_pct >= 60.0  # At least 60% coverage
    
    return {
        'valid': valid,
        'actual_candles': actual_candles,
        'expected_candles': expected_candles,
        'coverage_pct': coverage_pct,
        'gap_count': gaps,
        'date_range': f"{actual_start.date()} to {actual_end.date()}"
    }

def main():
    print("=" * 80)
    print("ENHANCED HISTORICAL DATA FETCHER")
    print("=" * 80)
    print(f"Date Range: 2020-01-01 to 2023-12-31")
    print(f"Timeframes: M5, M15, H1")
    print(f"Pairs: BTC/USD, ETH/USD, EUR/USD, GBP/USD")
    print("=" * 80)
    
    # Date range: 2020-2023 (full years)
    start_date = datetime(2020, 1, 1, 0, 0, 0)
    end_date = datetime(2023, 12, 31, 23, 59, 59)
    
    output_dir = Path('data/historical/curriculum_2020_2023')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timeframes = ['M5', 'M15', 'H1']
    
    # Crypto pairs (Coinbase)
    crypto_pairs = [
        ('BTC-USD', 'BTC_USD'),
        ('ETH-USD', 'ETH_USD')
    ]
    
    # Forex pairs (Oanda)
    forex_pairs = [
        ('EUR_USD', 'EUR_USD'),
        ('GBP_USD', 'GBP_USD')
    ]
    
    validation_results = []
    
    print("\n" + "=" * 80)
    print("PHASE 1: CRYPTO DATA (Coinbase Pro)")
    print("=" * 80)
    
    for coinbase_symbol, file_prefix in crypto_pairs:
        for timeframe in timeframes:
            try:
                df = fetch_coinbase_candles(coinbase_symbol, start_date, end_date, timeframe)
                
                if not df.empty:
                    output_file = output_dir / f"{file_prefix}_{timeframe}_2020_2023.parquet"
                    df.to_parquet(output_file, index=False)
                    
                    validation = validate_data(df, coinbase_symbol, timeframe, start_date, end_date)
                    validation_results.append({
                        'pair': coinbase_symbol,
                        'timeframe': timeframe,
                        'file': output_file.name,
                        **validation
                    })
                    
                    status = "✅ VALID" if validation['valid'] else "⚠️  LOW COVERAGE"
                    print(f"  💾 Saved: {output_file.name} - {status}")
                    print(f"     Coverage: {validation['coverage_pct']:.1f}% | Gaps: {validation['gap_count']}")
                else:
                    print(f"  ❌ Failed to fetch {coinbase_symbol} {timeframe}")
                
                time.sleep(1)  # Brief pause between timeframes
                
            except Exception as e:
                print(f"  ❌ Error processing {coinbase_symbol} {timeframe}: {e}")
                continue
    
    print("\n" + "=" * 80)
    print("PHASE 2: FOREX DATA (Oanda)")
    print("=" * 80)
    
    for oanda_symbol, file_prefix in forex_pairs:
        for timeframe in timeframes:
            try:
                df = fetch_oanda_candles(oanda_symbol, start_date, end_date, timeframe)
                
                if not df.empty:
                    output_file = output_dir / f"{file_prefix}_{timeframe}_2020_2023.parquet"
                    df.to_parquet(output_file, index=False)
                    
                    validation = validate_data(df, oanda_symbol, timeframe, start_date, end_date)
                    validation_results.append({
                        'pair': oanda_symbol,
                        'timeframe': timeframe,
                        'file': output_file.name,
                        **validation
                    })
                    
                    status = "✅ VALID" if validation['valid'] else "⚠️  LOW COVERAGE"
                    print(f"  💾 Saved: {output_file.name} - {status}")
                    print(f"     Coverage: {validation['coverage_pct']:.1f}% | Gaps: {validation['gap_count']}")
                else:
                    print(f"  ❌ Failed to fetch {oanda_symbol} {timeframe}")
                
                time.sleep(1)
                
            except Exception as e:
                print(f"  ❌ Error processing {oanda_symbol} {timeframe}: {e}")
                continue
    
    # Save validation report
    print("\n" + "=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)
    
    validation_df = pd.DataFrame(validation_results)
    validation_file = output_dir / 'data_validation_report.csv'
    validation_df.to_csv(validation_file, index=False)
    
    print(f"\n📊 Validation Report:")
    for _, row in validation_df.iterrows():
        status = "✅" if row['valid'] else "⚠️"
        print(f"{status} {row['pair']:<12} {row['timeframe']:<4} | "
              f"Coverage: {row['coverage_pct']:>5.1f}% | "
              f"Candles: {row['actual_candles']:>7,} | "
              f"Gaps: {row['gap_count']:>4}")
    
    valid_count = validation_df['valid'].sum()
    total_count = len(validation_df)
    
    print(f"\n📈 Overall: {valid_count}/{total_count} datasets passed validation")
    print(f"💾 Validation report saved: {validation_file}")
    print(f"📂 Data directory: {output_dir}")
    
    print("\n" + "=" * 80)
    print("🎉 HISTORICAL DATA FETCH COMPLETE!")
    print("=" * 80)
    
    return validation_df

if __name__ == '__main__':
    try:
        results = main()
        sys.exit(0)
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
