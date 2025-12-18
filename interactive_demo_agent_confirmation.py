#!/usr/bin/env python3
"""
Interactive test for agent confirmation prompt.
Run this to test the actual user confirmation dialog.
"""

from finance_feedback_engine.cli.commands.agent import _confirm_agent_startup

# Mock configuration
mock_config = {
    "agent": {
        "autonomous": {"enabled": False},
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

print("=" * 70)
print("INTERACTIVE CONFIRMATION TEST")
print("=" * 70)
print("\nThis will prompt you to confirm agent startup.")
print("You can test both 'y' (yes) and 'n' (no) responses.\n")

result = _confirm_agent_startup(
    mock_config,
    take_profit=0.05,
    stop_loss=0.02,
    asset_pairs_override=None,
    skip_confirmation=False,  # Force interactive prompt
)

print("\n" + "=" * 70)
print(f"CONFIRMATION RESULT: {'APPROVED' if result else 'CANCELLED'}")
print("=" * 70)

if result:
    print("\n✓ Agent would proceed to initialization")
else:
    print("\n✗ Agent startup cancelled - command would exit")
