"""
Comprehensive Bot Control API - Full control over the trading agent.

Provides endpoints for:
- Starting/stopping the agent
- Real-time status monitoring
- Configuration updates
- Manual trading controls
- Emergency stop
- Performance metrics
"""

import asyncio
import copy
import json
import logging
import queue
import time
from datetime import datetime
from enum import Enum
from typing import Any, AsyncIterator, Dict, List, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from ..agent.config import TradingAgentConfig
from ..agent.trading_loop_agent import TradingLoopAgent
from ..core import FinanceFeedbackEngine
from ..memory.portfolio_memory_adapter import PortfolioMemoryEngineAdapter
from ..monitoring.trade_monitor import TradeMonitor
from .dependencies import get_auth_manager, get_engine, verify_api_key_or_dev

logger = logging.getLogger(__name__)

# ===== Model Definitions (must be defined before use in type hints) =====
class BotState(str, Enum):
    """Bot operational states."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


class AgentControlRequest(BaseModel):
    """Request model for agent control operations."""

    asset_pairs: Optional[List[str]] = Field(
        None, description="Asset pairs to trade (overrides config)"
    )
    autonomous: bool = Field(True, description="Whether to run in autonomous mode")
    take_profit: Optional[float] = Field(
        None, ge=0.001, le=1.0, description="Take profit percentage (0.001 to 1.0)"
    )
    stop_loss: Optional[float] = Field(
        None, ge=0.001, le=1.0, description="Stop loss percentage (0.001 to 1.0)"
    )
    max_concurrent_trades: Optional[int] = Field(
        None, ge=1, le=10, description="Maximum concurrent trades"
    )


# ===== Router & Global State =====
# Router for bot control endpoints
# Note: Authentication is handled per-endpoint (WebSocket needs special handling)
bot_control_router = APIRouter(
    prefix="/api/v1/bot",
    tags=["bot-control"],
)

# Global agent instance management
_agent_instance: Optional[TradingLoopAgent] = None
_agent_task: Optional[asyncio.Task[None]] = None
_agent_lock = asyncio.Lock()
_queued_start_request: Optional[AgentControlRequest] = None


def is_agent_running() -> bool:
    """Return True if the trading agent is currently running."""
    return (
        _agent_instance is not None
        and _agent_task is not None
        and not _agent_task.done()
    )


class AgentStatusResponse(BaseModel):
    """Response model for agent status."""

    state: BotState
    agent_ooda_state: Optional[str] = None
    uptime_seconds: Optional[float] = None
    total_trades: int = 0
    active_positions: int = 0
    portfolio_value: Optional[float] = None
    daily_pnl: Optional[float] = None
    current_asset_pair: Optional[str] = None
    last_decision_time: Optional[datetime] = None
    error_message: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)
    # Optional enriched portfolio payload (development mode)
    balances: Optional[Dict[str, float]] = None
    portfolio: Optional[Dict[str, Any]] = None


class ManualTradeRequest(BaseModel):
    """Request model for manual trade execution."""

    asset_pair: str = Field(..., description="Asset pair to trade")
    action: str = Field(..., description="Trade action: BUY or SELL")
    size: Optional[float] = Field(
        None, description="Position size (uses default if not specified)"
    )
    price: Optional[float] = Field(
        None, description="Limit price (market order if not specified)"
    )
    stop_loss: Optional[float] = Field(None, description="Stop loss price")
    take_profit: Optional[float] = Field(None, description="Take profit price")

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        if v.upper() not in ["BUY", "SELL", "LONG", "SHORT"]:
            raise ValueError("Action must be BUY, SELL, LONG, or SHORT")
        return v.upper()


class ConfigUpdateRequest(BaseModel):
    """Request model for configuration updates."""

    stop_loss_pct: Optional[float] = Field(None, ge=0.001, le=0.1)
    position_size_pct: Optional[float] = Field(None, ge=0.001, le=0.05)
    confidence_threshold: Optional[float] = Field(None, ge=0.5, le=1.0)
    max_concurrent_trades: Optional[int] = Field(None, ge=1, le=10)
    provider_weights: Optional[Dict[str, float]] = None

    @field_validator("provider_weights")
    @classmethod
    def validate_weights(
        cls, v: Optional[Dict[str, float]]
    ) -> Optional[Dict[str, float]]:
        if v is not None:
            total = sum(v.values())
            if not (0.99 <= total <= 1.01):
                raise ValueError("Provider weights must sum to 1.0")
        return v


# ==========================================================================
# Internal helpers
# ==========================================================================


async def _start_queued_if_any(engine: FinanceFeedbackEngine) -> None:
    """Start the next queued agent request once the agent becomes idle."""
    global _queued_start_request

    try:
        async with _agent_lock:
            if _queued_start_request is None:
                return
            if is_agent_running():
                return

            # Coalesce to the latest queued request
            request = _queued_start_request
            _queued_start_request = None

        await _start_agent_from_request(request, engine)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to start queued agent: %s", exc, exc_info=True)


async def _start_agent_from_request(
    request: AgentControlRequest,
    engine: FinanceFeedbackEngine,
) -> AgentStatusResponse:
    """Create and launch the trading agent from the provided request."""
    global _agent_instance, _agent_task

    logger.info("Starting trading agent from request (queued=%s)", False)

    # Create config from request
    config_snapshot = copy.deepcopy(engine.config)
    agent_cfg_data = config_snapshot.get("agent", {})

    # Ensure agent_cfg_data is a dict (handle case where it might be a TradingAgentConfig object)
    if isinstance(agent_cfg_data, TradingAgentConfig):
        agent_cfg_data = agent_cfg_data.model_dump()
    elif not isinstance(agent_cfg_data, dict):
        agent_cfg_data = {}

    agent_config = TradingAgentConfig(**agent_cfg_data)

    if request.asset_pairs:
        agent_config.asset_pairs = request.asset_pairs
        agent_config.watchlist = request.asset_pairs

    if request.max_concurrent_trades:
        agent_config.max_daily_trades = request.max_concurrent_trades

    if request.autonomous:
        agent_config.autonomous.enabled = True

    take_profit = float(request.take_profit or 0.0)
    stop_loss = float(request.stop_loss or 0.0)

    portfolio_memory = engine.memory_engine or PortfolioMemoryEngineAdapter(
        config_snapshot
    )
    engine.memory_engine = portfolio_memory

    trade_monitor = engine.trade_monitor
    if trade_monitor is None:
        trade_monitor = TradeMonitor(
            platform=engine.trading_platform,
            portfolio_memory=portfolio_memory,
            portfolio_take_profit_percentage=take_profit,
            portfolio_stop_loss_percentage=stop_loss,
        )
        if hasattr(engine, "enable_monitoring_integration"):
            engine.enable_monitoring_integration(trade_monitor=trade_monitor)
        trade_monitor.start()

    # Initialize agent
    _agent_instance = TradingLoopAgent(
        config=agent_config,
        engine=engine,
        trade_monitor=trade_monitor,
        portfolio_memory=portfolio_memory,
        trading_platform=engine.trading_platform,
    )

    # Start agent in background
    async def run_agent() -> None:
        global _agent_instance, _agent_task
        try:
            assert _agent_instance is not None  # Guaranteed by closure
            await _agent_instance.run()
        except Exception as e:  # noqa: BLE001
            logger.error(f"Agent crashed: {e}", exc_info=True)
        finally:
            # Clean up global state when agent stops (gracefully or via crash)
            logger.info("Cleaning up agent state...")
            _agent_instance = None
            _agent_task = None

    _agent_task = asyncio.create_task(run_agent())

    # When the agent stops, automatically launch any queued start request
    _agent_task.add_done_callback(
        lambda _: asyncio.create_task(_start_queued_if_any(engine))
    )

    logger.info("✅ Trading agent started successfully")

    return AgentStatusResponse(
        state=BotState.RUNNING,
        agent_ooda_state=(_agent_instance.state.name if _agent_instance else None),
        uptime_seconds=0.0,
        config={
            "asset_pairs": request.asset_pairs,
            "autonomous": request.autonomous,
        },
    )


async def _enqueue_or_start_agent(
    request: AgentControlRequest,
    engine: FinanceFeedbackEngine,
) -> tuple[Optional[AgentStatusResponse], bool]:
    """Start the agent immediately or queue the latest start request."""
    global _queued_start_request

    async with _agent_lock:
        if is_agent_running():
            logger.info("Agent already running; queuing start request for later")
            _queued_start_request = request
            return None, True

        response = await _start_agent_from_request(request, engine)
        return response, False


def _extract_bearer_from_websocket(websocket: WebSocket) -> tuple[Optional[str], Optional[str]]:
    """Extract bearer token and selected subprotocol from WebSocket handshake headers or query params."""

    # Try Authorization header first
    auth_header = websocket.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:], None

    # Try query parameter (token=...)
    query_params = websocket.query_params
    if "token" in query_params:
        return query_params["token"], None

    # Try Sec-WebSocket-Protocol header (legacy support)
    protocol_header = websocket.headers.get("sec-websocket-protocol", "")
    protocols = [p.strip() for p in protocol_header.split(",") if p.strip()]
    for proto in protocols:
        if proto.lower().startswith("bearer "):
            # Return the first bearer token and echo it as accepted subprotocol
            return proto[7:], proto

    return None, protocols[0] if protocols else None


# ============================================================================
# BOT CONTROL ENDPOINTS
# ============================================================================


@bot_control_router.post("/start", response_model=AgentStatusResponse)
async def start_agent(
    request: AgentControlRequest,
    background_tasks: BackgroundTasks,
    _api_user: str = Depends(verify_api_key_or_dev),
    engine: FinanceFeedbackEngine = Depends(get_engine),
) -> AgentStatusResponse:
    """
    Start the trading agent.

    Initializes and starts the autonomous trading loop with specified parameters.
    """
    global _agent_instance, _agent_task

    try:
        logger.info("Starting trading agent via API...")

        response, queued = await _enqueue_or_start_agent(request, engine)
        if queued:
            assert response is None  # When queued, response is None
            return AgentStatusResponse(
                state=BotState.STARTING,
                agent_ooda_state=None,
                uptime_seconds=None,
                config={
                    "queued": True,
                    "asset_pairs": request.asset_pairs,
                    "autonomous": request.autonomous,
                },
            )

        assert response is not None  # When not queued, response must be non-None
        return response

    except HTTPException:
        # Re-raise HTTPExceptions with their original status codes
        raise
    except Exception as e:
        logger.error(f"Failed to start agent: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start agent: {str(e)}",
        )


@bot_control_router.post("/stop")
async def stop_agent(
    _api_user: str = Depends(verify_api_key_or_dev),
) -> Dict[str, str]:
    """
    Stop the trading agent.

    Gracefully shuts down the trading loop and closes open positions (if configured).
    """
    global _agent_instance, _agent_task

    try:
        logger.info("Stopping trading agent...")

        async with _agent_lock:
            if _agent_instance is None or _agent_task is None or _agent_task.done():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Agent is not running"
                )

            # Signal agent to stop
            if hasattr(_agent_instance, "stop"):
                _agent_instance.stop()

            # Cancel the task
            _agent_task.cancel()

            try:
                await asyncio.wait_for(_agent_task, timeout=10.0)
            except asyncio.TimeoutError:
                logger.warning("Agent didn't stop gracefully, forcing termination")
            except asyncio.CancelledError:
                logger.info("Agent task cancelled")

            _agent_instance = None
            _agent_task = None

        logger.info("✅ Trading agent stopped")

        return {"status": "stopped", "message": "Agent stopped successfully"}

    except HTTPException:
        # Re-raise HTTPExceptions with their original status codes
        raise
    except Exception as e:
        logger.error(f"Error stopping agent: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error stopping agent: {str(e)}",
        )


@bot_control_router.post("/emergency-stop")
async def emergency_stop(
    close_positions: bool = True,
    _api_user: str = Depends(verify_api_key_or_dev),
    engine: FinanceFeedbackEngine = Depends(get_engine),
) -> Dict[str, Any]:
    """
    EMERGENCY STOP - Immediately halt all trading.

    This will:
    1. Stop the agent immediately
    2. Optionally close all open positions at market price
    3. Log the emergency stop event
    """
    global _agent_instance, _agent_task

    logger.critical("🚨 EMERGENCY STOP TRIGGERED")

    try:
        async with _agent_lock:
            # Force stop agent
            if _agent_task is not None:
                _agent_task.cancel()
                try:
                    await _agent_task
                except asyncio.CancelledError:
                    pass
                _agent_instance = None
                _agent_task = None

            # Close positions if requested
            closed_positions = []
            platform = getattr(engine, "trading_platform", None)
            if close_positions and platform:
                logger.warning("Closing all open positions...")

                # Get open positions
                if hasattr(platform, "aget_portfolio_breakdown"):
                    breakdown = await platform.aget_portfolio_breakdown()
                    positions = breakdown.get("positions", [])

                    for position in positions:
                        try:
                            # Execute close trade without blocking the event loop
                            result = await platform.aexecute_trade(
                                {
                                    "asset_pair": position["asset_pair"],
                                    "action": (
                                        "SELL"
                                        if position.get("side") == "LONG"
                                        else "BUY"
                                    ),
                                    "size": position.get("size", 0),
                                    "order_type": "MARKET",
                                }
                            )
                            closed_positions.append(result)
                        except Exception as e:
                            logger.error(
                                f"Failed to close position {position.get('id', 'unknown')}: {e}"
                            )

            logger.critical("Emergency stop executed")

        return {
            "status": "emergency_stopped",
            "message": "Emergency stop executed",
            "closed_positions": len(closed_positions),
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.critical(f"Emergency stop failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Emergency stop failed: {str(e)}",
        )


@bot_control_router.post("/pause", response_model=AgentStatusResponse)
async def pause_agent(
    _api_user: str = Depends(verify_api_key_or_dev),
) -> AgentStatusResponse:
    """
    Pause the trading agent.

    Temporarily halts the trading loop without closing positions. The agent can be
    resumed later with the /resume endpoint.
    """
    global _agent_instance, _agent_task

    try:
        logger.info("Pausing trading agent...")

        async with _agent_lock:
            if _agent_instance is None or _agent_task is None or _agent_task.done():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Agent is not running - cannot pause an agent that isn't started"
                )

            # Set flag to pause (stop accepting new decisions)
            # The agent will continue to monitor existing positions
            # Use public pause() method instead of directly setting attributes
            if not _agent_instance.pause():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Failed to pause agent: agent is not running",
                )

            logger.info("✅ Trading agent paused")

            # Return current status
            uptime = None
            if hasattr(_agent_instance, "start_time"):
                uptime = (
                    datetime.utcnow() - _agent_instance.start_time
                ).total_seconds()

            return AgentStatusResponse(
                state=BotState.STOPPED,
                agent_ooda_state=(
                    _agent_instance.state.name
                    if _agent_instance and hasattr(_agent_instance, "state")
                    else None
                ),
                uptime_seconds=uptime,
                config={"paused": True},
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error pausing agent: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error pausing agent: {str(e)}",
        )


@bot_control_router.post("/resume", response_model=AgentStatusResponse)
async def resume_agent(
    _api_user: str = Depends(verify_api_key_or_dev),
) -> AgentStatusResponse:
    """
    Resume the trading agent.

    Resumes a paused agent to continue trading. Only works if the agent was previously
    paused (not stopped or crashed).
    """
    global _agent_instance, _agent_task

    try:
        logger.info("Resuming trading agent...")

        async with _agent_lock:
            if _agent_instance is None or _agent_task is None or _agent_task.done():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Agent is not running - cannot resume an agent that isn't started",
                )

            # Check if agent was paused (use safe getattr with default False)
            if not getattr(_agent_instance, "_paused", False):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Agent is not paused",
                )

            # Resume agent using public method
            if not _agent_instance.resume():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Failed to resume agent: agent is not paused",
                )

            logger.info("✅ Trading agent resumed")

            # Return current status
            uptime = None
            if hasattr(_agent_instance, "start_time"):
                uptime = (
                    datetime.utcnow() - _agent_instance.start_time
                ).total_seconds()

            return AgentStatusResponse(
                state=BotState.RUNNING,
                agent_ooda_state=(
                    _agent_instance.state.name
                    if _agent_instance and hasattr(_agent_instance, "state")
                    else None
                ),
                uptime_seconds=uptime,
                config={"paused": False},
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resuming agent: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error resuming agent: {str(e)}",
        )


async def _get_agent_status_internal(engine: FinanceFeedbackEngine) -> AgentStatusResponse:
    """
    Internal helper to get agent status without dependency injection.
    Used by both the API endpoint and internal callers.
    """
    global _agent_instance, _agent_task

    try:
        # Determine environment
        import os
        is_development = os.environ.get("ENVIRONMENT", "").lower() == "development"

        # Agent running state
        agent_running = (
            _agent_instance is not None and _agent_task is not None and not _agent_task.done()
        )
        agent_state = _agent_instance.state if (_agent_instance and agent_running) else None

        # Portfolio info (always attempt, even if agent is stopped)
        portfolio_value = None
        active_positions = 0
        balances_payload: Optional[Dict[str, float]] = None
        portfolio_payload: Optional[Dict[str, Any]] = None

        platform = getattr(engine, "trading_platform", None)

        if platform:
            try:
                # Try async balance first, fall back to sync via executor
                if hasattr(platform, "aget_balance"):
                    balance = await asyncio.wait_for(platform.aget_balance(), timeout=3.0)
                else:
                    loop = asyncio.get_running_loop()
                    balance = await asyncio.wait_for(
                        loop.run_in_executor(None, platform.get_balance), timeout=3.0
                    )

                if isinstance(balance, dict):
                    balances_payload = balance
                    portfolio_value = balance.get("total") or balance.get("balance")

                # Get breakdown
                breakdown = None
                if hasattr(platform, "aget_portfolio_breakdown"):
                    breakdown = await asyncio.wait_for(
                        platform.aget_portfolio_breakdown(), timeout=3.0
                    )
                elif hasattr(platform, "get_portfolio_breakdown"):
                    loop = asyncio.get_running_loop()
                    breakdown = await asyncio.wait_for(
                        loop.run_in_executor(None, platform.get_portfolio_breakdown),
                        timeout=3.0,
                    )

                if isinstance(breakdown, dict):
                    portfolio_payload = breakdown
                    # Prefer explicit positions list if available, else derive
                    positions = breakdown.get("positions") or breakdown.get("futures_positions") or []
                    active_positions = len(positions)

                    # Fallback: infer portfolio value from breakdown if balance lacks totals
                    if portfolio_value is None:
                        total_value = breakdown.get("total_value_usd")
                        if isinstance(total_value, (int, float)):
                            portfolio_value = float(total_value)

                # Final fallback: sum numeric balances when no total provided
                if portfolio_value is None and isinstance(balances_payload, dict):
                    numeric_balances = [v for v in balances_payload.values() if isinstance(v, (int, float))]
                    if numeric_balances:
                        portfolio_value = float(sum(numeric_balances))
            except asyncio.TimeoutError:
                logger.warning("Platform API call timed out after 3 seconds")
            except Exception as e:
                logger.warning(f"Could not fetch portfolio info: {e}")

        # Calculate uptime
        uptime = None
        if _agent_instance and hasattr(_agent_instance, "start_time"):
            uptime = (datetime.utcnow() - _agent_instance.start_time).total_seconds()

        # Fetch total trades and daily PnL from agent/monitor
        total_trades = 0
        daily_pnl = None
        if _agent_instance:
            # Try to get trade count from trade monitor
            trade_monitor = getattr(_agent_instance, "trade_monitor", None)
            if trade_monitor:
                try:
                    # Get today's trade count if available
                    daily_trades = getattr(trade_monitor, "daily_trade_count", 0)
                    total_trades = daily_trades
                    # Get daily PnL if available
                    if hasattr(trade_monitor, "get_daily_pnl"):
                        daily_pnl = trade_monitor.get_daily_pnl()
                except Exception:
                    pass

        # Safe access to agent config (handle both dict and object forms)
        agent_cfg = engine.config.get("agent", {})
        if isinstance(agent_cfg, TradingAgentConfig):
            asset_pairs = agent_cfg.asset_pairs
        elif isinstance(agent_cfg, dict):
            asset_pairs = agent_cfg.get("asset_pairs", [])
        else:
            asset_pairs = []

        # Build response
        resp = AgentStatusResponse(
            state=BotState.RUNNING if agent_running else BotState.STOPPED,
            agent_ooda_state=agent_state.name if agent_state else None,
            uptime_seconds=uptime,
            total_trades=total_trades,
            active_positions=active_positions,
            portfolio_value=portfolio_value,
            daily_pnl=daily_pnl,
            current_asset_pair=getattr(_agent_instance, "current_asset_pair", None),
            config={
                "asset_pairs": asset_pairs,
                "autonomous": True,
            },
        )

        # Enrich payload in development mode
        if is_development:
            resp.balances = balances_payload
            resp.portfolio = portfolio_payload

        return resp

    except Exception as e:
        logger.error(f"Error getting agent status: {e}", exc_info=True)
        return AgentStatusResponse(state=BotState.ERROR, error_message=str(e))


@bot_control_router.get("/status", response_model=AgentStatusResponse)
async def get_agent_status(
    _api_user: str = Depends(verify_api_key_or_dev),
    engine: FinanceFeedbackEngine = Depends(get_engine),
) -> AgentStatusResponse:
    """
    Get current agent status and performance metrics.
    """
    return await _get_agent_status_internal(engine)


async def _build_stream_payload(
    engine: FinanceFeedbackEngine, last_status_sent: float
) -> tuple[Dict[str, Any], float]:
    """Construct the next stream payload (dashboard event, status, or heartbeat)."""

    event_payload = None

    # Drain dashboard queue (non-blocking)
    if _agent_instance is not None and hasattr(_agent_instance, "_dashboard_event_queue"):
        try:
            loop = asyncio.get_running_loop()

            def _get_queue_item_nowait() -> Optional[Dict[str, Any]]:
                try:
                    result = _agent_instance._dashboard_event_queue.get_nowait()
                    return result if isinstance(result, dict) else None
                except queue.Empty:
                    return None

            queue_item = await asyncio.wait_for(
                loop.run_in_executor(None, _get_queue_item_nowait),
                timeout=3.0,
            )

            if queue_item is not None:
                event_payload = {
                    "event": queue_item.get("type", "event"),
                    "data": queue_item,
                }
        except asyncio.TimeoutError:
            event_payload = None
        except Exception as exc:  # noqa: BLE001
            logger.debug("Dashboard event stream read failed: %s", exc, exc_info=True)
            event_payload = None

    # If no queue event, emit periodic status + heartbeat
    if event_payload is None:
        now = time.time()
        if now - last_status_sent >= 5:
            status_payload = await _get_agent_status_internal(engine)
            status_data = (
                status_payload.model_dump(mode='json')
                if hasattr(status_payload, "model_dump")
                else status_payload.__dict__
            )
            event_payload = {"event": "status", "data": status_data}
            last_status_sent = now
        else:
            event_payload = {"event": "heartbeat", "data": {}}

    return event_payload, last_status_sent


@bot_control_router.get("/stream")
async def stream_agent_events(
    request: Request,
    _api_user: str = Depends(verify_api_key_or_dev),
    engine: FinanceFeedbackEngine = Depends(get_engine),
) -> StreamingResponse:
    """Server-Sent Events stream for live agent status and dashboard events."""

    async def event_generator() -> AsyncIterator[str]:
        last_status_sent = 0.0

        while True:
            # Stop streaming when client disconnects
            if await request.is_disconnected():
                logger.info("Client disconnected from /api/v1/bot/stream")
                break

            event_payload, last_status_sent = await _build_stream_payload(
                engine, last_status_sent
            )

            yield f"data: {json.dumps(event_payload, default=str)}\n\n"

            # Small sleep to avoid tight loop when idle
            await asyncio.sleep(0.5)

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
    }

    return StreamingResponse(event_generator(), media_type="text/event-stream", headers=headers)


@bot_control_router.websocket("/ws")
async def agent_websocket(
    websocket: WebSocket,
    engine: FinanceFeedbackEngine = Depends(get_engine),
) -> None:
    """WebSocket endpoint for live agent control and streaming events."""

    token, selected_protocol = _extract_bearer_from_websocket(websocket)
    if not token:
        await websocket.close(code=1008, reason="Missing bearer token")
        return

    # Get auth manager from engine (avoid dependency injection issues with WebSocket)
    from .dependencies import get_auth_manager_instance
    auth_manager = get_auth_manager_instance()

    client_ip = websocket.client.host if websocket.client else None
    user_agent = websocket.headers.get("user-agent")

    # Check if in development mode (skip auth)
    import os
    environment = os.getenv("ENVIRONMENT", "production").lower()
    if environment == "development":
        # Development mode: skip authentication
        pass
    else:
        # Production mode: validate API key
        try:
            is_valid, _, _ = auth_manager.validate_api_key(
                api_key=token, ip_address=client_ip, user_agent=user_agent
            )
            if not is_valid:
                await websocket.close(code=1008, reason="Invalid API key")
                return
        except ValueError:
            await websocket.close(code=1013, reason="Rate limited")
            return
        except Exception as exc:  # noqa: BLE001
            logger.warning("WebSocket auth failed: %s", exc)
            await websocket.close(code=1008, reason="Authentication failed")
            return

    await websocket.accept(subprotocol=selected_protocol)

    stop_event = asyncio.Event()

    async def sender() -> None:
        last_status_sent = 0.0
        while not stop_event.is_set():
            try:
                payload, last_status_sent = await _build_stream_payload(
                    engine, last_status_sent
                )
                await websocket.send_json(payload)
            except WebSocketDisconnect:
                logger.info("WebSocket sender: client disconnected")
                stop_event.set()
            except Exception as exc:  # noqa: BLE001
                logger.error(f"WebSocket sender error: {exc}", exc_info=True)
                stop_event.set()
            await asyncio.sleep(0.5)

    async def receiver() -> None:
        while not stop_event.is_set():
            try:
                message = await websocket.receive_json()
            except WebSocketDisconnect:
                stop_event.set()
                return
            except Exception as exc:  # noqa: BLE001
                logger.debug("WebSocket receive error: %s", exc, exc_info=True)
                stop_event.set()
                return

            action = message.get("action")
            if action == "start":
                payload = message.get("payload") or {}
                try:
                    request_model = AgentControlRequest(**payload)
                except Exception as exc:  # noqa: BLE001
                    await websocket.send_json(
                        {
                            "event": "error",
                            "data": {"message": f"Invalid start payload: {exc}"},
                        }
                    )
                    continue

                response, queued = await _enqueue_or_start_agent(
                    request_model, engine
                )
                await websocket.send_json(
                    {
                        "event": "start_ack",
                        "data": {
                            "queued": queued,
                            "state": response.state.value if response else BotState.STARTING.value,
                        },
                    }
                )
            else:
                await websocket.send_json(
                    {
                        "event": "error",
                        "data": {"message": f"Unknown action: {action}"},
                    }
                )

    # Start sender and receiver tasks immediately after accepting connection
    sender_task = asyncio.create_task(sender())
    receiver_task = asyncio.create_task(receiver())

    done, pending = await asyncio.wait(
        {sender_task, receiver_task}, return_when=asyncio.FIRST_COMPLETED
    )
    stop_event.set()

    for task in pending:
        task.cancel()

    logger.info("Client disconnected from /api/v1/bot/ws")


@bot_control_router.patch("/config")
async def update_config(
    request: ConfigUpdateRequest,
    _api_user: str = Depends(verify_api_key_or_dev),
    engine: FinanceFeedbackEngine = Depends(get_engine),
) -> Dict[str, Any]:
    """
    Update agent configuration in real-time.

    Updates take effect immediately for new decisions.
    """
    try:
        # Work on a copy to keep updates atomic and avoid partial mutations.
        config_snapshot = copy.deepcopy(engine.config)

        agent_cfg = config_snapshot.setdefault("agent", {})
        ensemble_cfg = config_snapshot.setdefault("ensemble", {})

        if not isinstance(agent_cfg, dict):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Engine config 'agent' section must be a mapping",
            )

        if not isinstance(ensemble_cfg, dict):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Engine config 'ensemble' section must be a mapping",
            )

        updates_for_agent: Dict[str, Any] = {}
        updates_for_ensemble: Dict[str, Any] = {}
        response_updates: Dict[str, Any] = {}

        if request.stop_loss_pct is not None:
            if not isinstance(request.stop_loss_pct, (int, float)):
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST, "stop_loss_pct must be numeric"
                )
            updates_for_agent["sizing_stop_loss_percentage"] = float(
                request.stop_loss_pct
            )
            response_updates["stop_loss_pct"] = float(request.stop_loss_pct)

        if request.position_size_pct is not None:
            if not isinstance(request.position_size_pct, (int, float)):
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST, "position_size_pct must be numeric"
                )
            updates_for_agent["sizing_risk_percentage"] = float(
                request.position_size_pct
            )
            response_updates["position_size_pct"] = float(request.position_size_pct)

        if request.confidence_threshold is not None:
            if not isinstance(request.confidence_threshold, (int, float)):
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST, "confidence_threshold must be numeric"
                )
            updates_for_agent["min_confidence_threshold"] = float(
                request.confidence_threshold
            )
            response_updates["confidence_threshold"] = float(
                request.confidence_threshold
            )

        if request.max_concurrent_trades is not None:
            if not isinstance(request.max_concurrent_trades, int):
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    "max_concurrent_trades must be an integer",
                )
            updates_for_agent["max_concurrent_trades"] = request.max_concurrent_trades
            response_updates["max_concurrent_trades"] = request.max_concurrent_trades

        if request.provider_weights is not None:
            if not isinstance(request.provider_weights, dict):
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST, "provider_weights must be a mapping"
                )
            updates_for_ensemble["provider_weights"] = request.provider_weights
            response_updates["provider_weights"] = request.provider_weights

        # Apply collected updates to the snapshot
        agent_cfg.update(updates_for_agent)
        ensemble_cfg.update(updates_for_ensemble)

        # Commit atomically by replacing engine.config contents
        engine.config.clear()
        engine.config.update(config_snapshot)

        logger.info(f"Configuration updated: {response_updates}")

        return {
            "status": "updated",
            "updates": response_updates,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to update config: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Config update failed: {str(e)}",
        )


@bot_control_router.post("/manual-trade")
async def execute_manual_trade(
    request: ManualTradeRequest,
    _api_user: str = Depends(verify_api_key_or_dev),
    engine: FinanceFeedbackEngine = Depends(get_engine),
) -> Dict[str, Any]:
    """
    Execute a manual trade, bypassing the autonomous agent.

    Use with caution - this directly executes on the platform.
    """
    try:
        logger.info(f"Manual trade request: {request.action} {request.asset_pair}")

        # Build trade parameters
        trade_params: Dict[str, Any] = {
            "asset_pair": request.asset_pair,
            "action": request.action,
            "order_type": "LIMIT" if request.price else "MARKET",
        }

        if request.size:
            trade_params["size"] = request.size

        if request.price:
            trade_params["price"] = request.price

        if request.stop_loss:
            trade_params["stop_loss"] = request.stop_loss

        if request.take_profit:
            trade_params["take_profit"] = request.take_profit

        platform = getattr(engine, "trading_platform", None)

        if platform is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Trading platform is not available",
            )

        # Execute trade
        result = await platform.aexecute_trade(trade_params)

        logger.info(f"✅ Manual trade executed: {result}")

        return {
            "status": "executed",
            "trade": result,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Manual trade failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Trade execution failed: {str(e)}",
        )


@bot_control_router.get("/positions")
async def get_open_positions(
    _api_user: str = Depends(verify_api_key_or_dev),
    engine: FinanceFeedbackEngine = Depends(get_engine),
) -> Dict[str, Any]:
    """
    Get all open positions.
    """
    try:
        platform = getattr(engine, "trading_platform", None)

        if platform is None or not hasattr(platform, "get_active_positions"):
            return {
                "positions": [],
                "message": "Platform does not support position tracking",
            }

        # Use standardized active positions
        raw = await platform.aget_active_positions()  # {"positions": [...]}
        raw_positions = raw.get("positions", [])

        transformed = []
        for pos in raw_positions:
            try:
                pid = str(pos.get("id") or pos.get("instrument") or "unknown")
                instrument = pos.get("instrument") or pos.get("product_id") or "UNKNOWN"
                side = (
                    pos.get("side")
                    or ("LONG" if float(pos.get("units", 0)) >= 0 else "SHORT")
                ).upper()
                entry = float(pos.get("entry_price", 0.0))
                current = float(pos.get("current_price", 0.0))
                pnl = float(pos.get("unrealized_pnl", pos.get("pnl", 0.0)))

                # Extract size (contracts or units)
                # Coinbase futures API returns 'number_of_contracts' or 'contracts'
                # OANDA returns 'units'
                def safe_get_field(obj: Any, *keys: str) -> Optional[Any]:
                    """Try multiple field names, supporting both dict and object access."""
                    for key in keys:
                        if isinstance(obj, dict):
                            val = obj.get(key)
                            if val is not None:
                                return val
                        else:
                            val = getattr(obj, key, None)
                            if val is not None:
                                return val
                    return None

                contracts = safe_get_field(pos, "contracts", "number_of_contracts")
                units = safe_get_field(pos, "units")

                # Handle size - prefer contracts for futures, units for forex
                size = 0.0
                if contracts is not None and contracts != 0:
                    size = abs(float(contracts))
                elif units is not None and units != 0:
                    size = abs(float(units))

                # If still no size, this is a problem - log it
                if size == 0:
                    logger.warning(
                        f"Position {instrument} has zero size. contracts={contracts}, units={units}, "
                        f"pos_keys={list(pos.keys()) if isinstance(pos, dict) else 'not a dict'}"
                    )

                # Calculate notional value for P&L%
                # For Coinbase futures: 1 contract = 1 unit of the base asset
                # notional = contracts * entry_price (the total USD value of the position)
                notional = 0.0

                if contracts is not None and contracts != 0 and entry > 0:
                    # Futures position (Coinbase) - notional is position value at entry
                    notional = abs(float(contracts)) * entry
                elif units is not None and units != 0 and entry > 0:
                    # Forex position (OANDA) - same calculation
                    notional = abs(float(units)) * entry

                # Final fallback: use entry * size if notional is still 0
                if notional == 0 and entry > 0 and size > 0:
                    notional = size * entry

                # Calculate P&L percentage based on notional value at entry
                try:
                    if notional > 0:
                        pnl_pct = (pnl / notional) * 100.0
                    else:
                        pnl_pct = 0.0
                except Exception as calc_err:
                    logger.error(
                        f"Error calculating pnl_pct: {calc_err}, pnl={pnl}, notional={notional}"
                    )
                    pnl_pct = 0.0

                # Log detailed P&L calculation for debugging
                logger.debug(
                    f"Position {instrument} P&L calculation: pnl={pnl}, notional={notional}, pnl_pct={pnl_pct}"
                )
                logger.info(
                    f"Position {instrument} P&L calculation: pnl={pnl}, notional={notional}, pnl_pct={pnl_pct}"
                )

                transformed.append(
                    {
                        "id": pid,
                        "asset_pair": instrument,
                        "side": side,
                        "size": size,
                        "entry_price": entry,
                        "current_price": current,
                        "unrealized_pnl": pnl,
                        "unrealized_pnl_pct": pnl_pct,
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to transform position: {e}")
                continue

        total_value = 0.0
        try:
            if hasattr(platform, "get_portfolio_breakdown"):
                pb = await platform.aget_portfolio_breakdown()
                total_value = float(pb.get("total_value_usd", 0.0))
        except Exception:
            total_value = 0.0

        return {
            "positions": transformed,
            "count": len(transformed),
            "total_value": total_value,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to get positions: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve positions: {str(e)}",
        )


@bot_control_router.post("/positions/{position_id}/close")
async def close_position(
    position_id: str,
    _api_user: str = Depends(verify_api_key_or_dev),
    engine: FinanceFeedbackEngine = Depends(get_engine),
) -> Dict[str, Any]:
    """
    Close a specific open position.
    """
    try:
        # Get position details
        breakdown = await engine.trading_platform.aget_portfolio_breakdown()
        positions = breakdown.get("positions", [])

        position = next((p for p in positions if p.get("id") == position_id), None)

        if not position:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Position {position_id} not found",
            )

        size = position.get("size")
        if not size or size <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Position {position_id} has invalid size: {size}",
            )

        # Check platform availability
        if not hasattr(engine, "trading_platform"):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Trading platform is not available",
            )

        # Execute closing trade
        result = await engine.trading_platform.aexecute_trade(
            {
                "asset_pair": position["asset_pair"],
                "action": "SELL" if position.get("side") == "LONG" else "BUY",
                "size": size,
                "order_type": "MARKET",
            }
        )

        logger.info(f"✅ Position {position_id} closed")

        return {
            "status": "closed",
            "position_id": position_id,
            "result": result,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to close position: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Position close failed: {str(e)}",
        )


# ============================================================================
# REAL-TIME DATA STREAMING WEBSOCKETS
# ============================================================================


@bot_control_router.websocket("/ws/portfolio")
async def portfolio_stream_websocket(
    websocket: WebSocket,
    engine: FinanceFeedbackEngine = Depends(get_engine),
) -> None:
    """
    WebSocket endpoint for real-time portfolio updates.

    Sends portfolio status updates as they change.
    """
    token, selected_protocol = _extract_bearer_from_websocket(websocket)
    if not token:
        await websocket.close(code=1008, reason="Missing bearer token")
        return

    from .dependencies import get_auth_manager_instance
    auth_manager = get_auth_manager_instance()

    client_ip = websocket.client.host if websocket.client else None
    user_agent = websocket.headers.get("user-agent")

    import os
    environment = os.getenv("ENVIRONMENT", "production").lower()
    if environment != "development":
        try:
            is_valid, _, _ = auth_manager.validate_api_key(
                api_key=token, ip_address=client_ip, user_agent=user_agent
            )
            if not is_valid:
                await websocket.close(code=1008, reason="Invalid API key")
                return
        except ValueError:
            await websocket.close(code=1013, reason="Rate limited")
            return
        except Exception as exc:
            logger.warning("WebSocket auth failed: %s", exc)
            await websocket.close(code=1008, reason="Authentication failed")
            return

    await websocket.accept(subprotocol=selected_protocol)

    stop_event = asyncio.Event()
    last_portfolio = None

    async def sender() -> None:
        nonlocal last_portfolio
        while not stop_event.is_set():
            try:
                from ..api.routes import get_portfolio_status
                portfolio = await get_portfolio_status(engine)

                # Only send if data changed
                portfolio_dict = (
                    portfolio.model_dump() if hasattr(portfolio, "model_dump")
                    else (portfolio.__dict__ if hasattr(portfolio, "__dict__") else portfolio)
                )

                if last_portfolio != portfolio_dict:
                    await websocket.send_json({
                        "event": "portfolio_update",
                        "data": portfolio_dict
                    })
                    last_portfolio = portfolio_dict

            except WebSocketDisconnect:
                stop_event.set()
            except Exception as exc:
                logger.debug("Portfolio WebSocket sender error: %s", exc)
                stop_event.set()

            await asyncio.sleep(2)  # Send updates every 2 seconds

    sender_task = asyncio.create_task(sender())

    try:
        # Keep connection alive, close on client disconnect
        while not stop_event.is_set():
            try:
                await asyncio.wait_for(websocket.receive_json(), timeout=30)
            except asyncio.TimeoutError:
                continue
            except WebSocketDisconnect:
                stop_event.set()
            except Exception:
                stop_event.set()
    finally:
        stop_event.set()
        sender_task.cancel()
        logger.info("Client disconnected from portfolio stream")


@bot_control_router.websocket("/ws/positions")
async def positions_stream_websocket(
    websocket: WebSocket,
    engine: FinanceFeedbackEngine = Depends(get_engine),
) -> None:
    """
    WebSocket endpoint for real-time position updates.

    Sends position updates (open, update, close) as they occur.
    """
    token, selected_protocol = _extract_bearer_from_websocket(websocket)
    if not token:
        await websocket.close(code=1008, reason="Missing bearer token")
        return

    from .dependencies import get_auth_manager_instance
    auth_manager = get_auth_manager_instance()

    client_ip = websocket.client.host if websocket.client else None
    user_agent = websocket.headers.get("user-agent")

    import os
    environment = os.getenv("ENVIRONMENT", "production").lower()
    if environment != "development":
        try:
            is_valid, _, _ = auth_manager.validate_api_key(
                api_key=token, ip_address=client_ip, user_agent=user_agent
            )
            if not is_valid:
                await websocket.close(code=1008, reason="Invalid API key")
                return
        except ValueError:
            await websocket.close(code=1013, reason="Rate limited")
            return
        except Exception as exc:
            logger.warning("WebSocket auth failed: %s", exc)
            await websocket.close(code=1008, reason="Authentication failed")
            return

    await websocket.accept(subprotocol=selected_protocol)

    stop_event = asyncio.Event()
    last_positions = None

    async def sender() -> None:
        nonlocal last_positions
        while not stop_event.is_set():
            try:
                # Get current positions from platform
                platform = getattr(engine, "trading_platform", None)
                if platform and hasattr(platform, "aget_portfolio_breakdown"):
                    breakdown = await asyncio.wait_for(
                        platform.aget_portfolio_breakdown(), timeout=3.0
                    )
                    positions = breakdown.get("positions", [])

                    # Check if positions changed
                    positions_snapshot = str(positions)  # Simple change detection
                    if last_positions != positions_snapshot:
                        await websocket.send_json({
                            "event": "positions_update",
                            "data": {"positions": positions}
                        })
                        last_positions = positions_snapshot

            except WebSocketDisconnect:
                stop_event.set()
            except asyncio.TimeoutError:
                pass  # Timeout is acceptable, just skip this update
            except Exception as exc:
                logger.debug("Positions WebSocket sender error: %s", exc)

            await asyncio.sleep(2)  # Send updates every 2 seconds

    sender_task = asyncio.create_task(sender())

    try:
        # Keep connection alive
        while not stop_event.is_set():
            try:
                await asyncio.wait_for(websocket.receive_json(), timeout=30)
            except asyncio.TimeoutError:
                continue
            except WebSocketDisconnect:
                stop_event.set()
            except Exception:
                stop_event.set()
    finally:
        stop_event.set()
        sender_task.cancel()
        logger.info("Client disconnected from positions stream")


@bot_control_router.websocket("/ws/decisions")
async def decisions_stream_websocket(
    websocket: WebSocket,
    engine: FinanceFeedbackEngine = Depends(get_engine),
) -> None:
    """
    WebSocket endpoint for real-time decision updates.

    Sends new decisions and decision events in real-time.
    """
    token, selected_protocol = _extract_bearer_from_websocket(websocket)
    if not token:
        await websocket.close(code=1008, reason="Missing bearer token")
        return

    from .dependencies import get_auth_manager_instance
    auth_manager = get_auth_manager_instance()

    client_ip = websocket.client.host if websocket.client else None
    user_agent = websocket.headers.get("user-agent")

    import os
    environment = os.getenv("ENVIRONMENT", "production").lower()
    if environment != "development":
        try:
            is_valid, _, _ = auth_manager.validate_api_key(
                api_key=token, ip_address=client_ip, user_agent=user_agent
            )
            if not is_valid:
                await websocket.close(code=1008, reason="Invalid API key")
                return
        except ValueError:
            await websocket.close(code=1013, reason="Rate limited")
            return
        except Exception as exc:
            logger.warning("WebSocket auth failed: %s", exc)
            await websocket.close(code=1008, reason="Authentication failed")
            return

    await websocket.accept(subprotocol=selected_protocol)

    stop_event = asyncio.Event()
    last_decision_count = 0

    async def sender() -> None:
        nonlocal last_decision_count
        while not stop_event.is_set():
            try:
                # Get recent decisions
                if hasattr(engine, "decision_store"):
                    decisions = engine.decision_store.get_recent_decisions(limit=1)

                    if decisions and len(decisions) > last_decision_count:
                        # Send new decision
                        latest = decisions[0]
                        await websocket.send_json({
                            "event": "decision_made",
                            "data": latest
                        })
                        last_decision_count = len(decisions)

            except WebSocketDisconnect:
                stop_event.set()
            except Exception as exc:
                logger.debug("Decisions WebSocket sender error: %s", exc)

            await asyncio.sleep(1)  # Check for new decisions every second

    sender_task = asyncio.create_task(sender())

    try:
        # Keep connection alive
        while not stop_event.is_set():
            try:
                await asyncio.wait_for(websocket.receive_json(), timeout=30)
            except asyncio.TimeoutError:
                continue
            except WebSocketDisconnect:
                stop_event.set()
            except Exception:
                stop_event.set()
    finally:
        stop_event.set()
        sender_task.cancel()
        logger.info("Client disconnected from decisions stream")

