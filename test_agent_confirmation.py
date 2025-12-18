#!/usr/bin/env python3
"""
Test script to demonstrate the agent confirmation prompt functionality.
This script simulates what happens when run-agent is invoked.
"""

from finance_feedback_engine.cli.commands.agent import (
    _confirm_agent_startup,
    _display_agent_configuration_summary,
)

# Mock configuration that would normally be loaded from config file
mock_config = {
    "agent": {
        "autonomous": {"enabled": False},  # Signal-only mode
        "asset_pairs": ["BTCUSD", "ETHUSD"],
        "max_daily_trades": 10,
    },
    "telegram": {
        "enabled": True,
        "bot_token": "mock_token_123",
        "chat_id": "mock_chat_id",
    },
    "webhook": {"enabled": False, "url": None},
    "trading_platform": {"name": "coinbase"},
}

# Test parameters
take_profit = 0.05
stop_loss = 0.02
asset_pairs_override = None

print("=" * 70)
print("TEST 1: Display configuration summary (no confirmation)")
print("=" * 70)
_display_agent_configuration_summary(
    mock_config, take_profit, stop_loss, asset_pairs_override
)

print("\n" + "=" * 70)
print("TEST 2: Confirmation with --yes flag (skip prompt)")
print("=" * 70)
result = _confirm_agent_startup(
    mock_config, take_profit, stop_loss, asset_pairs_override, skip_confirmation=True
)
print(f"Result: {result}")

print("\n" + "=" * 70)
print("TEST 3: Autonomous mode configuration")
print("=" * 70)
autonomous_config = mock_config.copy()
autonomous_config["agent"]["autonomous"]["enabled"] = True
_display_agent_configuration_summary(
    autonomous_config, take_profit, stop_loss, ["BTCUSD", "ETHUSD", "EURUSD"]
)

print("\n" + "=" * 70)
print("TESTS COMPLETED")
print("=" * 70)
print("\nTo test interactive confirmation (without --yes flag):")
print("  python test_agent_confirmation_interactive.py")
