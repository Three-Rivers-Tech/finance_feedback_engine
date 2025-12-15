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

import logging
import asyncio
import copy
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, Field, validator

from ..core import FinanceFeedbackEngine
from ..agent.trading_loop_agent import TradingLoopAgent, AgentState
from .dependencies import get_engine

logger = logging.getLogger(__name__)

# Router for bot control endpoints
bot_control_router = APIRouter(prefix="/api/v1/bot", tags=["bot-control"])

# Global agent instance management
_agent_instance: Optional[TradingLoopAgent] = None
_agent_task: Optional[asyncio.Task] = None
_agent_lock = asyncio.Lock()


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
        None,
        description="Asset pairs to trade (overrides config)"
    )
    autonomous: bool = Field(
        True,
        description="Whether to run in autonomous mode"
    )
    take_profit: Optional[float] = Field(
        None,
        ge=0.001,
        le=1.0,
        description="Take profit percentage (0.001 to 1.0)"
    )
    stop_loss: Optional[float] = Field(
        None,
        ge=0.001,
        le=1.0,
        description="Stop loss percentage (0.001 to 1.0)"
    )
    max_concurrent_trades: Optional[int] = Field(
        None,
        ge=1,
        le=10,
        description="Maximum concurrent trades"
    )
    dry_run: bool = Field(
        False,
        description="Run in simulation mode without executing trades"
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
    config: Dict[str, Any] = {}


class ManualTradeRequest(BaseModel):
    """Request model for manual trade execution."""

    asset_pair: str = Field(..., description="Asset pair to trade")
    action: str = Field(..., description="Trade action: BUY or SELL")
    size: Optional[float] = Field(None, description="Position size (uses default if not specified)")
    price: Optional[float] = Field(None, description="Limit price (market order if not specified)")
    stop_loss: Optional[float] = Field(None, description="Stop loss price")
    take_profit: Optional[float] = Field(None, description="Take profit price")

    @validator('action')
    def validate_action(cls, v):
        if v.upper() not in ['BUY', 'SELL', 'LONG', 'SHORT']:
            raise ValueError('Action must be BUY, SELL, LONG, or SHORT')
        return v.upper()


class ConfigUpdateRequest(BaseModel):
    """Request model for configuration updates."""

    stop_loss_pct: Optional[float] = Field(None, ge=0.001, le=0.1)
    position_size_pct: Optional[float] = Field(None, ge=0.001, le=0.05)
    confidence_threshold: Optional[float] = Field(None, ge=0.5, le=1.0)
    max_concurrent_trades: Optional[int] = Field(None, ge=1, le=10)
    provider_weights: Optional[Dict[str, float]] = None

    @validator('provider_weights')
    def validate_weights(cls, v):
        if v is not None:
            total = sum(v.values())
            if not (0.99 <= total <= 1.01):
                raise ValueError('Provider weights must sum to 1.0')
        return v


# ============================================================================
# BOT CONTROL ENDPOINTS
# ============================================================================

@bot_control_router.post("/start", response_model=AgentStatusResponse)
async def start_agent(
    request: AgentControlRequest,
    background_tasks: BackgroundTasks,
    engine: FinanceFeedbackEngine = Depends(get_engine)
):
    """
    Start the trading agent.

    Initializes and starts the autonomous trading loop with specified parameters.
    """
    global _agent_instance, _agent_task

    try:
        logger.info("Starting trading agent via API...")

        async with _agent_lock:
            if _agent_instance is not None and _agent_task is not None and not _agent_task.done():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Agent is already running. Stop it first before starting again."
                )

            # Create config from request
            config = engine.config.copy()

            if request.asset_pairs:
                config['agent'] = config.get('agent', {})
                config['agent']['asset_pairs'] = request.asset_pairs

            if request.take_profit:
                config['agent']['take_profit_percentage'] = request.take_profit

            if request.stop_loss:
                config['agent']['sizing_stop_loss_percentage'] = request.stop_loss

            if request.max_concurrent_trades:
                config['agent']['max_concurrent_trades'] = request.max_concurrent_trades

            # Initialize agent
            _agent_instance = TradingLoopAgent(config, engine)

            # Start agent in background
            async def run_agent():
                try:
                    await _agent_instance.run()
                except Exception as e:
                    logger.error(f"Agent crashed: {e}", exc_info=True)

            _agent_task = asyncio.create_task(run_agent())

            logger.info("✅ Trading agent started successfully")

            return AgentStatusResponse(
                state=BotState.RUNNING,
                agent_ooda_state=_agent_instance.state.value if _agent_instance else None,
                uptime_seconds=0.0,
                config={
                    "asset_pairs": request.asset_pairs,
                    "autonomous": request.autonomous,
                    "dry_run": request.dry_run
                }
            )

    except Exception as e:
        logger.error(f"Failed to start agent: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start agent: {str(e)}"
        )


@bot_control_router.post("/stop")
async def stop_agent():
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
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Agent is not running"
                )

            # Signal agent to stop
            if hasattr(_agent_instance, 'stop'):
                await _agent_instance.stop()

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
            detail=f"Error stopping agent: {str(e)}"
        )


@bot_control_router.post("/emergency-stop")
async def emergency_stop(
    close_positions: bool = True,
    engine: FinanceFeedbackEngine = Depends(get_engine)
):
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
                _agent_instance = None
                _agent_task = None

        # Close positions if requested
        closed_positions = []
        if close_positions and hasattr(engine, 'platform'):
            logger.warning("Closing all open positions...")

            # Get open positions
            if hasattr(engine.platform, 'get_portfolio_breakdown'):
                breakdown = engine.platform.get_portfolio_breakdown()
                positions = breakdown.get('positions', [])

                for position in positions:
                    try:
                        # Execute close trade
                        result = engine.platform.execute_trade({
                            'asset_pair': position['asset_pair'],
                            'action': 'SELL' if position.get('side') == 'LONG' else 'BUY',
                            'size': position.get('size', 0),
                            'order_type': 'MARKET'
                        })
                        closed_positions.append(result)
                    except Exception as e:
                        logger.error(f"Failed to close position {position}: {e}")

        return {
            "status": "emergency_stopped",
            "message": "Emergency stop executed",
            "closed_positions": len(closed_positions),
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.critical(f"Emergency stop failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Emergency stop failed: {str(e)}"
        )


@bot_control_router.get("/status", response_model=AgentStatusResponse)
async def get_agent_status(engine: FinanceFeedbackEngine = Depends(get_engine)):
    """
    Get current agent status and performance metrics.
    """
    global _agent_instance, _agent_task

    try:
        # Check if agent is running
        if _agent_instance is None or _agent_task is None or _agent_task.done():
            return AgentStatusResponse(
                state=BotState.STOPPED,
                total_trades=0,
                active_positions=0
            )

        # Get agent state
        agent_state = _agent_instance.state if _agent_instance else None

        # Get portfolio info
        portfolio_value = None
        active_positions = 0

        if hasattr(engine, 'platform'):
            try:
                balance = engine.platform.get_balance()
                portfolio_value = balance.get('total', balance.get('balance'))

                if hasattr(engine.platform, 'get_portfolio_breakdown'):
                    breakdown = engine.platform.get_portfolio_breakdown()
                    active_positions = len(breakdown.get('positions', []))
            except Exception as e:
                logger.warning(f"Could not fetch portfolio info: {e}")

        # Calculate uptime
        uptime = None
        if hasattr(_agent_instance, 'start_time'):
            uptime = (datetime.utcnow() - _agent_instance.start_time).total_seconds()

        return AgentStatusResponse(
            state=BotState.RUNNING,
            agent_ooda_state=agent_state.value if agent_state else None,
            uptime_seconds=uptime,
            active_positions=active_positions,
            portfolio_value=portfolio_value,
            current_asset_pair=getattr(_agent_instance, 'current_asset_pair', None),
            config={
                "asset_pairs": engine.config.get('agent', {}).get('asset_pairs', []),
                "autonomous": True
            }
        )

    except Exception as e:
        logger.error(f"Error getting agent status: {e}", exc_info=True)
        return AgentStatusResponse(
            state=BotState.ERROR,
            error_message=str(e)
        )


@bot_control_router.patch("/config")
async def update_config(
    request: ConfigUpdateRequest,
    engine: FinanceFeedbackEngine = Depends(get_engine)
):
    """
    Update agent configuration in real-time.

    Updates take effect immediately for new decisions.
    """
    try:
        # Work on a copy to keep updates atomic and avoid partial mutations.
        config_snapshot = copy.deepcopy(engine.config)

        agent_cfg = config_snapshot.setdefault('agent', {})
        ensemble_cfg = config_snapshot.setdefault('ensemble', {})

        if not isinstance(agent_cfg, dict):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Engine config 'agent' section must be a mapping"
            )

        if not isinstance(ensemble_cfg, dict):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Engine config 'ensemble' section must be a mapping"
            )

        updates_for_agent: Dict[str, Any] = {}
        updates_for_ensemble: Dict[str, Any] = {}
        response_updates: Dict[str, Any] = {}

        if request.stop_loss_pct is not None:
            if not isinstance(request.stop_loss_pct, (int, float)):
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "stop_loss_pct must be numeric")
            updates_for_agent['sizing_stop_loss_percentage'] = float(request.stop_loss_pct)
            response_updates['stop_loss_pct'] = float(request.stop_loss_pct)

        if request.position_size_pct is not None:
            if not isinstance(request.position_size_pct, (int, float)):
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "position_size_pct must be numeric")
            updates_for_agent['sizing_risk_percentage'] = float(request.position_size_pct)
            response_updates['position_size_pct'] = float(request.position_size_pct)

        if request.confidence_threshold is not None:
            if not isinstance(request.confidence_threshold, (int, float)):
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "confidence_threshold must be numeric")
            updates_for_agent['min_confidence_threshold'] = float(request.confidence_threshold)
            response_updates['confidence_threshold'] = float(request.confidence_threshold)

        if request.max_concurrent_trades is not None:
            if not isinstance(request.max_concurrent_trades, int):
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "max_concurrent_trades must be an integer")
            updates_for_agent['max_concurrent_trades'] = request.max_concurrent_trades
            response_updates['max_concurrent_trades'] = request.max_concurrent_trades

        if request.provider_weights is not None:
            if not isinstance(request.provider_weights, dict):
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "provider_weights must be a mapping")
            updates_for_ensemble['provider_weights'] = request.provider_weights
            response_updates['provider_weights'] = request.provider_weights

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
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Failed to update config: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Config update failed: {str(e)}"
        )


@bot_control_router.post("/manual-trade")
async def execute_manual_trade(
    request: ManualTradeRequest,
    engine: FinanceFeedbackEngine = Depends(get_engine)
):
    """
    Execute a manual trade, bypassing the autonomous agent.

    Use with caution - this directly executes on the platform.
    """
    try:
        logger.info(f"Manual trade request: {request.action} {request.asset_pair}")

        # Build trade parameters
        trade_params = {
            'asset_pair': request.asset_pair,
            'action': request.action,
            'order_type': 'LIMIT' if request.price else 'MARKET'
        }

        if request.size:
            trade_params['size'] = request.size

        if request.price:
            trade_params['price'] = request.price

        if request.stop_loss:
            trade_params['stop_loss'] = request.stop_loss

        if request.take_profit:
            trade_params['take_profit'] = request.take_profit

        # Execute trade
        result = engine.platform.execute_trade(trade_params)

        logger.info(f"✅ Manual trade executed: {result}")

        return {
            "status": "executed",
            "trade": result,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Manual trade failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Trade execution failed: {str(e)}"
        )


@bot_control_router.get("/positions")
async def get_open_positions(engine: FinanceFeedbackEngine = Depends(get_engine)):
    """
    Get all open positions.
    """
    try:
        if not hasattr(engine.platform, 'get_portfolio_breakdown'):
            return {"positions": [], "message": "Platform does not support position tracking"}

        breakdown = engine.platform.get_portfolio_breakdown()
        positions = breakdown.get('positions', [])

        return {
            "positions": positions,
            "count": len(positions),
            "total_value": breakdown.get('total_value'),
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Failed to get positions: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve positions: {str(e)}"
        )


@bot_control_router.post("/positions/{position_id}/close")
async def close_position(
    position_id: str,
    engine: FinanceFeedbackEngine = Depends(get_engine)
):
    """
    Close a specific open position.
    """
    try:
        # Get position details
        breakdown = engine.platform.get_portfolio_breakdown()
        positions = breakdown.get('positions', [])

        position = next((p for p in positions if p.get('id') == position_id), None)

        if not position:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Position {position_id} not found"
            )

        # Execute closing trade
        result = engine.platform.execute_trade({
            'asset_pair': position['asset_pair'],
            'action': 'SELL' if position.get('side') == 'LONG' else 'BUY',
            'size': position.get('size', 0),
            'order_type': 'MARKET'
        })

        logger.info(f"✅ Position {position_id} closed")

        return {
            "status": "closed",
            "position_id": position_id,
            "result": result,
            "timestamp": datetime.utcnow().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to close position: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Position close failed: {str(e)}"
        )
