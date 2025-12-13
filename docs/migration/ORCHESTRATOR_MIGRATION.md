# Migrating from TradingAgentOrchestrator to TradingLoopAgent

## Overview

`TradingAgentOrchestrator` is **deprecated** and will be removed in v3.0.
Please migrate to `TradingLoopAgent` which provides:
- Better state machine design
- Improved error handling
- More comprehensive testing
- Cleaner separation of concerns

## Quick Migration

### Before (DEPRECATED)
```python
from finance_feedback_engine.agent.orchestrator import TradingAgentOrchestrator

orchestrator = TradingAgentOrchestrator(
    config=agent_config,
    engine=decision_engine,
    platform=trading_platform
)

orchestrator.run()
```

### After (RECOMMENDED)
```python
from finance_feedback_engine.agent.trading_loop_agent import TradingLoopAgent

agent = TradingLoopAgent(
    config=agent_config,
    engine=finance_engine,  # Note: full engine, not just decision engine
    trade_monitor=trade_monitor,
    portfolio_memory=portfolio_memory,
    trading_platform=trading_platform
)

agent.run()
```

## Key Differences

| Feature | TradingAgentOrchestrator | TradingLoopAgent |
|---------|--------------------------|------------------|
| **State Machine** | Simple loop | Explicit states (IDLE, PERCEPTION, etc.) |
| **Dependencies** | DecisionEngine + Platform | Full engine + Monitor + Memory |
| **Error Handling** | Basic try/catch | State-aware recovery |
| **Testing** | Limited test coverage | Comprehensive tests |
| **Status** | ⚠️ DEPRECATED | ✅ ACTIVE |

## Migration Checklist

- [ ] Update imports
- [ ] Inject additional dependencies (trade_monitor, portfolio_memory)
- [ ] Test in simulation mode before live trading
- [ ] Remove orchestrator imports
- [ ] Update CI/CD if using orchestrator

## Support

For questions, see [GitHub Issues](https://github.com/Three-Rivers-Tech/finance_feedback_engine-2.0/issues)

**Timeline:**
- v2.1: Orchestrator deprecated (current)
- v2.2-2.9: Both supported with warnings
- v3.0: Orchestrator removed
