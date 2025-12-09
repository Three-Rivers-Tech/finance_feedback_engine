import datetime

import pandas as pd
import pytest

from finance_feedback_engine.backtesting import backtester as backtester_module
from finance_feedback_engine.backtesting.backtester import Backtester
from finance_feedback_engine.data_providers.historical_data_provider import HistoricalDataProvider
from finance_feedback_engine.decision_engine.engine import DecisionEngine
from finance_feedback_engine.monitoring.trade_monitor import TradeMonitor
from finance_feedback_engine.utils.validation import standardize_asset_pair
import finance_feedback_engine.monitoring.trade_monitor as trade_monitor_module
import finance_feedback_engine.risk.gatekeeper as gatekeeper_module


def test_risk_gatekeeper_blocks_after_drawdown(monkeypatch):
    # Simulate historical data with a 10% crash after first candle
    asset_pair = standardize_asset_pair('BTCUSD')
    initial_balance = 10000.0
    stop_loss_pct = 0.10  # 10% drawdown limit
    start_date = datetime.datetime(2025, 1, 1)
    end_date = datetime.datetime(2025, 1, 3)

    # Create mock historical data: price drops 10% after first candle
    data = pd.DataFrame([
        {"timestamp": start_date, "open": 10000, "high": 10000, "low": 10000, "close": 10000, "volume": 1000, "market_cap": 0},
        {"timestamp": start_date + datetime.timedelta(days=1), "open": 9000, "high": 9000, "low": 9000, "close": 9000, "volume": 1000, "market_cap": 0},
        {"timestamp": start_date + datetime.timedelta(days=2), "open": 8900, "high": 8900, "low": 8900, "close": 8900, "volume": 1000, "market_cap": 0},
    ])

    class SimpleHistoricalProvider(HistoricalDataProvider):
        def __init__(self):
            # Override to skip api_key requirement in base class for this test
            self.api_key = "test"

        def get_historical_data(self, asset_pair, start_date, end_date):
            return data

    class AlwaysBuyDecisionEngine(DecisionEngine):
        def __init__(self):
            super().__init__({}, backtest_mode=True)

        def generate_decision(self, asset_pair: str, market_data, balance, portfolio=None, memory_context=None, monitoring_context=None):
            return {
                "id": f"buy-{market_data['close']}",
                "asset_pair": asset_pair,
                "action": "BUY",
                "suggested_amount": 1000,
                "entry_price": market_data["close"],
                "confidence": 100
            }

    class PatchedTradeMonitor(TradeMonitor):
        def __init__(self, trading_platform=None, platform=None, *args, **kwargs):
            kwargs.pop("config", None)
            super().__init__(platform or trading_platform, *args, **kwargs)

    monkeypatch.setattr(trade_monitor_module, "TradeMonitor", PatchedTradeMonitor)

    call_count = {"calls": 0}

    def fake_validate_trade(self, decision, context):
        call_count["calls"] += 1
        # Allow first trade, block subsequent trades simulating drawdown breach
        if call_count["calls"] > 1:
            return False, "Max drawdown exceeded"
        return True, "ok"

    monkeypatch.setattr(gatekeeper_module.RiskGatekeeper, "validate_trade", fake_validate_trade)

    backtester = Backtester(
        historical_data_provider=SimpleHistoricalProvider(),
        initial_balance=initial_balance,
        stop_loss_percentage=stop_loss_pct,
        enable_risk_gatekeeper=True
    )

    results = backtester.run_backtest(
        asset_pair=asset_pair,
        start_date=start_date,
        end_date=end_date,
        decision_engine=AlwaysBuyDecisionEngine()
    )

    trades = results["trades"]
    # After the first trade, the drawdown should trigger and block further trades
    # Look for trades with success=False or error mentioning drawdown
    blocked = [t for t in trades if not t.get("success", True) and ("drawdown" in t.get("error", "") or "REJECTED" in t.get("error", ""))]
    # There should be at least one blocked trade after the crash
    assert blocked or len(trades) == 1, "RiskGatekeeper did not block trades after drawdown"
