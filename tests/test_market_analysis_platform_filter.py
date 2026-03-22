import pytest

from finance_feedback_engine.decision_engine.market_analysis import MarketAnalysisContext


def _history(start, step, days=40):
    return [
        {"date": f"2024-01-{i+1:02d}", "price": start + i * step}
        for i in range(days)
    ]


@pytest.mark.asyncio
async def test_risk_context_ignores_disabled_oanda_inputs_in_coinbase_only_runtime():
    mac = MarketAnalysisContext({"enabled_platforms": ["coinbase_advanced"]})
    portfolio = {
        "total_value_usd": 50000.0,
        "coinbase_holdings": {"BTCUSD": {"quantity": 1.0, "current_price": 50000.0}},
        "coinbase_price_history": {"BTCUSD": _history(40000, 100)},
        # stale dual-platform payload that should be ignored when Oanda is disabled
        "oanda_holdings": {"EUR_USD": {"units": 1000.0}},
        "oanda_price_history": {"EUR_USD": _history(1.05, 0.001)},
    }
    market_data = {
        "open": 50000.0,
        "close": 50500.0,
        "high": 51000.0,
        "low": 49500.0,
        "asset_type": "crypto",
        "date": "2026-03-22T13:00:00Z",
    }

    context = await mac.create_decision_context(
        asset_pair="BTCUSD",
        market_data=market_data,
        balance={"FUTURES_USD": 1000.0},
        portfolio=portfolio,
    )

    assert context["var_snapshot"]["portfolio_value"] > 0
    assert "Coinbase" in context["correlation_summary"]
    assert "Oanda" not in context["correlation_summary"]
    assert "Cross-Platform" not in context["correlation_summary"]
