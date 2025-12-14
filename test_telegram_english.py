#!/usr/bin/env python3
"""Send a simple English test message to verify Telegram connection."""

import asyncio
import yaml
from telegram import Bot

async def send_test_message():
    """Send a plain English test message."""

    # Load config
    # Load config
    try:
        with open('config/telegram.yaml') as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        print("❌ config/telegram.yaml not found")
        return
    except yaml.YAMLError as e:
        print(f"❌ Error parsing config: {e}")
        return

    bot_token = config.get('bot_token')
    if not bot_token:
        print("❌ No bot_token configured")
        return

    user_ids = config.get('allowed_user_ids', [])
    if not user_ids:
        print("❌ No allowed_user_ids configured")
        return
    user_id = user_ids[0]

    bot = Bot(token=bot_token)

    # Send simple English message
    message = """
🎉 **Telegram Bot Test - SUCCESS!** 🎉

✅ Your bot is connected and working!
✅ Chat ID verified: {user_id}
✅ Ready to receive trading approvals

Next step: Run the agent with:
`python main.py run-agent --asset-pairs "BTCUSD"`

This is a test from Finance Feedback Engine 2.0 🚀
""".format(user_id=user_id)

    print(f"📤 Sending English test message to user {user_id}...")

    try:
        await bot.send_message(
            chat_id=user_id,
            text=message,
            parse_mode='Markdown'
        )
        print("✅ Message sent successfully!")
        print("📱 Check your Telegram - you should see it in English!")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == '__main__':
    asyncio.run(send_test_message())
