import unittest

from finance_feedback_engine.decision_engine.engine import DecisionEngine
from finance_feedback_engine.decision_engine.ensemble_manager import (
    EnsembleDecisionManager,
)


class EnsembleSafetyChecksTest(unittest.TestCase):
    def test_adjust_weights_handles_zero_weight_total(self):
        config = {
            "ensemble": {
                "enabled_providers": ["local", "cli"],
                "provider_weights": {"local": 0.0, "cli": 0.0},
            }
        }
        manager = EnsembleDecisionManager(config)
        adjusted = manager._adjust_weights_for_active_providers(
            ["local", "cli"], []
        )

        self.assertAlmostEqual(sum(adjusted.values()), 1.0)
        self.assertAlmostEqual(adjusted["local"], 0.5)
        self.assertAlmostEqual(adjusted["cli"], 0.5)

    def test_is_valid_provider_response_strict_checks(self):
        engine = DecisionEngine({"ai_provider": "local"})

        valid_decision = {
            "action": "BUY",
            "confidence": 90,
            "reasoning": "Momentum strong, buying.",
            "amount": 1.2,
        }
        self.assertTrue(
            engine._is_valid_provider_response(valid_decision, "local")
        )

        missing_amount = {
            "action": "BUY",
            "confidence": 75,
            "reasoning": "No amount provided",
        }
        self.assertTrue(
            engine._is_valid_provider_response(missing_amount, "local")
        )

        none_amount = {**valid_decision, "amount": None}
        self.assertTrue(
            engine._is_valid_provider_response(none_amount, "local")
        )

        empty_reasoning = {**valid_decision, "reasoning": "   "}
        self.assertFalse(
            engine._is_valid_provider_response(empty_reasoning, "local")
        )

        high_confidence = {**valid_decision, "confidence": 120}
        self.assertFalse(
            engine._is_valid_provider_response(high_confidence, "local")
        )

        negative_amount = {**valid_decision, "amount": -5}
        self.assertFalse(
            engine._is_valid_provider_response(negative_amount, "local")
        )

        invalid_action = {**valid_decision, "action": "SHORT"}
        self.assertFalse(
            engine._is_valid_provider_response(invalid_action, "local")
        )

        fallback_reason = {**valid_decision, "reasoning": "Fallback mode used"}
        self.assertFalse(
            engine._is_valid_provider_response(fallback_reason, "local")
        )


if __name__ == "__main__":
    unittest.main()
