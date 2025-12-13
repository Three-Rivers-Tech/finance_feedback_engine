#!/usr/bin/env python3
"""
Demo script for MockLiveProvider.

Shows how to use MockLiveProvider to simulate live data streaming
for backtesting and strategy development.
"""

import pandas as pd
import numpy as np
from finance_feedback_engine.data_providers import MockLiveProvider


def generate_sample_data(days: int = 100, start_price: float = 50000.0):
    """Generate sample OHLCV data for testing."""
    print(f"\n📊 Generating {days} days of sample data...")

    dates = pd.date_range('2024-01-01', periods=days, freq='D')
    np.random.seed(42)

    # Simulate realistic price movement
    returns = np.random.randn(days) * 0.02  # 2% daily volatility
    close_prices = start_price * np.exp(np.cumsum(returns))

    data = pd.DataFrame({
        'date': dates.strftime('%Y-%m-%d'),
        'open': close_prices * (1 + np.random.randn(days) * 0.005),
        'high': close_prices * (1 + np.abs(np.random.randn(days)) * 0.01),
        'low': close_prices * (1 - np.abs(np.random.randn(days)) * 0.01),
        'close': close_prices,
        'volume': np.random.randint(1000000, 10000000, days),
        'market_cap': np.random.randint(500000000, 1000000000, days)
    })

    print(f"✅ Generated data from {data['date'].iloc[0]} to {data['date'].iloc[-1]}")
    print(f"   Price range: ${data['close'].min():.2f} - ${data['close'].max():.2f}")

    return data


def demo_basic_streaming():
    """Demo 1: Basic streaming functionality."""
    print("\n" + "="*70)
    print("DEMO 1: Basic Data Streaming")
    print("="*70)

    # Create small dataset
    data = pd.DataFrame({
        'open': [100.0, 101.0, 102.0, 103.0, 104.0],
        'high': [105.0, 106.0, 107.0, 108.0, 109.0],
        'low': [98.0, 99.0, 100.0, 101.0, 102.0],
        'close': [102.0, 103.0, 104.0, 105.0, 106.0],
    })

    provider = MockLiveProvider(data, asset_pair='BTCUSD')

    print("\n📈 Streaming 5 candles for BTCUSD...")
    print(f"   Starting at index: {provider.current_index}")

    candle_num = 1
    while provider.has_more_data():
        price = provider.get_current_price()
        progress = provider.get_progress()

        print(f"   Candle {candle_num}: ${price:.2f} (Progress: {progress['progress_pct']:.0f}%)")

        provider.advance()
        candle_num += 1

    # Final candle
    price = provider.get_current_price()
    print(f"   Candle {candle_num}: ${price:.2f} (Progress: 100%)")
    print(f"\n✅ Streamed {len(provider)} candles successfully")


def demo_comprehensive_data():
    """Demo 2: Comprehensive market data with enrichments."""
    print("\n" + "="*70)
    print("DEMO 2: Comprehensive Market Data")
    print("="*70)

    data = generate_sample_data(days=10)
    provider = MockLiveProvider(data, asset_pair='BTCUSD')

    print("\n📊 Fetching comprehensive market data...")

    # Advance a few candles
    for _ in range(3):
        provider.advance()

    # Get comprehensive data (async, so we'll use synchronous version for demo)
    candle = provider.get_current_candle()

    print(f"\n   Current Candle (Index {provider.current_index}):")
    print(f"   ├─ Date: {candle.get('date', 'N/A')}")
    print(f"   ├─ Open: ${candle['open']:.2f}")
    print(f"   ├─ High: ${candle['high']:.2f}")
    print(f"   ├─ Low: ${candle['low']:.2f}")
    print(f"   ├─ Close: ${candle['close']:.2f}")
    print(f"   ├─ Volume: {candle.get('volume', 0):,}")

    # Calculate enrichments manually
    price_range = candle['high'] - candle['low']
    body_size = abs(candle['close'] - candle['open'])
    is_bullish = candle['close'] > candle['open']

    print("\n   Enrichments:")
    print(f"   ├─ Price Range: ${price_range:.2f} ({price_range/candle['close']*100:.2f}%)")
    print(f"   ├─ Body Size: ${body_size:.2f}")
    print(f"   ├─ Trend: {'Bullish ↑' if is_bullish else 'Bearish ↓'}")
    print(f"   └─ Upper Wick: ${candle['high'] - max(candle['open'], candle['close']):.2f}")


def demo_historical_windows():
    """Demo 3: Historical windows for indicators."""
    print("\n" + "="*70)
    print("DEMO 3: Historical Windows & Moving Averages")
    print("="*70)

    data = generate_sample_data(days=50)
    provider = MockLiveProvider(data, asset_pair='BTCUSD')

    # Advance to middle of data
    for _ in range(30):
        provider.advance()

    print(f"\n📈 Calculating moving averages at index {provider.current_index}...")

    # Get windows of different sizes
    windows = {
        'MA-5': 5,
        'MA-10': 10,
        'MA-20': 20
    }

    current_price = provider.get_current_price()
    print(f"\n   Current Price: ${current_price:.2f}")
    print("\n   Moving Averages:")

    for name, size in windows.items():
        window = provider.get_historical_window(
            window_size=size,
            include_current=False  # Look-back only
        )
        ma = window['close'].mean()
        diff_pct = (current_price - ma) / ma * 100

        print(f"   ├─ {name}: ${ma:.2f} ({diff_pct:+.2f}%)")

    # Peek ahead (for demo purposes only!)
    print("\n   🔮 Peek Ahead (testing only):")
    for i in range(1, 4):
        future = provider.peek_ahead(i)
        if future:
            print(f"   ├─ +{i} candle: ${future['close']:.2f}")


def demo_simple_backtest():
    """Demo 4: Simple moving average strategy simulation (simplified)."""
    print("\n" + "="*70)
    print("DEMO 4: Simple MA Strategy Simulation")
    print("="*70)

    data = generate_sample_data(days=100, start_price=50000.0)
    provider = MockLiveProvider(data, asset_pair='BTCUSD')

    print("\n💼 Simulating strategy...")
    print("   Strategy: MA(20) Crossover (Signal-Only)")

    # Simplified tracking without actual platform trading
    cash = 10000.0
    btc_holdings = 0.0
    ma_period = 20
    signals = []

    # Warm up period
    for _ in range(ma_period):
        provider.advance()

    print(f"\n   📊 Generating signals ({len(data) - ma_period} candles)...\n")

    while provider.has_more_data():
        # Calculate MA
        window = provider.get_historical_window(
            window_size=ma_period,
            include_current=False
        )
        ma = window['close'].mean()

        current_price = provider.get_current_price()
        current_date = provider.get_current_candle().get('date', f'Index {provider.current_index}')

        # Simple signal logic
        if current_price > ma and btc_holdings == 0:
            # Buy signal
            btc_to_buy = cash / current_price
            btc_holdings = btc_to_buy
            cash = 0
            signals.append({
                'action': 'BUY',
                'price': current_price,
                'date': current_date
            })
            print(f"   🟢 BUY  @ ${current_price:.2f} ({btc_to_buy:.4f} BTC) on {current_date}")

        elif current_price < ma and btc_holdings > 0:
            # Sell signal
            cash = btc_holdings * current_price
            btc_holdings = 0
            signals.append({
                'action': 'SELL',
                'price': current_price,
                'date': current_date
            })
            print(f"   🔴 SELL @ ${current_price:.2f} (cash: ${cash:.2f}) on {current_date}")

        provider.advance()

    # Calculate final portfolio value
    final_price = provider.get_current_price()
    final_value = cash + (btc_holdings * final_price)
    total_return = (final_value - 10000.0) / 10000.0 * 100

    print("\n   📈 Strategy Results:")
    print(f"   ├─ Total Signals: {len(signals)}")
    print(f"   ├─ Buy Signals: {sum(1 for s in signals if s['action'] == 'BUY')}")
    print(f"   ├─ Sell Signals: {sum(1 for s in signals if s['action'] == 'SELL')}")
    print("   ├─ Initial Value: $10000.00")
    print(f"   ├─ Final Value: ${final_value:.2f}")
    print(f"   └─ Total Return: {total_return:+.2f}%")
    print("\n   Note: This is a simplified simulation showing MockLiveProvider functionality.")
    print("   For full backtesting, combine with MockTradingPlatform properly.")


def demo_reset_replay():
    """Demo 5: Reset and replay functionality."""
    print("\n" + "="*70)
    print("DEMO 5: Reset & Replay")
    print("="*70)

    data = pd.DataFrame({
        'open': [100.0, 101.0, 102.0, 103.0, 104.0],
        'high': [105.0, 106.0, 107.0, 108.0, 109.0],
        'low': [98.0, 99.0, 100.0, 101.0, 102.0],
        'close': [102.0, 103.0, 104.0, 105.0, 106.0],
    })

    provider = MockLiveProvider(data, asset_pair='BTCUSD')

    print("\n🔄 First pass:")
    prices_1 = []
    while provider.has_more_data():
        prices_1.append(provider.get_current_price())
        provider.advance()
    prices_1.append(provider.get_current_price())

    print(f"   Collected {len(prices_1)} prices: {prices_1}")

    # Reset to beginning
    print("\n🔄 Reset to beginning...")
    provider.reset(0)

    print("\n🔄 Second pass:")
    prices_2 = []
    while provider.has_more_data():
        prices_2.append(provider.get_current_price())
        provider.advance()
    prices_2.append(provider.get_current_price())

    print(f"   Collected {len(prices_2)} prices: {prices_2}")

    # Verify identical
    if prices_1 == prices_2:
        print("\n✅ Both passes produced identical results!")

    # Reset to middle
    print("\n🔄 Reset to index 2 (middle)...")
    provider.reset(2)

    print("\n🔄 Third pass (from middle):")
    prices_3 = []
    while provider.has_more_data():
        prices_3.append(provider.get_current_price())
        provider.advance()
    prices_3.append(provider.get_current_price())

    print(f"   Collected {len(prices_3)} prices: {prices_3}")
    print("   (Started from index 2, got last 3 candles)")


def main():
    """Run all demos."""
    print("\n" + "="*70)
    print("MockLiveProvider Demo Suite")
    print("="*70)
    print("\nThis demo shows MockLiveProvider capabilities for backtesting:")
    print("  1. Basic streaming")
    print("  2. Comprehensive market data")
    print("  3. Historical windows")
    print("  4. Simple backtest")
    print("  5. Reset & replay")

    try:
        demo_basic_streaming()
        demo_comprehensive_data()
        demo_historical_windows()
        demo_simple_backtest()
        demo_reset_replay()

        print("\n" + "="*70)
        print("✅ All demos completed successfully!")
        print("="*70)
        print("\nNext Steps:")
        print("  • See docs/MOCK_LIVE_PROVIDER_GUIDE.md for full documentation")
        print("  • Combine with MockTradingPlatform for full simulations")
        print("  • Use in backtesting workflows to avoid look-ahead bias")
        print("="*70 + "\n")

    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        raise


if __name__ == '__main__':
    main()
