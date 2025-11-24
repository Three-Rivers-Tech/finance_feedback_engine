from typing import List, Literal
from pydantic import BaseModel

class TradingAgentConfig(BaseModel):
    """
    Configuration model for the Trading Agent.
    Defines the agent's behavior, risk parameters, and operational controls.
    """
    # --- Execution Controls ---
    autonomous_execution: bool = False
    approval_policy: Literal["always", "never", "on_new_asset"] = "on_new_asset"
    max_daily_trades: int = 5

    # --- Strategic Goals ---
    strategic_goal: Literal["growth", "capital_preservation", "balanced"] = "balanced"
    risk_appetite: Literal["low", "medium", "high"] = "medium"
    max_drawdown_percent: float = 15.0

    # --- Data & Analysis Controls ---
    asset_pairs: List[str] = ["BTCUSD"]
    analysis_frequency_seconds: int = 300
