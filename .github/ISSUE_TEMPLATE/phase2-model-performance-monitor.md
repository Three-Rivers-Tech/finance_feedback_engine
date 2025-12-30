---
name: Phase 2 - Enhance ModelPerformanceMonitor (Statistical Drift Detection)
about: Implement statistical drift detection algorithms (t-tests, Z-tests, ADWIN/DDM)
title: "[PHASE-2] Enhance ModelPerformanceMonitor drift detection"
labels: ["phase-2", "monitoring", "drift-detection", "machine-learning"]
assignees: ""
---

## Overview

The `ModelPerformanceMonitor` class has basic concept drift detection (comparing win rate) but needs enhancement to support multiple statistical methods for more robust drift detection. The class already has all scaffold code; this task involves enriching the `detect_concept_drift()` method with proper statistical algorithms.

## Current State

**File**: `finance_feedback_engine/monitoring/model_performance_monitor.py`

**Current Implementation** (Line 376):
- Basic win rate comparison
- Hardcoded threshold check
- Limited to single metric

**Tests** (existing, pass): `tests/test_model_performance_monitor.py::test_detect_concept_drift`

## Proposed Enhancements

### 1. Statistical Tests for Concept Drift

Implement in `detect_concept_drift()`:

#### a. **T-Test** (for 2 performance windows)
- Compare mean performance metrics between baseline and current
- Null hypothesis: No significant difference in means
- Use: `scipy.stats.ttest_ind()`
- When: Small sample sizes (< 30 samples per window)

```python
# Example
baseline_wins = [1, 0, 1, 1, 0, ...]  # Success flags
current_wins = [0, 1, 0, 0, 1, ...]

t_stat, p_value = stats.ttest_ind(baseline_wins, current_wins)
if p_value < 0.05:  # Significant drift at 95% confidence
    drift_detected = True
```

#### b. **Z-Test** (for large samples)
- Compare proportions (win rate %) between periods
- When: Large sample sizes (> 30 samples per window)
- Formula: z = (p1 - p2) / sqrt(p * (1-p) * (1/n1 + 1/n2))

```python
from scipy.stats import norm

def z_test_proportions(baseline_wins, current_wins):
    n1, n2 = len(baseline_wins), len(current_wins)
    p1, p2 = sum(baseline_wins) / n1, sum(current_wins) / n2
    p_pooled = (sum(baseline_wins) + sum(current_wins)) / (n1 + n2)
    se = np.sqrt(p_pooled * (1 - p_pooled) * (1/n1 + 1/n2))
    z = (p1 - p2) / se
    p_value = 2 * (1 - norm.cdf(abs(z)))
    return z, p_value
```

#### c. **ADWIN Algorithm** (Adaptive Windowing)
- Online drift detection (single pass over stream)
- Automatically adjusts window size
- Detects abrupt and gradual drift
- Reference: Bifet & Gavaldà (2007)

Implementation library: Can use `river` package or custom implementation
```python
from river import drift

# Initialize ADWIN detector
adwin = drift.ADWIN()

# For each performance metric
for metric_value in performance_stream:
    adwin.update(metric_value)
    if adwin.drift_detected:
        logger.warning(f"Drift detected at position {adwin.iteration}")
```

#### d. **DDM Algorithm** (Drift Detection Method)
- Watches error rate over time
- Triggers on statistically significant increase
- Simpler than ADWIN; good for binary outcomes
- Reference: Gama et al. (2004)
- **Threshold hierarchy**: `drift_level > warning_level` (drift is the stricter threshold)

```python
# Pseudo-code for DDM
error_rate = 1 - accuracy
p = error_rate
n = sample_count

# Compute bounds
m_p = p + 2 * np.sqrt((p * (1 - p)) / n)
m_p_prime = p - 2 * np.sqrt((p * (1 - p)) / n)

# Check strict drift condition first, then less-severe warning
if m_p > drift_level:
    drift_detected = True
elif m_p > warning_level:
    warning_triggered = True
```

### 2. Multi-Metric Drift Detection

Extend beyond win rate to include:
- Accuracy
- Precision / Recall
- Sharpe ratio
- Max drawdown
- Average profit per trade

```python
metrics_to_check = {
    'win_rate': {'weight': 1.0, 'threshold': 0.3},  # 30% drop = drift
    'accuracy': {'weight': 0.8, 'threshold': 0.2},
    'sharpe_ratio': {'weight': 0.6, 'threshold': 0.5},
}
```

### 3. Configurable Detection Strategy

Add parameter to constructor:
```python
def __init__(
    self,
    model_id: str,
    drift_method: str = 'z_test',  # 'z_test', 't_test', 'adwin', 'ddm'
    drift_confidence: float = 0.95,  # Significance level
    metrics_to_monitor: List[str] = None,  # ['win_rate', 'accuracy', 'sharpe_ratio']
    ...
):
```

## Acceptance Criteria

- [ ] Implement at least 2 statistical methods (t-test + Z-test, or ADWIN)
- [ ] Support multiple metrics (not just win rate)
- [ ] Update `detect_concept_drift()` docstring with algorithm details
- [ ] Add configuration parameters for drift detection strategy
- [ ] All existing tests pass
- [ ] New tests for statistical methods (test t-test, z-test, ADWIN separately)
- [ ] Integration test combining all methods
- [ ] Performance acceptable (< 100ms for 1000-sample windows)
- [ ] Logging includes drift reasons and statistics

## Test Plan (TDD)

### Unit Tests
1. `test_drift_detection_t_test()` — Verify t-test detects known drift
2. `test_drift_detection_z_test()` — Verify Z-test for large samples
3. `test_drift_detection_adwin()` — Verify ADWIN online detection
4. `test_drift_detection_multi_metric()` — Drift across multiple metrics
5. `test_drift_detection_no_drift()` — False positives < 5%

### Integration Tests
1. `test_all_methods_agree_on_drift()` — Multiple methods consensus
2. `test_drift_score_calculation()` — Severity ranking

## Files to Modify

- `finance_feedback_engine/monitoring/model_performance_monitor.py` — Enhance `detect_concept_drift()`
- `tests/test_model_performance_monitor.py` — Add new test methods
- `finance_feedback_engine/monitoring/drift_algorithms.py` (NEW) — Helper functions for algorithms

## Dependencies

- `scipy.stats` (already installed)
- Optional: `river` for ADWIN (pip install river)

## References

- Bifet, A., & Gavaldà, R. (2007). Learning from time-changing data with adaptive windowing. SIAM
- Gama, J. et al. (2004). Learning with Drift Detection. SBBD
- `scipy.stats` documentation: https://docs.scipy.org/doc/scipy/reference/stats.html

## Priority

**Medium** — Nice-to-have enhancement for production monitoring; doesn't block Phase 1 functionality.

## Effort Estimate

**8-12 hours**
- T-test & Z-test: 2-3 hours
- ADWIN implementation: 4-5 hours
- Tests & integration: 2-4 hours

---

## Implementation Checklist

- [ ] Research ADWIN and DDM algorithms
- [ ] Create `drift_algorithms.py` helper module
- [ ] Implement t-test wrapper
- [ ] Implement Z-test wrapper
- [ ] Implement ADWIN detector
- [ ] Update `detect_concept_drift()` to use new methods
- [ ] Add configuration in `__init__`
- [ ] Write unit tests for each algorithm
- [ ] Write integration tests
- [ ] Update docstrings with algorithm references
- [ ] Benchmark performance
- [ ] Document in README/docs
