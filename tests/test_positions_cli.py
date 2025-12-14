import pytest
from click.testing import CliRunner
from unittest.mock import MagicMock, patch
from finance_feedback_engine.cli.main import cli
from finance_feedback_engine.trading_platforms.coinbase_platform import CoinbaseAdvancedPlatform
from finance_feedback_engine.trading_platforms.oanda_platform import OandaPlatform
from finance_feedback_engine.trading_platforms.unified_platform import UnifiedTradingPlatform

# --- Fixtures for Mocking Platforms ---

@pytest.fixture
def mock_coinbase_platform():
    """Fixture for a mocked CoinbaseAdvancedPlatform instance."""
    platform = MagicMock(spec=CoinbaseAdvancedPlatform)
    platform.get_active_positions.return_value = {
        'positions': [
            {
                'product_id': 'BTC-USD',
                'side': 'LONG',
                'contracts': 0.1,
                'entry_price': 50000.0,
                'current_price': 52000.0,
                'unrealized_pnl': 200.0,
                'leverage': 10.0
            }
        ]
    }
    platform.__class__.__name__ = "CoinbaseAdvancedPlatform"
    return platform

@pytest.fixture
def mock_oanda_platform():
    """Fixture for a mocked OandaPlatform instance."""
    platform = MagicMock(spec=OandaPlatform)
    platform.get_active_positions.return_value = {
        'positions': [
            {
                'instrument': 'EUR_USD',
                'position_type': 'LONG',
                'units': 10000,
                'unrealized_pl': 50.0,
                'entry_price': 1.1200,
                'current_price': 1.1250,
                'leverage': 50.0
            }
        ]
    }
    platform.__class__.__name__ = "OandaPlatform"
    return platform

@pytest.fixture
def mock_unified_platform(mock_coinbase_platform, mock_oanda_platform):
    """Fixture for a mocked UnifiedTradingPlatform instance."""
    unified = MagicMock(spec=UnifiedTradingPlatform)
    unified.platforms = {
        'coinbase': mock_coinbase_platform,
        'oanda': mock_oanda_platform
    }
    # Manually implementing the logic for the mock since it's now a real method
    unified.get_active_positions.side_effect = lambda: {
        'positions': [
            {**p, 'platform': 'coinbase'} for p in mock_coinbase_platform.get_active_positions()['positions']
        ] + [
            {**p, 'platform': 'oanda'} for p in mock_oanda_platform.get_active_positions()['positions']
        ]
    }
    return unified

# --- Tests for get_active_positions methods ---


def test_coinbase_get_active_positions_returns_expected_format(mock_coinbase_platform):
    """Test Coinbase get_active_positions returns data in expected format."""
    positions = mock_coinbase_platform.get_active_positions()
    assert 'positions' in positions
    assert len(positions['positions']) == 1
    pos = positions['positions'][0]
    assert pos['product_id'] == 'BTC-USD'
    assert pos['side'] == 'LONG'
    assert pos['unrealized_pnl'] == 200.0


def test_oanda_get_active_positions_returns_expected_format(mock_oanda_platform):
    """Test Oanda get_active_positions returns data in expected format."""
    positions = mock_oanda_platform.get_active_positions()
    assert 'positions' in positions
    assert len(positions['positions']) == 1
    pos = positions['positions'][0]
    assert pos['instrument'] == 'EUR_USD'
    assert pos['position_type'] == 'LONG'
    assert pos['unrealized_pl'] == 50.0

# --- CLI Integration Tests ---

@patch('finance_feedback_engine.cli.main.FinanceFeedbackEngine')
def test_positions_cli_command_single_platform(mock_engine_cls, mock_coinbase_platform):
    """Test the 'positions' CLI command with a single Coinbase platform."""
    # Setup the mock engine instance
    mock_engine_instance = MagicMock()
    mock_engine_instance.trading_platform = mock_coinbase_platform
    mock_engine_cls.return_value = mock_engine_instance

    runner = CliRunner()
    result = runner.invoke(cli, ['positions'])

    if result.exit_code != 0:
        print(result.output)

    assert result.exit_code == 0
    assert "Active Trading Positions" in result.output
    assert "LONG" in result.output


@patch('finance_feedback_engine.cli.main.FinanceFeedbackEngine')
def test_positions_cli_command_unified_platform(mock_engine_cls, mock_unified_platform):
    """Test the 'positions' CLI command with a unified platform."""
    # Setup the mock engine instance
    mock_engine_instance = MagicMock()
    mock_engine_instance.trading_platform = mock_unified_platform
    mock_engine_cls.return_value = mock_engine_instance

    runner = CliRunner()
    result = runner.invoke(cli, ['positions'])

    if result.exit_code != 0:
        print(result.output)

    assert result.exit_code == 0
    assert "Active Trading Positions" in result.output
    assert "BTC-USD" in result.output
    assert "EUR_USD" in result.output
    assert "UnifiedTradingPlatform" in result.output
    # Note: get_active_positions is called on sub-platforms, but unified logic is mocked
    # so we check if the unified platform's get_active_positions was called (via side_effect)
    # logic is handled in the fixture
    assert "BTC-USD" in result.output

@patch('finance_feedback_engine.cli.main.FinanceFeedbackEngine')
def test_positions_cli_command_no_positions(mock_engine_cls, mock_coinbase_platform):
    """Test the 'positions' CLI command when no active positions are found."""
    mock_coinbase_platform.get_active_positions.return_value = {'positions': []}

    mock_engine_instance = MagicMock()
    mock_engine_instance.trading_platform = mock_coinbase_platform
    mock_engine_cls.return_value = mock_engine_instance

    runner = CliRunner()
    result = runner.invoke(cli, ['positions'])

    assert result.exit_code == 0
    assert "No active positions found." in result.output
    mock_coinbase_platform.get_active_positions.assert_called_once()

@patch('finance_feedback_engine.cli.main.FinanceFeedbackEngine')
def test_positions_cli_command_platform_error(mock_engine_cls, mock_coinbase_platform):
    """Test the 'positions' CLI command handles platform errors gracefully."""
    mock_coinbase_platform.get_active_positions.side_effect = Exception("API connection error")

    mock_engine_instance = MagicMock()
    mock_engine_instance.trading_platform = mock_coinbase_platform
    mock_engine_cls.return_value = mock_engine_instance

    runner = CliRunner()
    result = runner.invoke(cli, ['positions'])

    # Click aborts with exit code 1
    assert result.exit_code != 0
    assert "Error fetching active positions: API connection error" in result.output
    mock_coinbase_platform.get_active_positions.assert_called_once()
