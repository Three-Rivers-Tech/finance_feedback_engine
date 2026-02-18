from finance_feedback_engine.decision_engine.decision_validator import DecisionValidator


def _base_config():
    return {
        "decision_engine": {
            "portfolio_stop_loss_percentage": 0.02,
            "portfolio_take_profit_percentage": 0.05,
        },
        "agent": {
            "min_confidence_threshold": 0.70,
            "quality_gate_enabled": True,
            "position_size_min_multiplier": 0.50,
            "position_size_full_confidence": 90.0,
            "high_volatility_threshold": 0.04,
            "position_size_high_volatility_scale": 0.75,
            "position_size_extreme_volatility_threshold": 0.07,
            "position_size_extreme_volatility_scale": 0.50,
        },
    }


def test_decision_validator_applies_size_multiplier():
    validator = DecisionValidator(config=_base_config())

    context = {
        "market_data": {"close": 100.0},
        "balance": {"USD": 1000.0},
        "price_change": 0.0,
        "volatility": 0.08,
        "portfolio": {},
    }
    ai_response = {"action": "BUY", "confidence": 72, "amount": 0}
    position_sizing_result = {
        "recommended_position_size": 1.0,
        "stop_loss_price": 98.0,
        "sizing_stop_loss_percentage": 0.02,
        "risk_percentage": 0.01,
    }

    decision = validator.create_decision(
        asset_pair="BTCUSD",
        context=context,
        ai_response=ai_response,
        position_sizing_result=position_sizing_result,
        relevant_balance={"USD": 1000.0},
        balance_source="test",
        has_existing_position=False,
        is_crypto=True,
        is_forex=False,
    )

    assert 0.5 <= decision["position_size_multiplier"] < 1.0
    assert decision["recommended_position_size"] < 1.0
    assert decision["suggested_amount"] < 100.0
