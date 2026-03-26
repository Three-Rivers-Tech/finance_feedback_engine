from unittest.mock import patch

from finance_feedback_engine.risk.gatekeeper import RiskGatekeeper


@patch("finance_feedback_engine.risk.gatekeeper.MarketSchedule")
def test_policy_action_veto_result_passes_for_allowed_action(mock_schedule):
    mock_schedule.get_market_status.return_value = {"is_open": True, "warning": None}
    gatekeeper = RiskGatekeeper()

    decision = {
        "action": "OPEN_SMALL_LONG",
        "asset_pair": "BTCUSD",
        "asset_category": "crypto",
        "volatility": 0.02,
        "confidence": 85,
    }
    context = {
        "asset_type": "crypto",
        "recent_performance": {"total_pnl": -0.01},
        "holdings": {},
    }

    result = gatekeeper.evaluate_policy_action_veto(decision, context)

    assert result["policy_action"] == "OPEN_SMALL_LONG"
    assert result["risk_vetoed"] is False
    assert result["risk_veto_reason"] is None
    assert "approved" in result["gatekeeper_message"].lower()


@patch("finance_feedback_engine.risk.gatekeeper.MarketSchedule")
def test_policy_action_veto_result_surfaces_block_reason(mock_schedule):
    mock_schedule.get_market_status.return_value = {"is_open": True, "warning": None}
    gatekeeper = RiskGatekeeper(max_drawdown_pct=0.05)

    decision = {
        "action": "OPEN_SMALL_LONG",
        "asset_pair": "BTCUSD",
        "asset_category": "crypto",
        "volatility": 0.02,
        "confidence": 85,
    }
    context = {
        "asset_type": "crypto",
        "recent_performance": {"total_pnl": -0.10},
        "holdings": {},
    }

    result = gatekeeper.evaluate_policy_action_veto(decision, context)

    assert result["policy_action"] == "OPEN_SMALL_LONG"
    assert result["risk_vetoed"] is True
    assert result["risk_veto_reason"] is not None
    assert "drawdown" in result["risk_veto_reason"].lower()


def test_policy_action_veto_helper_is_noop_for_legacy_action():
    gatekeeper = RiskGatekeeper()

    result = gatekeeper.evaluate_policy_action_veto(
        {"action": "BUY", "asset_pair": "BTCUSD"},
        {"asset_type": "crypto", "holdings": {}},
    )

    assert result["policy_action"] is None
    assert result["risk_vetoed"] is False
    assert result["risk_veto_reason"] is None



def test_entry_trade_detection_uses_canonical_policy_actions():
    gatekeeper = RiskGatekeeper()

    assert gatekeeper._is_entry_trade_action({"policy_action": "OPEN_SMALL_LONG"}) is True
    assert gatekeeper._is_entry_trade_action({"policy_action": "ADD_SMALL_SHORT"}) is True
    assert gatekeeper._is_entry_trade_action({"policy_action": "CLOSE_SHORT"}) is False
    assert gatekeeper._is_entry_trade_action({"policy_action": "REDUCE_LONG"}) is False
    assert gatekeeper._is_entry_trade_action({"action": "BUY"}) is True
    assert gatekeeper._is_entry_trade_action({"action": "HOLD"}) is False


@patch("finance_feedback_engine.risk.gatekeeper.MarketSchedule")
def test_policy_action_veto_helper_keeps_human_and_machine_messages_aligned_on_rejection(mock_schedule):
    mock_schedule.get_market_status.return_value = {"is_open": True, "warning": None}
    gatekeeper = RiskGatekeeper(max_drawdown_pct=0.05)

    decision = {
        "action": "OPEN_SMALL_LONG",
        "asset_pair": "BTCUSD",
        "asset_category": "crypto",
        "volatility": 0.02,
        "confidence": 85,
    }
    context = {
        "asset_type": "crypto",
        "recent_performance": {"total_pnl": -0.10},
        "holdings": {},
    }

    result = gatekeeper.evaluate_policy_action_veto(decision, context)

    assert result["risk_vetoed"] is True
    assert result["gatekeeper_message"] == result["risk_veto_reason"]
