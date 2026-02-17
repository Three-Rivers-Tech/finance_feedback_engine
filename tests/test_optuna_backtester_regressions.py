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
