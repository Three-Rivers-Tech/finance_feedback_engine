import inspect

from finance_feedback_engine.backtesting.backtester import Backtester


def test_run_backtest_accepts_allow_shorts_param():
    sig = inspect.signature(Backtester.run_backtest)
    assert "allow_shorts" in sig.parameters
    assert sig.parameters["allow_shorts"].default is True
