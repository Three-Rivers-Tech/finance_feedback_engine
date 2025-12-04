"""FastAPI application with lifespan management for Finance Feedback Engine."""

import logging
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..core import FinanceFeedbackEngine

logger = logging.getLogger(__name__)

# Shared application state
app_state: Dict[str, Any] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifespan (startup and shutdown).
    
    Startup: Initialize FinanceFeedbackEngine
    Shutdown: Cleanup resources
    """
    logger.info("🚀 Starting Finance Feedback Engine API...")
    
    try:
        # Initialize the engine (loads config from environment/config files)
        engine = FinanceFeedbackEngine()
        app_state["engine"] = engine
        logger.info("✅ Engine initialized successfully")
        
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
