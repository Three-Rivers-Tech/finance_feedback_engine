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
├── portfolio_state.json      # Checkpoint (full state snapshot, atomic write via .tmp and .bak)
├── portfolio_state.json.tmp  # Temp file for atomic checkpoint writes
├── portfolio_state.json.bak  # Previous checkpoint (for recovery)
├── portfolio.wal             # Write-ahead log (pending operations)
└── legacy/                   # Archive old individual files
    ├── outcome_*.json
    └── snapshot_*.json
```

**Atomic checkpoint write pattern:**
When creating `portfolio_state.json`, write the snapshot to `portfolio_state.json.tmp`, fsync the temp file, rename the existing `portfolio_state.json` to `portfolio_state.json.bak`, rename `portfolio_state.json.tmp` to `portfolio_state.json`, then fsync the directory to ensure metadata durability. This ensures that either the old or new checkpoint is always recoverable, and never a partial file.

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
    checksum: str  # For integrity verification (SHA256 recommended)
    checksum_algo: str = "sha256"  # Algorithm used for checksum
"""
WALEntry checksum field uses SHA256 for integrity and security. All writers/readers must use SHA256 for compute_checksum/verify_checksum. Tests must assert the exact algorithm and output format.
"""
```


#### Step 2.2: Implement WAL Writer
- [ ] Create `_append_to_wal(operation, data)` method
- [ ] Use append-only file writes (no atomic rename needed)
- [ ] Assign a strictly increasing sequence number to each entry, persisted in memory and checkpoint metadata
- [ ] Make fsync configurable via `wal_fsync` boolean config (default: true); log a clear durability warning if false
- [ ] Document fsync latency (1–10ms typical on HDDs) and trade-offs
- [ ] wal_fsync default is true (for durability, see config and Success Criteria)
- [ ] Add basic batching infrastructure (disabled by default) to support Phase 5
- [ ] In `_append_to_wal`, log a detailed warning and raise `StaleWALSequenceError` if WAL entry sequence <= checkpoint_sequence (fail-fast to prevent checkpoint corruption; see implementation for details)



#### Step 2.3: Implement WAL Recovery
- [ ] Create `_recover_from_wal()` method
- [ ] On startup, initialize the in-memory sequence counter from the latest checkpoint value plus any replayed WAL entries
- [ ] Read WAL entries since last checkpoint
- [ ] Replay operations in sequence order
- WAL Corruption Policy: On detecting WAL corruption during recovery, use the "Truncate at corruption" strategy. If a corrupted entry is found, log a warning with the file offset and entry details, discard all subsequent entries, and continue recovery with only the valid prefix. Sequence/ordering is preserved for all valid entries. Failure is visible via error logs and a metric (e.g., `wal_recovery_truncated`). No attempt is made to skip or repair individual entries. Trade-offs: "Skip and continue" risks state divergence, "Abort recovery" can block startup, while "Truncate at corruption" maximizes recovery of valid data while preventing replay of ambiguous or partial operations. This is referenced as the "WAL corruption policy" throughout the codebase and documentation.


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

#### Step 2.5: WAL Size Monitoring
- [ ] Monitor WAL file size (configurable threshold, e.g., 10MB)
- [ ] If threshold exceeded, trigger checkpoint and WAL truncation/rotation to prevent unbounded growth

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
- [ ] Before writing, either acquire a read lock (via state lock or new RWLock) or create a shallow/deep copy of the in-memory state and atomically write that copy (using the .bak swap behavior and sequence number recording)
- [ ] Atomic write of full state to `portfolio_state.json` using the temp file/rename/fsync pattern
- [ ] Keep previous checkpoint as `.bak` for recovery
- [ ] Record checkpoint sequence number in checkpoint metadata

#### Step 3.2: Implement Checkpoint Triggering
- [ ] Checkpoint after N operations (configurable, default: 100)
- [ ] Checkpoint on clean shutdown
- [ ] Checkpoint on explicit `save_memory()` call


#### Step 3.3: Implement WAL Truncation/Rotation
- [ ] After successful checkpoint, rotate WAL: create a new empty WAL file with incremented sequence (e.g., newWalPath with seq+1)
- [ ] Atomically rename the current WAL to current.wal.old (or similar) only after checkpoint succeeds
- [ ] Set checkpointSequenceNumber to reject stale entries
- [ ] On next successful checkpoint, delete the .old WAL file
- [ ] In recovery, check and replay both the current WAL and any .old WAL on startup so partial truncations do not lose entries


**Configuration options**:
```yaml
portfolio_memory:
    checkpoint_interval: 100  # Operations between checkpoints (default: 100)
        wal_enabled: true         # WAL is enabled by default for immediate durability and crash consistency
    wal_fsync: true           # fsync after each write (default: true for safety, but can be set false for performance)
```

**Defaults and Migration Guidance:**
    - WAL is now enabled by default to guarantee crash consistency and durability. Migration scripts should ensure WAL is active unless explicitly disabled for legacy compatibility.

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
- [ ] **Validate migration:**
    - Verify record/trade counts match originals
    - Compute and compare checksums or hashes for migrated blobs
    - Ensure required fields are present and well-typed
    - Compare a sample or full state snapshot against original files
    - If validation fails, abort/rollback migration, report clear error, and do not create checkpoint or delete/archive originals

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


#### Step 5.2: Implement Batched Writes (Opt-in)
- [ ] Buffer WAL entries in memory (configurable batch size)
- [ ] Flush batch on: batch full, timeout, explicit request
- [ ] Batched writes are **disabled by default**; enabling them violates the no-data-loss guarantee and must be explicitly opted-in with clear documentation of the risk

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

### Performance Regression Tests
- WAL write throughput (trades/sec) benchmark (serialization/deserialization)
- Timed tests for checkpoint creation/loading (duration)
- Timed recovery tests for various failure scenarios (recovery time)
- Memory/heap usage comparisons for large state files and concurrent access
- Tests must produce reproducible metrics and baseline artifacts for regression detection

### Chaos Tests
- Simulate crash during various operations
- Verify recovery produces correct state
- Test with corrupted files

### Backward Compatibility Tests
- Loading old individual file format
- Migration from legacy to new format
- Graceful handling of missing files

---


## Concurrency Control

PortfolioMemoryEngine may be accessed from multiple threads. To ensure thread safety:
- Use a read/write lock strategy around state access and checkpointing (readers for normal ops, writer/exclusive lock for checkpoint)
- Serialize WAL appends (single-writer or mutex around WAL.write/append)
- Avoid races between WAL append and checkpoint: flush WAL and obtain checkpoint write lock, or use an epoch/counting scheme
- Update Phase 2/3 design tasks to include these mechanisms and corresponding integration tests (concurrent access, WAL serialization, race-condition scenarios)

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
| Phase 1: Unify Loading | Low | Low | 3-4.5 hours |
| Phase 2: WAL Implementation | Medium | Medium | 6-9 hours |
| Phase 3: Checkpointing | Medium | Medium | 4.5-6 hours |
| Phase 4: Deprecate Legacy | Low | Low | 3-4.5 hours |
| Phase 5: Performance | Low | Low | 3-4.5 hours |

**Total**: ~23-30 hours

*Note: A 50% buffer was added to account for WAL recovery complexity, chaos testing, concurrent edge-case debugging, and migration/backward compatibility validation.*

---

## Success Criteria

1. No data loss with default configuration (`wal_fsync: true`, batching: false)
2. Single authoritative loading path
3. Recovery time < 5 seconds for typical state sizes
4. All existing tests pass
5. New chaos tests verify crash recovery

---

## References

- SQLite WAL mode: https://www.sqlite.org/wal.html
- Redis AOF persistence: https://redis.io/docs/management/persistence/
- PostgreSQL WAL: https://www.postgresql.org/docs/current/wal-intro.html
