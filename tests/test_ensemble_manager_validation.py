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
        adjusted = manager._adjust_weights_for_active_providers(["local", "cli"], [])

        self.assertAlmostEqual(sum(adjusted.values()), 1.0)
        self.assertAlmostEqual(adjusted["local"], 0.5)
        self.assertAlmostEqual(adjusted["cli"], 0.5)

    def test_is_valid_provider_response_strict_checks(self):
        manager = EnsembleDecisionManager({})

        valid_decision = {
            "action": "BUY",
            "confidence": 90,
            "reasoning": "Momentum strong, buying.",
        }
        self.assertTrue(manager._is_valid_provider_response(valid_decision, "local"))

        # Empty reasoning is now allowed (validation is more lenient)
        empty_reasoning = {**valid_decision, "reasoning": "   "}
        self.assertTrue(manager._is_valid_provider_response(empty_reasoning, "local"))

        invalid_action = {**valid_decision, "action": "SHORT"}
        self.assertFalse(manager._is_valid_provider_response(invalid_action, "local"))

    def test_local_models_config_reading(self):
        config = {
            "decision_engine": {
                "local_models": ["llama3.2:3b", "mistral:7b"],
                "local_priority": "soft",
            }
        }
        engine = DecisionEngine(config)
        self.assertEqual(engine.local_models, ["llama3.2:3b", "mistral:7b"])
        self.assertEqual(engine.local_priority, "soft")

    def test_local_models_validation(self):
        # Valid list
        config = {"decision_engine": {"local_models": ["model1", "model2"]}}
        engine = DecisionEngine(config)
        self.assertEqual(engine.local_models, ["model1", "model2"])

        # Invalid type
        config = {"decision_engine": {"local_models": "not_a_list"}}
        with self.assertRaises(ValueError):
            DecisionEngine(config)

        # Valid priority types
        for priority in [True, False, "soft", 1.5, 2.0]:
            config = {"decision_engine": {"local_priority": priority}}
            engine = DecisionEngine(config)
            self.assertEqual(engine.local_priority, priority)

        # Invalid priority type
        config = {"decision_engine": {"local_priority": "invalid"}}
        with self.assertRaises(ValueError):
            DecisionEngine(config)

    def test_debate_mode_validates_enabled_providers(self):
        # Test that debate mode fails when providers are not enabled
        config_invalid = {
            "ensemble": {
                "enabled_providers": ["local"],
                "debate_mode": True,
                "debate_providers": {
                    "bull": "gemini",
                    "bear": "qwen",
                    "judge": "local",
                },
            }
        }

        with self.assertRaises(ValueError) as context:
            EnsembleDecisionManager(config_invalid)

        self.assertIn(
            "debate providers are not in enabled_providers", str(context.exception)
        )
        self.assertIn("gemini", str(context.exception))
        self.assertIn("qwen", str(context.exception))

        # Test that debate mode works when all providers are enabled
        config_valid = {
            "ensemble": {
                "enabled_providers": ["local", "gemini", "qwen"],
                "debate_mode": True,
                "debate_providers": {
                    "bull": "gemini",
                    "bear": "qwen",
                    "judge": "local",
                },
            }
        }

        manager = EnsembleDecisionManager(config_valid)
        self.assertTrue(manager.debate_mode)
        self.assertEqual(manager.debate_providers["bull"], "gemini")
        self.assertEqual(manager.debate_providers["bear"], "qwen")
        self.assertEqual(manager.debate_providers["judge"], "local")

    def test_is_local_provider(self):
        config = {
            "ensemble": {
                "enabled_providers": ["local", "cli", "codex", "qwen", "gemini"],
            }
        }
        manager = EnsembleDecisionManager(config)

        # Test local providers
        self.assertTrue(manager._is_local_provider("local"))
        self.assertTrue(manager._is_local_provider("llama"))
        self.assertTrue(manager._is_local_provider("mistral"))
        self.assertTrue(manager._is_local_provider("deepseek"))
        self.assertTrue(manager._is_local_provider("gemma"))
        self.assertTrue(manager._is_local_provider("phi"))
        self.assertTrue(manager._is_local_provider("qwen:"))
        self.assertTrue(manager._is_local_provider("llama-7b"))

        # Test non-local providers
        self.assertFalse(manager._is_local_provider("cli"))
        self.assertFalse(manager._is_local_provider("codex"))
        self.assertFalse(manager._is_local_provider("gemini"))
        self.assertFalse(manager._is_local_provider("qwen"))
        self.assertFalse(manager._is_local_provider("remote"))

    def test_calculate_robust_weights_mixed_providers(self):
        config = {
            "ensemble": {
                "enabled_providers": ["local", "cli", "codex", "qwen", "gemini"],
                "provider_weights": {
                    "local": 0.2,
                    "cli": 0.2,
                    "codex": 0.2,
                    "qwen": 0.2,
                    "gemini": 0.2,
                },
                "local_dominance_target": 0.6,
            }
        }
        manager = EnsembleDecisionManager(config)

        # Mixed: local and cloud
        active = ["local", "cli", "codex"]
        weights = manager._calculate_robust_weights(active)

        # local: 0.2 * (0.6 / 0.2) = 0.6
        # cloud: cli 0.2 * (0.4 / 0.4) = 0.2, codex 0.2 * (0.4 / 0.4) = 0.2
        self.assertAlmostEqual(weights["local"], 0.6, places=3)
        self.assertAlmostEqual(weights["cli"], 0.2, places=3)
        self.assertAlmostEqual(weights["codex"], 0.2, places=3)
        self.assertAlmostEqual(sum(weights.values()), 1.0, places=3)

    def test_calculate_robust_weights_only_local(self):
        config = {
            "ensemble": {
                "enabled_providers": ["local", "llama"],
                "provider_weights": {"local": 0.3, "llama": 0.7},
                "local_dominance_target": 0.6,
            }
        }
        manager = EnsembleDecisionManager(config)

        active = ["local", "llama"]
        weights = manager._calculate_robust_weights(active)

        # Only local, should be equal: 0.5 each
        self.assertAlmostEqual(weights["local"], 0.5, places=3)
        self.assertAlmostEqual(weights["llama"], 0.5, places=3)
        self.assertAlmostEqual(sum(weights.values()), 1.0, places=3)

    def test_calculate_robust_weights_only_cloud(self):
        config = {
            "ensemble": {
                "enabled_providers": ["cli", "codex", "gemini"],
                "provider_weights": {"cli": 0.1, "codex": 0.3, "gemini": 0.6},
                "local_dominance_target": 0.6,
            }
        }
        manager = EnsembleDecisionManager(config)

        active = ["cli", "codex", "gemini"]
        weights = manager._calculate_robust_weights(active)

        # Only cloud, should be equal: 1/3 each
        self.assertAlmostEqual(weights["cli"], 1 / 3, places=3)
        self.assertAlmostEqual(weights["codex"], 1 / 3, places=3)
        self.assertAlmostEqual(weights["gemini"], 1 / 3, places=3)
        self.assertAlmostEqual(sum(weights.values()), 1.0, places=3)

    def test_calculate_robust_weights_empty(self):
        config = {
            "ensemble": {
                "enabled_providers": ["local"],
            }
        }
        manager = EnsembleDecisionManager(config)

        weights = manager._calculate_robust_weights([])
        self.assertEqual(weights, {})

    def test_calculate_robust_weights_with_dynamic_weights(self):
        config = {
            "ensemble": {
                "enabled_providers": ["local", "cli"],
                "provider_weights": {"local": 0.2, "cli": 0.8},
                "local_dominance_target": 0.6,
            }
        }
        dynamic_weights = {"local": 0.5, "cli": 0.5}
        manager = EnsembleDecisionManager(config, dynamic_weights)

        active = ["local", "cli"]
        weights = manager._calculate_robust_weights(active)

        # Dynamic weights are used directly as final weights
        self.assertAlmostEqual(weights["local"], 0.5, places=3)
        self.assertAlmostEqual(weights["cli"], 0.5, places=3)
        self.assertAlmostEqual(sum(weights.values()), 1.0, places=3)


if __name__ == "__main__":
    unittest.main()
