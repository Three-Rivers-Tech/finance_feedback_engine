"""
Comprehensive tests for position sizing calculator.

This module tests ALL critical paths in the position sizing logic to prevent
financial losses from incorrect position size calculations.

Coverage Target: 80%+
Risk Level: CRITICAL (incorrect sizing = direct financial loss)
"""

import pytest
from finance_feedback_engine.decision_engine.position_sizing import (
    PositionSizingCalculator,
    PolicySizingIntent,
    MIN_ORDER_SIZE_CRYPTO,
    MIN_ORDER_SIZE_FOREX,
    MIN_ORDER_SIZE_DEFAULT,
)


class TestPositionSizingCalculator:
    """Test suite for PositionSizingCalculator class."""

    @pytest.fixture
    def basic_config(self):
        """Basic configuration for position sizing."""
        return {
            "agent": {
                "risk_percentage": 0.01,  # 1% risk per trade
                "sizing_stop_loss_percentage": 0.02,  # 2% stop loss
                "use_dynamic_stop_loss": False,
                "use_kelly_criterion": False,
            }
        }

    @pytest.fixture
    def dynamic_stop_loss_config(self):
        """Configuration with dynamic stop loss enabled."""
        return {
            "agent": {
                "risk_percentage": 0.01,
                "sizing_stop_loss_percentage": 0.02,
                "use_dynamic_stop_loss": True,
                "atr_multiplier": 2.0,
                "min_stop_loss_pct": 0.01,
                "max_stop_loss_pct": 0.05,
            }
        }

    @pytest.fixture
    def kelly_config(self):
        """Configuration with Kelly Criterion enabled."""
        return {
            "agent": {
                "risk_percentage": 0.01,
                "sizing_stop_loss_percentage": 0.02,
                "use_kelly_criterion": True,
                "kelly_criterion": {
                    "default_win_rate": 0.55,
                    "default_avg_win": 100.0,
                    "default_avg_loss": 75.0,
                },
            }
        }

    @pytest.fixture
    def calculator(self, basic_config):
        """Create a basic position sizing calculator."""
        return PositionSizingCalculator(basic_config)

    # =========================================================================
    # CRITICAL PATH TESTS: calculate_position_size (Core Risk-Based Sizing)
    # =========================================================================

    def test_calculate_position_size_basic(self, calculator):
        """Test basic position sizing calculation."""
        # Account: $10,000
        # Risk: 1% = $100
        # Entry: $50,000
        # Stop Loss: 2% = $1,000
        # Expected Position Size: $100 / $1,000 = 0.1 units

        position_size = calculator.calculate_position_size(
            account_balance=10000.0,
            risk_percentage=0.01,
            entry_price=50000.0,
            stop_loss_percentage=0.02,
        )

        expected = 10000.0 * 0.01 / (50000.0 * 0.02)
        assert position_size == pytest.approx(expected, rel=1e-6)
        assert position_size == pytest.approx(0.1, rel=1e-6)

    def test_calculate_position_size_zero_entry_price(self, calculator):
        """Test position sizing with zero entry price (should return 0)."""
        position_size = calculator.calculate_position_size(
            account_balance=10000.0,
            risk_percentage=0.01,
            entry_price=0.0,
            stop_loss_percentage=0.02,
        )

        assert position_size == 0.0

    def test_calculate_position_size_zero_stop_loss(self, calculator):
        """Zero stop loss should be normalized to the minimum enforced stop distance."""
        position_size = calculator.calculate_position_size(
            account_balance=10000.0,
            risk_percentage=0.01,
            entry_price=50000.0,
            stop_loss_percentage=0.0,
        )

        expected = 10000.0 * 0.01 / (50000.0 * 0.005)
        assert position_size == pytest.approx(expected, rel=1e-6)
        assert position_size == pytest.approx(0.4, rel=1e-6)

    def test_calculate_position_size_high_risk(self, calculator):
        """Test position sizing with high risk percentage (5%)."""
        position_size = calculator.calculate_position_size(
            account_balance=10000.0,
            risk_percentage=0.05,  # 5% risk
            entry_price=50000.0,
            stop_loss_percentage=0.02,
        )

        # Risk: 5% = $500
        # Stop Loss Distance: 2% of $50k = $1,000
        # Position Size: $500 / $1,000 = 0.5 units
        assert position_size == pytest.approx(0.5, rel=1e-6)

    def test_calculate_position_size_tight_stop_loss(self, calculator):
        """Test position sizing with tight stop loss (1%)."""
        position_size = calculator.calculate_position_size(
            account_balance=10000.0,
            risk_percentage=0.01,
            entry_price=50000.0,
            stop_loss_percentage=0.01,  # Tight 1% stop loss
        )

        # Risk: 1% = $100
        # Stop Loss Distance: 1% of $50k = $500
        # Position Size: $100 / $500 = 0.2 units
        assert position_size == pytest.approx(0.2, rel=1e-6)

    def test_calculate_position_size_forex(self, calculator):
        """Test position sizing for forex pair (lower price)."""
        position_size = calculator.calculate_position_size(
            account_balance=10000.0,
            risk_percentage=0.01,
            entry_price=1.10,  # EUR/USD
            stop_loss_percentage=0.02,
        )

        # Risk: 1% = $100
        # Stop Loss Distance: 2% of $1.10 = $0.022
        # Position Size: $100 / $0.022 = 4545.45 units
        expected = 10000.0 * 0.01 / (1.10 * 0.02)
        assert position_size == pytest.approx(expected, rel=1e-6)

    # =========================================================================
    # CRITICAL PATH TESTS: calculate_dynamic_stop_loss (ATR-Based)
    # =========================================================================

    def test_calculate_dynamic_stop_loss_with_atr(self):
        """Test dynamic stop loss calculation using ATR from monitoring context."""
        config = {
            "agent": {
                "use_dynamic_stop_loss": True,
                "atr_multiplier": 2.0,
                "min_stop_loss_pct": 0.01,
                "max_stop_loss_pct": 0.05,
            }
        }
        calculator = PositionSizingCalculator(config)

        context = {
            "monitoring_context": {
                "multi_timeframe_pulse": {
                    "1d": {"atr": 1000.0}  # Daily ATR = $1000
                }
            }
        }

        # Current price: $50,000
        # ATR: $1,000
        # ATR Multiplier: 2.0
        # ATR-based stop loss: (1000 * 2.0) / 50000 = 0.04 = 4%
        stop_loss_pct = calculator.calculate_dynamic_stop_loss(
            current_price=50000.0,
            context=context,
            default_percentage=0.02,
            atr_multiplier=2.0,
            min_percentage=0.01,
            max_percentage=0.05,
        )

        expected = (1000.0 * 2.0) / 50000.0
        assert stop_loss_pct == pytest.approx(expected, rel=1e-6)
        assert stop_loss_pct == pytest.approx(0.04, rel=1e-6)

    def test_calculate_dynamic_stop_loss_bounded_min(self):
        """Test dynamic stop loss is bounded by minimum percentage."""
        config = {"agent": {}}
        calculator = PositionSizingCalculator(config)

        context = {
            "monitoring_context": {
                "multi_timeframe_pulse": {
                    "1d": {"atr": 100.0}  # Very small ATR
                }
            }
        }

        # ATR-based would be: (100 * 2.0) / 50000 = 0.004 = 0.4%
        # But min is 1%, so should return 1%
        stop_loss_pct = calculator.calculate_dynamic_stop_loss(
            current_price=50000.0,
            context=context,
            default_percentage=0.02,
            atr_multiplier=2.0,
            min_percentage=0.01,
            max_percentage=0.05,
        )

        assert stop_loss_pct == 0.01  # Bounded to minimum

    def test_calculate_dynamic_stop_loss_bounded_max(self):
        """Test dynamic stop loss is bounded by maximum percentage."""
        config = {"agent": {}}
        calculator = PositionSizingCalculator(config)

        context = {
            "monitoring_context": {
                "multi_timeframe_pulse": {
                    "1d": {"atr": 5000.0}  # Very large ATR
                }
            }
        }

        # ATR-based would be: (5000 * 2.0) / 50000 = 0.20 = 20%
        # But max is 5%, so should return 5%
        stop_loss_pct = calculator.calculate_dynamic_stop_loss(
            current_price=50000.0,
            context=context,
            default_percentage=0.02,
            atr_multiplier=2.0,
            min_percentage=0.01,
            max_percentage=0.05,
        )

        assert stop_loss_pct == 0.05  # Bounded to maximum

    def test_calculate_dynamic_stop_loss_no_atr_fallback(self):
        """Test dynamic stop loss falls back to default when ATR unavailable."""
        config = {"agent": {}}
        calculator = PositionSizingCalculator(config)

        context = {"monitoring_context": {}}  # No ATR data

        stop_loss_pct = calculator.calculate_dynamic_stop_loss(
            current_price=50000.0,
            context=context,
            default_percentage=0.02,
        )

        assert stop_loss_pct == 0.02  # Falls back to default

    def test_calculate_dynamic_stop_loss_atr_from_market_data(self):
        """Test ATR extraction from market_data (fallback source)."""
        config = {"agent": {}}
        calculator = PositionSizingCalculator(config)

        context = {
            "market_data": {"atr": 1000.0}  # ATR in market_data
        }

        stop_loss_pct = calculator.calculate_dynamic_stop_loss(
            current_price=50000.0,
            context=context,
            atr_multiplier=2.0,
            min_percentage=0.01,
            max_percentage=0.05,
        )

        expected = (1000.0 * 2.0) / 50000.0
        assert stop_loss_pct == pytest.approx(expected, rel=1e-6)

    def test_calculate_dynamic_stop_loss_zero_price(self):
        """Test dynamic stop loss with zero price returns default."""
        config = {"agent": {}}
        calculator = PositionSizingCalculator(config)

        context = {"monitoring_context": {"multi_timeframe_pulse": {"1d": {"atr": 1000.0}}}}

        stop_loss_pct = calculator.calculate_dynamic_stop_loss(
            current_price=0.0,  # Zero price
            context=context,
            default_percentage=0.02,
        )

        assert stop_loss_pct == 0.02  # Returns default

    # =========================================================================
    # CRITICAL PATH TESTS: calculate_position_sizing_params (Main Orchestration)
    # =========================================================================

    def test_calculate_position_sizing_params_buy_with_balance(self, calculator):
        """Test position sizing params for BUY action with valid balance."""
        context = {
            "asset_pair": "BTCUSD",
            "market_data": {"type": "crypto"},
        }

        result = calculator.calculate_position_sizing_params(
            context=context,
            current_price=50000.0,
            action="BUY",
            has_existing_position=False,
            relevant_balance={"USD": 10000.0},
            balance_source="coinbase",
        )

        # Verify all required keys present
        assert "recommended_position_size" in result
        assert "stop_loss_price" in result
        assert "sizing_stop_loss_percentage" in result
        assert "risk_percentage" in result
        assert "position_sizing_method" in result

        # Verify calculations
        assert result["recommended_position_size"] is not None
        assert result["recommended_position_size"] > 0
        assert result["stop_loss_price"] is not None
        assert result["stop_loss_price"] < 50000.0  # Stop loss below entry for LONG
        assert result["sizing_stop_loss_percentage"] == 0.02
        assert result["risk_percentage"] == 0.01
        assert result["position_sizing_method"] == "risk_based"

    def test_calculate_position_sizing_params_sell_with_balance(self, calculator):
        """Test position sizing params for SELL action with valid balance."""
        context = {
            "asset_pair": "BTCUSD",
            "market_data": {"type": "crypto"},
        }

        result = calculator.calculate_position_sizing_params(
            context=context,
            current_price=50000.0,
            action="SELL",
            has_existing_position=False,
            relevant_balance={"USD": 10000.0},
            balance_source="coinbase",
        )

        assert result["recommended_position_size"] > 0
        assert result["stop_loss_price"] > 50000.0  # Stop loss above entry for SHORT

    def test_calculate_position_sizing_params_hold_without_position(self, calculator):
        """Test HOLD action without existing position (should return zero sizing)."""
        context = {"asset_pair": "BTCUSD"}

        result = calculator.calculate_position_sizing_params(
            context=context,
            current_price=50000.0,
            action="HOLD",
            has_existing_position=False,
            relevant_balance={"USD": 10000.0},
            balance_source="coinbase",
        )

        assert result["recommended_position_size"] == 0
        assert result["stop_loss_price"] == 50000.0

    def test_calculate_position_sizing_params_hold_with_position(self, calculator):
        """Test HOLD action with existing position (should calculate sizing)."""
        context = {"asset_pair": "BTCUSD"}

        result = calculator.calculate_position_sizing_params(
            context=context,
            current_price=50000.0,
            action="HOLD",
            has_existing_position=True,
            relevant_balance={"USD": 10000.0},
            balance_source="coinbase",
        )

        assert result["recommended_position_size"] > 0


    @pytest.mark.parametrize(
        "asset_pair,current_price,position_state",
        [
            ("BTCUSD", 71110.0, "SHORT"),
            ("ETHUSD", 2163.0, "SHORT"),
            ("BTCUSD", 71110.0, {"state": "SHORT", "side": "SHORT"}),
            ("ETHUSD", 2163.0, {"state": "SHORT", "side": "SHORT"}),
        ],
    )
    def test_calculate_position_sizing_params_hold_with_existing_short_live_like_cases(self, calculator, asset_pair, current_price, position_state):
        context = {"asset_pair": asset_pair, "position_state": position_state}

        result = calculator.calculate_position_sizing_params(
            context=context,
            current_price=current_price,
            action="HOLD",
            has_existing_position=True,
            relevant_balance={"USD": 10000.0},
            balance_source="coinbase",
        )

        assert result["recommended_position_size"] > 0
        assert result["stop_loss_price"] > current_price
        assert result["position_sizing_method"] in {"risk_based", "minimum_order_size", "kelly_criterion", "existing_position_hold"}

    def test_build_policy_sizing_intent_is_provider_agnostic(self, calculator):
        """Stage 1 intent layer should stay provider-agnostic and additive."""
        intent = calculator.build_policy_sizing_intent(
            action="BUY",
            recommended_position_size=0.1,
            current_price=50000.0,
        )

        typed_intent = PolicySizingIntent(**intent)

        assert typed_intent.semantic_action == "BUY"
        assert typed_intent.provider_agnostic is True
        assert typed_intent.sizing_anchor == "quarter_kelly_conservative"
        assert typed_intent.target_exposure_pct == pytest.approx(5000.0, rel=1e-6)
        assert typed_intent.target_delta_pct == pytest.approx(5000.0, rel=1e-6)
        assert typed_intent.reduction_fraction is None

    def test_calculate_position_sizing_params_emits_policy_sizing_intent(self, calculator):
        """Legacy sizing output should now also surface Stage 1 sizing intent."""
        context = {
            "asset_pair": "BTCUSD",
            "market_data": {"type": "crypto"},
        }

        result = calculator.calculate_position_sizing_params(
            context=context,
            current_price=50000.0,
            action="BUY",
            has_existing_position=False,
            relevant_balance={"USD": 10000.0},
            balance_source="coinbase",
        )

        assert result["recommended_position_size"] is not None
        assert "policy_sizing_intent" in result
        assert result["policy_sizing_intent"]["semantic_action"] == "BUY"
        assert result["policy_sizing_intent"]["provider_agnostic"] is True
        assert result["policy_sizing_intent"]["sizing_anchor"] == "quarter_kelly_conservative"

    def test_hold_without_position_emits_zero_delta_policy_sizing_intent(self, calculator):
        """HOLD without a position should produce zero-delta intent."""
        result = calculator.calculate_position_sizing_params(
            context={"asset_pair": "BTCUSD"},
            current_price=50000.0,
            action="HOLD",
            has_existing_position=False,
            relevant_balance={"USD": 10000.0},
            balance_source="coinbase",
        )

        intent = result["policy_sizing_intent"]
        assert intent["semantic_action"] == "HOLD"
        assert intent["target_delta_pct"] == 0.0
        assert intent["target_exposure_pct"] is None

    def test_calculate_position_sizing_params_no_balance_crypto(self, calculator):
        """Test minimum order size fallback for crypto without balance."""
        context = {
            "asset_pair": "BTCUSD",
            "market_data": {"type": "crypto"},
        }

        result = calculator.calculate_position_sizing_params(
            context=context,
            current_price=50000.0,
            action="BUY",
            has_existing_position=False,
            relevant_balance={},  # No balance
            balance_source="coinbase",
        )

        # Should use minimum crypto order size ($10)
        expected_size = MIN_ORDER_SIZE_CRYPTO / 50000.0
        assert result["recommended_position_size"] == pytest.approx(expected_size, rel=1e-6)

    def test_calculate_position_sizing_params_no_balance_forex(self, calculator):
        """Test minimum order size fallback for forex without balance."""
        context = {
            "asset_pair": "EUR_USD",
            "market_data": {"type": "forex"},
        }

        result = calculator.calculate_position_sizing_params(
            context=context,
            current_price=1.10,
            action="BUY",
            has_existing_position=False,
            relevant_balance={},  # No balance
            balance_source="oanda",
        )

        # Should use minimum forex order size ($1)
        expected_size = MIN_ORDER_SIZE_FOREX / 1.10
        assert result["recommended_position_size"] == pytest.approx(expected_size, rel=1e-6)

    def test_calculate_position_sizing_params_legacy_percentage_conversion(self):
        """Test automatic conversion of realistic legacy percentage values (>1) to decimals."""
        config = {
            "agent": {
                "risk_percentage": 1.5,  # Legacy 1.5% stored as 1.5 instead of 0.015
                "sizing_stop_loss_percentage": 2.5,  # Legacy 2.5% stored as 2.5 instead of 0.025
                "use_dynamic_stop_loss": False,  # Disable dynamic to test fixed conversion
            }
        }
        calculator = PositionSizingCalculator(config)

        context = {"asset_pair": "BTCUSD"}

        result = calculator.calculate_position_sizing_params(
            context=context,
            current_price=50000.0,
            action="BUY",
            has_existing_position=False,
            relevant_balance={"USD": 10000.0},
            balance_source="test",
        )

        # Conversion happens: values > 1 are divided by 100 and then used normally.
        assert result["risk_percentage"] == pytest.approx(0.015, rel=1e-9)
        assert result["sizing_stop_loss_percentage"] == pytest.approx(0.025, rel=1e-9)

    def test_calculate_position_sizing_params_kelly_criterion(self):
        """Test that Kelly Criterion mode is used when enabled."""
        config = {
            "agent": {
                "risk_percentage": 0.01,
                "sizing_stop_loss_percentage": 0.02,
                "use_kelly_criterion": True,
                "kelly_criterion": {
                    "default_win_rate": 0.55,
                    "default_avg_win": 100.0,
                    "default_avg_loss": 75.0,
                },
            }
        }

        calculator = PositionSizingCalculator(config)

        context = {
            "asset_pair": "BTCUSD",
            "performance_metrics": {
                "win_rate": 0.60,
                "avg_win": 120.0,
                "avg_loss": 80.0,
            },
        }

        result = calculator.calculate_position_sizing_params(
            context=context,
            current_price=50000.0,
            action="BUY",
            has_existing_position=False,
            relevant_balance={"USD": 10000.0},
            balance_source="test",
        )

        # Kelly calculator is available in codebase, so should use it
        assert result["position_sizing_method"] == "kelly_criterion"
        assert result["recommended_position_size"] > 0
        assert "kelly_details" in result

    def test_calculate_position_sizing_params_dynamic_stop_loss(self, dynamic_stop_loss_config):
        """Test position sizing with dynamic stop loss enabled."""
        calculator = PositionSizingCalculator(dynamic_stop_loss_config)

        context = {
            "asset_pair": "BTCUSD",
            "monitoring_context": {
                "multi_timeframe_pulse": {
                    "1d": {"atr": 2000.0}  # $2000 ATR
                }
            },
        }

        result = calculator.calculate_position_sizing_params(
            context=context,
            current_price=50000.0,
            action="BUY",
            has_existing_position=False,
            relevant_balance={"USD": 10000.0},
            balance_source="test",
        )

        # ATR-based: (2000 * 2.0) / 50000 = 0.08 = 8%
        # But max is 5%, so should be capped at 5%
        assert result["sizing_stop_loss_percentage"] == 0.05

    def test_calculate_position_sizing_params_zero_price(self, calculator):
        """Test position sizing with zero price (edge case)."""
        context = {"asset_pair": "BTCUSD"}

        result = calculator.calculate_position_sizing_params(
            context=context,
            current_price=0.0,  # Zero price
            action="BUY",
            has_existing_position=False,
            relevant_balance={},
            balance_source="test",
        )

        assert result["recommended_position_size"] == 0

    # =========================================================================
    # UTILITY METHOD TESTS
    # =========================================================================

    def test_get_kelly_parameters_from_context(self, calculator):
        """Test Kelly parameter extraction from context."""
        context = {
            "performance_metrics": {
                "win_rate": 0.60,
                "avg_win": 150.0,
                "avg_loss": 100.0,
                "payoff_ratio": 1.5,
            }
        }

        params = calculator._get_kelly_parameters(context, {})

        assert params["win_rate"] == 0.60
        assert params["avg_win"] == 150.0
        assert params["avg_loss"] == 100.0
        assert params["payoff_ratio"] == 1.5

    def test_get_kelly_parameters_defaults(self, calculator):
        """Test Kelly parameter defaults when context empty."""
        context = {}
        kelly_config = {
            "default_win_rate": 0.55,
            "default_avg_win": 100.0,
            "default_avg_loss": 75.0,
        }

        params = calculator._get_kelly_parameters(context, kelly_config)

        assert params["win_rate"] == 0.55
        assert params["avg_win"] == 100.0
        assert params["avg_loss"] == 75.0
        assert params["payoff_ratio"] == pytest.approx(100.0 / 75.0)

    def test_get_kelly_parameters_bounds_checking(self, calculator):
        """Test Kelly parameters are bounded to valid ranges."""
        context = {
            "performance_metrics": {
                "win_rate": 1.5,  # Invalid: > 1.0
                "avg_win": -50.0,  # Invalid: negative
                "avg_loss": -30.0,  # Invalid: negative
            }
        }

        params = calculator._get_kelly_parameters(context, {})

        assert 0.0 <= params["win_rate"] <= 1.0
        assert params["avg_win"] >= 0.0
        assert params["avg_loss"] >= 0.0
        assert params["payoff_ratio"] >= 0.0

    def test_determine_position_type_buy(self):
        """Test position type determination for BUY action."""
        assert PositionSizingCalculator._determine_position_type("BUY") == "LONG"

    def test_determine_position_type_sell(self):
        """Test position type determination for SELL action."""
        assert PositionSizingCalculator._determine_position_type("SELL") == "SHORT"

    def test_determine_position_type_hold(self):
        """Test position type determination for HOLD action."""
        assert PositionSizingCalculator._determine_position_type("HOLD") is None

    # =========================================================================
    # INTEGRATION TESTS (Complex Scenarios)
    # =========================================================================

    def test_full_pipeline_crypto_buy(self):
        """Integration test: Full pipeline for crypto BUY with dynamic stop loss."""
        config = {
            "agent": {
                "risk_percentage": 0.02,  # 2% risk
                "sizing_stop_loss_percentage": 0.03,
                "use_dynamic_stop_loss": True,
                "atr_multiplier": 2.5,
                "min_stop_loss_pct": 0.01,
                "max_stop_loss_pct": 0.06,
            }
        }
        calculator = PositionSizingCalculator(config)

        context = {
            "asset_pair": "BTCUSD",
            "market_data": {"type": "crypto"},
            "monitoring_context": {
                "multi_timeframe_pulse": {
                    "1d": {"atr": 1500.0}
                }
            },
        }

        result = calculator.calculate_position_sizing_params(
            context=context,
            current_price=50000.0,
            action="BUY",
            has_existing_position=False,
            relevant_balance={"USD": 10000.0},
            balance_source="coinbase",
        )

        # Verify complete result
        assert result["position_sizing_method"] == "risk_based"
        assert result["recommended_position_size"] > 0
        assert result["stop_loss_price"] < 50000.0
        assert 0.01 <= result["sizing_stop_loss_percentage"] <= 0.06
        assert result["risk_percentage"] == 0.02

    def test_full_pipeline_forex_sell(self):
        """Integration test: Full pipeline for forex SELL with fixed stop loss."""
        config = {
            "agent": {
                "risk_percentage": 0.015,  # 1.5% risk
                "sizing_stop_loss_percentage": 0.025,  # 2.5% stop
                "use_dynamic_stop_loss": False,
            }
        }
        calculator = PositionSizingCalculator(config)

        context = {
            "asset_pair": "EUR_USD",
            "market_data": {"type": "forex"},
        }

        result = calculator.calculate_position_sizing_params(
            context=context,
            current_price=1.10,
            action="SELL",
            has_existing_position=False,
            relevant_balance={"USD": 5000.0},
            balance_source="oanda",
        )

        # Verify complete result for SHORT position
        assert result["recommended_position_size"] > 0
        assert result["stop_loss_price"] > 1.10  # Stop above entry for SHORT
        assert result["sizing_stop_loss_percentage"] == 0.025
        assert result["risk_percentage"] == 0.015


# =============================================================================
# EDGE CASE TESTS
# =============================================================================

class TestPositionSizingEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_extremely_small_account_balance(self):
        """Test position sizing with very small account balance."""
        config = {"agent": {"risk_percentage": 0.01, "sizing_stop_loss_percentage": 0.02}}
        calculator = PositionSizingCalculator(config)

        # Account balance: $1
        position_size = calculator.calculate_position_size(
            account_balance=1.0,
            risk_percentage=0.01,
            entry_price=50000.0,
            stop_loss_percentage=0.02,
        )

        # Should still calculate: $1 * 0.01 / ($50k * 0.02) = 0.00001
        assert position_size > 0
        assert position_size < 0.001

    def test_extremely_large_account_balance(self):
        """Test position sizing with very large account balance."""
        config = {"agent": {}}
        calculator = PositionSizingCalculator(config)

        # Account balance: $1 billion
        position_size = calculator.calculate_position_size(
            account_balance=1_000_000_000.0,
            risk_percentage=0.01,
            entry_price=50000.0,
            stop_loss_percentage=0.02,
        )

        # Should calculate correctly without overflow
        expected = 1_000_000_000.0 * 0.01 / (50000.0 * 0.02)
        assert position_size == pytest.approx(expected, rel=1e-6)

    def test_multiple_balance_currencies(self):
        """Test position sizing with balance in multiple currencies."""
        config = {"agent": {"risk_percentage": 0.01, "sizing_stop_loss_percentage": 0.02}}
        calculator = PositionSizingCalculator(config)

        context = {"asset_pair": "BTCUSD"}

        result = calculator.calculate_position_sizing_params(
            context=context,
            current_price=50000.0,
            action="BUY",
            has_existing_position=False,
            relevant_balance={"USD": 5000.0, "BTC": 0.1},  # Multiple currencies
            balance_source="test",
        )

        # Should sum all balance values
        total_balance = 5000.0 + 0.1  # USD + BTC value
        assert result["recommended_position_size"] > 0

    def test_empty_context(self):
        """Test position sizing with minimal/empty context."""
        config = {"agent": {}}
        calculator = PositionSizingCalculator(config)

        result = calculator.calculate_position_sizing_params(
            context={},  # Empty context
            current_price=100.0,
            action="BUY",
            has_existing_position=False,
            relevant_balance={"USD": 1000.0},
            balance_source="test",
        )

        # Should still work with defaults
        assert result["recommended_position_size"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])


    def test_calculate_position_sizing_params_recovers_forex_balance_from_context_snapshot(self, calculator):
        context = {
            "asset_pair": "EURUSD",
            "market_data": {"type": "forex"},
            "balance_snapshot": {"oanda_USD": 166.72},
        }

        result = calculator.calculate_position_sizing_params(
            context=context,
            current_price=1.08,
            action="BUY",
            has_existing_position=False,
            relevant_balance={},
            balance_source="Oanda",
        )

        assert result["recommended_position_size"] is not None
        assert result["recommended_position_size"] > 0


import logging


class TestPositionSizingLogBehavior:
    def test_hold_without_position_does_not_emit_no_valid_balance_warning(self, caplog):
        calculator = PositionSizingCalculator({"agent": {"risk_percentage": 0.01, "sizing_stop_loss_percentage": 0.02, "use_dynamic_stop_loss": False, "use_kelly_criterion": False}})
        with caplog.at_level(logging.INFO):
            result = calculator.calculate_position_sizing_params(
                context={"asset_pair": "BTCUSD", "market_data": {"type": "crypto"}},
                current_price=50000.0,
                action="HOLD",
                has_existing_position=False,
                relevant_balance={"FUTURES_USD": 749.04, "SPOT_USD": 0.0},
                balance_source="Coinbase",
            )

        assert result["recommended_position_size"] == 0
        assert "No valid Coinbase balance - using minimum order size" not in caplog.text
        assert "HOLD without existing position - no position sizing needed" in caplog.text

    def test_policy_open_short_uses_valid_coinbase_balance_without_fallback_warning(self, caplog):
        calculator = PositionSizingCalculator({"agent": {"risk_percentage": 0.01, "sizing_stop_loss_percentage": 0.02, "use_dynamic_stop_loss": False, "use_kelly_criterion": False}})
        with caplog.at_level(logging.INFO):
            result = calculator.calculate_position_sizing_params(
                context={"asset_pair": "ETHUSD", "market_data": {"type": "crypto"}},
                current_price=2000.0,
                action="OPEN_SMALL_SHORT",
                has_existing_position=False,
                relevant_balance={"FUTURES_USD": 329.86, "SPOT_USD": 0.0},
                balance_source="Coinbase",
            )

        assert result["recommended_position_size"] is not None
        assert result["recommended_position_size"] > 0
        assert "No valid Coinbase balance - using minimum order size" not in caplog.text
        assert "Position sizing:" in caplog.text


    def test_policy_open_short_minimum_sizing_uses_short_stop_loss_direction(self):
        calculator = PositionSizingCalculator({"agent": {"risk_percentage": 0.01, "sizing_stop_loss_percentage": 0.02, "use_dynamic_stop_loss": False, "use_kelly_criterion": False}})
        result = calculator.calculate_position_sizing_params(
            context={"asset_pair": "ETHUSD", "market_data": {"type": "crypto"}},
            current_price=2000.0,
            action="OPEN_SMALL_SHORT",
            has_existing_position=False,
            relevant_balance={"USD": 0.0},
            balance_source="Coinbase",
        )
        assert result["stop_loss_price"] > 2000.0

    def test_policy_open_long_minimum_sizing_uses_long_stop_loss_direction(self):
        calculator = PositionSizingCalculator({"agent": {"risk_percentage": 0.01, "sizing_stop_loss_percentage": 0.02, "use_dynamic_stop_loss": False, "use_kelly_criterion": False}})
        result = calculator.calculate_position_sizing_params(
            context={"asset_pair": "ETHUSD", "market_data": {"type": "crypto"}},
            current_price=2000.0,
            action="OPEN_SMALL_LONG",
            has_existing_position=False,
            relevant_balance={"USD": 0.0},
            balance_source="Coinbase",
        )
        assert result["stop_loss_price"] < 2000.0

    def test_position_sizing_input_debug_does_not_emit_critical(self, caplog):
        calculator = PositionSizingCalculator({"agent": {"risk_percentage": 0.01, "sizing_stop_loss_percentage": 0.02, "use_dynamic_stop_loss": False, "use_kelly_criterion": False}})
        with caplog.at_level(logging.DEBUG):
            calculator.calculate_position_sizing_params(
                context={"asset_pair": "BTCUSD", "market_data": {"type": "crypto"}},
                current_price=50000.0,
                action="BUY",
                has_existing_position=False,
                relevant_balance={"FUTURES_USD": 749.04, "SPOT_USD": 0.0},
                balance_source="Coinbase",
            )

        assert "POSITION_SIZING INPUT" in caplog.text
        assert all(record.levelno < logging.CRITICAL for record in caplog.records if "POSITION_SIZING INPUT" in record.getMessage())


    def test_close_short_with_existing_position_does_not_emit_min_order_warning(self, caplog):
        calculator = PositionSizingCalculator({"agent": {"risk_percentage": 0.01, "sizing_stop_loss_percentage": 0.02, "use_dynamic_stop_loss": False, "use_kelly_criterion": False}})
        with caplog.at_level(logging.INFO):
            result = calculator.calculate_position_sizing_params(
                context={"asset_pair": "BTCUSD", "market_data": {"type": "crypto"}},
                current_price=70867.56,
                action="CLOSE_SHORT",
                has_existing_position=True,
                relevant_balance={"FUTURES_USD": 198.13, "SPOT_USD": 0.0},
                balance_source="Coinbase",
            )

        assert result["recommended_position_size"] == 0
        assert "No valid Coinbase balance - using minimum order size" not in caplog.text
        assert "Position sizing skipped" in caplog.text
