# Deprecated Features

This document lists deprecated features in Finance Feedback Engine 2.0 and their recommended replacements.

## Overview

Deprecated features are marked with warnings but continue to function for backward compatibility. They will be removed in future major versions.

**Last Updated:** January 12, 2026  
**Deprecation Phase:** 1 (warnings enabled, functionality maintained)  
**Target Removal:** Version 2.0 (next major release)

---

## Deprecated CLI Commands & Options

### 1. `monitor start` Command (Agent Monitoring)

**Status:** ⚠️ **DEPRECATED** in v0.9.10  
**Removal Target:** v2.0

**Problem:**
- Manual monitor startup was error-prone
- Users had to remember to start the monitor separately
- Created confusion about agent execution state

**Current Behavior:**
- Still works but displays deprecation warning
- Does nothing if already running internally

**Recommended Replacement:**

Instead of:
```bash
python main.py run-agent BTCUSD
# In another terminal:
python main.py monitor
```

Use:
```bash
python main.py run-agent BTCUSD
# Monitor auto-starts based on config.monitoring.enabled
```

**Migration Steps:**
1. Remove any `monitor start` commands from your deployment scripts
2. Update `config.yaml` to set `monitoring.enabled: true` (default)
3. Run agent normally - monitoring starts automatically

**Location:** `finance_feedback_engine/cli/commands/agent.py:730-740`

---

### 2. `status` Command (Agent Status Reporting)

**Status:** ⚠️ **DEPRECATED** in v0.9.10  
**Removal Target:** v2.0

**Problem:**
- Status was inconsistent between CLI and internal state
- Difficult to maintain multiple status sources
- Redundant with dashboard

**Current Behavior:**
- Displays deprecation warning
- Returns minimal status info

**Recommended Replacement:**

Instead of:
```bash
python main.py status
```

Use:
```bash
# Via REST API:
curl http://localhost:8000/api/status

# Or use dashboard:
python main.py dashboard

# Or check agent logs:
tail -f logs/*.log
```

**Migration Steps:**
1. Remove `status` checks from monitoring scripts
2. Use REST API endpoints or dashboard for real-time status
3. Log to CloudWatch/ELK for production monitoring

**Location:** `finance_feedback_engine/cli/commands/agent.py:745-760`

---

### 3. `metrics` Command (Metrics Reporting)

**Status:** ⚠️ **DEPRECATED** in v0.9.10  
**Removal Target:** v2.0

**Problem:**
- Metrics generation was slow and blocking
- Aggregated metrics available in multiple better places
- OpenTelemetry provides superior metrics collection

**Current Behavior:**
- Displays deprecation warning
- Returns cached metrics only

**Recommended Replacement:**

Instead of:
```bash
python main.py metrics
```

Use:
```bash
# Via REST API:
curl http://localhost:8000/api/metrics

# Or use Prometheus (if enabled):
curl http://localhost:9090/metrics

# Or via dashboard:
python main.py dashboard  # Shows all metrics

# Or check OpenTelemetry traces:
# Configure OTEL_EXPORTER_OTLP_ENDPOINT in config
```

**Migration Steps:**
1. Remove `metrics` polling from monitoring scripts
2. Use REST API `/api/metrics` endpoint instead
3. Enable OpenTelemetry exporters in `config.yaml`:
   ```yaml
   observability:
     enabled: true
     opentelemetry:
       exporter: otlp
       endpoint: http://localhost:4317
   ```
4. Point monitoring tools (Datadog, New Relic) to OTEL exporter

**Location:** `finance_feedback_engine/cli/commands/agent.py:762-775`

---

## Deprecated Configuration Options

### 1. `decision_engine.quicktest_mode`

**Status:** ⚠️ **DEPRECATED** in v0.9.10  
**Removal Target:** v2.0

**Replacement:** `agent.quicktest_mode` or `QUICKTEST_MODE` env var

**Before:**
```yaml
decision_engine:
  quicktest_mode: true
```

**After:**
```yaml
agent:
  quicktest_mode: true
```

Or via environment:
```bash
export QUICKTEST_MODE=true
python main.py run-agent BTCUSD
```

---

### 2. Manual Position Monitoring

**Status:** ⚠️ **DEPRECATED** in v0.9.10  
**Replacement:** Automatic position tracking via `TradingLoopAgent`

**Before:**
```python
# Manual position tracking
positions = engine.get_active_positions()
engine.manually_update_position(position_id, new_price)
```

**After:**
```python
# Automatic via agent
agent = TradingLoopAgent(config)
await agent.run()  # Position tracking happens automatically
```

---

## Deprecation Timeline

| Feature | Deprecated | Removal | Status |
|---------|-----------|---------|--------|
| `monitor start` | v0.9.10 | v2.0 | ⚠️ Warning in logs |
| `status` | v0.9.10 | v2.0 | ⚠️ Warning in logs |
| `metrics` | v0.9.10 | v2.0 | ⚠️ Warning in logs |
| Quicktest config | v0.9.10 | v2.0 | ⚠️ Warning in logs |
| Manual position tracking | v0.9.10 | v2.0 | ⚠️ Warning in logs |

---

## Migration Guide

### For Monitoring & Operations

**Old Approach:**
```bash
# Monitor multiple agents manually
python main.py run-agent BTCUSD &
sleep 2
python main.py monitor

# Check status manually
python main.py status

# Get metrics
python main.py metrics > metrics.json
```

**New Approach:**
```bash
# Single command with auto-monitoring
python main.py run-agent BTCUSD

# In another terminal, check status via REST API
curl http://localhost:8000/api/status

# Monitor via dashboard
python main.py dashboard

# Or access metrics endpoint
curl http://localhost:8000/api/metrics
```

### For CI/CD Pipelines

**Old Approach:**
```bash
# Run agent + manual monitor
python main.py run-agent BTCUSD &
sleep 5
python main.py monitor
```

**New Approach:**
```bash
# Just run the agent - monitoring is automatic
python main.py run-agent BTCUSD &

# Health checks via REST API
for i in {1..5}; do
  curl http://localhost:8000/api/health && break
  sleep 1
done
```

### For Production Deployments

**Old Approach:**
```yaml
# Kubernetes: Multiple containers for agent + monitor
containers:
  - name: agent
    command: ["python", "main.py", "run-agent", "BTCUSD"]
  - name: monitor
    command: ["python", "main.py", "monitor"]
```

**New Approach:**
```yaml
# Single container with auto-monitoring
containers:
  - name: agent
    command: ["python", "main.py", "run-agent", "BTCUSD"]
    # monitoring.enabled: true (in config.yaml)
```

---

## Suppressing Deprecation Warnings

If you need to suppress deprecation warnings temporarily (not recommended):

```python
import warnings

# Suppress deprecation warnings globally
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Or suppress specific features
warnings.filterwarnings("ignore", message=".*monitor.*deprecated.*")
```

In configuration:
```yaml
logging:
  level: INFO
  filters:
    - name: ignore_deprecations
      pattern: deprecated
```

---

## Reporting Issues

If you encounter problems with deprecated features:

1. **File a GitHub issue** with:
   - Your current version
   - The deprecated feature you're using
   - Error messages or unexpected behavior
   - Your use case/reason for still needing the feature

2. **Consider migrating** to recommended replacements above

3. **Check migration guide** above for step-by-step instructions

---

## FAQ

**Q: Will deprecated features be supported in v1.x?**  
A: Yes, all deprecated features will continue working through v1.x. They will be removed only in v2.0.

**Q: Do I have to migrate immediately?**  
A: No, but we recommend planning migrations soon. Deprecated features may be disabled in minor version updates.

**Q: What happens if I use a deprecated feature?**  
A: You'll see warnings in logs, but the feature will continue to work as before.

**Q: How do I know what the replacement is?**  
A: See the feature's "Recommended Replacement" section above.

**Q: Will my config break?**  
A: No, old config files will continue to work. We'll issue deprecation warnings for config options, but they remain functional.

---

## Support

For deprecation-related questions or migration assistance:
- 📧 Email: dev@threerivers.tech
- 📖 Docs: https://github.com/Three-Rivers-Tech/finance_feedback_engine/docs
- 💬 Discussions: GitHub Discussions
