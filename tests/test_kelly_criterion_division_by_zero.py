"""
Test suite for Kelly Criterion division by zero bug (THR-87).

Tests that payoff_ratio = 0 scenarios are handled gracefully
without causing division by zero.
"""

import pytest
import math
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
            "max_position_size_pct": 0.1,
        }
    }
    return KellyCriterionCalculator(config)


class TestDivisionByZeroFixes:
    """Test that all division by zero scenarios are handled (THR-87)."""

    def test_explicit_zero_payoff_ratio(self, kelly_calculator):
        """
        SCENARIO 1: User explicitly passes payoff_ratio=0.0
        Should return 0, not crash.
        """
        win_rate = 0.6
        avg_win = 100.0
        avg_loss = 50.0

        kelly_fraction = kelly_calculator.calculate_kelly_fraction(
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            payoff_ratio=0.0,
        )

        assert kelly_fraction == 0.0
        assert not math.isnan(kelly_fraction)
        assert kelly_fraction != float("inf")

    def test_zero_avg_win(self, kelly_calculator):
        """
        SCENARIO 2: avg_win = 0 results in payoff_ratio = 0
        Should return 0, not crash.
        """
        win_rate = 0.6
        avg_win = 0.0
        avg_loss = 100.0

        kelly_fraction = kelly_calculator.calculate_kelly_fraction(
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
        )

        assert kelly_fraction == 0.0
        assert not math.isnan(kelly_fraction)
        assert kelly_fraction != float("inf")

    def test_negative_payoff_ratio(self, kelly_calculator):
        """
        SCENARIO 3: Negative payoff_ratio (invalid)
        Should return 0, not crash.
        """
        win_rate = 0.60
        avg_win = 100.0
        avg_loss = 50.0


        kelly_fraction = kelly_calculator.calculate_kelly_fraction(
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            payoff_ratio=-1.0,
        )

        assert kelly_fraction == 0.0

    def test_position_size_with_zero_payoff_ratio(self, kelly_calculator):
        """
        Position sizing should return 0 units when payoff_ratio=0.
        """
        account_balance = 10000.0
        win_rate = 0.60
        avg_win = 100.0
        avg_loss = 50.0
        current_price = 100.0

        position_size, details = kelly_calculator.calculate_position_size(
            account_balance=account_balance,
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            current_price=current_price,
            payoff_ratio=0.0,
        )

        # Should return 0 position size, not infinity
        assert position_size == 0
        assert details["kelly_fraction"] == 0.0
        assert details["position_size_dollars"] == 0.0
        assert details["position_size_units"] == 0.0
        assert not math.isnan(position_size)
        assert position_size != float('inf')
            import math
            assert not math.isnan(kelly_fraction), "kelly_fraction is NaN for negative payoff ratio"
            assert kelly_fraction != float("inf"), "kelly_fraction is inf for negative payoff ratio"
            assert kelly_fraction != -float("inf"), "kelly_fraction is -inf for negative payoff ratio"

    def test_both_avg_win_and_loss_zero(self, kelly_calculator):
        """
        Edge case: Both avg_win and avg_loss are zero.
        Should handle gracefully.
        """
        win_rate = 0.0
        avg_win = 0.0
        avg_loss = 0.0

        kelly_fraction = kelly_calculator.calculate_kelly_fraction(
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
        )

        # Should either return 0 or use the large payoff ratio path
        assert kelly_fraction >= 0.0
        assert not math.isnan(kelly_fraction)
        assert kelly_fraction != float('inf')

    def test_negative_avg_win(self, kelly_calculator):
        """
        Invalid case: Negative average win.
        Should handle gracefully.
        """
        win_rate = 0.6
        avg_win = -100.0
        avg_loss = 50.0

        kelly_fraction = kelly_calculator.calculate_kelly_fraction(
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
        )

        # Should return 0 for invalid inputs
        assert kelly_fraction == 0.0

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
