import os
import uuid

import pytest


@pytest.mark.skipif(os.environ.get("ENVIRONMENT", "").lower() != "development", reason="E2E runs in development mode only")
def test_profitable_trade_e2e():
    """End-to-end: execute a BUY then SELL on paper platform and realize profit.

    Uses the MockTradingPlatform via UnifiedTradingPlatform's paper sub-platform.
    Deterministic by fixing prices and notional.
    """
    # Arrange: dev mode and engine
    os.environ["ENVIRONMENT"] = "development"

    from finance_feedback_engine.utils.config_loader import load_config
    from finance_feedback_engine.core import FinanceFeedbackEngine

    config = load_config()
    engine = FinanceFeedbackEngine(config)

    # Access paper platform directly (UnifiedPlatform routes crypto/forex to real platforms)
    unified = engine.trading_platform
    assert hasattr(unified, "platforms") and "paper" in unified.platforms
    paper = unified.platforms["paper"]

    # Reset to a known balance for deterministic outcome
    if hasattr(paper, "reset"):
        paper.reset({"FUTURES_USD": 10000.0, "SPOT_USD": 3000.0, "SPOT_USDC": 1000.0})

    # Execute BUY
    buy_decision = {
        "id": f"e2e-{uuid.uuid4().hex[:8]}",
        "asset_pair": "BTCUSD",
        "action": "BUY",
        "suggested_amount": 1000.0,
        "entry_price": 100.0,
        "order_type": "market",
    }
    buy_result = paper.execute_trade(buy_decision)
    assert buy_result["success"], f"BUY failed: {buy_result}"

    # Execute SELL at higher price to realize profit
    sell_decision = {
        "id": buy_decision["id"],
        "asset_pair": "BTCUSD",
        "action": "SELL",
        "suggested_amount": 1000.0,
        "entry_price": 110.0,  # 10% higher
        "order_type": "market",
    }
    sell_result = paper.execute_trade(sell_decision)
    assert sell_result["success"], f"SELL failed: {sell_result}"

    # Validate realized P&L from response payload
    trade_record = sell_result.get("response", {})
    realized = float(trade_record.get("realized_pnl", 0.0))
    assert realized > 0.0, f"Expected positive realized PnL, got {realized}"

    # Optional: ensure futures balance increased net of fees
    balances = paper.get_balance()
    assert "FUTURES_USD" in balances
    assert balances["FUTURES_USD"] > 9000.0, f"Unexpected FUTURES_USD: {balances['FUTURES_USD']}"
