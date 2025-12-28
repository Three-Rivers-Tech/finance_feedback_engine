# Quick Fix Guide for Top 3 Issues

This document provides actionable fixes for the top 3 issues identified in the Finance Feedback Engine 2.0.

---

## 🔴 Issue #1: Re-enable API Authentication (CRITICAL)

### Location
`finance_feedback_engine/api/bot_control.py:33-37`

### Fix (5 minutes)

**Before:**
```python
# TEMPORARILY DISABLED AUTH FOR DEBUGGING - RE-ENABLE FOR PRODUCTION
bot_control_router = APIRouter(
    prefix="/api/v1/bot",
    tags=["bot-control"],
    # dependencies=[Depends(verify_api_key)],  # Temporarily disabled
)
```

**After:**
```python
# API authentication enabled for production security
bot_control_router = APIRouter(
    prefix="/api/v1/bot",
    tags=["bot-control"],
    dependencies=[Depends(verify_api_key)],  # Authentication required
)
```

### Test to Add

Create `tests/api/test_bot_control_auth.py`:
```python
"""Security tests for bot control authentication."""
import pytest
from fastapi.testclient import TestClient


def test_bot_start_requires_authentication(test_client):
    """Verify bot start endpoint requires valid API key."""
    response = test_client.post("/api/v1/bot/start")
    assert response.status_code == 401
    assert "API key required" in response.json()["detail"]


def test_bot_stop_requires_authentication(test_client):
    """Verify bot stop endpoint requires valid API key."""
    response = test_client.post("/api/v1/bot/stop")
    assert response.status_code == 401


def test_bot_status_requires_authentication(test_client):
    """Verify bot status endpoint requires valid API key."""
    response = test_client.get("/api/v1/bot/status")
    assert response.status_code == 401


def test_authenticated_bot_start_succeeds(test_client, valid_api_key):
    """Verify authenticated request succeeds."""
    headers = {"Authorization": f"Bearer {valid_api_key}"}
    response = test_client.post(
        "/api/v1/bot/start",
        json={"asset_pairs": ["BTCUSD"]},
        headers=headers
    )
    assert response.status_code in [200, 202]  # Success or Accepted
```

---

## 🟡 Issue #2: Implement Webhook Delivery (HIGH)

### Location
`finance_feedback_engine/agent/trading_loop_agent.py:1251`

### Implementation

Add this method to `TradingLoopAgent` class:

```python
async def _deliver_webhook(
    self, 
    webhook_url: str, 
    payload: dict,
    max_retries: int = 3
) -> bool:
    """
    Deliver webhook payload to configured URL with retry logic.
    
    Args:
        webhook_url: Target webhook URL
        payload: JSON payload to deliver
        max_retries: Maximum retry attempts
        
    Returns:
        bool: True if delivered successfully
    """
    import httpx
    from tenacity import (
        retry,
        stop_after_attempt,
        wait_exponential,
        retry_if_exception_type
    )
    
    @retry(
        stop=stop_after_attempt(max_retries),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.RequestError, httpx.TimeoutException))
    )
    async def _send_webhook():
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                webhook_url,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": f"FinanceFeedbackEngine/{self.version}",
                    "X-FFE-Event": payload.get("event_type", "decision"),
                }
            )
            response.raise_for_status()
            return response
    
    try:
        response = await _send_webhook()
        logger.info(
            "✅ Webhook delivered successfully (status: %s)",
            response.status_code,
        )
        return True
    except httpx.HTTPError as e:
        logger.error(
            "❌ Webhook delivery failed after %s attempts (%s)",
            max_retries,
            type(e).__name__,
        )
        return False
```

### Replace TODO Block

**Before:**
```python
if webhook_enabled and webhook_url:
    # TODO: Implement webhook delivery
    logger.info(
        f"Webhook delivery not yet implemented for {decision_id}"
    )
    failure_reasons.append(
        f"{decision_id}: Webhook delivery not implemented"
    )
```

**After:**
```python
if webhook_enabled and webhook_url:
    # Prepare webhook payload
    webhook_payload = {
        "event_type": "trading_decision",
        "decision_id": decision_id,
        "timestamp": datetime.utcnow().isoformat(),
        "asset_pair": decision.asset_pair,
        "action": decision.action,
        "confidence": decision.confidence,
        "reasoning": decision.reasoning,
    }
    
    # Deliver webhook with retry logic
    webhook_success = await self._deliver_webhook(
        webhook_url=webhook_url,
        payload=webhook_payload,
        max_retries=webhook_config.get("retry_attempts", 3)
    )
    
    if not webhook_success:
        failure_reasons.append(
            f"{decision_id}: Webhook delivery failed"
        )
```

### Configuration Update

Add to `config/config.yaml`:
```yaml
agent:
  webhook:
    enabled: false  # Set to true to enable
    url: ""  # e.g., https://hooks.slack.com/services/YOUR/WEBHOOK
    retry_attempts: 3
    timeout_seconds: 10
```

### Tests to Add

Create `tests/agent/test_webhook_delivery.py`:
```python
"""Tests for webhook delivery functionality."""
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_webhook_delivery_success(trading_agent):
    """Test successful webhook delivery."""
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value.status_code = 200
        
        result = await trading_agent._deliver_webhook(
            webhook_url="https://example.com/webhook",
            payload={"event": "test"}
        )
        
        assert result is True
        mock_post.assert_called_once()


@pytest.mark.asyncio
async def test_webhook_delivery_retry_on_failure(trading_agent):
    """Test webhook retries on transient failures."""
    with patch("httpx.AsyncClient.post") as mock_post:
        # Fail twice, succeed on third attempt
        mock_post.side_effect = [
            httpx.RequestError("Connection failed"),
            httpx.RequestError("Connection failed"),
            AsyncMock(status_code=200)
        ]
        
        result = await trading_agent._deliver_webhook(
            webhook_url="https://example.com/webhook",
            payload={"event": "test"},
            max_retries=3
        )
        
        assert result is True
        assert mock_post.call_count == 3


@pytest.mark.asyncio
async def test_webhook_delivery_max_retries_exceeded(trading_agent):
    """Test webhook fails after max retries."""
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.side_effect = httpx.RequestError("Always fails")
        
        result = await trading_agent._deliver_webhook(
            webhook_url="https://example.com/webhook",
            payload={"event": "test"},
            max_retries=3
        )
        
        assert result is False
        assert mock_post.call_count == 3
```

---

## 🟡 Issue #3: Add Prometheus Metrics (MEDIUM)

### Location
`finance_feedback_engine/api/routes.py:360`
`finance_feedback_engine/core.py` (instrumentation needed)
`finance_feedback_engine/decision_engine/engine.py` (instrumentation needed)

### Step 1: Create Metrics Module

Create `finance_feedback_engine/observability/metrics_core.py`:
```python
"""Core business logic metrics for Finance Feedback Engine."""
from opentelemetry import metrics

# Get meter instance
meter = metrics.get_meter("finance_feedback_engine.core")

# Decision generation metrics
decisions_counter = meter.create_counter(
    name="ffe.decisions.total",
    description="Total number of trading decisions generated",
    unit="1"
)

decision_latency = meter.create_histogram(
    name="ffe.decisions.latency",
    description="Decision generation latency",
    unit="s"
)

# Provider metrics
provider_requests = meter.create_counter(
    name="ffe.providers.requests.total",
    description="Total AI provider requests",
    unit="1"
)

provider_latency = meter.create_histogram(
    name="ffe.providers.latency",
    description="AI provider response time",
    unit="s"
)

# Trading execution metrics
trades_executed = meter.create_counter(
    name="ffe.trades.executed.total",
    description="Total trades executed",
    unit="1"
)

trade_execution_latency = meter.create_histogram(
    name="ffe.trades.execution_latency",
    description="Trade execution latency",
    unit="s"
)

# Risk metrics
risk_checks = meter.create_counter(
    name="ffe.risk.checks.total",
    description="Total risk checks performed",
    unit="1"
)
```

### Step 2: Instrument core.py

Add metrics to `FinanceFeedbackEngine.analyze_asset()`:
```python
from .observability.metrics_core import (
    decisions_counter,
    decision_latency,
)
from opentelemetry.trace import get_tracer

tracer = get_tracer(__name__)

async def analyze_asset(self, asset_pair: str, **kwargs) -> dict:
    """Generate trading decision with metrics instrumentation."""
    
    # Start timing
    start_time = time.time()
    
    with tracer.start_as_current_span("analyze_asset") as span:
        span.set_attribute("asset_pair", asset_pair)
        
        try:
            # ... existing logic ...
            decision = await self._generate_decision(...)
            
            # Record success metrics
            decisions_counter.add(
                1,
                {
                    "asset": asset_pair,
                    "action": decision.action,
                    "provider": kwargs.get("provider", "unknown")
                }
            )
            
            span.set_attribute("decision.action", decision.action)
            span.set_attribute("decision.confidence", decision.confidence)
            
            return decision
            
        except Exception as e:
            # Record error metrics
            decisions_counter.add(
                1,
                {
                    "asset": asset_pair,
                    "action": "error",
                    "provider": kwargs.get("provider", "unknown")
                }
            )
            span.record_exception(e)
            raise
            
        finally:
            # Record latency
            elapsed = time.time() - start_time
            decision_latency.record(
                elapsed,
                {"asset": asset_pair}
            )
```

### Step 3: Update /metrics endpoint

Update `finance_feedback_engine/api/routes.py`:
```python
@api_router.get("/metrics", tags=["monitoring"])
async def get_metrics():
    """
    Prometheus metrics endpoint with OpenTelemetry integration.
    
    Returns metrics in Prometheus text format for scraping.
    Metrics include:
    - Decision generation counters and latency
    - AI provider performance
    - Trade execution statistics
    - Risk check results
    """
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    from ..observability.metrics import get_prometheus_registry
    
    registry = get_prometheus_registry()
    metrics_output = generate_latest(registry)
    
    return Response(
        content=metrics_output,
        media_type=CONTENT_TYPE_LATEST
    )
```

### Step 4: Create Grafana Dashboard JSON

Create `monitoring/grafana/ffe_dashboard.json` with key panels for:
- Decision generation rate
- Decision latency (p50, p95, p99)
- Provider success rates
- Trade execution latency
- Risk check rejection rate

---

## Verification Checklist

After implementing fixes:

- [ ] **Issue #1**: API authentication enabled
  - [ ] Tests pass: `pytest tests/api/test_bot_control_auth.py -v`
  - [ ] Manual test: `curl http://localhost:8000/api/v1/bot/status` returns 401
  
- [ ] **Issue #2**: Webhook delivery working
  - [ ] Tests pass: `pytest tests/agent/test_webhook_delivery.py -v`
  - [ ] Manual test: Configure webhook URL and verify POST received
  
- [ ] **Issue #3**: Metrics instrumented
  - [ ] Tests pass: `pytest tests/observability/ -v`
  - [ ] Manual test: `curl http://localhost:8000/metrics` shows OpenTelemetry metrics
  - [ ] Grafana dashboard displays metrics

---

## Roll-out Strategy

1. **Staging Environment**: Deploy and test all three fixes
2. **Canary Deployment**: Roll out to 10% of production traffic
3. **Monitoring**: Watch for errors, latency spikes, or authentication issues
4. **Full Deployment**: Roll out to 100% after 24 hours of stable canary
5. **Documentation**: Update user-facing docs with authentication and webhook info

---

**Last Updated:** December 28, 2025  
**Status:** Ready for Implementation
