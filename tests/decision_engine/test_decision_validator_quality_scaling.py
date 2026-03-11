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


def test_decision_validator_surfaces_policy_sizing_metadata_additively():
    validator = DecisionValidator(config=_base_config())

    context = {
        "market_data": {"close": 100.0},
        "balance": {"USD": 1000.0},
        "price_change": 0.0,
        "volatility": 0.01,
        "portfolio": {},
    }
    ai_response = {"action": "BUY", "confidence": 80, "amount": 0}
    position_sizing_result = {
        "recommended_position_size": 1.0,
        "stop_loss_price": 98.0,
        "sizing_stop_loss_percentage": 0.02,
        "risk_percentage": 0.01,
        "policy_sizing_intent": {
            "semantic_action": "BUY",
            "target_exposure_pct": 100.0,
            "target_delta_pct": 100.0,
            "reduction_fraction": None,
            "sizing_anchor": "quarter_kelly_conservative",
            "provider_agnostic": True,
            "version": 1,
        },
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

    assert decision["action"] == "BUY"
    assert "suggested_amount" in decision
    assert "recommended_position_size" in decision
    assert decision["policy_sizing_intent"]["semantic_action"] == "BUY"
    assert decision["sizing_semantics_version"] == 1
    assert decision["sizing_anchor"] == "quarter_kelly_conservative"
    assert decision["provider_translation_required"] is True
    assert decision["effective_size_basis"] == "usd_notional"


def test_decision_validator_hold_preserves_zero_delta_policy_metadata():
    validator = DecisionValidator(config=_base_config())

    context = {
        "market_data": {"close": 100.0},
        "balance": {"USD": 1000.0},
        "price_change": 0.0,
        "volatility": 0.01,
        "portfolio": {},
    }
    ai_response = {"action": "HOLD", "confidence": 60, "amount": 0}
    position_sizing_result = {
        "recommended_position_size": 0,
        "stop_loss_price": 100.0,
        "sizing_stop_loss_percentage": 0.02,
        "risk_percentage": 0.01,
        "policy_sizing_intent": {
            "semantic_action": "HOLD",
            "target_exposure_pct": None,
            "target_delta_pct": 0.0,
            "reduction_fraction": None,
            "sizing_anchor": "quarter_kelly_conservative",
            "provider_agnostic": True,
            "version": 1,
        },
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

    assert decision["action"] == "HOLD"
    assert decision["suggested_amount"] == 0
    assert decision["policy_sizing_intent"]["target_delta_pct"] == 0.0
    assert decision["provider_translation_required"] is False
    assert decision["effective_size_basis"] == "usd_notional"


def test_decision_validator_preserves_legacy_fields_with_policy_metadata():
    validator = DecisionValidator(config=_base_config())

    context = {
        "market_data": {"close": 1.10},
        "balance": {"USD": 1000.0},
        "price_change": 0.0,
        "volatility": 0.01,
        "portfolio": {},
    }
    ai_response = {"action": "SELL", "confidence": 85, "amount": 0}
    position_sizing_result = {
        "recommended_position_size": 2500.0,
        "stop_loss_price": 1.12,
        "sizing_stop_loss_percentage": 0.02,
        "risk_percentage": 0.01,
        "policy_sizing_intent": {
            "semantic_action": "SELL",
            "target_exposure_pct": 2750.0,
            "target_delta_pct": 2750.0,
            "reduction_fraction": None,
            "sizing_anchor": "quarter_kelly_conservative",
            "provider_agnostic": True,
            "version": 1,
        },
    }

    decision = validator.create_decision(
        asset_pair="EUR_USD",
        context=context,
        ai_response=ai_response,
        position_sizing_result=position_sizing_result,
        relevant_balance={"USD": 1000.0},
        balance_source="test",
        has_existing_position=False,
        is_crypto=False,
        is_forex=True,
    )

    assert decision["action"] == "SELL"
    assert decision["position_type"] == "SHORT"
    assert decision["recommended_position_size"] > 0
    assert decision["recommended_position_size"] < 2500.0
    assert decision["suggested_amount"] == decision["recommended_position_size"]
    assert decision["effective_size_basis"] == "asset_units"
    assert decision["provider_translation_required"] is True


def test_decision_validator_policy_intent_stays_provider_agnostic():
    validator = DecisionValidator(config=_base_config())

    context = {
        "market_data": {"close": 100.0},
        "balance": {"USD": 1000.0},
        "price_change": 0.0,
        "volatility": 0.01,
        "portfolio": {},
    }
    ai_response = {"action": "BUY", "confidence": 80, "amount": 0}
    position_sizing_result = {
        "recommended_position_size": 1.0,
        "stop_loss_price": 98.0,
        "sizing_stop_loss_percentage": 0.02,
        "risk_percentage": 0.01,
        "policy_sizing_intent": {
            "semantic_action": "BUY",
            "target_exposure_pct": 100.0,
            "target_delta_pct": 100.0,
            "reduction_fraction": None,
            "sizing_anchor": "quarter_kelly_conservative",
            "provider_agnostic": True,
            "version": 1,
        },
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

    intent = decision["policy_sizing_intent"]
    assert "suggested_amount" not in intent
    assert "recommended_position_size" not in intent
    assert "units" not in intent
    assert intent["provider_agnostic"] is True
