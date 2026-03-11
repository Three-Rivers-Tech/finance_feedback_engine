from finance_feedback_engine.decision_engine.decision_validator import DecisionValidator
from finance_feedback_engine.decision_engine.position_sizing import PositionSizingCalculator, ProviderTranslationResult


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


def test_provider_translation_result_scaffold_is_additive_and_provider_neutral():
    calculator = PositionSizingCalculator(config=_base_config())
    intent = {
        "semantic_action": "BUY",
        "target_exposure_pct": 100.0,
        "target_delta_pct": 100.0,
        "reduction_fraction": None,
        "sizing_anchor": "quarter_kelly_conservative",
        "provider_agnostic": True,
        "version": 1,
    }

    result = calculator.build_provider_translation_result(
        provider="Coinbase",
        policy_sizing_intent=intent,
        translated_size=100.0,
        effective_exposure_pct=100.0,
        semantic_drift_detected=False,
        translation_notes="stage2 scaffold",
    )

    typed = ProviderTranslationResult(**result)
    assert typed.provider == "coinbase"
    assert typed.policy_sizing_intent["provider_agnostic"] is True
    assert typed.translated_size == 100.0
    assert typed.effective_exposure_pct == 100.0
    assert typed.semantic_drift_detected is False


def test_decision_validator_surfaces_provider_translation_result_additively():
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
        "provider_translation_result": {
            "provider": "coinbase",
            "policy_sizing_intent": {
                "semantic_action": "BUY",
                "target_exposure_pct": 100.0,
                "target_delta_pct": 100.0,
                "reduction_fraction": None,
                "sizing_anchor": "quarter_kelly_conservative",
                "provider_agnostic": True,
                "version": 1,
            },
            "translated_size": 100.0,
            "effective_exposure_pct": 100.0,
            "semantic_drift_detected": False,
            "translation_notes": "stage2 scaffold",
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
    assert decision["policy_sizing_intent"]["provider_agnostic"] is True
    assert decision["provider_translation_result"]["provider"] == "coinbase"
    assert decision["provider_translation_result"]["translated_size"] == 100.0
    assert decision["provider_translation_result"]["semantic_drift_detected"] is False


def test_decision_validator_surfaces_flat_translation_metadata_fields():
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
        "provider_translation_result": {
            "provider": "oanda",
            "policy_sizing_intent": {
                "semantic_action": "BUY",
                "target_exposure_pct": 100.0,
                "target_delta_pct": 100.0,
                "reduction_fraction": None,
                "sizing_anchor": "quarter_kelly_conservative",
                "provider_agnostic": True,
                "version": 1,
            },
            "translated_size": 1000,
            "effective_exposure_pct": 95.0,
            "semantic_drift_detected": True,
            "translation_notes": "oanda_integer_unit_translation",
            "version": 1,
        },
    }

    decision = validator.create_decision(
        asset_pair="EURUSD",
        context=context,
        ai_response=ai_response,
        position_sizing_result=position_sizing_result,
        relevant_balance={"USD": 1000.0},
        balance_source="test",
        has_existing_position=False,
        is_crypto=False,
        is_forex=True,
    )

    assert decision["translation_provider"] == "oanda"
    assert decision["translated_size"] == 1000
    assert decision["translated_effective_exposure_pct"] == 95.0
    assert decision["semantic_drift_detected"] is True
    assert decision["translation_notes"] == "oanda_integer_unit_translation"


def test_decision_validator_defaults_translation_fields_when_missing():
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

    assert decision["provider_translation_result"] is None
    assert decision["translation_provider"] is None
    assert decision["translated_size"] is None
    assert decision["translated_effective_exposure_pct"] is None
    assert decision["semantic_drift_detected"] is False
    assert decision["translation_notes"] is None


def test_decision_validator_keeps_legacy_and_translation_fields_together():
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
        "provider_translation_result": {
            "provider": "oanda",
            "policy_sizing_intent": {
                "semantic_action": "SELL",
                "target_exposure_pct": 2750.0,
                "target_delta_pct": 2750.0,
                "reduction_fraction": None,
                "sizing_anchor": "quarter_kelly_conservative",
                "provider_agnostic": True,
                "version": 1,
            },
            "translated_size": -2500,
            "effective_exposure_pct": 2750.0,
            "semantic_drift_detected": False,
            "translation_notes": "oanda_integer_unit_translation",
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
    assert decision["recommended_position_size"] > 0
    assert decision["suggested_amount"] == decision["recommended_position_size"]
    assert decision["translation_provider"] == "oanda"
    assert decision["translated_size"] == -2500



def test_decision_validator_surfaces_policy_action_metadata_additively():
    validator = DecisionValidator(config=_base_config())

    context = {
        "market_data": {"close": 100.0},
        "balance": {"USD": 1000.0},
        "price_change": 0.0,
        "volatility": 0.01,
        "portfolio": {},
    }
    ai_response = {
        "action": "OPEN_SMALL_LONG",
        "confidence": 80,
        "reasoning": "bounded policy action",
        "amount": 0,
    }
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

    assert decision["action"] == "OPEN_SMALL_LONG"
    assert decision["policy_action"] == "OPEN_SMALL_LONG"
    assert decision["policy_action_version"] == 1
    assert decision["policy_action_family"] == "open_long"
    assert decision["legacy_action_compatibility"] == "BUY"
    assert decision["structural_action_validity"] == "unchecked"


def test_decision_validator_keeps_legacy_action_fields_when_action_is_directional():
    validator = DecisionValidator(config=_base_config())

    context = {
        "market_data": {"close": 100.0},
        "balance": {"USD": 1000.0},
        "price_change": 0.0,
        "volatility": 0.01,
        "portfolio": {},
    }
    ai_response = {"action": "BUY", "confidence": 80, "reasoning": "legacy", "amount": 0}
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

    assert decision["action"] == "BUY"
    assert decision["policy_action"] is None
    assert decision["policy_action_version"] is None
    assert decision["policy_action_family"] is None
    assert decision["legacy_action_compatibility"] is None


def test_decision_validator_policy_action_close_has_no_legacy_compatibility():
    validator = DecisionValidator(config=_base_config())

    context = {
        "market_data": {"close": 100.0},
        "balance": {"USD": 1000.0},
        "price_change": 0.0,
        "volatility": 0.01,
        "portfolio": {},
    }
    ai_response = {
        "action": "CLOSE_LONG",
        "confidence": 80,
        "reasoning": "bounded policy action",
        "amount": 0,
    }
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
        has_existing_position=True,
        is_crypto=True,
        is_forex=False,
    )

    assert decision["policy_action"] == "CLOSE_LONG"
    assert decision["policy_action_family"] == "close_long"
    assert decision["legacy_action_compatibility"] is None



def test_decision_validator_surfaces_invalid_policy_action_context():
    validator = DecisionValidator(config=_base_config())

    context = {
        "market_data": {"close": 100.0},
        "balance": {"USD": 1000.0},
        "price_change": 0.0,
        "volatility": 0.01,
        "portfolio": {},
        "position_state": "flat",
    }
    ai_response = {
        "action": "ADD_SMALL_LONG",
        "confidence": 80,
        "reasoning": "invalid from flat",
        "amount": 0,
    }
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

    assert decision["policy_action"] == "ADD_SMALL_LONG"
    assert decision["current_position_state"] == "flat"
    assert decision["structural_action_validity"] == "invalid"
    assert decision["invalid_action_reason"] == "action ADD_SMALL_LONG is structurally invalid for position_state=flat"
    assert "OPEN_SMALL_LONG" in decision["legal_actions"]
    assert decision["risk_vetoed"] is False



def test_decision_validator_surfaces_valid_policy_action_context():
    validator = DecisionValidator(config=_base_config())

    context = {
        "market_data": {"close": 100.0},
        "balance": {"USD": 1000.0},
        "price_change": 0.0,
        "volatility": 0.01,
        "portfolio": {},
        "position_state": {"state": "LONG"},
    }
    ai_response = {
        "action": "CLOSE_LONG",
        "confidence": 80,
        "reasoning": "valid from long",
        "amount": 0,
    }
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
        has_existing_position=True,
        is_crypto=True,
        is_forex=False,
    )

    assert decision["current_position_state"] == "long"
    assert decision["structural_action_validity"] == "valid"
    assert decision["invalid_action_reason"] is None
    assert "CLOSE_LONG" in decision["legal_actions"]
    assert decision["action_context_version"] == 1



def test_decision_validator_surfaces_policy_action_veto_metadata_additively():
    validator = DecisionValidator(config=_base_config())

    context = {
        "market_data": {"close": 100.0},
        "balance": {"USD": 1000.0},
        "price_change": 0.0,
        "volatility": 0.01,
        "portfolio": {},
        "position_state": "flat",
        "policy_action_veto_result": {
            "policy_action": "OPEN_MEDIUM_LONG",
            "risk_vetoed": True,
            "risk_veto_reason": "Trade rejected: drawdown exceeds threshold",
            "gatekeeper_message": "Trade rejected: drawdown exceeds threshold",
            "version": 1,
        },
    }
    ai_response = {
        "action": "OPEN_MEDIUM_LONG",
        "confidence": 80,
        "reasoning": "risk vetoed",
        "amount": 0,
    }
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

    assert decision["structural_action_validity"] == "valid"
    assert decision["risk_vetoed"] is True
    assert decision["risk_veto_reason"] == "Trade rejected: drawdown exceeds threshold"
    assert decision["gatekeeper_message"] == "Trade rejected: drawdown exceeds threshold"
    assert decision["legacy_action_compatibility"] == "BUY"
