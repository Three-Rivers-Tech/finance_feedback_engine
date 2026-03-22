import logging

from finance_feedback_engine.risk.correlation_analyzer import CorrelationAnalyzer
from finance_feedback_engine.risk.var_calculator import VaRCalculator


def _history(start, step, days=40):
    return [
        {"date": f"2024-01-{i+1:02d}", "price": start + i * step}
        for i in range(days)
    ]


def test_dual_portfolio_var_adapts_to_single_active_platform(caplog):
    calc = VaRCalculator()
    coinbase_holdings = {"BTCUSD": {"quantity": 1.0, "current_price": 50000.0}}
    coinbase_history = {"BTCUSD": _history(40000, 100)}

    with caplog.at_level(logging.INFO):
        result = calc.calculate_dual_portfolio_var(
            coinbase_holdings,
            coinbase_history,
            {},
            {},
            confidence_level=0.95,
        )

    assert result["active_platforms"] == ["coinbase"]
    assert result["total_portfolio_value"] == result["coinbase_var"]["portfolio_value"]
    assert result["combined_var"]["portfolio_value"] == result["coinbase_var"]["portfolio_value"]
    assert result["combined_var"]["var_usd"] == result["coinbase_var"]["var_usd"]
    assert "oanda_var" not in result
    assert "Single-platform VaR: coinbase=" in caplog.text
    assert "Dual-portfolio VaR:" not in caplog.text


def test_dual_platform_correlations_adapt_to_single_active_platform(caplog):
    analyzer = CorrelationAnalyzer()
    coinbase_holdings = {
        "BTCUSD": {"quantity": 1.0},
        "ETHUSD": {"quantity": 2.0},
    }
    coinbase_history = {
        "BTCUSD": _history(40000, 100),
        "ETHUSD": _history(2000, 10),
    }

    with caplog.at_level(logging.INFO):
        result = analyzer.analyze_dual_platform_correlations(
            coinbase_holdings,
            coinbase_history,
            {},
            {},
        )

    assert result["active_platforms"] == ["coinbase"]
    assert "coinbase" in result
    assert "oanda" not in result
    assert "cross_platform" not in result
    assert "Analyzing correlations for coinbase platform" in caplog.text
    assert "Analyzing correlations for oanda platform" not in caplog.text
    assert "Analyzing cross-platform correlations" not in caplog.text


def test_format_correlation_summary_skips_inactive_platform_sections():
    analyzer = CorrelationAnalyzer()
    summary = analyzer.format_correlation_summary(
        {
            "active_platforms": ["coinbase"],
            "coinbase": {
                "num_holdings": 2,
                "max_correlation": 0.95,
                "highly_correlated": [("BTCUSD", "ETHUSD", 0.95)],
                "concentration_warning": None,
            },
            "overall_warnings": [],
        }
    )

    assert "Coinbase (2 holdings)" in summary
    assert "Oanda" not in summary
    assert "Cross-Platform" not in summary
