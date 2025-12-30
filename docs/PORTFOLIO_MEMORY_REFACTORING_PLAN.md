# Portfolio Memory Refactoring Plan
# Phase 2, Option 1: God Class Decomposition

**Date:** 2025-12-30
**Status:** 🚀 IN PROGRESS
**Effort:** 60 hours
**Expected Savings:** 25 hours/month

---

## Executive Summary

### Current State

```yaml
File: finance_feedback_engine/memory/portfolio_memory.py
Lines: 2,182
Methods: 40
Complexity: ~18
Test Coverage: 23.81%

Issues:
  - Multiple responsibilities violate Single Responsibility Principle
  - Difficult to test in isolation
  - High coupling between concerns
  - Long methods with complex logic
  - Hard to extend or modify
```

### Target Architecture

Split PortfolioMemoryEngine into **5 focused services**:

1. **TradeRecorder** - Record trade outcomes and events
2. **PerformanceAnalyzer** - Calculate performance metrics
3. **ThompsonIntegrator** - Update Thompson sampling weights
4. **VetoTracker** - Track veto decision outcomes
5. **MemoryPersistence** - Save/load memory state

---

## Method Distribution Analysis

### TradeRecorder (3 methods → ~300 lines)

**Responsibility:** Record trade outcomes and events

```python
Methods:
  - record_trade_outcome(outcome: TradeOutcome) -> None
  - _save_outcome(outcome: TradeOutcome) -> None
  - record_pair_selection(pair: str, selection_data: Dict) -> None

Dependencies:
  - MemoryPersistence (for saving)
  - PerformanceAnalyzer (trigger analysis)
  - ThompsonIntegrator (trigger updates)
  - VetoTracker (evaluate veto outcomes)

Data Structures:
  - trade_outcomes: deque[TradeOutcome]
  - pair_selections: List[Dict]
```

---

### PerformanceAnalyzer (11 methods → ~400 lines)

**Responsibility:** Calculate performance metrics (Sharpe, Sortino, drawdown, etc.)

```python
Methods:
  - analyze_performance() -> PerformanceSnapshot
  - _calculate_provider_stats() -> Dict[str, Dict]
  - _calculate_max_drawdown() -> float
  - _calculate_sharpe_ratio(returns: List[float]) -> float
  - _calculate_sortino_ratio(returns: List[float]) -> float
  - get_performance_over_period(hours: int) -> Dict
  - get_strategy_performance_summary() -> Dict
  - calculate_rolling_cost_averages() -> Dict
  - _detect_market_regime() -> str
  - _calculate_regime_performance() -> Dict
  - generate_learning_validation_metrics() -> Dict

Dependencies:
  - TradeRecorder (access trade outcomes)
  - numpy (for calculations)

Data Structures:
  - performance_snapshots: List[PerformanceSnapshot]
  - regime_performance: Dict[str, Dict]
```

---

### ThompsonIntegrator (5 methods → ~200 lines)

**Responsibility:** Update Thompson sampling weights based on outcomes

```python
Methods:
  - _trigger_thompson_sampling_update(outcome: TradeOutcome) -> None
  - register_thompson_sampling_callback(callback: Callable) -> None
  - _update_provider_performance(provider: str, outcome: bool) -> None
  - _update_regime_performance(regime: str, outcome: bool) -> None
  - get_provider_recommendations() -> Dict[str, float]

Dependencies:
  - TradeRecorder (access outcomes)
  - PerformanceAnalyzer (get provider stats)
  - Optional external Thompson sampling optimizer

Data Structures:
  - thompson_callback: Optional[Callable]
  - provider_performance: Dict[str, Dict]
```

---

### VetoTracker (4 methods → ~250 lines)

**Responsibility:** Track veto decision outcomes and effectiveness

```python
Methods:
  - _init_veto_metrics() -> None
  - _evaluate_veto_outcome(outcome: TradeOutcome) -> None
  - _update_veto_metrics(outcome: TradeOutcome) -> None
  - get_veto_threshold_recommendation() -> float

Dependencies:
  - TradeRecorder (access veto metadata)
  - PerformanceAnalyzer (compare veto vs non-veto performance)

Data Structures:
  - veto_metrics: Dict[str, Any]
    - vetos_applied: int
    - vetos_correct: int
    - vetos_incorrect: int
    - precision: float
    - recall: float
```

---

### MemoryPersistence (10 methods → ~300 lines)

**Responsibility:** Save/load memory state with atomic writes

```python
Methods:
  - save_to_disk() -> None
  - load_from_disk() -> None
  - _save_snapshot(snapshot: PerformanceSnapshot) -> None
  - _load_memory() -> None
  - save_memory() -> None
  - _atomic_write_file(filepath: Path, data: Any) -> None
  - snapshot() -> Dict
  - restore(snapshot: Dict) -> None
  - set_readonly(readonly: bool) -> None
  - is_readonly() -> bool

Dependencies:
  - FileIOManager (atomic writes)
  - json, fcntl (file operations)
  - All other services (save/load their state)

Data Structures:
  - storage_path: Path
  - readonly_mode: bool
```

---

### Context Generation (5 methods → ~330 lines)

**Responsibility:** Generate context for AI decisions

```python
Methods:
  - generate_context() -> Dict
  - format_context_for_prompt() -> str
  - get_pair_selection_context() -> Dict
  - get_summary() -> Dict
  - check_kelly_activation_criteria() -> bool

Dependencies:
  - TradeRecorder (recent trades)
  - PerformanceAnalyzer (metrics)
  - ThompsonIntegrator (provider recommendations)

Note: This may remain in a coordinator/facade class
```

---

## Refactoring Strategy

### Phase 1: Extract Interfaces (Week 1, 8 hours)

**Objective:** Define clean interfaces for each service

```python
# File: finance_feedback_engine/memory/interfaces.py

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from .models import TradeOutcome, PerformanceSnapshot

class ITradeRecorder(ABC):
    @abstractmethod
    def record_trade_outcome(self, outcome: TradeOutcome) -> None: ...

    @abstractmethod
    def get_recent_trades(self, limit: int = 20) -> List[TradeOutcome]: ...

    @abstractmethod
    def get_all_trades(self) -> List[TradeOutcome]: ...

class IPerformanceAnalyzer(ABC):
    @abstractmethod
    def analyze_performance(self) -> PerformanceSnapshot: ...

    @abstractmethod
    def calculate_sharpe_ratio(self) -> float: ...

    @abstractmethod
    def calculate_max_drawdown(self) -> float: ...

class IThompsonIntegrator(ABC):
    @abstractmethod
    def update_on_outcome(self, outcome: TradeOutcome) -> None: ...

    @abstractmethod
    def get_provider_recommendations(self) -> Dict[str, float]: ...

class IVetoTracker(ABC):
    @abstractmethod
    def evaluate_veto_outcome(self, outcome: TradeOutcome) -> None: ...

    @abstractmethod
    def get_veto_threshold_recommendation(self) -> float: ...

class IMemoryPersistence(ABC):
    @abstractmethod
    def save_to_disk(self) -> None: ...

    @abstractmethod
    def load_from_disk(self) -> None: ...
```

**Deliverables:**
- ✅ `finance_feedback_engine/memory/interfaces.py` (100 lines)
- ✅ Clear contracts for each service
- ✅ Testable interfaces

---

### Phase 2: Implement Services (Week 2-3, 32 hours)

#### 2.1 TradeRecorder (8 hours)

```python
# File: finance_feedback_engine/memory/trade_recorder.py

class TradeRecorder(ITradeRecorder):
    """Records and manages trade outcomes."""

    def __init__(self, max_memory_size: int = 1000):
        self.trade_outcomes = deque(maxlen=max_memory_size)
        self.pair_selections = []

    def record_trade_outcome(self, outcome: TradeOutcome) -> None:
        """Record a completed trade outcome."""
        self.trade_outcomes.append(outcome)
        logger.info(f"Recorded trade: {outcome.decision_id}")

    def get_recent_trades(self, limit: int = 20) -> List[TradeOutcome]:
        """Get most recent trades."""
        return list(self.trade_outcomes)[-limit:]
```

**Tests:** `tests/memory/test_trade_recorder.py` (25 tests)
- Test recording single outcome
- Test max memory size enforcement
- Test retrieval methods
- Test edge cases (empty, overflow)

---

#### 2.2 PerformanceAnalyzer (10 hours)

```python
# File: finance_feedback_engine/memory/performance_analyzer.py

class PerformanceAnalyzer(IPerformanceAnalyzer):
    """Analyzes trading performance metrics."""

    def __init__(self, trade_recorder: ITradeRecorder):
        self.trade_recorder = trade_recorder
        self.performance_snapshots = []

    def analyze_performance(self) -> PerformanceSnapshot:
        """Calculate comprehensive performance metrics."""
        trades = self.trade_recorder.get_all_trades()

        return PerformanceSnapshot(
            timestamp=datetime.now().isoformat(),
            total_trades=len(trades),
            win_rate=self._calculate_win_rate(trades),
            sharpe_ratio=self.calculate_sharpe_ratio(),
            max_drawdown=self.calculate_max_drawdown(),
            # ... other metrics
        )
```

**Tests:** `tests/memory/test_performance_analyzer.py` (35 tests)
- Test Sharpe ratio calculation
- Test Sortino ratio calculation
- Test max drawdown calculation
- Test provider stats aggregation
- Test regime detection
- Test edge cases (insufficient data)

---

#### 2.3 ThompsonIntegrator (6 hours)

```python
# File: finance_feedback_engine/memory/thompson_integrator.py

class ThompsonIntegrator(IThompsonIntegrator):
    """Integrates with Thompson sampling for adaptive learning."""

    def __init__(self):
        self.thompson_callback: Optional[Callable] = None
        self.provider_performance = defaultdict(lambda: {"wins": 0, "losses": 0})

    def register_callback(self, callback: Callable) -> None:
        """Register Thompson sampling update callback."""
        self.thompson_callback = callback

    def update_on_outcome(self, outcome: TradeOutcome) -> None:
        """Update Thompson sampling based on trade outcome."""
        if not self.thompson_callback:
            return

        if outcome.ai_provider:
            won = outcome.was_profitable
            self.thompson_callback(
                provider=outcome.ai_provider,
                won=won,
                regime=outcome.market_sentiment
            )
```

**Tests:** `tests/memory/test_thompson_integrator.py` (20 tests)
- Test callback registration
- Test update triggering
- Test provider performance tracking
- Test regime-specific updates

---

#### 2.4 VetoTracker (6 hours)

```python
# File: finance_feedback_engine/memory/veto_tracker.py

class VetoTracker(IVetoTracker):
    """Tracks veto decision effectiveness."""

    def __init__(self):
        self.veto_metrics = {
            "vetos_applied": 0,
            "vetos_correct": 0,
            "vetos_incorrect": 0,
            "precision": 0.0,
            "recall": 0.0
        }

    def evaluate_veto_outcome(self, outcome: TradeOutcome) -> None:
        """Evaluate whether veto was correct decision."""
        if not outcome.veto_applied:
            return

        # Veto was correct if trade would have been unprofitable
        veto_correct = not outcome.was_profitable
        outcome.veto_correct = veto_correct

        self._update_veto_metrics(outcome)
```

**Tests:** `tests/memory/test_veto_tracker.py` (20 tests)
- Test veto evaluation logic
- Test precision/recall calculation
- Test threshold recommendation
- Test edge cases

---

#### 2.5 MemoryPersistence (8 hours)

```python
# File: finance_feedback_engine/memory/memory_persistence.py

from finance_feedback_engine.utils.file_io import FileIOManager

class MemoryPersistence(IMemoryPersistence):
    """Handles saving and loading memory state."""

    def __init__(self, storage_path: Path):
        self.storage_path = storage_path
        self.file_io = FileIOManager()
        self.readonly_mode = False

    def save_to_disk(self, state: Dict[str, Any]) -> None:
        """Save complete memory state atomically."""
        if self.readonly_mode:
            logger.warning("Cannot save in readonly mode")
            return

        filepath = self.storage_path / "portfolio_memory.json"
        self.file_io.write_json(
            filepath,
            state,
            atomic=True,
            backup=True,
            create_dirs=True
        )
```

**Tests:** `tests/memory/test_memory_persistence.py` (25 tests)
- Test atomic save/load
- Test backup creation
- Test readonly mode
- Test snapshot/restore
- Test error handling

---

### Phase 3: Create Coordinator/Facade (Week 4, 12 hours)

```python
# File: finance_feedback_engine/memory/portfolio_memory_coordinator.py

class PortfolioMemoryCoordinator:
    """
    Coordinates the 5 memory services.

    Provides backward-compatible API while delegating to services.
    """

    def __init__(self, config: Dict[str, Any]):
        # Initialize services
        self.trade_recorder = TradeRecorder(
            max_memory_size=config.get("max_memory_size", 1000)
        )

        self.performance_analyzer = PerformanceAnalyzer(
            trade_recorder=self.trade_recorder
        )

        self.thompson_integrator = ThompsonIntegrator()

        self.veto_tracker = VetoTracker()

        self.persistence = MemoryPersistence(
            storage_path=Path(config.get("storage_path", "data/memory"))
        )

        # Load existing state
        self.persistence.load_from_disk()

    def record_trade_outcome(self, outcome: TradeOutcome) -> None:
        """Record trade outcome - delegates to services."""
        # Record the outcome
        self.trade_recorder.record_trade_outcome(outcome)

        # Trigger downstream updates
        self.performance_analyzer.on_trade_recorded(outcome)
        self.thompson_integrator.update_on_outcome(outcome)
        self.veto_tracker.evaluate_veto_outcome(outcome)

        # Save state
        self.persistence.save_to_disk(self._get_state())

    def analyze_performance(self) -> PerformanceSnapshot:
        """Analyze performance - delegates to PerformanceAnalyzer."""
        return self.performance_analyzer.analyze_performance()

    # ... other backward-compatible methods
```

**Tests:** `tests/memory/test_portfolio_memory_coordinator.py` (30 tests)
- Test service orchestration
- Test backward compatibility
- Test integration between services
- Test error propagation

---

### Phase 4: Migration & Testing (Week 5-6, 16 hours)

#### 4.1 Create Migration Adapter (4 hours)

```python
# File: finance_feedback_engine/memory/portfolio_memory.py (updated)

from .portfolio_memory_coordinator import PortfolioMemoryCoordinator

class PortfolioMemoryEngine(PortfolioMemoryCoordinator):
    """
    Backward-compatible adapter for PortfolioMemoryCoordinator.

    DEPRECATED: Use PortfolioMemoryCoordinator directly.
    This class will be removed in v2.0.
    """

    def __init__(self, config: Dict[str, Any]):
        logger.warning(
            "PortfolioMemoryEngine is deprecated. "
            "Use PortfolioMemoryCoordinator instead."
        )
        super().__init__(config)
```

#### 4.2 Update Dependent Modules (8 hours)

Find all usages of PortfolioMemoryEngine:

```bash
grep -r "PortfolioMemoryEngine" --include="*.py" | wc -l
# Expected: ~15 files
```

Update imports:
```python
# Old:
from finance_feedback_engine.memory.portfolio_memory import PortfolioMemoryEngine

# New:
from finance_feedback_engine.memory import PortfolioMemoryCoordinator
```

#### 4.3 Integration Testing (4 hours)

**Test Suite:** `tests/memory/test_memory_integration.py`
- Test end-to-end workflow
- Test backward compatibility
- Test all 40 original methods still work
- Performance regression tests

---

## Testing Strategy

### Test Coverage Goals

```yaml
Target_Coverage: 80%

Per_Service:
  TradeRecorder: 85%
  PerformanceAnalyzer: 90%
  ThompsonIntegrator: 75%
  VetoTracker: 80%
  MemoryPersistence: 90%
  Coordinator: 80%

Total_Tests: 180+
  Unit_Tests: 155
  Integration_Tests: 25
```

### Test Pyramid

```
Integration Tests (25)
    ├─ End-to-end memory workflow
    ├─ Service interaction tests
    └─ Backward compatibility tests

Unit Tests (155)
    ├─ TradeRecorder (25)
    ├─ PerformanceAnalyzer (35)
    ├─ ThompsonIntegrator (20)
    ├─ VetoTracker (20)
    ├─ MemoryPersistence (25)
    └─ Coordinator (30)
```

---

## File Structure

### New Files Created

```
finance_feedback_engine/memory/
├── __init__.py                          # Export public API
├── interfaces.py                        # Service interfaces (100 lines)
├── models.py                            # TradeOutcome, PerformanceSnapshot (existing)
├── trade_recorder.py                    # TradeRecorder (300 lines)
├── performance_analyzer.py              # PerformanceAnalyzer (400 lines)
├── thompson_integrator.py               # ThompsonIntegrator (200 lines)
├── veto_tracker.py                      # VetoTracker (250 lines)
├── memory_persistence.py                # MemoryPersistence (300 lines)
├── portfolio_memory_coordinator.py      # Coordinator (330 lines)
└── portfolio_memory.py                  # Deprecated adapter (50 lines)

tests/memory/
├── __init__.py
├── test_trade_recorder.py               # 25 tests
├── test_performance_analyzer.py         # 35 tests
├── test_thompson_integrator.py          # 20 tests
├── test_veto_tracker.py                 # 20 tests
├── test_memory_persistence.py           # 25 tests
├── test_portfolio_memory_coordinator.py # 30 tests
└── test_memory_integration.py           # 25 tests
```

---

## Benefits

### Code Quality

```yaml
Before:
  - 1 file: 2,182 lines
  - 1 class: 40 methods
  - Complexity: ~18
  - Hard to test
  - High coupling

After:
  - 7 files: ~1,880 lines total
  - 6 classes: 7-11 methods each
  - Complexity: ~5-8 per class
  - Easy to test in isolation
  - Low coupling, high cohesion
```

### Maintainability

- **Single Responsibility:** Each service has one clear purpose
- **Testability:** Services can be tested independently
- **Extensibility:** Easy to add new features
- **Readability:** Smaller, focused classes
- **Debugging:** Clear boundaries make issues easier to isolate

### Time Savings

```yaml
Monthly_Savings: 25 hours

Breakdown:
  Bug_Fixing: -12 hours (easier debugging)
  Feature_Development: -8 hours (clearer structure)
  Code_Review: -3 hours (smaller PRs)
  Onboarding: -2 hours (easier to understand)
```

---

## Risks & Mitigation

### Risk 1: Breaking Changes

**Mitigation:**
- Maintain backward-compatible adapter
- Comprehensive integration tests
- Gradual migration (services introduced one at a time)
- Deprecation warnings

### Risk 2: Performance Regression

**Mitigation:**
- Benchmark before/after
- Profile critical paths
- Optimize service boundaries
- Use efficient data structures

### Risk 3: Complex Dependencies

**Mitigation:**
- Clear interfaces
- Dependency injection
- Mock services in tests
- Document service interactions

---

## Success Criteria

```yaml
Functional:
  - ✅ All 180+ tests passing
  - ✅ 80% code coverage achieved
  - ✅ All original functionality preserved
  - ✅ Zero production regressions

Performance:
  - ✅ No degradation in memory operations
  - ✅ Atomic writes still working
  - ✅ Thompson sampling updates still fast

Quality:
  - ✅ Complexity reduced from 18 to <8 per class
  - ✅ Files reduced from 2,182 to <400 lines each
  - ✅ Clear separation of concerns
  - ✅ Comprehensive documentation

Adoption:
  - ✅ All dependent modules updated
  - ✅ Migration guide documented
  - ✅ Team trained on new architecture
```

---

## Timeline

```yaml
Week_1: Extract Interfaces (8 hours)
  - Define ITradeRecorder, IPerformanceAnalyzer, etc.
  - Create models.py with data classes
  - Document contracts

Week_2: Implement Core Services (16 hours)
  - TradeRecorder (8h)
  - PerformanceAnalyzer (10h)

Week_3: Implement Supporting Services (16 hours)
  - ThompsonIntegrator (6h)
  - VetoTracker (6h)
  - MemoryPersistence (8h)

Week_4: Coordinator & Tests (12 hours)
  - PortfolioMemoryCoordinator (8h)
  - Integration tests (4h)

Week_5: Migration (8 hours)
  - Update dependent modules (6h)
  - Documentation (2h)

Week_6: Buffer & Polish (8 hours)
  - Fix issues
  - Performance optimization
  - Final testing

Total: 60 hours over 6 weeks
```

---

**Status:** Ready to begin Week 1
**Next Step:** Extract interfaces and define service contracts
**Owner:** Technical Debt Reduction Team
**Approver:** Engineering Leadership
