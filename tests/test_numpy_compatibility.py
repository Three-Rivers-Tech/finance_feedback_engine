"""
Test numpy 2.x compatibility with downstream dependencies.

This test validates that numpy>=2.2.0,<2.4.0 works correctly with:
- pandas>=2.2.3
- scikit-learn>=1.7.0 (numpy 2.x support starts at 1.7.0)
- pandas-ta>=0.4.71b0 (Python 3.12+)

Added: 2025-12-15
Reason: Validate numpy 2.x migration and prevent regressions
"""

import numpy as np
import pandas as pd
import pytest
from packaging import version


class TestNumpyCompatibility:
    """Test suite for numpy 2.x compatibility."""

    def test_numpy_version_requirement(self):
        """Verify numpy version is 2.2.0 or higher."""
        numpy_version = version.parse(np.__version__)
        assert numpy_version >= version.parse(
            "2.2.0"
        ), f"numpy {np.__version__} < 2.2.0"
        assert numpy_version < version.parse(
            "2.4.0"
        ), f"numpy {np.__version__} >= 2.4.0 (untested)"

    def test_pandas_numpy_compatibility(self):
        """Test pandas operations with numpy 2.x."""
        # Create test data
        data = {
            "values": np.random.rand(100),
            "dates": pd.date_range("2024-01-01", periods=100),
        }
        df = pd.DataFrame(data)

        # Test common operations
        assert df["values"].mean() is not None
        assert df["values"].std() is not None

        # Test numpy array conversion
        arr = df["values"].to_numpy()
        assert isinstance(arr, np.ndarray)
        assert arr.dtype == np.float64

    def test_sklearn_numpy_compatibility(self):
        """Test scikit-learn with numpy 2.x."""
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.model_selection import train_test_split

        # Generate test data
        X = np.random.rand(100, 5)
        y = np.random.randint(0, 2, 100)

        # Split and train
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        clf = RandomForestClassifier(n_estimators=10, random_state=42)
        clf.fit(X_train, y_train)

        # Verify predictions work
        predictions = clf.predict(X_test)
        assert len(predictions) == len(y_test)
        assert predictions.dtype in [np.int64, np.int32]

    def test_pandas_ta_numpy_compatibility(self):
        """Test pandas-ta technical indicators with numpy 2.x."""
        try:
            import pandas_ta as ta
        except ImportError:
            pytest.skip("pandas-ta not installed")

        # Create sample OHLCV data
        df = pd.DataFrame(
            {
                "open": np.random.uniform(100, 200, 100),
                "high": np.random.uniform(100, 200, 100),
                "low": np.random.uniform(100, 200, 100),
                "close": np.random.uniform(100, 200, 100),
                "volume": np.random.randint(1000, 10000, 100),
            }
        )

        # Test RSI (used in trading engine)
        rsi = ta.rsi(df["close"], length=14)
        assert rsi is not None
        assert not rsi.dropna().empty

        # Test MACD (used in trading engine)
        macd = ta.macd(df["close"])
        assert macd is not None
        assert macd.shape[1] == 3  # MACD, signal, histogram

        # Test ADX (used in market regime detection)
        adx = ta.adx(df["high"], df["low"], df["close"], length=14)
        assert adx is not None
        assert adx.shape[1] == 4  # ADX, DMP, DMN, DX

        # Test ATR (used in market regime detection)
        atr = ta.atr(df["high"], df["low"], df["close"], length=14)
        assert atr is not None
        assert not atr.dropna().empty

    def test_numpy_deprecated_apis(self):
        """Verify no usage of deprecated numpy APIs."""
        import warnings

        # Test operations that might use deprecated APIs
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always", DeprecationWarning)

            # Common operations
            arr = np.array([1, 2, 3, 4, 5])
            _ = arr.mean()
            _ = arr.std()
            _ = np.random.rand(10)

            # Check for numpy-specific deprecation warnings
            numpy_warnings = [
                warning for warning in w if "numpy" in str(warning.message).lower()
            ]

            assert (
                len(numpy_warnings) == 0
            ), f"Found numpy deprecation warnings: {[str(w.message) for w in numpy_warnings]}"

    def test_version_compatibility_matrix(self):
        """Document and verify the compatibility matrix."""
        import sklearn

        # Document versions
        versions = {
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit-learn": sklearn.__version__,
        }

        print("\n=== Dependency Versions ===")
        for name, ver in versions.items():
            print(f"{name}: {ver}")

        # Verify minimum versions
        assert version.parse(pd.__version__) >= version.parse(
            "2.2.3"
        ), f"pandas {pd.__version__} < 2.2.3"
        assert version.parse(sklearn.__version__) >= version.parse(
            "1.7.0"
        ), f"scikit-learn {sklearn.__version__} < 1.7.0 (numpy 2.x support requires 1.7.0+)"
        assert version.parse(np.__version__) >= version.parse(
            "2.2.0"
        ), f"numpy {np.__version__} < 2.2.0"
