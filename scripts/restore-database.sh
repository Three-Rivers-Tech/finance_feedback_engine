#!/bin/bash
# ============================================================================
# Finance Feedback Engine - PostgreSQL Restore Script
# ============================================================================
# Restores PostgreSQL database from a gzip-compressed backup
#
# Usage:
#   ./scripts/restore-database.sh <backup_file>
#   ./scripts/restore-database.sh ./backups/ffe_backup_20260101_120000.sql.gz
#
# Environment variables (use defaults if not set):
#   POSTGRES_USER: Database user (default: ffe_user)
#   POSTGRES_DB: Database name (default: ffe)
#   POSTGRES_HOSTNAME: Database hostname (default: localhost)
#   POSTGRES_PORT: Database port (default: 5432)
#
# WARNING: This script will DROP and recreate the database!
#
# ============================================================================

set -euo pipefail

# Configuration
POSTGRES_USER="${POSTGRES_USER:-ffe_user}"
POSTGRES_DB="${POSTGRES_DB:-ffe}"
POSTGRES_HOSTNAME="${POSTGRES_HOSTNAME:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"

# Validate arguments
if [ $# -eq 0 ]; then
    echo "Usage: $0 <backup_file>"
    echo "Example: $0 ./backups/ffe_backup_20260101_120000.sql.gz"
    exit 1
fi

BACKUP_FILE="$1"

# Check if backup file exists
if [ ! -f "${BACKUP_FILE}" ]; then
    echo "✗ Backup file not found: ${BACKUP_FILE}" >&2
    exit 1
fi

echo "[$(date +'%Y-%m-%d %H:%M:%S')] Starting database restore from ${BACKUP_FILE}..."
BACKUP_SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
echo "[$(date +'%Y-%m-%d %H:%M:%S')] Backup size: ${BACKUP_SIZE}"

# Confirm restoration (safety check)
echo ""
echo "⚠️  WARNING: This will DROP and recreate the database '${POSTGRES_DB}'"
echo "⚠️  All existing data will be lost!"
echo ""
read -p "Type 'RESTORE' to proceed: " -r CONFIRMATION

if [ "${CONFIRMATION}" != "RESTORE" ]; then
    echo "Restore cancelled."
    exit 0
fi

echo ""
echo "[$(date +'%Y-%m-%d %H:%M:%S')] Step 1: Dropping existing database..."

# Drop existing database (allow for connection failures)
if ! psql -h "${POSTGRES_HOSTNAME}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -t -c \
    "SELECT COUNT(*) FROM pg_stat_activity WHERE datname = '${POSTGRES_DB}';" 2>/dev/null | grep -q "0$"; then
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] Terminating existing connections..."
    psql -h "${POSTGRES_HOSTNAME}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -t -c \
        "SELECT pg_terminate_backend(pg_stat_activity.pid) FROM pg_stat_activity \
         WHERE pg_stat_activity.datname = '${POSTGRES_DB}';" 2>/dev/null || true
fi

psql -h "${POSTGRES_HOSTNAME}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -t -c \
    "DROP DATABASE IF EXISTS ${POSTGRES_DB};" 2>/dev/null || true

echo "[$(date +'%Y-%m-%d %H:%M:%S')] Step 2: Creating new database..."
psql -h "${POSTGRES_HOSTNAME}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -t -c \
    "CREATE DATABASE ${POSTGRES_DB} ENCODING utf8 LOCALE 'C';" || {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] ✗ Failed to create database" >&2
    exit 1
}

echo "[$(date +'%Y-%m-%d %H:%M:%S')] Step 3: Restoring data from backup..."
if zcat "${BACKUP_FILE}" | psql -h "${POSTGRES_HOSTNAME}" -p "${POSTGRES_PORT}" \
    -U "${POSTGRES_USER}" "${POSTGRES_DB}" > /dev/null 2>&1; then
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] ✓ Data restored successfully"
else
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] ✗ Restore failed!" >&2
    exit 1
fi

echo "[$(date +'%Y-%m-%d %H:%M:%S')] Step 4: Verifying restoration..."

# Verify schema version
SCHEMA_VERSION=$(psql -h "${POSTGRES_HOSTNAME}" -p "${POSTGRES_PORT}" \
    -U "${POSTGRES_USER}" "${POSTGRES_DB}" -t -c \
    "SELECT version_num FROM alembic_version ORDER BY version_num DESC LIMIT 1;" 2>/dev/null || echo "UNKNOWN")

if [ "${SCHEMA_VERSION}" = "UNKNOWN" ]; then
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] ✗ Schema verification failed" >&2
    exit 1
fi

# Count tables
TABLE_COUNT=$(psql -h "${POSTGRES_HOSTNAME}" -p "${POSTGRES_PORT}" \
    -U "${POSTGRES_USER}" "${POSTGRES_DB}" -t -c \
    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';" 2>/dev/null || echo "0")

echo "[$(date +'%Y-%m-%d %H:%M:%S')] ✓ Database verification successful"
echo "[$(date +'%Y-%m-%d %H:%M:%S')] Schema version: ${SCHEMA_VERSION}"
echo "[$(date +'%Y-%m-%d %H:%M:%S')] Number of tables: ${TABLE_COUNT}"

echo ""
echo "[$(date +'%Y-%m-%d %H:%M:%S')] ✓ Restore completed successfully!"
echo "[$(date +'%Y-%m-%d %H:%M:%S')] Database is ready to use."
exit 0
