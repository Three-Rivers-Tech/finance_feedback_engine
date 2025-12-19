"""
Test suite for PnL semantics and consistency.

Tests the distinction between realized and unrealized PnL:
- realized_pnl: Profit/loss from closed trades
- unrealized_pnl: Mark-to-market loss/gain from equity curve
- total_pnl: Sum of both

When total_trades=0, realized_pnl must be 0 and unrealized_pnl must equal total_pnl.
"""

import json
from pathlib import Path

import pytest

RESULTS_FILE = Path("data/backtest_results/full_year_summary_20251208_150530.json")


@pytest.fixture
def backtest_results():
    """Load backtest results JSON, skip if not found."""
    if not RESULTS_FILE.exists():
        pytest.skip(f"Results file not found: {RESULTS_FILE}")

    with open(RESULTS_FILE, "r") as f:
        return json.load(f)


@pytest.mark.external_service
def test_pnl_consistency_zero_trades(backtest_results):
    """
    When total_trades=0, PnL must be entirely unrealized.

    This test validates that the backtest results distinguish between:
    - realized_pnl (0 when no trades executed)
    - unrealized_pnl (mark-to-market changes)
    - total_pnl (should equal unrealized_pnl when realized_pnl=0)
    """
    results = backtest_results

    # Test annual level
    annual_total_trades = results.get("total_trades", 0)
    annual_realized_pnl = results.get("realized_pnl", 0)
    annual_unrealized_pnl = results.get("unrealized_pnl", 0)
    annual_total_pnl = results.get("total_pnl", 0)

    # Verify consistency
    if annual_total_trades == 0:
        assert (
            annual_realized_pnl == 0
        ), f"When total_trades=0, realized_pnl must be 0, got {annual_realized_pnl}"
        assert abs(annual_unrealized_pnl - annual_total_pnl) < 0.01, (
            f"When total_trades=0, unrealized_pnl must equal total_pnl. "
            f"unrealized={annual_unrealized_pnl}, total={annual_total_pnl}"
        )

    # Test quarterly level
    for q in results.get("quarterly_breakdown", []):
        q_total_trades = q.get("total_trades", 0)
        q_realized_pnl = q.get("realized_pnl", 0)
        q_unrealized_pnl = q.get("unrealized_pnl", 0)
        q_total_pnl = q.get("total_pnl", 0)
        q_name = q.get("quarter", "Unknown")

        # Verify consistency
        if q_total_trades == 0:
            assert (
                q_realized_pnl == 0
            ), f"{q_name}: When total_trades=0, realized_pnl must be 0, got {q_realized_pnl}"
            assert abs(q_unrealized_pnl - q_total_pnl) < 0.01, (
                f"{q_name}: When total_trades=0, unrealized_pnl must equal total_pnl. "
                f"unrealized={q_unrealized_pnl}, total={q_total_pnl}"
            )


def test_pnl_summation(backtest_results):
    """
    Test that quarterly PnL values sum to annual PnL.
    """
    results = backtest_results

    annual_realized_pnl = results.get("realized_pnl", 0)
    annual_unrealized_pnl = results.get("unrealized_pnl", 0)
    annual_total_pnl = results.get("total_pnl", 0)

    quarterly_realized_sum = sum(
        q.get("realized_pnl", 0) for q in results.get("quarterly_breakdown", [])
    )
    quarterly_unrealized_sum = sum(
        q.get("unrealized_pnl", 0) for q in results.get("quarterly_breakdown", [])
    )
    quarterly_total_sum = sum(
        q.get("total_pnl", 0) for q in results.get("quarterly_breakdown", [])
    )

    # Allow small floating point differences
    tolerance = 0.1

    assert abs(quarterly_realized_sum - annual_realized_pnl) < tolerance, (
        f"Quarterly realized_pnl sum ({quarterly_realized_sum}) "
        f"does not match annual ({annual_realized_pnl})"
    )

    assert abs(quarterly_unrealized_sum - annual_unrealized_pnl) < tolerance, (
        f"Quarterly unrealized_pnl sum ({quarterly_unrealized_sum}) "
        f"does not match annual ({annual_unrealized_pnl})"
    )

    assert abs(quarterly_total_sum - annual_total_pnl) < tolerance, (
        f"Quarterly total_pnl sum ({quarterly_total_sum}) "
        f"does not match annual ({annual_total_pnl})"
    )


def test_win_rate_consistency(backtest_results):
    """
    Test that win_rate is 0 when total_trades=0.
    """
    results = backtest_results

    # Annual level
    if results.get("total_trades", 0) == 0:
        assert (
            results.get("overall_win_rate", 0) == 0
        ), f"When total_trades=0, win_rate must be 0, got {results.get('overall_win_rate')}"

    # Quarterly level
    for q in results.get("quarterly_breakdown", []):
        if q.get("total_trades", 0) == 0:
            assert (
                q.get("win_rate", 0) == 0
            ), f"{q.get('quarter')}: When total_trades=0, win_rate must be 0, got {q.get('win_rate')}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
