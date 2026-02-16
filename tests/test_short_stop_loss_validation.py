"""
Unit tests for SHORT position stop-loss validation.

Tests Issue #3 fix:
- Stop-loss percentage bounds checking
- Stop-loss price validation for LONG positions
- Stop-loss price validation for SHORT positions
- Minimum distance validation
"""

import pytest
import logging
from finance_feedback_engine.decision_engine.position_sizing import PositionSizingCalculator


class TestStopLossValidation:
    """Test stop-loss validation in position sizing."""

    @pytest.fixture
    def position_sizing_calc(self):
        """Create a position sizing calculator instance."""
        config = {
            "decision_engine": {
                "position_sizing": {
                    "risk_per_trade": 0.02,
                    "default_stop_loss_percentage": 0.02,
                }
            }
        }
        return PositionSizingCalculator(config)

    @pytest.fixture
    def base_context(self):
        """Base context for position sizing calculations."""
        return {
            "market_data": {"close": 50000.0, "type": "crypto"},
            "config": {},
            "asset_pair": "BTC-USD",
        }

    def test_minimum_stop_loss_enforcement_long(self, position_sizing_calc, base_context, caplog):
        """Test that stop-loss below minimum (0.5%) is adjusted for LONG."""
        with caplog.at_level(logging.WARNING):
            result = position_sizing_calc.calculate_position_sizing_params(
                context=base_context,
                current_price=50000.0,
                action="BUY",  # LONG position
                has_existing_position=False,
                relevant_balance={"total": 10000.0},
                balance_source="FUTURES_USD",
            )

            # Check that if a very small stop-loss was somehow set,
            # it gets adjusted to at least 0.5%
            stop_loss_price = result.get("stop_loss_price", 0)
            stop_loss_pct = result.get("sizing_stop_loss_percentage", 0)

            # Minimum should be 0.005 (0.5%)
            assert stop_loss_pct >= 0.005, f"Stop-loss % {stop_loss_pct} below minimum 0.005"

            # For LONG: stop-loss should be below entry
            assert (
                stop_loss_price < 50000.0
            ), f"LONG stop-loss {stop_loss_price} should be below entry 50000"

    def test_maximum_stop_loss_enforcement_long(self, position_sizing_calc, base_context, caplog):
        """Test that stop-loss above maximum (50%) is capped for LONG."""
        # Artificially high stop-loss percentage
        base_context["config"]["decision_engine"] = {
            "position_sizing": {"default_stop_loss_percentage": 0.75}  # 75% - way too high
        }

        with caplog.at_level(logging.WARNING):
            result = position_sizing_calc.calculate_position_sizing_params(
                context=base_context,
                current_price=50000.0,
                action="BUY",
                has_existing_position=False,
                relevant_balance={"total": 10000.0},
                balance_source="FUTURES_USD",
            )

            stop_loss_pct = result.get("sizing_stop_loss_percentage", 0)

            # Should be capped at 0.50 (50%)
            assert stop_loss_pct <= 0.50, f"Stop-loss % {stop_loss_pct} exceeds maximum 0.50"

    def test_short_stop_loss_above_entry(self, position_sizing_calc, base_context):
        """Test that SHORT stop-loss is ABOVE entry price."""
        result = position_sizing_calc.calculate_position_sizing_params(
            context=base_context,
            current_price=50000.0,
            action="SELL",  # SHORT position
            has_existing_position=False,
            relevant_balance={"total": 10000.0},
            balance_source="FUTURES_USD",
        )

        stop_loss_price = result.get("stop_loss_price", 0)

        # For SHORT: stop-loss MUST be ABOVE entry (liquidation on price rise)
        assert (
            stop_loss_price > 50000.0
        ), f"SHORT stop-loss {stop_loss_price} should be ABOVE entry 50000"

    def test_long_stop_loss_below_entry(self, position_sizing_calc, base_context):
        """Test that LONG stop-loss is BELOW entry price."""
        result = position_sizing_calc.calculate_position_sizing_params(
            context=base_context,
            current_price=50000.0,
            action="BUY",  # LONG position
            has_existing_position=False,
            relevant_balance={"total": 10000.0},
            balance_source="FUTURES_USD",
        )

        stop_loss_price = result.get("stop_loss_price", 0)

        # For LONG: stop-loss MUST be BELOW entry (liquidation on price drop)
        assert (
            stop_loss_price < 50000.0
        ), f"LONG stop-loss {stop_loss_price} should be BELOW entry 50000"

    def test_minimum_distance_enforcement_long(self, position_sizing_calc, base_context, caplog):
        """Test that stop-loss too close to entry is adjusted for LONG."""
        # Force a very small stop-loss percentage
        base_context["config"]["decision_engine"] = {
            "position_sizing": {"default_stop_loss_percentage": 0.001}  # 0.1% - too close
        }

        with caplog.at_level(logging.WARNING):
            result = position_sizing_calc.calculate_position_sizing_params(
                context=base_context,
                current_price=50000.0,
                action="BUY",
                has_existing_position=False,
                relevant_balance={"total": 10000.0},
                balance_source="FUTURES_USD",
            )

            stop_loss_price = result.get("stop_loss_price", 0)
            stop_loss_pct = result.get("sizing_stop_loss_percentage", 0)

            # Should be adjusted to at least 0.5%
            assert stop_loss_pct >= 0.005, f"Stop-loss % {stop_loss_pct} below minimum 0.005"

            # Distance should be at least 0.5% of entry
            min_distance = 50000.0 * 0.005  # $250
            actual_distance = abs(50000.0 - stop_loss_price)
            assert (
                actual_distance >= min_distance
            ), f"Distance {actual_distance} below minimum {min_distance}"

    def test_minimum_distance_enforcement_short(self, position_sizing_calc, base_context, caplog):
        """Test that stop-loss too close to entry is adjusted for SHORT."""
        # Force a very small stop-loss percentage
        base_context["config"]["decision_engine"] = {
            "position_sizing": {"default_stop_loss_percentage": 0.001}  # 0.1% - too close
        }

        with caplog.at_level(logging.WARNING):
            result = position_sizing_calc.calculate_position_sizing_params(
                context=base_context,
                current_price=50000.0,
                action="SELL",  # SHORT
                has_existing_position=False,
                relevant_balance={"total": 10000.0},
                balance_source="FUTURES_USD",
            )

            stop_loss_price = result.get("stop_loss_price", 0)
            stop_loss_pct = result.get("sizing_stop_loss_percentage", 0)

            # Should be adjusted to at least 0.5%
            assert stop_loss_pct >= 0.005, f"Stop-loss % {stop_loss_pct} below minimum 0.005"

            # Distance should be at least 0.5% of entry
            min_distance = 50000.0 * 0.005  # $250
            actual_distance = abs(stop_loss_price - 50000.0)
            assert (
                actual_distance >= min_distance
            ), f"Distance {actual_distance} below minimum {min_distance}"

            # For SHORT: stop-loss must be ABOVE entry
            assert (
                stop_loss_price > 50000.0
            ), f"SHORT stop-loss {stop_loss_price} should be above entry 50000"

    def test_invalid_current_price_zero(self, position_sizing_calc, base_context, caplog):
        """Test that current_price = 0 is handled gracefully."""
        with caplog.at_level(logging.ERROR):
            result = position_sizing_calc.calculate_position_sizing_params(
                context=base_context,
                current_price=0.0,  # Invalid price
                action="BUY",
                has_existing_position=False,
                relevant_balance={"total": 10000.0},
                balance_source="FUTURES_USD",
            )

            stop_loss_price = result.get("stop_loss_price", None)

            # Should default to 0 with error logged
            assert stop_loss_price == 0, f"Expected stop_loss_price=0 for invalid price, got {stop_loss_price}"
            assert "Invalid current_price" in caplog.text

    def test_invalid_current_price_negative(self, position_sizing_calc, base_context, caplog):
        """Test that negative current_price is handled gracefully."""
        with caplog.at_level(logging.ERROR):
            result = position_sizing_calc.calculate_position_sizing_params(
                context=base_context,
                current_price=-1000.0,  # Invalid negative price
                action="BUY",
                has_existing_position=False,
                relevant_balance={"total": 10000.0},
                balance_source="FUTURES_USD",
            )

            stop_loss_price = result.get("stop_loss_price", None)

            # Should default to 0 with error logged
            assert stop_loss_price == 0, f"Expected stop_loss_price=0 for negative price, got {stop_loss_price}"
            assert "Invalid current_price" in caplog.text

    def test_short_typical_stop_loss_calculation(self, position_sizing_calc, base_context):
        """Test typical SHORT stop-loss calculation (2% above entry)."""
        result = position_sizing_calc.calculate_position_sizing_params(
            context=base_context,
            current_price=50000.0,
            action="SELL",
            has_existing_position=False,
            relevant_balance={"total": 10000.0},
            balance_source="FUTURES_USD",
        )

        stop_loss_price = result.get("stop_loss_price", 0)
        stop_loss_pct = result.get("sizing_stop_loss_percentage", 0)

        # Assuming default 2% stop-loss
        expected_sl_price = 50000.0 * (1 + 0.02)  # $51,000

        # Allow small tolerance for rounding
        assert abs(stop_loss_price - expected_sl_price) < 100, (
            f"SHORT stop-loss {stop_loss_price} not close to expected {expected_sl_price}"
        )

        # Verify it's above entry
        assert stop_loss_price > 50000.0, "SHORT stop-loss should be above entry"

    def test_long_typical_stop_loss_calculation(self, position_sizing_calc, base_context):
        """Test typical LONG stop-loss calculation (2% below entry)."""
        result = position_sizing_calc.calculate_position_sizing_params(
            context=base_context,
            current_price=50000.0,
            action="BUY",
            has_existing_position=False,
            relevant_balance={"total": 10000.0},
            balance_source="FUTURES_USD",
        )

        stop_loss_price = result.get("stop_loss_price", 0)
        stop_loss_pct = result.get("sizing_stop_loss_percentage", 0)

        # Assuming default 2% stop-loss
        expected_sl_price = 50000.0 * (1 - 0.02)  # $49,000

        # Allow small tolerance for rounding
        assert abs(stop_loss_price - expected_sl_price) < 100, (
            f"LONG stop-loss {stop_loss_price} not close to expected {expected_sl_price}"
        )

        # Verify it's below entry
        assert stop_loss_price < 50000.0, "LONG stop-loss should be below entry"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
