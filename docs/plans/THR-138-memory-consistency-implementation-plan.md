# THR-138: Memory Consistency During Agent Restart

## Problem Statement

The `PortfolioMemoryEngine` has multiple persistence paths that can leave the system in an inconsistent state after a crash or abrupt restart:

1. **Dual persistence mechanisms**: Writes both individual files (`outcome_*.json`) AND a monolithic file (`portfolio_memory.json`)
2. **Dual loading mechanisms**: `_load_memory()` loads from individual files, while `load_from_disk()` loads from the monolithic file
3. **Non-transactional multi-file writes**: `save_memory()` writes multiple files sequentially with no rollback capability
4. **Performance concern**: `save_to_disk()` is called after every single trade outcome

## Current File Structure

| File Pattern | Written By | Loaded By | Purpose |
|-------------|-----------|-----------|---------|
| `outcome_{id}.json` | `_save_outcome()` | `_load_memory()` | Individual trade outcomes |
| `snapshot_{ts}.json` | `_save_snapshot()` | `_load_memory()` | Performance snapshots |
| `provider_performance.json` | `save_memory()` | Not loaded (rebuilt) | Provider stats |
| `regime_performance.json` | `save_memory()` | Not loaded (rebuilt) | Regime stats |
| `portfolio_memory.json` | `save_to_disk()` | `load_from_disk()` | Full state dump |

## Crash Scenarios Identified

### Scenario 1: Crash during `record_trade_outcome()`
- **Sequence**: In-memory update → `_save_outcome()` → `save_to_disk()`
- **Risk**: If crash after in-memory update but before `_save_outcome()`, outcome is lost
- **Impact**: HIGH - Lost trade data

### Scenario 2: Crash between individual file save and monolithic save
- **Sequence**: `_save_outcome()` completes → crash → `save_to_disk()` never runs
- **Risk**: Individual file has outcome, monolithic file doesn't
- **Impact**: MEDIUM - State depends on which loading method is used

### Scenario 3: Different loading paths produce different state
- **`core.py`**: Uses `load_from_disk()` → loads from `portfolio_memory.json`
- **`__init__`**: Uses `_load_memory()` → loads from individual files
- **Impact**: HIGH - Inconsistent behavior depending on initialization

### Scenario 4: Crash during `save_memory()`
- **Sequence**: `provider_performance.json` saved → crash → `regime_performance.json` not saved
- **Impact**: LOW - These files are not loaded; stats are rebuilt from outcomes

## Recommended Solution: Single Source of Truth with Write-Ahead Logging

### Design Principles

1. **Single authoritative state file**: Consolidate to `portfolio_state.json`
2. **Write-Ahead Log (WAL)**: Log operations before applying them
3. **Checkpoint mechanism**: Periodic full state snapshots
4. **Recovery on startup**: Replay WAL entries since last checkpoint

### Architecture

```
storage/
├── portfolio_state.json      # Checkpoint (full state snapshot)
├── portfolio.wal             # Write-ahead log (pending operations)
├── portfolio_state.json.bak  # Previous checkpoint (for recovery)
└── legacy/                   # Archive old individual files
    ├── outcome_*.json
    └── snapshot_*.json
```

## Step-by-Step Implementation Plan

### Phase 1: Unify Loading Mechanism (Low Risk)

**Goal**: Ensure consistent state regardless of initialization path.

#### Step 1.1: Audit Loading Paths
- [ ] Map all places that instantiate `PortfolioMemoryEngine`
- [ ] Identify which loading method each uses
- [ ] Document current behavior differences

#### Step 1.2: Consolidate to Single Loading Method
- [ ] Modify `__init__` to check for `portfolio_memory.json` first
- [ ] Fall back to `_load_memory()` only if monolithic file missing
- [ ] Add logging to track which path was used

#### Step 1.3: Add State Verification
- [ ] After loading, verify internal consistency
- [ ] Log warnings if trade count mismatches between sources
- [ ] Consider rebuilding derived stats from outcomes

**Files to modify**:
- `finance_feedback_engine/memory/portfolio_memory.py`
- `finance_feedback_engine/core.py`

**Tests to add**:
- Test loading from monolithic file
- Test loading from individual files when monolithic missing
- Test consistency check after loading

---

### Phase 2: Implement Write-Ahead Log (Medium Risk)

**Goal**: Ensure no operations are lost during crashes.

#### Step 2.1: Create WAL Data Structures
```python
@dataclass
class WALEntry:
    sequence_id: int
    operation: str  # "record_outcome", "update_stats", etc.
    timestamp: str
    data: Dict[str, Any]
    checksum: str  # For integrity verification
```

#### Step 2.2: Implement WAL Writer
- [ ] Create `_append_to_wal(operation, data)` method
- [ ] Use append-only file writes (no atomic rename needed)
- [ ] Add fsync after each entry for durability
- [ ] Include sequence numbers for ordering

#### Step 2.3: Implement WAL Recovery
- [ ] Create `_recover_from_wal()` method
- [ ] Read WAL entries since last checkpoint
- [ ] Replay operations in sequence order
- [ ] Handle partial/corrupted entries gracefully

#### Step 2.4: Modify `record_trade_outcome()`
```python
def record_trade_outcome(self, ...):
    # 1. Write to WAL first (durable)
    self._append_to_wal("record_outcome", outcome.to_dict())

    # 2. Update in-memory state
    self.trade_outcomes.append(outcome)

    # 3. Trigger checkpoint if needed (async/batched)
    self._maybe_checkpoint()
```

**Files to modify**:
- `finance_feedback_engine/memory/portfolio_memory.py`

**Tests to add**:
- Test WAL entry writing and reading
- Test recovery after simulated crash
- Test handling of corrupted WAL entries
- Test sequence number ordering

---

### Phase 3: Implement Checkpointing (Medium Risk)

**Goal**: Periodic full state snapshots for faster recovery.

#### Step 3.1: Create Checkpoint Mechanism
- [ ] Create `_write_checkpoint()` method
- [ ] Atomic write of full state to `portfolio_state.json`
- [ ] Keep previous checkpoint as `.bak` for recovery
- [ ] Record checkpoint sequence number

#### Step 3.2: Implement Checkpoint Triggering
- [ ] Checkpoint after N operations (configurable, default: 100)
- [ ] Checkpoint on clean shutdown
- [ ] Checkpoint on explicit `save_memory()` call

#### Step 3.3: Implement WAL Truncation
- [ ] After successful checkpoint, truncate WAL
- [ ] Keep checkpoint sequence number to reject stale WAL entries
- [ ] Handle edge case: crash during truncation

**Configuration options**:
```yaml
portfolio_memory:
  checkpoint_interval: 100  # Operations between checkpoints
  wal_enabled: true
  wal_fsync: true  # fsync after each write (slower but safer)
```

**Tests to add**:
- Test checkpoint creation and loading
- Test WAL truncation after checkpoint
- Test recovery with checkpoint + WAL replay

---

### Phase 4: Deprecate Legacy Persistence (Low Risk)

**Goal**: Remove redundant persistence paths.

#### Step 4.1: Mark Legacy Methods as Deprecated
- [ ] Add deprecation warnings to `_save_outcome()`, `_save_snapshot()`
- [ ] Add deprecation warning to individual file loading in `_load_memory()`
- [ ] Document migration path

#### Step 4.2: Add Migration Logic
- [ ] On first load with new system, migrate from individual files
- [ ] Archive individual files to `legacy/` directory
- [ ] Create initial checkpoint from migrated data

#### Step 4.3: Remove Legacy Code (Future Release)
- [ ] Remove `_save_outcome()`, `_save_snapshot()` after migration period
- [ ] Remove individual file loading from `_load_memory()`
- [ ] Clean up `save_memory()` to only checkpoint

**Files to modify**:
- `finance_feedback_engine/memory/portfolio_memory.py`

---

### Phase 5: Performance Optimization (Low Risk)

**Goal**: Reduce I/O overhead while maintaining durability.

#### Step 5.1: Remove Per-Trade `save_to_disk()`
- [ ] Remove `save_to_disk()` call from `record_trade_outcome()`
- [ ] Rely on WAL + periodic checkpointing instead
- [ ] Add explicit `flush()` method for critical operations

#### Step 5.2: Implement Batched Writes
- [ ] Buffer WAL entries in memory (configurable batch size)
- [ ] Flush batch on: batch full, timeout, explicit request
- [ ] Trade-off: slight durability risk for better performance

#### Step 5.3: Add Async Checkpointing (Optional)
- [ ] Run checkpoint in background thread
- [ ] Use copy-on-write for state during checkpoint
- [ ] Prevents blocking on large state saves

---

## Testing Strategy

### Unit Tests
- WAL entry serialization/deserialization
- Checkpoint creation and loading
- Recovery logic with various failure scenarios

### Integration Tests
- Full workflow: record trades → checkpoint → restart → verify state
- Concurrent access (if multi-threaded)
- Large state files (performance)

### Chaos Tests
- Simulate crash during various operations
- Verify recovery produces correct state
- Test with corrupted files

### Backward Compatibility Tests
- Loading old individual file format
- Migration from legacy to new format
- Graceful handling of missing files

---

## Rollback Plan

If issues arise during rollout:

1. **Phase 1-2**: Can disable WAL via config flag
2. **Phase 3**: Can skip checkpointing, rely on WAL only
3. **Phase 4**: Keep legacy code behind feature flag
4. **Phase 5**: Performance optimizations are optional

---

## Estimated Effort

| Phase | Complexity | Risk | Effort |
|-------|------------|------|--------|
| Phase 1: Unify Loading | Low | Low | 2-3 hours |
| Phase 2: WAL Implementation | Medium | Medium | 4-6 hours |
| Phase 3: Checkpointing | Medium | Medium | 3-4 hours |
| Phase 4: Deprecate Legacy | Low | Low | 2-3 hours |
| Phase 5: Performance | Low | Low | 2-3 hours |

**Total**: ~15-20 hours

---

## Success Criteria

1. No data loss on any crash scenario
2. Single authoritative loading path
3. Recovery time < 5 seconds for typical state sizes
4. All existing tests pass
5. New chaos tests verify crash recovery

---

## References

- SQLite WAL mode: https://www.sqlite.org/wal.html
- Redis AOF persistence: https://redis.io/docs/management/persistence/
- PostgreSQL WAL: https://www.postgresql.org/docs/current/wal-intro.html
