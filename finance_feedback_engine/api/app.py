"""FastAPI application with lifespan management for Finance Feedback Engine."""

import logging
import os

# Ensure library stubs are installed for type checking
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict

import yaml
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..auth import AuthManager
from ..core import FinanceFeedbackEngine

logger = logging.getLogger(__name__)

# Shared application state
app_state: Dict[str, Any] = {}


def load_tiered_config() -> dict:
    """
    Load configuration with tiered fallback: local → base config.
    This matches the CLI's config loading behavior.
    """
    config_dir = Path(__file__).parent.parent.parent / "config"
    local_config_path = config_dir / "config.local.yaml"
    base_config_path = config_dir / "config.yaml"

    config: Dict[str, Any] = {}

    # 1. Load local config first (preferred)
    if local_config_path.exists():
        try:
            with open(local_config_path, "r", encoding="utf-8") as f:
                local_config = yaml.safe_load(f)
                if local_config:
                    config.update(local_config)
        except (OSError, IOError) as e:
            raise RuntimeError(
                f"Error loading local config from {local_config_path}: {e}"
            ) from e
        except yaml.YAMLError as e:
            raise RuntimeError(
                f"YAML error in local config {local_config_path}: {e}"
            ) from e

    # 2. Load base config and fill missing keys
    if base_config_path.exists():
        try:
            with open(base_config_path, "r", encoding="utf-8") as f:
                base_config = yaml.safe_load(f)
                if base_config:
                    # Fill missing keys from base config
                    for key, value in base_config.items():
                        if key not in config:
                            config[key] = value
        except (OSError, IOError) as e:
            raise RuntimeError(
                f"Error loading base config from {base_config_path}: {e}"
            ) from e
        except yaml.YAMLError as e:
            raise RuntimeError(
                f"YAML error in base config {base_config_path}: {e}"
            ) from e

    # Validate that at least one config is loaded
    if not config:
        raise ValueError(
            "No valid configuration loaded from local or base config files."
        )

    return config


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifespan (startup and shutdown).

    Startup: Initialize FinanceFeedbackEngine, AuthManager, and Telegram bot
    Shutdown: Cleanup resources
    """
    logger.info("🚀 Starting Finance Feedback Engine API...")

    try:
        # Load configuration from tiered config files
        config = load_tiered_config()

        # Initialize the engine with loaded config
        engine = FinanceFeedbackEngine(config)
        app_state["engine"] = engine
        logger.info("✅ Engine initialized successfully")

        # Initialize Authentication Manager with secure API key validation
        logger.info("🔐 Initializing secure authentication manager...")

        # Collect API keys from config (for fallback validation)
        config_keys = {}
        if "api_keys" in config:
            # Support explicit API key configuration
            api_keys_config = config.get("api_keys", {})
            if isinstance(api_keys_config, dict):
                config_keys = {
                    name: api_key
                    for name, api_key in api_keys_config.items()
                    if isinstance(api_key, str) and api_key
                }

        # Also check environment variable (production best practice)
        env_api_key = os.getenv("FINANCE_FEEDBACK_API_KEY")
        if env_api_key:
            config_keys["default"] = env_api_key

        # Initialize auth manager with rate limiting from config
        rate_limit_config = config.get("api_auth", {})
        auth_manager = AuthManager(
            config_keys=config_keys,
            rate_limit_max=rate_limit_config.get("rate_limit_max", 100),
            rate_limit_window=rate_limit_config.get("rate_limit_window", 60),
            enable_fallback_to_config=rate_limit_config.get(
                "enable_fallback_to_config", True
            ),
        )
        app_state["auth_manager"] = auth_manager
        logger.info("✅ Authentication manager initialized with secure validation")

        # Log initial setup statistics
        stats = auth_manager.get_key_stats()
        logger.debug(f"📊 Authentication stats: {stats}")

        # Initialize Telegram bot if enabled in config
        telegram_config = config.get("telegram", {})
        if telegram_config.get("enabled", False):
            from ..integrations.telegram_bot import init_telegram_bot

            bot = init_telegram_bot(telegram_config)
            if bot:
                app_state["telegram_bot"] = bot
                logger.info("✅ Telegram bot initialized and ready for webhooks")
            else:
                logger.warning("⚠️  Telegram bot initialization failed")

        yield  # Application runs here

    finally:
        # Cleanup on shutdown
        logger.info("🛑 Shutting down Finance Feedback Engine API...")
        if "engine" in app_state:
            # Close any async resources
            engine = app_state["engine"]
            if hasattr(engine, "close"):
                await engine.close()
        app_state.clear()
        logger.info("✅ Shutdown complete")


# Create FastAPI application with lifespan
app = FastAPI(
    title="Finance Feedback Engine API",
    description="AI-powered trading decision engine with autonomous agent capabilities",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware for localhost development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:*", "http://127.0.0.1:*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from .bot_control import bot_control_router

# Import and include routers
from .routes import (
    decisions_router,
    health_router,
    metrics_router,
    status_router,
    telegram_router,
)

app.include_router(health_router, tags=["health"])
app.include_router(metrics_router, tags=["metrics"])
app.include_router(telegram_router, prefix="/webhook", tags=["telegram"])
app.include_router(decisions_router, prefix="/api/v1", tags=["decisions"])
app.include_router(status_router, prefix="/api/v1", tags=["status"])
app.include_router(bot_control_router, tags=["bot-control"])


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Finance Feedback Engine API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "metrics": "/metrics",
    }
