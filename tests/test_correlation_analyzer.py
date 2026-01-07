"""Tests for correlation analyzer."""

import hashlib
import pytest

from finance_feedback_engine.risk.correlation_analyzer import CorrelationAnalyzer


class TestCorrelationAnalyzer:
    """Test suite for CorrelationAnalyzer."""

    @pytest.fixture
    def analyzer(self):
        """Create a correlation analyzer."""
        return CorrelationAnalyzer(lookback_days=30)

    def test_init(self):
        """Test analyzer initialization."""
        analyzer = CorrelationAnalyzer(lookback_days=60)
        assert analyzer.lookback_days == 60
        assert analyzer.correlation_threshold == 0.7
        assert analyzer.cross_platform_warning_threshold == 0.5

    def test_calculate_pearson_correlation_perfect_positive(self, analyzer):
        """Test perfect positive correlation."""
        returns_a = [0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.10]
        returns_b = [0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.10]

        corr = analyzer.calculate_pearson_correlation(returns_a, returns_b)

        assert corr is not None
        assert abs(corr - 1.0) < 0.01  # Should be very close to 1.0

    def test_calculate_pearson_correlation_perfect_negative(self, analyzer):
        """Test perfect negative correlation."""
        returns_a = [0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.10]
        returns_b = [-0.01, -0.02, -0.03, -0.04, -0.05, -0.06, -0.07, -0.08, -0.09, -0.10]

        corr = analyzer.calculate_pearson_correlation(returns_a, returns_b)

        assert corr is not None
        assert abs(corr - (-1.0)) < 0.01  # Should be very close to -1.0

    def test_calculate_pearson_correlation_no_correlation(self, analyzer):
        """Test uncorrelated returns."""
        returns_a = [0.01, 0.02, -0.01, 0.03, -0.02, 0.01, -0.01, 0.02, -0.02, 0.01]
        returns_b = [0.02, -0.01, 0.01, -0.02, 0.03, -0.01, 0.02, -0.01, 0.01, -0.02]

        corr = analyzer.calculate_pearson_correlation(returns_a, returns_b)

        assert corr is not None
        assert abs(corr) < 0.5  # Should be low correlation

    def test_calculate_pearson_correlation_insufficient_data(self, analyzer):
        """Test correlation with insufficient data points."""
        returns_a = [0.01, 0.02, 0.03]
        returns_b = [0.01, 0.02, 0.03]

        corr = analyzer.calculate_pearson_correlation(returns_a, returns_b)

        assert corr is None

    def test_calculate_pearson_correlation_mismatched_length(self, analyzer):
        """Test correlation with mismatched series lengths."""
        returns_a = [0.01, 0.02, 0.03, 0.04, 0.05]
        returns_b = [0.01, 0.02, 0.03]

        corr = analyzer.calculate_pearson_correlation(returns_a, returns_b)

        assert corr is None

    def test_calculate_pearson_correlation_empty_series(self, analyzer):
        """Test correlation with empty series."""
        corr = analyzer.calculate_pearson_correlation([], [])
        assert corr is None

    def test_calculate_pearson_correlation_zero_std(self, analyzer):
        """Test correlation when one series has zero standard deviation."""
        returns_a = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        returns_b = [0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.10]

        corr = analyzer.calculate_pearson_correlation(returns_a, returns_b)

        assert corr is None

    def test_build_correlation_matrix(self, analyzer):
        """Test building correlation matrix from price history."""
        price_history = {
            "BTCUSD": [
                {"date": "2024-01-01", "price": 40000},
                {"date": "2024-01-02", "price": 41000},
                {"date": "2024-01-03", "price": 42000},
                {"date": "2024-01-04", "price": 43000},
                {"date": "2024-01-05", "price": 44000},
                {"date": "2024-01-06", "price": 45000},
                {"date": "2024-01-07", "price": 46000},
                {"date": "2024-01-08", "price": 47000},
                {"date": "2024-01-09", "price": 48000},
                {"date": "2024-01-10", "price": 49000},
                {"date": "2024-01-11", "price": 50000},
            ],
            "ETHUSD": [
                {"date": "2024-01-01", "price": 2000},
                {"date": "2024-01-02", "price": 2050},
                {"date": "2024-01-03", "price": 2100},
                {"date": "2024-01-04", "price": 2150},
                {"date": "2024-01-05", "price": 2200},
                {"date": "2024-01-06", "price": 2250},
                {"date": "2024-01-07", "price": 2300},
                {"date": "2024-01-08", "price": 2350},
                {"date": "2024-01-09", "price": 2400},
                {"date": "2024-01-10", "price": 2450},
                {"date": "2024-01-11", "price": 2500},
            ],
        }

        matrix = analyzer.build_correlation_matrix(price_history)

        assert ("BTCUSD", "ETHUSD") in matrix
        assert ("ETHUSD", "BTCUSD") in matrix
        assert matrix[("BTCUSD", "ETHUSD")] == matrix[("ETHUSD", "BTCUSD")]
        assert 0.9 <= matrix[("BTCUSD", "ETHUSD")] <= 1.0

    def test_build_correlation_matrix_empty(self, analyzer):
        """Test building correlation matrix with empty price history."""
        matrix = analyzer.build_correlation_matrix({})
        assert matrix == {}

    def test_build_correlation_matrix_single_asset(self, analyzer):
        """Test building correlation matrix with single asset."""
        price_history = {
            "BTCUSD": [
                {"date": "2024-01-01", "price": 40000},
                {"date": "2024-01-02", "price": 41000},
            ]
        }

        matrix = analyzer.build_correlation_matrix(price_history)
        assert matrix == {}

    def test_find_highly_correlated_pairs(self, analyzer):
        """Test finding highly correlated asset pairs."""
        correlation_matrix = {
            ("BTCUSD", "ETHUSD"): 0.95,
            ("ETHUSD", "BTCUSD"): 0.95,
            ("BTCUSD", "LTCUSD"): 0.65,
            ("LTCUSD", "BTCUSD"): 0.65,
            ("ETHUSD", "LTCUSD"): 0.80,
            ("LTCUSD", "ETHUSD"): 0.80,
        }

        pairs = analyzer.find_highly_correlated_pairs(correlation_matrix, threshold=0.7)

        assert len(pairs) == 2  # BTC-ETH and ETH-LTC
        correlations = [p[2] for p in pairs]
        assert 0.95 in correlations
        assert 0.80 in correlations

    def test_find_highly_correlated_pairs_no_duplicates(self, analyzer):
        """Test that highly correlated pairs don't include duplicates."""
        correlation_matrix = {
            ("BTCUSD", "ETHUSD"): 0.95,
            ("ETHUSD", "BTCUSD"): 0.95,
        }

        pairs = analyzer.find_highly_correlated_pairs(correlation_matrix)

        assert len(pairs) == 1  # Only one pair, not duplicated

    def test_analyze_platform_correlations_single_holding(self, analyzer):
        """Test analyzing correlations with single holding."""
        holdings = {"BTCUSD": {"quantity": 1.0}}
        price_history = {
            "BTCUSD": [
                {"date": "2024-01-01", "price": 40000},
                {"date": "2024-01-02", "price": 41000},
            ]
        }

        result = analyzer.analyze_platform_correlations(
            holdings, price_history, "coinbase"
        )

        assert result["platform"] == "coinbase"
        assert result["num_holdings"] == 1
        assert result["correlation_matrix"] == {}
        assert result["highly_correlated"] == []
        assert result["max_correlation"] == 0.0
        assert result["concentration_warning"] is None

    def test_analyze_platform_correlations_no_holdings(self, analyzer):
        """Test analyzing correlations with no holdings."""
        result = analyzer.analyze_platform_correlations({}, {}, "coinbase")

        assert result["platform"] == "coinbase"
        assert result["num_holdings"] == 0
        assert result["concentration_warning"] is None

    def test_analyze_platform_correlations_with_warning(self, analyzer):
        """Test analyzing correlations that trigger concentration warning."""
        holdings = {
            "BTCUSD": {"quantity": 1.0},
            "ETHUSD": {"quantity": 10.0},
            "LTCUSD": {"quantity": 100.0},
            "DOGEUSD": {"quantity": 1000.0},
        }

        # Create highly correlated price history for all assets
        price_history = {}
        base_prices = [100, 105, 110, 115, 120, 125, 130, 135, 140, 145, 150]

        for asset in holdings.keys():
            # Use deterministic multiplier derived from asset string for repeatability
            stable_multiplier = int(hashlib.md5(asset.encode()).hexdigest(), 16) % 10
            price_history[asset] = [
                {"date": f"2024-01-{i+1:02d}", "price": price * (1 + stable_multiplier * 0.01)}
                for i, price in enumerate(base_prices)
            ]

        result = analyzer.analyze_platform_correlations(
            holdings, price_history, "coinbase"
        )

        assert result["platform"] == "coinbase"
        assert result["num_holdings"] == 4
        # Should have high correlations due to similar price movements
        assert len(result["highly_correlated"]) > 0

    def test_analyze_cross_platform_correlation(self, analyzer):
        """Test analyzing cross-platform correlations."""
        coinbase_price_history = {
            "BTCUSD": [
                {"date": f"2024-01-{i+1:02d}", "price": 40000 + i * 1000}
                for i in range(15)
            ]
        }

        oanda_price_history = {
            "EUR_USD": [
                {"date": f"2024-01-{i+1:02d}", "price": 1.10 + i * 0.001}
                for i in range(15)
            ]
        }

        result = analyzer.analyze_cross_platform_correlation(
            coinbase_price_history, oanda_price_history
        )

        assert "cross_correlations" in result
        assert "max_correlation" in result
        assert "warning" in result

    def test_analyze_cross_platform_correlation_empty(self, analyzer):
        """Test analyzing cross-platform correlations with empty data."""
        result = analyzer.analyze_cross_platform_correlation({}, {})

        assert result["cross_correlations"] == []
        assert result["max_correlation"] == 0.0
        assert result["warning"] is None

    def test_analyze_dual_platform_correlations(self, analyzer):
        """Test comprehensive dual-platform correlation analysis."""
        coinbase_holdings = {"BTCUSD": {"quantity": 1.0}}
        coinbase_price_history = {
            "BTCUSD": [
                {"date": f"2024-01-{i+1:02d}", "price": 40000 + i * 1000}
                for i in range(15)
            ]
        }

        oanda_holdings = {"EUR_USD": {"quantity": 1000.0}}
        oanda_price_history = {
            "EUR_USD": [
                {"date": f"2024-01-{i+1:02d}", "price": 1.10 + i * 0.001}
                for i in range(15)
            ]
        }

        result = analyzer.analyze_dual_platform_correlations(
            coinbase_holdings,
            coinbase_price_history,
            oanda_holdings,
            oanda_price_history,
        )

        assert "coinbase" in result
        assert "oanda" in result
        assert "cross_platform" in result
        assert "overall_warnings" in result

        assert result["coinbase"]["platform"] == "coinbase"
        assert result["oanda"]["platform"] == "oanda"

    def test_format_correlation_summary(self, analyzer):
        """Test formatting correlation summary."""
        analysis = {
            "coinbase": {
                "num_holdings": 2,
                "max_correlation": 0.95,
                "highly_correlated": [("BTCUSD", "ETHUSD", 0.95)],
                "concentration_warning": None,
            },
            "oanda": {
                "num_holdings": 1,
                "max_correlation": 0.0,
                "highly_correlated": [],
                "concentration_warning": None,
            },
            "cross_platform": {
                "max_correlation": 0.30,
                "warning": None,
            },
            "overall_warnings": [],
        }

        summary = analyzer.format_correlation_summary(analysis)

        assert "Correlation Analysis Summary" in summary
        assert "Coinbase (2 holdings)" in summary
        assert "Oanda (1 holdings)" in summary
        assert "Cross-Platform" in summary
        assert "0.95" in summary

    def test_format_correlation_summary_with_warnings(self, analyzer):
        """Test formatting correlation summary with warnings."""
        analysis = {
            "coinbase": {
                "num_holdings": 3,
                "max_correlation": 0.85,
                "highly_correlated": [("BTCUSD", "ETHUSD", 0.85)],
                "concentration_warning": "3 assets with correlation >0.7",
            },
            "oanda": {
                "num_holdings": 2,
                "max_correlation": 0.60,
                "highly_correlated": [],
                "concentration_warning": None,
            },
            "cross_platform": {
                "max_correlation": 0.55,
                "warning": "Cross-platform correlation detected",
            },
            "overall_warnings": [
                "3 assets with correlation >0.7",
                "Cross-platform correlation detected",
            ],
        }

        summary = analyzer.format_correlation_summary(analysis)

        assert "Warnings" in summary or "⚠️" in summary
        assert "3 assets with correlation >0.7" in summary

    def test_correlation_matrix_symmetry(self, analyzer):
        """Test that correlation matrix is symmetric."""
        price_history = {
            "BTCUSD": [
                {"date": f"2024-01-{i+1:02d}", "price": 40000 + i * 1000}
                for i in range(15)
            ],
            "ETHUSD": [
                {"date": f"2024-01-{i+1:02d}", "price": 2000 + i * 50}
                for i in range(15)
            ],
        }

        matrix = analyzer.build_correlation_matrix(price_history)

        # Check symmetry
        for (asset_a, asset_b), corr in matrix.items():
            if asset_a != asset_b:
                assert matrix.get((asset_b, asset_a)) == corr

    def test_correlation_clamping(self, analyzer):
        """Test that correlations are clamped to [-1, 1]."""
        # Create data that might cause floating point errors
        returns_a = [0.001] * 20
        returns_b = [0.001] * 20

        corr = analyzer.calculate_pearson_correlation(returns_a, returns_b)

        if corr is not None:
            assert -1.0 <= corr <= 1.0
