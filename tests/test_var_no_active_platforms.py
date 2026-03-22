import logging

from finance_feedback_engine.risk.var_calculator import VaRCalculator


def test_var_with_no_active_platforms_does_not_log_dual_portfolio(caplog):
    calc = VaRCalculator()
    with caplog.at_level(logging.INFO):
        result = calc.calculate_dual_portfolio_var({}, {}, {}, {}, confidence_level=0.95)

    assert result["active_platforms"] == []
    assert result["combined_var"]["var_usd"] == 0.0
    assert "Dual-portfolio VaR:" not in caplog.text
    assert "No active-platform VaR inputs available" in caplog.text
