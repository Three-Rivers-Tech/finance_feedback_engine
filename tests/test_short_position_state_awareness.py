"""
Unit tests for SHORT position state awareness in decision engine.

Tests Issue #1 & #2 fixes:
- Position state extraction
- Signal validation against position state
- Prompt generation with position awareness
"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from finance_feedback_engine.decision_engine.engine import DecisionEngine


class TestPositionStateExtraction:
    """Test _extract_position_state method."""

    @pytest.fixture
    def decision_engine(self):
        """Create a decision engine instance with minimal config."""
        config = {
            "decision_engine": {
                "ai_provider": "mock",
                "enable_veto_logic": False,
            }
        }
        return DecisionEngine(config=config)

    def test_extract_flat_state(self, decision_engine):
        """Test position state extraction when FLAT (no position)."""
        context = {
            "monitoring_context": {
                "active_positions": {
                    "futures": []  # No positions
                }
            }
        }

        state = decision_engine._extract_position_state(context, "BTC-USD")

        assert state["has_position"] is False
        assert state["side"] is None
        assert state["state"] == "FLAT"
        assert state["contracts"] == 0
        assert state["entry_price"] == 0
        assert state["unrealized_pnl"] == 0
        assert set(state["allowed_signals"]) == {"BUY", "SELL", "HOLD"}

    def test_extract_long_state(self, decision_engine):
        """Test position state extraction when LONG."""
        context = {
            "monitoring_context": {
                "active_positions": {
                    "futures": [
                        {
                            "product_id": "BTC-USD",
                            "side": "LONG",
                            "contracts": 0.5,
                            "entry_price": 50000.0,
                            "unrealized_pnl": 1000.0,
                        }
                    ]
                }
            }
        }

        state = decision_engine._extract_position_state(context, "BTC-USD")

        assert state["has_position"] is True
        assert state["side"] == "LONG"
        assert state["state"] == "LONG"
        assert state["contracts"] == 0.5
        assert state["entry_price"] == 50000.0
        assert state["unrealized_pnl"] == 1000.0
        assert set(state["allowed_signals"]) == {"SELL", "HOLD"}  # Can only close or hold

    def test_extract_short_state(self, decision_engine):
        """Test position state extraction when SHORT."""
        context = {
            "monitoring_context": {
                "active_positions": {
                    "futures": [
                        {
                            "product_id": "EUR-USD",
                            "side": "SHORT",
                            "contracts": -1000.0,
                            "entry_price": 1.10,
                            "unrealized_pnl": -50.0,
                        }
                    ]
                }
            }
        }

        state = decision_engine._extract_position_state(context, "EUR-USD")

        assert state["has_position"] is True
        assert state["side"] == "SHORT"
        assert state["state"] == "SHORT"
        assert state["contracts"] == -1000.0
        assert state["entry_price"] == 1.10
        assert state["unrealized_pnl"] == -50.0
        assert set(state["allowed_signals"]) == {"BUY", "HOLD"}  # Can only close or hold

    def test_extract_wrong_asset(self, decision_engine):
        """Test position state extraction for asset we don't have position in."""
        context = {
            "monitoring_context": {
                "active_positions": {
                    "futures": [
                        {
                            "product_id": "BTC-USD",
                            "side": "LONG",
                            "contracts": 0.5,
                            "entry_price": 50000.0,
                            "unrealized_pnl": 1000.0,
                        }
                    ]
                }
            }
        }

        # Query for ETH-USD when we only have BTC-USD
        state = decision_engine._extract_position_state(context, "ETH-USD")

        assert state["has_position"] is False
        assert state["state"] == "FLAT"
        assert set(state["allowed_signals"]) == {"BUY", "SELL", "HOLD"}

    def test_extract_no_monitoring_context(self, decision_engine):
        """Test position state extraction when monitoring context is missing."""
        context = {}  # No monitoring_context

        state = decision_engine._extract_position_state(context, "BTC-USD")

        assert state["has_position"] is False
        assert state["state"] == "FLAT"


class TestSignalValidation:
    """Test _validate_signal_against_position method."""

    @pytest.fixture
    def decision_engine(self):
        """Create a decision engine instance with minimal config."""
        config = {
            "decision_engine": {
                "ai_provider": "mock",
                "enable_veto_logic": False,
            }
        }
        return DecisionEngine(config=config)

    def test_buy_when_flat_valid(self, decision_engine):
        """Test BUY signal when FLAT is valid."""
        position_state = {
            "has_position": False,
            "state": "FLAT",
            "allowed_signals": ["BUY", "SELL", "HOLD"],
        }

        is_valid, error = decision_engine._validate_signal_against_position(
            "BUY", position_state, "BTC-USD"
        )

        assert is_valid is True
        assert error is None

    def test_sell_when_flat_valid(self, decision_engine):
        """Test SELL signal when FLAT is valid (opens SHORT)."""
        position_state = {
            "has_position": False,
            "state": "FLAT",
            "allowed_signals": ["BUY", "SELL", "HOLD"],
        }

        is_valid, error = decision_engine._validate_signal_against_position(
            "SELL", position_state, "BTC-USD"
        )

        assert is_valid is True
        assert error is None

    def test_buy_when_long_invalid(self, decision_engine):
        """Test BUY signal when LONG is invalid (can't add to long)."""
        position_state = {
            "has_position": True,
            "side": "LONG",
            "state": "LONG",
            "allowed_signals": ["SELL", "HOLD"],
        }

        is_valid, error = decision_engine._validate_signal_against_position(
            "BUY", position_state, "BTC-USD"
        )

        assert is_valid is False
        assert "BUY not allowed" in error or "Cannot BUY when already LONG" in error
        assert "BTC-USD" in error

    def test_sell_when_long_valid(self, decision_engine):
        """Test SELL signal when LONG is valid (closes position)."""
        position_state = {
            "has_position": True,
            "side": "LONG",
            "state": "LONG",
            "allowed_signals": ["SELL", "HOLD"],
        }

        is_valid, error = decision_engine._validate_signal_against_position(
            "SELL", position_state, "BTC-USD"
        )

        assert is_valid is True
        assert error is None

    def test_sell_when_short_invalid(self, decision_engine):
        """Test SELL signal when SHORT is invalid (can't add to short)."""
        position_state = {
            "has_position": True,
            "side": "SHORT",
            "state": "SHORT",
            "allowed_signals": ["BUY", "HOLD"],
        }

        is_valid, error = decision_engine._validate_signal_against_position(
            "SELL", position_state, "EUR-USD"
        )

        assert is_valid is False
        assert "SELL not allowed" in error or "Cannot SELL when already SHORT" in error
        assert "EUR-USD" in error

    def test_buy_when_short_valid(self, decision_engine):
        """Test BUY signal when SHORT is valid (closes position)."""
        position_state = {
            "has_position": True,
            "side": "SHORT",
            "state": "SHORT",
            "allowed_signals": ["BUY", "HOLD"],
        }

        is_valid, error = decision_engine._validate_signal_against_position(
            "BUY", position_state, "EUR-USD"
        )

        assert is_valid is True
        assert error is None

    def test_hold_always_valid(self, decision_engine):
        """Test HOLD signal is valid in any state."""
        states = [
            {"has_position": False, "state": "FLAT", "allowed_signals": ["BUY", "SELL", "HOLD"]},
            {"has_position": True, "side": "LONG", "state": "LONG", "allowed_signals": ["SELL", "HOLD"]},
            {"has_position": True, "side": "SHORT", "state": "SHORT", "allowed_signals": ["BUY", "HOLD"]},
        ]

        for position_state in states:
            is_valid, error = decision_engine._validate_signal_against_position(
                "HOLD", position_state, "BTC-USD"
            )
            assert is_valid is True, f"HOLD should be valid in state {position_state['state']}"
            assert error is None


class TestPromptGeneration:
    """Test that position state is included in AI prompt."""

    @pytest.fixture
    def decision_engine(self):
        """Create a decision engine instance with minimal config."""
        config = {
            "decision_engine": {
                "ai_provider": "mock",
                "enable_veto_logic": False,
            }
        }
        return DecisionEngine(config=config)

    def test_prompt_includes_flat_state(self, decision_engine):
        """Test that prompt includes FLAT position state."""
        context = {
            "asset_pair": "BTC-USD",
            "market_data": {
                "close": 50000.0,
                "type": "crypto",
                "trend": "neutral",
            },
            "balance": 10000.0,
            "price_change": 2.5,
            "volatility": 0.03,
            "market_status": {"is_open": True},
            "data_freshness": {"is_fresh": True},
            "monitoring_context": {
                "active_positions": {"futures": []},
                "has_monitoring_data": True,
            },
        }

        prompt = decision_engine._create_ai_prompt(context)

        assert "YOUR CURRENT POSITION STATE" in prompt
        assert "FLAT" in prompt
        assert "no active position in BTC-USD" in prompt.lower()
        assert "BUY (open LONG), SELL (open SHORT), HOLD" in prompt

    def test_prompt_includes_long_state(self, decision_engine):
        """Test that prompt includes LONG position state with warnings."""
        context = {
            "asset_pair": "BTC-USD",
            "market_data": {
                "close": 52000.0,
                "type": "crypto",
                "trend": "bullish",
            },
            "balance": 10000.0,
            "price_change": 4.0,
            "volatility": 0.02,
            "market_status": {"is_open": True},
            "data_freshness": {"is_fresh": True},
            "monitoring_context": {
                "active_positions": {
                    "futures": [
                        {
                            "product_id": "BTC-USD",
                            "side": "LONG",
                            "contracts": 0.5,
                            "entry_price": 50000.0,
                            "unrealized_pnl": 1000.0,
                        }
                    ]
                },
                "has_monitoring_data": True,
            },
        }

        prompt = decision_engine._create_ai_prompt(context)

        assert "YOUR CURRENT POSITION STATE" in prompt
        assert "LONG position in BTC-USD" in prompt
        assert "Entry Price: $50000.00" in prompt
        assert "Unrealized P&L: +$1000.00" in prompt
        assert "SELL, HOLD" in prompt  # Allowed signals
        assert "CRITICAL CONSTRAINT" in prompt
        assert "PROHIBITED" in prompt

    def test_prompt_includes_short_state(self, decision_engine):
        """Test that prompt includes SHORT position state with warnings."""
        context = {
            "asset_pair": "EUR-USD",
            "market_data": {
                "close": 1.08,
                "type": "forex",
                "trend": "bearish",
            },
            "balance": 10000.0,
            "price_change": -1.8,
            "volatility": 0.015,
            "market_status": {"is_open": True},
            "data_freshness": {"is_fresh": True},
            "monitoring_context": {
                "active_positions": {
                    "futures": [
                        {
                            "product_id": "EUR-USD",
                            "side": "SHORT",
                            "contracts": -1000.0,
                            "entry_price": 1.10,
                            "unrealized_pnl": 200.0,
                        }
                    ]
                },
                "has_monitoring_data": True,
            },
        }

        prompt = decision_engine._create_ai_prompt(context)

        assert "YOUR CURRENT POSITION STATE" in prompt
        assert "SHORT position in EUR-USD" in prompt
        assert "Entry Price: $1.10" in prompt
        assert "Unrealized P&L: +$200.00" in prompt
        assert "BUY, HOLD" in prompt  # Allowed signals (can only BUY to close SHORT)
        assert "CRITICAL CONSTRAINT" in prompt


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
