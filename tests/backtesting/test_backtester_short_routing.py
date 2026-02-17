from datetime import datetime

import pandas as pd

from finance_feedback_engine.backtesting.backtester import Backtester


class _DecisionEngineShort:
    async def generate_decision(self, **kwargs):
        return {"id": "d1", "action": "SHORT", "position_size": 100.0}


class _FakeProvider:
    def __init__(self, historical_data, asset_pair, start_index=0):
        self.current_index = 0
        self._done = False

    def initialize_pulse_mode(self, base_timeframe="1h"):
        return None

    def advance_pulse(self):
        if self._done:
            return False
        self._done = True
        self.current_index = 1
        return True

    async def get_pulse_data(self):
        return {}

    async def get_comprehensive_market_data(self, asset_pair, include_sentiment=True):
        return {
            "current_price": 100.0,
            "timeframes": {"1h": {"candles": [{"close": 100.0}]}}
        }


class _FakePlatform:
    last_action = None

    def __init__(self, initial_balance, slippage_config):
        self._balance = {"FUTURES_USD": list(initial_balance.values())[0]}
        self._trades = []

    def get_balance(self):
        return self._balance

    def execute_trade(self, decision):
        self.__class__.last_action = decision.get("action")
        self._trades.append({"success": True, "pnl_value": 0.0, "fee": 0.0})
        return {"success": True}

    def get_trade_history(self):
        return self._trades


class _FakeAgent:
    def __init__(self, config, engine, trade_monitor, trading_platform, **kwargs):
        self.engine = engine
        self.is_running = True

    async def process_cycle(self):
        decision = await self.engine.analyze_asset("BTC-USD")
        if decision and decision.get("action") != "HOLD":
            self.engine.execute_decision(decision["id"])
        return True


def _build_data():
    idx = pd.date_range("2025-01-01", periods=2, freq="H")
    return pd.DataFrame(
        {
            "open": [100.0, 100.0],
            "high": [101.0, 101.0],
            "low": [99.0, 99.0],
            "close": [100.0, 100.0],
            "volume": [1000.0, 1000.0],
        },
        index=idx,
    )


def test_short_signal_routes_to_sell_when_allowed(monkeypatch):
    from finance_feedback_engine.agent import trading_loop_agent
    from finance_feedback_engine.data_providers import mock_live_provider
    from finance_feedback_engine.trading_platforms import mock_platform

    monkeypatch.setattr(trading_loop_agent, "TradingLoopAgent", _FakeAgent)
    monkeypatch.setattr(mock_live_provider, "MockLiveProvider", _FakeProvider)
    monkeypatch.setattr(mock_platform, "MockTradingPlatform", _FakePlatform)

    bt = Backtester(historical_data_provider=None, initial_balance=1000.0)

    bt.run_backtest(
        "BTCUSD",
        datetime(2025, 1, 1),
        datetime(2025, 1, 2),
        _DecisionEngineShort(),
        data_override=_build_data(),
        allow_shorts=True,
    )

    assert _FakePlatform.last_action == "SELL"


def test_short_signal_blocked_when_not_allowed(monkeypatch):
    from finance_feedback_engine.agent import trading_loop_agent
    from finance_feedback_engine.data_providers import mock_live_provider
    from finance_feedback_engine.trading_platforms import mock_platform

    monkeypatch.setattr(trading_loop_agent, "TradingLoopAgent", _FakeAgent)
    monkeypatch.setattr(mock_live_provider, "MockLiveProvider", _FakeProvider)
    monkeypatch.setattr(mock_platform, "MockTradingPlatform", _FakePlatform)

    _FakePlatform.last_action = None

    bt = Backtester(historical_data_provider=None, initial_balance=1000.0)

    bt.run_backtest(
        "BTCUSD",
        datetime(2025, 1, 1),
        datetime(2025, 1, 2),
        _DecisionEngineShort(),
        data_override=_build_data(),
        allow_shorts=False,
    )

    assert _FakePlatform.last_action is None
