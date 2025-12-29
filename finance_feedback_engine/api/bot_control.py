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
import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from ..agent.config import TradingAgentConfig
from ..agent.trading_loop_agent import TradingLoopAgent
from ..core import FinanceFeedbackEngine
from ..memory.portfolio_memory import PortfolioMemoryEngine
from ..monitoring.trade_monitor import TradeMonitor
from .dependencies import get_engine, verify_api_key

logger = logging.getLogger(__name__)

# Router for bot control endpoints
# API authentication enabled for production security
bot_control_router = APIRouter(
    prefix="/api/v1/bot",
    tags=["bot-control"],
    dependencies=[Depends(verify_api_key)],  # Authentication required
)

# Global agent instance management
_agent_instance: Optional[TradingLoopAgent] = None
_agent_task: Optional[asyncio.Task] = None
_agent_lock = asyncio.Lock()


def is_agent_running() -> bool:
    """Return True if the trading agent is currently running."""
    return (
        _agent_instance is not None
        and _agent_task is not None
        and not _agent_task.done()
    )


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


# ============================================================================
# BOT CONTROL ENDPOINTS
# ============================================================================


@bot_control_router.post("/start", response_model=AgentStatusResponse)
async def start_agent(
    request: AgentControlRequest,
    background_tasks: BackgroundTasks,
    engine: FinanceFeedbackEngine = Depends(get_engine),
) -> AgentStatusResponse:
    """
    Start the trading agent.

    Initializes and starts the autonomous trading loop with specified parameters.
    """
    global _agent_instance, _agent_task

    try:
        logger.info("Starting trading agent via API...")

        async with _agent_lock:
            if (
                _agent_instance is not None
                and _agent_task is not None
                and not _agent_task.done()
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Agent is already running. Stop it first before starting again.",
                )

            # Create config from request
            config_snapshot = copy.deepcopy(engine.config)
            agent_cfg_data = config_snapshot.get("agent", {})
            agent_config = TradingAgentConfig(**agent_cfg_data)

            if request.asset_pairs:
                agent_config.asset_pairs = request.asset_pairs
                agent_config.watchlist = request.asset_pairs

            if request.max_concurrent_trades:
                agent_config.max_concurrent_trades = request.max_concurrent_trades

            if request.autonomous:
                agent_config.autonomous.enabled = True

            take_profit = float(request.take_profit or 0.0)
            stop_loss = float(request.stop_loss or 0.0)

            portfolio_memory = engine.memory_engine or PortfolioMemoryEngine(
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
                try:
                    await _agent_instance.run()
                except Exception as e:  # noqa: BLE001
                    logger.error(f"Agent crashed: {e}", exc_info=True)

            _agent_task = asyncio.create_task(run_agent())

            logger.info("✅ Trading agent started successfully")

            return AgentStatusResponse(
                state=BotState.RUNNING,
                agent_ooda_state=(
                    _agent_instance.state.name if _agent_instance else None
                ),
                uptime_seconds=0.0,
                config={
                    "asset_pairs": request.asset_pairs,
                    "autonomous": request.autonomous,
                },
            )

    except Exception as e:
        logger.error(f"Failed to start agent: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start agent: {str(e)}",
        )


@bot_control_router.post("/stop")
async def stop_agent() -> Dict[str, str]:
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

    except Exception as e:
        logger.error(f"Error stopping agent: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error stopping agent: {str(e)}",
        )


@bot_control_router.post("/emergency-stop")
async def emergency_stop(
    close_positions: bool = True, engine: FinanceFeedbackEngine = Depends(get_engine)
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


@bot_control_router.get("/status", response_model=AgentStatusResponse)
async def get_agent_status(
    engine: FinanceFeedbackEngine = Depends(get_engine),
) -> AgentStatusResponse:
    """
    Get current agent status and performance metrics.
    """
    global _agent_instance, _agent_task

    try:
        # Check if agent is running
        if _agent_instance is None or _agent_task is None or _agent_task.done():
            return AgentStatusResponse(
                state=BotState.STOPPED, total_trades=0, active_positions=0
            )

        # Get agent state
        agent_state = _agent_instance.state if _agent_instance else None

        # Get portfolio info
        portfolio_value = None
        active_positions = 0

        platform = getattr(engine, "trading_platform", None)

        if platform:
            try:
                # Add timeout to prevent hanging on API calls
                balance = await asyncio.wait_for(platform.aget_balance(), timeout=3.0)
                portfolio_value = balance.get("total", balance.get("balance"))

                if hasattr(platform, "aget_portfolio_breakdown"):
                    breakdown = await asyncio.wait_for(
                        platform.aget_portfolio_breakdown(), timeout=3.0
                    )
                    active_positions = len(breakdown.get("positions", []))
            except asyncio.TimeoutError:
                logger.warning("Platform API call timed out after 3 seconds")
            except Exception as e:
                logger.warning(f"Could not fetch portfolio info: {e}")

        # Calculate uptime
        uptime = None
        if hasattr(_agent_instance, "start_time"):
            uptime = (datetime.utcnow() - _agent_instance.start_time).total_seconds()

        return AgentStatusResponse(
            state=BotState.RUNNING,
            agent_ooda_state=agent_state.name if agent_state else None,
            uptime_seconds=uptime,
            active_positions=active_positions,
            portfolio_value=portfolio_value,
            current_asset_pair=getattr(_agent_instance, "current_asset_pair", None),
            config={
                "asset_pairs": engine.config.get("agent", {}).get("asset_pairs", []),
                "autonomous": True,
            },
        )

    except Exception as e:
        logger.error(f"Error getting agent status: {e}", exc_info=True)
        return AgentStatusResponse(state=BotState.ERROR, error_message=str(e))


@bot_control_router.patch("/config")
async def update_config(
    request: ConfigUpdateRequest, engine: FinanceFeedbackEngine = Depends(get_engine)
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
    request: ManualTradeRequest, engine: FinanceFeedbackEngine = Depends(get_engine)
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
                def safe_get_field(obj, *keys):
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
    position_id: str, engine: FinanceFeedbackEngine = Depends(get_engine)
):
    """
    Close a specific open position.
    """
    try:
        # Get position details
        breakdown = await engine.platform.aget_portfolio_breakdown()
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
        if not hasattr(engine, "platform"):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Trading platform is not available",
            )

        # Execute closing trade
        result = await engine.platform.aexecute_trade(
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
