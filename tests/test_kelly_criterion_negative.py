"""
Test suite for Kelly Criterion negative fraction handling (THR-93).

Tests that negative Kelly fractions (indicating -EV trades) correctly
return 0 instead of being forced to a positive minimum.
"""

import pytest
from finance_feedback_engine.decision_engine.kelly_criterion import (
    KellyCriterionCalculator,
)


@pytest.fixture
def kelly_calculator():
    """Create Kelly Criterion calculator with standard config."""
    config = {
        "kelly_criterion": {
            "kelly_fraction_cap": 0.25,
            "kelly_fraction_multiplier": 0.5,
            "min_kelly_fraction": 0.001,
            "max_position_size_pct": 0.10,
        }
    }
    return KellyCriterionCalculator(config)


class TestNegativeKellyHandling:
    """Test that negative Kelly values are handled correctly (THR-93 bug fix)."""

    def test_negative_kelly_returns_zero_not_minimum(self, kelly_calculator):
        """
        When Kelly formula produces negative value (indicating -EV trade),
        should return 0, NOT the minimum kelly fraction (0.001).

        This is the core THR-93 bug fix.
        """
        # Low win rate + poor payoff ratio = negative Kelly
        win_rate = 0.40  # 40% win rate
        avg_win = 50.0  # Average win $50
        avg_loss = 100.0  # Average loss $100 (payoff ratio = 0.5)

        # Kelly formula: (b*p - q) / b = (0.5 * 0.4 - 0.6) / 0.5 = -0.8
        kelly_fraction = kelly_calculator.calculate_kelly_fraction(
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
        )

        # CRITICAL: Should return 0, not min_kelly_fraction (0.001)
        assert kelly_fraction == 0.0
        assert kelly_fraction != kelly_calculator.min_kelly_fraction

    def test_very_low_win_rate_produces_zero(self, kelly_calculator):
        """Low win rate should produce negative Kelly -> 0."""
        win_rate = 0.30  # 30% win rate
        avg_win = 100.0
        avg_loss = 100.0  # 1:1 payoff

        # Kelly = (1 * 0.3 - 0.7) / 1 = -0.4
        kelly_fraction = kelly_calculator.calculate_kelly_fraction(
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
        )

        assert kelly_fraction == 0.0

    def test_poor_payoff_ratio_produces_zero(self, kelly_calculator):
        """Poor payoff ratio should produce negative Kelly -> 0."""
        win_rate = 0.50  # 50% win rate
        avg_win = 50.0
        avg_loss = 200.0  # Payoff ratio = 0.25 (poor)

        # Kelly = (0.25 * 0.5 - 0.5) / 0.25 = -1.5
        kelly_fraction = kelly_calculator.calculate_kelly_fraction(
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
        )

        assert kelly_fraction == 0.0

    def test_break_even_produces_zero(self, kelly_calculator):
        """Break-even scenario (Kelly = 0) should return 0."""
        win_rate = 0.50  # 50% win rate
        avg_win = 100.0
        avg_loss = 100.0  # 1:1 payoff

        # Kelly = (1 * 0.5 - 0.5) / 1 = 0
        kelly_fraction = kelly_calculator.calculate_kelly_fraction(
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
        )

        assert kelly_fraction == 0.0

    def test_position_size_with_negative_kelly(self, kelly_calculator):
        """
        Position sizing should return 0 units when Kelly is negative.
        """
        account_balance = 10000.0
        win_rate = 0.40
        avg_win = 50.0
        avg_loss = 100.0
        current_price = 100.0

        position_size, details = kelly_calculator.calculate_position_size(
            account_balance=account_balance,
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            current_price=current_price,
        )

        # Should return 0 position size
        assert position_size == 0.0
        assert details["kelly_fraction"] == 0.0
        assert details["position_size_dollars"] == 0.0
        assert details["position_size_units"] == 0.0


class TestPositiveKellyStillWorks:
    """Test that positive Kelly values still work correctly after fix."""

    def test_positive_kelly_applies_minimum(self, kelly_calculator):
        """
        When Kelly is positive but very small, minimum should still apply.
        """
        win_rate = 0.51  # 51% win rate (barely +EV)
        avg_win = 100.0
        avg_loss = 100.0  # 1:1 payoff

        # Kelly = (1 * 0.51 - 0.49) / 1 = 0.02
        # After cap (0.25) and multiplier (0.5): 0.02 * 0.5 = 0.01
        # After minimum (0.001): max(0.01, 0.001) = 0.01
        kelly_fraction = kelly_calculator.calculate_kelly_fraction(
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
        )

        assert kelly_fraction > 0
        # Should be at least the minimum
        assert kelly_fraction >= kelly_calculator.min_kelly_fraction

    def test_good_kelly_scenario(self, kelly_calculator):
        """Test typical positive Kelly scenario."""
        win_rate = 0.60  # 60% win rate
        avg_win = 150.0
        avg_loss = 100.0  # 1.5:1 payoff ratio

        # Kelly = (1.5 * 0.6 - 0.4) / 1.5 = 0.333...
        # After cap (0.25): min(0.333, 0.25) = 0.25
        # After multiplier (0.5): 0.25 * 0.5 = 0.125
        # After minimum (0.001): max(0.125, 0.001) = 0.125
        kelly_fraction = kelly_calculator.calculate_kelly_fraction(
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
        )

        assert kelly_fraction > 0
        assert kelly_fraction == pytest.approx(0.125)

    def test_position_size_with_positive_kelly(self, kelly_calculator):
        """Position sizing should work correctly with positive Kelly."""
        account_balance = 10000.0
        win_rate = 0.60
        avg_win = 150.0
        avg_loss = 100.0
        current_price = 100.0

        position_size, details = kelly_calculator.calculate_position_size(
            account_balance=account_balance,
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            current_price=current_price,
        )

        # Should have non-zero position
        assert position_size > 0
        assert details["kelly_fraction"] > 0
        assert details["position_size_dollars"] > 0
        assert details["position_size_units"] > 0


class TestEdgeCases:
    """Test edge cases in Kelly calculation."""

    def test_zero_avg_loss_handled(self, kelly_calculator):
        """Zero average loss should be handled gracefully."""
        win_rate = 0.60
        avg_win = 150.0
        avg_loss = 0.0  # Edge case

        # Should not crash, should use large payoff ratio
        kelly_fraction = kelly_calculator.calculate_kelly_fraction(
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
        )

        # Should be capped at kelly_fraction_cap
        assert kelly_fraction > 0
        assert kelly_fraction <= kelly_calculator.kelly_fraction_cap * kelly_calculator.kelly_fraction_multiplier

    def test_win_rate_boundary_values(self, kelly_calculator):
        """Test win rate at boundaries (0, 0.5, 1)."""
        avg_win = 100.0
        avg_loss = 100.0

        # Win rate = 0 (never win)
        kelly_0 = kelly_calculator.calculate_kelly_fraction(
            win_rate=0.0,
            avg_win=avg_win,
            avg_loss=avg_loss,
        )
        assert kelly_0 == 0.0

        # Win rate = 0.5 (break even)
        kelly_50 = kelly_calculator.calculate_kelly_fraction(
            win_rate=0.5,
            avg_win=avg_win,
            avg_loss=avg_loss,
        )
        assert kelly_50 == 0.0

        # Win rate = 1.0 (always win)
        kelly_100 = kelly_calculator.calculate_kelly_fraction(
            win_rate=1.0,
            avg_win=avg_win,
            avg_loss=avg_loss,
        )
        assert kelly_100 > 0

    def test_invalid_win_rate_clipped(self, kelly_calculator):
        """Invalid win rates should be clipped to [0, 1]."""
        avg_win = 100.0
        avg_loss = 100.0

        # Win rate > 1 should be clipped to 1
        kelly_high = kelly_calculator.calculate_kelly_fraction(
            win_rate=1.5,
            avg_win=avg_win,
            avg_loss=avg_loss,
        )
        assert kelly_high > 0  # Should treat as win_rate=1.0

        # Win rate < 0 should be clipped to 0
        kelly_low = kelly_calculator.calculate_kelly_fraction(
            win_rate=-0.5,
            avg_win=avg_win,
            avg_loss=avg_loss,
        )
        assert kelly_low == 0.0  # Should treat as win_rate=0.0


class TestRealWorldScenarios:
    """Test realistic trading scenarios."""

    def test_losing_strategy_negative_kelly(self, kelly_calculator):
        """
        Realistic losing strategy should produce 0 Kelly.

        Example: 35% win rate, avg win $80, avg loss $100
        """
        win_rate = 0.35
        avg_win = 80.0
        avg_loss = 100.0

        kelly_fraction = kelly_calculator.calculate_kelly_fraction(
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
        )

        assert kelly_fraction == 0.0

    def test_marginal_strategy_small_positive_kelly(self, kelly_calculator):
        """
        Marginally profitable strategy should produce small positive Kelly.

        Example: 52% win rate, avg win $100, avg loss $100
        """
        win_rate = 0.52
        avg_win = 100.0
        avg_loss = 100.0

        kelly_fraction = kelly_calculator.calculate_kelly_fraction(
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
        )

        assert kelly_fraction > 0
        assert kelly_fraction >= kelly_calculator.min_kelly_fraction

    def test_strong_strategy_capped_kelly(self, kelly_calculator):
        """
        Very strong strategy should be capped at maximum.

        Example: 75% win rate, avg win $200, avg loss $50
        """
        win_rate = 0.75
        avg_win = 200.0
        avg_loss = 50.0

        kelly_fraction = kelly_calculator.calculate_kelly_fraction(
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
        )

        # Should be capped at kelly_fraction_cap * kelly_fraction_multiplier
        max_kelly = kelly_calculator.kelly_fraction_cap * kelly_calculator.kelly_fraction_multiplier
        assert kelly_fraction <= max_kelly


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
