"""Tunnel manager for exposing local webhooks (ngrok auto-setup with custom domain support)."""

import logging
from typing import Optional
import os

logger = logging.getLogger(__name__)


class TunnelManager:
    """
    Manages ngrok tunnel for webhook endpoints with custom domain scaffolding.

    Provides automatic ngrok tunnel setup with easy replacement for production domains.
    """

    def __init__(self, config: dict):
        """
        Initialize tunnel manager.

        Args:
            config: Telegram configuration dict with webhook_url and ngrok settings
        """
        self.config = config
        self.tunnel = None
        self._public_url = None

    def get_public_url(self, port: int = 8000) -> str:
        """
        Get public URL for webhook, using custom domain or auto-starting ngrok.

        Workflow:
        1. Check if custom webhook_url is configured (production)
        2. If not, auto-start ngrok tunnel (development)
        3. Return public HTTPS URL

        Args:
            port: Local port to expose (default: 8000)

        Returns:
            Public HTTPS URL for webhook registration
        """
        # Check for custom domain first (production setup)
        custom_url = self.config.get('webhook_url')
        if custom_url:
            logger.info(f"✅ Using custom webhook URL: {custom_url}")
            self._public_url = custom_url
            return custom_url

        # Auto-setup ngrok tunnel (development)
        return self._setup_ngrok_tunnel(port)

    def _setup_ngrok_tunnel(self, port: int) -> str:
        """
        Auto-setup ngrok tunnel for local development.

        Args:
            port: Local port to tunnel

        Returns:
            Public ngrok URL

        Raises:
            RuntimeError: If ngrok setup fails
        """
        try:
            from pyngrok import ngrok, conf

            # Set auth token if provided
            auth_token = self.config.get('ngrok_auth_token') or os.environ.get('NGROK_AUTHTOKEN')
            if auth_token:
                conf.get_default().auth_token = auth_token
            else:
                logger.warning(
                    "⚠️  No ngrok auth token found. Free tier limits: 40 req/min, 20 conn/min. "
                    "Set telegram.ngrok_auth_token in config or NGROK_AUTHTOKEN env var."
                )

            # Connect to ngrok
            logger.info(f"🔧 Starting ngrok tunnel on port {port}...")
            self.tunnel = ngrok.connect(port, "http")
            self._public_url = self.tunnel.public_url

            logger.warning(
                f"⚠️  Using ngrok tunnel: {self._public_url}\n"
                f"   This URL changes on restart. For production:\n"
                f"   1. Set telegram.webhook_url in config/telegram.yaml\n"
                f"   2. Configure nginx reverse proxy or Cloudflare Tunnel\n"
                f"   3. See docs/TELEGRAM_APPROVAL.md for details"
            )

            return self._public_url
        except ImportError:
            raise RuntimeError(
                "pyngrok not installed. Install with: pip install pyngrok"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to start ngrok tunnel: {e}")

    def close(self):
        """Close ngrok tunnel if active."""
        if self.tunnel:
            try:
                from pyngrok import ngrok
                ngrok.disconnect(self.tunnel.public_url)
                logger.info("✅ ngrok tunnel closed")
            except Exception as e:
                logger.error(f"Failed to close ngrok tunnel: {e}")
            finally:
                self.tunnel = None
                self._public_url = None

    def __del__(self):
        """Cleanup on deletion."""
        self.close()
