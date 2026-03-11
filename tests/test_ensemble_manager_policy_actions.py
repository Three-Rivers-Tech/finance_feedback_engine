import unittest

from finance_feedback_engine.decision_engine.ensemble_manager import EnsembleDecisionManager


class EnsemblePolicyActionAggregationTest(unittest.TestCase):
    def test_weighted_voting_accepts_policy_actions(self):
        config = {
            "ensemble": {
                "enabled_providers": ["local", "cli"],
                "provider_weights": {"local": 0.5, "cli": 0.5},
                "voting_strategy": "weighted",
            }
        }
        manager = EnsembleDecisionManager(config)

        result = manager._weighted_voting(
            providers=["local", "cli"],
            actions=["OPEN_SMALL_LONG", "OPEN_SMALL_LONG"],
            confidences=[80, 70],
            reasonings=["bullish", "also bullish"],
            amounts=[100.0, 90.0],
        )

        self.assertEqual(result["action"], "OPEN_SMALL_LONG")
        self.assertEqual(result["policy_action"], "OPEN_SMALL_LONG")
        self.assertEqual(result["legacy_action_compatibility"], "BUY")
        self.assertIn("OPEN_SMALL_LONG", result["action_votes"])

    def test_weighted_voting_keeps_legacy_path_for_directional_actions(self):
        config = {
            "ensemble": {
                "enabled_providers": ["local", "cli"],
                "provider_weights": {"local": 0.5, "cli": 0.5},
                "voting_strategy": "weighted",
            }
        }
        manager = EnsembleDecisionManager(config)

        result = manager._weighted_voting(
            providers=["local", "cli"],
            actions=["BUY", "BUY"],
            confidences=[80, 70],
            reasonings=["bullish", "also bullish"],
            amounts=[100.0, 90.0],
        )

        self.assertEqual(result["action"], "BUY")
        self.assertIsNone(result.get("policy_action"))

    def test_policy_action_vote_does_not_collapse_to_direction_only(self):
        config = {
            "ensemble": {
                "enabled_providers": ["local", "cli", "codex"],
                "provider_weights": {"local": 0.34, "cli": 0.33, "codex": 0.33},
                "voting_strategy": "weighted",
            }
        }
        manager = EnsembleDecisionManager(config)

        result = manager._weighted_voting(
            providers=["local", "cli", "codex"],
            actions=["OPEN_SMALL_LONG", "OPEN_SMALL_LONG", "ADD_SMALL_LONG"],
            confidences=[80, 75, 90],
            reasonings=["open", "open", "add"],
            amounts=[100.0, 100.0, 120.0],
        )

        self.assertIn(result["action"], {"OPEN_SMALL_LONG", "ADD_SMALL_LONG"})
        self.assertIn("OPEN_SMALL_LONG", result["action_votes"])
        self.assertIn("ADD_SMALL_LONG", result["action_votes"])
        self.assertNotIn("BUY", result["action_votes"])


if __name__ == "__main__":
    unittest.main()
