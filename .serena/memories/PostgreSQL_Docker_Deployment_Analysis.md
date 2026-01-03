# PostgreSQL + Docker Deployment Analysis for FFE

## Current Database Architecture in FFE

### SQLite Usage (Primary):
1. **Decision Cache** (`finance_feedback_engine/backtesting/decision_cache.py`)
   - SQLite database: `data/cache/backtest_decisions.db`
   - Connection pooling with max 5 connections
   - WAL mode enabled for concurrent reads
   - Thread-safe implementation with `check_same_thread=False`

2. **Authentication Manager** (`finance_feedback_engine/auth/auth_manager.py`)
   - SQLite database: `data/auth.db`
   - Tables: API keys, authentication audit log
   - Thread-safe with locks
   - Rate limiting tracking

3. **Decision Store** (`finance_feedback_engine/persistence/decision_store.py`)
   - JSON file-based storage (not database)
   - Path: `data/decisions/`
   - Append-only audit trail

### Current Docker Setup:
- **No PostgreSQL service** in docker-compose.yml
- Backend service uses SQLite (file-based)
- Volumes: `ffe-data` persists data directory
- Health checks implemented but NO database connection tests

### SQLAlchemy Status:
- Installed as dependency (pyproject.toml)
- NOT currently used in codebase
- No ORM models defined
- No migration framework (Alembic) configured

## FFE's Specific Database Needs

### Data That Needs Persistence:
1. **Decision Cache** (backtesting performance optimization)
2. **API Authentication** (API keys, audit logs, rate limiting)
3. **Portfolio Memory** (JSON-based performance tracking)
4. **Trading History** (potential future feature)
5. **Configuration** (dynamic updates)

### Scaling Constraints:
- Currently single-worker compatible (SQLite limitation)
- Multi-worker deployment would require shared database
- Production should migrate to PostgreSQL Phase 2

## PostgreSQL Integration Checklist

### Phase 1: Docker Compose Setup
- [ ] Add PostgreSQL 16+ service to docker-compose.yml
- [ ] Configure health checks (pg_isready)
- [ ] Set up volumes for persistence
- [ ] Configure environment variables
- [ ] Create init scripts for schema

### Phase 2: Connection & Pooling
- [ ] Add SQLAlchemy configuration
- [ ] Implement connection pooling (PgBouncer or SQLAlchemy pool)
- [ ] Configure connection retry logic
- [ ] Add circuit breaker pattern

### Phase 3: Migrations
- [ ] Install Alembic
- [ ] Create initial migration for auth tables
- [ ] Create migration for decision cache tables
- [ ] Create migration for portfolio memory tables
- [ ] Add migration runners to startup sequence

### Phase 4: Health Checks
- [ ] Database connectivity test in /health endpoint
- [ ] Database schema version check
- [ ] Connection pool status in metrics

### Phase 5: Backup & Recovery
- [ ] pg_dump integration in backup.sh
- [ ] Automated daily backups to volume
- [ ] Recovery procedure documentation
- [ ] Point-in-time recovery capability

## Industry Standard Startup Sequence

### Standard Docker + PostgreSQL Pattern:
1. **PostgreSQL Container Startup** (wait for initialization)
   - Data directory creation
   - initdb runs (creates template0, template1, postgres DB)
   - Extensions loaded
   - Custom schema/users created (init scripts)
   
2. **Health Check Phase**
   - `pg_isready` test in container
   - Initial wait: 10-30s for DB to initialize
   - Subsequent checks every 10s
   
3. **Application Container Startup**
   - Depends on PostgreSQL healthcheck
   - Run migrations (Alembic upgrade head)
   - Initialize cache tables
   - Load initial data
   - Start API server

4. **Ready State**
   - /ready endpoint returns 200 when all subsystems ready
   - /health returns detailed status

### Database Connection Flow:
```
PostgreSQL Init (30s)
    ↓
Health Check Passes (pg_isready OK)
    ↓
Backend Container Starts
    ↓
Run Migrations (Alembic)
    ↓
Initialize Tables/Sequences
    ↓
Start API Server
    ↓
Warmup Period (connection pool primed)
```

## Recommended Environment Variables

```bash
# PostgreSQL Service
POSTGRES_USER=ffe_user
POSTGRES_PASSWORD=<random_32_chars>
POSTGRES_DB=ffe
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

# SQLAlchemy Connection
DATABASE_URL=postgresql://ffe_user:password@postgres:5432/ffe

# Connection Pooling
DB_POOL_SIZE=20              # Max connections
DB_POOL_RECYCLE=3600         # Recycle after 1h
DB_POOL_TIMEOUT=30           # Connection wait timeout
DB_ECHO=false                # SQL logging

# Alembic
ALEMBIC_VERSION_TABLE=alembic_version
ALEMBIC_VERSION_TABLE_SCHEMA=public
```

## Health Check Enhancements Required

### Current Health Check (`/health`):
- ✅ Ollama status
- ✅ Service uptime
- ❌ Database connectivity
- ❌ Database schema version
- ❌ Connection pool status

### Needed Additions:
```python
def check_database_health():
    # 1. Test connection (SELECT 1)
    # 2. Check schema version vs app version
    # 3. Verify all required tables exist
    # 4. Check connection pool utilization
    # 5. Measure query latency
```

## Migration Strategy (Alembic Setup)

### Initial Setup Steps:
```bash
1. pip install alembic
2. alembic init alembic
3. Edit alembic/env.py:
   - Add SQLAlchemy target_metadata
   - Add offline render function
4. Create initial migration:
   alembic revision --autogenerate -m "Initial schema"
5. Add to startup: alembic upgrade head
```

### FFE-Specific Migrations:
1. **V001_initial_auth_schema.py** - API key tables
2. **V002_decision_cache_schema.py** - Cache tables  
3. **V003_portfolio_memory_schema.py** - Performance tracking
4. **V004_add_indexes.py** - Performance optimization

## Connection Pooling Best Practices

### SQLAlchemy Pool Configuration:
```python
engine = create_engine(
    DATABASE_URL,
    pool_size=20,              # Min connections
    max_overflow=10,           # Additional connections
    pool_recycle=3600,         # Recycle after 1h
    pool_pre_ping=True,        # Test before use
    echo=False                 # SQL logging
)
```

### PgBouncer (Optional Advanced):
- Use when: Multiple app instances
- Connection pooling at DB level
- Reduces DB connection count
- Not needed for single-node FFE initially

## Backup & Recovery for Single-Node

### Daily Backup Strategy:
```bash
# In backup.sh (automated daily):
docker-compose exec -T postgres pg_dump \
    -U $POSTGRES_USER \
    $POSTGRES_DB > backups/$(date +%Y%m%d).sql

# Compression:
gzip backups/$(date +%Y%m%d).sql
```

### Recovery Procedure:
```bash
1. Stop backend: docker-compose stop backend
2. Restore: docker-compose exec postgres psql -U user db < backup.sql
3. Verify schema: SELECT version()
4. Restart backend: docker-compose up backend
5. Check /ready endpoint
```

### Data Retention:
- Keep last 30 days of backups
- Store in separate volume
- Test recovery monthly

## Twelve-Factor App Compliance

### Backing Services (Factor IV):
- PostgreSQL should be external to app
- Connection via DATABASE_URL env var ✅
- Replaceable without code changes ✅

### Config (Factor III):
- All database config from environment ✅
- No hardcoded credentials ✅
- Support multiple environments (dev/staging/prod) ✅

### Disposability (Factor IX):
- Fast startup with migration automation ✅
- Graceful shutdown (connection cleanup) ⚠️ NEEDED
- No session affinity ✅

### Dev/Prod Parity (Factor X):
- Same PostgreSQL version across environments ✅
- Same connection pool settings ✅
- Same migration tools ✅

## Risk Mitigation for Single-Node

### Failure Modes:
1. **Database Unavailable** → App startup fails (desired)
2. **Connection Pool Exhaustion** → Requests queue/timeout (need monitoring)
3. **Disk Full** → Database can't write (monitoring needed)
4. **Corrupt Data** → Recovery from backup (procedures needed)

### Monitoring:
- Database size: `SELECT pg_database_size('ffe')`
- Connection count: `SELECT count(*) FROM pg_stat_activity`
- Long-running queries: Check pg_stat_statements
- Slow query log: Enable with log_min_duration_statement

## Next Steps (Priority Order)

1. **Add PostgreSQL to docker-compose.yml** (1 day)
2. **Update connection code** (2 days)
3. **Implement Alembic migrations** (3 days)
4. **Add database health checks** (1 day)
5. **Testing & validation** (2 days)
6. **Documentation** (1 day)

**Estimated Phase 2 Effort:** 1-2 weeks for full PostgreSQL migration

