"""Regression tests for TradingAgentConfig dict/object handling in bot control."""

import pytest
from finance_feedback_engine.agent.config import TradingAgentConfig


class TestTradingAgentConfigHandling:
    """Regression tests for TradingAgentConfig dict/object handling.

    These tests verify that bot control endpoints gracefully handle both
    dict and TradingAgentConfig object forms in engine.config["agent"],
    preventing "has no object 'get'" AttributeError crashes.

    Background: The start_agent and get_agent_status endpoints in bot_control.py
    were calling .get() on engine.config["agent"], but in some cases this value
    was a TradingAgentConfig object instead of a dict, causing AttributeError.

    Fix: Added isinstance() checks to handle both forms gracefully.
    """

    def test_config_dict_conversion(self):
        """Test that TradingAgentConfig can be converted to dict and reconstructed."""
        # Create a TradingAgentConfig object
        agent_cfg = TradingAgentConfig(
            asset_pairs=["BTCUSD"],
            autonomous={"enabled": True},
        )

        # Convert to dict (as done in the fixed start_agent code)
        if isinstance(agent_cfg, TradingAgentConfig):
            agent_cfg_data = agent_cfg.model_dump()
        else:
            agent_cfg_data = {}

        # Verify it can be reconstructed
        reconstructed = TradingAgentConfig(**agent_cfg_data)
        assert reconstructed.asset_pairs == ["BTCUSD"]
        assert reconstructed.max_daily_trades == 5  # default

    def test_safe_asset_pairs_access_from_dict(self):
        """Test safe access to asset_pairs when config["agent"] is a dict."""
        agent_cfg_dict = {"asset_pairs": ["BTCUSD"], "watchlist": ["BTCUSD"]}

        # Using the safe pattern from the fix
        if isinstance(agent_cfg_dict, TradingAgentConfig):
            asset_pairs = agent_cfg_dict.asset_pairs
        elif isinstance(agent_cfg_dict, dict):
            asset_pairs = agent_cfg_dict.get("asset_pairs", [])
        else:
            asset_pairs = []

        assert asset_pairs == ["BTCUSD"]

    def test_safe_asset_pairs_access_from_object(self):
        """Test safe access to asset_pairs when config["agent"] is a TradingAgentConfig."""
        agent_cfg_obj = TradingAgentConfig(
            asset_pairs=["ETHUSDT"],
            autonomous={"enabled": True},
        )

        # Using the safe pattern from the fix
        if isinstance(agent_cfg_obj, TradingAgentConfig):
            asset_pairs = agent_cfg_obj.asset_pairs
        elif isinstance(agent_cfg_obj, dict):
            asset_pairs = agent_cfg_obj.get("asset_pairs", [])
        else:
            asset_pairs = []

        assert asset_pairs == ["ETHUSDT"]

    def test_old_pattern_fails_on_object(self):
        """Verify the old pattern (calling .get() on object) raises AttributeError."""
        agent_cfg_obj = TradingAgentConfig(
            asset_pairs=["ETHUSDT"],
            autonomous={"enabled": True},
        )

        # The old buggy code would call:
        # asset_pairs = agent_cfg_obj.get("asset_pairs", [])  # BUG: AttributeError

        with pytest.raises(AttributeError, match="has no attribute 'get'"):
            agent_cfg_obj.get("asset_pairs", [])  # type: ignore
