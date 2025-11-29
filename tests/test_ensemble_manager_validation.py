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

    def test_local_models_config_reading(self):
        config = {
            "decision_engine": {
                "local_models": ["llama3.2:3b", "mistral:7b"],
                "local_priority": "soft"
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

    def test_local_candidates_building(self):
        config = {
            "decision_engine": {
                "local_models": ["llama3.2:3b", "mistral:7b"]
            },
            "ensemble": {
                "enabled_providers": ["llama3.2:3b", "mistral:7b", "gemini"]
            }
        }
        engine = DecisionEngine(config)
        # Simulate the partitioning logic
        enabled_providers = ["llama3.2:3b", "mistral:7b", "gemini"]
        local_candidates = []
        if engine.local_models:
            for model in engine.local_models:
                if model in enabled_providers:
                    local_candidates.append(model)
        self.assertEqual(local_candidates, ["llama3.2:3b", "mistral:7b"])

    def test_adjusted_weights_computation(self):
        config = {
            "ensemble": {
                "enabled_providers": ["local1", "remote1"],
                "provider_weights": {"local1": 0.5, "remote1": 0.5}
            }
        }
        manager = EnsembleDecisionManager(config)
        
        # Test soft boost
        adjusted_weights = {}
        local_candidates = ["local1"]
        boost_factor = 1.5
        for p in ["local1", "remote1"]:
            base_weight = manager.base_weights.get(p, 1.0)
            if p in local_candidates:
                adjusted_weights[p] = base_weight * boost_factor
            else:
                adjusted_weights[p] = base_weight
        total = sum(adjusted_weights.values())
        adjusted_weights = {p: w / total for p, w in adjusted_weights.items()}
        
        expected_local = (0.5 * 1.5) / (0.5 * 1.5 + 0.5)
        expected_remote = 0.5 / (0.5 * 1.5 + 0.5)
        self.assertAlmostEqual(adjusted_weights["local1"], expected_local, places=3)
        self.assertAlmostEqual(adjusted_weights["remote1"], expected_remote, places=3)

    def test_debate_mode_validates_enabled_providers(self):
        # Test that debate mode fails when providers are not enabled
        config_invalid = {
            "ensemble": {
                "enabled_providers": ["local"],
                "debate_mode": True,
                "debate_providers": {
                    "bull": "gemini",
                    "bear": "qwen",
                    "judge": "local"
                }
            }
        }
        
        with self.assertRaises(ValueError) as context:
            EnsembleDecisionManager(config_invalid)
        
        self.assertIn("debate providers are not in enabled_providers", str(context.exception))
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
                    "judge": "local"
                }
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
                "provider_weights": {"local": 0.2, "cli": 0.2, "codex": 0.2, "qwen": 0.2, "gemini": 0.2},
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
        self.assertAlmostEqual(weights["cli"], 1/3, places=3)
        self.assertAlmostEqual(weights["codex"], 1/3, places=3)
        self.assertAlmostEqual(weights["gemini"], 1/3, places=3)
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
        
        # local: 0.5 * (0.6 / 0.5) = 0.6
        # cloud: cli 0.5 * (0.4 / 0.5) = 0.4
        self.assertAlmostEqual(weights["local"], 0.6, places=3)
        self.assertAlmostEqual(weights["cli"], 0.4, places=3)
        self.assertAlmostEqual(sum(weights.values()), 1.0, places=3)


if __name__ == "__main__":
    unittest.main()
