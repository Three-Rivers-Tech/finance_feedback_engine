"""Test for TradingAgentConfig polymorphism handling across the codebase.

This test suite ensures that code which previously assumed engine.config["agent"]
was always a dict can now handle both dict and TradingAgentConfig object forms.
"""

import pytest
from finance_feedback_engine.agent.config import TradingAgentConfig
from finance_feedback_engine.decision_engine.position_sizing import PositionSizingCalculator
from finance_feedback_engine.cli.commands.agent import run_agent as agent_run


@pytest.fixture
def config_with_agent_dict():
    """Config with agent as dict (legacy format)."""
    return {
        "agent": {
            "asset_pairs": ["BTCUSD", "ETHUSD"],
            "risk_percentage": 0.02,
            "sizing_stop_loss_percentage": 0.03,
            "use_dynamic_stop_loss": True,
            "atr_multiplier": 2.5,
            "min_stop_loss_pct": 0.01,
            "max_stop_loss_pct": 0.05,
        },
        "decision_engine": {"ai_provider": "ensemble"},
        "ensemble": {"debate_mode": False},
    }


@pytest.fixture
def config_with_agent_object():
    """Config with agent as TradingAgentConfig object (current format)."""
    return {
        "agent": TradingAgentConfig(
            asset_pairs=["BTCUSD", "ETHUSD"],
            risk_percentage=0.02,
            sizing_stop_loss_percentage=0.03,
        ),
        "decision_engine": {"ai_provider": "ensemble"},
        "ensemble": {"debate_mode": False},
    }


class TestPositionSizingWithPolymorphicConfig:
    """Test position sizing calculator handles both dict and object forms."""

    def test_position_sizing_with_dict_agent_config(self, config_with_agent_dict):
        """Position sizing should work with dict agent config."""
        calculator = PositionSizingCalculator(config_with_agent_dict)

        # Should not raise AttributeError
        result = calculator.calculate_position_sizing_params(
            context={},
            current_price=50000,
            action="BUY",
            has_existing_position=False,
            relevant_balance={"USD": 10000},
            balance_source="test",
            signal_only_default=False,
        )

        assert result is not None
        assert "risk_percentage" in result

    def test_position_sizing_with_object_agent_config(self, config_with_agent_object):
        """Position sizing should work with TradingAgentConfig object."""
        calculator = PositionSizingCalculator(config_with_agent_object)

        # Should not raise AttributeError: 'TradingAgentConfig' object has no attribute 'get'
        result = calculator.calculate_position_sizing_params(
            context={},
            current_price=50000,
            action="BUY",
            has_existing_position=False,
            relevant_balance={"USD": 10000},
            balance_source="test",
            signal_only_default=False,
        )

        assert result is not None
        assert "risk_percentage" in result

    def test_position_sizing_uses_correct_risk_percentage(self, config_with_agent_object):
        """Position sizing should extract risk percentage correctly from object."""
        calculator = PositionSizingCalculator(config_with_agent_object)
        result = calculator.calculate_position_sizing_params(
            context={},
            current_price=50000,
            action="BUY",
            has_existing_position=False,
            relevant_balance={"USD": 10000},
            balance_source="test",
            signal_only_default=False,
        )

        # Should use 0.02 (2%) from the TradingAgentConfig object
        assert result["risk_percentage"] == 0.02


class TestBotControlConfigHandling:
    """Test bot control endpoints handle both config forms (indirectly)."""

    def test_start_agent_with_trading_agent_config(self):
        """start_agent endpoint should accept TradingAgentConfig objects.

        This is tested indirectly via API in integration tests,
        but we document the requirement here.
        """
        # The endpoint receives a request and internally converts
        # engine.config["agent"] (which might be TradingAgentConfig)
        # to a dict before creating a new TradingAgentConfig(**data)
        agent_config_obj = TradingAgentConfig(
            asset_pairs=["BTCUSD"],
            risk_percentage=0.01,
        )

        # The isinstance check in start_agent should handle this
        assert isinstance(agent_config_obj, TradingAgentConfig)

        # model_dump() should work
        dumped = agent_config_obj.model_dump()
        assert isinstance(dumped, dict)
        assert dumped["asset_pairs"] == ["BTCUSD"]
        assert dumped["risk_percentage"] == 0.01


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
