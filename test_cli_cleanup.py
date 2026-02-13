#!/usr/bin/env python3
"""Test that CLI commands properly clean up aiohttp sessions (THR-206)."""

import asyncio
import gc
import os
import sys
import warnings
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

# Configure environment
os.environ["ENVIRONMENT"] = "test"
os.environ["ALPHA_VANTAGE_API_KEY"] = "test_key"


def test_analyze_command_cleanup():
    """Test that analyze command properly cleans up engine."""
    from click.testing import CliRunner
    from finance_feedback_engine.cli.main import cli
    
    print("🧪 Testing analyze command cleanup...")
    
    # Track warnings
    warnings.simplefilter("always", ResourceWarning)
    warning_count = 0
    
    def warning_handler(message, category, filename, lineno, file=None, line=None):
        nonlocal warning_count
        if "unclosed" in str(message).lower() or "session" in str(message).lower():
            warning_count += 1
            print(f"⚠️  Warning: {message}")
    
    warnings.showwarning = warning_handler
    
    runner = CliRunner()
    
    # Mock the engine methods to prevent actual API calls
    with patch('finance_feedback_engine.core.FinanceFeedbackEngine.analyze_asset') as mock_analyze:
        mock_analyze.return_value = {
            'id': 'test-123',
            'asset_pair': 'BTCUSD',
            'action': 'HOLD',
            'confidence': 75,
            'reasoning': 'Test decision'
        }
        
        # Run the command
        result = runner.invoke(cli, ['analyze', 'BTCUSD'])
        
        # Check result
        assert result.exit_code == 0, f"Command failed: {result.output}"
    
    # Force garbage collection
    gc.collect()
    
    print(f"{'✅' if warning_count == 0 else '❌'} Analyze command: {warning_count} session warnings")
    return warning_count == 0


def test_balance_command_cleanup():
    """Test that balance command properly cleans up engine."""
    from click.testing import CliRunner
    from finance_feedback_engine.cli.main import cli
    
    print("\n🧪 Testing balance command cleanup...")
    
    # Track warnings
    warnings.simplefilter("always", ResourceWarning)
    warning_count = 0
    
    def warning_handler(message, category, filename, lineno, file=None, line=None):
        nonlocal warning_count
        if "unclosed" in str(message).lower() or "session" in str(message).lower():
            warning_count += 1
            print(f"⚠️  Warning: {message}")
    
    warnings.showwarning = warning_handler
    
    runner = CliRunner()
    
    # Mock the engine methods
    with patch('finance_feedback_engine.core.FinanceFeedbackEngine.get_balance') as mock_balance:
        mock_balance.return_value = {
            'USD': 10000.0,
            'BTC': 0.5
        }
        
        # Run the command
        result = runner.invoke(cli, ['balance'])
        
        # Check result
        assert result.exit_code == 0, f"Command failed: {result.output}"
    
    # Force garbage collection
    gc.collect()
    
    print(f"{'✅' if warning_count == 0 else '❌'} Balance command: {warning_count} session warnings")
    return warning_count == 0


def test_multiple_sequential_commands():
    """Test multiple sequential CLI commands (simulating real usage)."""
    from click.testing import CliRunner
    from finance_feedback_engine.cli.main import cli
    
    print("\n🧪 Testing multiple sequential commands...")
    
    # Track warnings
    warnings.simplefilter("always", ResourceWarning)
    warning_count = 0
    
    def warning_handler(message, category, filename, lineno, file=None, line=None):
        nonlocal warning_count
        if "unclosed" in str(message).lower() or "session" in str(message).lower():
            warning_count += 1
            print(f"⚠️  Warning: {message}")
    
    warnings.showwarning = warning_handler
    
    runner = CliRunner()
    
    # Run multiple commands in sequence
    with patch('finance_feedback_engine.core.FinanceFeedbackEngine.analyze_asset') as mock_analyze, \
         patch('finance_feedback_engine.core.FinanceFeedbackEngine.get_balance') as mock_balance:
        
        mock_analyze.return_value = {
            'id': 'test-123',
            'asset_pair': 'BTCUSD',
            'action': 'HOLD',
            'confidence': 75
        }
        mock_balance.return_value = {'USD': 10000.0}
        
        # Run 5 commands in sequence
        for i in range(5):
            result = runner.invoke(cli, ['analyze', 'BTCUSD'])
            assert result.exit_code == 0
            gc.collect()
    
    # Final garbage collection
    gc.collect()
    
    print(f"{'✅' if warning_count == 0 else '❌'} Sequential commands: {warning_count} session warnings")
    return warning_count == 0


if __name__ == "__main__":
    try:
        test1 = test_analyze_command_cleanup()
        test2 = test_balance_command_cleanup()
        test3 = test_multiple_sequential_commands()
        
        all_passed = test1 and test2 and test3
        
        print(f"\n{'='*60}")
        print(f"{'✅ ALL TESTS PASSED' if all_passed else '❌ SOME TESTS FAILED'}")
        print(f"{'='*60}")
        
        sys.exit(0 if all_passed else 1)
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
