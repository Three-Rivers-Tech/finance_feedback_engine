import asyncio
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from finance_feedback_engine.backtesting.backtester import Backtester
from finance_feedback_engine.backtesting.monte_carlo import MonteCarloSimulator
from finance_feedback_engine.backtesting.agent_backtester import AgentModeBacktester


class FakeHistoricalProvider:
    def get_historical_data(self, asset_pair, start_date, end_date, timeframe="1h"):
        # Build 20 simple candles with ascending prices
        if isinstance(start_date, str):
            start_dt = datetime.fromisoformat(start_date)
        else:
            start_dt = start_date
        rows = []
        price = 100.0
        for i in range(20):
            ts = start_dt + timedelta(hours=i)
            open_p = price
            close_p = price * (1.0 + 0.001)
            high_p = max(open_p, close_p) * 1.001
            low_p = min(open_p, close_p) * 0.999
            rows.append({
                "date": ts.isoformat(),
                "open": open_p,
                "high": high_p,
                "low": low_p,
                "close": close_p,
                "volume": 1000 + i,
            })
            price = close_p
        df = pd.DataFrame(rows)
        df["timestamp"] = pd.to_datetime(df["date"], utc=True)
        df = df.set_index("timestamp")["open high low close volume".split()].sort_index()
        return df


class FakeDecisionEngine:
    async def generate_decision(self, asset_pair, market_data, balance, portfolio, memory_context, monitoring_context):
        # Minimal BUY decision using market_data
        entry_price = float(market_data.get("close", market_data.get("open", 100)))
        return {
            "id": f"dec-{asset_pair}-{market_data.get('timestamp', 't')}",
            "asset_pair": asset_pair,
            "action": "BUY",
            "suggested_amount": 100.0,
            "entry_price": entry_price,
            "timestamp": datetime.utcnow().isoformat(),
        }


def test_fee_model_maker_vs_taker():
    bt = Backtester(FakeHistoricalProvider(), initial_balance=10000.0)
    taker_fee = bt._calculate_fees(platform="coinbase", size=1000.0, is_maker=False)
    maker_fee = bt._calculate_fees(platform="coinbase", size=1000.0, is_maker=True)
    assert taker_fee > maker_fee


def test_realistic_slippage_tiers():
    bt = Backtester(FakeHistoricalProvider(), initial_balance=10000.0, config={"features": {"enhanced_slippage_model": True}, "backtesting": {"slippage_model": "realistic"}})
    ts = datetime.utcnow()
    s_crypto = bt._calculate_realistic_slippage("BTCUSD", 500, ts)
    s_fx = bt._calculate_realistic_slippage("EURUSD", 500, ts)
    s_exotic = bt._calculate_realistic_slippage("USDMXN", 500, ts)
    assert s_crypto >= s_fx
    assert s_exotic >= s_crypto


def test_monte_carlo_price_path_perturbation():
    bt = Backtester(FakeHistoricalProvider(), initial_balance=10000.0)
    mc = MonteCarloSimulator()
    dec = FakeDecisionEngine()
    results = mc.run_monte_carlo(bt, "BTCUSD", "2024-01-01", "2024-01-10", dec, num_simulations=50, price_noise_std=0.002, seed=42)
    assert results["num_simulations"] == 50
    assert "percentiles" in results
    assert set(results["percentiles"].keys()) == {"p5", "p25", "p50", "p75", "p95"}


def test_agent_ooda_throttling_and_metrics():
    bt = AgentModeBacktester(FakeHistoricalProvider(), initial_balance=10000.0, analysis_frequency_seconds=600, max_daily_trades=2)
    dec = FakeDecisionEngine()
    # Run backtest; ensure ooda metrics present
    results = bt.run_backtest("BTCUSD", "2024-01-01", "2024-01-02", dec)
    assert "ooda_metrics" in results
    metrics = results["ooda_metrics"]
    # Frequency throttling should skip some pulses when analysis_frequency_seconds > 300
    assert metrics["candles_skipped_frequency"] >= 1
