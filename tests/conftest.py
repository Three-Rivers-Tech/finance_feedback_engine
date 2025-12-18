import logging
import os
import shutil
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest
import yaml
from click.testing import CliRunner

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


# --- Logging Configuration Fixture ---
# This fixture ensures all logging handlers are properly cleaned up after tests
# to prevent "I/O operation on closed file" errors.

@pytest.fixture(scope="session", autouse=True)
def configure_test_logging():
    """
    Configure pytest logging to use caplog instead of file handlers.

    Prevents "I/O operation on closed file" errors by avoiding file-based
    log handlers that can get closed unexpectedly during test teardown.
    """
    # Get root logger
    root_logger = logging.getLogger()

    # Remove any existing file handlers
    for handler in root_logger.handlers[:]:
        if isinstance(handler, (logging.FileHandler, logging.StreamHandler)):
            # Close and remove the handler
            handler.close()
            root_logger.removeHandler(handler)

    # Set root logger to WARNING to minimize noise in test output
    root_logger.setLevel(logging.WARNING)

    yield

    # Cleanup after tests: ensure all handlers are removed
    for handler in root_logger.handlers[:]:
        handler.close()
        root_logger.removeHandler(handler)


# --- Async Fixtures for Resource Cleanup ---


@pytest.fixture
async def alpha_vantage_provider():
    """
    Provides an AlphaVantageProvider with proper async cleanup.

    This fixture ensures that aiohttp sessions are properly closed after tests,
    preventing "Unclosed client session" warnings.

    Uses async context manager pattern for guaranteed cleanup.
    """
    from finance_feedback_engine.data_providers.alpha_vantage_provider import AlphaVantageProvider

    provider = AlphaVantageProvider(
        api_key="test_api_key_12345",
        is_backtest=True  # Allow mock data in tests
    )

    yield provider

    # Cleanup: Close the session if it exists
    # Use try/except to ensure cleanup even if provider.close() fails
    try:
        await provider.close()
    except Exception:
        pass


@pytest.fixture
def coinbase_provider():
    """
    Provides a Coinbase data provider (synchronous - no async cleanup needed).
    """
    from finance_feedback_engine.data_providers.coinbase_data import CoinbaseDataProvider

    # CoinbaseDataProvider uses requests (sync), not aiohttp
    provider = CoinbaseDataProvider(
        credentials={"api_key": "test_key", "api_secret": "test_secret"}
    )

    yield provider

    # No async cleanup needed - uses requests library


@pytest.fixture
def oanda_provider():
    """
    Provides an Oanda data provider (synchronous - no async cleanup needed).
    """
    from finance_feedback_engine.data_providers.oanda_data import OandaDataProvider

    # OandaDataProvider uses requests (sync), not aiohttp
    provider = OandaDataProvider(
        credentials={
            "access_token": "test_oanda_token",
            "account_id": "test_account_123",
            "environment": "practice"
        }
    )

    yield provider

    # No async cleanup needed - uses requests library


@pytest.fixture
async def unified_data_provider():
    """
    Provides a UnifiedDataProvider with proper async cleanup.

    Uses async context manager pattern and ensures all child provider
    sessions are properly closed.
    """
    from finance_feedback_engine.data_providers.unified_data_provider import UnifiedDataProvider

    config = {
        "alpha_vantage_api_key": "test_av_key",
        "platform_credentials": {
            "coinbase": {
                "api_key": "test_cb_key",
                "api_secret": "test_cb_secret"
            },
            "oanda": {
                "api_key": "test_oanda_key",
                "account_id": "test_account"
            }
        }
    }

    provider = UnifiedDataProvider(config=config)

    yield provider

    # Cleanup: Close all provider sessions with error handling
    try:
        if hasattr(provider, 'alpha_vantage') and hasattr(provider.alpha_vantage, 'close'):
            await provider.alpha_vantage.close()
    except Exception:
        pass


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


@pytest.fixture(scope="session")
def test_config_path():
    """
    Provides the path to the unified test configuration file.

    Returns:
        Path: Path to config/config.test.mock.yaml
    """
    return Path("config/config.test.mock.yaml")


@pytest.fixture(scope="function")
async def mock_engine(test_config_path):
    """
    Provides a FinanceFeedbackEngine instance with test configuration.

    Args:
        test_config_path: Fixture providing path to test config

    Returns:
        FinanceFeedbackEngine: Engine initialized with mock config

    Note:
        This is now an async fixture to properly cleanup async resources
        like aiohttp sessions in data providers.
    """
    from finance_feedback_engine import FinanceFeedbackEngine

    with open(test_config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    engine = FinanceFeedbackEngine(config)

    yield engine

    # Cleanup: Close async resources
    try:
        await engine.close()
    except Exception:
        pass  # Ignore cleanup errors


@pytest.fixture(scope="function")
def isolated_cli_runner(tmp_path):
    """
    Provides a CliRunner with isolated filesystem for file operations.

    Args:
        tmp_path: Pytest fixture providing temporary directory

    Returns:
        tuple: (CliRunner, Path to temp directory)
    """
    runner = CliRunner()
    return runner, tmp_path


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_data():
    """
    Session-scoped fixture that cleans up test data directories.

    Runs automatically before and after test session to ensure clean state.
    """
    # Cleanup before tests
    test_dirs = [
        Path("data/decisions_test"),
        Path("data/test_metrics"),
        Path("data/test_memory"),
    ]

    for test_dir in test_dirs:
        if test_dir.exists():
            shutil.rmtree(test_dir, ignore_errors=True)

    yield

    # Cleanup after tests
    for test_dir in test_dirs:
        if test_dir.exists():
            shutil.rmtree(test_dir, ignore_errors=True)


# --- Fixtures for Data Testing ---


@pytest.fixture(scope="session")
def sample_historical_data() -> pd.DataFrame:
    """
    Provides a sample pandas DataFrame representing historical market data.

    Implementation Notes:
    - DataFrames should have a DatetimeIndex and standard financial columns.
    - Useful for testing data validation, backtesting, and AI model inputs.
    """
    dates = pd.to_datetime(
        ["2023-01-01", "2023-01-02", "2023-01-03", "2023-01-04", "2023-01-05"], utc=True
    )
    data = {
        "open": [100.0, 101.5, 102.0, 103.5, 104.0],
        "high": [102.0, 102.5, 103.0, 104.5, 105.0],
        "low": [99.5, 100.0, 101.5, 102.0, 103.0],
        "close": [101.5, 102.0, 103.5, 104.0, 104.5],
        "volume": [1000, 1100, 1050, 1200, 1150],
        "RSI": [30.0, 35.0, 40.0, 45.0, 50.0],  # Example feature
    }
    df = pd.DataFrame(data, index=dates)
    df.index.name = "timestamp"
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
    mock.predict.return_value = {
        "action": "BUY",
        "confidence": 0.9,
        "reasoning": "Mocked reason",
    }
    mock.explain.return_value = {
        "key_factors": ["mock_feature_1"],
        "feature_contributions": {"mock_feature_1": 0.5},
    }
    mock.get_metadata.return_value = {"model_name": "MockAI", "version": "0.0.1"}
    return mock
    # return DummyAIModel({"model_name": "TestMockModel"}) # Alternative: use a simple concrete dummy


@pytest.fixture(scope="function")
def mock_trading_platform():
    """
    Provides a mocked trading platform for testing interactions.
    """
    from finance_feedback_engine.trading_platforms.base_platform import (
        BaseTradingPlatform,
    )

    mock = MagicMock(spec=BaseTradingPlatform)
    mock.get_balance.return_value = {"USD": 10000.0, "BTC": 0.5}
    mock.execute_trade.return_value = {
        "order_id": "mock_123",
        "status": "FILLED",
        "success": True,
        "message": "Mock trade executed",
    }
    mock.get_portfolio_breakdown.return_value = {
        "total_value_usd": 10000.0,
        "positions": [],
    }
    mock.get_account_info.return_value = {"max_leverage": 10.0}
    return mock


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
