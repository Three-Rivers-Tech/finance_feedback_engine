# PostgreSQL Deployment Guide

## Overview

Finance Feedback Engine now uses **PostgreSQL 16** as the primary database, replacing SQLite. This enables:

- ✅ Multi-worker deployment (4+ Uvicorn workers)
- ✅ Concurrent read/write operations
- ✅ Advanced pooling and connection management
- ✅ Automated migrations via Alembic
- ✅ Better performance at scale
- ✅ Production-grade monitoring

## Quick Start (Docker Compose)

### 1. Configure Environment

```bash
# Copy the example environment file
cp .env.example .env

# Edit with your settings (or use defaults for local development)
nano .env
```

**Minimum required variables:**
```bash
DATABASE_URL="postgresql+psycopg2://ffe_user:changeme@postgres:5432/ffe"
POSTGRES_USER="ffe_user"
POSTGRES_PASSWORD="changeme"
POSTGRES_DB="ffe"
```

### 2. Start Services

```bash
# Start all services (includes PostgreSQL)
docker-compose up -d

# Verify PostgreSQL is healthy
docker-compose ps postgres

# Check backend migrations
docker-compose logs backend | grep -i alembic
```

### 3. Verify Setup

```bash
# Test database connectivity
curl http://localhost:8000/health | jq '.database'

# Expected response:
# {
#   "available": true,
#   "latency_ms": 12,
#   "schema_version": "004_add_indexes",
#   "tables": ["alembic_version", "api_keys", ...],
#   "connections": 3,
#   "pool_size": 20,
#   "error": null
# }
```

---

## Connection Pool Tuning

Adjust pool settings based on your deployment scenario:

### Development (Default)

```bash
DB_POOL_SIZE=20
DB_POOL_OVERFLOW=10
DB_POOL_RECYCLE=3600
DB_POOL_TIMEOUT=30
```

### High-Load Testing

```bash
DB_POOL_SIZE=50
DB_POOL_OVERFLOW=20
DB_POOL_RECYCLE=1800  # Recycle more frequently under load
DB_POOL_TIMEOUT=30
```

### Single-Worker (Limited Resources)

```bash
DB_POOL_SIZE=5
DB_POOL_OVERFLOW=0
DB_POOL_RECYCLE=3600
DB_POOL_TIMEOUT=60
```

### Monitoring Pool Status

```bash
# Check active connections
curl http://localhost:8000/health | jq '.database.connections'

# Query database directly
docker-compose exec postgres psql -U ffe_user -d ffe -c \
  "SELECT datname, count(*) as connections FROM pg_stat_activity GROUP BY datname;"
```

---

## Database Migrations

### Understanding Alembic

Migrations are managed by **Alembic** and automatically applied on startup:

```bash
# Migrations automatically run in Dockerfile:
alembic upgrade head
```

### Migration Files

Stored in `alembic/versions/`:

1. **V001_initial_auth_schema.py** - API keys and audit tables
2. **V002_decision_cache_schema.py** - Decision cache and statistics
3. **V003_portfolio_memory_schema.py** - Trade outcomes and performance tracking
4. **V004_add_indexes.py** - Performance indexes and constraints

### Creating New Migrations

```bash
# Generate migration (requires models to be ORM-based)
alembic revision --autogenerate -m "Add new table"

# Review the generated migration file
cat alembic/versions/<latest>.py

# Manual migration (if needed)
alembic revision -m "Custom changes"
```

### Checking Migration Status

```bash
# Connect to database
docker-compose exec postgres psql -U ffe_user -d ffe

# Check current schema version
SELECT * FROM alembic_version;

# View all tables
\dt

# Exit
\q
```

---

## Backup & Recovery

### Automated Daily Backup

```bash
# Make backup script executable
chmod +x scripts/backup-database.sh

# Create manual backup
./scripts/backup-database.sh

# Verify backup was created
ls -lh backups/
```

### Backup Retention

- Default: 30 days
- Older backups are automatically deleted
- Configure: `BACKUP_RETENTION_DAYS` environment variable

```bash
# Example: Keep 60 days of backups
BACKUP_RETENTION_DAYS=60 ./scripts/backup-database.sh
```

### Restore from Backup

```bash
# Make restore script executable
chmod +x scripts/restore-database.sh

# Restore from specific backup
./scripts/restore-database.sh ./backups/ffe_backup_20260101_120000.sql.gz

# Confirm when prompted (type 'RESTORE')
```

### Backup Best Practices

```bash
# Schedule daily backups (crontab)
0 2 * * * /path/to/finance_feedback_engine-2.0/scripts/backup-database.sh

# Test restore monthly
0 3 1 * * /path/to/test-restore.sh

# Copy backups to external storage (cloud, NAS, etc.)
0 4 * * * aws s3 sync ./backups s3://my-bucket/ffe-backups/
```

---

## Health Checks

### Backend Health Check Endpoint

```bash
# Full health status
curl http://localhost:8000/health | jq

# Database-specific health
curl http://localhost:8000/health | jq '.database'

# Readiness check
curl http://localhost:8000/ready | jq
```

### Expected Health Response

```json
{
  "database": {
    "available": true,
    "latency_ms": 15,
    "schema_version": "004_add_indexes",
    "tables": [
      "alembic_version",
      "api_keys",
      "auth_audit",
      "decision_cache",
      "cache_stats",
      "trade_outcomes",
      "provider_performance",
      "thompson_stats"
    ],
    "connections": 12,
    "pool_size": 20,
    "error": null
  }
}
```

### Manual Database Health Check

```bash
# Check PostgreSQL availability
docker-compose exec postgres pg_isready -U ffe_user

# Expected: "accepting connections"

# Test connection from backend container
docker-compose exec backend psql postgresql://ffe_user:changeme@postgres:5432/ffe -c "SELECT 1"

# Expected: (1 row, 1 column with value 1)
```

---

## Monitoring & Metrics

### Database Size

```bash
# Check database size
docker-compose exec postgres psql -U ffe_user -d ffe -c \
  "SELECT pg_size_pretty(pg_database_size('ffe'));"
```

### Connection Pool Metrics

```bash
# Current pool status from health endpoint
curl http://localhost:8000/health | jq '.database.connections'

# Active vs idle connections
docker-compose exec postgres psql -U ffe_user -d ffe -c \
  "SELECT state, count(*) FROM pg_stat_activity WHERE datname='ffe' GROUP BY state;"
```

### Query Performance

```bash
# Slow query log (queries taking >1 second)
docker-compose exec postgres psql -U ffe_user -d ffe -c \
  "SELECT query, calls, mean_exec_time, max_exec_time FROM pg_stat_statements \
   ORDER BY max_exec_time DESC LIMIT 10;"
```

### Table Sizes

```bash
# Largest tables (helps identify growth)
docker-compose exec postgres psql -U ffe_user -d ffe -c \
  "SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size \
   FROM pg_tables \
   ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC LIMIT 10;"
```

---

## Troubleshooting

### PostgreSQL Won't Start

```bash
# Check logs
docker-compose logs postgres

# Common issues:
# - Port 5432 already in use: Change POSTGRES_PORT in .env
# - Data directory corrupted: docker-compose down && rm -rf postgres-data && docker-compose up postgres
# - Permission denied: Check directory permissions (chmod 755 on backups/)
```

### Backend Connection Failures

```bash
# Verify database is healthy
docker-compose ps postgres

# Check backend logs
docker-compose logs backend | head -50

# Test connection manually
docker-compose exec backend python -c \
  "from finance_feedback_engine.database import check_database_health; import pprint; pprint.pprint(check_database_health())"
```

### Connection Pool Exhausted

```bash
# Symptoms: "QueuePool limit exceeded" errors

# Check active connections
docker-compose exec postgres psql -U ffe_user -d ffe -c \
  "SELECT pid, usename, application_name, state FROM pg_stat_activity;"

# Increase pool size in .env
DB_POOL_SIZE=30
DB_POOL_OVERFLOW=15

# Restart backend
docker-compose restart backend
```

### Migrations Failed

```bash
# Check migration status
docker-compose exec backend alembic current

# View detailed error
docker-compose logs backend | grep -i alembic

# Rollback to previous version (if safe)
docker-compose exec backend alembic downgrade -1

# Upgrade again
docker-compose exec backend alembic upgrade head
```

### Slow Queries

```bash
# Enable slow query logging (in PostgreSQL)
docker-compose exec postgres psql -U ffe_user -d ffe -c \
  "ALTER SYSTEM SET log_min_duration_statement = 1000;"

# Reload configuration
docker-compose exec postgres psql -U ffe_user -d ffe -c \
  "SELECT pg_reload_conf();"

# Check logs
docker-compose logs postgres | grep "LOG:"
```

---

## Production Deployment

### Best Practices

1. **Use Strong Passwords**
   ```bash
   # Generate secure password
   openssl rand -base64 32
   
   # Use in .env.production
   POSTGRES_PASSWORD="your_secure_password"
   ```

2. **Configure Backup Schedule**
   ```bash
   # Daily backup at 2 AM
   0 2 * * * /path/to/scripts/backup-database.sh
   
   # Test restore monthly
   0 3 1 * * /path/to/scripts/restore-database.sh /path/to/latest/backup.sql.gz
   ```

3. **Monitor Disk Space**
   ```bash
   # Alert if < 10% free space
   df -h | grep /var/lib/postgresql/
   ```

4. **Set Connection Limits**
   ```bash
   # In postgresql.conf or via ALTER SYSTEM
   max_connections = 100
   shared_buffers = 256MB  # 25% of available RAM
   ```

5. **Enable SSL/TLS**
   ```bash
   # Update DATABASE_URL with sslmode
   DATABASE_URL="postgresql+psycopg2://user:pass@host/db?sslmode=require"
   ```

6. **Archive WAL Logs**
   ```bash
   # For point-in-time recovery
   # Requires PostgreSQL configuration
   ```

---

## Twelve-Factor Compliance

✅ **III. Config** - All settings via environment variables  
✅ **IV. Backing Services** - PostgreSQL treated as attached resource  
✅ **IX. Disposability** - Fast startup, graceful shutdown  
✅ **X. Dev/Prod Parity** - Same PostgreSQL across all environments  

---

## Performance Benchmarks

### Single-Node (docker-compose on laptop)

- Connection latency: 10-20ms
- Query throughput: 500-1000 ops/sec per worker
- Connection pool utilization: 20-40%
- Memory usage: 256MB PostgreSQL + 512MB Python

### Multi-Worker (4x Uvicorn)

- Effective throughput: 2000-4000 ops/sec
- Connection pool: Fully utilized with queuing
- Max pool size recommended: 20-30

---

## FAQ

**Q: Can I use SQLite?**  
A: No. PostgreSQL is required for multi-worker deployments. SQLite is single-writer only.

**Q: How do I scale horizontally?**  
A: Current setup is single-node. For multi-node, add PgBouncer and shared PostgreSQL cluster.

**Q: What's the backup frequency?**  
A: Default daily at 2 AM (configurable). Retention is 30 days (configurable).

**Q: Can I migrate existing SQLite data?**  
A: Not recommended for this version. Start fresh with PostgreSQL. Data migration requires custom scripts.

**Q: How do I tune for high concurrency?**  
A: Increase `DB_POOL_SIZE` (50-100), add `DB_POOL_OVERFLOW` (20-50), reduce `DB_POOL_RECYCLE` (1800).

---

## Related Documentation

- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [PostgreSQL 16 Docs](https://www.postgresql.org/docs/16/)
- [SQLAlchemy Connection Pooling](https://docs.sqlalchemy.org/en/20/core/pooling.html)
- [Docker PostgreSQL Image](https://hub.docker.com/_/postgres)

---

**Last Updated:** January 2, 2026  
**Version:** 1.0 (PostgreSQL Migration)
