# Autonomous Trading Agent

This document outlines the design and implementation of the fully autonomous trading agent.

## 1. Configuration

The autonomous agent's behavior will be controlled through the `agent.yaml` configuration file. This allows for easy adjustments of its parameters without changing the code.

### 1.1. Schema (`finance_feedback_engine/agent/config.py`)

We will introduce a new Pydantic model to hold the configuration for the autonomous agent. This ensures that the configuration is type-safe and validated upon loading.

The following class will be added to `finance_feedback_engine/agent/config.py`:

```python
class AutonomousAgentConfig(BaseModel):
    """Configuration for the autonomous trading agent."""
    enabled: bool = False
    profit_target: float = 0.05  # 5%
    stop_loss: float = 0.02  # 2%
```

The main `AgentConfig` class will be updated to include this new model:

```python
class AgentConfig(BaseModel):
    """Main agent configuration."""
    # ... existing fields
    autonomous: AutonomousAgentConfig = Field(default_factory=AutonomousAgentConfig)
```

This structure nests the autonomous agent's settings under an `autonomous` key in the configuration file, providing a clear and organized hierarchy.
