"""Tunnel manager for exposing local webhooks (ngrok auto-setup with custom domain support)."""

import logging
import os
import threading

logger = logging.getLogger(__name__)


class TunnelManager:
    """
    Manages ngrok tunnel for webhook endpoints with custom domain scaffolding.

    Provides automatic ngrok tunnel setup with easy replacement for production domains.
    Supports context manager protocol for deterministic cleanup.

    Usage:
        # Context manager (recommended):
        with TunnelManager(config) as tunnel:
            url = tunnel.get_public_url(port=8000)
            # ... use webhook URL ...
        # Tunnel automatically closed on exit

        # Manual cleanup (for long-lived instances):
        tunnel = TunnelManager(config)
        try:
            url = tunnel.get_public_url(port=8000)
            # ... use webhook URL ...
        finally:
            tunnel.close()
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
        self._public_port = None
        self._lock = threading.Lock()

    def get_public_url(self, port: int = 8000) -> str:
        """
        Get public URL for webhook, using custom domain or auto-starting ngrok.

        Workflow:
        1. Check if custom webhook_url is configured (production)
        2. If not, auto-start ngrok tunnel (development)
        3. Return public HTTPS URL

        Port tracking ensures cached URLs match the requested port.

        Args:
            port: Local port to expose (default: 8000)

        Returns:
            Public HTTPS URL for webhook registration
        """
        # Check for custom domain first (production setup)
        custom_url = self.config.get('webhook_url')
        if custom_url:
            logger.info(f"✅ Using custom webhook URL: {custom_url} (port: {port})")
            self._public_url = custom_url
            self._public_port = port
            return custom_url

        # Auto-setup ngrok tunnel (development)
        return self._setup_ngrok_tunnel(port)

    def _setup_ngrok_tunnel(self, port: int) -> str:
        """
        Auto-setup ngrok tunnel for local development (idempotent).

        Checks for existing active tunnel before creating a new one.
        Validates that cached tunnel matches the requested port.
        Thread-safe for concurrent calls.

        Args:
            port: Local port to tunnel

        Returns:
            Public ngrok URL

        Raises:
            RuntimeError: If ngrok setup fails
        """
        with self._lock:
            # Check if we already have an active tunnel
            if self.tunnel and self._public_url and self._public_port is not None:
                # Port mismatch - need to recreate tunnel for new port
                if self._public_port != port:
                    logger.info(f"🔄 Port changed ({self._public_port} → {port}), recreating tunnel...")
                    try:
                        from pyngrok import ngrok
                        ngrok.disconnect(self.tunnel.public_url)
                    except Exception as e:
                        logger.warning(f"Failed to disconnect old tunnel: {e}")
                    self.tunnel = None
                    self._public_url = None
                    self._public_port = None
                else:
                    # Port matches - check if tunnel is still active
                    try:
                        from pyngrok import ngrok
                        # Verify tunnel is still active by checking ngrok's tunnel list
                        active_tunnels = ngrok.get_tunnels()
                        if any(t.public_url == self._public_url for t in active_tunnels):
                            logger.debug(f"♻️  Reusing existing ngrok tunnel: {self._public_url} (port: {port})")
                            return self._public_url
                        else:
                            # Tunnel object exists but is no longer active - clean up
                            logger.info("🧹 Existing tunnel is closed, creating new one...")
                            self.tunnel = None
                            self._public_url = None
                            self._public_port = None
                    except Exception as e:
                        # Error checking tunnel status - assume stale, clean up
                        logger.warning(f"⚠️  Tunnel validation failed ({e}), recreating...")
                        self.tunnel = None
                        self._public_url = None
                        self._public_port = None

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
                self._public_port = port

                logger.warning(
                    f"⚠️  Using ngrok tunnel: {self._public_url} (port: {port})\n"
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
        """Close ngrok tunnel if active. Safe to call multiple times."""
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
                self._public_port = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures cleanup."""
        try:
            self.close()
        except Exception as e:
            logger.error(f"Error during context manager cleanup: {e}")
        # Suppress exceptions during cleanup to avoid masking original exceptions
        return False

    def __del__(self):
        """Fallback cleanup on deletion (context manager preferred)."""
        try:
            self.close()
        except Exception:
            pass  # Suppress all exceptions in __del__
