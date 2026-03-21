"""
TDD tests for position-awareness prompt improvements.

Two changes under test:
1. format_for_ai_prompt() includes POSITION AWARENESS DIRECTIVES when positions exist,
   and directives appear BEFORE the data block (lost-in-the-middle mitigation)
2. Hard code enforcement: slot-consuming entry actions are blocked when slots_available == 0
"""

import pytest
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_context(futures=None, slots_available=2, active_trades=0, pnl=-18.0):
    futures = futures or []
    return {
        "has_monitoring_data": True,
        "active_positions": {"futures": futures, "spot": []},
        "active_trades_count": active_trades,
        "max_concurrent_trades": 2,
        "slots_available": slots_available,
        "risk_metrics": {
            "total_exposure_usd": 7736.0,
            "unrealized_pnl": pnl,
            "leverage_estimate": 10.05,
            "net_exposure": 7736.0,
        },
        "position_concentration": {"num_positions": 0},
        "recent_performance": {},
        "multi_timeframe_pulse": None,
    }


def make_eth_position(pnl=-18.0):
    return {
        "product_id": "ETP-20DEC30-CDE",
        "side": "LONG",
        "number_of_contracts": "4",
        "avg_entry_price": "1983.25",
        "current_price": "1949.00",
        "unrealized_pnl": str(pnl),
    }


def get_provider():
    from finance_feedback_engine.monitoring.context_provider import MonitoringContextProvider
    return MonitoringContextProvider(platform=MagicMock(), trade_monitor=None)


# ---------------------------------------------------------------------------
# Change 1: format_for_ai_prompt — directives block
# ---------------------------------------------------------------------------

class TestPositionAwarenessDirectives:

    def test_directives_present_when_positions_exist(self):
        provider = get_provider()
        ctx = make_context(futures=[make_eth_position()], slots_available=1, active_trades=1)
        result = provider.format_for_ai_prompt(ctx)
        assert "POSITION AWARENESS DIRECTIVES" in result

    def test_directives_absent_when_no_positions(self):
        provider = get_provider()
        ctx = make_context(futures=[], slots_available=2, active_trades=0)
        result = provider.format_for_ai_prompt(ctx)
        assert "POSITION AWARENESS DIRECTIVES" not in result

    def test_directives_absent_when_no_monitoring_data(self):
        provider = get_provider()
        result = provider.format_for_ai_prompt({"has_monitoring_data": False})
        assert "POSITION AWARENESS DIRECTIVES" not in result
        assert "No active trading positions" in result

    def test_no_buy_directive_when_slots_zero(self):
        provider = get_provider()
        ctx = make_context(futures=[make_eth_position(), make_eth_position()],
                           slots_available=0, active_trades=2)
        result = provider.format_for_ai_prompt(ctx)
        assert "do NOT recommend OPEN_*" in result

    def test_directive_defines_hold_sell_buy(self):
        provider = get_provider()
        ctx = make_context(futures=[make_eth_position()], slots_available=1, active_trades=1)
        result = provider.format_for_ai_prompt(ctx)
        assert "HOLD" in result and "OPEN_*" in result and "REDUCE_* / CLOSE_*" in result

    def test_directive_mentions_confidence_and_risk(self):
        provider = get_provider()
        ctx = make_context(futures=[make_eth_position()], slots_available=1, active_trades=1)
        result = provider.format_for_ai_prompt(ctx)
        assert "confidence" in result.lower()

    def test_directives_appear_before_position_data(self):
        """Critical: directives must precede data (lost-in-the-middle mitigation)."""
        provider = get_provider()
        ctx = make_context(futures=[make_eth_position()], slots_available=1, active_trades=1)
        result = provider.format_for_ai_prompt(ctx)
        directive_idx = result.find("POSITION AWARENESS DIRECTIVES")
        data_idx = result.find("Active Positions")
        assert directive_idx != -1, "Directives block missing"
        assert data_idx != -1, "Active Positions data missing"
        assert directive_idx < data_idx, \
            "Directives must appear BEFORE position data to avoid lost-in-the-middle"


# ---------------------------------------------------------------------------
# Change 2: enforce_slot_constraints — block slot-consuming entry actions
# ---------------------------------------------------------------------------

class TestHardSlotEnforcement:

    def test_buy_blocked_when_slots_zero(self):
        from finance_feedback_engine.monitoring.context_provider import enforce_slot_constraints
        decision = {"action": "BUY", "confidence": 75, "asset_pair": "ETHUSD"}
        ctx = make_context(futures=[make_eth_position(), make_eth_position()],
                           slots_available=0, active_trades=2)
        result = enforce_slot_constraints(decision, ctx)
        assert result["action"] == "HOLD"
        assert result["policy_action"] == "HOLD"

    def test_buy_blocked_result_has_reason(self):
        from finance_feedback_engine.monitoring.context_provider import enforce_slot_constraints
        decision = {"action": "BUY", "confidence": 75, "asset_pair": "ETHUSD"}
        ctx = make_context(slots_available=0)
        result = enforce_slot_constraints(decision, ctx)
        assert "override_reason" in result or "quality_flag" in result

    def test_buy_allowed_when_slots_available(self):
        from finance_feedback_engine.monitoring.context_provider import enforce_slot_constraints
        decision = {"action": "BUY", "confidence": 75, "asset_pair": "ETHUSD"}
        ctx = make_context(futures=[make_eth_position()], slots_available=1)
        result = enforce_slot_constraints(decision, ctx)
        assert result["action"] == "BUY"

    def test_hold_unaffected(self):
        from finance_feedback_engine.monitoring.context_provider import enforce_slot_constraints
        decision = {"action": "HOLD", "confidence": 60, "asset_pair": "ETHUSD"}
        result = enforce_slot_constraints(decision, make_context(slots_available=0))
        assert result["action"] == "HOLD"

    def test_sell_unaffected(self):
        from finance_feedback_engine.monitoring.context_provider import enforce_slot_constraints
        decision = {"action": "SELL", "confidence": 70, "asset_pair": "ETHUSD"}
        result = enforce_slot_constraints(decision, make_context(slots_available=0))
        assert result["action"] == "SELL"

    def test_none_context_passes_through(self):
        from finance_feedback_engine.monitoring.context_provider import enforce_slot_constraints
        decision = {"action": "BUY", "confidence": 75, "asset_pair": "ETHUSD"}
        result = enforce_slot_constraints(decision, None)
        assert result["action"] == "BUY"

    def test_empty_context_passes_through(self):
        from finance_feedback_engine.monitoring.context_provider import enforce_slot_constraints
        decision = {"action": "BUY", "confidence": 75, "asset_pair": "ETHUSD"}
        result = enforce_slot_constraints(decision, {})
        assert result["action"] == "BUY"


    def test_open_policy_action_blocked_when_slots_zero(self):
        from finance_feedback_engine.monitoring.context_provider import enforce_slot_constraints
        decision = {"policy_action": "OPEN_SMALL_LONG", "action": "OPEN_SMALL_LONG", "confidence": 75, "asset_pair": "ETHUSD"}
        result = enforce_slot_constraints(decision, make_context(slots_available=0))
        assert result["action"] == "HOLD"
        assert result["policy_action"] == "HOLD"

    def test_reduce_policy_action_allowed_when_slots_zero(self):
        from finance_feedback_engine.monitoring.context_provider import enforce_slot_constraints
        decision = {"policy_action": "REDUCE_LONG", "action": "REDUCE_LONG", "confidence": 75, "asset_pair": "ETHUSD"}
        result = enforce_slot_constraints(decision, make_context(slots_available=0))
        assert result["action"] == "REDUCE_LONG"
        assert result["policy_action"] == "REDUCE_LONG"
