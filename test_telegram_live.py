#!/usr/bin/env python3
"""Quick test of Telegram approval bot integration."""

import asyncio
import yaml
from pathlib import Path

async def test_telegram_approval():
    """Test sending an approval request via Telegram."""

    # Load Telegram config
    telegram_config_path = Path('config/telegram.yaml')
    if not telegram_config_path.exists():
        print("❌ config/telegram.yaml not found")
        return

    with open(telegram_config_path) as f:
        telegram_config = yaml.safe_load(f)

    if not telegram_config.get('enabled'):
        print("❌ Telegram bot is not enabled in config")
        return

    if not telegram_config.get('bot_token'):
        print("❌ No bot_token configured")
        return

    # Initialize bot
    try:
        from finance_feedback_engine.integrations.telegram_bot import TelegramApprovalBot

        print("📱 Initializing Telegram bot...")
        bot = TelegramApprovalBot(telegram_config)

        if not bot.bot:
            print("❌ Bot initialization failed - check your bot_token")
            return

        print("✅ Bot initialized successfully!")

        # Create a test decision
        test_decision = {
            'decision_id': 'test_live_' + str(asyncio.get_event_loop().time()),
            'asset_pair': 'BTCUSD',
            'action': 'BUY',
            'confidence': 85,
            'position_size': 0.1,
            'stop_loss': 2.0,
            'take_profit': 5.0,
            'market_regime': 'trending',
            'sentiment': {'overall_sentiment': 'bullish'},
            'reasoning': '🧪 TEST: This is a test approval request from Finance Feedback Engine'
        }

        # Get first allowed user ID
        user_ids = telegram_config.get('allowed_user_ids', [])
        if not user_ids:
            print("❌ No allowed_user_ids configured")
            return

        user_id = user_ids[0]

        print(f"\n📤 Sending test approval request to Telegram user {user_id}...")
        print(f"   Asset: {test_decision['asset_pair']}")
        print(f"   Action: {test_decision['action']}")
        print(f"   Confidence: {test_decision['confidence']}%")

        # Send approval request
        await bot.send_approval_request(test_decision, user_id)

        print("\n✅ Test message sent successfully!")
        print("\n📱 Check your Telegram app - you should see an approval request!")
        print("   You should see buttons for: ✅ Approve | ❌ Reject")

        # Note about webhook
        print("\n💡 Note: For the buttons to work, you need:")
        print("   1. The FastAPI server running (for webhook)")
        print("   2. Or implement manual approval polling")

        print("\n🎉 Telegram bot test complete!")

    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("   Run: pip install python-telegram-bot")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    print("=" * 60)
    print("🧪 Telegram Bot Test - Finance Feedback Engine 2.0")
    print("=" * 60)
    print()

    asyncio.run(test_telegram_approval())
