from finance_feedback_engine.decision_engine.engine import DecisionEngine


def _make_engine():
    return DecisionEngine(config={"decision_engine": {"signal_only_default": False}}, data_provider=object())



def test_extract_canonical_policy_state_for_flat_position():
    engine = _make_engine()
    context = {"monitoring_context": {"active_positions": {"futures": []}}}

    result = engine._extract_canonical_policy_state(context, "BTCUSD")

    assert result["position_state"] == "flat"
    assert result["unrealized_pnl"] == 0.0
    assert result["current_price"] == 0
    assert result["version"] == 1



def test_extract_canonical_policy_state_for_long_position():
    engine = _make_engine()
    context = {
        "monitoring_context": {
            "active_positions": {
                "futures": [
                    {
                        "product_id": "BTCUSD",
                        "side": "LONG",
                        "contracts": 2,
                        "entry_price": 105000,
                        "unrealized_pnl": 123.45,
                    }
                ]
            }
        }
    }

    result = engine._extract_canonical_policy_state(context, "BTCUSD")

    assert result["position_state"] == "long"
    assert result["current_price"] == 105000.0
    assert result["unrealized_pnl"] == 123.45



def test_extract_canonical_policy_state_gracefully_handles_unknown_position_side():
    engine = _make_engine()
    context = {
        "monitoring_context": {
            "active_positions": {
                "futures": [
                    {
                        "product_id": "BTCUSD",
                        "side": "UNKNOWN",
                        "contracts": 1,
                        "entry_price": 100000,
                        "unrealized_pnl": 0.0,
                    }
                ]
            }
        }
    }

    result = engine._extract_canonical_policy_state(context, "BTCUSD")

    assert result["position_state"] is None
    assert result["current_price"] == 100000.0
    assert result["unrealized_pnl"] == 0.0



def test_extract_canonical_policy_state_for_short_position():
    engine = _make_engine()
    context = {
        "monitoring_context": {
            "active_positions": {
                "futures": [
                    {
                        "product_id": "BTCUSD",
                        "side": "SHORT",
                        "contracts": 3,
                        "entry_price": 99000,
                        "unrealized_pnl": -45.0,
                    }
                ]
            }
        }
    }

    result = engine._extract_canonical_policy_state(context, "BTCUSD")

    assert result["position_state"] == "short"
    assert result["current_price"] == 99000.0
    assert result["unrealized_pnl"] == -45.0
