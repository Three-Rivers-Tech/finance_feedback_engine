import pytest
from click.testing import CliRunner
import pandas as pd
from datetime import datetime, timezone
from unittest.mock import MagicMock

# TODO: Import components to be tested from the main application
# from finance_feedback_engine.cli.main import cli
# from finance_feedback_engine.utils.config_loader import load_config
# from finance_feedback_engine.decision_engine.base_ai_model import DummyAIModel
# from finance_feedback_engine.trading_platforms.base_platform import BaseTradingPlatform


# --- Fixtures for CLI Testing ---

@pytest.fixture(scope="function")
def cli_runner():
    """
    Provides a Click CLI runner for isolated command testing.

    Implementation Notes:
    - `CliRunner` is the standard way to test `click` applications.
    - `scope="function"` ensures a fresh runner for each test function,
      preventing side effects between tests.
    """
    return CliRunner()

# TODO: Add a fixture for a mocked configuration object
# @pytest.fixture(scope="session")
# def mock_config():
#     """
#     Provides a mock configuration dictionary for testing.
#     """
#     return {
#         "alpha_vantage_api_key": "MOCK_AV_KEY",
#         "trading_platform": "mock",
#         "decision_engine": {
#             "ai_provider": "dummy",
#             "model_name": "TestModel"
#         }
#     }

# --- Fixtures for Data Testing ---

@pytest.fixture(scope="session")
def sample_historical_data() -> pd.DataFrame:
    """
    Provides a sample pandas DataFrame representing historical market data.

    Implementation Notes:
    - DataFrames should have a DatetimeIndex and standard financial columns.
    - Useful for testing data validation, backtesting, and AI model inputs.
    """
    dates = pd.to_datetime([
        "2023-01-01", "2023-01-02", "2023-01-03", "2023-01-04", "2023-01-05"
    ], utc=True)
    data = {
        'open': [100.0, 101.5, 102.0, 103.5, 104.0],
        'high': [102.0, 102.5, 103.0, 104.5, 105.0],
        'low': [99.5, 100.0, 101.5, 102.0, 103.0],
        'close': [101.5, 102.0, 103.5, 104.0, 104.5],
        'volume': [1000, 1100, 1050, 1200, 1150],
        'RSI': [30.0, 35.0, 40.0, 45.0, 50.0] # Example feature
    }
    df = pd.DataFrame(data, index=dates)
    df.index.name = 'timestamp'
    return df

# TODO: Add a fixture for invalid historical data to test validation
# @pytest.fixture(scope="session")
# def invalid_historical_data() -> pd.DataFrame:
#     """
#     Provides sample historical data with known issues for validation tests.
#     """
#     # Example: missing values, non-numeric prices, incorrect timestamps
#     pass


# --- Fixtures for AI/ML Component Testing ---

@pytest.fixture(scope="function")
def mock_ai_model():
    """
    Provides a mocked AI model adhering to the BaseAIModel interface.

    Implementation Notes:
    - Mocks are essential for isolating AI model logic and preventing external
      API calls during unit tests.
    - `MagicMock` can simulate class instances and their methods.
    """
    # TODO: Replace MagicMock with a mock based on BaseAIModel or DummyAIModel
    # For more complex scenarios, you might use unittest.mock.create_autospec
    # from finance_feedback_engine.decision_engine.base_ai_model import BaseAIModel
    mock = MagicMock()
    mock.predict.return_value = {"action": "BUY", "confidence": 0.9, "reasoning": "Mocked reason"}
    mock.explain.return_value = {"key_factors": ["mock_feature_1"], "feature_contributions": {"mock_feature_1": 0.5}}
    mock.get_metadata.return_value = {"model_name": "MockAI", "version": "0.0.1"}
    return mock
    # return DummyAIModel({"model_name": "TestMockModel"}) # Alternative: use a simple concrete dummy

# TODO: Add a fixture for a mocked trading platform
# @pytest.fixture(scope="function")
# def mock_trading_platform():
#     """
#     Provides a mocked trading platform for testing interactions.
#     """
#     mock = MagicMock(spec=BaseTradingPlatform)
#     mock.get_balance.return_value = {"USD": 10000.0, "BTC": 0.5}
#     mock.place_order.return_value = {"order_id": "mock_123", "status": "FILLED"}
#     return mock


# --- General Purpose Fixtures ---

@pytest.fixture(scope="session")
def temporary_file_path(tmp_path_factory):
    """
    Provides a path to a temporary file, useful for testing file I/O operations.
    """
    temp_dir = tmp_path_factory.mktemp("temp_test_files")
    return temp_dir / "test_file.txt"

# TODO: Add more fixtures as needed for common test setups:
# - Mocked external API responses (e.g., Alpha Vantage, Oanda)
# - Pre-configured FinanceFeedbackEngine instance for integration tests
# - Database connection fixtures (e.g., in-memory SQLite for testing persistence)

