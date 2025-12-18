# Logging & Monitoring Architecture for Finance Feedback Engine

## Executive Summary

This document defines a comprehensive logging and monitoring architecture for the Finance Feedback Engine that builds upon existing infrastructure ([`TradingLoopAgent`](../finance_feedback_engine/agent/trading_loop_agent.py:30), [`TradeMonitor`](../finance_feedback_engine/monitoring/trade_monitor.py:17), [`DecisionEngine`](../finance_feedback_engine/decision_engine/engine.py:15), [`RiskGatekeeper`](../finance_feedback_engine/risk/gatekeeper.py:14)) to provide real-time observability, automatic optimization, and predictive analytics.

**Key Design Principles:**
- **Non-invasive**: Leverage existing logging infrastructure at [`main.py:setup_logging()`](../finance_feedback_engine/cli/main.py:327)
- **Performance-first**: Minimize overhead on critical trading paths
- **Production-ready**: Build on existing Prometheus setup at [`monitoring/prometheus.yml`](../monitoring/prometheus.yml:1)
- **ML-driven**: Use metrics to train optimization models

---

## 1. System Architecture Overview

### High-Level Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     FINANCE FEEDBACK ENGINE                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │ TradingLoop  │───▶│ DecisionEngine│───▶│ RiskGatekeeper│     │
│  │   Agent      │    │               │    │              │      │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘      │
│         │                   │                    │              │
│         │                   │                    │              │
│         ▼                   ▼                    ▼              │
│  ┌─────────────────────────────────────────────────────┐       │
│  │          STRUCTURED LOGGING LAYER                   │       │
│  │  (JSON logs with correlation IDs)                   │       │
│  └──────────────────────┬──────────────────────────────┘       │
│                         │                                       │
│                         ▼                                       │
│  ┌─────────────────────────────────────────────────────┐       │
│  │      REAL-TIME OUTPUT PARSER & ANALYZER             │       │
│  │  • Pattern matching (errors, bottlenecks)           │       │
│  │  • Metric extraction (latencies, counts)            │       │
│  │  • Event detection (kill-switch, API failures)      │       │
│  └──────────────────────┬──────────────────────────────┘       │
│                         │                                       │
│         ┌───────────────┴───────────────┐                      │
│         ▼                               ▼                      │
│  ┌──────────────┐              ┌──────────────┐               │
│  │  Prometheus  │              │  TimeSeries  │               │
│  │   Metrics    │              │   Database   │               │
│  │  (existing)  │              │  (InfluxDB)  │               │
│  └──────┬───────┘              └──────┬───────┘               │
│         │                             │                        │
│         └──────────────┬──────────────┘                        │
│                        ▼                                       │
│         ┌──────────────────────────────┐                      │
│         │      GRAFANA DASHBOARDS      │                      │
│         │  • Agent Health & States     │                      │
│         │  • Trade Performance & P&L   │                      │
│         │  • API Health & Latencies    │                      │
│         │  • Resource Utilization      │                      │
│         └──────────────┬───────────────┘                      │
│                        │                                       │
│                        ▼                                       │
│         ┌──────────────────────────────┐                      │
│         │     ALERTING ENGINE          │                      │
│         │  • Telegram notifications    │                      │
│         │  • Email alerts              │                      │
│         │  • PagerDuty escalation      │                      │
│         └──────────────┬───────────────┘                      │
│                        │                                       │
│                        ▼                                       │
│         ┌──────────────────────────────┐                      │
│         │  ML OPTIMIZATION ENGINE      │                      │
│         │  • Anomaly detection         │                      │
│         │  • Bottleneck prediction     │                      │
│         │  • Auto-tuning suggestions   │                      │
│         └──────────────────────────────┘                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Log Capture**: Agent state transitions → Structured JSON logs with correlation IDs
2. **Processing**: Real-time parser extracts metrics, detects patterns
3. **Storage**: Metrics → Prometheus (15s scrape) + InfluxDB (time-series detail)
4. **Visualization**: Grafana dashboards (real-time + historical views)
5. **Alerting**: Rule-based alerts → Telegram/Email/PagerDuty
6. **Optimization**: ML models analyze metrics → Auto-tune recommendations

---

## 2. Logging Capture System

### Structured JSON Logging

**Implementation**: Extend existing [`setup_logging()`](../finance_feedback_engine/cli/main.py:327) with JSON formatter

```python
# finance_feedback_engine/monitoring/logging_config.py
import logging
import json
import uuid
from datetime import datetime

class CorrelationIDFilter(logging.Filter):
    """Add correlation ID to all log records."""
    def filter(self, record):
        if not hasattr(record, 'correlation_id'):
            record.correlation_id = str(uuid.uuid4())
        return True

class JSONFormatter(logging.Formatter):
    """Format logs as JSON with metadata."""
    def format(self, record):
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'correlation_id': getattr(record, 'correlation_id', None),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        # Add extra fields
        if hasattr(record, 'agent_state'):
            log_data['agent_state'] = record.agent_state
        if hasattr(record, 'decision_id'):
            log_data['decision_id'] = record.decision_id
        if hasattr(record, 'asset_pair'):
            log_data['asset_pair'] = record.asset_pair
        if hasattr(record, 'duration_ms'):
            log_data['duration_ms'] = record.duration_ms
            
        return json.dumps(log_data)
```

### Log Rotation Strategy

**Configuration** (to be added to [`config/config.yaml`](../config/config.yaml:372)):

```yaml
logging:
  level: "INFO"
  format: "json"  # or "text" for development
  
  # Rotation policy
  rotation:
    max_bytes: 10485760  # 10 MB
    backup_count: 30     # Keep 30 files
    
  # Retention policy
  retention:
    hot_tier_days: 7      # Keep last 7 days in fast storage
    warm_tier_days: 30    # Archive 8-30 days to S3/object storage
    cold_tier_days: 365   # Compress and deep archive for compliance
    
  # Performance settings
  async_logging: true     # Non-blocking I/O
  buffer_size: 8192       # 8KB buffer
```

### Process Output Capture

**New Component**: [`ProcessMonitor`](../finance_feedback_engine/monitoring/output_capture/process_monitor.py) (to be created)

```python
# finance_feedback_engine/monitoring/output_capture/process_monitor.py
class ProcessMonitor:
    """Capture stdout/stderr/return codes from subprocesses."""
    
    def capture_llm_call(self, provider: str, prompt: str) -> dict:
        """Monitor LLM API calls with timeout and error capture."""
        start_time = time.time()
        
        try:
            # Existing LLM call logic here
            result = self._execute_llm_call(provider, prompt)
            
            # Record success metrics
            self.metrics.record_llm_call(
                provider=provider,
                duration_ms=(time.time() - start_time) * 1000,
                status='success',
                tokens=result.get('usage', {}).get('total_tokens', 0)
            )
            
            return result
            
        except TimeoutError as e:
            self.metrics.record_llm_call(
                provider=provider,
                duration_ms=(time.time() - start_time) * 1000,
                status='timeout',
                error=str(e)
            )
            raise
```

---

## 3. Real-Time Output Parser & Analyzer

### Pattern Matching Engine

**New Component**: [`LogParser`](../finance_feedback_engine/monitoring/output_capture/log_parser.py) (to be created)

Key patterns to detect:
- **Kill-switch triggers**: `"KILL SWITCH TRIGGERED"`, `"Portfolio limit exceeded"`
- **API failures**: `"Connection refused"`, `"rate limit exceeded"`, `"timeout"`
- **Stale data**: `"Data is STALE"`, `"age_minutes > threshold"`
- **Risk violations**: `"RiskGatekeeper rejected"`, `"Max drawdown exceeded"`
- **Performance bottlenecks**: `duration_ms > p99_threshold`

```python
# finance_feedback_engine/monitoring/output_capture/log_parser.py
import re
from typing import Dict, List

class LogParser:
    """Real-time log parsing and metric extraction."""
    
    PATTERNS = {
        'kill_switch': re.compile(r'KILL.*SWITCH|Portfolio.*limit.*exceeded', re.I),
        'api_failure': re.compile(r'Connection refused|rate limit|timeout|502|503', re.I),
        'stale_data': re.compile(r'STALE.*data|age_minutes:\s*(\d+)', re.I),
        'risk_violation': re.compile(r'RiskGatekeeper.*reject|drawdown.*exceed', re.I),
        'slow_query': re.compile(r'duration_ms:\s*(\d+)', re.I),
    }
    
    def parse_log_line(self, line: str) -> Dict:
        """Extract metrics and events from a log line."""
        events = []
        metrics = {}
        
        # Pattern matching
        for event_type, pattern in self.PATTERNS.items():
            match = pattern.search(line)
            if match:
                events.append({
                    'type': event_type,
                    'timestamp': datetime.utcnow().isoformat(),
                    'details': match.group(0)
                })
                
                # Extract numeric metrics
                if event_type == 'slow_query' and match.groups():
                    metrics['duration_ms'] = int(match.group(1))
                    
        return {'events': events, 'metrics': metrics}
```

### Stream Processing Architecture

Use **Kafka** or **Redis Streams** for real-time log processing:

```
Logs → Filebeat → Kafka → Spark Streaming → Metrics DB
                      ↓
                   Alerting
```

---

## 4. Metrics Storage & Time-Series Database

### Schema Design

**Prometheus Metrics** (existing at [`finance_feedback_engine/monitoring/prometheus.py`](../finance_feedback_engine/monitoring/prometheus.py:1)):

```python
# Extend existing metrics with new observability metrics

# Agent cycle metrics
agent_cycle_duration_seconds = Histogram(
    'ffe_agent_cycle_duration_seconds',
    'Time to complete one OODA cycle',
    ['state'],  # IDLE, LEARNING, PERCEPTION, REASONING, RISK_CHECK, EXECUTION
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
)

# Decision generation latency (by provider and phase)
decision_generation_latency_seconds = Histogram(
    'ffe_decision_generation_latency_seconds',
    'Time to generate trading decision',
    ['provider', 'phase'],  # phase: phase1, phase2, ensemble
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0]
)

# API call latencies
api_call_duration_seconds = Histogram(
    'ffe_api_call_duration_seconds',
    'External API call duration',
    ['service', 'endpoint'],  # service: alpha_vantage, coinbase, oanda
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)

# Risk check metrics
risk_check_result_total = Counter(
    'ffe_risk_check_result_total',
    'Risk gatekeeper check results',
    ['result', 'reason']  # result: approved, rejected
)

# Position recovery metrics (startup)
position_recovery_duration_seconds = Histogram(
    'ffe_position_recovery_duration_seconds',
    'Time to recover positions on startup',
    ['platform'],
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0]
)
```

### InfluxDB Schema (for detailed time-series)

```sql
-- Database: ffe_metrics

-- Measurement: agent_states
-- Fields: state_value (int), cycle_count (int)
-- Tags: agent_id, environment

-- Measurement: trade_executions
-- Fields: pnl_dollars (float), duration_seconds (float), confidence (float)
-- Tags: asset_pair, action, platform, decision_id

-- Measurement: api_latencies
-- Fields: duration_ms (float), status_code (int)
-- Tags: service, endpoint, method

-- Measurement: llm_calls
-- Fields: duration_ms (float), tokens_used (int), cost_usd (float)
-- Tags: provider, model, phase

-- Retention policies
CREATE RETENTION POLICY "hot" ON "ffe_metrics" DURATION 7d REPLICATION 1 DEFAULT
CREATE RETENTION POLICY "warm" ON "ffe_metrics" DURATION 30d REPLICATION 1
CREATE RETENTION POLICY "cold" ON "ffe_metrics" DURATION 365d REPLICATION 1
```

---

## 5. Performance Analysis & Bottleneck Detection

### Key Performance Indicators (KPIs)

**Agent Performance:**
- Cycle duration by state (target: <5s per cycle)
- State transition frequency (detect infinite loops)
- Decision generation latency (target: <30s)

**API Performance:**
- AlphaVantage latency (p50, p95, p99)
- Trading platform latency (Coinbase/Oanda)
- LLM provider latency (by model)

**Trade Performance:**
- Execution time (order placement to fill)
- Position recovery time (startup)
- P&L calculation accuracy

**Resource Utilization:**
- CPU usage (target: <70% sustained)
- Memory usage (detect leaks)
- Disk I/O (log rotation impact)

### Bottleneck Detection Algorithm

```python
# finance_feedback_engine/monitoring/analysis/bottleneck_detector.py
class BottleneckDetector:
    """Identify performance bottlenecks using statistical analysis."""
    
    def detect_bottlenecks(self, time_window='1h') -> List[Dict]:
        """Analyze metrics and identify bottlenecks."""
        bottlenecks = []
        
        # 1. Check for high p99 latencies
        slow_endpoints = self.query_influx(f"""
            SELECT PERCENTILE(duration_ms, 99) as p99
            FROM api_latencies
            WHERE time > now() - {time_window}
            GROUP BY service, endpoint
            HAVING p99 > 5000
        """)
        
        for endpoint in slow_endpoints:
            bottlenecks.append({
                'type': 'high_latency',
                'component': f"{endpoint['service']}/{endpoint['endpoint']}",
                'p99_ms': endpoint['p99'],
                'threshold_ms': 5000,
                'severity': 'high' if endpoint['p99'] > 10000 else 'medium'
            })
        
        # 2. Check for state transition loops
        stuck_states = self.detect_stuck_states()
        bottlenecks.extend(stuck_states)
        
        # 3. Check for memory leaks
        memory_growth = self.detect_memory_growth()
        if memory_growth:
            bottlenecks.append(memory_growth)
            
        return bottlenecks
```

---

## 6. Automatic Optimization Strategies

### Caching Layer

**New Component**: [`CacheManager`](../finance_feedback_engine/monitoring/optimization/cache_manager.py) (to be created)

```python
# finance_feedback_engine/monitoring/optimization/cache_manager.py
import redis
from typing import Optional

class CacheManager:
    """Intelligent caching for frequently accessed data."""
    
    def __init__(self, redis_url: str = 'redis://localhost:6379'):
        self.redis_client = redis.from_url(redis_url)
        
    def cache_market_data(self, asset_pair: str, data: dict, ttl: int = 60):
        """Cache market data with TTL."""
        key = f"market_data:{asset_pair}"
        self.redis_client.setex(key, ttl, json.dumps(data))
        
    def cache_provider_response(self, provider: str, prompt_hash: str, response: dict, ttl: int = 300):
        """Cache LLM responses to avoid duplicate calls."""
        key = f"llm:{provider}:{prompt_hash}"
        self.redis_client.setex(key, ttl, json.dumps(response))
```

### Adaptive Retry Logic

Extend existing circuit breaker with dynamic backoff:

```python
# Enhance finance_feedback_engine/utils/circuit_breaker.py
class AdaptiveCircuitBreaker(CircuitBreaker):
    """Circuit breaker with dynamic retry timing."""
    
    def calculate_backoff(self) -> float:
        """Calculate exponential backoff with jitter."""
        base_delay = 2.0
        max_delay = 60.0
        
        # Exponential backoff with historical failure rate
        delay = min(base_delay * (2 ** self.failure_count), max_delay)
        
        # Add jitter to prevent thundering herd
        jitter = random.uniform(0, delay * 0.1)
        
        return delay + jitter
```

### Dynamic Resource Allocation

Monitor and adjust thread pool sizes based on load:

```python
# finance_feedback_engine/monitoring/optimization/optimizer_engine.py
class ResourceOptimizer:
    """Dynamically adjust resource allocation."""
    
    def optimize_thread_pool(self, trade_monitor):
        """Adjust MAX_CONCURRENT_TRADES based on system load."""
        current_load = psutil.cpu_percent()
        current_memory = psutil.virtual_memory().percent
        
        if current_load < 50 and current_memory < 60:
            # System has capacity, increase concurrency
            new_max = min(trade_monitor.MAX_CONCURRENT_TRADES + 1, 5)
            trade_monitor.MAX_CONCURRENT_TRADES = new_max
            logger.info(f"Increased max concurrent trades to {new_max}")
            
        elif current_load > 80 or current_memory > 80:
            # System under pressure, reduce concurrency
            new_max = max(trade_monitor.MAX_CONCURRENT_TRADES - 1, 1)
            trade_monitor.MAX_CONCURRENT_TRADES = new_max
            logger.warning(f"Reduced max concurrent trades to {new_max}")
```

---

## 7. Visualization Dashboards

### Grafana Dashboard Specifications

**Dashboard 1: Agent Health & State Transitions**

```json
{
  "title": "Agent Health & State Transitions",
  "panels": [
    {
      "title": "OODA Loop State",
      "type": "stat",
      "targets": [{
        "expr": "ffe_agent_state"
      }],
      "fieldConfig": {
        "mappings": [
          {"value": 0, "text": "IDLE"},
          {"value": 1, "text": "LEARNING"},
          {"value": 2, "text": "PERCEPTION"},
          {"value": 3, "text": "REASONING"},
          {"value": 4, "text": "RISK_CHECK"},
          {"value": 5, "text": "EXECUTION"}
        ]
      }
    },
    {
      "title": "Cycle Duration by State",
      "type": "graph",
      "targets": [{
        "expr": "rate(ffe_agent_cycle_duration_seconds_sum[5m]) / rate(ffe_agent_cycle_duration_seconds_count[5m])"
      }]
    },
    {
      "title": "State Transition Heatmap",
      "type": "heatmap",
      "targets": [{
        "expr": "rate(ffe_agent_state[1m])"
      }]
    }
  ]
}
```

**Dashboard 2: Trade Performance & P&L**

```json
{
  "title": "Trade Performance & P&L",
  "panels": [
    {
      "title": "Cumulative P&L",
      "type": "graph",
      "targets": [{
        "expr": "sum(ffe_trade_pnl_dollars_summary_sum)"
      }]
    },
    {
      "title": "Win Rate (24h)",
      "type": "gauge",
      "targets": [{
        "expr": "sum(ffe_trade_pnl_dollars_summary_count{pnl>0}) / sum(ffe_trade_pnl_dollars_summary_count) * 100"
      }]
    },
    {
      "title": "P&L Distribution",
      "type": "histogram",
      "targets": [{
        "expr": "ffe_trade_pnl_dollars_summary"
      }]
    }
  ]
}
```

**Dashboard 3: API Health & Latencies**

```json
{
  "title": "API Health & Latencies",
  "panels": [
    {
      "title": "API Latency (p95)",
      "type": "graph",
      "targets": [{
        "expr": "histogram_quantile(0.95, rate(ffe_api_call_duration_seconds_bucket[5m]))"
      }],
      "legend": {"show": true}
    },
    {
      "title": "Circuit Breaker States",
      "type": "stat",
      "targets": [{
        "expr": "ffe_circuit_breaker_state"
      }],
      "fieldConfig": {
        "mappings": [
          {"value": 0, "text": "CLOSED", "color": "green"},
          {"value": 1, "text": "OPEN", "color": "red"},
          {"value": 2, "text": "HALF-OPEN", "color": "yellow"}
        ]
      }
    }
  ]
}
```

---

## 8. Alerting Mechanisms

### Alert Rule Definitions

**File**: [`monitoring/alert_rules.yml`](../monitoring/alert_rules.yml:1) (to be enhanced)

```yaml
groups:
  - name: agent_health
    interval: 30s
    rules:
      # Kill switch triggered
      - alert: KillSwitchTriggered
        expr: increase(ffe_risk_check_result_total{result="rejected",reason="kill_switch"}[1m]) > 0
        for: 0m
        labels:
          severity: critical
          component: agent
        annotations:
          summary: "Kill switch triggered"
          description: "Agent kill switch was activated due to portfolio loss threshold"
          
      # Agent stuck in state
      - alert: AgentStuckInState
        expr: changes(ffe_agent_state[5m]) == 0 AND ffe_agent_state != 0
        for: 5m
        labels:
          severity: high
          component: agent
        annotations:
          summary: "Agent stuck in {{ $labels.state }}"
          description: "Agent has not transitioned states in 5 minutes"
          
  - name: api_health
    interval: 1m
    rules:
      # High API latency
      - alert: HighAPILatency
        expr: histogram_quantile(0.95, rate(ffe_api_call_duration_seconds_bucket[5m])) > 10
        for: 5m
        labels:
          severity: warning
          component: api
        annotations:
          summary: "High API latency for {{ $labels.service }}"
          description: "p95 latency is {{ $value }}s (threshold: 10s)"
          
      # API failure rate
      - alert: HighAPIFailureRate
        expr: rate(ffe_provider_requests_total{status="failure"}[5m]) / rate(ffe_provider_requests_total[5m]) > 0.1
        for: 3m
        labels:
          severity: high
          component: api
        annotations:
          summary: "High failure rate for {{ $labels.provider }}"
          description: "{{ $value | humanizePercentage }} of requests failing"
          
  - name: resource_exhaustion
    interval: 1m
    rules:
      # Memory usage
      - alert: HighMemoryUsage
        expr: process_resident_memory_bytes / node_memory_MemTotal_bytes > 0.9
        for: 5m
        labels:
          severity: warning
          component: system
        annotations:
          summary: "High memory usage"
          description: "Memory usage is {{ $value | humanizePercentage }}"
          
      # Disk space
      - alert: LowDiskSpace
        expr: (node_filesystem_avail_bytes{mountpoint="/data"} / node_filesystem_size_bytes) < 0.1
        for: 5m
        labels:
          severity: high
          component: system
        annotations:
          summary: "Low disk space on /data"
          description: "Only {{ $value | humanizePercentage }} free space remaining"
```

### Alert Routing

**Alertmanager Configuration**: [`monitoring/alertmanager.yml`](../monitoring/alertmanager.yml:1) (to be enhanced)

```yaml
route:
  receiver: 'default'
  group_by: ['alertname', 'component']
  group_wait: 10s
  group_interval: 5m
  repeat_interval: 4h
  
  routes:
    # Critical alerts → PagerDuty + Telegram
    - match:
        severity: critical
      receiver: 'critical-alerts'
      continue: true
      
    # High severity → Telegram
    - match:
        severity: high
      receiver: 'telegram'
      
    # Warnings → Email
    - match:
        severity: warning
      receiver: 'email'

receivers:
  - name: 'critical-alerts'
    pagerduty_configs:
      - service_key: '${PAGERDUTY_SERVICE_KEY}'
        description: '{{ .GroupLabels.alertname }}: {{ .Annotations.summary }}'
    webhook_configs:
      - url: '${TELEGRAM_WEBHOOK_URL}'
        
  - name: 'telegram'
    webhook_configs:
      - url: '${TELEGRAM_WEBHOOK_URL}'
        send_resolved: true
        
  - name: 'email'
    email_configs:
      - to: '${ALERT_EMAIL}'
        from: 'alerts@ffe.local'
        smarthost: 'smtp.gmail.com:587'
        auth_username: '${SMTP_USERNAME}'
        auth_password: '${SMTP_PASSWORD}'
```

---

## 9. ML-Based Predictive Analysis

### Feature Engineering

```python
# finance_feedback_engine/monitoring/analysis/anomaly_detector.py
from sklearn.ensemble import IsolationForest
import pandas as pd

class AnomalyDetector:
    """ML-based anomaly detection for metrics."""
    
    def extract_features(self, time_window='1h') -> pd.DataFrame:
        """Extract features from metrics for ML models."""
        features = {
            # Agent metrics
            'cycle_duration_mean': self.get_metric('ffe_agent_cycle_duration_seconds', 'mean'),
            'cycle_duration_p95': self.get_metric('ffe_agent_cycle_duration_seconds', 'p95'),
            'state_transition_rate': self.get_metric('ffe_agent_state', 'changes'),
            
            # API metrics
            'api_latency_p95': self.get_metric('ffe_api_call_duration_seconds', 'p95'),
            'api_failure_rate': self.get_metric('ffe_provider_requests_total', 'failure_rate'),
            
            # Trade metrics
            'win_rate': self.get_metric('ffe_trade_pnl_dollars_summary', 'win_rate'),
            'avg_pnl': self.get_metric('ffe_trade_pnl_dollars_summary', 'mean'),
            
            # Resource metrics
            'cpu_usage': self.get_metric('process_cpu_seconds_total', 'rate'),
            'memory_usage': self.get_metric('process_resident_memory_bytes', 'current'),
        }
        
        return pd.DataFrame([features])
    
    def detect_anomalies(self) -> List[Dict]:
        """Detect anomalies using Isolation Forest."""
        features = self.extract_features()
        
        # Use pre-trained model
        predictions = self.model.predict(features)
        
        anomalies = []
        if predictions[0] == -1:  # Anomaly detected
            anomalies.append({
                'timestamp': datetime.utcnow().isoformat(),
                'type': 'performance_anomaly',
                'features': features.to_dict('records')[0],
                'severity': self.calculate_severity(features)
            })
            
        return anomalies
```

### Proactive Optimization Recommendations

```python
# finance_feedback_engine/monitoring/optimization/feedback_loop.py
class OptimizationFeedbackLoop:
    """Generate optimization recommendations from metrics."""
    
    def generate_recommendations(self) -> List[Dict]:
        """Analyze metrics and suggest optimizations."""
        recommendations = []
        
        # Check for cache hit rate
        cache_hit_rate = self.get_cache_hit_rate()
        if cache_hit_rate < 0.6:
            recommendations.append({
                'type': 'cache_tuning',
                'action': 'increase_ttl',
                'reason': f'Cache hit rate is {cache_hit_rate:.2%}',
                'suggested_config': {'cache_ttl': 300}
            })
        
        # Check for provider performance
        slow_providers = self.identify_slow_providers()
        if slow_providers:
            recommendations.append({
                'type': 'provider_weight_adjustment',
                'action': 'reduce_weight',
                'providers': slow_providers,
                'reason': 'High latency detected'
            })
        
        return recommendations
```

---

## 10. Implementation Roadmap

### Phase 1: Core Logging Capture (Week 1)

**Goals:**
- Implement structured JSON logging
- Add correlation IDs
- Set up log rotation

**Tasks:**
1. Create [`LoggingConfig`](../finance_feedback_engine/monitoring/logging_config.py) module
2. Extend [`setup_logging()`](../finance_feedback_engine/cli/main.py:327) with JSON formatter
3. Add correlation ID filter to all loggers
4. Configure log rotation in [`config.yaml`](../config/config.yaml:372)
5. Update [`TradingLoopAgent`](../finance_feedback_engine/agent/trading_loop_agent.py:30) to log state transitions with metadata

**Deliverables:**
- `finance_feedback_engine/monitoring/logging_config.py`
- Updated `finance_feedback_engine/cli/main.py`
- Configuration schema in `config/config.yaml`

### Phase 2: Metrics Collection & Storage (Week 2)

**Goals:**
- Extend Prometheus metrics
- Set up InfluxDB
- Implement real-time parser

**Tasks:**
1. Add new metrics to [`prometheus.py`](../finance_feedback_engine/monitoring/prometheus.py:1)
2. Deploy InfluxDB container
3. Create [`LogParser`](../finance_feedback_engine/monitoring/output_capture/log_parser.py) for pattern matching
4. Implement [`ProcessMonitor`](../finance_feedback_engine/monitoring/output_capture/process_monitor.py) for subprocess capture
5. Set up Filebeat → Kafka → InfluxDB pipeline

**Deliverables:**
- Extended Prometheus metrics
- InfluxDB schema and retention policies
- `finance_feedback_engine/monitoring/output_capture/` module

### Phase 3: Dashboards & Alerting (Week 3)

**Goals:**
- Create Grafana dashboards
- Configure alerting rules
- Set up notification channels

**Tasks:**
1. Create 3 core Grafana dashboards (Agent Health, Trade Performance, API Health)
2. Define alert rules in [`alert_rules.yml`](../monitoring/alert_rules.yml:1)
3. Configure Alertmanager routing
4. Integrate Telegram bot for notifications
5. Set up PagerDuty integration

**Deliverables:**
- Grafana dashboard JSON files
- Alert rules configuration
- Telegram bot integration

### Phase 4: Optimization Engine & ML (Week 4)

**Goals:**
- Implement caching layer
- Build anomaly detection
- Create auto-tuning engine

**Tasks:**
1. Deploy Redis for caching
2. Create [`CacheManager`](../finance_feedback_engine/monitoring/optimization/cache_manager.py)
3. Implement [`AnomalyDetector`](../finance_feedback_engine/monitoring/analysis/anomaly_detector.py) with Isolation Forest
4. Build [`OptimizationFeedbackLoop`](../finance_feedback_engine/monitoring/optimization/feedback_loop.py)
5. Train initial ML models on historical metrics

**Deliverables:**
- `finance_feedback_engine/monitoring/optimization/` module
- Trained ML models
- Auto-tuning documentation

---

## 11. File Structure & Components

```
finance_feedback_engine/
  monitoring/
    # Existing components
    trade_monitor.py              # Main orchestrator (existing)
    trade_tracker.py              # Individual trade tracking (existing)
    metrics_collector.py          # Trade metrics storage (existing)
    prometheus.py                 # Prometheus metrics (existing)
    model_performance_monitor.py  # ML model monitoring (existing)
    context_provider.py           # Monitoring context (existing)
    
    # New components to create
    logging_config.py             # Structured logging setup
    
    output_capture/
      __init__.py
      process_monitor.py          # Subprocess output capture
      log_parser.py               # Real-time log parsing
      
    metrics/
      __init__.py
      time_series_store.py        # InfluxDB wrapper
      kpi_calculator.py           # Derived metrics calculation
      
    analysis/
      __init__.py
      bottleneck_detector.py      # Performance bottleneck detection
      anomaly_detector.py         # ML-based anomaly detection
      
    optimization/
      __init__.py
      cache_manager.py            # Redis caching layer
      optimizer_engine.py         # Resource optimization
      feedback_loop.py            # Metrics → config updates

monitoring/
  # Existing Prometheus setup
  prometheus.yml                  # Prometheus config (existing)
  alert_rules.yml                 # Alert rules (existing, to be enhanced)
  alertmanager.yml                # Alertmanager config (existing, to be enhanced)
  docker-compose.yml              # Container orchestration (existing)
  
  # New components
  grafana/
    dashboards/
      agent_health.json           # Agent state & performance
      trade_performance.json      # P&L and trade metrics
      api_health.json             # API latencies and errors
      resource_utilization.json   # CPU, memory, disk
    provisioning/
      dashboards.yml
      datasources.yml

config/
  config.yaml                     # Enhanced with logging config
```

---

## 12. Configuration Schema

**Addition to [`config/config.yaml`](../config/config.yaml:1):**

```yaml
# ============================================
# LOGGING & MONITORING CONFIGURATION
# ============================================
logging:
  level: "INFO"
  format: "json"  # or "text"
  
  # Output destinations
  outputs:
    console: true
    file:
      enabled: true
      path: "logs/ffe.log"
    syslog:
      enabled: false
      address: "localhost:514"
  
  # Rotation policy
  rotation:
    max_bytes: 10485760  # 10 MB
    backup_count: 30
    compression: "gzip"
  
  # Retention tiers
  retention:
    hot_tier_days: 7
    warm_tier_days: 30
    cold_tier_days: 365
  
  # Performance settings
  async_logging: true
  buffer_size: 8192
  correlation_id_header: "X-Correlation-ID"

# Metrics collection
metrics:
  # Prometheus metrics endpoint
  prometheus:
    enabled: true
    port: 8000
    path: "/metrics"
  
  # InfluxDB time-series storage
  influxdb:
    enabled: true
    url: "http://localhost:8086"
    database: "ffe_metrics"
    retention_policy: "hot"
    batch_size: 100
    flush_interval_seconds: 10
  
  # Metric collection intervals
  intervals:
    agent_state: 5  # seconds
    api_metrics: 1
    resource_metrics: 10

# Dashboard configuration
dashboards:
  grafana:
    enabled: true
    url: "http://localhost:3000"
    refresh_rates:
      fast: 2      # Active trades, agent state
      medium: 5    # Portfolio, risk checks
      slow: 10     # Market data
      lazy: 30     # Performance stats

# Alerting configuration
alerting:
  enabled: true
  
  # Alert channels
  channels:
    telegram:
      enabled: false
      bot_token: "${TELEGRAM_BOT_TOKEN}"
      chat_id: "${TELEGRAM_CHAT_ID}"
      
    email:
      enabled: false
      smtp_host: "smtp.gmail.com"
      smtp_port: 587
      from_address: "alerts@ffe.local"
      to_addresses:
        - "admin@example.com"
      
    pagerduty:
      enabled: false
      service_key: "${PAGERDUTY_SERVICE_KEY}"
  
  # Alert thresholds
  thresholds:
    api_latency_p95_seconds: 10
    agent_stuck_duration_seconds: 300
    memory_usage_percent: 90
    disk_usage_percent: 90
    failure_rate_percent: 10

# Optimization engine
optimization:
  enabled: true
  
  # Caching configuration
  cache:
    redis_url: "redis://localhost:6379"
    market_data_ttl: 60
    llm_response_ttl: 300
    
  # Auto-tuning
  auto_tuning:
    enabled: true
    learning_rate: 0.1
    
  # Resource management
  resources:
    auto_scale_thread_pool: true
    min_concurrent_trades: 1
    max_concurrent_trades: 5
    
  # ML models
  ml:
    anomaly_detection:
      enabled: true
      model_path: "models/anomaly_detector.pkl"
      sensitivity: 0.7
    
    failure_prediction:
      enabled: false
      lookback_hours: 24
```

---

## 13. API Endpoints

**New HTTP endpoints** (to be added to existing API server):

```python
# finance_feedback_engine/api/monitoring_endpoints.py
from fastapi import APIRouter, Query
from typing import Optional

router = APIRouter(prefix="/monitoring", tags=["monitoring"])

@router.get("/health")
async def health_check():
    """System health check."""
    return {
        "status": "healthy",
        "agent_running": agent.is_running,
        "trade_monitor_running": trade_monitor.is_running,
        "timestamp": datetime.utcnow().isoformat()
    }

@router.get("/metrics")
async def prometheus_metrics():
    """Prometheus metrics endpoint."""
    from finance_feedback_engine.monitoring.prometheus import generate_metrics
    return Response(content=generate_metrics(), media_type="text/plain")

@router.get("/logs/stream")
async def stream_logs(
    level: Optional[str] = Query("INFO"),
    component: Optional[str] = Query(None)
):
    """WebSocket endpoint for real-time log streaming."""
    # WebSocket implementation for live log tailing
    pass

@router.get("/analysis/bottlenecks")
async def get_bottlenecks(time_window: str = Query("1h")):
    """Get current performance bottlenecks."""
    from finance_feedback_engine.monitoring.analysis.bottleneck_detector import BottleneckDetector
    
    detector = BottleneckDetector()
    bottlenecks = detector.detect_bottlenecks(time_window)
    
    return {
        "time_window": time_window,
        "bottlenecks": bottlenecks,
        "timestamp": datetime.utcnow().isoformat()
    }

@router.get("/optimization/recommendations")
async def get_optimization_recommendations():
    """Get suggested optimizations based on metrics."""
    from finance_feedback_engine.monitoring.optimization.feedback_loop import OptimizationFeedbackLoop
    
    loop = OptimizationFeedbackLoop()
    recommendations = loop.generate_recommendations()
    
    return {
        "recommendations": recommendations,
        "timestamp": datetime.utcnow().isoformat()
    }

@router.post("/cache/clear")
async def clear_cache(cache_type: Optional[str] = Query(None)):
    """Clear specific cache or all caches."""
    from finance_feedback_engine.monitoring.optimization.cache_manager import CacheManager
    
    cache = CacheManager()
    if cache_type:
        cache.clear(cache_type)
    else:
        cache.clear_all()
    
    return {"status": "success", "cache_type": cache_type or "all"}
```

---

## 14. Security & Privacy Considerations

### PII Handling in Logs

**Sensitive Data to Redact:**
- API keys and tokens
- Account IDs
- User credentials
- Trading positions (in some jurisdictions)

**Implementation:**

```python
# finance_feedback_engine/monitoring/logging_config.py
import re

class PIIRedactor:
    """Redact sensitive information from logs."""
    
    PATTERNS = {
        'api_key': re.compile(r'(api[_-]?key["\s:=]+)([a-zA-Z0-9_-]{20,})'),
        'token': re.compile(r'(token["\s:=]+)([a-zA-Z0-9_-]{20,})'),
        'account_id': re.compile(r'(account[_-]?id["\s:=]+)(\d{3}-\d{3}-\d{7}-\d{3})'),
    }
    
    def redact(self, message: str) -> str:
        """Redact PII from log message."""
        for pattern_name, pattern in self.PATTERNS.items():
            message = pattern.sub(r'\1[REDACTED]', message)
        return message
```

### Access Control

**Metrics Access:**
- `/metrics` endpoint: Read-only, internal network only
- Grafana: Role-based access (Admin, Operator, Viewer)
- InfluxDB: Separate read/write credentials

**Configuration:**

```yaml
# monitoring/grafana/provisioning/datasources/prometheus.yml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    jsonData:
      httpMethod: POST
      # Enable authentication
      basicAuth: true
    secureJsonData:
      basicAuthPassword: ${PROMETHEUS_PASSWORD}
```

### Encryption

**At Rest:**
- InfluxDB: Enable encryption for data directory
- Log files: Encrypt sensitive logs with GPG

**In Transit:**
- TLS for all HTTP endpoints
- Mutual TLS for Prometheus scrape targets

### Compliance (GDPR, SOC2)

**Data Retention:**
- Logs: 90 days max (configurable per jurisdiction)
- Metrics: 365 days max
- Trade data: 7 years (financial regulations)

**Right to be Forgotten:**
- Implement log purge API for user data deletion
- Document data retention in privacy policy

---

## Risks & Mitigation Strategies

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| **Performance Overhead** | Logging slows trading loop | Medium | • Use async logging<br>• Buffer writes<br>• Benchmark impact |
| **Log Storage Costs** | High disk usage | High | • Aggressive rotation<br>• Compression<br>• Tiered storage |
| **Alert Fatigue** | Missed critical alerts | High | • Tuned thresholds<br>• Alert grouping<br>• Escalation policies |
| **Privacy Violations** | Logged sensitive data | Medium | • PII redaction<br>• Access controls<br>• Audit logging |
| **Monitoring Blind Spots** | Missed issues | Low | • Comprehensive metrics<br>• Regular reviews<br>• Incident post-mortems |

---

## Next Steps

1. **Review this architecture** with the development team
2. **Prioritize features** based on immediate needs
3. **Start with Phase 1** (logging capture) for quick wins
4. **Iterate and refine** based on production feedback

For implementation, switch to **Code mode** and reference this architecture document.

---

## References

- Existing Infrastructure:
  - [`TradingLoopAgent`](../finance_feedback_engine/agent/trading_loop_agent.py:30) - OODA state machine
  - [`TradeMonitor`](../finance_feedback_engine/monitoring/trade_monitor.py:17) - Trade tracking (30s intervals)
  - [`DecisionEngine`](../finance_feedback_engine/decision_engine/engine.py:15) - AI decision generation
  - [`RiskGatekeeper`](../finance_feedback_engine/risk/gatekeeper.py:14) - Risk validation
  - [`setup_logging()`](../finance_feedback_engine/cli/main.py:327) - Current logging setup
  - [`prometheus.py`](../finance_feedback_engine/monitoring/prometheus.py:1) - Existing metrics
  - [`prometheus.yml`](../monitoring/prometheus.yml:1) - Prometheus configuration

- Related Documentation:
  - README.md - Project overview
  - PRODUCTION_READINESS_REVIEW_2.1.md - Production readiness checklist
  - docs/ENSEMBLE_SYSTEM.md - Multi-provider AI architecture
