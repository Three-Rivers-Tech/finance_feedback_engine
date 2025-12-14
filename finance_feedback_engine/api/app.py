"""FastAPI application with lifespan management for Finance Feedback Engine."""

import logging
import yaml
from contextlib import asynccontextmanager
from typing import Dict, Any
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

    config = {}

    # 1. Load local config first (preferred)
    if local_config_path.exists():
        with open(local_config_path, 'r', encoding='utf-8') as f:
            local_config = yaml.safe_load(f)
            if local_config:
                config.update(local_config)

    # 2. Load base config and fill missing keys
    if base_config_path.exists():
        with open(base_config_path, 'r', encoding='utf-8') as f:
            base_config = yaml.safe_load(f)
            if base_config:
                # Fill missing keys from base config
                for key, value in base_config.items():
                    if key not in config:
                        config[key] = value

    return config


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifespan (startup and shutdown).

    Startup: Initialize FinanceFeedbackEngine and Telegram bot
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

        # Initialize Telegram bot if enabled in config
        telegram_config = config.get('telegram', {})
        if telegram_config.get('enabled', False):
            from ..integrations.telegram_bot import init_telegram_bot
            bot = init_telegram_bot(telegram_config)
            if bot:
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
            if hasattr(engine, 'close'):
                await engine.close()
        app_state.clear()
        logger.info("✅ Shutdown complete")


# Create FastAPI application with lifespan
app = FastAPI(
    title="Finance Feedback Engine API",
    description="AI-powered trading decision engine with autonomous agent capabilities",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware for localhost development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:*", "http://127.0.0.1:*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import and include routers
from .routes import health_router, metrics_router, telegram_router, decisions_router, status_router

app.include_router(health_router, tags=["health"])
app.include_router(metrics_router, tags=["metrics"])
app.include_router(telegram_router, prefix="/webhook", tags=["telegram"])
app.include_router(decisions_router, prefix="/api/v1", tags=["decisions"])
app.include_router(status_router, prefix="/api/v1", tags=["status"])


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Finance Feedback Engine API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "metrics": "/metrics"
    }
