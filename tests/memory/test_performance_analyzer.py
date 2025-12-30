"""
Comprehensive tests for PerformanceAnalyzer service.

Tests cover:
- Sharpe/Sortino ratio calculations
- Maximum drawdown tracking
- Provider performance attribution
- Market regime detection
- Learning validation metrics
- Edge cases and error handling
"""

import pytest
from datetime import datetime, timedelta

import numpy as np

from finance_feedback_engine.memory.performance_analyzer import PerformanceAnalyzer
from finance_feedback_engine.memory.trade_recorder import TradeRecorder
from finance_feedback_engine.memory.portfolio_memory import TradeOutcome


@pytest.fixture
def trade_recorder():
    """Create a TradeRecorder instance for testing."""
    return TradeRecorder(max_memory_size=1000)


@pytest.fixture
def analyzer(trade_recorder):
    """Create a PerformanceAnalyzer instance."""
    return PerformanceAnalyzer(trade_recorder)


class TestPerformanceAnalyzerInitialization:
    """Test PerformanceAnalyzer initialization."""

    def test_init(self, trade_recorder):
        """Should initialize with trade_recorder."""
        analyzer = PerformanceAnalyzer(trade_recorder)
        assert analyzer.trade_recorder is trade_recorder
        assert len(analyzer.performance_snapshots) == 0

    def test_init_regime_performance(self, analyzer):
        """Should initialize empty regime performance dict."""
        assert len(analyzer.regime_performance) == 0


class TestAnalyzePerformance:
    """Test comprehensive performance analysis."""

    def test_analyze_performance_no_trades(self, analyzer):
        """Should return empty snapshot with no trades."""
        snapshot = analyzer.analyze_performance()

        assert snapshot.total_trades == 0
        assert snapshot.win_rate == 0.0

    def test_analyze_performance_basic_metrics(self, analyzer, trade_recorder):
        """Should calculate basic metrics correctly."""
        # Add some trades
        trades = [
            TradeOutcome(
                decision_id="t1",
                asset_pair="BTC-USD",
                action="BUY",
                entry_timestamp=datetime.now().isoformat(),
                realized_pnl=100.0,
                pnl_percentage=5.0,
                was_profitable=True,
            ),
            TradeOutcome(
                decision_id="t2",
                asset_pair="ETH-USD",
                action="SELL",
                entry_timestamp=datetime.now().isoformat(),
                realized_pnl=-50.0,
                pnl_percentage=-2.5,
                was_profitable=False,
            ),
            TradeOutcome(
                decision_id="t3",
                asset_pair="XRP-USD",
                action="BUY",
                entry_timestamp=datetime.now().isoformat(),
                realized_pnl=75.0,
                pnl_percentage=3.0,
                was_profitable=True,
            ),
        ]

        for trade in trades:
            trade_recorder.record_trade_outcome(trade)

        snapshot = analyzer.analyze_performance()

        assert snapshot.total_trades == 3
        assert snapshot.winning_trades == 2
        assert snapshot.losing_trades == 1
        assert snapshot.win_rate == pytest.approx(2 / 3, rel=1e-6)
        assert snapshot.total_pnl == 125.0
        assert snapshot.avg_win == pytest.approx(87.5, rel=1e-6)
        assert snapshot.avg_loss == pytest.approx(-50.0, rel=1e-6)

    def test_analyze_performance_profit_factor(self, analyzer, trade_recorder):
        """Should calculate profit factor correctly."""
        trades = [
            TradeOutcome(
                decision_id="t1",
                asset_pair="BTC-USD",
                action="BUY",
                entry_timestamp=datetime.now().isoformat(),
                realized_pnl=200.0,
                was_profitable=True,
            ),
            TradeOutcome(
                decision_id="t2",
                asset_pair="ETH-USD",
                action="SELL",
                entry_timestamp=datetime.now().isoformat(),
                realized_pnl=-100.0,
                was_profitable=False,
            ),
        ]

        for trade in trades:
            trade_recorder.record_trade_outcome(trade)

        snapshot = analyzer.analyze_performance()

        # Profit factor = gross_profit / gross_loss = 200 / 100 = 2.0
        assert snapshot.profit_factor == pytest.approx(2.0, rel=1e-6)

    def test_analyze_performance_stores_snapshot(self, analyzer, trade_recorder):
        """Should store snapshot after analysis."""
        trade = TradeOutcome(
            decision_id="t1",
            asset_pair="BTC-USD",
            action="BUY",
            entry_timestamp=datetime.now().isoformat(),
            realized_pnl=100.0,
            was_profitable=True,
        )
        trade_recorder.record_trade_outcome(trade)

        assert len(analyzer.performance_snapshots) == 0

        analyzer.analyze_performance()

        assert len(analyzer.performance_snapshots) == 1


class TestSharpeRatio:
    """Test Sharpe ratio calculation."""

    def test_sharpe_ratio_insufficient_data(self, analyzer):
        """Should return 0 with < 2 returns."""
        sharpe = analyzer.calculate_sharpe_ratio()
        assert sharpe == 0.0

    def test_sharpe_ratio_calculation(self, analyzer, trade_recorder):
        """Should calculate Sharpe ratio correctly."""
        # Create trades with known returns
        returns = [5.0, -2.0, 3.0, -1.0, 4.0, 2.0]

        for i, ret in enumerate(returns):
            trade = TradeOutcome(
                decision_id=f"t{i}",
                asset_pair="BTC-USD",
                action="BUY",
                entry_timestamp=datetime.now().isoformat(),
                pnl_percentage=ret,
            )
            trade_recorder.record_trade_outcome(trade)

        sharpe = analyzer.calculate_sharpe_ratio()

        # Sharpe = (mean / std) * sqrt(250)
        mean = np.mean(returns)
        std = np.std(returns, ddof=1)
        expected = (mean / std) * np.sqrt(250)

        assert sharpe == pytest.approx(expected, rel=1e-6)

    def test_sharpe_ratio_zero_std(self, analyzer, trade_recorder):
        """Should return 0 when all returns are identical."""
        for i in range(3):
            trade = TradeOutcome(
                decision_id=f"t{i}",
                asset_pair="BTC-USD",
                action="BUY",
                entry_timestamp=datetime.now().isoformat(),
                pnl_percentage=5.0,  # All same
            )
            trade_recorder.record_trade_outcome(trade)

        sharpe = analyzer.calculate_sharpe_ratio()
        assert sharpe == 0.0


class TestSortinoRatio:
    """Test Sortino ratio calculation."""

    def test_sortino_ratio_insufficient_data(self, analyzer):
        """Should return 0 with < 2 returns."""
        sortino = analyzer.calculate_sortino_ratio()
        assert sortino == 0.0

    def test_sortino_ratio_calculation(self, analyzer, trade_recorder):
        """Should calculate Sortino ratio correctly."""
        returns = [5.0, -2.0, 3.0, -1.0, 4.0, 2.0]

        for i, ret in enumerate(returns):
            trade = TradeOutcome(
                decision_id=f"t{i}",
                asset_pair="BTC-USD",
                action="BUY",
                entry_timestamp=datetime.now().isoformat(),
                pnl_percentage=ret,
            )
            trade_recorder.record_trade_outcome(trade)

        sortino = analyzer.calculate_sortino_ratio()

        # Sortino uses only downside deviation
        mean = np.mean(returns)
        downside_returns = [r for r in returns if r < 0]
        downside_std = np.std(downside_returns, ddof=1)
        expected = (mean / downside_std) * np.sqrt(250)

        assert sortino == pytest.approx(expected, rel=1e-6)

    def test_sortino_ratio_no_losses(self, analyzer, trade_recorder):
        """Should return 0 when no negative returns."""
        for i in range(3):
            trade = TradeOutcome(
                decision_id=f"t{i}",
                asset_pair="BTC-USD",
                action="BUY",
                entry_timestamp=datetime.now().isoformat(),
                pnl_percentage=5.0 + i,  # All positive
            )
            trade_recorder.record_trade_outcome(trade)

        sortino = analyzer.calculate_sortino_ratio()
        assert sortino == 0.0


class TestMaxDrawdown:
    """Test maximum drawdown calculation."""

    def test_max_drawdown_no_trades(self, analyzer):
        """Should return 0 with no trades."""
        dd = analyzer.calculate_max_drawdown()
        assert dd == 0.0

    def test_max_drawdown_calculation(self, analyzer, trade_recorder):
        """Should calculate max drawdown correctly."""
        # Cumulative P&L: 100, 150, 100, 50, 150
        # Peak: 100, 150, 150, 150, 150
        # Drawdown: 0%, 0%, 33.3%, 66.7%, 0%
        # Max DD: 66.7%

        pnls = [100, 50, -50, -50, 100]

        for i, pnl in enumerate(pnls):
            trade = TradeOutcome(
                decision_id=f"t{i}",
                asset_pair="BTC-USD",
                action="BUY",
                entry_timestamp=datetime.now().isoformat(),
                realized_pnl=pnl,
            )
            trade_recorder.record_trade_outcome(trade)

        dd = analyzer.calculate_max_drawdown()

        # Expected max drawdown: (150 - 50) / 150 = 0.6667
        assert dd == pytest.approx(0.6667, rel=1e-3)

    def test_max_drawdown_monotonic_increase(self, analyzer, trade_recorder):
        """Should return 0 for monotonically increasing P&L."""
        for i in range(5):
            trade = TradeOutcome(
                decision_id=f"t{i}",
                asset_pair="BTC-USD",
                action="BUY",
                entry_timestamp=datetime.now().isoformat(),
                realized_pnl=100.0,  # Always positive
            )
            trade_recorder.record_trade_outcome(trade)

        dd = analyzer.calculate_max_drawdown()
        assert dd == 0.0


class TestProviderStats:
    """Test provider performance statistics."""

    def test_provider_stats_empty(self, analyzer):
        """Should return empty dict with no trades."""
        stats = analyzer.calculate_provider_stats()
        assert stats == {}

    def test_provider_stats_calculation(self, analyzer, trade_recorder):
        """Should calculate provider stats correctly."""
        trades = [
            TradeOutcome(
                decision_id="t1",
                asset_pair="BTC-USD",
                action="BUY",
                entry_timestamp=datetime.now().isoformat(),
                ai_provider="local",
                realized_pnl=100.0,
                was_profitable=True,
            ),
            TradeOutcome(
                decision_id="t2",
                asset_pair="ETH-USD",
                action="SELL",
                entry_timestamp=datetime.now().isoformat(),
                ai_provider="local",
                realized_pnl=-50.0,
                was_profitable=False,
            ),
            TradeOutcome(
                decision_id="t3",
                asset_pair="XRP-USD",
                action="BUY",
                entry_timestamp=datetime.now().isoformat(),
                ai_provider="qwen",
                realized_pnl=75.0,
                was_profitable=True,
            ),
        ]

        for trade in trades:
            trade_recorder.record_trade_outcome(trade)

        stats = analyzer.calculate_provider_stats()

        assert "local" in stats
        assert "qwen" in stats

        assert stats["local"]["total_trades"] == 2
        assert stats["local"]["winning_trades"] == 1
        assert stats["local"]["win_rate"] == 0.5
        assert stats["local"]["total_pnl"] == 50.0
        assert stats["local"]["avg_pnl"] == 25.0

        assert stats["qwen"]["total_trades"] == 1
        assert stats["qwen"]["win_rate"] == 1.0


class TestPerformanceOverPeriod:
    """Test period-specific performance analysis."""

    def test_performance_over_period_no_trades(self, analyzer):
        """Should return zero metrics with no trades."""
        perf = analyzer.get_performance_over_period(hours=24)

        assert perf["total_trades"] == 0
        assert perf["total_pnl"] == 0.0

    def test_performance_over_period_within_window(self, analyzer, trade_recorder):
        """Should only include trades within time window."""
        now = datetime.now()

        # Trade within window
        trade1 = TradeOutcome(
            decision_id="t1",
            asset_pair="BTC-USD",
            action="BUY",
            entry_timestamp=(now - timedelta(hours=2)).isoformat(),
            exit_timestamp=(now - timedelta(hours=2)).isoformat(),
            realized_pnl=100.0,
            was_profitable=True,
        )

        # Trade outside window
        trade2 = TradeOutcome(
            decision_id="t2",
            asset_pair="ETH-USD",
            action="SELL",
            entry_timestamp=(now - timedelta(hours=10)).isoformat(),
            exit_timestamp=(now - timedelta(hours=10)).isoformat(),
            realized_pnl=50.0,
            was_profitable=True,
        )

        trade_recorder.record_trade_outcome(trade1)
        trade_recorder.record_trade_outcome(trade2)

        perf = analyzer.get_performance_over_period(hours=6)

        assert perf["total_trades"] == 1  # Only trade1
        assert perf["total_pnl"] == 100.0


class TestRollingCostAverages:
    """Test rolling cost average calculations."""

    def test_rolling_costs_no_data(self, analyzer):
        """Should return zeros with no cost data."""
        costs = analyzer.calculate_rolling_cost_averages()

        assert costs["avg_slippage"] == 0.0
        assert costs["avg_fees"] == 0.0
        assert costs["avg_spread"] == 0.0
        assert costs["avg_total_cost"] == 0.0

    def test_rolling_costs_calculation(self, analyzer, trade_recorder):
        """Should calculate average costs correctly."""
        trades = [
            TradeOutcome(
                decision_id="t1",
                asset_pair="BTC-USD",
                action="BUY",
                entry_timestamp=datetime.now().isoformat(),
                slippage_cost=10.0,
                fee_cost=5.0,
                spread_cost=2.0,
                total_transaction_cost=17.0,
            ),
            TradeOutcome(
                decision_id="t2",
                asset_pair="ETH-USD",
                action="SELL",
                entry_timestamp=datetime.now().isoformat(),
                slippage_cost=8.0,
                fee_cost=4.0,
                spread_cost=1.5,
                total_transaction_cost=13.5,
            ),
        ]

        for trade in trades:
            trade_recorder.record_trade_outcome(trade)

        costs = analyzer.calculate_rolling_cost_averages()

        assert costs["avg_slippage"] == pytest.approx(9.0, rel=1e-6)
        assert costs["avg_fees"] == pytest.approx(4.5, rel=1e-6)
        assert costs["avg_spread"] == pytest.approx(1.75, rel=1e-6)
        assert costs["avg_total_cost"] == pytest.approx(15.25, rel=1e-6)


class TestMarketRegimeDetection:
    """Test market regime detection."""

    def test_regime_detection_insufficient_data(self, analyzer):
        """Should return 'insufficient_data' with < 10 trades."""
        regime = analyzer.detect_market_regime()
        assert regime == "insufficient_data"

    def test_regime_detection_volatile(self, analyzer, trade_recorder):
        """Should detect volatile regime."""
        # High volatility returns
        returns = [10.0, -8.0, 12.0, -9.0, 11.0, -7.0, 13.0, -10.0, 9.0, -8.5]

        for i, ret in enumerate(returns):
            trade = TradeOutcome(
                decision_id=f"t{i}",
                asset_pair="BTC-USD",
                action="BUY",
                entry_timestamp=datetime.now().isoformat(),
                pnl_percentage=ret,
            )
            trade_recorder.record_trade_outcome(trade)

        regime = analyzer.detect_market_regime()
        assert regime == "volatile"

    def test_regime_detection_trending(self, analyzer, trade_recorder):
        """Should detect trending regime."""
        # Consistent positive returns
        returns = [2.5, 3.0, 2.8, 3.2, 2.9, 3.1, 2.7, 3.3, 2.6, 3.0]

        for i, ret in enumerate(returns):
            trade = TradeOutcome(
                decision_id=f"t{i}",
                asset_pair="BTC-USD",
                action="BUY",
                entry_timestamp=datetime.now().isoformat(),
                pnl_percentage=ret,
            )
            trade_recorder.record_trade_outcome(trade)

        regime = analyzer.detect_market_regime()
        assert regime == "trending"

    def test_regime_detection_ranging(self, analyzer, trade_recorder):
        """Should detect ranging regime."""
        # Low volatility, low trend
        returns = [0.5, -0.3, 0.4, -0.2, 0.3, -0.4, 0.2, -0.1, 0.3, -0.2]

        for i, ret in enumerate(returns):
            trade = TradeOutcome(
                decision_id=f"t{i}",
                asset_pair="BTC-USD",
                action="BUY",
                entry_timestamp=datetime.now().isoformat(),
                pnl_percentage=ret,
            )
            trade_recorder.record_trade_outcome(trade)

        regime = analyzer.detect_market_regime()
        assert regime == "ranging"


class TestRegimePerformance:
    """Test regime-specific performance tracking."""

    def test_regime_performance_calculation(self, analyzer, trade_recorder):
        """Should track performance per regime."""
        trades = [
            TradeOutcome(
                decision_id="t1",
                asset_pair="BTC-USD",
                action="BUY",
                entry_timestamp=datetime.now().isoformat(),
                market_sentiment="trending",
                realized_pnl=100.0,
                was_profitable=True,
            ),
            TradeOutcome(
                decision_id="t2",
                asset_pair="ETH-USD",
                action="SELL",
                entry_timestamp=datetime.now().isoformat(),
                market_sentiment="trending",
                realized_pnl=-50.0,
                was_profitable=False,
            ),
            TradeOutcome(
                decision_id="t3",
                asset_pair="XRP-USD",
                action="BUY",
                entry_timestamp=datetime.now().isoformat(),
                market_sentiment="ranging",
                realized_pnl=75.0,
                was_profitable=True,
            ),
        ]

        for trade in trades:
            trade_recorder.record_trade_outcome(trade)

        regime_perf = analyzer.calculate_regime_performance()

        assert "trending" in regime_perf
        assert "ranging" in regime_perf

        assert regime_perf["trending"]["total_trades"] == 2
        assert regime_perf["trending"]["win_rate"] == 0.5
        assert regime_perf["trending"]["total_pnl"] == 50.0

        assert regime_perf["ranging"]["total_trades"] == 1
        assert regime_perf["ranging"]["win_rate"] == 1.0


class TestLearningValidation:
    """Test learning validation metrics."""

    def test_learning_validation_insufficient_data(self, analyzer):
        """Should return insufficient_data status with < 20 trades."""
        metrics = analyzer.generate_learning_validation_metrics()

        assert metrics["status"] == "insufficient_data"
        assert metrics["required"] == 20

    def test_learning_validation_effective(self, analyzer, trade_recorder):
        """Should detect effective learning."""
        # Early period: poor performance
        for i in range(10):
            trade = TradeOutcome(
                decision_id=f"early{i}",
                asset_pair="BTC-USD",
                action="BUY",
                entry_timestamp=datetime.now().isoformat(),
                realized_pnl=-10.0 if i < 7 else 10.0,
                was_profitable=i >= 7,
            )
            trade_recorder.record_trade_outcome(trade)

        # Recent period: better performance
        for i in range(10):
            trade = TradeOutcome(
                decision_id=f"recent{i}",
                asset_pair="BTC-USD",
                action="BUY",
                entry_timestamp=datetime.now().isoformat(),
                realized_pnl=15.0 if i < 7 else -5.0,
                was_profitable=i < 7,
            )
            trade_recorder.record_trade_outcome(trade)

        metrics = analyzer.generate_learning_validation_metrics()

        assert metrics["status"] == "success"
        assert metrics["learning_effective"] is True
        assert metrics["improvement"]["win_rate_improvement"] > 0


class TestUtilityMethods:
    """Test utility methods."""

    def test_get_snapshots(self, analyzer, trade_recorder):
        """Should return all performance snapshots."""
        assert len(analyzer.get_snapshots()) == 0

        # Create a snapshot
        trade = TradeOutcome(
            decision_id="t1",
            asset_pair="BTC-USD",
            action="BUY",
            entry_timestamp=datetime.now().isoformat(),
            realized_pnl=100.0,
            was_profitable=True,
        )
        trade_recorder.record_trade_outcome(trade)
        analyzer.analyze_performance()

        snapshots = analyzer.get_snapshots()
        assert len(snapshots) == 1

    def test_clear_snapshots(self, analyzer, trade_recorder):
        """Should clear all snapshots."""
        trade = TradeOutcome(
            decision_id="t1",
            asset_pair="BTC-USD",
            action="BUY",
            entry_timestamp=datetime.now().isoformat(),
            realized_pnl=100.0,
            was_profitable=True,
        )
        trade_recorder.record_trade_outcome(trade)
        analyzer.analyze_performance()

        assert len(analyzer.performance_snapshots) == 1

        analyzer.clear_snapshots()

        assert len(analyzer.performance_snapshots) == 0

    def test_get_strategy_performance_summary(self, analyzer, trade_recorder):
        """Should return comprehensive strategy summary."""
        trade = TradeOutcome(
            decision_id="t1",
            asset_pair="BTC-USD",
            action="BUY",
            entry_timestamp=datetime.now().isoformat(),
            realized_pnl=100.0,
            was_profitable=True,
            ai_provider="local",
        )
        trade_recorder.record_trade_outcome(trade)

        summary = analyzer.get_strategy_performance_summary()

        assert "overall" in summary
        assert "risk_metrics" in summary
        assert "providers" in summary
        assert "regimes" in summary
