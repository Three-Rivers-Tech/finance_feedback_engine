#!/bin/bash
# ============================================================================
# Finance Feedback Engine - PostgreSQL Backup Script
# ============================================================================
# Creates a gzip-compressed backup of the PostgreSQL database
# Automatically cleans up backups older than 30 days
#
# Usage:
#   ./scripts/backup-database.sh
#
# Environment variables (use defaults if not set):
#   POSTGRES_USER: Database user (default: ffe_user)
#   POSTGRES_DB: Database name (default: ffe)
#   POSTGRES_HOSTNAME: Database hostname (default: localhost)
#   POSTGRES_PORT: Database port (default: 5432)
#   BACKUP_RETENTION_DAYS: Keep backups for N days (default: 30)
#   BACKUP_PATH: Directory for backups (default: ./backups)
#
# ============================================================================

set -euo pipefail

# Configuration
POSTGRES_USER="${POSTGRES_USER:-ffe_user}"
POSTGRES_DB="${POSTGRES_DB:-ffe}"
POSTGRES_HOSTNAME="${POSTGRES_HOSTNAME:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
BACKUP_PATH="${BACKUP_PATH:-./backups}"

# Create backup directory if it doesn't exist
mkdir -p "${BACKUP_PATH}"

# Generate backup filename with timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_PATH}/ffe_backup_${TIMESTAMP}.sql.gz"

echo "[$(date +'%Y-%m-%d %H:%M:%S')] Starting database backup to ${BACKUP_FILE}..."

# Perform backup with error handling
if pg_dump \
    -h "${POSTGRES_HOSTNAME}" \
    -p "${POSTGRES_PORT}" \
    -U "${POSTGRES_USER}" \
    --verbose \
    --no-password \
    "${POSTGRES_DB}" 2>&1 | gzip > "${BACKUP_FILE}"; then

    BACKUP_SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] ✓ Backup completed successfully (${BACKUP_SIZE})"

    # List recent backups
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] Recent backups:"
    ls -lh "${BACKUP_PATH}"/ffe_backup_*.sql.gz 2>/dev/null | tail -5 || true

else
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] ✗ Backup failed!" >&2
    exit 1
fi

# Clean up old backups
echo "[$(date +'%Y-%m-%d %H:%M:%S')] Cleaning backups older than ${BACKUP_RETENTION_DAYS} days..."
BACKUP_COUNT_BEFORE=$(find "${BACKUP_PATH}" -name "ffe_backup_*.sql.gz" -type f | wc -l)

find "${BACKUP_PATH}" -name "ffe_backup_*.sql.gz" -type f -mtime +${BACKUP_RETENTION_DAYS} -delete

BACKUP_COUNT_AFTER=$(find "${BACKUP_PATH}" -name "ffe_backup_*.sql.gz" -type f | wc -l)
DELETED=$((BACKUP_COUNT_BEFORE - BACKUP_COUNT_AFTER))

if [ ${DELETED} -gt 0 ]; then
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] Deleted ${DELETED} old backup(s)"
else
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] No old backups to delete"
fi

echo "[$(date +'%Y-%m-%d %H:%M:%S')] ✓ Backup process completed successfully"
exit 0
