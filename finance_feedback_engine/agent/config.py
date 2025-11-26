from typing import List, Literal
from pydantic import BaseModel, Field

class AutonomousAgentConfig(BaseModel):
    """Configuration for the autonomous trading agent."""
    enabled: bool = False
    profit_target: float = 0.05  # 5%
    stop_loss: float = 0.02  # 2%

class TradingAgentConfig(BaseModel):
    """
    Configuration model for the Trading Agent.
    Defines the agent's behavior, risk parameters, and operational controls.
    """
    # --- Execution Controls ---
    autonomous_execution: bool = False
    approval_policy: Literal["always", "never", "on_new_asset"] = "on_new_asset"
    max_daily_trades: int = 5
    # Kill-switch thresholds (percentage of portfolio P/L)
    # Stop trading if portfolio gains >= kill_switch_gain_pct
    # or losses <= -kill_switch_loss_pct
    kill_switch_gain_pct: float = 5.0
    kill_switch_loss_pct: float = 2.0
    autonomous: AutonomousAgentConfig = Field(default_factory=AutonomousAgentConfig)

    # --- Strategic Goals ---
    strategic_goal: Literal["growth", "capital_preservation", "balanced"] = "balanced"
    risk_appetite: Literal["low", "medium", "high"] = "medium"
    max_drawdown_percent: float = 15.0

    # --- Data & Analysis Controls ---
    asset_pairs: List[str] = ["BTCUSD", "ETHUSD"]
    analysis_frequency_seconds: int = 300
