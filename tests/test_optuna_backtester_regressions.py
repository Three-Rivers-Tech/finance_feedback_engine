from unittest.mock import Mock

from finance_feedback_engine.backtesting.backtester import Backtester
from finance_feedback_engine.decision_engine.engine import DecisionEngine
from finance_feedback_engine.decision_engine.market_analysis import MarketAnalysisContext


def test_semantic_memory_formatter_accepts_vector_store_tuples():
    semantic_memory = [
        (
            "rec-1",
            0.93,
            {
                "asset_pair": "BTCUSD",
                "action": "BUY",
                "outcome": "WIN",
                "confidence": 81,
                "reasoning": "Momentum continuation",
            },
        )
    ]

    decision_text = DecisionEngine._format_semantic_memory(Mock(), semantic_memory)
    analyzer_text = MarketAnalysisContext._format_semantic_memory(Mock(), semantic_memory)

    assert "Pattern #1: BTCUSD | Action: BUY | Outcome: WIN" in decision_text
    assert "Pattern #1: BTCUSD | Action: BUY | Outcome: WIN" in analyzer_text


def test_backtester_get_portfolio_breakdown_delegates_to_platform():
    provider = Mock()
    platform = Mock()
    platform.get_portfolio_breakdown.return_value = {
        "holdings": [{"symbol": "BTC", "value_usd": 1234.0}],
        "total_value_usd": 1234.0,
    }

    backtester = Backtester(historical_data_provider=provider, platform=platform)

    breakdown = backtester.get_portfolio_breakdown()

    assert breakdown["total_value_usd"] == 1234.0
    platform.get_portfolio_breakdown.assert_called_once()


import asyncio
from datetime import UTC, datetime, timedelta
from finance_feedback_engine.decision_engine.market_analysis import MarketAnalysisContext


class _ScheduleStub:
    def get_market_status(self, asset_pair, asset_type):
        return {"is_open": False, "session": "Closed"}


def test_market_analysis_infers_forex_asset_type_for_freshness_when_missing():
    analyzer = MarketAnalysisContext.__new__(MarketAnalysisContext)
    analyzer.market_schedule = _ScheduleStub()
    analyzer._calculate_price_change = lambda market_data: 0.0
    analyzer._calculate_volatility = lambda market_data: 0.0

    async def _detect(asset_pair):
        return "LOW_VOLATILITY_RANGING"

    analyzer._detect_market_regime = _detect

    stale_forex_ts = (datetime.now(UTC) - timedelta(hours=20)).isoformat()
    market_data = {"timestamp": stale_forex_ts}

    context = asyncio.run(
        analyzer.create_decision_context(
            asset_pair="EURUSD",
            market_data=market_data,
            balance={},
            portfolio={},
            memory_context={},
            monitoring_context={},
        )
    )

    assert context["market_status"]["session"] == "Closed"
    assert context["data_freshness"]["is_fresh"] is True

