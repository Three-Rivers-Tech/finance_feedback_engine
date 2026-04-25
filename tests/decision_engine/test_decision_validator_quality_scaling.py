import pytest
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



def test_decision_validator_exit_sizing_respects_contract_size_metadata():
    validator = DecisionValidator(config=_base_config())

    context = {
        "market_data": {"close": 2127.0},
        "balance": {"USD": 1000.0},
        "price_change": 0.0,
        "volatility": 0.01,
        "portfolio": {},
        "position_state": {"state": "LONG", "contracts": 5.0, "contract_size": 0.1},
    }
    ai_response = {
        "action": "CLOSE_LONG",
        "confidence": 80,
        "reasoning": "trim the full long",
        "amount": 5050.0,
    }
    position_sizing_result = {
        "recommended_position_size": 0,
        "stop_loss_price": 2080.0,
        "sizing_stop_loss_percentage": 0.02,
        "risk_percentage": 0.01,
    }

    decision = validator.create_decision(
        asset_pair="ETHUSD",
        context=context,
        ai_response=ai_response,
        position_sizing_result=position_sizing_result,
        relevant_balance={"USD": 1000.0},
        balance_source="test",
        has_existing_position=True,
        is_crypto=True,
        is_forex=False,
    )

    assert decision["recommended_position_size"] == 5.0
    assert decision["suggested_amount"] == pytest.approx(1063.5)



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



def test_decision_validator_leaves_action_context_unchecked_without_position_state():
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
        "reasoning": "no position state provided",
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

    assert decision["policy_action"] == "OPEN_SMALL_LONG"
    assert decision["structural_action_validity"] == "unchecked"
    assert decision["current_position_state"] is None
    assert decision["legal_actions"] is None
    assert decision["invalid_action_reason"] is None



def test_decision_validator_surfaces_canonical_action_context_and_control_outcome():
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

    assert decision["action_context"]["current_position_state"] == "flat"
    assert decision["action_context"]["structural_action_validity"] == "valid"
    assert decision["action_context"]["risk_vetoed"] is True
    assert decision["action_context"]["risk_vetoed"] == decision["risk_vetoed"]
    assert decision["action_context"]["risk_veto_reason"] == decision["risk_veto_reason"]
    assert decision["action_context"]["gatekeeper_message"] == decision["gatekeeper_message"]
    assert decision["control_outcome"]["status"] == "vetoed"
    assert decision["control_outcome"]["reason_code"] == "RISK_VETO"
    assert decision["control_outcome"]["message"] == "Trade rejected: drawdown exceeds threshold"



def test_decision_validator_surfaces_canonical_policy_state_additively():
    validator = DecisionValidator(config=_base_config())

    context = {
        "market_data": {"close": 100.0},
        "balance": {"USD": 1000.0},
        "price_change": 0.0,
        "volatility": 0.03,
        "portfolio": {"unrealized_pnl": 12.5},
        "position_state": {"state": "LONG"},
        "market_regime": "trend",
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

    assert decision["policy_state"]["position_state"] == "long"
    assert decision["policy_state"]["market_regime"] == "trend"
    assert decision["policy_state"]["volatility"] == 0.03
    assert decision["policy_state"]["current_price"] == 100.0
    assert decision["policy_state"]["unrealized_pnl"] == 12.5
    assert decision["policy_state"]["version"] == 1



def test_decision_validator_surfaces_policy_package_additively():
    validator = DecisionValidator(config=_base_config())

    context = {
        "market_data": {"close": 100.0},
        "balance": {"USD": 1000.0},
        "price_change": 0.0,
        "volatility": 0.03,
        "portfolio": {"unrealized_pnl": 12.5},
        "position_state": "flat",
        "market_regime": "trend",
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

    assert decision["policy_package"]["version"] == 1
    assert decision["policy_package"]["policy_state"] == decision["policy_state"]
    assert decision["policy_package"]["action_context"] == decision["action_context"]
    assert decision["policy_package"]["policy_sizing_intent"] == decision["policy_sizing_intent"]
    assert decision["policy_package"]["provider_translation_result"] == decision["provider_translation_result"]
    assert decision["policy_package"]["control_outcome"] == decision["control_outcome"]
    assert decision["policy_package"]["control_outcome"]["status"] == "vetoed"



def test_decision_validator_policy_package_stays_aligned_when_context_is_partial():
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
        "reasoning": "partial context",
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

    assert decision["policy_package"]["policy_state"] == decision["policy_state"]
    assert decision["policy_package"]["action_context"] == decision["action_context"]
    assert decision["policy_package"]["control_outcome"] == decision["control_outcome"]
    assert decision["policy_package"]["action_context"]["structural_action_validity"] == "unchecked"
    assert decision["policy_package"]["policy_state"]["position_state"] is None



def test_decision_validator_policy_package_keeps_sizing_translation_alignment():
    validator = DecisionValidator(config=_base_config())

    context = {
        "market_data": {"close": 100.0},
        "balance": {"USD": 1000.0},
        "price_change": 0.0,
        "volatility": 0.03,
        "portfolio": {"unrealized_pnl": 12.5},
        "position_state": "flat",
        "market_regime": "trend",
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

    assert decision["policy_package"]["policy_sizing_intent"] == decision["policy_sizing_intent"]
    assert decision["policy_package"]["provider_translation_result"] == decision["provider_translation_result"]
    assert decision["policy_package"]["policy_sizing_intent"]["provider_agnostic"] is True
    assert decision["policy_package"]["provider_translation_result"]["provider"] == "coinbase"



def test_decision_validator_policy_package_gracefully_handles_missing_sizing_translation_context():
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
        "action": "OPEN_SMALL_LONG",
        "confidence": 80,
        "reasoning": "partial context",
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

    assert decision["policy_package"]["policy_sizing_intent"] is None
    assert decision["policy_package"]["provider_translation_result"] is None



def test_decision_validator_policy_package_alignment_holds_without_translation_context():
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
        "action": "OPEN_SMALL_LONG",
        "confidence": 80,
        "reasoning": "no translation context",
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

    assert decision["policy_package"]["policy_state"] == decision["policy_state"]
    assert decision["policy_package"]["action_context"] == decision["action_context"]
    assert decision["policy_package"]["policy_sizing_intent"] is None
    assert decision["policy_package"]["provider_translation_result"] is None



def test_decision_validator_materializes_policy_trace_from_canonical_surfaces():
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
        "action": "OPEN_SMALL_LONG",
        "confidence": 80,
        "reasoning": "materialize trace",
        "amount": 0,
        "ai_provider": "ensemble",
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

    assert decision["policy_trace"]["policy_package"] == decision["policy_package"]
    assert decision["policy_trace"]["decision_envelope"]["action"] == decision["action"]
    assert decision["policy_trace"]["decision_envelope"]["policy_action"] == decision["policy_action"]
    assert decision["policy_trace"]["decision_envelope"]["legacy_action_compatibility"] == decision["legacy_action_compatibility"]
    assert decision["policy_trace"]["decision_envelope"]["confidence"] == decision["confidence"]
    assert decision["policy_trace"]["decision_envelope"]["reasoning"] == decision["reasoning"]
    assert decision["policy_trace"]["decision_metadata"]["asset_pair"] == "BTCUSD"
    assert decision["policy_trace"]["decision_metadata"]["ai_provider"] == "ensemble"
    assert decision["policy_trace"]["trace_version"] == 1



def test_decision_validator_preserves_legacy_path_without_policy_trace():
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
        "action": "BUY",
        "confidence": 80,
        "reasoning": "legacy path",
        "amount": 0,
        "ai_provider": "local",
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

    assert decision["policy_package"] is None
    assert decision["policy_trace"] is None


def test_decision_validator_preserves_contract_effective_futures_notional_for_open_medium_entry():
    validator = DecisionValidator(config=_base_config())

    context = {
        "market_data": {"close": 20.0},
        "balance": {"USD": 1000.0},
        "price_change": 0.0,
        "volatility": 0.01,
        "portfolio": {},
    }
    ai_response = {
        "action": "BUY",
        "policy_action": "OPEN_MEDIUM_LONG",
        "confidence": 72,
        "amount": 0,
    }
    position_sizing_result = {
        "recommended_position_size": 7.112,
        "stop_loss_price": 19.0,
        "sizing_stop_loss_percentage": 0.05,
        "risk_percentage": 0.01,
        "policy_sizing_intent": {
            "semantic_action": "OPEN_MEDIUM_LONG",
            "target_exposure_pct": 142.24,
            "target_delta_pct": 142.24,
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

    assert decision["policy_action"] == "OPEN_MEDIUM_LONG"
    assert decision["position_size_multiplier"] < 1.0
    assert decision["suggested_amount"] == 142.24


def test_decision_validator_still_scales_open_small_entries_outside_preservation_seam():
    validator = DecisionValidator(config=_base_config())

    context = {
        "market_data": {"close": 20.0},
        "balance": {"USD": 1000.0},
        "price_change": 0.0,
        "volatility": 0.01,
        "portfolio": {},
    }
    ai_response = {
        "action": "BUY",
        "policy_action": "OPEN_SMALL_LONG",
        "confidence": 72,
        "amount": 0,
    }
    position_sizing_result = {
        "recommended_position_size": 7.112,
        "stop_loss_price": 19.0,
        "sizing_stop_loss_percentage": 0.05,
        "risk_percentage": 0.01,
        "policy_sizing_intent": {
            "semantic_action": "OPEN_SMALL_LONG",
            "target_exposure_pct": 142.24,
            "target_delta_pct": 142.24,
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

    assert decision["policy_action"] == "OPEN_SMALL_LONG"
    assert decision["position_size_multiplier"] < 1.0
    assert decision["suggested_amount"] < 142.24

