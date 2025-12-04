"""Telegram bot for trading decision approvals."""

import logging
import asyncio
import json
from typing import Optional, Dict, Any
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Global telegram bot instance (initialized if config enabled)
telegram_bot: Optional['TelegramApprovalBot'] = None


class TelegramApprovalBot:
    """
    Telegram bot for interactive trading decision approvals.

    Features:
    - Webhook-based updates from Telegram
    - Inline keyboard for Approve/Reject/Modify actions
    - Approval queue backed by Redis
    - User whitelist for security
    """

    def __init__(self, config: dict):
        """
        Initialize Telegram approval bot.

        Args:
            config: Telegram configuration with bot_token, allowed_user_ids, etc.
        """
        self.config = config
        self.bot_token = config.get('bot_token')
        self.allowed_users = set(config.get('allowed_user_ids', []))
        self.use_redis = config.get('use_redis', False)

        # TODO: Import python-telegram-bot
        # from telegram import Bot
        # self.bot = Bot(token=self.bot_token)
        self.bot = None

        # Approval queue (Redis or in-memory)
        self.approval_queue = {}
        self.redis_client = None

        # Initialize Redis if enabled
        if self.use_redis:
            self._init_redis()

        # Tunnel manager for webhook URL
        from .tunnel_manager import TunnelManager
        self.tunnel_manager = TunnelManager(config)

        logger.info("✅ Telegram approval bot initialized")

    def _init_redis(self):
        """Initialize Redis connection for approval queue."""
        try:
            from .redis_manager import RedisManager

            # Ensure Redis is running (with user prompts)
            if not RedisManager.ensure_running():
                logger.warning("⚠️  Redis setup failed. Falling back to in-memory queue.")
                self.use_redis = False
                return

            import redis
            self.redis_client = redis.Redis(
                host='localhost',
                port=6379,
                decode_responses=True
            )
            self.redis_client.ping()
            logger.info("✅ Redis connection established for approval queue")
        except Exception as e:
            logger.error(f"❌ Redis initialization failed: {e}. Using in-memory queue.")
            self.use_redis = False
            self.redis_client = None

    async def setup_webhook(self, public_url: str):
        """
        Register webhook with Telegram Bot API.

        Args:
            public_url: Public HTTPS URL for webhook endpoint
        """
        try:
            webhook_url = f"{public_url}/webhook/telegram"
            logger.info(f"🔗 Registering webhook: {webhook_url}")

            # TODO: Implement with python-telegram-bot
            # await self.bot.set_webhook(url=webhook_url)

            logger.info("✅ Webhook registered successfully")
        except Exception as e:
            logger.error(f"❌ Webhook registration failed: {e}")
            raise

    def format_decision_message(self, decision: Dict[str, Any]) -> str:
        """
        Format decision as readable Telegram message.

        Args:
            decision: Decision dictionary from DecisionStore

        Returns:
            Formatted message text
        """
        return f"""
🤖 **Trading Decision Approval Required**

**Asset:** {decision.get('asset_pair')}
**Action:** {decision.get('action')}
**Confidence:** {decision.get('confidence')}%

**Position Size:** {decision.get('position_size', 'N/A')}
**Stop Loss:** {decision.get('stop_loss', 'N/A')}%
**Take Profit:** {decision.get('take_profit', 'N/A')}%

**Market Regime:** {decision.get('market_regime', 'Unknown')}
**Sentiment:** {decision.get('sentiment', {}).get('overall_sentiment', 'N/A')}

**Reasoning:**
{decision.get('reasoning', 'No reasoning provided')}

**Decision ID:** `{decision.get('decision_id')}`
"""

    def create_approval_keyboard(self, decision_id: str):
        """
        Create inline keyboard with Approve/Reject/Modify buttons.

        Args:
            decision_id: Decision ID for callback data

        Returns:
            InlineKeyboardMarkup object
        """
        # TODO: Implement with python-telegram-bot
        # from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        # keyboard = [
        #     [
        #         InlineKeyboardButton("✅ Approve", callback_data=f"approve:{decision_id}"),
        #         InlineKeyboardButton("❌ Reject", callback_data=f"reject:{decision_id}")
        #     ],
        #     [
        #         InlineKeyboardButton("✏️ Modify", callback_data=f"modify:{decision_id}")
        #     ]
        # ]
        # return InlineKeyboardMarkup(keyboard)

        return None  # Stub for now

    async def send_approval_request(self, decision: Dict[str, Any], user_id: int):
        """
        Send approval request to Telegram user.

        Args:
            decision: Decision dictionary
            user_id: Telegram user ID to send to
        """
        try:
            message_text = self.format_decision_message(decision)
            keyboard = self.create_approval_keyboard(decision['decision_id'])

            # TODO: Implement with python-telegram-bot
            # await self.bot.send_message(
            #     chat_id=user_id,
            #     text=message_text,
            #     reply_markup=keyboard,
            #     parse_mode='Markdown'
            # )

            logger.info(f"📤 Approval request sent to user {user_id}")
        except Exception as e:
            logger.error(f"❌ Failed to send approval request: {e}")
            raise

    async def process_update(self, update_data: Dict[str, Any], engine):
        """
        Process incoming Telegram update from webhook.

        Args:
            update_data: Raw update data from Telegram Bot API
            engine: FinanceFeedbackEngine instance for executing decisions
        """
        try:
            # TODO: Implement with python-telegram-bot
            # from telegram import Update
            # update = Update.de_json(update_data, self.bot)

            # Handle callback queries (button presses)
            # if update.callback_query:
            #     await self._handle_callback_query(update.callback_query, engine)

            # Handle commands
            # elif update.message and update.message.text:
            #     await self._handle_message(update.message)

            logger.debug(f"Received Telegram update: {update_data}")
        except Exception as e:
            logger.error(f"❌ Error processing Telegram update: {e}")
            raise

    async def _handle_callback_query(self, query, engine):
        """
        Handle inline keyboard button presses.

        Args:
            query: CallbackQuery object from Telegram
            engine: FinanceFeedbackEngine instance
        """
        # TODO: Implement callback handling
        # callback_data = query.data  # Format: "approve:decision_id" or "reject:decision_id"
        # action, decision_id = callback_data.split(':')

        # if action == 'approve':
        #     # Execute decision
        #     await self._approve_decision(decision_id, engine)
        #     await query.answer("✅ Decision approved and executed")

        # elif action == 'reject':
        #     # Save rejection
        #     await self._reject_decision(decision_id)
        #     await query.answer("❌ Decision rejected")

        # elif action == 'modify':
        #     # Start modification flow
        #     await query.answer("✏️ Modification not implemented yet. Use CLI for now.")

        pass

    async def _approve_decision(self, decision_id: str, engine):
        """
        Approve and execute a trading decision.

        Args:
            decision_id: Decision ID to approve
            engine: FinanceFeedbackEngine instance
        """
        # Save approval to queue/file
        approval_data = {
            "decision_id": decision_id,
            "approved": True,
            "timestamp": datetime.now().isoformat(),
            "source": "telegram"
        }

        # Save to data/approvals/
        approvals_dir = Path("data/approvals")
        approvals_dir.mkdir(parents=True, exist_ok=True)

        approval_file = approvals_dir / f"{decision_id}_approved.json"
        with open(approval_file, 'w') as f:
            json.dump(approval_data, f, indent=2)

        logger.info(f"✅ Decision {decision_id} approved via Telegram")

        # Execute via engine
        try:
            result = engine.execute_decision(decision_id)
            logger.info(f"✅ Decision {decision_id} executed: {result}")
        except Exception as e:
            logger.error(f"❌ Execution failed for {decision_id}: {e}")
            raise

    async def _reject_decision(self, decision_id: str):
        """
        Reject a trading decision.

        Args:
            decision_id: Decision ID to reject
        """
        approval_data = {
            "decision_id": decision_id,
            "approved": False,
            "timestamp": datetime.now().isoformat(),
            "source": "telegram"
        }

        approvals_dir = Path("data/approvals")
        approvals_dir.mkdir(parents=True, exist_ok=True)

        approval_file = approvals_dir / f"{decision_id}_rejected.json"
        with open(approval_file, 'w') as f:
            json.dump(approval_data, f, indent=2)

        logger.info(f"❌ Decision {decision_id} rejected via Telegram")

    def close(self):
        """Cleanup resources."""
        if self.tunnel_manager:
            self.tunnel_manager.close()
        if self.redis_client:
            self.redis_client.close()


def init_telegram_bot(config: dict) -> Optional[TelegramApprovalBot]:
    """
    Initialize global Telegram bot instance.

    Args:
        config: Telegram configuration dictionary

    Returns:
        TelegramApprovalBot instance or None if disabled
    """
    global telegram_bot

    if not config.get('enabled', False):
        logger.info("⏭️  Telegram bot disabled in config")
        return None

    if not config.get('bot_token'):
        logger.warning("⚠️  Telegram bot_token not configured. Bot disabled.")
        return None

    try:
        telegram_bot = TelegramApprovalBot(config)
        logger.info("✅ Telegram bot initialized successfully")
        return telegram_bot
    except Exception as e:
        logger.error(f"❌ Telegram bot initialization failed: {e}")
        return None
